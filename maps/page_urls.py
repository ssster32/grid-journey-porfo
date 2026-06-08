from django.urls import path

from .views import MapAreaPageDetailView, MapAreaPageListView

urlpatterns = [
    path(
        "",
        MapAreaPageListView.as_view(),
        name="map-area-page-list",
    ),
    path(
        "<int:area_id>/",
        MapAreaPageDetailView.as_view(),
        name="map-area-page-detail",
    ),
]
