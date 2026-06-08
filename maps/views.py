import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.staticfiles import finders
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import GridCell, GridRating, MapArea, MapAreaShare
from .serializers import (
    BulkGridRatingSerializer,
    GridCellScoreSerializer,
    MapAreaListSerializer,
    MapAreaSerializer,
    MapAreaShareCreateSerializer,
    MapAreaShareSerializer,
    GridRatingCreateSerializer,
    GridRatingResponseSerializer,
)
from .services import (
    build_feature_summaries_for_map_area_from_overpass,
    calculate_initial_score_breakdown_from_feature_summary,
    calculate_initial_score_from_feature_summary,
    generate_grid_cells_for_area,
    MIN_FOREST_COVERAGE_RATIO_FOR_SCORE,
    update_grid_cell_score,
    validate_center_grid_limits,
)


API_AUTHENTICATION_CLASSES = [
    TokenAuthentication,
    BasicAuthentication,
    SessionAuthentication,
]

logger = logging.getLogger(__name__)


def get_viewable_map_area_or_404(user, area_id):
    queryset = MapArea.objects.filter(Q(created_by=user) | Q(shares__user=user))
    return get_object_or_404(queryset.distinct(), id=area_id)


def get_owned_map_area_or_404(user, area_id):
    return get_object_or_404(MapArea.objects.filter(created_by=user), id=area_id)


def rateable_grid_cells_for_user(user):
    return GridCell.objects.filter(
        Q(area__created_by=user) | Q(area__shares__user=user)
    ).distinct()


def log_overpass_feature_summary(area, user_id, feature_summaries_by_position):
    summaries = list(feature_summaries_by_position.values())
    scores = [
        calculate_initial_score_from_feature_summary(summary)
        for summary in summaries
    ]
    score_min = min(scores) if scores else 0.0
    score_max = max(scores) if scores else 0.0
    score_avg = sum(scores) / len(scores) if scores else 0.0

    logger.info(
        "Overpass auto feature summary: "
        "area_id=%s user_id=%s summary_count=%s "
        "building_cells=%s road_cells=%s park_cells=%s river_cells=%s "
        "coastal_cells=%s water_cells=%s forest_cells=%s "
        "score_min=%.2f score_max=%.2f score_avg=%.2f",
        area.id,
        user_id,
        len(feature_summaries_by_position),
        sum(summary.get("building_count", 0) > 0 for summary in summaries),
        sum(summary.get("road_count", 0) > 0 for summary in summaries),
        sum(summary.get("has_park", False) is True for summary in summaries),
        sum(summary.get("has_river", False) is True for summary in summaries),
        sum(summary.get("is_coastal", False) is True for summary in summaries),
        sum(summary.get("water_coverage_ratio", 0) > 0 for summary in summaries),
        sum(summary.get("forest_coverage_ratio", 0) > 0 for summary in summaries),
        score_min,
        score_max,
        score_avg,
    )


def log_overpass_score_breakdown_summary(
    area,
    user_id,
    feature_summaries_by_position,
):
    summaries = list(feature_summaries_by_position.values())
    breakdowns = [
        calculate_initial_score_breakdown_from_feature_summary(summary)
        for summary in summaries
    ]

    def component_values(key):
        return [breakdown[key] for breakdown in breakdowns]

    def component_average(key):
        values = component_values(key)
        return sum(values) / len(values) if values else 0.0

    def component_max(key):
        values = component_values(key)
        return max(values) if values else 0.0

    logger.info(
        "Overpass auto score breakdown summary: "
        "area_id=%s user_id=%s summary_count=%s "
        "base_score_avg=%.2f base_score_max=%.2f "
        "diversity_bonus_avg=%.2f diversity_bonus_max=%.2f "
        "context_bonus_avg=%.2f context_bonus_max=%.2f "
        "penalty_avg=%.2f penalty_max=%.2f "
        "raw_score_avg=%.2f raw_score_max=%.2f "
        "clamped_score_avg=%.2f clamped_score_max=%.2f "
        "max_score_cells=%s "
        "building_base_cells=%s road_base_cells=%s road_scored_cells=%s "
        "park_context_cells=%s river_context_cells=%s "
        "forest_context_cells=%s coastal_context_cells=%s "
        "water_penalty_cells=%s unreachable_water_penalty_cells=%s "
        "waterfront_context_cells=%s forest_penalty_cells=%s "
        "empty_cell_penalty_cells=%s "
        "surface_railway_context_cells=%s "
        "surface_railway_context_bonus_avg=%.2f "
        "surface_railway_context_bonus_max=%.2f "
        "surface_station_context_cells=%s "
        "surface_station_context_bonus_avg=%.2f "
        "surface_station_context_bonus_max=%.2f "
        "subway_station_context_cells=%s "
        "subway_station_context_bonus_avg=%.2f "
        "subway_station_context_bonus_max=%.2f "
        "public_transport_station_context_cells=%s "
        "public_transport_station_context_bonus_avg=%.2f "
        "public_transport_station_context_bonus_max=%.2f "
        "station_count_avg=%.2f "
        "station_count_max=%.2f "
        "station_density_cluster_count_avg=%.2f "
        "station_density_cluster_count_max=%.2f "
        "dense_station_density_cluster_count_max=%.2f "
        "dense_station_cluster_context_cells=%s "
        "major_station_cluster_context_cells=%s "
        "station_density_bonus_avg=%.2f "
        "station_density_bonus_max=%.2f "
        "landmark_context_cells=%s "
        "landmark_context_bonus_avg=%.2f "
        "landmark_context_bonus_max=%.2f "
        "castle_proximity_context_cells=%s "
        "castle_near_context_cells=%s "
        "castle_mid_context_cells=%s "
        "castle_far_context_cells=%s "
        "castle_proximity_bonus_avg=%.2f "
        "castle_proximity_bonus_max=%.2f "
        "castle_proximity_skipped_castle_cells=%s "
        "station_proximity_context_cells=%s "
        "station_proximity_near_context_cells=%s "
        "station_proximity_mid_context_cells=%s "
        "station_proximity_bonus_avg=%.2f "
        "station_proximity_bonus_max=%.2f "
        "park_waterfront_combo_context_cells=%s "
        "park_waterfront_combo_bonus_avg=%.2f "
        "park_waterfront_combo_bonus_max=%.2f "
        "high_context_3_context_cells=%s "
        "high_context_4_context_cells=%s "
        "high_context_5_context_cells=%s "
        "high_context_bonus_avg=%.2f "
        "high_context_bonus_max=%.2f "
        "motorway_context_cells=%s "
        "motorway_context_bonus_avg=%.2f "
        "motorway_context_bonus_max=%.2f "
        "trunk_context_cells=%s "
        "trunk_context_bonus_avg=%.2f "
        "trunk_context_bonus_max=%.2f",
        area.id,
        user_id,
        len(summaries),
        component_average("base_score"),
        component_max("base_score"),
        component_average("diversity_bonus"),
        component_max("diversity_bonus"),
        component_average("context_bonus"),
        component_max("context_bonus"),
        component_average("penalty"),
        component_max("penalty"),
        component_average("raw_score"),
        component_max("raw_score"),
        component_average("clamped_score"),
        component_max("clamped_score"),
        sum(breakdown["clamped_score"] >= 3.0 for breakdown in breakdowns),
        sum(breakdown["building_base_bonus"] > 0 for breakdown in breakdowns),
        sum(breakdown["road_base_bonus"] > 0 for breakdown in breakdowns),
        sum(breakdown["road_base_bonus"] > 0 for breakdown in breakdowns),
        sum(breakdown["has_park_context"] for breakdown in breakdowns),
        sum(breakdown["has_river_context"] for breakdown in breakdowns),
        sum(breakdown["has_forest_context"] for breakdown in breakdowns),
        sum(breakdown["has_coastal_context"] for breakdown in breakdowns),
        sum(breakdown["has_water_penalty"] for breakdown in breakdowns),
        sum(
            breakdown["is_likely_unreachable_water_cell"]
            for breakdown in breakdowns
        ),
        sum(breakdown["has_waterfront_context"] for breakdown in breakdowns),
        sum(breakdown["has_forest_penalty"] for breakdown in breakdowns),
        sum(breakdown["has_empty_cell_penalty"] for breakdown in breakdowns),
        sum(breakdown["has_surface_railway_context"] for breakdown in breakdowns),
        component_average("surface_railway_context_bonus"),
        component_max("surface_railway_context_bonus"),
        sum(breakdown["has_surface_station_context"] for breakdown in breakdowns),
        component_average("surface_station_context_bonus"),
        component_max("surface_station_context_bonus"),
        sum(breakdown["has_subway_station_context"] for breakdown in breakdowns),
        component_average("subway_station_context_bonus"),
        component_max("subway_station_context_bonus"),
        sum(
            breakdown["has_public_transport_station_context"]
            for breakdown in breakdowns
        ),
        component_average("public_transport_station_context_bonus"),
        component_max("public_transport_station_context_bonus"),
        component_average("scored_station_count"),
        component_max("scored_station_count"),
        component_average("station_cluster_count"),
        component_max("station_cluster_count"),
        component_max("dense_station_cluster_count"),
        sum(
            breakdown["has_dense_station_cluster_context"]
            for breakdown in breakdowns
        ),
        sum(
            breakdown["has_major_station_cluster_context"]
            for breakdown in breakdowns
        ),
        component_average("station_density_bonus"),
        component_max("station_density_bonus"),
        sum(breakdown["has_landmark_context"] for breakdown in breakdowns),
        component_average("landmark_context_bonus"),
        component_max("landmark_context_bonus"),
        sum(breakdown["has_castle_proximity_context"] for breakdown in breakdowns),
        sum(
            breakdown["has_castle_near_proximity_context"]
            for breakdown in breakdowns
        ),
        sum(
            breakdown["has_castle_mid_proximity_context"]
            for breakdown in breakdowns
        ),
        sum(
            breakdown["has_castle_far_proximity_context"]
            for breakdown in breakdowns
        ),
        component_average("castle_proximity_bonus"),
        component_max("castle_proximity_bonus"),
        sum(
            breakdown["is_castle_proximity_skipped_castle_cell"]
            for breakdown in breakdowns
        ),
        sum(breakdown["has_station_proximity_context"] for breakdown in breakdowns),
        sum(
            breakdown["has_station_proximity_near_context"]
            for breakdown in breakdowns
        ),
        sum(
            breakdown["has_station_proximity_mid_context"]
            for breakdown in breakdowns
        ),
        component_average("station_proximity_bonus"),
        component_max("station_proximity_bonus"),
        sum(
            breakdown["has_park_waterfront_combo_context"]
            for breakdown in breakdowns
        ),
        component_average("park_waterfront_combo_bonus"),
        component_max("park_waterfront_combo_bonus"),
        sum(breakdown["has_high_context_3_context"] for breakdown in breakdowns),
        sum(breakdown["has_high_context_4_context"] for breakdown in breakdowns),
        sum(breakdown["has_high_context_5_context"] for breakdown in breakdowns),
        component_average("high_context_bonus"),
        component_max("high_context_bonus"),
        sum(breakdown["has_motorway_context"] for breakdown in breakdowns),
        component_average("motorway_context_bonus"),
        component_max("motorway_context_bonus"),
        sum(breakdown["has_trunk_context"] for breakdown in breakdowns),
        component_average("trunk_context_bonus"),
        component_max("trunk_context_bonus"),
    )


def log_overpass_context_candidate_summary(
    area,
    user_id,
    feature_summaries_by_position,
    station_proximity_summary=None,
):
    if station_proximity_summary is None:
        station_proximity_summary = {}

    breakdowns = [
        calculate_initial_score_breakdown_from_feature_summary(summary)
        for summary in feature_summaries_by_position.values()
    ]

    context_counts = []
    park_waterfront_combo_cells = 0
    for breakdown in breakdowns:
        if breakdown["has_park"] and breakdown["has_waterfront_context"]:
            park_waterfront_combo_cells += 1

        station_context = (
            breakdown["has_surface_station_context"]
            or breakdown["has_subway_station_context"]
            or breakdown["has_public_transport_station_context"]
        )
        context_count = sum(
            (
                breakdown["has_park_context"],
                breakdown["has_waterfront_context"],
                breakdown["has_river_context"],
                breakdown["has_surface_railway_context"],
                station_context,
                breakdown["station_density_bonus"] > 0,
                breakdown["has_motorway_context"],
                breakdown["has_trunk_context"],
                breakdown["has_landmark_context"],
                breakdown["has_castle_proximity_context"],
            )
        )
        context_counts.append(context_count)

    context_candidate_count_avg = (
        sum(context_counts) / len(context_counts) if context_counts else 0.0
    )
    context_candidate_count_max = max(context_counts) if context_counts else 0

    logger.info(
        "Overpass auto context candidate summary: "
        "area_id=%s user_id=%s summary_count=%s "
        "park_waterfront_combo_cells=%s "
        "high_context_3_cells=%s "
        "high_context_5_cells=%s "
        "context_candidate_count_avg=%.2f "
        "context_candidate_count_max=%s "
        "station_proximity_features=%s "
        "station_proximity_near_cells=%s "
        "station_proximity_mid_cells=%s "
        "station_proximity_cells=%s "
        "station_proximity_station_cells=%s "
        "station_proximity_non_station_cells=%s "
        "station_proximity_min_distance_m=%.2f "
        "station_proximity_avg_distance_m=%.2f "
        "station_proximity_max_distance_m=%.2f",
        area.id,
        user_id,
        len(breakdowns),
        park_waterfront_combo_cells,
        sum(context_count >= 3 for context_count in context_counts),
        sum(context_count >= 5 for context_count in context_counts),
        context_candidate_count_avg,
        context_candidate_count_max,
        station_proximity_summary.get("station_proximity_features", 0),
        station_proximity_summary.get("station_proximity_near_cells", 0),
        station_proximity_summary.get("station_proximity_mid_cells", 0),
        station_proximity_summary.get("station_proximity_cells", 0),
        station_proximity_summary.get("station_proximity_station_cells", 0),
        station_proximity_summary.get("station_proximity_non_station_cells", 0),
        station_proximity_summary.get("station_proximity_min_distance_m", 0.0),
        station_proximity_summary.get("station_proximity_avg_distance_m", 0.0),
        station_proximity_summary.get("station_proximity_max_distance_m", 0.0),
    )


def log_overpass_river_summary(
    area,
    user_id,
    feature_summaries_by_position,
    river_summary=None,
):
    if river_summary is None:
        summaries = list(feature_summaries_by_position.values())
        river_summary = {
            "river_cells": sum(
                summary.get("has_river", False) is True for summary in summaries
            ),
            "river_avg_overlap": 0.0,
            "river_max_overlap": 0.0,
            "river_large_bounds_cells": 0,
            "river_small_overlap_cells": 0,
        }

    logger.info(
        "Overpass auto river summary: "
        "area_id=%s user_id=%s river_cells=%s "
        "river_avg_overlap=%.4f river_max_overlap=%.4f "
        "river_large_bounds_cells=%s river_small_overlap_cells=%s",
        area.id,
        user_id,
        river_summary.get("river_cells", 0),
        river_summary.get("river_avg_overlap", 0.0),
        river_summary.get("river_max_overlap", 0.0),
        river_summary.get("river_large_bounds_cells", 0),
        river_summary.get("river_small_overlap_cells", 0),
    )


def log_overpass_scored_river_summary(area, user_id, feature_summaries_by_position):
    summaries = list(feature_summaries_by_position.values())
    river_coverages = [
        float(summary.get("river_coverage_ratio", 0.0))
        for summary in summaries
        if summary.get("river_coverage_ratio", 0.0) > 0
    ]
    river_coverage_avg = (
        sum(river_coverages) / len(river_coverages)
        if river_coverages
        else 0.0
    )
    river_coverage_max = max(river_coverages) if river_coverages else 0.0

    logger.info(
        "Overpass auto scored river summary: "
        "area_id=%s user_id=%s scored_river_cells=%s "
        "river_coverage_cells=%s river_coverage_avg=%.4f "
        "river_coverage_max=%.4f",
        area.id,
        user_id,
        sum(summary.get("has_river", False) is True for summary in summaries),
        len(river_coverages),
        river_coverage_avg,
        river_coverage_max,
    )


def _positive_coverage_values(summaries, key):
    return [
        float(summary.get(key, 0.0))
        for summary in summaries
        if summary.get(key, 0.0) > 0
    ]


def _coverage_average(coverage_values):
    if not coverage_values:
        return 0.0
    return sum(coverage_values) / len(coverage_values)


def log_overpass_scored_natural_coverage_summary(
    area,
    user_id,
    feature_summaries_by_position,
):
    summaries = list(feature_summaries_by_position.values())
    park_coverages = _positive_coverage_values(summaries, "park_coverage_ratio")
    water_coverages = _positive_coverage_values(summaries, "water_coverage_ratio")
    forest_coverages = _positive_coverage_values(summaries, "forest_coverage_ratio")

    logger.info(
        "Overpass auto scored natural coverage summary: "
        "area_id=%s user_id=%s "
        "park_cells=%s park_coverage_cells=%s "
        "park_coverage_avg=%.4f park_coverage_max=%.4f "
        "water_coverage_cells=%s water_coverage_avg=%.4f "
        "water_coverage_max=%.4f "
        "forest_coverage_cells=%s scored_forest_cells=%s "
        "forest_coverage_avg=%.4f "
        "forest_coverage_max=%.4f",
        area.id,
        user_id,
        sum(summary.get("has_park", False) is True for summary in summaries),
        len(park_coverages),
        _coverage_average(park_coverages),
        max(park_coverages) if park_coverages else 0.0,
        len(water_coverages),
        _coverage_average(water_coverages),
        max(water_coverages) if water_coverages else 0.0,
        len(forest_coverages),
        sum(
            summary.get("forest_coverage_ratio", 0.0)
            >= MIN_FOREST_COVERAGE_RATIO_FOR_SCORE
            for summary in summaries
        ),
        _coverage_average(forest_coverages),
        max(forest_coverages) if forest_coverages else 0.0,
    )


def log_overpass_waterway_summary(
    area,
    user_id,
    waterway_summary=None,
):
    if waterway_summary is None:
        waterway_summary = {}

    logger.info(
        "Overpass auto waterway summary: "
        "area_id=%s user_id=%s "
        "waterway_river_features=%s waterway_stream_features=%s "
        "waterway_canal_features=%s waterway_unknown_features=%s "
        "waterway_river_cells=%s waterway_stream_cells=%s "
        "waterway_canal_cells=%s waterway_unknown_cells=%s",
        area.id,
        user_id,
        waterway_summary.get("waterway_river_features", 0),
        waterway_summary.get("waterway_stream_features", 0),
        waterway_summary.get("waterway_canal_features", 0),
        waterway_summary.get("waterway_unknown_features", 0),
        waterway_summary.get("waterway_river_cells", 0),
        waterway_summary.get("waterway_stream_cells", 0),
        waterway_summary.get("waterway_canal_cells", 0),
        waterway_summary.get("waterway_unknown_cells", 0),
    )


def log_overpass_railway_summary(
    area,
    user_id,
    railway_summary=None,
):
    if railway_summary is None:
        railway_summary = {}

    logger.info(
        "Overpass auto railway summary: "
        "area_id=%s user_id=%s "
        "railway_features=%s surface_railway_features=%s "
        "underground_railway_features=%s unknown_railway_features=%s "
        "railway_cells=%s surface_railway_cells=%s "
        "underground_railway_cells=%s unknown_railway_cells=%s",
        area.id,
        user_id,
        railway_summary.get("railway_features", 0),
        railway_summary.get("surface_railway_features", 0),
        railway_summary.get("underground_railway_features", 0),
        railway_summary.get("unknown_railway_features", 0),
        railway_summary.get("railway_cells", 0),
        railway_summary.get("surface_railway_cells", 0),
        railway_summary.get("underground_railway_cells", 0),
        railway_summary.get("unknown_railway_cells", 0),
    )


def log_overpass_station_summary(
    area,
    user_id,
    station_summary=None,
):
    if station_summary is None:
        station_summary = {}

    logger.info(
        "Overpass auto station summary: "
        "area_id=%s user_id=%s "
        "station_features=%s railway_station_features=%s "
        "railway_halt_features=%s subway_station_features=%s "
        "bus_station_features=%s public_transport_station_features=%s "
        "unknown_station_features=%s "
        "station_cells=%s railway_station_cells=%s "
        "railway_halt_cells=%s subway_station_cells=%s "
        "bus_station_cells=%s public_transport_station_cells=%s "
        "unknown_station_cells=%s "
        "station_cluster_cells=%s "
        "dense_station_cluster_cells=%s "
        "major_station_cluster_cells=%s "
        "station_cluster_count_avg=%.2f "
        "station_cluster_count_max=%s "
        "dense_station_cluster_count_max=%s "
        "major_station_cluster_count_max=%s",
        area.id,
        user_id,
        station_summary.get("station_features", 0),
        station_summary.get("railway_station_features", 0),
        station_summary.get("railway_halt_features", 0),
        station_summary.get("subway_station_features", 0),
        station_summary.get("bus_station_features", 0),
        station_summary.get("public_transport_station_features", 0),
        station_summary.get("unknown_station_features", 0),
        station_summary.get("station_cells", 0),
        station_summary.get("railway_station_cells", 0),
        station_summary.get("railway_halt_cells", 0),
        station_summary.get("subway_station_cells", 0),
        station_summary.get("bus_station_cells", 0),
        station_summary.get("public_transport_station_cells", 0),
        station_summary.get("unknown_station_cells", 0),
        station_summary.get("station_cluster_cells", 0),
        station_summary.get("dense_station_cluster_cells", 0),
        station_summary.get("major_station_cluster_cells", 0),
        station_summary.get("station_cluster_count_avg", 0.0),
        station_summary.get("station_cluster_count_max", 0),
        station_summary.get("dense_station_cluster_count_max", 0),
        station_summary.get("major_station_cluster_count_max", 0),
    )


def log_overpass_landmark_summary(
    area,
    user_id,
    landmark_summary=None,
):
    if landmark_summary is None:
        landmark_summary = {}

    logger.info(
        "Overpass auto landmark summary: "
        "area_id=%s user_id=%s "
        "landmark_features=%s landmark_cells=%s "
        "tourism_attraction_features=%s tourism_attraction_cells=%s "
        "tourism_museum_features=%s tourism_museum_cells=%s "
        "tourism_gallery_features=%s tourism_gallery_cells=%s "
        "tourism_viewpoint_features=%s tourism_viewpoint_cells=%s "
        "historic_castle_features=%s historic_castle_cells=%s "
        "historic_monument_features=%s historic_monument_cells=%s "
        "historic_memorial_features=%s historic_memorial_cells=%s "
        "historic_ruins_features=%s historic_ruins_cells=%s "
        "historic_archaeological_site_features=%s "
        "historic_archaeological_site_cells=%s "
        "unknown_landmark_features=%s unknown_landmark_cells=%s",
        area.id,
        user_id,
        landmark_summary.get("landmark_features", 0),
        landmark_summary.get("landmark_cells", 0),
        landmark_summary.get("tourism_attraction_features", 0),
        landmark_summary.get("tourism_attraction_cells", 0),
        landmark_summary.get("tourism_museum_features", 0),
        landmark_summary.get("tourism_museum_cells", 0),
        landmark_summary.get("tourism_gallery_features", 0),
        landmark_summary.get("tourism_gallery_cells", 0),
        landmark_summary.get("tourism_viewpoint_features", 0),
        landmark_summary.get("tourism_viewpoint_cells", 0),
        landmark_summary.get("historic_castle_features", 0),
        landmark_summary.get("historic_castle_cells", 0),
        landmark_summary.get("historic_monument_features", 0),
        landmark_summary.get("historic_monument_cells", 0),
        landmark_summary.get("historic_memorial_features", 0),
        landmark_summary.get("historic_memorial_cells", 0),
        landmark_summary.get("historic_ruins_features", 0),
        landmark_summary.get("historic_ruins_cells", 0),
        landmark_summary.get("historic_archaeological_site_features", 0),
        landmark_summary.get("historic_archaeological_site_cells", 0),
        landmark_summary.get("unknown_landmark_features", 0),
        landmark_summary.get("unknown_landmark_cells", 0),
    )


def log_overpass_castle_proximity_summary(
    area,
    user_id,
    castle_proximity_summary=None,
):
    if castle_proximity_summary is None:
        castle_proximity_summary = {}

    logger.info(
        "Overpass auto castle proximity summary: "
        "area_id=%s user_id=%s "
        "castle_features=%s "
        "castle_near_cells=%s castle_mid_cells=%s castle_far_cells=%s "
        "castle_proximity_cells=%s "
        "castle_min_distance_m=%.2f "
        "castle_avg_distance_m=%.2f "
        "castle_max_distance_m=%.2f",
        area.id,
        user_id,
        castle_proximity_summary.get("castle_features", 0),
        castle_proximity_summary.get("castle_near_cells", 0),
        castle_proximity_summary.get("castle_mid_cells", 0),
        castle_proximity_summary.get("castle_far_cells", 0),
        castle_proximity_summary.get("castle_proximity_cells", 0),
        castle_proximity_summary.get("castle_min_distance_m", 0.0),
        castle_proximity_summary.get("castle_avg_distance_m", 0.0),
        castle_proximity_summary.get("castle_max_distance_m", 0.0),
    )


def log_overpass_expressway_summary(
    area,
    user_id,
    expressway_summary=None,
):
    if expressway_summary is None:
        expressway_summary = {}

    logger.info(
        "Overpass auto expressway summary: "
        "area_id=%s user_id=%s "
        "expressway_features=%s motorway_features=%s "
        "motorway_link_features=%s trunk_features=%s "
        "trunk_link_features=%s unknown_expressway_features=%s "
        "expressway_cells=%s motorway_cells=%s "
        "motorway_link_cells=%s trunk_cells=%s "
        "trunk_link_cells=%s unknown_expressway_cells=%s",
        area.id,
        user_id,
        expressway_summary.get("expressway_features", 0),
        expressway_summary.get("motorway_features", 0),
        expressway_summary.get("motorway_link_features", 0),
        expressway_summary.get("trunk_features", 0),
        expressway_summary.get("trunk_link_features", 0),
        expressway_summary.get("unknown_expressway_features", 0),
        expressway_summary.get("expressway_cells", 0),
        expressway_summary.get("motorway_cells", 0),
        expressway_summary.get("motorway_link_cells", 0),
        expressway_summary.get("trunk_cells", 0),
        expressway_summary.get("trunk_link_cells", 0),
        expressway_summary.get("unknown_expressway_cells", 0),
    )


def log_overpass_expressway_bounds_summary(
    area,
    user_id,
    expressway_bounds_summary=None,
):
    if expressway_bounds_summary is None:
        expressway_bounds_summary = {}

    logger.info(
        "Overpass auto expressway bounds summary: "
        "area_id=%s user_id=%s "
        "expressway_features=%s expressway_cells=%s "
        "expressway_avg_overlap=%.4f expressway_max_overlap=%.4f "
        "expressway_large_bounds_features=%s "
        "expressway_large_bounds_cells=%s "
        "motorway_features=%s motorway_cells=%s "
        "motorway_avg_overlap=%.4f motorway_max_overlap=%.4f "
        "motorway_link_features=%s motorway_link_cells=%s "
        "motorway_link_avg_overlap=%.4f motorway_link_max_overlap=%.4f "
        "trunk_features=%s trunk_cells=%s "
        "trunk_avg_overlap=%.4f trunk_max_overlap=%.4f "
        "trunk_link_features=%s trunk_link_cells=%s "
        "trunk_link_avg_overlap=%.4f trunk_link_max_overlap=%.4f "
        "unknown_expressway_features=%s unknown_expressway_cells=%s "
        "unknown_expressway_avg_overlap=%.4f "
        "unknown_expressway_max_overlap=%.4f",
        area.id,
        user_id,
        expressway_bounds_summary.get("expressway_features", 0),
        expressway_bounds_summary.get("expressway_cells", 0),
        expressway_bounds_summary.get("expressway_avg_overlap", 0.0),
        expressway_bounds_summary.get("expressway_max_overlap", 0.0),
        expressway_bounds_summary.get("expressway_large_bounds_features", 0),
        expressway_bounds_summary.get("expressway_large_bounds_cells", 0),
        expressway_bounds_summary.get("motorway_features", 0),
        expressway_bounds_summary.get("motorway_cells", 0),
        expressway_bounds_summary.get("motorway_avg_overlap", 0.0),
        expressway_bounds_summary.get("motorway_max_overlap", 0.0),
        expressway_bounds_summary.get("motorway_link_features", 0),
        expressway_bounds_summary.get("motorway_link_cells", 0),
        expressway_bounds_summary.get("motorway_link_avg_overlap", 0.0),
        expressway_bounds_summary.get("motorway_link_max_overlap", 0.0),
        expressway_bounds_summary.get("trunk_features", 0),
        expressway_bounds_summary.get("trunk_cells", 0),
        expressway_bounds_summary.get("trunk_avg_overlap", 0.0),
        expressway_bounds_summary.get("trunk_max_overlap", 0.0),
        expressway_bounds_summary.get("trunk_link_features", 0),
        expressway_bounds_summary.get("trunk_link_cells", 0),
        expressway_bounds_summary.get("trunk_link_avg_overlap", 0.0),
        expressway_bounds_summary.get("trunk_link_max_overlap", 0.0),
        expressway_bounds_summary.get("unknown_expressway_features", 0),
        expressway_bounds_summary.get("unknown_expressway_cells", 0),
        expressway_bounds_summary.get("unknown_expressway_avg_overlap", 0.0),
        expressway_bounds_summary.get("unknown_expressway_max_overlap", 0.0),
    )


def log_overpass_effective_expressway_summary(
    area,
    user_id,
    effective_expressway_summary=None,
):
    if effective_expressway_summary is None:
        effective_expressway_summary = {}

    logger.info(
        "Overpass auto effective expressway summary: "
        "area_id=%s user_id=%s "
        "effective_expressway_features=%s "
        "effective_expressway_cells=%s "
        "effective_expressway_avg_overlap=%.4f "
        "effective_expressway_max_overlap=%.4f "
        "effective_motorway_features=%s effective_motorway_cells=%s "
        "effective_motorway_avg_overlap=%.4f "
        "effective_motorway_max_overlap=%.4f "
        "effective_motorway_link_features=%s effective_motorway_link_cells=%s "
        "effective_motorway_link_avg_overlap=%.4f "
        "effective_motorway_link_max_overlap=%.4f "
        "effective_trunk_features=%s effective_trunk_cells=%s "
        "effective_trunk_avg_overlap=%.4f "
        "effective_trunk_max_overlap=%.4f "
        "effective_trunk_link_features=%s effective_trunk_link_cells=%s "
        "effective_trunk_link_avg_overlap=%.4f "
        "effective_trunk_link_max_overlap=%.4f "
        "effective_unknown_expressway_features=%s "
        "effective_unknown_expressway_cells=%s "
        "effective_unknown_expressway_avg_overlap=%.4f "
        "effective_unknown_expressway_max_overlap=%.4f "
        "filtered_expressway_large_bounds_features=%s "
        "filtered_expressway_large_bounds_cells=%s",
        area.id,
        user_id,
        effective_expressway_summary.get("effective_expressway_features", 0),
        effective_expressway_summary.get("effective_expressway_cells", 0),
        effective_expressway_summary.get("effective_expressway_avg_overlap", 0.0),
        effective_expressway_summary.get("effective_expressway_max_overlap", 0.0),
        effective_expressway_summary.get("effective_motorway_features", 0),
        effective_expressway_summary.get("effective_motorway_cells", 0),
        effective_expressway_summary.get("effective_motorway_avg_overlap", 0.0),
        effective_expressway_summary.get("effective_motorway_max_overlap", 0.0),
        effective_expressway_summary.get("effective_motorway_link_features", 0),
        effective_expressway_summary.get("effective_motorway_link_cells", 0),
        effective_expressway_summary.get(
            "effective_motorway_link_avg_overlap",
            0.0,
        ),
        effective_expressway_summary.get(
            "effective_motorway_link_max_overlap",
            0.0,
        ),
        effective_expressway_summary.get("effective_trunk_features", 0),
        effective_expressway_summary.get("effective_trunk_cells", 0),
        effective_expressway_summary.get("effective_trunk_avg_overlap", 0.0),
        effective_expressway_summary.get("effective_trunk_max_overlap", 0.0),
        effective_expressway_summary.get("effective_trunk_link_features", 0),
        effective_expressway_summary.get("effective_trunk_link_cells", 0),
        effective_expressway_summary.get("effective_trunk_link_avg_overlap", 0.0),
        effective_expressway_summary.get("effective_trunk_link_max_overlap", 0.0),
        effective_expressway_summary.get("effective_unknown_expressway_features", 0),
        effective_expressway_summary.get("effective_unknown_expressway_cells", 0),
        effective_expressway_summary.get(
            "effective_unknown_expressway_avg_overlap",
            0.0,
        ),
        effective_expressway_summary.get(
            "effective_unknown_expressway_max_overlap",
            0.0,
        ),
        effective_expressway_summary.get(
            "filtered_expressway_large_bounds_features",
            0,
        ),
        effective_expressway_summary.get(
            "filtered_expressway_large_bounds_cells",
            0,
        ),
    )


def log_overpass_waterway_river_bounds_summary(
    area,
    user_id,
    waterway_river_bounds_summary=None,
):
    if waterway_river_bounds_summary is None:
        waterway_river_bounds_summary = {}

    logger.info(
        "Overpass auto waterway river bounds summary: "
        "area_id=%s user_id=%s "
        "waterway_river_bounds_features=%s "
        "waterway_river_bounds_intersecting_map_features=%s "
        "waterway_river_bounds_covering_map_features=%s "
        "waterway_river_bounds_large_area_features=%s "
        "waterway_river_bounds_filtered_features=%s "
        "waterway_river_bounds_filtered_cells=%s "
        "waterway_river_bounds_max_area_ratio_to_map=%.4f "
        "waterway_river_bounds_max_height_ratio_to_map=%.4f "
        "waterway_river_bounds_max_width_ratio_to_map=%.4f",
        area.id,
        user_id,
        waterway_river_bounds_summary.get("waterway_river_bounds_features", 0),
        waterway_river_bounds_summary.get(
            "waterway_river_bounds_intersecting_map_features",
            0,
        ),
        waterway_river_bounds_summary.get(
            "waterway_river_bounds_covering_map_features",
            0,
        ),
        waterway_river_bounds_summary.get(
            "waterway_river_bounds_large_area_features",
            0,
        ),
        waterway_river_bounds_summary.get(
            "waterway_river_bounds_filtered_features",
            0,
        ),
        waterway_river_bounds_summary.get(
            "waterway_river_bounds_filtered_cells",
            0,
        ),
        waterway_river_bounds_summary.get(
            "waterway_river_bounds_max_area_ratio_to_map",
            0.0,
        ),
        waterway_river_bounds_summary.get(
            "waterway_river_bounds_max_height_ratio_to_map",
            0.0,
        ),
        waterway_river_bounds_summary.get(
            "waterway_river_bounds_max_width_ratio_to_map",
            0.0,
        ),
    )


class MapDemoView(APIView):
    def get(self, request):
        demo_path = finders.find("maps/demo.html")
        if demo_path is None:
            raise Http404("demo page not found")

        with open(demo_path, encoding="utf-8") as demo_file:
            return HttpResponse(demo_file.read(), content_type="text/html")


class MapAreaPageListView(LoginRequiredMixin, TemplateView):
    login_url = "login"
    template_name = "maps/grid_list.html"


class MapAreaPageDetailView(LoginRequiredMixin, TemplateView):
    login_url = "login"
    template_name = "maps/grid_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        area = get_viewable_map_area_or_404(
            self.request.user,
            self.kwargs["area_id"],
        )
        is_owner = area.created_by_id == self.request.user.id
        if is_owner:
            created_by_label = "自分"
        elif area.created_by:
            created_by_label = area.created_by.username
        else:
            created_by_label = "不明"

        context["area"] = area
        context["is_owner"] = is_owner
        context["display_type"] = "メモグリッド" if is_owner else "共有メモグリッド"
        context["created_by_label"] = created_by_label
        return context


class MapAreaListCreateView(APIView):
    authentication_classes = API_AUTHENTICATION_CLASSES
    permission_classes = [IsAuthenticated]

    def get(self, request):
        shared_area_ids = set(
            MapAreaShare.objects.filter(user=request.user).values_list(
                "area_id",
                flat=True,
            )
        )
        areas = (
            MapArea.objects.filter(
                Q(created_by=request.user) | Q(id__in=shared_area_ids)
            )
            .distinct()
            .order_by("name", "id")
        )

        return Response(
            {
                "areas": MapAreaListSerializer(
                    areas,
                    many=True,
                    context={
                        "request": request,
                        "shared_area_ids": shared_area_ids,
                    },
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = MapAreaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        center_grid_options = serializer.center_grid_options

        if center_grid_options is None:
            return Response(
                {
                    "detail": (
                        "MapArea 作成には center_lat/center_lng/"
                        "grid_size_meters/rows/cols が必要です。"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validate_center_grid_limits(
                grid_size_meters=serializer.validated_data["grid_size_meters"],
                rows=center_grid_options["rows"],
                cols=center_grid_options["cols"],
                is_staff=request.user.is_staff,
            )
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                area = serializer.save(created_by=request.user)
                grid_generation_options = {
                    "rows": center_grid_options["rows"],
                    "cols": center_grid_options["cols"],
                    "lat_step": center_grid_options["lat_step"],
                    "lng_step": center_grid_options["lng_step"],
                }
                feature_summaries_by_position = None

                if area.initial_score_mode == MapArea.InitialScoreMode.AUTO:
                    try:
                        feature_summaries_by_position = (
                            build_feature_summaries_for_map_area_from_overpass(
                                area,
                                **grid_generation_options,
                            )
                        )
                        logger.info(
                            "Overpass auto initial score succeeded: "
                            "area_id=%s user_id=%s initial_score_mode=%s "
                            "summary_count=%s",
                            area.id,
                            request.user.id,
                            area.initial_score_mode,
                            len(feature_summaries_by_position),
                        )
                        log_overpass_feature_summary(
                            area,
                            request.user.id,
                            feature_summaries_by_position,
                        )
                        log_overpass_score_breakdown_summary(
                            area,
                            request.user.id,
                            feature_summaries_by_position,
                        )
                        log_overpass_context_candidate_summary(
                            area,
                            request.user.id,
                            feature_summaries_by_position,
                            getattr(
                                feature_summaries_by_position,
                                "station_proximity_summary",
                                None,
                            ),
                        )
                        log_overpass_river_summary(
                            area,
                            request.user.id,
                            feature_summaries_by_position,
                            getattr(
                                feature_summaries_by_position,
                                "river_summary",
                                None,
                            ),
                        )
                        log_overpass_scored_river_summary(
                            area,
                            request.user.id,
                            feature_summaries_by_position,
                        )
                        log_overpass_scored_natural_coverage_summary(
                            area,
                            request.user.id,
                            feature_summaries_by_position,
                        )
                        log_overpass_waterway_summary(
                            area,
                            request.user.id,
                            getattr(
                                feature_summaries_by_position,
                                "waterway_summary",
                                None,
                            ),
                        )
                        log_overpass_railway_summary(
                            area,
                            request.user.id,
                            getattr(
                                feature_summaries_by_position,
                                "railway_summary",
                                None,
                            ),
                        )
                        log_overpass_station_summary(
                            area,
                            request.user.id,
                            getattr(
                                feature_summaries_by_position,
                                "station_summary",
                                None,
                            ),
                        )
                        log_overpass_landmark_summary(
                            area,
                            request.user.id,
                            getattr(
                                feature_summaries_by_position,
                                "landmark_summary",
                                None,
                            ),
                        )
                        log_overpass_castle_proximity_summary(
                            area,
                            request.user.id,
                            getattr(
                                feature_summaries_by_position,
                                "castle_proximity_summary",
                                None,
                            ),
                        )
                        log_overpass_expressway_summary(
                            area,
                            request.user.id,
                            getattr(
                                feature_summaries_by_position,
                                "expressway_summary",
                                None,
                            ),
                        )
                        log_overpass_expressway_bounds_summary(
                            area,
                            request.user.id,
                            getattr(
                                feature_summaries_by_position,
                                "expressway_bounds_summary",
                                None,
                            ),
                        )
                        log_overpass_effective_expressway_summary(
                            area,
                            request.user.id,
                            getattr(
                                feature_summaries_by_position,
                                "effective_expressway_summary",
                                None,
                            ),
                        )
                        log_overpass_waterway_river_bounds_summary(
                            area,
                            request.user.id,
                            getattr(
                                feature_summaries_by_position,
                                "waterway_river_bounds_summary",
                                None,
                            ),
                        )
                    except ValueError as error:
                        logger.warning(
                            "Overpass auto initial score failed; using fallback: "
                            "area_id=%s user_id=%s error=%s",
                            area.id,
                            request.user.id,
                            error,
                        )
                        feature_summaries_by_position = None

                if feature_summaries_by_position is not None:
                    grid_generation_options["feature_summaries_by_position"] = (
                        feature_summaries_by_position
                    )

                generate_grid_cells_for_area(area, **grid_generation_options)
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            MapAreaSerializer(area).data,
            status=status.HTTP_201_CREATED,
        )


class MapAreaDetailView(APIView):
    authentication_classes = API_AUTHENTICATION_CLASSES
    permission_classes = [IsAuthenticated]

    def get(self, request, area_id):
        area = get_viewable_map_area_or_404(request.user, area_id)

        return Response(
            MapAreaSerializer(area).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, area_id):
        area = get_owned_map_area_or_404(request.user, area_id)
        area.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class MapAreaShareListCreateView(APIView):
    authentication_classes = API_AUTHENTICATION_CLASSES
    permission_classes = [IsAuthenticated]

    def get(self, request, area_id):
        area = get_owned_map_area_or_404(request.user, area_id)
        shares = area.shares.select_related("user").all()

        return Response(
            {
                "area": {
                    "id": area.id,
                    "name": area.name,
                },
                "shares": MapAreaShareSerializer(shares, many=True).data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, area_id):
        area = get_owned_map_area_or_404(request.user, area_id)
        serializer = MapAreaShareCreateSerializer(
            data=request.data,
            context={"area": area},
        )
        serializer.is_valid(raise_exception=True)

        share = MapAreaShare.objects.create(
            area=area,
            user=serializer.validated_data["user"],
        )

        return Response(
            {
                "share": MapAreaShareSerializer(share).data,
            },
            status=status.HTTP_201_CREATED,
        )


class MapAreaShareDetailView(APIView):
    authentication_classes = API_AUTHENTICATION_CLASSES
    permission_classes = [IsAuthenticated]

    def delete(self, request, area_id, share_id):
        area = get_owned_map_area_or_404(request.user, area_id)
        share = get_object_or_404(MapAreaShare, id=share_id, area=area)
        share.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class GridRatingCreateView(APIView):
    authentication_classes = API_AUTHENTICATION_CLASSES
    permission_classes = [IsAuthenticated]

    def post(self, request, grid_id):
        grid = get_object_or_404(rateable_grid_cells_for_user(request.user), id=grid_id)
        serializer = GridRatingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        rating, created = GridRating.objects.update_or_create(
            grid=grid,
            user=request.user,
            defaults={
                "score": serializer.validated_data["score"],
                "comment": serializer.validated_data.get("comment", ""),
            },
        )
        updated_grid = update_grid_cell_score(grid)

        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(
            {
                "rating": GridRatingResponseSerializer(rating).data,
                "grid": GridCellScoreSerializer(updated_grid).data,
            },
            status=response_status,
        )


class BulkGridRatingCreateView(APIView):
    authentication_classes = API_AUTHENTICATION_CLASSES
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = BulkGridRatingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        grid_ids = serializer.validated_data["grid_ids"]
        grids = rateable_grid_cells_for_user(request.user).filter(id__in=grid_ids)
        grids_by_id = {grid.id: grid for grid in grids}
        if len(grids_by_id) != len(grid_ids):
            return Response(
                {
                    "grid_ids": [
                        "存在しない、または採点権限がない GridCell ID が含まれています。"
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        ordered_grids = [grids_by_id[grid_id] for grid_id in grid_ids]

        has_updated_rating = False
        updated_grids = []
        for grid in ordered_grids:
            _, created = GridRating.objects.update_or_create(
                grid=grid,
                user=request.user,
                defaults={
                    "score": serializer.validated_data["score"],
                    "comment": serializer.validated_data.get("comment", ""),
                },
            )
            if not created:
                has_updated_rating = True
            updated_grids.append(update_grid_cell_score(grid))

        response_status = (
            status.HTTP_200_OK if has_updated_rating else status.HTTP_201_CREATED
        )
        return Response(
            {
                "grids": GridCellScoreSerializer(updated_grids, many=True).data,
            },
            status=response_status,
        )


class GridCellListView(APIView):
    authentication_classes = API_AUTHENTICATION_CLASSES
    permission_classes = [IsAuthenticated]

    def get(self, request, area_id):
        area = get_viewable_map_area_or_404(request.user, area_id)
        grids = area.grid_cells.order_by("row_index", "col_index")

        return Response(
            {
                "area": {
                    "id": area.id,
                    "name": area.name,
                },
                "grids": GridCellScoreSerializer(grids, many=True).data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, area_id):
        area = get_object_or_404(MapArea, id=area_id)

        if area.created_by != request.user:
            return Response(
                {"detail": "この MapArea の GridCell を生成する権限がありません。"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            grids = generate_grid_cells_for_area(area)
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "area": {
                    "id": area.id,
                    "name": area.name,
                },
                "grids": GridCellScoreSerializer(grids, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )
