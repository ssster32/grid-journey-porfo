from django.urls import path

from .views import (
    BulkGridRatingCreateView,
    GridCellListView,
    GridRatingCreateView,
    MapDemoView,
    MapAreaDetailView,
    MapAreaListCreateView,
)

urlpatterns = [
    path(
        "demo/",
        MapDemoView.as_view(),
        name="map-demo",
    ),
    path(
        "areas/",
        MapAreaListCreateView.as_view(),
        name="map-area-list-create",
    ),
    path(
        "areas/<int:area_id>/",
        MapAreaDetailView.as_view(),
        name="map-area-detail",
    ),
    path(
        "areas/<int:area_id>/grids/",
        GridCellListView.as_view(),
        name="grid-cell-list",
    ),
    path(
        "areas/<int:area_id>/grids/",
        GridCellListView.as_view(),
        name="grid-cell-generate",
    ),
    path(
        "grids/bulk-ratings/",
        BulkGridRatingCreateView.as_view(),
        name="bulk-grid-rating-create",
    ),
    path(
        "grids/<int:grid_id>/ratings/",
        GridRatingCreateView.as_view(),
        name="grid-rating-create",
    ),
]
