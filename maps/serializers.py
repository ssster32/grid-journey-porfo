from rest_framework import serializers

from .models import GridCell, GridRating, MapArea


class MapAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MapArea
        fields = [
            "id",
            "name",
            "description",
            "north",
            "south",
            "east",
            "west",
            "grid_size_meters",
            "source",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        if attrs["north"] <= attrs["south"]:
            raise serializers.ValidationError(
                {"north": "north は south より大きい値にしてください。"}
            )
        if attrs["east"] <= attrs["west"]:
            raise serializers.ValidationError(
                {"east": "east は west より大きい値にしてください。"}
            )
        if attrs["grid_size_meters"] <= 0:
            raise serializers.ValidationError(
                {"grid_size_meters": "grid_size_meters は 0 より大きい値にしてください。"}
            )

        return attrs


class GridRatingCreateSerializer(serializers.Serializer):
    score = serializers.IntegerField(min_value=1, max_value=10)
    comment = serializers.CharField(required=False, allow_blank=True)


class GridRatingResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = GridRating
        fields = [
            "id",
            "grid",
            "user",
            "score",
            "comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class GridCellScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = GridCell
        fields = [
            "id",
            "area",
            "row_index",
            "col_index",
            "north",
            "south",
            "east",
            "west",
            "initial_score",
            "average_user_score",
            "rating_count",
            "calculated_score",
            "score_updated_at",
        ]
        read_only_fields = fields


class BulkGridRatingSerializer(serializers.Serializer):
    grid_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    score = serializers.IntegerField(min_value=1, max_value=10)
    comment = serializers.CharField(required=False, allow_blank=True)

    def validate_grid_ids(self, grid_ids):
        unique_grid_ids = list(dict.fromkeys(grid_ids))
        existing_grid_ids = set(
            GridCell.objects.filter(id__in=unique_grid_ids).values_list("id", flat=True)
        )
        missing_grid_ids = [
            grid_id for grid_id in unique_grid_ids if grid_id not in existing_grid_ids
        ]

        if missing_grid_ids:
            raise serializers.ValidationError(
                f"存在しない GridCell ID が含まれています: {missing_grid_ids}"
            )

        return unique_grid_ids
