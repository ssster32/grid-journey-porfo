from django.urls import path

from .views import (
    BulkGridRatingCreateView,
    GridCellListView,
    GridRatingCreateView,
    MapDemoView,
    MapAreaDetailView,
    MapAreaListCreateView,
    MapAreaShareDetailView,
    MapAreaShareListCreateView,
)

# /api/maps/ 配下のJSON API用URLをまとめる。
# 画面表示ではなく、作成・詳細・共有・GridCell取得・採点処理への入口。
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
        "areas/<int:area_id>/shares/",
        MapAreaShareListCreateView.as_view(),
        name="map-area-share-list-create",
    ),
    path(
        "areas/<int:area_id>/shares/<int:share_id>/",
        MapAreaShareDetailView.as_view(),
        name="map-area-share-detail",
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
