from django.urls import path

from .views import MapAreaPageListView

urlpatterns = [
    path(
        "",
        MapAreaPageListView.as_view(),
        name="map-area-page-list",
    ),
]
