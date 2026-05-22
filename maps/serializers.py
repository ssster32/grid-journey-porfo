from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import GridCell, GridRating, MapArea, MapAreaShare


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


class MapAreaListSerializer(MapAreaSerializer):
    visibility = serializers.SerializerMethodField()
    display_type = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    created_by_username = serializers.SerializerMethodField()

    class Meta(MapAreaSerializer.Meta):
        fields = MapAreaSerializer.Meta.fields + [
            "visibility",
            "display_type",
            "is_owner",
            "created_by_username",
        ]
        read_only_fields = fields

    def get_is_owner(self, obj):
        request = self.context["request"]
        return obj.created_by_id == request.user.id

    def get_visibility(self, obj):
        if self.get_is_owner(obj):
            return "private"
        return "shared"

    def get_display_type(self, obj):
        if self.get_visibility(obj) == "private":
            return "メモグリッド"
        return "共有メモグリッド"

    def get_created_by_username(self, obj):
        if obj.created_by is None:
            return None
        return obj.created_by.username


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = [
            "id",
            "username",
        ]
        read_only_fields = fields


class MapAreaShareSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)

    class Meta:
        model = MapAreaShare
        fields = [
            "id",
            "area",
            "user",
            "created_at",
        ]
        read_only_fields = fields


class MapAreaShareCreateSerializer(serializers.Serializer):
    username = serializers.CharField()

    def validate(self, attrs):
        area = self.context["area"]
        username = attrs["username"]
        user = get_user_model().objects.filter(username=username).first()

        if user is None:
            raise serializers.ValidationError(
                {"username": "指定されたユーザーは存在しません。"}
            )
        if user == area.created_by:
            raise serializers.ValidationError(
                {"username": "作成者自身は共有相手に追加できません。"}
            )
        if MapAreaShare.objects.filter(area=area, user=user).exists():
            raise serializers.ValidationError(
                {"username": "このユーザーは既に共有相手に追加されています。"}
            )

        attrs["user"] = user
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
