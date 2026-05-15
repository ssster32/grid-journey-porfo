from django.conf import settings
from django.db import models
from django.db.models import F, Q


class MapArea(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    north = models.FloatField()
    south = models.FloatField()
    east = models.FloatField()
    west = models.FloatField()
    grid_size_meters = models.PositiveIntegerField()
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
        ]
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


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
