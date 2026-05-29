from math import ceil, cos, isfinite, radians

from django.db.models import Avg, Count
from django.utils import timezone

from .models import GridCell


METERS_PER_DEGREE = 111000
MAX_GENERAL_USER_GRID_CELLS = 500
MAX_GENERAL_USER_GRID_HEIGHT_METERS = 30000
MAX_GENERAL_USER_GRID_WIDTH_METERS = 30000
MIN_LONGITUDE_COSINE = 0.01
INITIAL_SCORE_MIN = 0.0
INITIAL_SCORE_MAX = 3.0


def _clamp_initial_score(score):
    return min(max(score, INITIAL_SCORE_MIN), INITIAL_SCORE_MAX)


def _feature_number(feature_summary, key, default=0.0):
    value = feature_summary.get(key, default)
    if isinstance(value, bool):
        raise ValueError(f"{key} は数値で指定してください。")

    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{key} は数値で指定してください。")

    if not isfinite(value) or value < 0:
        raise ValueError(f"{key} は 0 以上の有限数で指定してください。")

    return value


def _feature_ratio(feature_summary, key, default=0.0):
    value = _feature_number(feature_summary, key, default)
    if value > 1:
        raise ValueError(f"{key} は 0.0 から 1.0 の範囲で指定してください。")

    return value


def _bounds_number(bounds, key):
    value = bounds.get(key)
    if isinstance(value, bool):
        raise ValueError(f"{key} は数値で指定してください。")

    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{key} は数値で指定してください。")

    if not isfinite(value):
        raise ValueError(f"{key} は有限数で指定してください。")

    return value


def _normalize_bounds(bounds):
    if not isinstance(bounds, dict):
        raise ValueError("bounds は辞書で指定してください。")

    normalized_bounds = {
        "north": _bounds_number(bounds, "north"),
        "south": _bounds_number(bounds, "south"),
        "east": _bounds_number(bounds, "east"),
        "west": _bounds_number(bounds, "west"),
    }
    if normalized_bounds["north"] <= normalized_bounds["south"]:
        raise ValueError("north は south より大きい値にしてください。")
    if normalized_bounds["east"] <= normalized_bounds["west"]:
        raise ValueError("east は west より大きい値にしてください。")

    return normalized_bounds


def feature_intersects_grid_cell(feature_bounds, grid_cell_bounds):
    """Return True when two bboxes overlap with positive area."""
    feature_bounds = _normalize_bounds(feature_bounds)
    grid_cell_bounds = _normalize_bounds(grid_cell_bounds)

    return (
        max(feature_bounds["south"], grid_cell_bounds["south"])
        < min(feature_bounds["north"], grid_cell_bounds["north"])
        and max(feature_bounds["west"], grid_cell_bounds["west"])
        < min(feature_bounds["east"], grid_cell_bounds["east"])
    )


def _feature_covers_grid_cell(feature_bounds, grid_cell_bounds):
    feature_bounds = _normalize_bounds(feature_bounds)
    grid_cell_bounds = _normalize_bounds(grid_cell_bounds)

    return (
        feature_bounds["north"] >= grid_cell_bounds["north"]
        and feature_bounds["south"] <= grid_cell_bounds["south"]
        and feature_bounds["east"] >= grid_cell_bounds["east"]
        and feature_bounds["west"] <= grid_cell_bounds["west"]
    )


def build_feature_summary_for_grid_cell(grid_cell_bounds, map_features):
    """Build feature summary for one GridCell from provisional bbox features."""
    grid_cell_bounds = _normalize_bounds(grid_cell_bounds)
    if not isinstance(map_features, list):
        raise ValueError("map_features はリストで指定してください。")

    feature_summary = {
        "building_count": 0,
        "road_count": 0,
        "water_coverage_ratio": 0.0,
        "forest_coverage_ratio": 0.0,
        "has_park": False,
        "has_river": False,
        "is_coastal": False,
    }

    for feature in map_features:
        if not isinstance(feature, dict):
            raise ValueError("map_features の各要素は辞書で指定してください。")

        feature_kind = feature.get("kind")
        if feature_kind not in {
            "building",
            "road",
            "water",
            "forest",
            "park",
            "river",
            "coastline",
        }:
            continue

        feature_bounds = _normalize_bounds(feature.get("bounds"))
        if not feature_intersects_grid_cell(feature_bounds, grid_cell_bounds):
            continue

        if feature_kind == "building":
            feature_summary["building_count"] += 1
        elif feature_kind == "road":
            feature_summary["road_count"] += 1
        elif feature_kind == "water":
            feature_summary["water_coverage_ratio"] = max(
                feature_summary["water_coverage_ratio"],
                1.0
                if _feature_covers_grid_cell(feature_bounds, grid_cell_bounds)
                else 0.5,
            )
        elif feature_kind == "forest":
            feature_summary["forest_coverage_ratio"] = max(
                feature_summary["forest_coverage_ratio"],
                1.0
                if _feature_covers_grid_cell(feature_bounds, grid_cell_bounds)
                else 0.5,
            )
        elif feature_kind == "park":
            feature_summary["has_park"] = True
        elif feature_kind == "river":
            feature_summary["has_river"] = True
        elif feature_kind == "coastline":
            feature_summary["is_coastal"] = True

    return feature_summary


def build_feature_summaries_for_grid_cells(grid_cells, map_features):
    """Build feature summaries keyed by each GridCell position."""
    feature_summaries = {}

    for grid_cell in grid_cells:
        grid_cell_bounds = {
            "north": grid_cell.north,
            "south": grid_cell.south,
            "east": grid_cell.east,
            "west": grid_cell.west,
        }
        feature_summaries[(grid_cell.row_index, grid_cell.col_index)] = (
            build_feature_summary_for_grid_cell(grid_cell_bounds, map_features)
        )

    return feature_summaries


def build_feature_summaries_for_grid_cell_contexts(grid_cell_contexts, map_features):
    """Build feature summaries keyed by each unsaved GridCell context position."""
    if not isinstance(grid_cell_contexts, list):
        raise ValueError("grid_cell_contexts はリストで指定してください。")

    feature_summaries = {}

    for grid_cell_context in grid_cell_contexts:
        if not isinstance(grid_cell_context, dict):
            raise ValueError("grid_cell_contexts の各要素は辞書で指定してください。")

        row_index = grid_cell_context.get("row_index")
        col_index = grid_cell_context.get("col_index")
        if (
            not isinstance(row_index, int)
            or isinstance(row_index, bool)
            or not isinstance(col_index, int)
            or isinstance(col_index, bool)
        ):
            raise ValueError("row_index と col_index は整数で指定してください。")

        grid_cell_bounds = {
            "north": grid_cell_context.get("north"),
            "south": grid_cell_context.get("south"),
            "east": grid_cell_context.get("east"),
            "west": grid_cell_context.get("west"),
        }
        feature_summaries[(row_index, col_index)] = (
            build_feature_summary_for_grid_cell(grid_cell_bounds, map_features)
        )

    return feature_summaries


def calculate_initial_score_from_feature_summary(feature_summary):
    """Calculate a provisional 0.0-3.0 initial score from feature summary data."""
    if not isinstance(feature_summary, dict):
        raise ValueError("feature_summary は辞書で指定してください。")

    building_count = _feature_number(feature_summary, "building_count")
    road_count = _feature_number(feature_summary, "road_count")
    water_coverage_ratio = _feature_ratio(feature_summary, "water_coverage_ratio")
    forest_coverage_ratio = _feature_ratio(feature_summary, "forest_coverage_ratio")
    has_park = bool(feature_summary.get("has_park", False))
    has_river = bool(feature_summary.get("has_river", False))
    is_coastal = bool(feature_summary.get("is_coastal", False))

    base_score = 0.3
    base_score += min(building_count / 20, 1.0) * 0.7
    base_score += min(road_count / 10, 1.0) * 0.5

    feature_categories = [
        building_count > 0,
        road_count > 0,
        has_park,
        has_river,
        is_coastal,
        water_coverage_ratio > 0,
        forest_coverage_ratio > 0,
    ]
    diversity_bonus = min(sum(feature_categories) * 0.18, 0.9)

    context_bonus = 0.0
    if has_park and building_count > 0:
        context_bonus += 0.2
    if has_river and building_count > 0:
        context_bonus += 0.25
    if is_coastal and (building_count > 0 or road_count > 0):
        context_bonus += 0.3
    if forest_coverage_ratio > 0 and building_count > 0:
        context_bonus += 0.15

    penalty = 0.0
    if water_coverage_ratio >= 0.95:
        penalty += 2.4
    if forest_coverage_ratio >= 0.95 and building_count == 0 and road_count == 0:
        penalty += 2.0
    if building_count == 0 and road_count == 0:
        penalty += 0.6

    raw_score = base_score + diversity_bonus + context_bonus - penalty
    return _clamp_initial_score(raw_score)


def determine_initial_score_for_grid_cell(
    *,
    region_feature_level,
    grid_context=None,
):
    """Return the initial GridCell score as a 0.0-3.0 float value."""
    if isinstance(grid_context, dict) and "feature_summary" in grid_context:
        return calculate_initial_score_from_feature_summary(
            grid_context["feature_summary"]
        )

    if isinstance(region_feature_level, bool):
        raise ValueError("region_feature_level は 0.0 から 3.0 の数値で指定してください。")

    try:
        initial_score = float(region_feature_level)
    except (TypeError, ValueError):
        raise ValueError("region_feature_level は 0.0 から 3.0 の数値で指定してください。")

    if not isfinite(initial_score) or initial_score < 0.0 or initial_score > 3.0:
        raise ValueError("region_feature_level は 0.0 から 3.0 の数値で指定してください。")

    return initial_score


def _validate_positive_grid_dimensions(grid_size_meters, rows, cols):
    try:
        grid_size_meters = float(grid_size_meters)
    except (TypeError, ValueError):
        raise ValueError("grid_size_meters は 0 より大きい値にしてください。")

    if not isinstance(rows, int) or isinstance(rows, bool):
        raise ValueError("rows と cols は正の整数で指定してください。")
    if not isinstance(cols, int) or isinstance(cols, bool):
        raise ValueError("rows と cols は正の整数で指定してください。")
    if rows <= 0 or cols <= 0:
        raise ValueError("rows と cols は正の整数で指定してください。")
    if not isfinite(grid_size_meters) or grid_size_meters <= 0:
        raise ValueError("grid_size_meters は 0 より大きい値にしてください。")

    return grid_size_meters


def calculate_bounds_from_center(
    center_lat,
    center_lng,
    grid_size_meters,
    rows,
    cols,
):
    """Calculate MapArea bounds from center position and grid dimensions."""
    grid_size_meters = _validate_positive_grid_dimensions(
        grid_size_meters,
        rows,
        cols,
    )

    try:
        center_lat = float(center_lat)
        center_lng = float(center_lng)
    except (TypeError, ValueError):
        raise ValueError("center_lat と center_lng は数値で指定してください。")

    if not isfinite(center_lat) or not -90 < center_lat < 90:
        raise ValueError("center_lat は -90 より大きく 90 より小さい値にしてください。")
    if not isfinite(center_lng) or not -180 <= center_lng <= 180:
        raise ValueError("center_lng は -180 以上 180 以下の値にしてください。")

    longitude_cosine = cos(radians(center_lat))
    if abs(longitude_cosine) < MIN_LONGITUDE_COSINE:
        raise ValueError("center_lat が極に近すぎるため経度方向を計算できません。")

    lat_step = grid_size_meters / METERS_PER_DEGREE
    lng_step = grid_size_meters / (METERS_PER_DEGREE * longitude_cosine)
    height_deg = lat_step * rows
    width_deg = lng_step * cols

    return {
        "north": center_lat + height_deg / 2,
        "south": center_lat - height_deg / 2,
        "east": center_lng + width_deg / 2,
        "west": center_lng - width_deg / 2,
        "lat_step": lat_step,
        "lng_step": lng_step,
        "rows": rows,
        "cols": cols,
    }


def validate_center_grid_limits(
    grid_size_meters,
    rows,
    cols,
    is_staff=False,
):
    """Validate general-user limits for center-based MapArea creation."""
    grid_size_meters = _validate_positive_grid_dimensions(
        grid_size_meters,
        rows,
        cols,
    )

    if is_staff:
        return

    if rows * cols > MAX_GENERAL_USER_GRID_CELLS:
        raise ValueError(
            "一般ユーザーは rows * cols が 500 を超える MapArea を作成できません。"
        )
    if grid_size_meters * rows > MAX_GENERAL_USER_GRID_HEIGHT_METERS:
        raise ValueError(
            "一般ユーザーは南北方向が 30000m を超える MapArea を作成できません。"
        )
    if grid_size_meters * cols > MAX_GENERAL_USER_GRID_WIDTH_METERS:
        raise ValueError(
            "一般ユーザーは東西方向が 30000m を超える MapArea を作成できません。"
        )


def _validate_positive_step(step, field_name):
    try:
        step = float(step)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} は 0 より大きい有限数で指定してください。")

    if not isfinite(step) or step <= 0:
        raise ValueError(f"{field_name} は 0 より大きい有限数で指定してください。")

    return step


def build_grid_cell_contexts_for_area(
    map_area,
    rows=None,
    cols=None,
    lat_step=None,
    lng_step=None,
):
    """Build GridCell context dictionaries without saving them."""
    if map_area.grid_size_meters <= 0:
        raise ValueError("grid_size_meters は 0 より大きい値にしてください。")
    if map_area.north <= map_area.south:
        raise ValueError("north は south より大きい値にしてください。")
    if map_area.east <= map_area.west:
        raise ValueError("east は west より大きい値にしてください。")

    explicit_grid_args = (rows, cols, lat_step, lng_step)
    specified_arg_count = sum(arg is not None for arg in explicit_grid_args)
    uses_explicit_grid_size = specified_arg_count == len(explicit_grid_args)

    if specified_arg_count not in (0, len(explicit_grid_args)):
        raise ValueError(
            "rows / cols / lat_step / lng_step はすべて指定するか、"
            "すべて省略してください。"
        )

    if uses_explicit_grid_size:
        # 中心座標方式では、呼び出し側が指定した行数・列数をそのまま使う。
        _validate_positive_grid_dimensions(map_area.grid_size_meters, rows, cols)
        lat_step = _validate_positive_step(lat_step, "lat_step")
        lng_step = _validate_positive_step(lng_step, "lng_step")
        row_count = rows
        col_count = cols
    else:
        lat_step = map_area.grid_size_meters / METERS_PER_DEGREE
        lng_step = map_area.grid_size_meters / METERS_PER_DEGREE
        row_count = ceil((map_area.north - map_area.south) / lat_step)
        col_count = ceil((map_area.east - map_area.west) / lng_step)

    grid_cell_contexts = []
    for row_index in range(row_count):
        cell_north = map_area.north - row_index * lat_step
        if uses_explicit_grid_size:
            if row_index == row_count - 1:
                cell_south = map_area.south
            else:
                cell_south = cell_north - lat_step
        else:
            cell_south = max(map_area.south, cell_north - lat_step)

        for col_index in range(col_count):
            cell_west = map_area.west + col_index * lng_step
            if uses_explicit_grid_size:
                if col_index == col_count - 1:
                    cell_east = map_area.east
                else:
                    cell_east = cell_west + lng_step
            else:
                cell_east = min(map_area.east, cell_west + lng_step)

            grid_cell_contexts.append(
                {
                    "row_index": row_index,
                    "col_index": col_index,
                    "north": cell_north,
                    "south": cell_south,
                    "east": cell_east,
                    "west": cell_west,
                }
            )

    return grid_cell_contexts


def generate_grid_cells_for_area(
    map_area,
    rows=None,
    cols=None,
    lat_step=None,
    lng_step=None,
    feature_summaries_by_position=None,
):
    """Generate and save GridCell rows for one MapArea."""
    if feature_summaries_by_position is None:
        feature_summaries_by_position = {}
    elif not isinstance(feature_summaries_by_position, dict):
        raise ValueError("feature_summaries_by_position は辞書で指定してください。")

    if map_area.grid_cells.exists():
        raise ValueError("この MapArea には既に GridCell があります。")

    grid_cell_contexts = build_grid_cell_contexts_for_area(
        map_area,
        rows=rows,
        cols=cols,
        lat_step=lat_step,
        lng_step=lng_step,
    )

    grid_cells = []
    for grid_context in grid_cell_contexts:
        row_index = grid_context["row_index"]
        col_index = grid_context["col_index"]
        feature_summary = feature_summaries_by_position.get((row_index, col_index))
        if feature_summary is not None:
            grid_context["feature_summary"] = feature_summary

        initial_score = determine_initial_score_for_grid_cell(
            region_feature_level=map_area.region_feature_level,
            grid_context=grid_context,
        )
        grid_cells.append(
            GridCell(
                area=map_area,
                row_index=row_index,
                col_index=col_index,
                north=grid_context["north"],
                south=grid_context["south"],
                east=grid_context["east"],
                west=grid_context["west"],
                initial_score=initial_score,
                average_user_score=0,
                rating_count=0,
                calculated_score=initial_score,
                score_updated_at=None,
            )
        )

    return GridCell.objects.bulk_create(grid_cells)


def update_grid_cell_score(grid_cell):
    """Recalculate and save score fields for one GridCell."""
    rating_summary = grid_cell.ratings.aggregate(
        average_score=Avg("score"),
        rating_count=Count("id"),
    )
    rating_count = rating_summary["rating_count"]

    if rating_count == 0:
        grid_cell.average_user_score = 0
        grid_cell.rating_count = 0
        grid_cell.calculated_score = grid_cell.initial_score
        grid_cell.score_updated_at = None
    else:
        average_user_score = rating_summary["average_score"]
        grid_cell.average_user_score = average_user_score
        grid_cell.rating_count = rating_count
        grid_cell.calculated_score = (
            grid_cell.initial_score + average_user_score
        ) / 2
        grid_cell.score_updated_at = timezone.now()

    grid_cell.save(
        update_fields=[
            "average_user_score",
            "rating_count",
            "calculated_score",
            "score_updated_at",
            "updated_at",
        ]
    )

    return grid_cell
