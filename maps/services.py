import logging
from collections import Counter
from math import ceil, cos, isfinite, radians
from time import perf_counter

import requests
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from .models import GridCell, MapArea


# MapArea creation, OSM feature collection, auto scoring, and score aggregation live
# together here because each step feeds the next one in the map preview workflow.
logger = logging.getLogger(__name__)

METERS_PER_DEGREE = 111000
MAX_GENERAL_USER_GRID_CELLS = 500
MAX_GENERAL_USER_GRID_HEIGHT_METERS = 30000
MAX_GENERAL_USER_GRID_WIDTH_METERS = 30000
MIN_LONGITUDE_COSINE = 0.01
INITIAL_SCORE_MIN = 0.0
INITIAL_SCORE_MAX = 3.0
BASE_INITIAL_SCORE = 0.2
BUILDING_BASE_SCORE_MAX_BONUS = 0.4
BUILDING_COUNT_FOR_MAX_BASE_SCORE = 20
AUTO_SCORE_FETCH_BUILDINGS = True
# 比較時だけ True にすると、広範囲の building 取得除外を試せる。
AUTO_SCORE_SKIP_BUILDINGS_WHEN_LARGE = False
# 画面側の2km制限より手前で、building取得有無を比較するための調査用しきい値。
AUTO_SCORE_BUILDING_SKIP_LONG_SIDE_METERS = 1500
AUTO_SCORE_BUILDING_MODE_GEOMETRY = "geometry"
AUTO_SCORE_BUILDING_MODE_CENTER = "center"
AUTO_SCORE_BUILDING_MODES = (
    AUTO_SCORE_BUILDING_MODE_GEOMETRY,
    AUTO_SCORE_BUILDING_MODE_CENTER,
)
AUTO_SCORE_BUILDING_MODE = AUTO_SCORE_BUILDING_MODE_CENTER
# 分割取得は Overpass の 429 制限に当たりやすい場合があるため、
# 現時点では比較用としてデフォルト無効。
AUTO_SCORE_SPLIT_OVERPASS_FETCH = False
AUTO_SCORE_OVERPASS_SPLIT_ROWS = 2
AUTO_SCORE_OVERPASS_SPLIT_COLS = 2
# station / landmark など、詳細 geometry が不要そうな地物を軽量出力で比較するための調査用フラグ。
AUTO_SCORE_LIGHTWEIGHT_OVERPASS_OUTPUT = False
ROAD_BASE_SCORE_MAX_BONUS = 0.0
ROAD_COUNT_FOR_MAX_BASE_SCORE = 10
WATERFRONT_CONTEXT_BONUS = 0.15
SURFACE_RAILWAY_CONTEXT_BONUS = 0.10
SURFACE_STATION_CONTEXT_BONUS = 0.30
SUBWAY_STATION_CONTEXT_BONUS = 0.20
PUBLIC_TRANSPORT_STATION_CONTEXT_BONUS = 0.20
MOTORWAY_CONTEXT_BONUS = 0.15
TRUNK_CONTEXT_BONUS = 0.07
MIN_FOREST_COVERAGE_RATIO_FOR_SCORE = 0.10
RAILWAY_SURFACE_TYPES = {"rail", "light_rail", "tram"}
RAILWAY_UNDERGROUND_TYPES = {"subway"}
RAILWAY_TARGET_TYPES = RAILWAY_SURFACE_TYPES | RAILWAY_UNDERGROUND_TYPES
STATION_RAILWAY_TYPES = {"station", "halt"}
EXPRESSWAY_HIGHWAY_TYPES = {"motorway", "motorway_link", "trunk", "trunk_link"}
MAX_EXPRESSWAY_BOUNDS_AREA_RATIO_FOR_LOG = 20.0
MAX_EXPRESSWAY_BOUNDS_LENGTH_RATIO_FOR_LOG = 10.0
MAX_ROAD_BOUNDS_AREA_RATIO_FOR_COUNT = 20.0
MAX_ROAD_BOUNDS_LENGTH_RATIO_FOR_COUNT = 10.0
MAX_RIVER_BOUNDS_AREA_RATIO_FOR_INTERSECTION = 20.0
MAX_RIVER_BOUNDS_LENGTH_RATIO_FOR_INTERSECTION = 10.0
MIN_LARGE_RIVER_OVERLAP_RATIO_FOR_INTERSECTION = 0.05
MIN_RIVER_COVERAGE_RATIO_FOR_HAS_RIVER = 0.05
LARGE_WATERWAY_RIVER_BOUNDS_AREA_RATIO_TO_MAP = 1.0
MAX_WATERWAY_RIVER_BOUNDS_AREA_RATIO_TO_MAP_FOR_GRID_CELL = (
    LARGE_WATERWAY_RIVER_BOUNDS_AREA_RATIO_TO_MAP
)


class FeatureSummariesByPosition(dict):
    """Dict of feature summaries with optional log-only river aggregate data."""


WATERWAY_SUMMARY_KEYS = ("river", "stream", "canal", "unknown")
STATION_SUMMARY_KEYS = (
    "railway_station",
    "railway_halt",
    "subway_station",
    "bus_station",
    "public_transport_station",
    "unknown",
)
SCORED_STATION_SUMMARY_TYPES = {
    "railway_station",
    "railway_halt",
    "subway_station",
    "public_transport_station",
}
STATION_PROXIMITY_SUMMARY_TYPES = {
    "railway_station",
    "railway_halt",
    "public_transport_station",
}
STATION_DENSE_CLUSTER_DISTANCE_METERS = 150
STATION_BROAD_CLUSTER_DISTANCE_METERS = 300
STATION_PROXIMITY_NEAR_DISTANCE_METERS = 150
STATION_PROXIMITY_MID_DISTANCE_METERS = 300
STATION_PROXIMITY_NEAR_CONTEXT_BONUS = 0.20
STATION_PROXIMITY_MID_CONTEXT_BONUS = 0.10
STATION_MAJOR_CLUSTER_MIN_FEATURES = 4
STATION_DENSITY_MAJOR_CLUSTER_MIN_FEATURES = 3
PARK_WATERFRONT_COMBO_CONTEXT_BONUS = 0.15
HIGH_CONTEXT_3_CONTEXT_BONUS = 0.10
HIGH_CONTEXT_4_CONTEXT_BONUS = 0.20
HIGH_CONTEXT_5_CONTEXT_BONUS = 0.25
DEFAULT_GRID_SIZE_SCORE_MULTIPLIER = 1.0
AUTO_SCORE_BREAKDOWN_SCORE_KEYS = (
    "base_score",
    "diversity_bonus",
    "context_bonus",
    "penalty",
    "raw_score",
    "clamped_score",
)
AUTO_SCORE_BREAKDOWN_BONUS_KEYS = (
    "surface_railway_context_bonus",
    "surface_station_context_bonus",
    "subway_station_context_bonus",
    "public_transport_station_context_bonus",
    "station_density_bonus",
    "station_proximity_bonus",
    "motorway_context_bonus",
    "trunk_context_bonus",
    "landmark_context_bonus",
    "castle_proximity_bonus",
    "park_waterfront_combo_bonus",
    "high_context_bonus",
)
AUTO_SCORE_BREAKDOWN_FLAG_KEYS = (
    "has_park_context",
    "has_river_context",
    "has_forest_context",
    "has_coastal_context",
    "has_waterfront_context",
    "has_surface_railway_context",
    "has_surface_station_context",
    "has_subway_station_context",
    "has_public_transport_station_context",
    "has_dense_station_cluster_context",
    "has_major_station_cluster_context",
    "has_station_proximity_context",
    "has_motorway_context",
    "has_trunk_context",
    "has_landmark_context",
    "has_castle_proximity_context",
    "has_park_waterfront_combo_context",
    "has_high_context_3_context",
    "has_high_context_4_context",
    "has_high_context_5_context",
    "has_water_penalty",
    "has_forest_penalty",
    "has_empty_cell_penalty",
)
AUTO_SCORE_BREAKDOWN_COUNT_KEYS = (
    "feature_category_count",
    "context_candidate_count",
    "scored_station_count",
    "station_cluster_count",
    "dense_station_cluster_count",
)
LANDMARK_TOURISM_TYPES = {"attraction", "museum", "gallery", "viewpoint"}
LANDMARK_HISTORIC_TYPES = {
    "castle",
    "monument",
    "memorial",
    "ruins",
    "archaeological_site",
}
LANDMARK_SUMMARY_KEYS = (
    "tourism_attraction",
    "tourism_museum",
    "tourism_gallery",
    "tourism_viewpoint",
    "historic_castle",
    "historic_monument",
    "historic_memorial",
    "historic_ruins",
    "historic_archaeological_site",
    "unknown",
)
LANDMARK_CONTEXT_BONUS_CAP = 1.0
LANDMARK_CONTEXT_BONUSES = {
    "tourism_attraction": 0.35,
    "tourism_museum": 0.20,
    "tourism_gallery": 0.10,
    "tourism_viewpoint": 0.40,
    "historic_castle": 0.80,
    "historic_monument": 0.20,
    "historic_memorial": 0.15,
    "historic_ruins": 0.40,
    "historic_archaeological_site": 0.45,
}
CASTLE_NEAR_DISTANCE_METERS = 250
CASTLE_MID_DISTANCE_METERS = 500
CASTLE_FAR_DISTANCE_METERS = 800
CASTLE_NEAR_CONTEXT_BONUS = 0.65
CASTLE_MID_CONTEXT_BONUS = 0.35
CASTLE_FAR_CONTEXT_BONUS = 0.15
EXPRESSWAY_SUMMARY_KEYS = (
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "unknown",
)


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


def calculate_grid_size_score_multiplier(grid_size_meters):
    """Return the auto-score bonus multiplier for a GridCell size.

    Large cells naturally contain more features, so presence-based bonuses are
    softened as grid_size_meters grows. 300m is treated as the neutral size.
    """
    if grid_size_meters is None:
        return DEFAULT_GRID_SIZE_SCORE_MULTIPLIER

    try:
        grid_size = float(grid_size_meters)
    except (TypeError, ValueError):
        return DEFAULT_GRID_SIZE_SCORE_MULTIPLIER

    if grid_size <= 100:
        return 1.4
    if grid_size <= 200:
        return 1.25
    if grid_size <= 300:
        return 1.0
    if grid_size <= 400:
        return 0.95
    if grid_size <= 500:
        return 0.9
    if grid_size < 1000:
        return 0.8
    return 0.7


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


def _normalize_positive_int(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name} は 1 以上の整数で指定してください。")

    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} は 1 以上の整数で指定してください。")

    if value <= 0:
        raise ValueError(f"{name} は 1 以上の整数で指定してください。")

    return value


def _response_text_preview(response_text, max_length=160):
    response_text = str(response_text or "")
    response_text = " ".join(response_text.split())
    return response_text[:max_length]


def _status_code_from_error(error):
    error_message = str(error)
    marker = "status_code="
    if marker not in error_message:
        return None

    status_code_text = error_message.split(marker, maxsplit=1)[1].split(
        maxsplit=1
    )[0]
    try:
        return int(status_code_text)
    except ValueError:
        return None


def normalize_auto_score_building_mode(building_mode=None):
    if building_mode is None:
        building_mode = AUTO_SCORE_BUILDING_MODE
    if building_mode not in AUTO_SCORE_BUILDING_MODES:
        raise ValueError(
            "building_mode は geometry または center で指定してください。"
        )
    return building_mode


def _point_number(point, key):
    value = point.get(key)
    if isinstance(value, bool):
        raise ValueError(f"{key} は数値で指定してください。")

    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{key} は数値で指定してください。")

    if not isfinite(value):
        raise ValueError(f"{key} は有限数で指定してください。")

    return value


def _normalize_point(point):
    if not isinstance(point, dict):
        raise ValueError("point は辞書で指定してください。")

    return {
        "lat": _point_number(point, "lat"),
        "lon": _point_number(point, "lon"),
    }


def _point_in_bounds(point, bounds):
    point = _normalize_point(point)
    bounds = _normalize_bounds(bounds)
    return (
        bounds["south"] <= point["lat"] <= bounds["north"]
        and bounds["west"] <= point["lon"] <= bounds["east"]
    )


def classify_osm_element(tags):
    """Classify OSM tags into one app-level map feature kind.

    OSM has many tag combinations. The app keeps only the kinds that currently
    affect scoring and leaves unsupported tags unused instead of guessing.
    """
    if not isinstance(tags, dict):
        raise ValueError("tags は辞書で指定してください。")

    waterway = tags.get("waterway")
    natural = tags.get("natural")
    landuse = tags.get("landuse")
    leisure = tags.get("leisure")
    railway = tags.get("railway")
    highway = tags.get("highway")
    tourism = tags.get("tourism")
    historic = tags.get("historic")

    if natural == "coastline":
        return "coastline"
    if waterway in {"river", "stream", "canal"}:
        return "river"
    if natural == "water" or "water" in tags or waterway == "riverbank":
        return "water"
    if landuse == "forest" or natural == "wood":
        return "forest"
    if leisure in {"park", "garden"}:
        return "park"
    if (
        railway in STATION_RAILWAY_TYPES
        or tags.get("station") == "subway"
        or tags.get("public_transport") == "station"
        or tags.get("amenity") == "bus_station"
    ):
        return "station"
    if railway in RAILWAY_TARGET_TYPES:
        return "railway"
    if highway in EXPRESSWAY_HIGHWAY_TYPES:
        return "expressway"
    if tourism in LANDMARK_TOURISM_TYPES or historic in LANDMARK_HISTORIC_TYPES:
        return "landmark"
    if "highway" in tags:
        return "road"
    if "building" in tags:
        return "building"

    return None


def build_bounds_from_osm_element(element):
    """Build normalized bbox bounds from one OSM element."""
    if not isinstance(element, dict):
        raise ValueError("element は辞書で指定してください。")

    if "bounds" in element:
        bounds = element["bounds"]
        if isinstance(bounds, dict) and {
            "minlat",
            "minlon",
            "maxlat",
            "maxlon",
        }.issubset(bounds):
            bounds = {
                "north": bounds["maxlat"],
                "south": bounds["minlat"],
                "east": bounds["maxlon"],
                "west": bounds["minlon"],
            }

        return _normalize_bounds(bounds)

    geometry = element.get("geometry")
    if not geometry:
        return None

    north = south = east = west = None
    for point in geometry:
        if not isinstance(point, dict):
            return None

        try:
            lat = float(point["lat"])
            lon = float(point["lon"])
        except (KeyError, TypeError, ValueError):
            return None

        if not isfinite(lat) or not isfinite(lon):
            return None

        north = lat if north is None else max(north, lat)
        south = lat if south is None else min(south, lat)
        east = lon if east is None else max(east, lon)
        west = lon if west is None else min(west, lon)

    try:
        return _normalize_bounds(
            {
                "north": north,
                "south": south,
                "east": east,
                "west": west,
            }
        )
    except ValueError:
        return None


def build_center_from_osm_element(element):
    """Build a normalized center point from one OSM element when available."""
    if not isinstance(element, dict):
        raise ValueError("element は辞書で指定してください。")

    center = element.get("center")
    if center is not None:
        try:
            return _normalize_point(center)
        except ValueError:
            return None

    if "lat" in element and "lon" in element:
        try:
            return _normalize_point({"lat": element["lat"], "lon": element["lon"]})
        except ValueError:
            return None

    bounds = build_bounds_from_osm_element(element)
    if bounds is None:
        return None

    return {
        "lat": (bounds["north"] + bounds["south"]) / 2,
        "lon": (bounds["east"] + bounds["west"]) / 2,
    }


def build_map_feature_from_osm_element(element):
    """Build one app feature from one OSM element when it has usable bounds."""
    if not isinstance(element, dict):
        raise ValueError("element は辞書で指定してください。")

    kind = classify_osm_element(element.get("tags", {}))
    if kind is None:
        return None

    bounds = build_bounds_from_osm_element(element)
    center = (
        build_center_from_osm_element(element)
        if kind in {"building", "station", "landmark"}
        else None
    )
    if bounds is None and center is None:
        return None

    map_feature = {
        "kind": kind,
        "source": "osm",
        "source_type": element.get("type"),
        "source_id": element.get("id"),
    }
    if bounds is not None:
        map_feature["bounds"] = bounds
    if center is not None:
        map_feature["center"] = center

    tags = element.get("tags", {})
    waterway = tags.get("waterway")
    if waterway:
        map_feature["source_waterway"] = waterway
    railway = tags.get("railway")
    if railway:
        map_feature["source_railway"] = railway
    if "station" in tags:
        map_feature["source_station"] = tags.get("station")
    if "public_transport" in tags:
        map_feature["source_public_transport"] = tags.get("public_transport")
    if "amenity" in tags:
        map_feature["source_amenity"] = tags.get("amenity")
    if "highway" in tags:
        map_feature["source_highway"] = tags.get("highway")
    if "tourism" in tags:
        map_feature["source_tourism"] = tags.get("tourism")
    if "historic" in tags:
        map_feature["source_historic"] = tags.get("historic")
    if "tunnel" in tags:
        map_feature["source_tunnel"] = tags.get("tunnel")
    if "layer" in tags:
        map_feature["source_layer"] = tags.get("layer")
    if "bridge" in tags:
        map_feature["source_bridge"] = tags.get("bridge")

    return map_feature


def parse_overpass_elements_to_map_features(elements):
    """Convert Overpass elements into map features, skipping unusable entries."""
    if not isinstance(elements, list):
        raise ValueError("elements はリストで指定してください。")

    map_features = []
    skipped_count = 0
    for element in elements:
        if not isinstance(element, dict):
            raise ValueError("elements の各要素は辞書で指定してください。")

        try:
            map_feature = build_map_feature_from_osm_element(element)
        except ValueError:
            skipped_count += 1
            continue

        if map_feature is not None:
            map_features.append(map_feature)
        else:
            skipped_count += 1

    kind_counts = Counter(feature["kind"] for feature in map_features)
    logger.info(
        "[auto_grid_create] step=feature_classify raw=%s valid=%s skipped=%s",
        len(elements),
        len(map_features),
        skipped_count,
    )
    logger.info(
        "[auto_grid_create] step=feature_counts building=%s road=%s park=%s "
        "river=%s water=%s forest=%s railway=%s station=%s expressway=%s "
        "landmark=%s coastline=%s",
        kind_counts.get("building", 0),
        kind_counts.get("road", 0),
        kind_counts.get("park", 0),
        kind_counts.get("river", 0),
        kind_counts.get("water", 0),
        kind_counts.get("forest", 0),
        kind_counts.get("railway", 0),
        kind_counts.get("station", 0),
        kind_counts.get("expressway", 0),
        kind_counts.get("landmark", 0),
        kind_counts.get("coastline", 0),
    )

    return map_features


def _log_map_feature_counts(map_features):
    kind_counts = Counter(feature["kind"] for feature in map_features)
    logger.info(
        "[auto_grid_create] step=feature_counts building=%s road=%s park=%s "
        "river=%s water=%s forest=%s railway=%s station=%s expressway=%s "
        "landmark=%s coastline=%s",
        kind_counts.get("building", 0),
        kind_counts.get("road", 0),
        kind_counts.get("park", 0),
        kind_counts.get("river", 0),
        kind_counts.get("water", 0),
        kind_counts.get("forest", 0),
        kind_counts.get("railway", 0),
        kind_counts.get("station", 0),
        kind_counts.get("expressway", 0),
        kind_counts.get("landmark", 0),
        kind_counts.get("coastline", 0),
    )


def split_bounds(bounds, rows=2, cols=2):
    """Split one bbox into row x col smaller bboxes."""
    bounds = _normalize_bounds(bounds)
    rows = _normalize_positive_int(rows, "rows")
    cols = _normalize_positive_int(cols, "cols")

    lat_step = (bounds["north"] - bounds["south"]) / rows
    lng_step = (bounds["east"] - bounds["west"]) / cols
    split_bbox_list = []
    for row_index in range(rows):
        part_north = bounds["north"] - (lat_step * row_index)
        part_south = bounds["north"] - (lat_step * (row_index + 1))
        for col_index in range(cols):
            part_west = bounds["west"] + (lng_step * col_index)
            part_east = bounds["west"] + (lng_step * (col_index + 1))
            split_bbox_list.append(
                _normalize_bounds(
                    {
                        "north": part_north,
                        "south": part_south,
                        "east": part_east,
                        "west": part_west,
                    }
                )
            )

    return split_bbox_list


def _feature_dedupe_key(map_feature):
    if not isinstance(map_feature, dict):
        raise ValueError("map_feature は辞書で指定してください。")

    source_type = map_feature.get("source_type")
    source_id = map_feature.get("source_id")
    if source_type is None or source_id is None:
        return None

    return (source_type, source_id)


def dedupe_map_features(map_features):
    """Remove duplicated OSM features by source type and id when both exist."""
    if not isinstance(map_features, list):
        raise ValueError("map_features はリストで指定してください。")

    deduped_features = []
    seen_keys = set()
    duplicate_count = 0
    for map_feature in map_features:
        if not isinstance(map_feature, dict):
            raise ValueError("map_features の各要素は辞書で指定してください。")

        dedupe_key = _feature_dedupe_key(map_feature)
        if dedupe_key is None:
            deduped_features.append(map_feature)
            continue
        if dedupe_key in seen_keys:
            duplicate_count += 1
            continue

        seen_keys.add(dedupe_key)
        deduped_features.append(map_feature)

    return deduped_features, duplicate_count


def determine_auto_score_building_fetch_options(grid_size_meters, rows, cols):
    """Return building fetch options for the auto-score Overpass query."""
    if (
        isinstance(grid_size_meters, bool)
        or isinstance(rows, bool)
        or isinstance(cols, bool)
    ):
        raise ValueError("grid_size_meters, rows, cols は数値で指定してください。")

    try:
        grid_size_meters = float(grid_size_meters)
        rows = int(rows)
        cols = int(cols)
    except (TypeError, ValueError):
        raise ValueError("grid_size_meters, rows, cols は数値で指定してください。")

    if (
        not isfinite(grid_size_meters)
        or grid_size_meters <= 0
        or rows <= 0
        or cols <= 0
    ):
        raise ValueError("grid_size_meters, rows, cols は 0 より大きい値にしてください。")

    long_side_meters = grid_size_meters * max(rows, cols)
    include_buildings = AUTO_SCORE_FETCH_BUILDINGS
    building_mode = normalize_auto_score_building_mode()
    building_skip_reason = "none"
    if not AUTO_SCORE_FETCH_BUILDINGS:
        building_skip_reason = "disabled"
    elif (
        AUTO_SCORE_SKIP_BUILDINGS_WHEN_LARGE
        and long_side_meters >= AUTO_SCORE_BUILDING_SKIP_LONG_SIDE_METERS
    ):
        include_buildings = False
        building_skip_reason = "large_area"

    return {
        "include_buildings": include_buildings,
        "long_side_meters": long_side_meters,
        "building_skip_reason": building_skip_reason,
        "building_mode": building_mode,
    }


def build_overpass_query(
    bounds,
    *,
    include_buildings=True,
    building_mode=None,
    lightweight_output=None,
):
    """Build an Overpass QL query for map feature candidates within bounds.

    The query intentionally requests broad candidates first; later steps narrow
    them down per GridCell so unsupported or oversized features can be skipped.
    """
    if not isinstance(include_buildings, bool):
        raise ValueError("include_buildings は真偽値で指定してください。")
    building_mode = normalize_auto_score_building_mode(building_mode)
    if lightweight_output is None:
        lightweight_output = AUTO_SCORE_LIGHTWEIGHT_OVERPASS_OUTPUT
    if not isinstance(lightweight_output, bool):
        raise ValueError("lightweight_output は真偽値で指定してください。")

    bounds = _normalize_bounds(bounds)
    bbox = (
        f'{bounds["south"]},{bounds["west"]},'
        f'{bounds["north"]},{bounds["east"]}'
    )
    # coverage や線形地物のセル判定に影響しやすい地物は geom を維持する。
    geometry_filters = (
        '["natural"="water"]',
        '["water"]',
        '["waterway"="riverbank"]',
        '["waterway"="river"]',
        '["waterway"="stream"]',
        '["waterway"="canal"]',
        '["landuse"="forest"]',
        '["natural"="wood"]',
        '["leisure"="park"]',
        '["leisure"="garden"]',
        '["natural"="coastline"]',
        '["railway"="rail"]',
        '["railway"="subway"]',
        '["railway"="light_rail"]',
        '["railway"="tram"]',
        # road は現在の自動採点に寄与しないため、通常道路は取得しない。
        # expressway は文脈要素として使うため、高速道路相当だけ取得する。
        '["highway"="motorway"]',
        '["highway"="motorway_link"]',
        '["highway"="trunk"]',
        '["highway"="trunk_link"]',
    )
    # 存在や近さが主用途の地物は、軽量出力ON時に center で比較する。
    lightweight_filters = (
        '["railway"="station"]',
        '["railway"="halt"]',
        '["station"="subway"]',
        '["public_transport"="station"]',
        '["amenity"="bus_station"]',
        '["tourism"="attraction"]',
        '["tourism"="museum"]',
        '["tourism"="gallery"]',
        '["tourism"="viewpoint"]',
        '["historic"="castle"]',
        '["historic"="monument"]',
        '["historic"="memorial"]',
        '["historic"="ruins"]',
        '["historic"="archaeological_site"]',
    )
    query_lines = [
        "[out:json][timeout:25];",
    ]
    if include_buildings and building_mode == AUTO_SCORE_BUILDING_MODE_CENTER:
        # center mode は building だけ代表点を取得し、ポリゴン geometry 処理を避ける。
        query_lines.extend(
            [
                "(",
                f'  nwr["building"]({bbox});',
                ");",
                "out body center;",
            ]
        )
    elif include_buildings:
        # geometry mode は既存通り building も他地物と同じ出力形式で取得する。
        geometry_filters = ('["building"]',) + geometry_filters

    if lightweight_output:
        query_lines.append("(")
        for target_filter in lightweight_filters:
            query_lines.append(f"  nwr{target_filter}({bbox});")
        query_lines.extend(
            [
                ");",
                "out body center;",
            ]
        )
    else:
        geometry_filters = geometry_filters + lightweight_filters

    if geometry_filters:
        query_lines.append("(")
        for target_filter in geometry_filters:
            query_lines.append(f"  nwr{target_filter}({bbox});")
        query_lines.extend(
            [
                ");",
                "out body geom;",
            ]
        )

    return "\n".join(query_lines)


def fetch_osm_features_from_overpass(
    bounds,
    *,
    endpoint="https://overpass-api.de/api/interpreter",
    timeout=25,
    include_buildings=True,
    building_mode=None,
    lightweight_output=None,
):
    """Fetch OSM features from Overpass and convert them into map features.

    External API responses may be unavailable or malformed, so this function
    validates the response shape before the scoring pipeline uses it.
    """
    building_mode = normalize_auto_score_building_mode(building_mode)
    query = build_overpass_query(
        bounds,
        include_buildings=include_buildings,
        building_mode=building_mode,
        lightweight_output=lightweight_output,
    )

    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError("endpoint は空でない文字列で指定してください。")
    endpoint = endpoint.strip()

    if isinstance(timeout, bool):
        raise ValueError("timeout は 0 より大きい数値で指定してください。")
    try:
        timeout = float(timeout)
    except (TypeError, ValueError):
        raise ValueError("timeout は 0 より大きい数値で指定してください。")
    if not isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout は 0 より大きい数値で指定してください。")

    headers = {
        "Accept": "application/json",
        "Content-Type": "text/plain; charset=utf-8",
        "User-Agent": "portfolio-api-map-score/1.0",
    }

    request_started_at = perf_counter()
    try:
        response = requests.post(
            endpoint,
            data=query.encode("utf-8"),
            headers=headers,
            timeout=timeout,
        )
    except Exception as exc:
        logger.info(
            "[auto_grid_create] step=overpass_fetch_failed elapsed_sec=%.3f "
            "error=%s",
            perf_counter() - request_started_at,
            exc,
        )
        raise ValueError("Overpass API へのリクエストに失敗しました。") from exc

    if response.status_code != 200:
        response_text = _response_text_preview(getattr(response, "text", ""))
        error_message = (
            "Overpass API から正常なレスポンスを取得できませんでした。"
            f" status_code={response.status_code}"
        )
        if response_text:
            error_message += f" response_text={response_text}"
        logger.info(
            "[auto_grid_create] step=overpass_fetch_failed elapsed_sec=%.3f "
            "status_code=%s",
            perf_counter() - request_started_at,
            response.status_code,
        )
        raise ValueError(error_message)

    try:
        response_data = response.json()
    except ValueError as exc:
        logger.info(
            "[auto_grid_create] step=overpass_fetch_failed elapsed_sec=%.3f "
            "error=%s",
            perf_counter() - request_started_at,
            exc,
        )
        raise ValueError("Overpass API レスポンスをJSONとして読めません。") from exc

    if not isinstance(response_data, dict):
        raise ValueError("Overpass API レスポンスは辞書形式である必要があります。")
    if "elements" not in response_data:
        raise ValueError("Overpass API レスポンスに elements がありません。")
    if not isinstance(response_data["elements"], list):
        raise ValueError("Overpass API レスポンスの elements はリストである必要があります。")

    fetch_elapsed_sec = perf_counter() - request_started_at
    logger.info(
        "[auto_grid_create] step=overpass_fetch features=%s elapsed_sec=%.3f",
        len(response_data["elements"]),
        fetch_elapsed_sec,
    )

    classify_started_at = perf_counter()
    try:
        map_features = parse_overpass_elements_to_map_features(
            response_data["elements"]
        )
    except ValueError as exc:
        raise ValueError("Overpass API レスポンスの elements が不正です。") from exc
    logger.info(
        "[auto_grid_create] step=feature_classify_elapsed raw=%s valid=%s "
        "skipped=%s elapsed_sec=%.3f",
        len(response_data["elements"]),
        len(map_features),
        len(response_data["elements"]) - len(map_features),
        perf_counter() - classify_started_at,
    )

    return map_features


def fetch_osm_features_from_overpass_split(
    bounds,
    *,
    endpoint="https://overpass-api.de/api/interpreter",
    timeout=25,
    include_buildings=True,
    building_mode=None,
    lightweight_output=None,
    split_rows=2,
    split_cols=2,
    area_id=None,
):
    """Fetch OSM features by splitting one bbox into smaller Overpass requests."""
    building_mode = normalize_auto_score_building_mode(building_mode)
    split_rows = _normalize_positive_int(split_rows, "split_rows")
    split_cols = _normalize_positive_int(split_cols, "split_cols")
    split_bbox_list = split_bounds(bounds, rows=split_rows, cols=split_cols)
    logger.info(
        "[auto_grid_create] step=overpass_split_fetch area_id=%s enabled=True "
        "split_rows=%s split_cols=%s parts=%s lightweight_output=%s",
        area_id,
        split_rows,
        split_cols,
        len(split_bbox_list),
        lightweight_output,
    )

    split_started_at = perf_counter()
    split_raw_features = []
    for part_index, part_bounds in enumerate(split_bbox_list, start=1):
        part_started_at = perf_counter()
        try:
            part_features = fetch_osm_features_from_overpass(
                part_bounds,
                endpoint=endpoint,
                timeout=timeout,
                include_buildings=include_buildings,
                building_mode=building_mode,
                lightweight_output=lightweight_output,
            )
        except ValueError as exc:
            status_code = _status_code_from_error(exc)
            logger.info(
                "[auto_grid_create] step=overpass_split_part_failed area_id=%s "
                "split_enabled=True split_rows=%s split_cols=%s part=%s/%s "
                "elapsed_sec=%.3f status_code=%s fallback=split_fetch_failed",
                area_id,
                split_rows,
                split_cols,
                part_index,
                len(split_bbox_list),
                perf_counter() - part_started_at,
                status_code,
            )
            logger.info(
                "[auto_grid_create] step=overpass_split_fetch_failed area_id=%s "
                "split_enabled=True split_rows=%s split_cols=%s "
                "completed_parts=%s/%s failed_part=%s/%s elapsed_sec=%.3f "
                "status_code=%s fallback=auto_score_fallback error=%s",
                area_id,
                split_rows,
                split_cols,
                part_index - 1,
                len(split_bbox_list),
                part_index,
                len(split_bbox_list),
                perf_counter() - split_started_at,
                status_code,
                exc,
            )
            raise

        split_raw_features.extend(part_features)
        logger.info(
            "[auto_grid_create] step=overpass_split_part area_id=%s part=%s/%s "
            "raw_features=%s elapsed_sec=%.3f",
            area_id,
            part_index,
            len(split_bbox_list),
            len(part_features),
            perf_counter() - part_started_at,
        )

    deduped_features, duplicate_count = dedupe_map_features(split_raw_features)
    logger.info(
        "[auto_grid_create] step=overpass_split_dedupe area_id=%s "
        "split_raw_features=%s deduped_features=%s duplicate_features=%s",
        area_id,
        len(split_raw_features),
        len(deduped_features),
        duplicate_count,
    )
    _log_map_feature_counts(deduped_features)

    return deduped_features


def build_feature_summaries_for_map_area_from_overpass(
    map_area,
    *,
    padding_meters=0,
    rows=None,
    cols=None,
    lat_step=None,
    lng_step=None,
):
    """Build feature summaries for unsaved GridCells using Overpass map features."""
    area_id = getattr(map_area, "id", None)
    total_started_at = perf_counter()
    grid_cell_contexts = build_grid_cell_contexts_for_area(
        map_area,
        rows=rows,
        cols=cols,
        lat_step=lat_step,
        lng_step=lng_step,
    )
    row_count = (
        max(context["row_index"] for context in grid_cell_contexts) + 1
        if grid_cell_contexts
        else 0
    )
    col_count = (
        max(context["col_index"] for context in grid_cell_contexts) + 1
        if grid_cell_contexts
        else 0
    )
    building_fetch_options = determine_auto_score_building_fetch_options(
        map_area.grid_size_meters,
        row_count,
        col_count,
    )
    overpass_bounds = build_overpass_bbox_for_map_area(
        map_area,
        padding_meters=padding_meters,
    )
    logger.info(
        "[auto_grid_create] step=overpass_query area_id=%s "
        "include_buildings=%s building_mode=%s long_side_meters=%.0f "
        "building_skip_reason=%s split_enabled=%s split_rows=%s split_cols=%s "
        "lightweight_output=%s output_geometry_kinds=%s output_lightweight_kinds=%s",
        area_id,
        building_fetch_options["include_buildings"],
        building_fetch_options["building_mode"],
        building_fetch_options["long_side_meters"],
        building_fetch_options["building_skip_reason"],
        AUTO_SCORE_SPLIT_OVERPASS_FETCH,
        AUTO_SCORE_OVERPASS_SPLIT_ROWS,
        AUTO_SCORE_OVERPASS_SPLIT_COLS,
        AUTO_SCORE_LIGHTWEIGHT_OVERPASS_OUTPUT,
        (
            "park,water,river,forest,coastline,railway,expressway"
            if AUTO_SCORE_LIGHTWEIGHT_OVERPASS_OUTPUT
            else "park,water,river,forest,coastline,railway,expressway,station,landmark"
        ),
        (
            "building,station,landmark"
            if AUTO_SCORE_LIGHTWEIGHT_OVERPASS_OUTPUT
            else "building"
        ),
    )
    fetch_started_at = perf_counter()
    try:
        if AUTO_SCORE_SPLIT_OVERPASS_FETCH:
            map_features = fetch_osm_features_from_overpass_split(
                overpass_bounds,
                include_buildings=building_fetch_options["include_buildings"],
                building_mode=building_fetch_options["building_mode"],
                lightweight_output=AUTO_SCORE_LIGHTWEIGHT_OVERPASS_OUTPUT,
                split_rows=AUTO_SCORE_OVERPASS_SPLIT_ROWS,
                split_cols=AUTO_SCORE_OVERPASS_SPLIT_COLS,
                area_id=area_id,
            )
        else:
            map_features = fetch_osm_features_from_overpass(
                overpass_bounds,
                include_buildings=building_fetch_options["include_buildings"],
                building_mode=building_fetch_options["building_mode"],
                lightweight_output=AUTO_SCORE_LIGHTWEIGHT_OVERPASS_OUTPUT,
            )
    except ValueError as exc:
        status_code = _status_code_from_error(exc)
        logger.info(
            "[auto_grid_create] step=overpass_fetch_failed area_id=%s "
            "split_enabled=%s split_rows=%s split_cols=%s lightweight_output=%s "
            "elapsed_sec=%.3f status_code=%s fallback=auto_score_fallback error=%s",
            area_id,
            AUTO_SCORE_SPLIT_OVERPASS_FETCH,
            AUTO_SCORE_OVERPASS_SPLIT_ROWS,
            AUTO_SCORE_OVERPASS_SPLIT_COLS,
            AUTO_SCORE_LIGHTWEIGHT_OVERPASS_OUTPUT,
            perf_counter() - fetch_started_at,
            status_code,
            exc,
        )
        raise
    logger.info(
        "[auto_grid_create] step=overpass_fetch area_id=%s features=%s "
        "elapsed_sec=%.3f split_enabled=%s lightweight_output=%s",
        area_id,
        len(map_features),
        perf_counter() - fetch_started_at,
        AUTO_SCORE_SPLIT_OVERPASS_FETCH,
        AUTO_SCORE_LIGHTWEIGHT_OVERPASS_OUTPUT,
    )
    map_area_bounds = {
        "north": map_area.north,
        "south": map_area.south,
        "east": map_area.east,
        "west": map_area.west,
    }

    summary_started_at = perf_counter()
    feature_summaries = FeatureSummariesByPosition(
        build_feature_summaries_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
            map_area_bounds=map_area_bounds,
        )
    )
    summary_elapsed_sec = perf_counter() - summary_started_at
    avg_cell_ms = (
        (summary_elapsed_sec / len(grid_cell_contexts)) * 1000
        if grid_cell_contexts
        else 0.0
    )
    logger.info(
        "[auto_grid_create] step=feature_summary area_id=%s cells=%s "
        "features=%s elapsed_sec=%.3f avg_cell_ms=%.2f",
        area_id,
        len(grid_cell_contexts),
        len(map_features),
        summary_elapsed_sec,
        avg_cell_ms,
    )
    building_count_total = sum(
        summary.get("building_count", 0) for summary in feature_summaries.values()
    )
    building_skipped_missing_position = 0
    building_center_fallback_count = 0
    for feature in map_features:
        if not isinstance(feature, dict) or feature.get("kind") != "building":
            continue
        building_position = _building_position_for_grid_cell(
            feature,
            building_fetch_options["building_mode"],
        )
        if building_position is None:
            building_skipped_missing_position += 1
        elif (
            building_fetch_options["building_mode"] == AUTO_SCORE_BUILDING_MODE_GEOMETRY
            and building_position[0] == "center"
        ):
            building_center_fallback_count += 1

    logger.info(
        "[auto_grid_create] step=building_summary area_id=%s "
        "building_mode=%s building_count_total=%s building_cells=%s "
        "building_skipped_missing_position=%s building_center_fallback_count=%s",
        area_id,
        building_fetch_options["building_mode"],
        building_count_total,
        sum(
            summary.get("building_count", 0) > 0
            for summary in feature_summaries.values()
        ),
        building_skipped_missing_position,
        building_center_fallback_count,
    )
    feature_summaries.river_summary = (
        summarize_river_feature_matches_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )
    )
    feature_summaries.waterway_summary = (
        summarize_waterway_feature_matches_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )
    )
    feature_summaries.railway_summary = (
        summarize_railway_feature_matches_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )
    )
    feature_summaries.station_summary = (
        summarize_station_feature_matches_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )
    )
    feature_summaries.station_proximity_summary = (
        summarize_station_proximity_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )
    )
    feature_summaries.landmark_summary = (
        summarize_landmark_feature_matches_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )
    )
    feature_summaries.castle_proximity_summary = (
        summarize_castle_proximity_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )
    )
    feature_summaries.expressway_summary = (
        summarize_expressway_feature_matches_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )
    )
    feature_summaries.expressway_bounds_summary = (
        summarize_expressway_bounds_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )
    )
    feature_summaries.effective_expressway_summary = (
        summarize_effective_expressway_feature_matches_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )
    )
    feature_summaries.waterway_river_bounds_summary = (
        summarize_waterway_river_bounds_for_map_area(
            map_area_bounds,
            map_features,
            grid_cell_contexts=grid_cell_contexts,
        )
    )
    logger.info(
        "[auto_grid_create] step=feature_summary_total area_id=%s cells=%s "
        "features=%s elapsed_sec=%.3f",
        area_id,
        len(grid_cell_contexts),
        len(map_features),
        perf_counter() - total_started_at,
    )

    return feature_summaries


def _empty_river_feature_match_summary():
    return {
        "river_cells": 0,
        "river_avg_overlap": 0.0,
        "river_max_overlap": 0.0,
        "river_large_bounds_cells": 0,
        "river_small_overlap_cells": 0,
    }


def _waterway_summary_key(source_waterway):
    if source_waterway in WATERWAY_SUMMARY_KEYS[:-1]:
        return source_waterway
    return "unknown"


def _empty_waterway_feature_match_summary():
    summary = {}
    for waterway in WATERWAY_SUMMARY_KEYS:
        summary[f"waterway_{waterway}_features"] = 0
        summary[f"waterway_{waterway}_cells"] = 0
    return summary


def _empty_waterway_river_bounds_summary():
    return {
        "waterway_river_bounds_features": 0,
        "waterway_river_bounds_intersecting_map_features": 0,
        "waterway_river_bounds_covering_map_features": 0,
        "waterway_river_bounds_large_area_features": 0,
        "waterway_river_bounds_filtered_features": 0,
        "waterway_river_bounds_filtered_cells": 0,
        "waterway_river_bounds_max_area_ratio_to_map": 0.0,
        "waterway_river_bounds_max_height_ratio_to_map": 0.0,
        "waterway_river_bounds_max_width_ratio_to_map": 0.0,
    }


def _empty_railway_feature_match_summary():
    return {
        "railway_features": 0,
        "surface_railway_features": 0,
        "underground_railway_features": 0,
        "unknown_railway_features": 0,
        "railway_cells": 0,
        "surface_railway_cells": 0,
        "underground_railway_cells": 0,
        "unknown_railway_cells": 0,
    }


def _empty_station_feature_match_summary():
    summary = {
        "station_features": 0,
        "station_cells": 0,
    }
    for station_type in STATION_SUMMARY_KEYS[:-1]:
        summary[f"{station_type}_features"] = 0
        summary[f"{station_type}_cells"] = 0
    summary["unknown_station_features"] = 0
    summary["unknown_station_cells"] = 0
    summary["station_cluster_cells"] = 0
    summary["dense_station_cluster_cells"] = 0
    summary["major_station_cluster_cells"] = 0
    summary["station_cluster_count_avg"] = 0.0
    summary["station_cluster_count_max"] = 0
    summary["dense_station_cluster_count_max"] = 0
    summary["major_station_cluster_count_max"] = 0
    return summary


def _empty_station_proximity_summary():
    return {
        "station_proximity_features": 0,
        "station_proximity_near_cells": 0,
        "station_proximity_mid_cells": 0,
        "station_proximity_cells": 0,
        "station_proximity_station_cells": 0,
        "station_proximity_non_station_cells": 0,
        "station_proximity_min_distance_m": 0.0,
        "station_proximity_avg_distance_m": 0.0,
        "station_proximity_max_distance_m": 0.0,
    }


def _empty_landmark_feature_match_summary():
    summary = {
        "landmark_features": 0,
        "landmark_cells": 0,
    }
    for landmark_type in LANDMARK_SUMMARY_KEYS[:-1]:
        summary[f"{landmark_type}_features"] = 0
        summary[f"{landmark_type}_cells"] = 0
    summary["unknown_landmark_features"] = 0
    summary["unknown_landmark_cells"] = 0
    return summary


def _empty_castle_proximity_summary():
    return {
        "castle_features": 0,
        "castle_near_cells": 0,
        "castle_mid_cells": 0,
        "castle_far_cells": 0,
        "castle_proximity_cells": 0,
        "castle_min_distance_m": 0.0,
        "castle_avg_distance_m": 0.0,
        "castle_max_distance_m": 0.0,
    }


def _empty_expressway_feature_match_summary():
    summary = {
        "expressway_features": 0,
        "expressway_cells": 0,
    }
    for expressway_type in EXPRESSWAY_SUMMARY_KEYS[:-1]:
        summary[f"{expressway_type}_features"] = 0
        summary[f"{expressway_type}_cells"] = 0
    summary["unknown_expressway_features"] = 0
    summary["unknown_expressway_cells"] = 0
    return summary


def _empty_expressway_bounds_summary():
    summary = {
        "expressway_features": 0,
        "expressway_cells": 0,
        "expressway_avg_overlap": 0.0,
        "expressway_max_overlap": 0.0,
        "expressway_large_bounds_features": 0,
        "expressway_large_bounds_cells": 0,
    }
    for expressway_type in EXPRESSWAY_SUMMARY_KEYS:
        expressway_field = _expressway_summary_field(expressway_type)
        summary[f"{expressway_field}_features"] = 0
        summary[f"{expressway_field}_cells"] = 0
        summary[f"{expressway_field}_avg_overlap"] = 0.0
        summary[f"{expressway_field}_max_overlap"] = 0.0
    return summary


def _empty_effective_expressway_summary():
    summary = {
        "effective_expressway_features": 0,
        "effective_expressway_cells": 0,
        "effective_expressway_avg_overlap": 0.0,
        "effective_expressway_max_overlap": 0.0,
        "filtered_expressway_large_bounds_features": 0,
        "filtered_expressway_large_bounds_cells": 0,
    }
    for expressway_type in EXPRESSWAY_SUMMARY_KEYS:
        expressway_field = _expressway_summary_field(expressway_type)
        summary[f"effective_{expressway_field}_features"] = 0
        summary[f"effective_{expressway_field}_cells"] = 0
        summary[f"effective_{expressway_field}_avg_overlap"] = 0.0
        summary[f"effective_{expressway_field}_max_overlap"] = 0.0
    return summary


def _railway_layer_number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def classify_railway_feature_surface_type(feature):
    """Classify one railway map feature as surface, underground, or unknown."""
    if not isinstance(feature, dict):
        raise ValueError("feature は辞書で指定してください。")

    source_railway = feature.get("source_railway")
    source_tunnel = str(feature.get("source_tunnel", "")).strip().lower()
    source_layer = _railway_layer_number(feature.get("source_layer"))

    if (
        source_railway in RAILWAY_UNDERGROUND_TYPES
        or source_tunnel in {"yes", "true", "building_passage"}
        or (source_layer is not None and source_layer < 0)
    ):
        return "underground"

    if (
        source_railway in RAILWAY_SURFACE_TYPES
        and source_tunnel not in {"yes", "true", "building_passage"}
        and (source_layer is None or source_layer >= 0)
    ):
        return "surface"

    return "unknown"


def classify_station_feature_type(feature):
    """Classify one station map feature for log-only summaries."""
    if not isinstance(feature, dict):
        raise ValueError("feature は辞書で指定してください。")

    source_railway = feature.get("source_railway")
    source_station = feature.get("source_station")
    source_public_transport = feature.get("source_public_transport")
    source_amenity = feature.get("source_amenity")

    # station=subway is checked first so subway stations are visible in logs
    # even when OSM also tags them as railway=station.
    if source_station == "subway":
        return "subway_station"
    if source_railway == "station":
        return "railway_station"
    if source_railway == "halt":
        return "railway_halt"
    if source_amenity == "bus_station":
        return "bus_station"
    if source_public_transport == "station":
        return "public_transport_station"

    return "unknown"


def classify_landmark_feature_type(feature):
    """Classify one tourism/historic map feature for log-only summaries."""
    if not isinstance(feature, dict):
        raise ValueError("feature は辞書で指定してください。")

    source_tourism = feature.get("source_tourism")
    source_historic = feature.get("source_historic")
    if source_tourism in LANDMARK_TOURISM_TYPES:
        return f"tourism_{source_tourism}"
    if source_historic in LANDMARK_HISTORIC_TYPES:
        return f"historic_{source_historic}"

    return "unknown"


def classify_expressway_feature_type(feature):
    """Classify one expressway map feature for log-only summaries."""
    if not isinstance(feature, dict):
        raise ValueError("feature は辞書で指定してください。")

    source_highway = feature.get("source_highway")
    if source_highway in EXPRESSWAY_HIGHWAY_TYPES:
        return source_highway

    return "unknown"


def _station_summary_field(station_type):
    if station_type == "unknown":
        return "unknown_station"
    return station_type


def _landmark_summary_field(landmark_type):
    if landmark_type == "unknown":
        return "unknown_landmark"
    return landmark_type


def _bounds_center(bounds):
    normalized_bounds = _normalize_bounds(bounds)
    return (
        (normalized_bounds["north"] + normalized_bounds["south"]) / 2,
        (normalized_bounds["east"] + normalized_bounds["west"]) / 2,
    )


def _map_feature_center_point(feature):
    if not isinstance(feature, dict):
        raise ValueError("feature は辞書で指定してください。")

    center = feature.get("center")
    if center is not None:
        return _normalize_point(center)

    center_lat, center_lng = _bounds_center(feature.get("bounds"))
    return {"lat": center_lat, "lon": center_lng}


def _map_feature_center_tuple(feature):
    center = _map_feature_center_point(feature)
    return (center["lat"], center["lon"])


def _center_tuple_in_bounds(center_tuple, bounds):
    return _point_in_bounds(
        {"lat": center_tuple[0], "lon": center_tuple[1]},
        bounds,
    )


def _feature_match_for_grid_cell_by_bounds_or_center(feature, grid_cell_bounds):
    try:
        feature_bounds = _normalize_bounds(feature.get("bounds"))
    except ValueError as bounds_error:
        try:
            feature_center = _map_feature_center_tuple(feature)
        except ValueError:
            raise bounds_error

        if _center_tuple_in_bounds(feature_center, grid_cell_bounds):
            return ("center", feature_center, feature_center)
        return None

    if not feature_intersects_grid_cell(feature_bounds, grid_cell_bounds):
        return None

    return ("bounds", feature_bounds, _bounds_center(feature_bounds))


def _building_position_for_grid_cell(feature, building_mode):
    """Return how a building can be matched to a GridCell, or None if unusable."""
    if not isinstance(feature, dict):
        raise ValueError("feature は辞書で指定してください。")

    if building_mode == AUTO_SCORE_BUILDING_MODE_CENTER:
        try:
            return ("center", _map_feature_center_point(feature))
        except ValueError:
            return None

    try:
        return ("bounds", _normalize_bounds(feature.get("bounds")))
    except ValueError:
        try:
            return ("center", _map_feature_center_point(feature))
        except ValueError:
            return None


def _distance_between_points_meters(first_point, second_point):
    first_lat, first_lng = first_point
    second_lat, second_lng = second_point
    average_lat = (first_lat + second_lat) / 2
    lat_distance = (first_lat - second_lat) * METERS_PER_DEGREE
    lng_distance = (
        (first_lng - second_lng)
        * METERS_PER_DEGREE
        * max(cos(radians(average_lat)), MIN_LONGITUDE_COSINE)
    )
    return (lat_distance**2 + lng_distance**2) ** 0.5


def _max_station_cluster_size(station_centers, distance_threshold_meters):
    if len(station_centers) < 2:
        return 0

    neighbors = {index: set() for index in range(len(station_centers))}
    for first_index, first_center in enumerate(station_centers):
        for second_index in range(first_index + 1, len(station_centers)):
            distance = _distance_between_points_meters(
                first_center,
                station_centers[second_index],
            )
            if distance <= distance_threshold_meters:
                neighbors[first_index].add(second_index)
                neighbors[second_index].add(first_index)

    visited = set()
    max_cluster_size = 0
    for index in range(len(station_centers)):
        if index in visited:
            continue

        stack = [index]
        cluster_size = 0
        while stack:
            current_index = stack.pop()
            if current_index in visited:
                continue
            visited.add(current_index)
            cluster_size += 1
            stack.extend(neighbors[current_index] - visited)

        if cluster_size > 1:
            max_cluster_size = max(max_cluster_size, cluster_size)

    return max_cluster_size


def _castle_centers_from_map_features(map_features):
    castle_centers = []
    for feature in map_features:
        if not isinstance(feature, dict):
            raise ValueError("map_features の各要素は辞書で指定してください。")
        if feature.get("kind") != "landmark":
            continue
        if classify_landmark_feature_type(feature) != "historic_castle":
            continue

        castle_centers.append(_map_feature_center_tuple(feature))

    return castle_centers


def _scored_station_centers_from_map_features(map_features):
    station_entries = []
    for feature in map_features:
        if not isinstance(feature, dict):
            raise ValueError("map_features の各要素は辞書で指定してください。")
        if feature.get("kind") != "station":
            continue

        station_type = classify_station_feature_type(feature)
        if station_type not in STATION_PROXIMITY_SUMMARY_TYPES:
            continue

        try:
            feature_bounds = _normalize_bounds(feature.get("bounds"))
            feature_center = _bounds_center(feature_bounds)
        except ValueError:
            feature_bounds = None
            feature_center = _map_feature_center_tuple(feature)
        station_entries.append((feature_bounds, feature_center))

    return station_entries


def _station_proximity_band_for_grid_cell(grid_cell_bounds, station_centers):
    if not station_centers:
        return None, None

    grid_cell_center = _bounds_center(grid_cell_bounds)
    min_distance = min(
        _distance_between_points_meters(station_center, grid_cell_center)
        for station_center in station_centers
    )
    if min_distance <= STATION_PROXIMITY_NEAR_DISTANCE_METERS:
        return "near", min_distance
    if min_distance <= STATION_PROXIMITY_MID_DISTANCE_METERS:
        return "mid", min_distance

    return None, None


def _castle_proximity_band_for_grid_cell(grid_cell_bounds, castle_centers):
    if not castle_centers:
        return None, None

    grid_cell_center = _bounds_center(grid_cell_bounds)
    min_distance = min(
        _distance_between_points_meters(castle_center, grid_cell_center)
        for castle_center in castle_centers
    )
    if min_distance <= CASTLE_NEAR_DISTANCE_METERS:
        return "near", min_distance
    if min_distance <= CASTLE_MID_DISTANCE_METERS:
        return "mid", min_distance
    if min_distance <= CASTLE_FAR_DISTANCE_METERS:
        return "far", min_distance

    return None, None


def _expressway_summary_field(expressway_type):
    if expressway_type == "unknown":
        return "unknown_expressway"
    return expressway_type


def summarize_railway_feature_matches_for_grid_cell_contexts(
    grid_cell_contexts,
    map_features,
):
    """Summarize railway feature matches for log output only."""
    if not isinstance(grid_cell_contexts, list):
        raise ValueError("grid_cell_contexts はリストで指定してください。")
    if not isinstance(map_features, list):
        raise ValueError("map_features はリストで指定してください。")

    railway_summary = _empty_railway_feature_match_summary()
    cell_keys_by_type = {
        "railway": set(),
        "surface": set(),
        "underground": set(),
        "unknown": set(),
    }
    grid_cell_entries = []

    for index, grid_cell_context in enumerate(grid_cell_contexts):
        if not isinstance(grid_cell_context, dict):
            raise ValueError("grid_cell_contexts の各要素は辞書で指定してください。")

        grid_cell_bounds = {
            "north": grid_cell_context.get("north"),
            "south": grid_cell_context.get("south"),
            "east": grid_cell_context.get("east"),
            "west": grid_cell_context.get("west"),
        }
        grid_cell_entries.append(
            (
                (
                    grid_cell_context.get("row_index", index),
                    grid_cell_context.get("col_index", index),
                ),
                _normalize_bounds(grid_cell_bounds),
            )
        )

    for feature in map_features:
        if not isinstance(feature, dict):
            raise ValueError("map_features の各要素は辞書で指定してください。")
        if feature.get("kind") != "railway":
            continue

        railway_type = classify_railway_feature_surface_type(feature)
        railway_summary["railway_features"] += 1
        railway_summary[f"{railway_type}_railway_features"] += 1
        feature_bounds = _normalize_bounds(feature.get("bounds"))

        for cell_key, grid_cell_bounds in grid_cell_entries:
            if feature_intersects_grid_cell(feature_bounds, grid_cell_bounds):
                cell_keys_by_type["railway"].add(cell_key)
                cell_keys_by_type[railway_type].add(cell_key)

    railway_summary["railway_cells"] = len(cell_keys_by_type["railway"])
    railway_summary["surface_railway_cells"] = len(cell_keys_by_type["surface"])
    railway_summary["underground_railway_cells"] = len(
        cell_keys_by_type["underground"]
    )
    railway_summary["unknown_railway_cells"] = len(cell_keys_by_type["unknown"])

    return railway_summary


def _build_grid_cell_entries_for_summary(grid_cell_contexts):
    grid_cell_entries = []
    for index, grid_cell_context in enumerate(grid_cell_contexts):
        if not isinstance(grid_cell_context, dict):
            raise ValueError("grid_cell_contexts の各要素は辞書で指定してください。")

        grid_cell_bounds = {
            "north": grid_cell_context.get("north"),
            "south": grid_cell_context.get("south"),
            "east": grid_cell_context.get("east"),
            "west": grid_cell_context.get("west"),
        }
        grid_cell_entries.append(
            (
                (
                    grid_cell_context.get("row_index", index),
                    grid_cell_context.get("col_index", index),
                ),
                _normalize_bounds(grid_cell_bounds),
            )
        )

    return grid_cell_entries


def summarize_station_feature_matches_for_grid_cell_contexts(
    grid_cell_contexts,
    map_features,
):
    """Summarize station feature matches for log output only."""
    if not isinstance(grid_cell_contexts, list):
        raise ValueError("grid_cell_contexts はリストで指定してください。")
    if not isinstance(map_features, list):
        raise ValueError("map_features はリストで指定してください。")

    station_summary = _empty_station_feature_match_summary()
    cell_keys_by_type = {"station": set()}
    for station_type in STATION_SUMMARY_KEYS:
        cell_keys_by_type[_station_summary_field(station_type)] = set()
    grid_cell_entries = _build_grid_cell_entries_for_summary(grid_cell_contexts)
    station_centers_by_cell = {
        cell_key: [] for cell_key, _grid_cell_bounds in grid_cell_entries
    }

    for feature in map_features:
        if not isinstance(feature, dict):
            raise ValueError("map_features の各要素は辞書で指定してください。")
        if feature.get("kind") != "station":
            continue

        station_type = classify_station_feature_type(feature)
        station_field = _station_summary_field(station_type)
        station_summary["station_features"] += 1
        station_summary[f"{station_field}_features"] += 1

        for cell_key, grid_cell_bounds in grid_cell_entries:
            feature_match = _feature_match_for_grid_cell_by_bounds_or_center(
                feature,
                grid_cell_bounds,
            )
            if feature_match is None:
                continue
            cell_keys_by_type["station"].add(cell_key)
            cell_keys_by_type[station_field].add(cell_key)
            if station_type in SCORED_STATION_SUMMARY_TYPES:
                station_centers_by_cell[cell_key].append(feature_match[2])

    station_summary["station_cells"] = len(cell_keys_by_type["station"])
    for station_type in STATION_SUMMARY_KEYS:
        station_field = _station_summary_field(station_type)
        station_summary[f"{station_field}_cells"] = len(
            cell_keys_by_type[station_field]
        )

    broad_cluster_counts = []
    dense_cluster_counts = []
    major_cluster_counts = []
    for station_centers in station_centers_by_cell.values():
        broad_cluster_count = _max_station_cluster_size(
            station_centers,
            STATION_BROAD_CLUSTER_DISTANCE_METERS,
        )
        dense_cluster_count = _max_station_cluster_size(
            station_centers,
            STATION_DENSE_CLUSTER_DISTANCE_METERS,
        )
        if broad_cluster_count > 0:
            broad_cluster_counts.append(broad_cluster_count)
        if dense_cluster_count > 0:
            dense_cluster_counts.append(dense_cluster_count)
        if broad_cluster_count >= STATION_MAJOR_CLUSTER_MIN_FEATURES:
            major_cluster_counts.append(broad_cluster_count)

    station_summary["station_cluster_cells"] = len(broad_cluster_counts)
    station_summary["dense_station_cluster_cells"] = len(dense_cluster_counts)
    station_summary["major_station_cluster_cells"] = len(major_cluster_counts)
    if broad_cluster_counts:
        station_summary["station_cluster_count_avg"] = (
            sum(broad_cluster_counts) / len(broad_cluster_counts)
        )
        station_summary["station_cluster_count_max"] = max(broad_cluster_counts)
    if dense_cluster_counts:
        station_summary["dense_station_cluster_count_max"] = max(
            dense_cluster_counts
        )
    if major_cluster_counts:
        station_summary["major_station_cluster_count_max"] = max(
            major_cluster_counts
        )

    return station_summary


def summarize_station_proximity_for_grid_cell_contexts(
    grid_cell_contexts,
    map_features,
):
    """Summarize GridCell distance bands around scored station features."""
    if not isinstance(grid_cell_contexts, list):
        raise ValueError("grid_cell_contexts はリストで指定してください。")
    if not isinstance(map_features, list):
        raise ValueError("map_features はリストで指定してください。")

    station_proximity_summary = _empty_station_proximity_summary()
    grid_cell_entries = _build_grid_cell_entries_for_summary(grid_cell_contexts)
    station_entries = _scored_station_centers_from_map_features(map_features)
    station_centers = [center for _bounds, center in station_entries]
    station_proximity_summary["station_proximity_features"] = len(station_entries)

    proximity_distances = []
    station_body_cells = set()
    proximity_cell_keys = set()
    for cell_key, grid_cell_bounds in grid_cell_entries:
        is_station_body_cell = any(
            (
                feature_intersects_grid_cell(station_bounds, grid_cell_bounds)
                if station_bounds is not None
                else _center_tuple_in_bounds(station_center, grid_cell_bounds)
            )
            for station_bounds, station_center in station_entries
        )
        if is_station_body_cell:
            station_body_cells.add(cell_key)

        proximity_band, min_distance = _station_proximity_band_for_grid_cell(
            grid_cell_bounds,
            station_centers,
        )
        if proximity_band == "near":
            station_proximity_summary["station_proximity_near_cells"] += 1
            proximity_cell_keys.add(cell_key)
            proximity_distances.append(min_distance)
        elif proximity_band == "mid":
            station_proximity_summary["station_proximity_mid_cells"] += 1
            proximity_cell_keys.add(cell_key)
            proximity_distances.append(min_distance)

    station_proximity_summary["station_proximity_cells"] = len(
        proximity_cell_keys
    )
    station_proximity_summary["station_proximity_station_cells"] = len(
        proximity_cell_keys & station_body_cells
    )
    station_proximity_summary["station_proximity_non_station_cells"] = (
        len(proximity_cell_keys - station_body_cells)
    )
    if proximity_distances:
        station_proximity_summary["station_proximity_min_distance_m"] = min(
            proximity_distances
        )
        station_proximity_summary["station_proximity_avg_distance_m"] = (
            sum(proximity_distances) / len(proximity_distances)
        )
        station_proximity_summary["station_proximity_max_distance_m"] = max(
            proximity_distances
        )

    return station_proximity_summary


def summarize_landmark_feature_matches_for_grid_cell_contexts(
    grid_cell_contexts,
    map_features,
):
    """Summarize tourism/historic feature matches for log output only."""
    if not isinstance(grid_cell_contexts, list):
        raise ValueError("grid_cell_contexts はリストで指定してください。")
    if not isinstance(map_features, list):
        raise ValueError("map_features はリストで指定してください。")

    landmark_summary = _empty_landmark_feature_match_summary()
    cell_keys_by_type = {"landmark": set()}
    for landmark_type in LANDMARK_SUMMARY_KEYS:
        cell_keys_by_type[_landmark_summary_field(landmark_type)] = set()
    grid_cell_entries = _build_grid_cell_entries_for_summary(grid_cell_contexts)

    for feature in map_features:
        if not isinstance(feature, dict):
            raise ValueError("map_features の各要素は辞書で指定してください。")
        if feature.get("kind") != "landmark":
            continue

        landmark_type = classify_landmark_feature_type(feature)
        landmark_field = _landmark_summary_field(landmark_type)
        landmark_summary["landmark_features"] += 1
        landmark_summary[f"{landmark_field}_features"] += 1

        for cell_key, grid_cell_bounds in grid_cell_entries:
            if (
                _feature_match_for_grid_cell_by_bounds_or_center(
                    feature,
                    grid_cell_bounds,
                )
                is not None
            ):
                cell_keys_by_type["landmark"].add(cell_key)
                cell_keys_by_type[landmark_field].add(cell_key)

    landmark_summary["landmark_cells"] = len(cell_keys_by_type["landmark"])
    for landmark_type in LANDMARK_SUMMARY_KEYS:
        landmark_field = _landmark_summary_field(landmark_type)
        landmark_summary[f"{landmark_field}_cells"] = len(
            cell_keys_by_type[landmark_field]
        )

    return landmark_summary


def summarize_castle_proximity_for_grid_cell_contexts(
    grid_cell_contexts,
    map_features,
):
    """Summarize non-overlapping GridCell distance bands around castles."""
    if not isinstance(grid_cell_contexts, list):
        raise ValueError("grid_cell_contexts はリストで指定してください。")
    if not isinstance(map_features, list):
        raise ValueError("map_features はリストで指定してください。")

    castle_summary = _empty_castle_proximity_summary()
    grid_cell_entries = _build_grid_cell_entries_for_summary(grid_cell_contexts)
    castle_centers = _castle_centers_from_map_features(map_features)
    castle_summary["castle_features"] = len(castle_centers)

    proximity_distances = []
    for _cell_key, grid_cell_bounds in grid_cell_entries:
        proximity_band, min_distance = _castle_proximity_band_for_grid_cell(
            grid_cell_bounds,
            castle_centers,
        )
        if proximity_band == "near":
            castle_summary["castle_near_cells"] += 1
            proximity_distances.append(min_distance)
        elif proximity_band == "mid":
            castle_summary["castle_mid_cells"] += 1
            proximity_distances.append(min_distance)
        elif proximity_band == "far":
            castle_summary["castle_far_cells"] += 1
            proximity_distances.append(min_distance)

    castle_summary["castle_proximity_cells"] = len(proximity_distances)
    if proximity_distances:
        castle_summary["castle_min_distance_m"] = min(proximity_distances)
        castle_summary["castle_avg_distance_m"] = (
            sum(proximity_distances) / len(proximity_distances)
        )
        castle_summary["castle_max_distance_m"] = max(proximity_distances)

    return castle_summary


def summarize_expressway_feature_matches_for_grid_cell_contexts(
    grid_cell_contexts,
    map_features,
):
    """Summarize expressway feature matches for log output only."""
    if not isinstance(grid_cell_contexts, list):
        raise ValueError("grid_cell_contexts はリストで指定してください。")
    if not isinstance(map_features, list):
        raise ValueError("map_features はリストで指定してください。")

    expressway_summary = _empty_expressway_feature_match_summary()
    cell_keys_by_type = {"expressway": set()}
    for expressway_type in EXPRESSWAY_SUMMARY_KEYS:
        cell_keys_by_type[_expressway_summary_field(expressway_type)] = set()
    grid_cell_entries = _build_grid_cell_entries_for_summary(grid_cell_contexts)

    for feature in map_features:
        if not isinstance(feature, dict):
            raise ValueError("map_features の各要素は辞書で指定してください。")
        if feature.get("kind") != "expressway":
            continue

        expressway_type = classify_expressway_feature_type(feature)
        expressway_field = _expressway_summary_field(expressway_type)
        expressway_summary["expressway_features"] += 1
        expressway_summary[f"{expressway_field}_features"] += 1
        feature_bounds = _normalize_bounds(feature.get("bounds"))

        for cell_key, grid_cell_bounds in grid_cell_entries:
            if feature_intersects_grid_cell(feature_bounds, grid_cell_bounds):
                cell_keys_by_type["expressway"].add(cell_key)
                cell_keys_by_type[expressway_field].add(cell_key)

    expressway_summary["expressway_cells"] = len(cell_keys_by_type["expressway"])
    for expressway_type in EXPRESSWAY_SUMMARY_KEYS:
        expressway_field = _expressway_summary_field(expressway_type)
        expressway_summary[f"{expressway_field}_cells"] = len(
            cell_keys_by_type[expressway_field]
        )

    return expressway_summary


def _store_max_overlap(cell_overlaps, cell_key, overlap_ratio):
    cell_overlaps[cell_key] = max(cell_overlaps.get(cell_key, 0.0), overlap_ratio)


def _set_overlap_summary(summary, prefix, cell_overlaps):
    overlaps = list(cell_overlaps.values())
    summary[f"{prefix}_cells"] = len(overlaps)
    if overlaps:
        summary[f"{prefix}_avg_overlap"] = sum(overlaps) / len(overlaps)
        summary[f"{prefix}_max_overlap"] = max(overlaps)


def summarize_expressway_bounds_for_grid_cell_contexts(
    grid_cell_contexts,
    map_features,
):
    """Summarize expressway bbox overlap and size ratios for log output only."""
    if not isinstance(grid_cell_contexts, list):
        raise ValueError("grid_cell_contexts はリストで指定してください。")
    if not isinstance(map_features, list):
        raise ValueError("map_features はリストで指定してください。")

    bounds_summary = _empty_expressway_bounds_summary()
    cell_overlaps_by_type = {"expressway": {}}
    for expressway_type in EXPRESSWAY_SUMMARY_KEYS:
        cell_overlaps_by_type[_expressway_summary_field(expressway_type)] = {}
    large_bounds_cell_keys = set()
    grid_cell_entries = _build_grid_cell_entries_for_summary(grid_cell_contexts)

    for feature in map_features:
        if not isinstance(feature, dict):
            raise ValueError("map_features の各要素は辞書で指定してください。")
        if feature.get("kind") != "expressway":
            continue

        expressway_type = classify_expressway_feature_type(feature)
        expressway_field = _expressway_summary_field(expressway_type)
        bounds_summary["expressway_features"] += 1
        bounds_summary[f"{expressway_field}_features"] += 1
        feature_bounds = _normalize_bounds(feature.get("bounds"))
        is_large_feature = False

        for cell_key, grid_cell_bounds in grid_cell_entries:
            if not feature_intersects_grid_cell(feature_bounds, grid_cell_bounds):
                continue

            overlap_ratio = calculate_bounds_overlap_ratio(
                feature_bounds,
                grid_cell_bounds,
            )
            size_ratios = calculate_bounds_size_ratios(
                feature_bounds,
                grid_cell_bounds,
            )
            is_large_bounds = (
                size_ratios["area_ratio"] > MAX_EXPRESSWAY_BOUNDS_AREA_RATIO_FOR_LOG
                or size_ratios["height_ratio"]
                > MAX_EXPRESSWAY_BOUNDS_LENGTH_RATIO_FOR_LOG
                or size_ratios["width_ratio"]
                > MAX_EXPRESSWAY_BOUNDS_LENGTH_RATIO_FOR_LOG
            )

            _store_max_overlap(
                cell_overlaps_by_type["expressway"],
                cell_key,
                overlap_ratio,
            )
            _store_max_overlap(
                cell_overlaps_by_type[expressway_field],
                cell_key,
                overlap_ratio,
            )
            if is_large_bounds:
                is_large_feature = True
                large_bounds_cell_keys.add(cell_key)

        if is_large_feature:
            bounds_summary["expressway_large_bounds_features"] += 1

    _set_overlap_summary(
        bounds_summary,
        "expressway",
        cell_overlaps_by_type["expressway"],
    )
    bounds_summary["expressway_large_bounds_cells"] = len(large_bounds_cell_keys)
    for expressway_type in EXPRESSWAY_SUMMARY_KEYS:
        expressway_field = _expressway_summary_field(expressway_type)
        _set_overlap_summary(
            bounds_summary,
            expressway_field,
            cell_overlaps_by_type[expressway_field],
        )

    return bounds_summary


def _is_large_expressway_bounds_for_grid_cell(feature_bounds, grid_cell_bounds):
    size_ratios = calculate_bounds_size_ratios(feature_bounds, grid_cell_bounds)
    return (
        size_ratios["area_ratio"] > MAX_EXPRESSWAY_BOUNDS_AREA_RATIO_FOR_LOG
        or size_ratios["height_ratio"]
        > MAX_EXPRESSWAY_BOUNDS_LENGTH_RATIO_FOR_LOG
        or size_ratios["width_ratio"]
        > MAX_EXPRESSWAY_BOUNDS_LENGTH_RATIO_FOR_LOG
    )


def summarize_effective_expressway_feature_matches_for_grid_cell_contexts(
    grid_cell_contexts,
    map_features,
):
    """Summarize expressways after excluding large-bounds candidates."""
    if not isinstance(grid_cell_contexts, list):
        raise ValueError("grid_cell_contexts はリストで指定してください。")
    if not isinstance(map_features, list):
        raise ValueError("map_features はリストで指定してください。")

    effective_summary = _empty_effective_expressway_summary()
    cell_overlaps_by_type = {"effective_expressway": {}}
    for expressway_type in EXPRESSWAY_SUMMARY_KEYS:
        expressway_field = _expressway_summary_field(expressway_type)
        cell_overlaps_by_type[f"effective_{expressway_field}"] = {}
    filtered_large_bounds_cell_keys = set()
    grid_cell_entries = _build_grid_cell_entries_for_summary(grid_cell_contexts)

    for feature in map_features:
        if not isinstance(feature, dict):
            raise ValueError("map_features の各要素は辞書で指定してください。")
        if feature.get("kind") != "expressway":
            continue

        expressway_type = classify_expressway_feature_type(feature)
        expressway_field = _expressway_summary_field(expressway_type)
        feature_bounds = _normalize_bounds(feature.get("bounds"))
        intersecting_overlaps = []
        large_bounds_cell_keys = set()

        for cell_key, grid_cell_bounds in grid_cell_entries:
            if not feature_intersects_grid_cell(feature_bounds, grid_cell_bounds):
                continue

            overlap_ratio = calculate_bounds_overlap_ratio(
                feature_bounds,
                grid_cell_bounds,
            )
            intersecting_overlaps.append((cell_key, overlap_ratio))
            if _is_large_expressway_bounds_for_grid_cell(
                feature_bounds,
                grid_cell_bounds,
            ):
                large_bounds_cell_keys.add(cell_key)

        if large_bounds_cell_keys:
            effective_summary["filtered_expressway_large_bounds_features"] += 1
            filtered_large_bounds_cell_keys.update(large_bounds_cell_keys)
            continue

        effective_summary["effective_expressway_features"] += 1
        effective_summary[f"effective_{expressway_field}_features"] += 1
        for cell_key, overlap_ratio in intersecting_overlaps:
            _store_max_overlap(
                cell_overlaps_by_type["effective_expressway"],
                cell_key,
                overlap_ratio,
            )
            _store_max_overlap(
                cell_overlaps_by_type[f"effective_{expressway_field}"],
                cell_key,
                overlap_ratio,
            )

    effective_summary["filtered_expressway_large_bounds_cells"] = len(
        filtered_large_bounds_cell_keys
    )
    _set_overlap_summary(
        effective_summary,
        "effective_expressway",
        cell_overlaps_by_type["effective_expressway"],
    )
    for expressway_type in EXPRESSWAY_SUMMARY_KEYS:
        expressway_field = _expressway_summary_field(expressway_type)
        _set_overlap_summary(
            effective_summary,
            f"effective_{expressway_field}",
            cell_overlaps_by_type[f"effective_{expressway_field}"],
        )

    return effective_summary


def summarize_waterway_river_bounds_for_map_area(
    map_area_bounds,
    map_features,
    grid_cell_contexts=None,
):
    """Summarize waterway=river bbox size ratios against a MapArea bbox."""
    map_area_bounds = _normalize_bounds(map_area_bounds)
    if not isinstance(map_features, list):
        raise ValueError("map_features はリストで指定してください。")
    grid_cell_entries = []
    if grid_cell_contexts is not None:
        if not isinstance(grid_cell_contexts, list):
            raise ValueError("grid_cell_contexts はリストで指定してください。")
        for index, grid_cell_context in enumerate(grid_cell_contexts):
            if not isinstance(grid_cell_context, dict):
                raise ValueError("grid_cell_contexts の各要素は辞書で指定してください。")
            grid_cell_entries.append(
                (
                    (
                        grid_cell_context.get("row_index", index),
                        grid_cell_context.get("col_index", index),
                    ),
                    _normalize_bounds(
                        {
                            "north": grid_cell_context.get("north"),
                            "south": grid_cell_context.get("south"),
                            "east": grid_cell_context.get("east"),
                            "west": grid_cell_context.get("west"),
                        }
                    ),
                )
            )

    bounds_summary = _empty_waterway_river_bounds_summary()
    filtered_cell_keys = set()

    for feature in map_features:
        if not isinstance(feature, dict):
            raise ValueError("map_features の各要素は辞書で指定してください。")
        if feature.get("kind") != "river" or feature.get("source_waterway") != "river":
            continue

        bounds_summary["waterway_river_bounds_features"] += 1
        feature_bounds = _normalize_bounds(feature.get("bounds"))
        size_ratios = calculate_bounds_size_ratios(feature_bounds, map_area_bounds)
        bounds_summary["waterway_river_bounds_max_area_ratio_to_map"] = max(
            bounds_summary["waterway_river_bounds_max_area_ratio_to_map"],
            size_ratios["area_ratio"],
        )
        bounds_summary["waterway_river_bounds_max_height_ratio_to_map"] = max(
            bounds_summary["waterway_river_bounds_max_height_ratio_to_map"],
            size_ratios["height_ratio"],
        )
        bounds_summary["waterway_river_bounds_max_width_ratio_to_map"] = max(
            bounds_summary["waterway_river_bounds_max_width_ratio_to_map"],
            size_ratios["width_ratio"],
        )

        if feature_intersects_grid_cell(feature_bounds, map_area_bounds):
            bounds_summary["waterway_river_bounds_intersecting_map_features"] += 1
        if _feature_covers_grid_cell(feature_bounds, map_area_bounds):
            bounds_summary["waterway_river_bounds_covering_map_features"] += 1
        if is_large_waterway_river_bounds_for_map_area(
            feature_bounds,
            map_area_bounds,
        ):
            bounds_summary["waterway_river_bounds_large_area_features"] += 1
            bounds_summary["waterway_river_bounds_filtered_features"] += 1
            for cell_key, grid_cell_bounds in grid_cell_entries:
                if feature_intersects_grid_cell(feature_bounds, grid_cell_bounds):
                    filtered_cell_keys.add(cell_key)

    bounds_summary["waterway_river_bounds_filtered_cells"] = len(filtered_cell_keys)

    return bounds_summary


def summarize_waterway_feature_matches_for_grid_cell_contexts(
    grid_cell_contexts,
    map_features,
):
    """Summarize source waterway tag counts for log output only."""
    if not isinstance(grid_cell_contexts, list):
        raise ValueError("grid_cell_contexts はリストで指定してください。")
    if not isinstance(map_features, list):
        raise ValueError("map_features はリストで指定してください。")

    waterway_summary = _empty_waterway_feature_match_summary()
    cell_keys_by_waterway = {waterway: set() for waterway in WATERWAY_SUMMARY_KEYS}
    grid_cell_entries = []

    for index, grid_cell_context in enumerate(grid_cell_contexts):
        if not isinstance(grid_cell_context, dict):
            raise ValueError("grid_cell_contexts の各要素は辞書で指定してください。")

        grid_cell_bounds = {
            "north": grid_cell_context.get("north"),
            "south": grid_cell_context.get("south"),
            "east": grid_cell_context.get("east"),
            "west": grid_cell_context.get("west"),
        }
        grid_cell_entries.append(
            (
                (
                    grid_cell_context.get("row_index", index),
                    grid_cell_context.get("col_index", index),
                ),
                _normalize_bounds(grid_cell_bounds),
            )
        )

    for feature in map_features:
        if not isinstance(feature, dict):
            raise ValueError("map_features の各要素は辞書で指定してください。")
        if feature.get("kind") != "river":
            continue

        waterway_key = _waterway_summary_key(feature.get("source_waterway"))
        waterway_summary[f"waterway_{waterway_key}_features"] += 1
        feature_bounds = _normalize_bounds(feature.get("bounds"))

        for cell_key, grid_cell_bounds in grid_cell_entries:
            if feature_intersects_grid_cell(feature_bounds, grid_cell_bounds):
                cell_keys_by_waterway[waterway_key].add(cell_key)

    for waterway in WATERWAY_SUMMARY_KEYS:
        waterway_summary[f"waterway_{waterway}_cells"] = len(
            cell_keys_by_waterway[waterway]
        )

    return waterway_summary


def summarize_river_feature_matches_for_grid_cell_contexts(
    grid_cell_contexts,
    map_features,
):
    """Summarize river bbox matches for log output without changing scoring."""
    if not isinstance(grid_cell_contexts, list):
        raise ValueError("grid_cell_contexts はリストで指定してください。")
    if not isinstance(map_features, list):
        raise ValueError("map_features はリストで指定してください。")

    river_summary = _empty_river_feature_match_summary()
    marked_river_overlaps = []

    for grid_cell_context in grid_cell_contexts:
        if not isinstance(grid_cell_context, dict):
            raise ValueError("grid_cell_contexts の各要素は辞書で指定してください。")

        grid_cell_bounds = {
            "north": grid_cell_context.get("north"),
            "south": grid_cell_context.get("south"),
            "east": grid_cell_context.get("east"),
            "west": grid_cell_context.get("west"),
        }
        grid_cell_bounds = _normalize_bounds(grid_cell_bounds)
        cell_marked_overlaps = []
        has_large_bounds = False
        has_small_overlap = False

        for feature in map_features:
            if not isinstance(feature, dict):
                raise ValueError("map_features の各要素は辞書で指定してください。")
            if feature.get("kind") != "river":
                continue

            feature_bounds = _normalize_bounds(feature.get("bounds"))
            if not feature_intersects_grid_cell(feature_bounds, grid_cell_bounds):
                continue

            size_ratios = calculate_bounds_size_ratios(
                feature_bounds,
                grid_cell_bounds,
            )
            overlap_ratio = calculate_bounds_overlap_ratio(
                feature_bounds,
                grid_cell_bounds,
            )
            is_large_river_bounds = (
                size_ratios["area_ratio"] > MAX_RIVER_BOUNDS_AREA_RATIO_FOR_INTERSECTION
                or size_ratios["height_ratio"]
                > MAX_RIVER_BOUNDS_LENGTH_RATIO_FOR_INTERSECTION
                or size_ratios["width_ratio"]
                > MAX_RIVER_BOUNDS_LENGTH_RATIO_FOR_INTERSECTION
            )

            if is_large_river_bounds:
                has_large_bounds = True
            if overlap_ratio < MIN_LARGE_RIVER_OVERLAP_RATIO_FOR_INTERSECTION:
                has_small_overlap = True
            if (
                not is_large_river_bounds
                or overlap_ratio >= MIN_LARGE_RIVER_OVERLAP_RATIO_FOR_INTERSECTION
            ):
                cell_marked_overlaps.append(overlap_ratio)

        if cell_marked_overlaps:
            marked_river_overlaps.append(max(cell_marked_overlaps))
        if has_large_bounds:
            river_summary["river_large_bounds_cells"] += 1
        if has_small_overlap:
            river_summary["river_small_overlap_cells"] += 1

    river_summary["river_cells"] = len(marked_river_overlaps)
    if marked_river_overlaps:
        river_summary["river_avg_overlap"] = (
            sum(marked_river_overlaps) / len(marked_river_overlaps)
        )
        river_summary["river_max_overlap"] = max(marked_river_overlaps)

    return river_summary


def build_overpass_bbox_for_map_area(map_area, padding_meters=0):
    """Build an Overpass bbox dict from MapArea bounds."""
    bounds = _normalize_bounds(
        {
            "north": getattr(map_area, "north", None),
            "south": getattr(map_area, "south", None),
            "east": getattr(map_area, "east", None),
            "west": getattr(map_area, "west", None),
        }
    )

    if isinstance(padding_meters, bool):
        raise ValueError("padding_meters は 0 以上の数値で指定してください。")

    try:
        padding_meters = float(padding_meters)
    except (TypeError, ValueError):
        raise ValueError("padding_meters は 0 以上の数値で指定してください。")

    if not isfinite(padding_meters) or padding_meters < 0:
        raise ValueError("padding_meters は 0 以上の数値で指定してください。")

    if padding_meters == 0:
        return bounds

    center_lat = (bounds["north"] + bounds["south"]) / 2
    longitude_cosine = cos(radians(center_lat))
    if abs(longitude_cosine) < MIN_LONGITUDE_COSINE:
        raise ValueError("中心緯度が極域に近すぎるため経度方向のpaddingを計算できません。")

    lat_padding = padding_meters / METERS_PER_DEGREE
    lng_padding = padding_meters / (METERS_PER_DEGREE * longitude_cosine)

    return {
        "north": bounds["north"] + lat_padding,
        "south": bounds["south"] - lat_padding,
        "east": bounds["east"] + lng_padding,
        "west": bounds["west"] - lng_padding,
    }


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


def calculate_bounds_overlap_ratio(feature_bounds, grid_cell_bounds):
    """Return the overlap area ratio within one GridCell bbox.

    Coverage ratios let wide features such as water, forest, and parks affect
    scoring by how much of the cell they occupy, not just by existing nearby.
    """
    feature_bounds = _normalize_bounds(feature_bounds)
    grid_cell_bounds = _normalize_bounds(grid_cell_bounds)

    overlap_height = max(
        0.0,
        min(feature_bounds["north"], grid_cell_bounds["north"])
        - max(feature_bounds["south"], grid_cell_bounds["south"]),
    )
    overlap_width = max(
        0.0,
        min(feature_bounds["east"], grid_cell_bounds["east"])
        - max(feature_bounds["west"], grid_cell_bounds["west"]),
    )
    grid_cell_area = (
        (grid_cell_bounds["north"] - grid_cell_bounds["south"])
        * (grid_cell_bounds["east"] - grid_cell_bounds["west"])
    )
    overlap_area = overlap_height * overlap_width

    return min(max(overlap_area / grid_cell_area, 0.0), 1.0)


def calculate_bounds_size_ratios(feature_bounds, grid_cell_bounds):
    """Return feature bbox size ratios against another bbox."""
    feature_bounds = _normalize_bounds(feature_bounds)
    grid_cell_bounds = _normalize_bounds(grid_cell_bounds)

    feature_height = feature_bounds["north"] - feature_bounds["south"]
    feature_width = feature_bounds["east"] - feature_bounds["west"]
    grid_cell_height = grid_cell_bounds["north"] - grid_cell_bounds["south"]
    grid_cell_width = grid_cell_bounds["east"] - grid_cell_bounds["west"]
    height_ratio = feature_height / grid_cell_height
    width_ratio = feature_width / grid_cell_width

    return {
        "height_ratio": height_ratio,
        "width_ratio": width_ratio,
        "area_ratio": height_ratio * width_ratio,
    }


def is_large_waterway_river_bounds_for_map_area(feature_bounds, map_area_bounds):
    """Return True when a waterway=river bbox is too large for MapArea scoring.

    Some OSM river bounds cover an area much wider than the visible river. Using
    them as-is can make unrelated cells look like river cells.
    """
    size_ratios = calculate_bounds_size_ratios(feature_bounds, map_area_bounds)
    return (
        size_ratios["area_ratio"]
        >= MAX_WATERWAY_RIVER_BOUNDS_AREA_RATIO_TO_MAP_FOR_GRID_CELL
    )


def should_use_river_feature_for_grid_cell(feature, map_area_bounds):
    """Return False for MapArea-scale waterway=river bounds that over-mark cells."""
    if map_area_bounds is None:
        return True
    map_area_bounds = _normalize_bounds(map_area_bounds)

    if not isinstance(feature, dict):
        raise ValueError("feature は辞書で指定してください。")
    if feature.get("kind") != "river" or feature.get("source_waterway") != "river":
        return True

    return not is_large_waterway_river_bounds_for_map_area(
        feature.get("bounds"),
        map_area_bounds,
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


def build_feature_summary_for_grid_cell(
    grid_cell_bounds,
    map_features,
    map_area_bounds=None,
):
    """Build feature summary for one GridCell from provisional bbox features.

    The summary keeps both simple presence counts and overlap ratios so the
    scorer can distinguish "contains a feature" from "mostly covered by it".
    """
    grid_cell_bounds = _normalize_bounds(grid_cell_bounds)
    if map_area_bounds is not None:
        map_area_bounds = _normalize_bounds(map_area_bounds)
    if not isinstance(map_features, list):
        raise ValueError("map_features はリストで指定してください。")

    feature_summary = {
        "building_count": 0,
        "road_count": 0,
        "water_coverage_ratio": 0.0,
        "forest_coverage_ratio": 0.0,
        "park_coverage_ratio": 0.0,
        "river_coverage_ratio": 0.0,
        "surface_railway_count": 0,
        "underground_railway_count": 0,
        "unknown_railway_count": 0,
        "railway_station_count": 0,
        "railway_halt_count": 0,
        "subway_station_count": 0,
        "bus_station_count": 0,
        "public_transport_station_count": 0,
        "unknown_station_count": 0,
        "station_cluster_count": 0,
        "dense_station_cluster_count": 0,
        "station_proximity_near_count": 0,
        "station_proximity_mid_count": 0,
        "motorway_count": 0,
        "motorway_link_count": 0,
        "trunk_count": 0,
        "trunk_link_count": 0,
        "unknown_expressway_count": 0,
        "tourism_attraction_count": 0,
        "tourism_museum_count": 0,
        "tourism_gallery_count": 0,
        "tourism_viewpoint_count": 0,
        "historic_castle_count": 0,
        "historic_monument_count": 0,
        "historic_memorial_count": 0,
        "historic_ruins_count": 0,
        "historic_archaeological_site_count": 0,
        "unknown_landmark_count": 0,
        "castle_near_proximity_count": 0,
        "castle_mid_proximity_count": 0,
        "castle_far_proximity_count": 0,
        "has_park": False,
        "has_river": False,
        "is_coastal": False,
    }
    station_centers = []
    station_proximity_entries = _scored_station_centers_from_map_features(
        map_features
    )
    station_proximity_centers = [
        station_center for _station_bounds, station_center in station_proximity_entries
    ]
    castle_centers = _castle_centers_from_map_features(map_features)
    building_mode = normalize_auto_score_building_mode()

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
            "railway",
            "station",
            "expressway",
            "landmark",
        }:
            continue

        if feature_kind == "building":
            building_position = _building_position_for_grid_cell(
                feature,
                building_mode,
            )
            if building_position is None:
                continue
            position_type, position_value = building_position
            if position_type == "bounds":
                if feature_intersects_grid_cell(position_value, grid_cell_bounds):
                    feature_summary["building_count"] += 1
                continue
            if _point_in_bounds(position_value, grid_cell_bounds):
                feature_summary["building_count"] += 1
            continue

        if feature_kind in {"station", "landmark"}:
            feature_match = _feature_match_for_grid_cell_by_bounds_or_center(
                feature,
                grid_cell_bounds,
            )
            if feature_match is None:
                continue

            if feature_kind == "station":
                station_type = classify_station_feature_type(feature)
                if station_type == "unknown":
                    feature_summary["unknown_station_count"] += 1
                else:
                    feature_summary[f"{station_type}_count"] += 1
                    if station_type in SCORED_STATION_SUMMARY_TYPES:
                        station_centers.append(feature_match[2])
                continue

            landmark_type = classify_landmark_feature_type(feature)
            if landmark_type == "unknown":
                feature_summary["unknown_landmark_count"] += 1
            else:
                feature_summary[f"{landmark_type}_count"] += 1
            continue

        feature_bounds = _normalize_bounds(feature.get("bounds"))
        if not feature_intersects_grid_cell(feature_bounds, grid_cell_bounds):
            continue

        if feature_kind == "road":
            # Very large road bounds are often coarse OSM geometry, so they are
            # ignored for road counts to avoid making every nearby cell busy.
            size_ratios = calculate_bounds_size_ratios(
                feature_bounds,
                grid_cell_bounds,
            )
            if (
                size_ratios["area_ratio"] <= MAX_ROAD_BOUNDS_AREA_RATIO_FOR_COUNT
                and size_ratios["height_ratio"]
                <= MAX_ROAD_BOUNDS_LENGTH_RATIO_FOR_COUNT
                and size_ratios["width_ratio"] <= MAX_ROAD_BOUNDS_LENGTH_RATIO_FOR_COUNT
            ):
                feature_summary["road_count"] += 1
        elif feature_kind == "water":
            feature_summary["water_coverage_ratio"] = max(
                feature_summary["water_coverage_ratio"],
                calculate_bounds_overlap_ratio(feature_bounds, grid_cell_bounds),
            )
        elif feature_kind == "forest":
            feature_summary["forest_coverage_ratio"] = max(
                feature_summary["forest_coverage_ratio"],
                calculate_bounds_overlap_ratio(feature_bounds, grid_cell_bounds),
            )
        elif feature_kind == "park":
            feature_summary["park_coverage_ratio"] = max(
                feature_summary["park_coverage_ratio"],
                calculate_bounds_overlap_ratio(feature_bounds, grid_cell_bounds),
            )
            feature_summary["has_park"] = True
        elif feature_kind == "river":
            # MapArea-scale waterway=river bboxes can over-mark every GridCell.
            if not should_use_river_feature_for_grid_cell(feature, map_area_bounds):
                continue

            size_ratios = calculate_bounds_size_ratios(
                feature_bounds,
                grid_cell_bounds,
            )
            overlap_ratio = calculate_bounds_overlap_ratio(
                feature_bounds,
                grid_cell_bounds,
            )
            is_large_river_bounds = (
                size_ratios["area_ratio"] > MAX_RIVER_BOUNDS_AREA_RATIO_FOR_INTERSECTION
                or size_ratios["height_ratio"]
                > MAX_RIVER_BOUNDS_LENGTH_RATIO_FOR_INTERSECTION
                or size_ratios["width_ratio"]
                > MAX_RIVER_BOUNDS_LENGTH_RATIO_FOR_INTERSECTION
            )
            # GridCell-scale large river bboxes still count when overlap is meaningful.
            if (
                not is_large_river_bounds
                or overlap_ratio >= MIN_LARGE_RIVER_OVERLAP_RATIO_FOR_INTERSECTION
            ):
                feature_summary["river_coverage_ratio"] = max(
                    feature_summary["river_coverage_ratio"],
                    overlap_ratio,
                )
        elif feature_kind == "coastline":
            feature_summary["is_coastal"] = True
        elif feature_kind == "railway":
            railway_type = classify_railway_feature_surface_type(feature)
            feature_summary[f"{railway_type}_railway_count"] += 1
        elif feature_kind == "expressway":
            # Expressway bounds can be much larger than the actual road segment;
            # counting only local-sized bounds keeps the score from spreading.
            if _is_large_expressway_bounds_for_grid_cell(
                feature_bounds,
                grid_cell_bounds,
            ):
                continue
            expressway_type = classify_expressway_feature_type(feature)
            if expressway_type == "unknown":
                feature_summary["unknown_expressway_count"] += 1
            else:
                feature_summary[f"{expressway_type}_count"] += 1

    feature_summary["station_cluster_count"] = _max_station_cluster_size(
        station_centers,
        STATION_BROAD_CLUSTER_DISTANCE_METERS,
    )
    feature_summary["dense_station_cluster_count"] = _max_station_cluster_size(
        station_centers,
        STATION_DENSE_CLUSTER_DISTANCE_METERS,
    )
    station_proximity_band, _station_proximity_distance = (
        _station_proximity_band_for_grid_cell(
            grid_cell_bounds,
            station_proximity_centers,
        )
    )
    if station_proximity_band is not None:
        feature_summary[f"station_proximity_{station_proximity_band}_count"] = 1
    castle_proximity_band, _castle_proximity_distance = (
        _castle_proximity_band_for_grid_cell(grid_cell_bounds, castle_centers)
    )
    if castle_proximity_band is not None:
        feature_summary[f"castle_{castle_proximity_band}_proximity_count"] = 1
    feature_summary["has_river"] = (
        feature_summary["river_coverage_ratio"] >= MIN_RIVER_COVERAGE_RATIO_FOR_HAS_RIVER
    )

    return feature_summary


def build_feature_summaries_for_grid_cells(grid_cells, map_features):
    """Build feature summaries keyed by each saved GridCell position."""
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


def build_feature_summaries_for_grid_cell_contexts(
    grid_cell_contexts,
    map_features,
    map_area_bounds=None,
):
    """Build feature summaries keyed by each unsaved GridCell context position.

    Create-time auto scoring runs before GridCell rows are saved, so it uses the
    same summary logic against temporary context dictionaries.
    """
    if not isinstance(grid_cell_contexts, list):
        raise ValueError("grid_cell_contexts はリストで指定してください。")
    if map_area_bounds is not None:
        map_area_bounds = _normalize_bounds(map_area_bounds)

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
            build_feature_summary_for_grid_cell(
                grid_cell_bounds,
                map_features,
                map_area_bounds=map_area_bounds,
            )
        )

    return feature_summaries


def calculate_initial_score_breakdown_from_feature_summary(
    feature_summary,
    grid_size_meters=None,
):
    """Calculate score details from feature summary data.

    Auto scoring is split into base, diversity, context, and penalty so the UI
    can explain why a GridCell received its initial score.
    """
    if not isinstance(feature_summary, dict):
        raise ValueError("feature_summary は辞書で指定してください。")

    building_count = _feature_number(feature_summary, "building_count")
    road_count = _feature_number(feature_summary, "road_count")
    surface_railway_count = _feature_number(
        feature_summary,
        "surface_railway_count",
    )
    underground_railway_count = _feature_number(
        feature_summary,
        "underground_railway_count",
    )
    unknown_railway_count = _feature_number(
        feature_summary,
        "unknown_railway_count",
    )
    railway_station_count = _feature_number(
        feature_summary,
        "railway_station_count",
    )
    railway_halt_count = _feature_number(
        feature_summary,
        "railway_halt_count",
    )
    subway_station_count = _feature_number(
        feature_summary,
        "subway_station_count",
    )
    bus_station_count = _feature_number(
        feature_summary,
        "bus_station_count",
    )
    public_transport_station_count = _feature_number(
        feature_summary,
        "public_transport_station_count",
    )
    unknown_station_count = _feature_number(
        feature_summary,
        "unknown_station_count",
    )
    station_cluster_count = _feature_number(
        feature_summary,
        "station_cluster_count",
    )
    dense_station_cluster_count = _feature_number(
        feature_summary,
        "dense_station_cluster_count",
    )
    station_proximity_near_count = _feature_number(
        feature_summary,
        "station_proximity_near_count",
    )
    station_proximity_mid_count = _feature_number(
        feature_summary,
        "station_proximity_mid_count",
    )
    motorway_count = _feature_number(feature_summary, "motorway_count")
    motorway_link_count = _feature_number(feature_summary, "motorway_link_count")
    trunk_count = _feature_number(feature_summary, "trunk_count")
    trunk_link_count = _feature_number(feature_summary, "trunk_link_count")
    unknown_expressway_count = _feature_number(
        feature_summary,
        "unknown_expressway_count",
    )
    tourism_attraction_count = _feature_number(
        feature_summary,
        "tourism_attraction_count",
    )
    tourism_museum_count = _feature_number(
        feature_summary,
        "tourism_museum_count",
    )
    tourism_gallery_count = _feature_number(
        feature_summary,
        "tourism_gallery_count",
    )
    tourism_viewpoint_count = _feature_number(
        feature_summary,
        "tourism_viewpoint_count",
    )
    historic_castle_count = _feature_number(
        feature_summary,
        "historic_castle_count",
    )
    historic_monument_count = _feature_number(
        feature_summary,
        "historic_monument_count",
    )
    historic_memorial_count = _feature_number(
        feature_summary,
        "historic_memorial_count",
    )
    historic_ruins_count = _feature_number(
        feature_summary,
        "historic_ruins_count",
    )
    historic_archaeological_site_count = _feature_number(
        feature_summary,
        "historic_archaeological_site_count",
    )
    unknown_landmark_count = _feature_number(
        feature_summary,
        "unknown_landmark_count",
    )
    castle_near_proximity_count = _feature_number(
        feature_summary,
        "castle_near_proximity_count",
    )
    castle_mid_proximity_count = _feature_number(
        feature_summary,
        "castle_mid_proximity_count",
    )
    castle_far_proximity_count = _feature_number(
        feature_summary,
        "castle_far_proximity_count",
    )
    water_coverage_ratio = _feature_ratio(feature_summary, "water_coverage_ratio")
    forest_coverage_ratio = _feature_ratio(feature_summary, "forest_coverage_ratio")
    has_park_value = bool(feature_summary.get("has_park", False))
    _feature_ratio(
        feature_summary,
        "park_coverage_ratio",
        1.0 if has_park_value else 0.0,
    )
    has_park = has_park_value
    has_river_value = bool(feature_summary.get("has_river", False))
    river_coverage_ratio = _feature_ratio(
        feature_summary,
        "river_coverage_ratio",
        1.0 if has_river_value else 0.0,
    )
    has_river = (
        has_river_value
        or river_coverage_ratio >= MIN_RIVER_COVERAGE_RATIO_FOR_HAS_RIVER
    )
    has_scored_forest = (
        forest_coverage_ratio >= MIN_FOREST_COVERAGE_RATIO_FOR_SCORE
    )
    is_coastal = bool(feature_summary.get("is_coastal", False))
    has_building = building_count > 0
    has_road = road_count > 0
    has_water = water_coverage_ratio > 0

    building_base_bonus = (
        min(building_count / BUILDING_COUNT_FOR_MAX_BASE_SCORE, 1.0)
        * BUILDING_BASE_SCORE_MAX_BONUS
    )
    road_base_bonus = (
        min(road_count / ROAD_COUNT_FOR_MAX_BASE_SCORE, 1.0)
        * ROAD_BASE_SCORE_MAX_BONUS
    )
    base_score = BASE_INITIAL_SCORE + building_base_bonus + road_base_bonus

    feature_categories = [
        has_building,
        has_park,
        has_river,
        is_coastal,
        has_water,
        has_scored_forest,
    ]
    feature_category_count = sum(feature_categories)
    diversity_bonus = min(feature_category_count * 0.18, 0.9)

    has_park_context = has_park and has_building
    has_river_context = has_river and has_building
    has_coastal_context = is_coastal and (has_building or has_road)
    has_forest_context = has_scored_forest and has_building
    has_surface_railway_context = surface_railway_count > 0
    has_surface_station_context = (
        railway_station_count > 0 or railway_halt_count > 0
    )
    has_subway_station_context = subway_station_count > 0
    has_public_transport_station_context = public_transport_station_count > 0
    scored_station_count = (
        railway_station_count
        + railway_halt_count
        + subway_station_count
        + public_transport_station_count
    )
    has_dense_station_cluster_context = dense_station_cluster_count >= 2
    has_major_station_cluster_context = (
        station_cluster_count >= STATION_DENSITY_MAJOR_CLUSTER_MIN_FEATURES
    )
    has_station_proximity_near = station_proximity_near_count > 0
    has_station_proximity_mid = station_proximity_mid_count > 0
    is_station_proximity_station_cell = scored_station_count > 0
    if is_station_proximity_station_cell:
        station_proximity_bonus = 0.0
    elif has_station_proximity_near:
        station_proximity_bonus = STATION_PROXIMITY_NEAR_CONTEXT_BONUS
    elif has_station_proximity_mid:
        station_proximity_bonus = STATION_PROXIMITY_MID_CONTEXT_BONUS
    else:
        station_proximity_bonus = 0.0
    has_station_proximity_context = station_proximity_bonus > 0
    has_motorway_context = motorway_count > 0 or motorway_link_count > 0
    has_trunk_context = trunk_count > 0 or trunk_link_count > 0
    landmark_counts = {
        "tourism_attraction": tourism_attraction_count,
        "tourism_museum": tourism_museum_count,
        "tourism_gallery": tourism_gallery_count,
        "tourism_viewpoint": tourism_viewpoint_count,
        "historic_castle": historic_castle_count,
        "historic_monument": historic_monument_count,
        "historic_memorial": historic_memorial_count,
        "historic_ruins": historic_ruins_count,
        "historic_archaeological_site": historic_archaeological_site_count,
    }
    landmark_context_bonuses = {
        f"{landmark_type}_context_bonus": (
            LANDMARK_CONTEXT_BONUSES[landmark_type]
            if count > 0
            else 0.0
        )
        for landmark_type, count in landmark_counts.items()
    }
    landmark_context_bonus = min(
        sum(landmark_context_bonuses.values()),
        LANDMARK_CONTEXT_BONUS_CAP,
    )
    has_landmark_context = landmark_context_bonus > 0
    has_castle_near_proximity = castle_near_proximity_count > 0
    has_castle_mid_proximity = castle_mid_proximity_count > 0
    has_castle_far_proximity = castle_far_proximity_count > 0
    has_castle_proximity = (
        has_castle_near_proximity
        or has_castle_mid_proximity
        or has_castle_far_proximity
    )
    has_historic_castle = historic_castle_count > 0
    is_castle_proximity_skipped_castle_cell = (
        has_historic_castle and has_castle_proximity
    )
    if has_historic_castle:
        castle_proximity_bonus = 0.0
    elif has_castle_near_proximity:
        castle_proximity_bonus = CASTLE_NEAR_CONTEXT_BONUS
    elif has_castle_mid_proximity:
        castle_proximity_bonus = CASTLE_MID_CONTEXT_BONUS
    elif has_castle_far_proximity:
        castle_proximity_bonus = CASTLE_FAR_CONTEXT_BONUS
    else:
        castle_proximity_bonus = 0.0
    has_castle_proximity_context = castle_proximity_bonus > 0
    is_likely_unreachable_water_cell = (
        water_coverage_ratio >= 0.95
        and not has_building
        and not has_road
        and not has_park
        and not has_river
    )
    has_waterfront_context = (
        has_water
        and not is_likely_unreachable_water_cell
        and (has_building or has_road or has_park or has_river)
    )
    has_park_waterfront_combo_context = has_park and has_waterfront_context
    park_waterfront_combo_bonus = (
        PARK_WATERFRONT_COMBO_CONTEXT_BONUS
        if has_park_waterfront_combo_context
        else 0.0
    )

    has_station_context = (
        has_surface_station_context
        or has_subway_station_context
        or has_public_transport_station_context
    )
    context_candidate_count = sum(
        (
            has_park_context,
            has_waterfront_context,
            has_river_context,
            has_surface_railway_context,
            has_station_context,
            has_dense_station_cluster_context or has_major_station_cluster_context,
            has_motorway_context,
            has_trunk_context,
            has_landmark_context,
            has_castle_proximity_context,
        )
    )
    has_high_context_3_context = context_candidate_count >= 3
    has_high_context_4_context = context_candidate_count >= 4
    has_high_context_5_context = context_candidate_count >= 5
    if has_high_context_5_context:
        high_context_bonus = HIGH_CONTEXT_5_CONTEXT_BONUS
    elif has_high_context_4_context:
        high_context_bonus = HIGH_CONTEXT_4_CONTEXT_BONUS
    elif has_high_context_3_context:
        high_context_bonus = HIGH_CONTEXT_3_CONTEXT_BONUS
    else:
        high_context_bonus = 0.0

    context_bonus = 0.0
    if has_park_context:
        context_bonus += 0.2
    if has_river_context:
        context_bonus += 0.25
    if has_coastal_context:
        context_bonus += 0.3
    if has_forest_context:
        context_bonus += 0.15
    if has_waterfront_context:
        context_bonus += WATERFRONT_CONTEXT_BONUS
    surface_railway_context_bonus = (
        SURFACE_RAILWAY_CONTEXT_BONUS if has_surface_railway_context else 0.0
    )
    context_bonus += surface_railway_context_bonus
    surface_station_context_bonus = (
        SURFACE_STATION_CONTEXT_BONUS
        if has_surface_station_context
        else 0.0
    )
    context_bonus += surface_station_context_bonus
    subway_station_context_bonus = (
        SUBWAY_STATION_CONTEXT_BONUS
        if has_subway_station_context
        else 0.0
    )
    context_bonus += subway_station_context_bonus
    public_transport_station_context_bonus = (
        PUBLIC_TRANSPORT_STATION_CONTEXT_BONUS
        if has_public_transport_station_context
        else 0.0
    )
    context_bonus += public_transport_station_context_bonus
    station_density_bonus = 0.0
    if has_dense_station_cluster_context:
        station_density_bonus += 0.40
    if has_major_station_cluster_context:
        station_density_bonus += 0.30
    station_density_bonus = min(station_density_bonus, 0.70)
    context_bonus += station_density_bonus
    motorway_context_bonus = (
        MOTORWAY_CONTEXT_BONUS if has_motorway_context else 0.0
    )
    context_bonus += motorway_context_bonus
    trunk_context_bonus = TRUNK_CONTEXT_BONUS if has_trunk_context else 0.0
    context_bonus += trunk_context_bonus
    context_bonus += landmark_context_bonus
    context_bonus += castle_proximity_bonus
    context_bonus += station_proximity_bonus
    context_bonus += park_waterfront_combo_bonus
    context_bonus += high_context_bonus

    has_water_penalty = is_likely_unreachable_water_cell
    has_forest_penalty = (
        forest_coverage_ratio >= 0.95 and not has_building and not has_road
    )
    has_empty_cell_penalty = not has_building and not has_road

    penalty = 0.0
    if has_water_penalty:
        penalty += 2.4
    if has_forest_penalty:
        penalty += 2.0
    if has_empty_cell_penalty:
        penalty += 0.6

    grid_size_multiplier = calculate_grid_size_score_multiplier(grid_size_meters)
    # Presence and diversity bonuses are easier to trigger in larger cells, so
    # only the positive bonus parts are size-adjusted. Penalty stays unchanged.
    base_score *= grid_size_multiplier
    diversity_bonus *= grid_size_multiplier
    context_bonus *= grid_size_multiplier

    raw_score = base_score + diversity_bonus + context_bonus - penalty
    clamped_score = _clamp_initial_score(raw_score)

    return {
        "base_score": base_score,
        "building_base_bonus": building_base_bonus,
        "road_base_bonus": road_base_bonus,
        "diversity_bonus": diversity_bonus,
        "context_bonus": context_bonus,
        "penalty": penalty,
        "raw_score": raw_score,
        "clamped_score": clamped_score,
        "grid_size_multiplier": grid_size_multiplier,
        "feature_category_count": feature_category_count,
        "surface_railway_count": surface_railway_count,
        "underground_railway_count": underground_railway_count,
        "unknown_railway_count": unknown_railway_count,
        "railway_station_count": railway_station_count,
        "railway_halt_count": railway_halt_count,
        "subway_station_count": subway_station_count,
        "bus_station_count": bus_station_count,
        "public_transport_station_count": public_transport_station_count,
        "unknown_station_count": unknown_station_count,
        "motorway_count": motorway_count,
        "motorway_link_count": motorway_link_count,
        "trunk_count": trunk_count,
        "trunk_link_count": trunk_link_count,
        "unknown_expressway_count": unknown_expressway_count,
        "tourism_attraction_count": tourism_attraction_count,
        "tourism_museum_count": tourism_museum_count,
        "tourism_gallery_count": tourism_gallery_count,
        "tourism_viewpoint_count": tourism_viewpoint_count,
        "historic_castle_count": historic_castle_count,
        "historic_monument_count": historic_monument_count,
        "historic_memorial_count": historic_memorial_count,
        "historic_ruins_count": historic_ruins_count,
        "historic_archaeological_site_count": historic_archaeological_site_count,
        "unknown_landmark_count": unknown_landmark_count,
        "castle_near_proximity_count": castle_near_proximity_count,
        "castle_mid_proximity_count": castle_mid_proximity_count,
        "castle_far_proximity_count": castle_far_proximity_count,
        "has_building": has_building,
        "has_road": has_road,
        "has_park": has_park,
        "has_river": has_river,
        "has_water": has_water,
        "has_scored_forest": has_scored_forest,
        "is_coastal": is_coastal,
        "has_park_context": has_park_context,
        "has_river_context": has_river_context,
        "has_forest_context": has_forest_context,
        "has_coastal_context": has_coastal_context,
        "has_surface_railway_context": has_surface_railway_context,
        "surface_railway_context_bonus": surface_railway_context_bonus,
        "has_surface_station_context": has_surface_station_context,
        "surface_station_context_bonus": surface_station_context_bonus,
        "has_subway_station_context": has_subway_station_context,
        "subway_station_context_bonus": subway_station_context_bonus,
        "has_public_transport_station_context": (
            has_public_transport_station_context
        ),
        "public_transport_station_context_bonus": (
            public_transport_station_context_bonus
        ),
        "scored_station_count": scored_station_count,
        "station_cluster_count": station_cluster_count,
        "dense_station_cluster_count": dense_station_cluster_count,
        "station_proximity_near_count": station_proximity_near_count,
        "station_proximity_mid_count": station_proximity_mid_count,
        "station_density_bonus": station_density_bonus,
        "has_dense_station_cluster_context": has_dense_station_cluster_context,
        "has_major_station_cluster_context": has_major_station_cluster_context,
        "has_station_proximity_context": has_station_proximity_context,
        "has_station_proximity_near_context": (
            has_station_proximity_context and has_station_proximity_near
        ),
        "has_station_proximity_mid_context": (
            has_station_proximity_context and has_station_proximity_mid
        ),
        "station_proximity_bonus": station_proximity_bonus,
        "is_station_proximity_station_cell": is_station_proximity_station_cell,
        "has_motorway_context": has_motorway_context,
        "motorway_context_bonus": motorway_context_bonus,
        "has_trunk_context": has_trunk_context,
        "trunk_context_bonus": trunk_context_bonus,
        "has_landmark_context": has_landmark_context,
        "landmark_context_bonus": landmark_context_bonus,
        **landmark_context_bonuses,
        "has_castle_proximity_context": has_castle_proximity_context,
        "has_castle_near_proximity_context": (
            has_castle_proximity_context and has_castle_near_proximity
        ),
        "has_castle_mid_proximity_context": (
            has_castle_proximity_context and has_castle_mid_proximity
        ),
        "has_castle_far_proximity_context": (
            has_castle_proximity_context and has_castle_far_proximity
        ),
        "castle_proximity_bonus": castle_proximity_bonus,
        "is_castle_proximity_skipped_castle_cell": (
            is_castle_proximity_skipped_castle_cell
        ),
        "is_likely_unreachable_water_cell": is_likely_unreachable_water_cell,
        "has_waterfront_context": has_waterfront_context,
        "has_park_waterfront_combo_context": has_park_waterfront_combo_context,
        "park_waterfront_combo_bonus": park_waterfront_combo_bonus,
        "context_candidate_count": context_candidate_count,
        "has_high_context_3_context": has_high_context_3_context,
        "has_high_context_4_context": has_high_context_4_context,
        "has_high_context_5_context": has_high_context_5_context,
        "high_context_bonus": high_context_bonus,
        "has_water_penalty": has_water_penalty,
        "has_unreachable_water_penalty": is_likely_unreachable_water_cell,
        "has_forest_penalty": has_forest_penalty,
        "has_empty_cell_penalty": has_empty_cell_penalty,
    }


def calculate_initial_score_from_feature_summary(
    feature_summary,
    grid_size_meters=None,
):
    """Calculate a provisional 0.0-3.0 initial score from feature summary data."""
    breakdown = calculate_initial_score_breakdown_from_feature_summary(
        feature_summary,
        grid_size_meters=grid_size_meters,
    )
    return breakdown["clamped_score"]


def build_auto_score_breakdown_from_feature_summary(
    feature_summary,
    grid_size_meters=None,
):
    """Build a compact JSON-safe score breakdown for GridCell API display.

    The compact shape is stored on GridCell so the detail page can explain the
    automatic score without exposing every internal intermediate value.
    """
    breakdown = calculate_initial_score_breakdown_from_feature_summary(
        feature_summary,
        grid_size_meters=grid_size_meters,
    )

    return {
        **{key: breakdown[key] for key in AUTO_SCORE_BREAKDOWN_SCORE_KEYS},
        "grid_size_multiplier": breakdown["grid_size_multiplier"],
        "bonuses": {
            key: breakdown[key]
            for key in AUTO_SCORE_BREAKDOWN_BONUS_KEYS
        },
        "flags": {
            key: bool(breakdown[key])
            for key in AUTO_SCORE_BREAKDOWN_FLAG_KEYS
        },
        "counts": {
            key: breakdown[key]
            for key in AUTO_SCORE_BREAKDOWN_COUNT_KEYS
        },
    }


def determine_initial_score_for_grid_cell(
    *,
    region_feature_level,
    grid_context=None,
):
    """Return the initial GridCell score as a 0.0-3.0 float value.

    Feature summaries take priority for auto mode; manual mode falls back to the
    selected region_feature_level so both creation paths share one generator.
    """
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
    """Calculate MapArea bounds from center position and grid dimensions.

    Latitude can use a fixed meters-per-degree approximation, but longitude
    narrows toward the poles, so it is corrected with cos(center_lat).
    """
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
    """Validate general-user limits for center-based MapArea creation.

    This keeps accidental huge grids from producing too many GridCells or
    expensive Overpass requests, while still allowing staff-only large checks.
    """
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
    """Build GridCell context dictionaries without saving them.

    Contexts let preview/auto-score code calculate each cell's bounds before
    the database rows exist, while keeping saved GridCells inside MapArea bounds.
    """
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
    """Generate and save GridCell rows for one MapArea.

    A cell either receives an auto-score breakdown from OSM summaries or falls
    back to the manually selected region feature level.
    """
    if feature_summaries_by_position is None:
        feature_summaries_by_position = {}
    elif not isinstance(feature_summaries_by_position, dict):
        raise ValueError("feature_summaries_by_position は辞書で指定してください。")

    if map_area.grid_cells.exists():
        raise ValueError("この MapArea には既に GridCell があります。")

    total_started_at = perf_counter()
    grid_cell_contexts = build_grid_cell_contexts_for_area(
        map_area,
        rows=rows,
        cols=cols,
        lat_step=lat_step,
        lng_step=lng_step,
    )

    grid_cells = []
    score_started_at = perf_counter()
    initial_scores = []
    for grid_context in grid_cell_contexts:
        row_index = grid_context["row_index"]
        col_index = grid_context["col_index"]
        feature_summary = feature_summaries_by_position.get((row_index, col_index))
        if feature_summary is not None:
            grid_context["feature_summary"] = feature_summary
            auto_score_breakdown = build_auto_score_breakdown_from_feature_summary(
                feature_summary,
                grid_size_meters=map_area.grid_size_meters,
            )
            initial_score = auto_score_breakdown["clamped_score"]
        else:
            auto_score_breakdown = None
            initial_score = determine_initial_score_for_grid_cell(
                region_feature_level=map_area.region_feature_level,
                grid_context=grid_context,
            )
        initial_scores.append(initial_score)

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
                auto_score_breakdown=auto_score_breakdown,
                average_user_score=0,
                rating_count=0,
                calculated_score=initial_score,
                score_updated_at=None,
            )
        )

    score_elapsed_sec = perf_counter() - score_started_at
    if feature_summaries_by_position:
        logger.info(
            "[auto_grid_create] step=auto_score area_id=%s cells=%s avg=%.2f "
            "min=%.2f max=%.2f elapsed_sec=%.3f",
            map_area.id,
            len(grid_cells),
            sum(initial_scores) / len(initial_scores) if initial_scores else 0.0,
            min(initial_scores) if initial_scores else 0.0,
            max(initial_scores) if initial_scores else 0.0,
            score_elapsed_sec,
        )

    db_started_at = perf_counter()
    created_grid_cells = GridCell.objects.bulk_create(grid_cells)
    logger.info(
        "[%s] step=gridcell_bulk_create area_id=%s cells=%s elapsed_sec=%.3f",
        (
            "auto_grid_create"
            if feature_summaries_by_position
            else "manual_grid_create"
        ),
        map_area.id,
        len(created_grid_cells),
        perf_counter() - db_started_at,
    )
    logger.info(
        "[%s] step=gridcell_generate area_id=%s cells=%s elapsed_sec=%.3f",
        (
            "auto_grid_create"
            if feature_summaries_by_position
            else "manual_grid_create"
        ),
        map_area.id,
        len(created_grid_cells),
        perf_counter() - total_started_at,
    )

    return created_grid_cells


def truncate_grid_generation_error_message(message, max_length=500):
    """Return a short single-line error message for MapArea status fields."""
    message = " ".join(str(message or "").split())
    if len(message) <= max_length:
        return message
    return message[:max_length]


def _save_grid_generation_status(map_area, status, *, finished_at=None, error_message=""):
    map_area.grid_generation_status = status
    map_area.grid_generation_finished_at = finished_at
    map_area.grid_generation_error_message = truncate_grid_generation_error_message(
        error_message
    )
    map_area.save(
        update_fields=[
            "grid_generation_status",
            "grid_generation_finished_at",
            "grid_generation_error_message",
            "updated_at",
        ]
    )


def run_grid_generation_for_area(
    map_area,
    *,
    rows=None,
    cols=None,
    lat_step=None,
    lng_step=None,
    user_id=None,
    auto_success_callback=None,
    auto_failure_callback=None,
):
    """Run the current synchronous GridCell generation flow for one MapArea.

    This is the high-level entry point that can later be called from a
    management command or job worker. It still runs synchronously, but records
    the final generation state on MapArea.
    """
    now = timezone.now()
    map_area.grid_generation_status = MapArea.GridGenerationStatus.RUNNING
    map_area.grid_generation_started_at = now
    map_area.grid_generation_finished_at = None
    map_area.grid_generation_error_message = ""
    map_area.grid_generation_attempt_count = (
        (map_area.grid_generation_attempt_count or 0) + 1
    )
    map_area.save(
        update_fields=[
            "grid_generation_status",
            "grid_generation_started_at",
            "grid_generation_finished_at",
            "grid_generation_error_message",
            "grid_generation_attempt_count",
            "updated_at",
        ]
    )

    grid_generation_options = {
        "rows": rows,
        "cols": cols,
        "lat_step": lat_step,
        "lng_step": lng_step,
    }
    feature_summaries_by_position = None
    fallback_error = None

    if map_area.initial_score_mode == MapArea.InitialScoreMode.AUTO:
        try:
            feature_summaries_by_position = (
                build_feature_summaries_for_map_area_from_overpass(
                    map_area,
                    **grid_generation_options,
                )
            )
            if auto_success_callback is not None:
                auto_success_callback(
                    map_area,
                    user_id,
                    feature_summaries_by_position,
                )
        except ValueError as error:
            fallback_error = error
            if auto_failure_callback is not None:
                auto_failure_callback(map_area, user_id, error)
            else:
                logger.warning(
                    "Overpass auto initial score failed; using fallback: "
                    "area_id=%s user_id=%s error=%s",
                    map_area.id,
                    user_id,
                    error,
                )
            feature_summaries_by_position = None

    if feature_summaries_by_position is not None:
        grid_generation_options["feature_summaries_by_position"] = (
            feature_summaries_by_position
        )

    try:
        created_grid_cells = generate_grid_cells_for_area(
            map_area,
            **grid_generation_options,
        )
    except ValueError as error:
        _save_grid_generation_status(
            map_area,
            MapArea.GridGenerationStatus.FAILED,
            finished_at=timezone.now(),
            error_message=error,
        )
        raise

    if fallback_error is not None:
        _save_grid_generation_status(
            map_area,
            MapArea.GridGenerationStatus.FALLBACK_COMPLETED,
            finished_at=timezone.now(),
            error_message=fallback_error,
        )
    else:
        _save_grid_generation_status(
            map_area,
            MapArea.GridGenerationStatus.COMPLETED,
            finished_at=timezone.now(),
        )

    return created_grid_cells


def update_grid_cell_score(grid_cell):
    """Recalculate and save score fields for one GridCell.

    initial_score is treated as the first vote. average_user_score and
    rating_count still describe only user ratings, while calculated_score blends
    the initial score with every user score so its influence fades naturally.
    """
    rating_summary = grid_cell.ratings.aggregate(
        average_score=Avg("score"),
        rating_count=Count("id"),
        score_sum=Sum("score"),
    )
    rating_count = rating_summary["rating_count"]

    if rating_count == 0:
        grid_cell.average_user_score = 0
        grid_cell.rating_count = 0
        grid_cell.calculated_score = grid_cell.initial_score
        grid_cell.score_updated_at = None
    else:
        average_user_score = rating_summary["average_score"]
        user_score_sum = rating_summary["score_sum"] or 0
        grid_cell.average_user_score = average_user_score
        grid_cell.rating_count = rating_count
        grid_cell.calculated_score = (
            grid_cell.initial_score + user_score_sum
        ) / (1 + rating_count)
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
