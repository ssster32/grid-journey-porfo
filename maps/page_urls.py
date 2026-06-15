from django.urls import path

from .views import (
    MapAreaPageCreateView,
    MapAreaPageDetailView,
    MapAreaPageListView,
)

# /maps/ 配下の画面URLをまとめる。
# API用URLとは分けて、一覧・作成・詳細の3画面へルーティングする。
urlpatterns = [
    path(
        "",
        MapAreaPageListView.as_view(),
        name="map-area-page-list",
    ),
    path(
        "new/",
        MapAreaPageCreateView.as_view(),
        name="map-area-page-create",
    ),
    path(
        "<int:area_id>/",
        MapAreaPageDetailView.as_view(),
        name="map-area-page-detail",
    ),
]
