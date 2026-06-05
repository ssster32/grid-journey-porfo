from django.conf import settings
from django.db import models
from django.db.models import F, Q


class MapArea(models.Model):
    class InitialScoreMode(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTO = "auto", "Auto"

    class RegionFeatureLevel(models.IntegerChoices):
        INITIAL = 0, "初期値"
        COMMON = 1, "ありふれた地域"
        NORMAL = 2, "普通の地域"
        DISTINCTIVE = 3, "特徴的な地域"

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    north = models.FloatField()
    south = models.FloatField()
    east = models.FloatField()
    west = models.FloatField()
    grid_size_meters = models.PositiveIntegerField()
    region_feature_level = models.PositiveSmallIntegerField(
        choices=RegionFeatureLevel.choices,
        default=RegionFeatureLevel.INITIAL,
    )
    initial_score_mode = models.CharField(
        max_length=20,
        choices=InitialScoreMode.choices,
        default=InitialScoreMode.MANUAL,
    )
    source = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="map_areas",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(north__gt=F("south")),
                name="map_area_north_gt_south",
            ),
            models.CheckConstraint(
                condition=Q(east__gt=F("west")),
                name="map_area_east_gt_west",
            ),
            models.CheckConstraint(
                condition=Q(grid_size_meters__gt=0),
                name="map_area_grid_size_meters_gt_0",
            ),
            models.CheckConstraint(
                condition=Q(region_feature_level__gte=0)
                & Q(region_feature_level__lte=3),
                name="map_area_region_feature_level_between_0_and_3",
            ),
        ]
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class MapAreaShare(models.Model):
    area = models.ForeignKey(
        MapArea,
        on_delete=models.CASCADE,
        related_name="shares",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shared_map_areas",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["area", "user"],
                name="unique_map_area_share_per_user",
            ),
        ]
        ordering = ["area", "user", "id"]

    def __str__(self):
        return f"{self.area} shared with {self.user}"


class GridCell(models.Model):
    area = models.ForeignKey(
        MapArea,
        on_delete=models.CASCADE,
        related_name="grid_cells",
    )
    row_index = models.PositiveIntegerField()
    col_index = models.PositiveIntegerField()
    north = models.FloatField()
    south = models.FloatField()
    east = models.FloatField()
    west = models.FloatField()
    initial_score = models.FloatField(default=0)
    auto_score_breakdown = models.JSONField(blank=True, null=True)
    average_user_score = models.FloatField(default=0)
    rating_count = models.PositiveIntegerField(default=0)
    calculated_score = models.FloatField(default=0)
    score_updated_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["area", "row_index", "col_index"],
                name="unique_grid_cell_position_per_area",
            ),
        ]
        ordering = ["area", "row_index", "col_index"]

    def __str__(self):
        return f"{self.area} ({self.row_index}, {self.col_index})"


class GridRating(models.Model):
    grid = models.ForeignKey(
        GridCell,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="grid_ratings",
    )
    score = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(score__gte=1) & Q(score__lte=10),
                name="grid_rating_score_between_1_and_10",
            ),
            models.UniqueConstraint(
                fields=["grid", "user"],
                name="unique_grid_rating_per_user",
            ),
        ]
        ordering = ["grid", "user", "id"]

    def __str__(self):
        return f"{self.user} -> {self.grid}: {self.score}"
