import logging

from django.contrib.staticfiles import finders
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
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
        "empty_cell_penalty_cells=%s",
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
