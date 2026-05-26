from math import ceil, cos, isfinite, radians

from django.db.models import Avg, Count
from django.utils import timezone

from .models import GridCell


METERS_PER_DEGREE = 111000
MAX_GENERAL_USER_GRID_CELLS = 500
MAX_GENERAL_USER_GRID_HEIGHT_METERS = 30000
MAX_GENERAL_USER_GRID_WIDTH_METERS = 30000
MIN_LONGITUDE_COSINE = 0.01


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


def generate_grid_cells_for_area(
    map_area,
    rows=None,
    cols=None,
    lat_step=None,
    lng_step=None,
):
    """Generate and save GridCell rows for one MapArea."""
    if map_area.grid_size_meters <= 0:
        raise ValueError("grid_size_meters は 0 より大きい値にしてください。")
    if map_area.north <= map_area.south:
        raise ValueError("north は south より大きい値にしてください。")
    if map_area.east <= map_area.west:
        raise ValueError("east は west より大きい値にしてください。")
    if map_area.grid_cells.exists():
        raise ValueError("この MapArea には既に GridCell があります。")

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

    grid_cells = []
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

            grid_cells.append(
                GridCell(
                    area=map_area,
                    row_index=row_index,
                    col_index=col_index,
                    north=cell_north,
                    south=cell_south,
                    east=cell_east,
                    west=cell_west,
                    initial_score=0,
                    average_user_score=0,
                    rating_count=0,
                    calculated_score=0,
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
