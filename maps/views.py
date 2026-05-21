from django.contrib.staticfiles import finders
from django.db import transaction
from django.http import Http404, HttpResponse
from rest_framework import status
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import GridCell, GridRating, MapArea
from .serializers import (
    BulkGridRatingSerializer,
    GridCellScoreSerializer,
    MapAreaSerializer,
    GridRatingCreateSerializer,
    GridRatingResponseSerializer,
)
from .services import generate_grid_cells_for_area, update_grid_cell_score


class MapDemoView(APIView):
    def get(self, request):
        demo_path = finders.find("maps/demo.html")
        if demo_path is None:
            raise Http404("demo page not found")

        with open(demo_path, encoding="utf-8") as demo_file:
            return HttpResponse(demo_file.read(), content_type="text/html")


class MapAreaListCreateView(APIView):
    authentication_classes = [BasicAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        areas = MapArea.objects.filter(created_by=request.user)

        return Response(
            {
                "areas": MapAreaSerializer(areas, many=True).data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = MapAreaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                area = serializer.save(created_by=request.user)
                generate_grid_cells_for_area(area)
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
    authentication_classes = [BasicAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, area_id):
        area = get_object_or_404(MapArea, id=area_id, created_by=request.user)

        return Response(
            MapAreaSerializer(area).data,
            status=status.HTTP_200_OK,
        )


class GridRatingCreateView(APIView):
    authentication_classes = [BasicAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, grid_id):
        grid = get_object_or_404(
            GridCell,
            id=grid_id,
            area__created_by=request.user,
        )
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
    authentication_classes = [BasicAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = BulkGridRatingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        grid_ids = serializer.validated_data["grid_ids"]
        grids = GridCell.objects.filter(
            id__in=grid_ids,
            area__created_by=request.user,
        )
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
    authentication_classes = [BasicAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, area_id):
        area = get_object_or_404(MapArea, id=area_id, created_by=request.user)
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
