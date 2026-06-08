from django.urls import path

from .views import (
    MapAreaPageCreateView,
    MapAreaPageDetailView,
    MapAreaPageListView,
)

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
