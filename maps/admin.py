from django.contrib import admin

from .models import GridCell, GridRating, MapArea


@admin.register(MapArea)
class MapAreaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "grid_size_meters",
        "source",
        "created_by",
        "created_at",
    )
    search_fields = ("name", "source")
    list_filter = ("source", "created_at")


@admin.register(GridCell)
class GridCellAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "area",
        "row_index",
        "col_index",
        "initial_score",
        "calculated_score",
        "rating_count",
    )
    list_filter = ("area",)
    search_fields = ("area__name",)


@admin.register(GridRating)
class GridRatingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "grid",
        "user",
        "score",
        "created_at",
        "updated_at",
    )
    list_filter = ("score", "created_at")
    search_fields = ("grid__area__name", "user__username")
