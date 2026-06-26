from django.contrib import admin

from .models import GridCell, GridRating, MapArea, MapAreaShare


# Django管理画面で、提出前のデータ確認や検索をしやすくする設定。
@admin.register(MapArea)
class MapAreaAdmin(admin.ModelAdmin):
    # MapAreaの作成者・範囲設定を一覧から追いやすくする。
    list_display = (
        "id",
        "name",
        "grid_generation_status",
        "grid_generation_attempt_count",
        "grid_size_meters",
        "map_grid_rows",
        "map_grid_cols",
        "source",
        "created_by",
        "created_at",
    )
    search_fields = ("name", "source")
    list_filter = ("grid_generation_status", "source", "created_at")
    readonly_fields = (
        "grid_generation_started_at",
        "grid_generation_finished_at",
    )


@admin.register(MapAreaShare)
class MapAreaShareAdmin(admin.ModelAdmin):
    # どのメモグリッドを誰に共有しているかを確認する。
    list_display = ("id", "area", "user", "created_at")
    search_fields = ("area__name", "user__username")
    list_filter = ("created_at",)


@admin.register(GridCell)
class GridCellAdmin(admin.ModelAdmin):
    # マスごとの位置とスコア状態を管理画面で確認する。
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
    # ユーザー採点とコメントの紐づき確認に使う。
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
