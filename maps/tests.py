import base64
from math import cos, radians
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import GridCell, GridRating, MapArea, MapAreaShare
from .serializers import (
    BulkGridRatingSerializer,
    GridCellScoreSerializer,
    GridRatingCreateSerializer,
    GridRatingResponseSerializer,
    MapAreaSerializer,
)
from .services import (
    METERS_PER_DEGREE,
    build_grid_cell_contexts_for_area,
    calculate_initial_score_from_feature_summary,
    calculate_bounds_from_center,
    generate_grid_cells_for_area,
    update_grid_cell_score,
    validate_center_grid_limits,
)


class SerializerTestDataMixin:
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="testuser",
            password="test-password",
        )
        self.area = MapArea.objects.create(
            name="Test Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            created_by=self.user,
        )
        self.grid = GridCell.objects.create(
            area=self.area,
            row_index=0,
            col_index=0,
            north=35.7,
            south=35.69,
            east=139.8,
            west=139.79,
            initial_score=3,
            auto_score_breakdown={
                "base_score": 0.6,
                "diversity_bonus": 0.48,
                "context_bonus": 1.5,
                "penalty": 0.0,
                "raw_score": 2.58,
                "clamped_score": 2.58,
                "flags": {"has_landmark_context": True},
                "bonuses": {"landmark_context_bonus": 0.35},
                "counts": {"context_candidate_count": 1},
            },
            average_user_score=4,
            rating_count=1,
            calculated_score=3.5,
        )


class GridRatingCreateSerializerTests(TestCase):
    def test_score_1_is_valid(self):
        serializer = GridRatingCreateSerializer(data={"score": 1})

        self.assertTrue(serializer.is_valid())

    def test_score_10_is_valid(self):
        serializer = GridRatingCreateSerializer(data={"score": 10})

        self.assertTrue(serializer.is_valid())

    def test_score_0_is_invalid(self):
        serializer = GridRatingCreateSerializer(data={"score": 0})

        self.assertFalse(serializer.is_valid())
        self.assertIn("score", serializer.errors)

    def test_score_11_is_invalid(self):
        serializer = GridRatingCreateSerializer(data={"score": 11})

        self.assertFalse(serializer.is_valid())
        self.assertIn("score", serializer.errors)

    def test_blank_comment_is_valid(self):
        serializer = GridRatingCreateSerializer(data={"score": 5, "comment": ""})

        self.assertTrue(serializer.is_valid())

    def test_missing_score_is_invalid(self):
        serializer = GridRatingCreateSerializer(data={"comment": "nice"})

        self.assertFalse(serializer.is_valid())
        self.assertIn("score", serializer.errors)


class GridRatingResponseSerializerTests(SerializerTestDataMixin, TestCase):
    def test_grid_rating_instance_can_be_serialized(self):
        rating = GridRating.objects.create(
            grid=self.grid,
            user=self.user,
            score=8,
            comment="good",
        )

        data = GridRatingResponseSerializer(rating).data

        self.assertEqual(data["id"], rating.id)
        self.assertEqual(data["grid"], self.grid.id)
        self.assertEqual(data["user"], self.user.id)
        self.assertEqual(data["score"], 8)
        self.assertEqual(data["comment"], "good")
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)


class GridCellScoreSerializerTests(SerializerTestDataMixin, TestCase):
    def test_grid_cell_instance_can_be_serialized(self):
        data = GridCellScoreSerializer(self.grid).data

        self.assertEqual(data["id"], self.grid.id)
        self.assertEqual(data["area"], self.area.id)
        self.assertEqual(data["row_index"], 0)
        self.assertEqual(data["col_index"], 0)
        self.assertEqual(data["north"], 35.7)
        self.assertEqual(data["south"], 35.69)
        self.assertEqual(data["east"], 139.8)
        self.assertEqual(data["west"], 139.79)
        self.assertEqual(data["initial_score"], 3)
        self.assertEqual(data["auto_score_breakdown"]["base_score"], 0.6)
        self.assertTrue(
            data["auto_score_breakdown"]["flags"]["has_landmark_context"]
        )
        self.assertEqual(data["average_user_score"], 4)
        self.assertEqual(data["rating_count"], 1)
        self.assertEqual(data["calculated_score"], 3.5)
        self.assertIn("score_updated_at", data)


class MapAreaShareModelTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="owner",
            password="test-password",
        )
        self.shared_user = get_user_model().objects.create_user(
            username="shareduser",
            password="test-password",
        )
        self.area = MapArea.objects.create(
            name="Shared Memo Grid",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            created_by=self.owner,
        )

    def test_map_area_share_can_be_created(self):
        share = MapAreaShare.objects.create(
            area=self.area,
            user=self.shared_user,
        )

        self.assertEqual(share.area, self.area)
        self.assertEqual(share.user, self.shared_user)
        self.assertIsNotNone(share.created_at)
        self.assertEqual(str(share), f"{self.area} shared with {self.shared_user}")

    def test_area_related_name_can_get_shares(self):
        share = MapAreaShare.objects.create(
            area=self.area,
            user=self.shared_user,
        )

        self.assertEqual(list(self.area.shares.all()), [share])

    def test_user_related_name_can_get_shared_map_areas(self):
        share = MapAreaShare.objects.create(
            area=self.area,
            user=self.shared_user,
        )

        self.assertEqual(list(self.shared_user.shared_map_areas.all()), [share])

    def test_same_area_and_user_cannot_be_shared_twice(self):
        MapAreaShare.objects.create(
            area=self.area,
            user=self.shared_user,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MapAreaShare.objects.create(
                    area=self.area,
                    user=self.shared_user,
                )

    def test_deleting_map_area_deletes_share(self):
        share = MapAreaShare.objects.create(
            area=self.area,
            user=self.shared_user,
        )

        self.area.delete()

        self.assertFalse(MapAreaShare.objects.filter(id=share.id).exists())

    def test_deleting_shared_user_deletes_share(self):
        share = MapAreaShare.objects.create(
            area=self.area,
            user=self.shared_user,
        )

        self.shared_user.delete()

        self.assertFalse(MapAreaShare.objects.filter(id=share.id).exists())


class MapAreaModelTests(TestCase):
    def test_region_feature_level_defaults_to_zero(self):
        area = MapArea.objects.create(
            name="Default Region Feature Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
        )

        self.assertEqual(area.region_feature_level, 0)

    def test_initial_score_mode_defaults_to_manual(self):
        area = MapArea.objects.create(
            name="Default Initial Score Mode Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
        )

        self.assertEqual(area.initial_score_mode, MapArea.InitialScoreMode.MANUAL)


class MapAreaSerializerTests(TestCase):
    def center_payload(self):
        return {
            "name": "Center Area",
            "description": "center based",
            "center_lat": 35.695,
            "center_lng": 139.795,
            "grid_size_meters": 500,
            "rows": 6,
            "cols": 8,
            "source": "manual",
        }

    def test_valid_map_area_data_is_valid(self):
        serializer = MapAreaSerializer(data=self.center_payload())

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNotNone(serializer.center_grid_options)

    def test_center_based_map_area_data_is_valid(self):
        serializer = MapAreaSerializer(data=self.center_payload())

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIn("north", serializer.validated_data)
        self.assertIn("south", serializer.validated_data)
        self.assertIn("east", serializer.validated_data)
        self.assertIn("west", serializer.validated_data)
        self.assertGreater(
            serializer.validated_data["north"],
            serializer.validated_data["south"],
        )
        self.assertGreater(
            serializer.validated_data["east"],
            serializer.validated_data["west"],
        )

    def test_center_based_input_fields_are_removed_from_validated_data(self):
        serializer = MapAreaSerializer(data=self.center_payload())

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("center_lat", serializer.validated_data)
        self.assertNotIn("center_lng", serializer.validated_data)
        self.assertNotIn("rows", serializer.validated_data)
        self.assertNotIn("cols", serializer.validated_data)

    def test_center_based_map_area_sets_center_grid_options(self):
        serializer = MapAreaSerializer(data=self.center_payload())

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.center_grid_options["rows"], 6)
        self.assertEqual(serializer.center_grid_options["cols"], 8)
        self.assertIn("lat_step", serializer.center_grid_options)
        self.assertIn("lng_step", serializer.center_grid_options)

    def test_center_based_write_only_fields_are_not_in_serializer_data(self):
        serializer = MapAreaSerializer(data=self.center_payload())

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("center_lat", serializer.data)
        self.assertNotIn("center_lng", serializer.data)
        self.assertNotIn("rows", serializer.data)
        self.assertNotIn("cols", serializer.data)
        self.assertIn("region_feature_level", serializer.data)
        self.assertIn("initial_score_mode", serializer.data)

    def test_region_feature_level_defaults_to_zero(self):
        serializer = MapAreaSerializer(data=self.center_payload())

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["region_feature_level"], 0)

    def test_initial_score_mode_defaults_to_manual(self):
        serializer = MapAreaSerializer(data=self.center_payload())

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["initial_score_mode"],
            MapArea.InitialScoreMode.MANUAL,
        )

    def test_initial_score_mode_manual_and_auto_are_valid(self):
        for initial_score_mode in (
            MapArea.InitialScoreMode.MANUAL,
            MapArea.InitialScoreMode.AUTO,
        ):
            with self.subTest(initial_score_mode=initial_score_mode):
                serializer = MapAreaSerializer(
                    data={
                        **self.center_payload(),
                        "initial_score_mode": initial_score_mode,
                    }
                )

                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertEqual(
                    serializer.validated_data["initial_score_mode"],
                    initial_score_mode,
                )

    def test_invalid_initial_score_mode_is_invalid(self):
        invalid_values = ("invalid", "", None, 1, True)

        for initial_score_mode in invalid_values:
            with self.subTest(initial_score_mode=initial_score_mode):
                serializer = MapAreaSerializer(
                    data={
                        **self.center_payload(),
                        "initial_score_mode": initial_score_mode,
                    }
                )

                self.assertFalse(serializer.is_valid())
                self.assertIn("initial_score_mode", serializer.errors)

    def test_region_feature_level_0_to_3_are_valid(self):
        for region_feature_level in (0, 1, 2, 3):
            with self.subTest(region_feature_level=region_feature_level):
                payload = {
                    **self.center_payload(),
                    "region_feature_level": region_feature_level,
                }
                serializer = MapAreaSerializer(data=payload)

                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertEqual(
                    serializer.validated_data["region_feature_level"],
                    region_feature_level,
                )

    def test_region_feature_level_less_than_zero_is_invalid(self):
        serializer = MapAreaSerializer(
            data={**self.center_payload(), "region_feature_level": -1}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("region_feature_level", serializer.errors)

    def test_region_feature_level_greater_than_three_is_invalid(self):
        serializer = MapAreaSerializer(
            data={**self.center_payload(), "region_feature_level": 4}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("region_feature_level", serializer.errors)

    def test_region_feature_level_non_integer_is_invalid(self):
        serializer = MapAreaSerializer(
            data={**self.center_payload(), "region_feature_level": "abc"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("region_feature_level", serializer.errors)

    def test_region_feature_level_null_is_invalid(self):
        serializer = MapAreaSerializer(
            data={**self.center_payload(), "region_feature_level": None}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("region_feature_level", serializer.errors)

    def test_legacy_bounds_input_is_invalid(self):
        serializer = MapAreaSerializer(
            data={
                "name": "Tokyo Station Area",
                "north": 35.7,
                "south": 35.6,
                "east": 139.8,
                "west": 139.7,
                "grid_size_meters": 500,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_legacy_and_center_based_fields_are_invalid(self):
        payload = {
            **self.center_payload(),
            "north": 35.7,
            "south": 35.6,
            "east": 139.8,
            "west": 139.7,
        }
        serializer = MapAreaSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_incomplete_center_based_fields_are_invalid(self):
        payload = self.center_payload()
        payload.pop("rows")
        serializer = MapAreaSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_incomplete_legacy_fields_are_invalid(self):
        serializer = MapAreaSerializer(
            data={
                "name": "Tokyo Station Area",
                "north": 35.7,
                "south": 35.6,
                "grid_size_meters": 500,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_missing_center_lat_is_invalid(self):
        payload = self.center_payload()
        payload.pop("center_lat")
        serializer = MapAreaSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_missing_center_lng_is_invalid(self):
        payload = self.center_payload()
        payload.pop("center_lng")
        serializer = MapAreaSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_missing_cols_is_invalid(self):
        payload = self.center_payload()
        payload.pop("cols")
        serializer = MapAreaSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_center_based_rows_less_than_or_equal_to_zero_is_invalid(self):
        payload = {**self.center_payload(), "rows": 0}
        serializer = MapAreaSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_center_based_cols_less_than_or_equal_to_zero_is_invalid(self):
        payload = {**self.center_payload(), "cols": 0}
        serializer = MapAreaSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_center_based_invalid_center_lat_is_invalid(self):
        payload = {**self.center_payload(), "center_lat": 90}
        serializer = MapAreaSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_center_based_invalid_center_lng_is_invalid(self):
        payload = {**self.center_payload(), "center_lng": 181}
        serializer = MapAreaSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)


class BulkGridRatingSerializerTests(SerializerTestDataMixin, TestCase):
    def test_existing_grid_ids_and_score_are_valid(self):
        serializer = BulkGridRatingSerializer(
            data={"grid_ids": [self.grid.id], "score": 5}
        )

        self.assertTrue(serializer.is_valid())

    def test_score_1_is_valid(self):
        serializer = BulkGridRatingSerializer(
            data={"grid_ids": [self.grid.id], "score": 1}
        )

        self.assertTrue(serializer.is_valid())

    def test_score_10_is_valid(self):
        serializer = BulkGridRatingSerializer(
            data={"grid_ids": [self.grid.id], "score": 10}
        )

        self.assertTrue(serializer.is_valid())

    def test_score_0_is_invalid(self):
        serializer = BulkGridRatingSerializer(
            data={"grid_ids": [self.grid.id], "score": 0}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("score", serializer.errors)

    def test_score_11_is_invalid(self):
        serializer = BulkGridRatingSerializer(
            data={"grid_ids": [self.grid.id], "score": 11}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("score", serializer.errors)

    def test_empty_grid_ids_is_invalid(self):
        serializer = BulkGridRatingSerializer(data={"grid_ids": [], "score": 5})

        self.assertFalse(serializer.is_valid())
        self.assertIn("grid_ids", serializer.errors)

    def test_unknown_grid_id_is_invalid(self):
        serializer = BulkGridRatingSerializer(
            data={"grid_ids": [self.grid.id, 999999], "score": 5}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("grid_ids", serializer.errors)

    def test_duplicate_grid_ids_are_removed(self):
        serializer = BulkGridRatingSerializer(
            data={"grid_ids": [self.grid.id, self.grid.id], "score": 5}
        )

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["grid_ids"], [self.grid.id])

    def test_blank_comment_is_valid(self):
        serializer = BulkGridRatingSerializer(
            data={"grid_ids": [self.grid.id], "score": 5, "comment": ""}
        )

        self.assertTrue(serializer.is_valid())


class UpdateGridCellScoreTests(SerializerTestDataMixin, TestCase):
    def test_grid_with_ratings_updates_aggregate_score_fields(self):
        second_user = get_user_model().objects.create_user(
            username="seconduser",
            password="test-password",
        )
        GridRating.objects.create(grid=self.grid, user=self.user, score=8)
        GridRating.objects.create(grid=self.grid, user=second_user, score=6)

        update_grid_cell_score(self.grid)
        self.grid.refresh_from_db()

        self.assertEqual(self.grid.average_user_score, 7)
        self.assertEqual(self.grid.rating_count, 2)
        self.assertEqual(self.grid.calculated_score, 5)
        self.assertIsNotNone(self.grid.score_updated_at)

    def test_grid_without_ratings_uses_initial_score(self):
        self.grid.average_user_score = 8
        self.grid.rating_count = 3
        self.grid.calculated_score = 7
        self.grid.save()

        update_grid_cell_score(self.grid)
        self.grid.refresh_from_db()

        self.assertEqual(self.grid.average_user_score, 0)
        self.assertEqual(self.grid.rating_count, 0)
        self.assertEqual(self.grid.calculated_score, self.grid.initial_score)
        self.assertIsNone(self.grid.score_updated_at)


class CalculateBoundsFromCenterTests(TestCase):
    def test_calculates_bounds_from_center(self):
        result = calculate_bounds_from_center(
            center_lat=35.695,
            center_lng=139.795,
            grid_size_meters=500,
            rows=6,
            cols=8,
        )

        self.assertGreater(result["north"], result["south"])
        self.assertGreater(result["east"], result["west"])
        self.assertAlmostEqual((result["north"] + result["south"]) / 2, 35.695)
        self.assertAlmostEqual((result["east"] + result["west"]) / 2, 139.795)
        self.assertEqual(result["rows"], 6)
        self.assertEqual(result["cols"], 8)

    def test_lat_step_uses_meters_per_degree(self):
        result = calculate_bounds_from_center(35.695, 139.795, 500, 6, 8)

        self.assertAlmostEqual(result["lat_step"], 500 / METERS_PER_DEGREE)

    def test_rows_define_latitude_height(self):
        result = calculate_bounds_from_center(35.695, 139.795, 500, 6, 8)

        self.assertAlmostEqual(
            result["north"] - result["south"],
            result["lat_step"] * 6,
        )

    def test_cols_define_longitude_width(self):
        result = calculate_bounds_from_center(35.695, 139.795, 500, 6, 8)

        self.assertAlmostEqual(
            result["east"] - result["west"],
            result["lng_step"] * 8,
        )

    def test_lng_step_uses_center_lat_cosine_correction(self):
        result = calculate_bounds_from_center(35.695, 139.795, 500, 6, 8)
        expected_lng_step = 500 / (METERS_PER_DEGREE * cos(radians(35.695)))

        self.assertAlmostEqual(result["lng_step"], expected_lng_step)

    def test_invalid_center_lat_raises_value_error(self):
        with self.assertRaises(ValueError):
            calculate_bounds_from_center(90, 139.795, 500, 6, 8)

    def test_non_finite_center_lat_raises_value_error(self):
        with self.assertRaises(ValueError):
            calculate_bounds_from_center(float("inf"), 139.795, 500, 6, 8)

    def test_invalid_center_lng_raises_value_error(self):
        with self.assertRaises(ValueError):
            calculate_bounds_from_center(35.695, 181, 500, 6, 8)

    def test_non_finite_center_lng_raises_value_error(self):
        with self.assertRaises(ValueError):
            calculate_bounds_from_center(35.695, float("nan"), 500, 6, 8)

    def test_grid_size_meters_less_than_or_equal_to_zero_raises_value_error(self):
        with self.assertRaises(ValueError):
            calculate_bounds_from_center(35.695, 139.795, 0, 6, 8)

    def test_rows_less_than_or_equal_to_zero_raises_value_error(self):
        with self.assertRaises(ValueError):
            calculate_bounds_from_center(35.695, 139.795, 500, 0, 8)

    def test_cols_less_than_or_equal_to_zero_raises_value_error(self):
        with self.assertRaises(ValueError):
            calculate_bounds_from_center(35.695, 139.795, 500, 6, 0)

    def test_non_integer_rows_raises_value_error(self):
        with self.assertRaises(ValueError):
            calculate_bounds_from_center(35.695, 139.795, 500, 6.5, 8)

    def test_non_integer_cols_raises_value_error(self):
        with self.assertRaises(ValueError):
            calculate_bounds_from_center(35.695, 139.795, 500, 6, 8.5)


class ValidateCenterGridLimitsTests(TestCase):
    def test_general_user_can_use_cell_count_equal_to_limit(self):
        validate_center_grid_limits(10, 20, 25)

    def test_general_user_cell_count_over_limit_raises_value_error(self):
        with self.assertRaises(ValueError):
            validate_center_grid_limits(10, 20, 26)

    def test_general_user_can_use_height_equal_to_limit(self):
        validate_center_grid_limits(1000, 30, 10)

    def test_general_user_height_over_limit_raises_value_error(self):
        with self.assertRaises(ValueError):
            validate_center_grid_limits(1000, 31, 10)

    def test_general_user_can_use_width_equal_to_limit(self):
        validate_center_grid_limits(1000, 10, 30)

    def test_general_user_width_over_limit_raises_value_error(self):
        with self.assertRaises(ValueError):
            validate_center_grid_limits(1000, 10, 31)

    def test_staff_user_is_exempt_from_general_limits(self):
        validate_center_grid_limits(1000, 100, 100, is_staff=True)

    def test_staff_user_still_needs_positive_grid_size(self):
        with self.assertRaises(ValueError):
            validate_center_grid_limits(0, 100, 100, is_staff=True)

    def test_staff_user_still_needs_positive_rows(self):
        with self.assertRaises(ValueError):
            validate_center_grid_limits(1000, 0, 100, is_staff=True)

    def test_staff_user_still_needs_positive_cols(self):
        with self.assertRaises(ValueError):
            validate_center_grid_limits(1000, 100, 0, is_staff=True)

    def test_non_integer_rows_raises_value_error(self):
        with self.assertRaises(ValueError):
            validate_center_grid_limits(1000, 1.5, 100)

    def test_non_integer_cols_raises_value_error(self):
        with self.assertRaises(ValueError):
            validate_center_grid_limits(1000, 100, 1.5)


class GenerateGridCellsForAreaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="testuser",
            password="test-password",
        )
        self.area = MapArea.objects.create(
            name="Grid Area",
            north=1.0,
            south=0.85,
            east=1.0,
            west=0.85,
            grid_size_meters=11100,
            created_by=self.user,
        )

    def create_center_grid_area(self):
        bounds = calculate_bounds_from_center(
            center_lat=35.695,
            center_lng=139.795,
            grid_size_meters=500,
            rows=6,
            cols=8,
        )
        area = MapArea.objects.create(
            name="Center Grid Area",
            north=bounds["north"],
            south=bounds["south"],
            east=bounds["east"],
            west=bounds["west"],
            grid_size_meters=500,
            created_by=self.user,
        )

        return area, bounds

    def test_map_area_generates_grid_cells(self):
        grid_cells = generate_grid_cells_for_area(self.area)

        self.assertEqual(len(grid_cells), 4)
        self.assertEqual(GridCell.objects.filter(area=self.area).count(), 4)

    def test_build_grid_cell_contexts_returns_expected_count(self):
        contexts = build_grid_cell_contexts_for_area(self.area)

        self.assertEqual(len(contexts), 4)

    def test_build_grid_cell_contexts_indexes_match_generated_grid_cells(self):
        contexts = build_grid_cell_contexts_for_area(self.area)
        generate_grid_cells_for_area(self.area)
        context_positions = [
            (context["row_index"], context["col_index"]) for context in contexts
        ]
        grid_positions = list(
            GridCell.objects.filter(area=self.area).values_list(
                "row_index",
                "col_index",
            )
        )

        self.assertEqual(context_positions, grid_positions)

    def test_build_grid_cell_contexts_bounds_match_generated_grid_cells(self):
        contexts = build_grid_cell_contexts_for_area(self.area)
        generate_grid_cells_for_area(self.area)

        for context in contexts:
            grid_cell = GridCell.objects.get(
                area=self.area,
                row_index=context["row_index"],
                col_index=context["col_index"],
            )
            self.assertAlmostEqual(context["north"], grid_cell.north)
            self.assertAlmostEqual(context["south"], grid_cell.south)
            self.assertAlmostEqual(context["east"], grid_cell.east)
            self.assertAlmostEqual(context["west"], grid_cell.west)

    def test_generated_grid_indexes_start_from_zero(self):
        generate_grid_cells_for_area(self.area)

        positions = list(
            GridCell.objects.filter(area=self.area).values_list(
                "row_index",
                "col_index",
            )
        )

        self.assertEqual(positions, [(0, 0), (0, 1), (1, 0), (1, 1)])

    def test_generated_grid_score_fields_use_initial_values(self):
        grid_cells = generate_grid_cells_for_area(self.area)

        for grid_cell in grid_cells:
            self.assertEqual(grid_cell.initial_score, 0)
            self.assertIsNone(grid_cell.auto_score_breakdown)
            self.assertEqual(grid_cell.average_user_score, 0)
            self.assertEqual(grid_cell.rating_count, 0)
            self.assertEqual(grid_cell.calculated_score, 0)
            self.assertIsNone(grid_cell.score_updated_at)

    def test_generated_grid_score_fields_use_region_feature_level(self):
        self.area.region_feature_level = 2
        self.area.save(update_fields=["region_feature_level"])

        grid_cells = generate_grid_cells_for_area(self.area)

        for grid_cell in grid_cells:
            self.assertEqual(grid_cell.initial_score, 2.0)
            self.assertIsNone(grid_cell.auto_score_breakdown)
            self.assertEqual(grid_cell.average_user_score, 0)
            self.assertEqual(grid_cell.rating_count, 0)
            self.assertEqual(grid_cell.calculated_score, 2.0)
            self.assertIsNone(grid_cell.score_updated_at)

    def test_generated_grid_stores_auto_score_breakdown_for_feature_summary(self):
        grid_cells = generate_grid_cells_for_area(
            self.area,
            feature_summaries_by_position={
                (0, 0): {
                    "building_count": 20,
                    "has_park": True,
                    "water_coverage_ratio": 0.2,
                    "tourism_attraction_count": 1,
                },
            },
        )
        auto_grid = next(
            grid_cell
            for grid_cell in grid_cells
            if grid_cell.row_index == 0 and grid_cell.col_index == 0
        )
        manual_grid = next(
            grid_cell
            for grid_cell in grid_cells
            if grid_cell.row_index == 0 and grid_cell.col_index == 1
        )

        self.assertIsNotNone(auto_grid.auto_score_breakdown)
        self.assertEqual(
            auto_grid.initial_score,
            auto_grid.auto_score_breakdown["clamped_score"],
        )
        self.assertIn("base_score", auto_grid.auto_score_breakdown)
        self.assertIn("diversity_bonus", auto_grid.auto_score_breakdown)
        self.assertIn("context_bonus", auto_grid.auto_score_breakdown)
        self.assertIn("penalty", auto_grid.auto_score_breakdown)
        self.assertIn("raw_score", auto_grid.auto_score_breakdown)
        self.assertIn("flags", auto_grid.auto_score_breakdown)
        self.assertTrue(
            auto_grid.auto_score_breakdown["flags"]["has_landmark_context"]
        )
        self.assertIsNone(manual_grid.auto_score_breakdown)

    def test_explicit_rows_and_cols_generate_exact_grid_count(self):
        area, bounds = self.create_center_grid_area()

        grid_cells = generate_grid_cells_for_area(
            area,
            rows=bounds["rows"],
            cols=bounds["cols"],
            lat_step=bounds["lat_step"],
            lng_step=bounds["lng_step"],
        )

        self.assertEqual(len(grid_cells), 48)
        self.assertEqual(GridCell.objects.filter(area=area).count(), 48)

    def test_explicit_grid_cell_contexts_match_generated_grid_cells(self):
        area, bounds = self.create_center_grid_area()

        contexts = build_grid_cell_contexts_for_area(
            area,
            rows=bounds["rows"],
            cols=bounds["cols"],
            lat_step=bounds["lat_step"],
            lng_step=bounds["lng_step"],
        )
        generate_grid_cells_for_area(
            area,
            rows=bounds["rows"],
            cols=bounds["cols"],
            lat_step=bounds["lat_step"],
            lng_step=bounds["lng_step"],
        )

        self.assertEqual(len(contexts), 48)
        first_context = contexts[0]
        last_context = contexts[-1]
        first_grid = GridCell.objects.get(area=area, row_index=0, col_index=0)
        last_grid = GridCell.objects.get(area=area, row_index=5, col_index=7)
        self.assertAlmostEqual(first_context["north"], first_grid.north)
        self.assertAlmostEqual(first_context["west"], first_grid.west)
        self.assertAlmostEqual(last_context["south"], last_grid.south)
        self.assertAlmostEqual(last_context["east"], last_grid.east)

    def test_explicit_rows_and_cols_generate_expected_indexes(self):
        area, bounds = self.create_center_grid_area()

        generate_grid_cells_for_area(
            area,
            rows=bounds["rows"],
            cols=bounds["cols"],
            lat_step=bounds["lat_step"],
            lng_step=bounds["lng_step"],
        )
        row_indexes = set(
            GridCell.objects.filter(area=area).values_list("row_index", flat=True)
        )
        col_indexes = set(
            GridCell.objects.filter(area=area).values_list("col_index", flat=True)
        )

        self.assertEqual(row_indexes, set(range(6)))
        self.assertEqual(col_indexes, set(range(8)))

    def test_explicit_grid_cells_align_to_area_bounds(self):
        area, bounds = self.create_center_grid_area()

        generate_grid_cells_for_area(
            area,
            rows=bounds["rows"],
            cols=bounds["cols"],
            lat_step=bounds["lat_step"],
            lng_step=bounds["lng_step"],
        )
        first_grid = GridCell.objects.get(area=area, row_index=0, col_index=0)
        last_row_grid = GridCell.objects.get(area=area, row_index=5, col_index=0)
        last_col_grid = GridCell.objects.get(area=area, row_index=0, col_index=7)

        self.assertAlmostEqual(first_grid.north, area.north)
        self.assertAlmostEqual(first_grid.west, area.west)
        self.assertAlmostEqual(last_row_grid.south, area.south)
        self.assertAlmostEqual(last_col_grid.east, area.east)

    def test_explicit_steps_are_reflected_in_grid_bounds(self):
        area, bounds = self.create_center_grid_area()

        generate_grid_cells_for_area(
            area,
            rows=bounds["rows"],
            cols=bounds["cols"],
            lat_step=bounds["lat_step"],
            lng_step=bounds["lng_step"],
        )
        grid = GridCell.objects.get(area=area, row_index=1, col_index=1)

        self.assertAlmostEqual(grid.north, area.north - bounds["lat_step"])
        self.assertAlmostEqual(grid.south, grid.north - bounds["lat_step"])
        self.assertAlmostEqual(grid.west, area.west + bounds["lng_step"])
        self.assertAlmostEqual(grid.east, grid.west + bounds["lng_step"])

    def test_edge_grid_cells_do_not_exceed_map_area_bounds(self):
        generate_grid_cells_for_area(self.area)

        for grid_cell in GridCell.objects.filter(area=self.area):
            self.assertLessEqual(grid_cell.north, self.area.north)
            self.assertGreaterEqual(grid_cell.south, self.area.south)
            self.assertLessEqual(grid_cell.east, self.area.east)
            self.assertGreaterEqual(grid_cell.west, self.area.west)

        edge_grid = GridCell.objects.get(area=self.area, row_index=1, col_index=1)

        self.assertAlmostEqual(edge_grid.south, self.area.south)
        self.assertAlmostEqual(edge_grid.east, self.area.east)

    def test_existing_grid_cells_raise_value_error_without_creating_more(self):
        GridCell.objects.create(
            area=self.area,
            row_index=0,
            col_index=0,
            north=1.0,
            south=0.9,
            east=0.95,
            west=0.85,
        )

        with self.assertRaises(ValueError):
            generate_grid_cells_for_area(self.area)

        self.assertEqual(GridCell.objects.filter(area=self.area).count(), 1)

    def test_partial_explicit_grid_args_raise_value_error(self):
        with self.assertRaises(ValueError):
            generate_grid_cells_for_area(self.area, rows=6)

        with self.assertRaises(ValueError):
            generate_grid_cells_for_area(self.area, rows=6, cols=8)

        with self.assertRaises(ValueError):
            generate_grid_cells_for_area(
                self.area,
                rows=6,
                cols=8,
                lat_step=0.001,
            )

        with self.assertRaises(ValueError):
            generate_grid_cells_for_area(
                self.area,
                lat_step=0.001,
                lng_step=0.001,
            )

    def test_explicit_rows_less_than_or_equal_to_zero_raises_value_error(self):
        with self.assertRaises(ValueError):
            generate_grid_cells_for_area(
                self.area,
                rows=0,
                cols=8,
                lat_step=0.001,
                lng_step=0.001,
            )

    def test_explicit_cols_less_than_or_equal_to_zero_raises_value_error(self):
        with self.assertRaises(ValueError):
            generate_grid_cells_for_area(
                self.area,
                rows=6,
                cols=0,
                lat_step=0.001,
                lng_step=0.001,
            )

    def test_explicit_non_integer_rows_raises_value_error(self):
        with self.assertRaises(ValueError):
            generate_grid_cells_for_area(
                self.area,
                rows=6.5,
                cols=8,
                lat_step=0.001,
                lng_step=0.001,
            )

    def test_explicit_non_integer_cols_raises_value_error(self):
        with self.assertRaises(ValueError):
            generate_grid_cells_for_area(
                self.area,
                rows=6,
                cols=8.5,
                lat_step=0.001,
                lng_step=0.001,
            )

    def test_explicit_lat_step_less_than_or_equal_to_zero_raises_value_error(self):
        with self.assertRaises(ValueError):
            generate_grid_cells_for_area(
                self.area,
                rows=6,
                cols=8,
                lat_step=0,
                lng_step=0.001,
            )

    def test_explicit_lng_step_less_than_or_equal_to_zero_raises_value_error(self):
        with self.assertRaises(ValueError):
            generate_grid_cells_for_area(
                self.area,
                rows=6,
                cols=8,
                lat_step=0.001,
                lng_step=0,
            )

    def test_grid_size_meters_less_than_or_equal_to_zero_raises_value_error(self):
        self.area.grid_size_meters = 0

        with self.assertRaises(ValueError):
            generate_grid_cells_for_area(self.area)

        self.assertEqual(GridCell.objects.filter(area=self.area).count(), 0)

    def test_north_less_than_or_equal_to_south_raises_value_error(self):
        self.area.north = self.area.south

        with self.assertRaises(ValueError):
            generate_grid_cells_for_area(self.area)

        self.assertEqual(GridCell.objects.filter(area=self.area).count(), 0)

    def test_east_less_than_or_equal_to_west_raises_value_error(self):
        self.area.east = self.area.west

        with self.assertRaises(ValueError):
            generate_grid_cells_for_area(self.area)

        self.assertEqual(GridCell.objects.filter(area=self.area).count(), 0)


class MapDemoViewTests(TestCase):
    def test_demo_page_returns_200(self):
        response = self.client.get(reverse("map-demo"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Map Demo")
        self.assertContains(response, "メモグリッド作成")
        self.assertContains(response, "メモグリッド一覧を取得")
        self.assertContains(response, "メモグリッドを作成")
        self.assertContains(response, "自分が作成したメモグリッドは一覧から削除できます")
        self.assertContains(response, "共有メモグリッドは削除できません")
        self.assertContains(response, "中心緯度")
        self.assertContains(response, "中心経度")
        self.assertContains(response, "縦方向のマス数")
        self.assertContains(response, "横方向のマス数")
        self.assertContains(response, "center_lat")
        self.assertContains(response, "center_lng")
        self.assertContains(response, "rows")
        self.assertContains(response, "cols")
        self.assertContains(response, "area-center-lat")
        self.assertContains(response, "area-center-lng")
        self.assertContains(response, "area-rows")
        self.assertContains(response, "area-cols")
        self.assertContains(response, "初期スコア設定")
        self.assertContains(response, "initial_score_mode")
        self.assertContains(response, "region_feature_level")
        self.assertContains(response, "area-region-feature-level")
        self.assertContains(response, "自動設定")
        self.assertContains(response, "0: 初期値")
        self.assertContains(response, "1: ありふれた地域")
        self.assertContains(response, "2: 普通の地域")
        self.assertContains(response, "3: 特徴的な地域")
        self.assertNotContains(response, "area-north")
        self.assertNotContains(response, "area-south")
        self.assertNotContains(response, "area-east")
        self.assertNotContains(response, "area-west")
        self.assertNotContains(response, "GridCell を自動生成")
        self.assertContains(response, "セルの再取得")
        self.assertContains(response, "selected-area-name")
        self.assertContains(response, "メモグリッドを選択してください")
        self.assertNotContains(response, "grids-heading")
        self.assertNotContains(response, "selected-area-label")
        self.assertNotContains(response, "Score Map")
        self.assertNotContains(response, "score-map-view-mode")
        self.assertNotContains(response, "score-map-view-mode-fit")
        self.assertNotContains(response, "score-map-view-mode-detail")
        self.assertNotContains(response, "score-map-stage")
        self.assertNotContains(response, "score-map-background")
        self.assertNotContains(response, "score-map-grid-layer")
        self.assertNotContains(response, "score-selection-rect")
        self.assertNotContains(response, "score-map-ratio")
        self.assertContains(response, "Leaflet")
        self.assertContains(response, "Map Preview")
        self.assertContains(response, "MapArea を選択してください")
        self.assertContains(response, "GridCell 境界")
        self.assertContains(response, "地図上でのスコア分布")
        self.assertContains(response, "GridCell は Map Preview から選択できます")
        self.assertContains(response, "Shift + ドラッグ")
        self.assertContains(response, "範囲選択")
        self.assertContains(response, "map-preview-legend")
        self.assertContains(response, "map-preview")
        self.assertContains(response, "map-preview-status")
        self.assertContains(response, "OpenStreetMap")
        self.assertContains(response, "leaflet.css")
        self.assertContains(response, "leaflet.js")
        self.assertContains(response, "共有相手管理")
        self.assertContains(response, "share-summary")
        self.assertContains(response, "共有相手一覧を取得")
        self.assertContains(response, "共有相手 username")
        self.assertContains(response, "共有相手を追加")
        self.assertContains(response, "共有を解除")
        self.assertContains(response, "share-username")
        self.assertContains(response, "load-shares")
        self.assertContains(response, "add-share")
        self.assertContains(response, "shares-list")
        self.assertContains(response, "選択中のマス")
        self.assertContains(response, "GridCell を選択してください")
        self.assertContains(response, "選択数")
        self.assertContains(response, "選択をすべて解除")
        self.assertContains(response, "採点方式")
        self.assertContains(response, "個別に入力し、まとめて採点")
        self.assertContains(response, "選択グリッドを全て同じ値で採点")
        self.assertContains(response, "まとめて採点する")
        self.assertContains(response, "同じ値で採点する")
        self.assertContains(response, "selected-grid-label")
        self.assertContains(response, "selected-grid-count")
        self.assertContains(response, "clear-selected-grids")
        self.assertContains(response, "selected-grids-list")
        self.assertContains(response, "multi-rating-mode-individual")
        self.assertContains(response, "multi-rating-mode-same")
        self.assertContains(response, "same-score-input")
        self.assertContains(response, "individual-rating-submit")
        self.assertContains(response, "same-score-rating-submit")
        self.assertContains(response, "selected-grid-message")
        self.assertContains(response, "selected-grid-loading-spinner")
        self.assertContains(response, "loading-spinner")
        self.assertContains(response, "auto-score-breakdown")
        self.assertContains(response, "自動採点理由")
        self.assertContains(response, "自動採点内訳なし")
        self.assertNotContains(response, "selected-grid-rating-form")
        self.assertNotContains(response, "selected-grid-score")
        self.assertNotContains(response, "selected-grid-rate-button")
        self.assertNotContains(response, "grids-body")
        self.assertNotContains(response, "data-rate-grid")

    def test_demo_static_files_include_area_delete_ui(self):
        demo_js_path = finders.find("maps/demo.js")
        demo_css_path = finders.find("maps/demo.css")

        with open(demo_js_path, encoding="utf-8") as demo_js_file:
            demo_js = demo_js_file.read()
        with open(demo_css_path, encoding="utf-8") as demo_css_file:
            demo_css = demo_css_file.read()

        self.assertIn("deleteArea", demo_js)
        self.assertIn("clearSelectedAreaStateAfterDelete", demo_js)
        self.assertIn("clearMapAreaPreview", demo_js)
        self.assertIn("boxZoom: false", demo_js)
        self.assertIn("zoomSnap: 0.25", demo_js)
        self.assertIn("zoomDelta: 0.25", demo_js)
        self.assertIn("MAP_PREVIEW_TARGET_FILL_RATIO", demo_js)
        self.assertIn("mapPreviewFitPadding", demo_js)
        self.assertIn("getBoundingClientRect", demo_js)
        self.assertIn("padding: mapPreviewFitPadding()", demo_js)
        self.assertIn("maxZoom: MAP_PREVIEW_MAX_ZOOM", demo_js)
        self.assertIn("mapGridScoreLabelsById", demo_js)
        self.assertIn("gridCellCenterLatLng", demo_js)
        self.assertIn("mapGridScoreLabelIcon", demo_js)
        self.assertIn("mapPreviewScoreLabelClass", demo_js)
        self.assertIn("map-preview-score-label", demo_js)
        self.assertIn("map-preview-score-low", demo_js)
        self.assertIn("map-preview-score-middle", demo_js)
        self.assertIn("map-preview-score-high", demo_js)
        self.assertIn("map-preview-score-very-high", demo_js)
        self.assertNotIn(
            "className: `map-preview-score-label ${scoreClass(score)}`",
            demo_js,
        )
        self.assertIn("const isIndividualMode = mode === \"individual\"", demo_js)
        self.assertIn("const isSameMode = mode === \"same\"", demo_js)
        self.assertIn("elements.individualRatingSubmit.hidden", demo_js)
        self.assertIn("elements.sameScoreRatingSubmit.hidden", demo_js)
        self.assertNotIn("applyExtraMapPreviewZoom(area)", demo_js)
        self.assertIn("area-delete-button", demo_js)
        self.assertIn("data-delete-area-id", demo_js)
        self.assertIn("関連するGridCell、採点、共有設定も削除されます", demo_js)
        self.assertIn("areaRegionFeatureLevel", demo_js)
        self.assertIn("selectedInitialScoreValue", demo_js)
        self.assertIn("initialScoreMode", demo_js)
        self.assertIn("regionFeatureLevel", demo_js)
        self.assertIn("initial_score_mode", demo_js)
        self.assertIn("initial_score_mode: initialScoreMode", demo_js)
        self.assertIn("\"auto\"", demo_js)
        self.assertIn("\"manual\"", demo_js)
        self.assertIn("region_feature_level", demo_js)
        self.assertIn("region_feature_level: regionFeatureLevel", demo_js)
        self.assertIn("selectedAreaName", demo_js)
        self.assertIn("elements.selectedAreaName.textContent = areaName", demo_js)
        self.assertIn("autoScoreBreakdown", demo_js)
        self.assertIn("renderAutoScoreBreakdown", demo_js)
        self.assertIn("auto_score_breakdown", demo_js)
        self.assertIn("主な理由", demo_js)
        self.assertIn("観光名所", demo_js)
        self.assertIn("公園 + 水辺", demo_js)
        self.assertNotIn("scoreMap", demo_js)
        self.assertNotIn("renderScoreMap", demo_js)
        self.assertNotIn("highlightSelectedScoreCells", demo_js)
        self.assertNotIn("score-map", demo_css)
        self.assertIn(".auto-score-breakdown", demo_css)
        self.assertIn(".auto-score-components", demo_css)
        self.assertIn(".auto-score-reasons", demo_css)
        self.assertIn(".map-preview-score-label", demo_css)
        self.assertIn(".map-preview-score-label.map-preview-score-low", demo_css)
        self.assertIn(".map-preview-score-label.map-preview-score-middle", demo_css)
        self.assertIn(".map-preview-score-label.map-preview-score-high", demo_css)
        self.assertIn(".map-preview-score-label.map-preview-score-very-high", demo_css)
        self.assertIn("background: transparent", demo_css)
        self.assertIn("pointer-events: none", demo_css)
        self.assertIn(".area-delete-button", demo_css)


class TokenAuthenticationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="testuser",
            password="test-password",
        )
        self.other_user = get_user_model().objects.create_user(
            username="otheruser",
            password="other-password",
        )
        self.client = APIClient()
        self.token_url = reverse("api-token-auth")
        self.area_url = reverse("map-area-list-create")
        self.valid_payload = {
            "name": "Token Test Area",
            "description": "created with token",
            "center_lat": 35.695,
            "center_lng": 139.795,
            "grid_size_meters": 500,
            "rows": 6,
            "cols": 8,
            "source": "token-test",
        }

    def token_credentials(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        return {"HTTP_AUTHORIZATION": f"Token {token.key}"}

    def basic_credentials(self, username, password):
        raw_credentials = f"{username}:{password}".encode()
        encoded_credentials = base64.b64encode(raw_credentials).decode()
        return {"HTTP_AUTHORIZATION": f"Basic {encoded_credentials}"}

    def test_valid_username_and_password_return_token(self):
        response = self.client.post(
            self.token_url,
            {
                "username": "testuser",
                "password": "test-password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)
        self.assertEqual(response.data["token"], Token.objects.get(user=self.user).key)

    def test_invalid_password_returns_400(self):
        response = self.client.post(
            self.token_url,
            {
                "username": "testuser",
                "password": "wrong-password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("token", response.data)

    def test_token_authentication_can_get_map_area_list(self):
        own_area = MapArea.objects.create(
            name="Own Token Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            created_by=self.user,
        )

        response = self.client.get(
            self.area_url,
            **self.token_credentials(self.user),
        )
        area_ids = [area["id"] for area in response.data["areas"]]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(own_area.id, area_ids)

    def test_token_authentication_can_create_map_area(self):
        response = self.client.post(
            self.area_url,
            self.valid_payload,
            format="json",
            **self.token_credentials(self.user),
        )
        area = MapArea.objects.get(id=response.data["id"])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(area.created_by, self.user)
        self.assertGreater(GridCell.objects.filter(area=area).count(), 0)

    def test_token_authentication_keeps_created_by_view_restriction(self):
        other_area = MapArea.objects.create(
            name="Other Token Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            created_by=self.other_user,
        )
        detail_url = reverse("map-area-detail", kwargs={"area_id": other_area.id})

        response = self.client.get(
            detail_url,
            **self.token_credentials(self.user),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_basic_authentication_still_works(self):
        own_area = MapArea.objects.create(
            name="Own Basic Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            created_by=self.user,
        )

        response = self.client.get(
            self.area_url,
            **self.basic_credentials("testuser", "test-password"),
        )
        area_ids = [area["id"] for area in response.data["areas"]]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(own_area.id, area_ids)


class MapAreaCreateViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="testuser",
            password="test-password",
        )
        self.staff_user = get_user_model().objects.create_user(
            username="staffuser",
            password="test-password",
            is_staff=True,
        )
        self.client = APIClient()
        self.url = reverse("map-area-list-create")
        self.valid_payload = {
            "name": "Center API Area",
            "description": "center based api",
            "center_lat": 35.695,
            "center_lng": 139.795,
            "grid_size_meters": 500,
            "rows": 6,
            "cols": 8,
            "source": "manual",
        }

    def center_payload(self):
        return self.valid_payload.copy()

    def legacy_payload(self):
        return {
            "name": "Legacy Area",
            "description": "legacy area",
            "north": 35.7,
            "south": 35.6,
            "east": 139.8,
            "west": 139.7,
            "grid_size_meters": 500,
            "source": "manual",
        }

    def test_authenticated_user_can_create_map_area(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, self.valid_payload, format="json")
        area = MapArea.objects.get(id=response.data["id"])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Center API Area")
        self.assertEqual(response.data["description"], "center based api")
        self.assertIn("north", response.data)
        self.assertIn("south", response.data)
        self.assertIn("east", response.data)
        self.assertIn("west", response.data)
        self.assertNotIn("center_lat", response.data)
        self.assertNotIn("center_lng", response.data)
        self.assertNotIn("rows", response.data)
        self.assertNotIn("cols", response.data)
        self.assertEqual(response.data["grid_size_meters"], 500)
        self.assertEqual(response.data["region_feature_level"], 0)
        self.assertEqual(response.data["initial_score_mode"], "manual")
        self.assertEqual(response.data["source"], "manual")
        self.assertEqual(response.data["created_by"], self.user.id)
        self.assertIn("created_at", response.data)
        self.assertIn("updated_at", response.data)
        self.assertEqual(area.created_by, self.user)
        self.assertEqual(area.region_feature_level, 0)
        self.assertEqual(area.initial_score_mode, MapArea.InitialScoreMode.MANUAL)
        self.assertEqual(GridCell.objects.filter(area=area).count(), 48)

    def test_authenticated_user_can_create_center_based_map_area(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, self.center_payload(), format="json")
        area = MapArea.objects.get(id=response.data["id"])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("north", response.data)
        self.assertIn("south", response.data)
        self.assertIn("east", response.data)
        self.assertIn("west", response.data)
        self.assertNotIn("center_lat", response.data)
        self.assertNotIn("center_lng", response.data)
        self.assertNotIn("rows", response.data)
        self.assertNotIn("cols", response.data)
        self.assertEqual(area.created_by, self.user)

    def test_center_based_map_area_generates_rows_times_cols_grid_cells(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, self.center_payload(), format="json")
        area = MapArea.objects.get(id=response.data["id"])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(GridCell.objects.filter(area=area).count(), 48)

    def test_create_map_area_with_region_feature_level_sets_grid_initial_scores(self):
        self.client.force_authenticate(user=self.user)
        payload = {**self.center_payload(), "region_feature_level": 3}

        response = self.client.post(self.url, payload, format="json")
        area = MapArea.objects.get(id=response.data["id"])
        grids = GridCell.objects.filter(area=area)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["region_feature_level"], 3)
        self.assertEqual(area.region_feature_level, 3)
        self.assertEqual(grids.count(), 48)
        self.assertTrue(grids.filter(initial_score=3).exists())
        self.assertEqual(grids.exclude(initial_score=3).count(), 0)
        self.assertEqual(grids.exclude(calculated_score=3).count(), 0)

    @patch("maps.views.build_feature_summaries_for_map_area_from_overpass")
    def test_create_map_area_with_manual_initial_score_mode(self, mock_overpass):
        self.client.force_authenticate(user=self.user)
        payload = {
            **self.center_payload(),
            "region_feature_level": 2,
            "initial_score_mode": "manual",
        }

        response = self.client.post(self.url, payload, format="json")
        area = MapArea.objects.get(id=response.data["id"])
        grids = GridCell.objects.filter(area=area)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["initial_score_mode"], "manual")
        self.assertEqual(area.initial_score_mode, MapArea.InitialScoreMode.MANUAL)
        mock_overpass.assert_not_called()
        self.assertEqual(grids.exclude(initial_score=2).count(), 0)
        self.assertEqual(grids.exclude(calculated_score=2).count(), 0)

    @patch("maps.views.build_feature_summaries_for_map_area_from_overpass")
    def test_create_map_area_with_auto_initial_score_mode_uses_overpass_summary(
        self,
        mock_overpass,
    ):
        self.client.force_authenticate(user=self.user)
        feature_summary = {
            "building_count": 20,
            "road_count": 10,
            "has_park": True,
            "has_river": True,
            "is_coastal": True,
            "water_coverage_ratio": 0.1,
            "park_coverage_ratio": 0.3,
            "river_coverage_ratio": 0.2,
            "surface_railway_count": 1,
            "railway_station_count": 1,
        }
        second_feature_summary = {
            "road_count": 5,
            "forest_coverage_ratio": 0.5,
            "underground_railway_count": 1,
            "unknown_station_count": 1,
            "motorway_count": 1,
        }
        expected_score = calculate_initial_score_from_feature_summary(feature_summary)
        second_expected_score = calculate_initial_score_from_feature_summary(
            second_feature_summary
        )
        expected_scores = [expected_score, second_expected_score]
        mock_overpass.return_value = {
            (0, 0): feature_summary,
            (1, 0): second_feature_summary,
        }
        payload = {
            **self.center_payload(),
            "region_feature_level": 2,
            "initial_score_mode": "auto",
        }

        with self.assertLogs("maps.views", level="INFO") as logs:
            response = self.client.post(self.url, payload, format="json")
        area = MapArea.objects.get(id=response.data["id"])
        auto_grid = GridCell.objects.get(area=area, row_index=0, col_index=0)
        fallback_grid = GridCell.objects.get(area=area, row_index=0, col_index=1)
        call_args = mock_overpass.call_args
        log_output = "\n".join(logs.output)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["initial_score_mode"], "auto")
        self.assertEqual(area.initial_score_mode, MapArea.InitialScoreMode.AUTO)
        mock_overpass.assert_called_once()
        self.assertEqual(call_args.args[0], area)
        self.assertEqual(call_args.kwargs["rows"], 6)
        self.assertEqual(call_args.kwargs["cols"], 8)
        self.assertGreater(call_args.kwargs["lat_step"], 0)
        self.assertGreater(call_args.kwargs["lng_step"], 0)
        self.assertEqual(auto_grid.initial_score, expected_score)
        self.assertEqual(auto_grid.calculated_score, expected_score)
        self.assertEqual(fallback_grid.initial_score, 2)
        self.assertEqual(fallback_grid.calculated_score, 2)
        self.assertIn("Overpass auto initial score succeeded", log_output)
        self.assertIn(f"area_id={area.id}", log_output)
        self.assertIn(f"user_id={self.user.id}", log_output)
        self.assertIn("initial_score_mode=auto", log_output)
        self.assertIn("Overpass auto feature summary", log_output)
        self.assertIn("summary_count=2", log_output)
        self.assertIn("building_cells=1", log_output)
        self.assertIn("road_cells=2", log_output)
        self.assertIn("park_cells=1", log_output)
        self.assertIn("river_cells=1", log_output)
        self.assertIn("coastal_cells=1", log_output)
        self.assertIn("water_cells=1", log_output)
        self.assertIn("forest_cells=1", log_output)
        self.assertIn(f"score_min={min(expected_scores):.2f}", log_output)
        self.assertIn(f"score_max={max(expected_scores):.2f}", log_output)
        self.assertIn(
            f"score_avg={sum(expected_scores) / len(expected_scores):.2f}",
            log_output,
        )
        self.assertIn("Overpass auto score breakdown summary", log_output)
        self.assertIn("base_score_avg=", log_output)
        self.assertIn("base_score_max=", log_output)
        self.assertIn("diversity_bonus_avg=", log_output)
        self.assertIn("diversity_bonus_max=", log_output)
        self.assertIn("context_bonus_avg=", log_output)
        self.assertIn("context_bonus_max=", log_output)
        self.assertIn("penalty_avg=", log_output)
        self.assertIn("penalty_max=", log_output)
        self.assertIn("raw_score_avg=", log_output)
        self.assertIn("raw_score_max=", log_output)
        self.assertIn("clamped_score_avg=", log_output)
        self.assertIn("clamped_score_max=", log_output)
        self.assertIn(
            f"max_score_cells={sum(score >= 3.0 for score in expected_scores)}",
            log_output,
        )
        self.assertIn("building_base_cells=1", log_output)
        self.assertIn("road_base_cells=0", log_output)
        self.assertIn("road_scored_cells=0", log_output)
        self.assertIn("park_context_cells=1", log_output)
        self.assertIn("river_context_cells=1", log_output)
        self.assertIn("forest_context_cells=0", log_output)
        self.assertIn("coastal_context_cells=1", log_output)
        self.assertIn("water_penalty_cells=0", log_output)
        self.assertIn("unreachable_water_penalty_cells=0", log_output)
        self.assertIn("waterfront_context_cells=1", log_output)
        self.assertIn("forest_penalty_cells=0", log_output)
        self.assertIn("empty_cell_penalty_cells=0", log_output)
        self.assertIn("surface_railway_context_cells=1", log_output)
        self.assertIn("surface_railway_context_bonus_avg=", log_output)
        self.assertIn("surface_railway_context_bonus_max=", log_output)
        self.assertIn("surface_station_context_cells=1", log_output)
        self.assertIn("surface_station_context_bonus_avg=", log_output)
        self.assertIn("surface_station_context_bonus_max=", log_output)
        self.assertIn("subway_station_context_cells=0", log_output)
        self.assertIn("subway_station_context_bonus_avg=", log_output)
        self.assertIn("subway_station_context_bonus_max=", log_output)
        self.assertIn("public_transport_station_context_cells=0", log_output)
        self.assertIn("public_transport_station_context_bonus_avg=", log_output)
        self.assertIn("public_transport_station_context_bonus_max=", log_output)
        self.assertIn("station_count_avg=0.50", log_output)
        self.assertIn("station_count_max=1.00", log_output)
        self.assertIn("station_density_cluster_count_avg=", log_output)
        self.assertIn("station_density_cluster_count_max=", log_output)
        self.assertIn("dense_station_density_cluster_count_max=", log_output)
        self.assertIn("dense_station_cluster_context_cells=0", log_output)
        self.assertIn("major_station_cluster_context_cells=0", log_output)
        self.assertIn("station_density_bonus_avg=", log_output)
        self.assertIn("station_density_bonus_max=", log_output)
        self.assertIn("landmark_context_cells=0", log_output)
        self.assertIn("landmark_context_bonus_avg=", log_output)
        self.assertIn("landmark_context_bonus_max=", log_output)
        self.assertIn("castle_proximity_context_cells=0", log_output)
        self.assertIn("castle_near_context_cells=0", log_output)
        self.assertIn("castle_mid_context_cells=0", log_output)
        self.assertIn("castle_far_context_cells=0", log_output)
        self.assertIn("castle_proximity_bonus_avg=", log_output)
        self.assertIn("castle_proximity_bonus_max=", log_output)
        self.assertIn("castle_proximity_skipped_castle_cells=0", log_output)
        self.assertIn("station_proximity_context_cells=0", log_output)
        self.assertIn("station_proximity_near_context_cells=0", log_output)
        self.assertIn("station_proximity_mid_context_cells=0", log_output)
        self.assertIn("station_proximity_bonus_avg=", log_output)
        self.assertIn("station_proximity_bonus_max=", log_output)
        self.assertIn("park_waterfront_combo_context_cells=", log_output)
        self.assertIn("park_waterfront_combo_bonus_avg=", log_output)
        self.assertIn("park_waterfront_combo_bonus_max=", log_output)
        self.assertIn("high_context_3_context_cells=", log_output)
        self.assertIn("high_context_4_context_cells=", log_output)
        self.assertIn("high_context_5_context_cells=", log_output)
        self.assertIn("high_context_bonus_avg=", log_output)
        self.assertIn("high_context_bonus_max=", log_output)
        self.assertIn("motorway_context_cells=1", log_output)
        self.assertIn("motorway_context_bonus_avg=", log_output)
        self.assertIn("motorway_context_bonus_max=", log_output)
        self.assertIn("trunk_context_cells=0", log_output)
        self.assertIn("trunk_context_bonus_avg=", log_output)
        self.assertIn("trunk_context_bonus_max=", log_output)
        self.assertIn("Overpass auto context candidate summary", log_output)
        self.assertIn("park_waterfront_combo_cells=", log_output)
        self.assertIn("high_context_3_cells=", log_output)
        self.assertIn("high_context_5_cells=", log_output)
        self.assertIn("context_candidate_count_avg=", log_output)
        self.assertIn("context_candidate_count_max=", log_output)
        self.assertIn("station_proximity_features=0", log_output)
        self.assertIn("station_proximity_near_cells=0", log_output)
        self.assertIn("station_proximity_mid_cells=0", log_output)
        self.assertIn("station_proximity_cells=0", log_output)
        self.assertIn("station_proximity_station_cells=0", log_output)
        self.assertIn("station_proximity_non_station_cells=0", log_output)
        self.assertIn("station_proximity_min_distance_m=0.00", log_output)
        self.assertIn("station_proximity_avg_distance_m=0.00", log_output)
        self.assertIn("station_proximity_max_distance_m=0.00", log_output)
        self.assertIn("Overpass auto scored river summary", log_output)
        self.assertIn("scored_river_cells=1", log_output)
        self.assertIn("river_coverage_cells=1", log_output)
        self.assertIn("river_coverage_avg=0.2000", log_output)
        self.assertIn("river_coverage_max=0.2000", log_output)
        self.assertIn("Overpass auto scored natural coverage summary", log_output)
        self.assertIn("park_cells=1", log_output)
        self.assertIn("park_coverage_cells=1", log_output)
        self.assertIn("park_coverage_avg=0.3000", log_output)
        self.assertIn("park_coverage_max=0.3000", log_output)
        self.assertIn("water_coverage_cells=1", log_output)
        self.assertIn("water_coverage_avg=0.1000", log_output)
        self.assertIn("water_coverage_max=0.1000", log_output)
        self.assertIn("forest_coverage_cells=1", log_output)
        self.assertIn("scored_forest_cells=1", log_output)
        self.assertIn("forest_coverage_avg=0.5000", log_output)
        self.assertIn("forest_coverage_max=0.5000", log_output)
        self.assertIn("Overpass auto waterway summary", log_output)
        self.assertIn("waterway_river_features=0", log_output)
        self.assertIn("waterway_stream_features=0", log_output)
        self.assertIn("waterway_canal_features=0", log_output)
        self.assertIn("waterway_unknown_features=0", log_output)
        self.assertIn("waterway_river_cells=0", log_output)
        self.assertIn("waterway_stream_cells=0", log_output)
        self.assertIn("waterway_canal_cells=0", log_output)
        self.assertIn("waterway_unknown_cells=0", log_output)
        self.assertIn("Overpass auto railway summary", log_output)
        self.assertIn("railway_features=0", log_output)
        self.assertIn("surface_railway_features=0", log_output)
        self.assertIn("underground_railway_features=0", log_output)
        self.assertIn("unknown_railway_features=0", log_output)
        self.assertIn("railway_cells=0", log_output)
        self.assertIn("surface_railway_cells=0", log_output)
        self.assertIn("underground_railway_cells=0", log_output)
        self.assertIn("unknown_railway_cells=0", log_output)
        self.assertIn("Overpass auto station summary", log_output)
        self.assertIn("station_features=0", log_output)
        self.assertIn("railway_station_features=0", log_output)
        self.assertIn("railway_halt_features=0", log_output)
        self.assertIn("subway_station_features=0", log_output)
        self.assertIn("bus_station_features=0", log_output)
        self.assertIn("public_transport_station_features=0", log_output)
        self.assertIn("unknown_station_features=0", log_output)
        self.assertIn("station_cells=0", log_output)
        self.assertIn("railway_station_cells=0", log_output)
        self.assertIn("railway_halt_cells=0", log_output)
        self.assertIn("subway_station_cells=0", log_output)
        self.assertIn("bus_station_cells=0", log_output)
        self.assertIn("public_transport_station_cells=0", log_output)
        self.assertIn("station_cluster_cells=0", log_output)
        self.assertIn("dense_station_cluster_cells=0", log_output)
        self.assertIn("major_station_cluster_cells=0", log_output)
        self.assertIn("station_cluster_count_avg=0.00", log_output)
        self.assertIn("station_cluster_count_max=0", log_output)
        self.assertIn("dense_station_cluster_count_max=0", log_output)
        self.assertIn("major_station_cluster_count_max=0", log_output)
        self.assertIn("unknown_station_cells=0", log_output)
        self.assertIn("Overpass auto landmark summary", log_output)
        self.assertIn("landmark_features=0", log_output)
        self.assertIn("landmark_cells=0", log_output)
        self.assertIn("tourism_attraction_features=0", log_output)
        self.assertIn("tourism_attraction_cells=0", log_output)
        self.assertIn("tourism_museum_features=0", log_output)
        self.assertIn("tourism_museum_cells=0", log_output)
        self.assertIn("tourism_gallery_features=0", log_output)
        self.assertIn("tourism_gallery_cells=0", log_output)
        self.assertIn("tourism_viewpoint_features=0", log_output)
        self.assertIn("tourism_viewpoint_cells=0", log_output)
        self.assertIn("historic_castle_features=0", log_output)
        self.assertIn("historic_castle_cells=0", log_output)
        self.assertIn("historic_monument_features=0", log_output)
        self.assertIn("historic_monument_cells=0", log_output)
        self.assertIn("historic_memorial_features=0", log_output)
        self.assertIn("historic_memorial_cells=0", log_output)
        self.assertIn("historic_ruins_features=0", log_output)
        self.assertIn("historic_ruins_cells=0", log_output)
        self.assertIn("historic_archaeological_site_features=0", log_output)
        self.assertIn("historic_archaeological_site_cells=0", log_output)
        self.assertIn("unknown_landmark_features=0", log_output)
        self.assertIn("unknown_landmark_cells=0", log_output)
        self.assertIn("Overpass auto castle proximity summary", log_output)
        self.assertIn("castle_features=0", log_output)
        self.assertIn("castle_near_cells=0", log_output)
        self.assertIn("castle_mid_cells=0", log_output)
        self.assertIn("castle_far_cells=0", log_output)
        self.assertIn("castle_proximity_cells=0", log_output)
        self.assertIn("castle_min_distance_m=0.00", log_output)
        self.assertIn("castle_avg_distance_m=0.00", log_output)
        self.assertIn("castle_max_distance_m=0.00", log_output)
        self.assertIn("Overpass auto expressway summary", log_output)
        self.assertIn("expressway_features=0", log_output)
        self.assertIn("motorway_features=0", log_output)
        self.assertIn("motorway_link_features=0", log_output)
        self.assertIn("trunk_features=0", log_output)
        self.assertIn("trunk_link_features=0", log_output)
        self.assertIn("unknown_expressway_features=0", log_output)
        self.assertIn("expressway_cells=0", log_output)
        self.assertIn("motorway_cells=0", log_output)
        self.assertIn("motorway_link_cells=0", log_output)
        self.assertIn("trunk_cells=0", log_output)
        self.assertIn("trunk_link_cells=0", log_output)
        self.assertIn("unknown_expressway_cells=0", log_output)
        self.assertIn("Overpass auto expressway bounds summary", log_output)
        self.assertIn("expressway_avg_overlap=0.0000", log_output)
        self.assertIn("expressway_max_overlap=0.0000", log_output)
        self.assertIn("expressway_large_bounds_features=0", log_output)
        self.assertIn("expressway_large_bounds_cells=0", log_output)
        self.assertIn("motorway_avg_overlap=0.0000", log_output)
        self.assertIn("motorway_max_overlap=0.0000", log_output)
        self.assertIn("motorway_link_avg_overlap=0.0000", log_output)
        self.assertIn("motorway_link_max_overlap=0.0000", log_output)
        self.assertIn("trunk_avg_overlap=0.0000", log_output)
        self.assertIn("trunk_max_overlap=0.0000", log_output)
        self.assertIn("trunk_link_avg_overlap=0.0000", log_output)
        self.assertIn("trunk_link_max_overlap=0.0000", log_output)
        self.assertIn("unknown_expressway_avg_overlap=0.0000", log_output)
        self.assertIn("unknown_expressway_max_overlap=0.0000", log_output)
        self.assertIn("Overpass auto effective expressway summary", log_output)
        self.assertIn("effective_expressway_features=0", log_output)
        self.assertIn("effective_expressway_cells=0", log_output)
        self.assertIn("effective_expressway_avg_overlap=0.0000", log_output)
        self.assertIn("effective_expressway_max_overlap=0.0000", log_output)
        self.assertIn("effective_motorway_features=0", log_output)
        self.assertIn("effective_motorway_cells=0", log_output)
        self.assertIn("effective_motorway_avg_overlap=0.0000", log_output)
        self.assertIn("effective_trunk_features=0", log_output)
        self.assertIn("effective_trunk_cells=0", log_output)
        self.assertIn("effective_trunk_avg_overlap=0.0000", log_output)
        self.assertIn("filtered_expressway_large_bounds_features=0", log_output)
        self.assertIn("filtered_expressway_large_bounds_cells=0", log_output)
        self.assertIn("Overpass auto waterway river bounds summary", log_output)
        self.assertIn("waterway_river_bounds_features=0", log_output)
        self.assertIn("waterway_river_bounds_intersecting_map_features=0", log_output)
        self.assertIn("waterway_river_bounds_covering_map_features=0", log_output)
        self.assertIn("waterway_river_bounds_large_area_features=0", log_output)
        self.assertIn("waterway_river_bounds_filtered_features=0", log_output)
        self.assertIn("waterway_river_bounds_filtered_cells=0", log_output)
        self.assertIn(
            "waterway_river_bounds_max_area_ratio_to_map=0.0000",
            log_output,
        )
        self.assertIn(
            "waterway_river_bounds_max_height_ratio_to_map=0.0000",
            log_output,
        )
        self.assertIn(
            "waterway_river_bounds_max_width_ratio_to_map=0.0000",
            log_output,
        )
        self.assertNotIn("using fallback", log_output)

    @patch("maps.views.build_feature_summaries_for_map_area_from_overpass")
    def test_create_map_area_with_auto_initial_score_mode_falls_back_when_overpass_fails(
        self,
        mock_overpass,
    ):
        self.client.force_authenticate(user=self.user)
        mock_overpass.side_effect = ValueError("Overpass取得に失敗しました。")
        payload = {
            **self.center_payload(),
            "region_feature_level": 2,
            "initial_score_mode": "auto",
        }

        with self.assertLogs("maps.views", level="WARNING") as logs:
            response = self.client.post(self.url, payload, format="json")
        area = MapArea.objects.get(id=response.data["id"])
        grids = GridCell.objects.filter(area=area)
        log_output = "\n".join(logs.output)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["initial_score_mode"], "auto")
        self.assertEqual(area.initial_score_mode, MapArea.InitialScoreMode.AUTO)
        mock_overpass.assert_called_once()
        self.assertEqual(grids.count(), 48)
        self.assertEqual(grids.exclude(initial_score=2).count(), 0)
        self.assertEqual(grids.exclude(calculated_score=2).count(), 0)
        self.assertIn("Overpass auto initial score failed; using fallback", log_output)
        self.assertIn(f"area_id={area.id}", log_output)
        self.assertIn(f"user_id={self.user.id}", log_output)
        self.assertIn("Overpass取得に失敗しました。", log_output)

    def test_create_map_area_without_region_feature_level_uses_zero(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, self.center_payload(), format="json")
        area = MapArea.objects.get(id=response.data["id"])
        grids = GridCell.objects.filter(area=area)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["region_feature_level"], 0)
        self.assertEqual(area.region_feature_level, 0)
        self.assertEqual(grids.exclude(initial_score=0).count(), 0)
        self.assertEqual(grids.exclude(calculated_score=0).count(), 0)

    def test_create_map_area_with_invalid_region_feature_level_returns_400(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {**self.center_payload(), "region_feature_level": 4},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("region_feature_level", response.data)
        self.assertEqual(MapArea.objects.count(), 0)
        self.assertEqual(GridCell.objects.count(), 0)

    def test_create_map_area_with_invalid_initial_score_mode_returns_400(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {**self.center_payload(), "initial_score_mode": "invalid"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("initial_score_mode", response.data)
        self.assertEqual(MapArea.objects.count(), 0)
        self.assertEqual(GridCell.objects.count(), 0)

    def test_center_based_grid_cells_align_to_area_bounds(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, self.center_payload(), format="json")
        area = MapArea.objects.get(id=response.data["id"])
        last_row_grid = GridCell.objects.get(area=area, row_index=5, col_index=0)
        last_col_grid = GridCell.objects.get(area=area, row_index=0, col_index=7)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertAlmostEqual(last_row_grid.south, area.south)
        self.assertAlmostEqual(last_col_grid.east, area.east)

    def test_center_based_created_map_area_grid_cells_can_be_listed_immediately(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, self.center_payload(), format="json")
        area = MapArea.objects.get(id=response.data["id"])
        grid_list_url = reverse("grid-cell-list", kwargs={"area_id": area.id})
        grid_response = self.client.get(grid_list_url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(grid_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(grid_response.data["grids"]), 48)

    def test_general_user_cannot_create_center_based_area_over_cell_count_limit(self):
        self.client.force_authenticate(user=self.user)
        payload = {**self.center_payload(), "rows": 20, "cols": 26}

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "一般ユーザーは rows * cols が 500 を超える MapArea を作成できません。",
        )
        self.assertEqual(MapArea.objects.count(), 0)
        self.assertEqual(GridCell.objects.count(), 0)

    def test_general_user_cannot_create_center_based_area_over_height_limit(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            **self.center_payload(),
            "grid_size_meters": 1000,
            "rows": 31,
            "cols": 10,
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "一般ユーザーは南北方向が 30000m を超える MapArea を作成できません。",
        )
        self.assertEqual(MapArea.objects.count(), 0)
        self.assertEqual(GridCell.objects.count(), 0)

    def test_general_user_cannot_create_center_based_area_over_width_limit(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            **self.center_payload(),
            "grid_size_meters": 1000,
            "rows": 10,
            "cols": 31,
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "一般ユーザーは東西方向が 30000m を超える MapArea を作成できません。",
        )
        self.assertEqual(MapArea.objects.count(), 0)
        self.assertEqual(GridCell.objects.count(), 0)

    def test_staff_user_can_create_center_based_area_over_general_limits(self):
        self.client.force_authenticate(user=self.staff_user)
        payload = {
            **self.center_payload(),
            "grid_size_meters": 1000,
            "rows": 31,
            "cols": 31,
        }

        response = self.client.post(self.url, payload, format="json")
        area = MapArea.objects.get(id=response.data["id"])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(area.created_by, self.staff_user)
        self.assertEqual(GridCell.objects.filter(area=area).count(), 961)

    def test_authenticated_user_create_map_area_generates_grid_cells(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, self.valid_payload, format="json")
        area = MapArea.objects.get(id=response.data["id"])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertGreater(GridCell.objects.filter(area=area).count(), 0)

    def test_legacy_bounds_input_returns_400(self):
        self.client.force_authenticate(user=self.user)
        payload = self.legacy_payload()

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("center_lat/center_lng/grid_size_meters/rows/cols", str(response.data))
        self.assertEqual(MapArea.objects.count(), 0)
        self.assertEqual(GridCell.objects.count(), 0)

    def test_missing_center_lat_returns_400(
        self,
    ):
        self.client.force_authenticate(user=self.user)
        payload = self.valid_payload.copy()
        payload.pop("center_lat")

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("center_lat/center_lng/grid_size_meters/rows/cols", str(response.data))
        self.assertEqual(MapArea.objects.count(), 0)
        self.assertEqual(GridCell.objects.count(), 0)

    def test_missing_center_lng_returns_400(self):
        self.client.force_authenticate(user=self.user)
        payload = self.valid_payload.copy()
        payload.pop("center_lng")

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("center_lat/center_lng/grid_size_meters/rows/cols", str(response.data))
        self.assertEqual(MapArea.objects.count(), 0)
        self.assertEqual(GridCell.objects.count(), 0)

    def test_missing_rows_returns_400(self):
        self.client.force_authenticate(user=self.user)
        payload = self.valid_payload.copy()
        payload.pop("rows")

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("center_lat/center_lng/grid_size_meters/rows/cols", str(response.data))
        self.assertEqual(MapArea.objects.count(), 0)
        self.assertEqual(GridCell.objects.count(), 0)

    def test_missing_cols_returns_400(self):
        self.client.force_authenticate(user=self.user)
        payload = self.valid_payload.copy()
        payload.pop("cols")

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("center_lat/center_lng/grid_size_meters/rows/cols", str(response.data))
        self.assertEqual(MapArea.objects.count(), 0)
        self.assertEqual(GridCell.objects.count(), 0)

    def test_generated_grid_cells_are_linked_to_created_map_area(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, self.valid_payload, format="json")
        area = MapArea.objects.get(id=response.data["id"])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(GridCell.objects.filter(area=area).exists())
        self.assertEqual(
            GridCell.objects.exclude(area=area).count(),
            0,
        )

    def test_created_map_area_grid_cells_can_be_listed_immediately(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, self.valid_payload, format="json")
        area = MapArea.objects.get(id=response.data["id"])
        grid_list_url = reverse("grid-cell-list", kwargs={"area_id": area.id})
        grid_response = self.client.get(grid_list_url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(grid_response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(grid_response.data["grids"]), 0)

    def test_create_map_area_then_generate_grid_cells_again_returns_400(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, self.valid_payload, format="json")
        area = MapArea.objects.get(id=response.data["id"])
        generate_url = reverse("grid-cell-generate", kwargs={"area_id": area.id})
        generate_response = self.client.post(generate_url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            generate_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            generate_response.data["detail"],
            "この MapArea には既に GridCell があります。",
        )

    def test_grid_generation_failure_rolls_back_map_area_creation(self):
        self.client.force_authenticate(user=self.user)

        with patch(
            "maps.views.generate_grid_cells_for_area",
            side_effect=ValueError("GridCell 生成に失敗しました。"),
        ):
            response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "GridCell 生成に失敗しました。",
        )
        self.assertEqual(MapArea.objects.count(), 0)
        self.assertEqual(GridCell.objects.count(), 0)

    def test_unauthenticated_user_cannot_create_map_area(self):
        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(MapArea.objects.count(), 0)
        self.assertEqual(GridCell.objects.count(), 0)

    def test_blank_name_returns_400(self):
        self.client.force_authenticate(user=self.user)
        payload = {**self.valid_payload, "name": ""}

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)
        self.assertEqual(MapArea.objects.count(), 0)
        self.assertEqual(GridCell.objects.count(), 0)

    def test_grid_size_meters_less_than_or_equal_to_zero_returns_400(self):
        self.client.force_authenticate(user=self.user)
        payload = {**self.valid_payload, "grid_size_meters": 0}

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("grid_size_meters", response.data)
        self.assertEqual(MapArea.objects.count(), 0)
        self.assertEqual(GridCell.objects.count(), 0)

    def test_missing_required_field_returns_400(self):
        self.client.force_authenticate(user=self.user)
        payload = self.valid_payload.copy()
        payload.pop("center_lat")

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", response.data)
        self.assertEqual(MapArea.objects.count(), 0)
        self.assertEqual(GridCell.objects.count(), 0)

    def test_request_created_by_is_ignored(self):
        other_user = get_user_model().objects.create_user(
            username="otheruser",
            password="test-password",
        )
        self.client.force_authenticate(user=self.user)
        payload = {**self.valid_payload, "created_by": other_user.id}

        response = self.client.post(self.url, payload, format="json")
        area = MapArea.objects.get(id=response.data["id"])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created_by"], self.user.id)
        self.assertEqual(area.created_by, self.user)


class MapAreaListViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="testuser",
            password="test-password",
        )
        self.client = APIClient()
        self.url = reverse("map-area-list-create")

    def test_authenticated_user_can_get_map_area_list(self):
        area_b = MapArea.objects.create(
            name="B Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            source="manual",
            created_by=self.user,
        )
        area_a = MapArea.objects.create(
            name="A Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            source="manual",
            created_by=self.user,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("areas", response.data)
        self.assertEqual(len(response.data["areas"]), 2)
        self.assertEqual(response.data["areas"][0]["id"], area_a.id)
        self.assertEqual(response.data["areas"][1]["id"], area_b.id)
        self.assertEqual(response.data["areas"][0]["name"], "A Area")
        self.assertEqual(response.data["areas"][0]["created_by"], self.user.id)
        self.assertEqual(response.data["areas"][0]["created_by_username"], self.user.username)
        self.assertEqual(response.data["areas"][0]["initial_score_mode"], "manual")
        self.assertEqual(response.data["areas"][0]["visibility"], "private")
        self.assertEqual(response.data["areas"][0]["display_type"], "メモグリッド")
        self.assertIs(response.data["areas"][0]["is_owner"], True)
        self.assertIn("created_at", response.data["areas"][0])
        self.assertIn("updated_at", response.data["areas"][0])

    def test_shared_map_area_is_included_in_list(self):
        owner = get_user_model().objects.create_user(
            username="owner",
            password="test-password",
        )
        shared_area = MapArea.objects.create(
            name="Shared Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            created_by=owner,
        )
        MapAreaShare.objects.create(area=shared_area, user=self.user)
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)
        area = response.data["areas"][0]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["areas"]), 1)
        self.assertEqual(area["id"], shared_area.id)
        self.assertEqual(area["visibility"], "shared")
        self.assertEqual(area["display_type"], "共有メモグリッド")
        self.assertIs(area["is_owner"], False)
        self.assertEqual(area["created_by_username"], owner.username)

    def test_other_users_map_areas_are_not_included_in_list(self):
        other_user = get_user_model().objects.create_user(
            username="otheruser",
            password="test-password",
        )
        own_area = MapArea.objects.create(
            name="Own Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            created_by=self.user,
        )
        other_area = MapArea.objects.create(
            name="Other User Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=other_user,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)
        area_ids = [area["id"] for area in response.data["areas"]]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(own_area.id, area_ids)
        self.assertNotIn(other_area.id, area_ids)

    def test_unshared_other_users_map_areas_are_not_included_when_shared_exists(self):
        owner = get_user_model().objects.create_user(
            username="owner",
            password="test-password",
        )
        shared_area = MapArea.objects.create(
            name="Shared Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            created_by=owner,
        )
        unshared_area = MapArea.objects.create(
            name="Unshared Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=owner,
        )
        MapAreaShare.objects.create(area=shared_area, user=self.user)
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)
        area_ids = [area["id"] for area in response.data["areas"]]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(shared_area.id, area_ids)
        self.assertNotIn(unshared_area.id, area_ids)

    def test_map_areas_without_creator_are_not_included_in_list(self):
        own_area = MapArea.objects.create(
            name="Own Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            created_by=self.user,
        )
        no_creator_area = MapArea.objects.create(
            name="No Creator Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=None,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)
        area_ids = [area["id"] for area in response.data["areas"]]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(own_area.id, area_ids)
        self.assertNotIn(no_creator_area.id, area_ids)

    def test_list_returns_empty_when_user_has_no_own_map_areas(self):
        other_user = get_user_model().objects.create_user(
            username="otheruser",
            password="test-password",
        )
        MapArea.objects.create(
            name="Other User Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            created_by=other_user,
        )
        MapArea.objects.create(
            name="No Creator Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=None,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["areas"], [])

    def test_own_shared_map_area_is_not_duplicated_and_owner_status_wins(self):
        own_area = MapArea.objects.create(
            name="Own Shared Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            created_by=self.user,
        )
        MapAreaShare.objects.create(area=own_area, user=self.user)
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)
        areas = response.data["areas"]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(areas), 1)
        self.assertEqual(areas[0]["id"], own_area.id)
        self.assertEqual(areas[0]["visibility"], "private")
        self.assertEqual(areas[0]["display_type"], "メモグリッド")
        self.assertIs(areas[0]["is_owner"], True)
        self.assertEqual(areas[0]["created_by_username"], self.user.username)

    def test_area_without_map_areas_returns_empty_list(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["areas"], [])

    def test_unauthenticated_user_cannot_get_map_area_list(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MapAreaDetailViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="testuser",
            password="test-password",
        )
        self.client = APIClient()
        self.area = MapArea.objects.create(
            name="Tokyo Station Area",
            description="manual area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            source="manual",
            created_by=self.user,
        )
        self.url = reverse("map-area-detail", kwargs={"area_id": self.area.id})

    def test_authenticated_user_can_get_map_area_detail(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.area.id)
        self.assertEqual(response.data["name"], "Tokyo Station Area")
        self.assertEqual(response.data["description"], "manual area")
        self.assertEqual(response.data["north"], 35.7)
        self.assertEqual(response.data["south"], 35.6)
        self.assertEqual(response.data["east"], 139.8)
        self.assertEqual(response.data["west"], 139.7)
        self.assertEqual(response.data["grid_size_meters"], 500)
        self.assertEqual(response.data["initial_score_mode"], "manual")
        self.assertEqual(response.data["source"], "manual")
        self.assertEqual(response.data["created_by"], self.user.id)
        self.assertIn("created_at", response.data)
        self.assertIn("updated_at", response.data)

    def test_unauthenticated_user_cannot_get_map_area_detail(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unknown_area_id_returns_404(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("map-area-detail", kwargs={"area_id": 999999})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_users_map_area_detail_returns_404(self):
        other_user = get_user_model().objects.create_user(
            username="otheruser",
            password="test-password",
        )
        other_area = MapArea.objects.create(
            name="Other User Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=other_user,
        )
        self.client.force_authenticate(user=self.user)
        url = reverse("map-area-detail", kwargs={"area_id": other_area.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_shared_map_area_detail_can_be_viewed(self):
        owner = get_user_model().objects.create_user(
            username="owner",
            password="test-password",
        )
        shared_area = MapArea.objects.create(
            name="Shared Area",
            description="shared memo grid",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=owner,
        )
        MapAreaShare.objects.create(area=shared_area, user=self.user)
        self.client.force_authenticate(user=self.user)
        url = reverse("map-area-detail", kwargs={"area_id": shared_area.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], shared_area.id)
        self.assertEqual(response.data["name"], "Shared Area")
        self.assertEqual(response.data["description"], "shared memo grid")
        self.assertEqual(response.data["created_by"], owner.id)

    def test_map_area_without_creator_detail_returns_404(self):
        no_creator_area = MapArea.objects.create(
            name="No Creator Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=None,
        )
        self.client.force_authenticate(user=self.user)
        url = reverse("map-area-detail", kwargs={"area_id": no_creator_area.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_shared_map_area_without_creator_detail_can_be_viewed(self):
        no_creator_area = MapArea.objects.create(
            name="Shared No Creator Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=None,
        )
        MapAreaShare.objects.create(area=no_creator_area, user=self.user)
        self.client.force_authenticate(user=self.user)
        url = reverse("map-area-detail", kwargs={"area_id": no_creator_area.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], no_creator_area.id)
        self.assertIsNone(response.data["created_by"])

    def test_owner_can_delete_map_area(self):
        shared_user = get_user_model().objects.create_user(
            username="shareduser",
            password="test-password",
        )
        grid = GridCell.objects.create(
            area=self.area,
            row_index=0,
            col_index=0,
            north=35.7,
            south=35.69,
            east=139.8,
            west=139.79,
            calculated_score=5,
        )
        GridRating.objects.create(grid=grid, user=self.user, score=8)
        MapAreaShare.objects.create(area=self.area, user=shared_user)
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(MapArea.objects.filter(id=self.area.id).exists())
        self.assertFalse(GridCell.objects.filter(id=grid.id).exists())
        self.assertFalse(GridRating.objects.filter(grid_id=grid.id).exists())
        self.assertFalse(MapAreaShare.objects.filter(area_id=self.area.id).exists())

    def test_unauthenticated_user_cannot_delete_map_area(self):
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(MapArea.objects.filter(id=self.area.id).exists())

    def test_unknown_area_id_delete_returns_404(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("map-area-detail", kwargs={"area_id": 999999})

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_user_cannot_delete_map_area(self):
        other_user = get_user_model().objects.create_user(
            username="otheruser",
            password="test-password",
        )
        self.client.force_authenticate(user=other_user)

        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(MapArea.objects.filter(id=self.area.id).exists())

    def test_shared_user_cannot_delete_map_area(self):
        shared_user = get_user_model().objects.create_user(
            username="shareduser",
            password="test-password",
        )
        MapAreaShare.objects.create(area=self.area, user=shared_user)
        self.client.force_authenticate(user=shared_user)

        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(MapArea.objects.filter(id=self.area.id).exists())

    def test_map_area_without_creator_delete_returns_404(self):
        no_creator_area = MapArea.objects.create(
            name="No Creator Delete Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=None,
        )
        self.client.force_authenticate(user=self.user)
        url = reverse("map-area-detail", kwargs={"area_id": no_creator_area.id})

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(MapArea.objects.filter(id=no_creator_area.id).exists())


class MapAreaShareManagementViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="owner",
            password="test-password",
        )
        self.shared_user = get_user_model().objects.create_user(
            username="shareduser",
            password="test-password",
        )
        self.other_user = get_user_model().objects.create_user(
            username="otheruser",
            password="test-password",
        )
        self.client = APIClient()
        self.area = MapArea.objects.create(
            name="Owner Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            created_by=self.owner,
        )
        self.grid = GridCell.objects.create(
            area=self.area,
            row_index=0,
            col_index=0,
            north=35.7,
            south=35.69,
            east=139.8,
            west=139.79,
            initial_score=3,
        )
        self.list_url = reverse(
            "map-area-share-list-create",
            kwargs={"area_id": self.area.id},
        )

    def test_owner_can_get_share_list(self):
        share = MapAreaShare.objects.create(
            area=self.area,
            user=self.shared_user,
        )
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["area"]["id"], self.area.id)
        self.assertEqual(response.data["area"]["name"], self.area.name)
        self.assertEqual(len(response.data["shares"]), 1)
        self.assertEqual(response.data["shares"][0]["id"], share.id)
        self.assertEqual(response.data["shares"][0]["area"], self.area.id)
        self.assertEqual(response.data["shares"][0]["user"]["id"], self.shared_user.id)
        self.assertEqual(
            response.data["shares"][0]["user"]["username"],
            self.shared_user.username,
        )
        self.assertNotIn("email", response.data["shares"][0]["user"])
        self.assertIn("created_at", response.data["shares"][0])

    def test_owner_gets_empty_share_list_when_no_shares_exist(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["shares"], [])

    def test_shared_user_cannot_get_share_list(self):
        MapAreaShare.objects.create(area=self.area, user=self.shared_user)
        self.client.force_authenticate(user=self.shared_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unshared_user_cannot_get_share_list(self):
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_user_cannot_get_share_list(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unknown_area_id_share_list_returns_404(self):
        self.client.force_authenticate(user=self.owner)
        url = reverse(
            "map-area-share-list-create",
            kwargs={"area_id": 999999},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_area_without_creator_share_list_returns_404(self):
        no_creator_area = MapArea.objects.create(
            name="No Creator Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            created_by=None,
        )
        self.client.force_authenticate(user=self.owner)
        url = reverse(
            "map-area-share-list-create",
            kwargs={"area_id": no_creator_area.id},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_add_share_by_username(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url,
            {"username": self.shared_user.username},
            format="json",
        )
        share = MapAreaShare.objects.get(area=self.area, user=self.shared_user)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["share"]["id"], share.id)
        self.assertEqual(response.data["share"]["area"], self.area.id)
        self.assertEqual(response.data["share"]["user"]["id"], self.shared_user.id)
        self.assertEqual(
            response.data["share"]["user"]["username"],
            self.shared_user.username,
        )
        self.assertNotIn("email", response.data["share"]["user"])

    def test_added_user_can_view_grid_and_rate_area(self):
        self.client.force_authenticate(user=self.owner)
        self.client.post(
            self.list_url,
            {"username": self.shared_user.username},
            format="json",
        )

        self.client.force_authenticate(user=self.shared_user)
        list_response = self.client.get(reverse("map-area-list-create"))
        detail_response = self.client.get(
            reverse("map-area-detail", kwargs={"area_id": self.area.id})
        )
        grids_response = self.client.get(
            reverse("grid-cell-list", kwargs={"area_id": self.area.id})
        )
        rating_response = self.client.post(
            reverse("grid-rating-create", kwargs={"grid_id": self.grid.id}),
            {"score": 7},
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["areas"][0]["id"], self.area.id)
        self.assertEqual(list_response.data["areas"][0]["visibility"], "shared")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(grids_response.status_code, status.HTTP_200_OK)
        self.assertEqual(rating_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            GridRating.objects.filter(grid=self.grid, user=self.shared_user).exists()
        )

    def test_unknown_username_cannot_be_shared(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url,
            {"username": "missing-user"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)
        self.assertFalse(MapAreaShare.objects.exists())

    def test_missing_username_cannot_be_shared(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(self.list_url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)
        self.assertFalse(MapAreaShare.objects.exists())

    def test_non_string_username_cannot_be_shared(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url,
            {"username": 123},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)
        self.assertFalse(MapAreaShare.objects.exists())

    def test_duplicate_share_returns_400(self):
        MapAreaShare.objects.create(area=self.area, user=self.shared_user)
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url,
            {"username": self.shared_user.username},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            MapAreaShare.objects.filter(area=self.area, user=self.shared_user).count(),
            1,
        )

    def test_owner_cannot_share_area_with_self(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.list_url,
            {"username": self.owner.username},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(MapAreaShare.objects.exists())

    def test_shared_user_cannot_add_share(self):
        MapAreaShare.objects.create(area=self.area, user=self.shared_user)
        self.client.force_authenticate(user=self.shared_user)

        response = self.client.post(
            self.list_url,
            {"username": self.other_user.username},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(
            MapAreaShare.objects.filter(area=self.area, user=self.other_user).exists()
        )

    def test_unshared_user_cannot_add_share(self):
        self.client.force_authenticate(user=self.other_user)

        response = self.client.post(
            self.list_url,
            {"username": self.shared_user.username},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(MapAreaShare.objects.exists())

    def test_unauthenticated_user_cannot_add_share(self):
        response = self.client.post(
            self.list_url,
            {"username": self.shared_user.username},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(MapAreaShare.objects.exists())

    def test_area_without_creator_cannot_be_shared_by_regular_user(self):
        no_creator_area = MapArea.objects.create(
            name="No Creator Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            created_by=None,
        )
        self.client.force_authenticate(user=self.owner)
        url = reverse(
            "map-area-share-list-create",
            kwargs={"area_id": no_creator_area.id},
        )

        response = self.client.post(
            url,
            {"username": self.shared_user.username},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(MapAreaShare.objects.filter(area=no_creator_area).exists())

    def test_owner_can_delete_share(self):
        share = MapAreaShare.objects.create(area=self.area, user=self.shared_user)
        self.client.force_authenticate(user=self.owner)
        url = reverse(
            "map-area-share-detail",
            kwargs={"area_id": self.area.id, "share_id": share.id},
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(MapAreaShare.objects.filter(id=share.id).exists())

    def test_deleted_user_loses_view_and_rating_access(self):
        share = MapAreaShare.objects.create(area=self.area, user=self.shared_user)
        self.client.force_authenticate(user=self.owner)
        delete_url = reverse(
            "map-area-share-detail",
            kwargs={"area_id": self.area.id, "share_id": share.id},
        )
        self.client.delete(delete_url)

        self.client.force_authenticate(user=self.shared_user)
        detail_response = self.client.get(
            reverse("map-area-detail", kwargs={"area_id": self.area.id})
        )
        grids_response = self.client.get(
            reverse("grid-cell-list", kwargs={"area_id": self.area.id})
        )
        rating_response = self.client.post(
            reverse("grid-rating-create", kwargs={"grid_id": self.grid.id}),
            {"score": 7},
            format="json",
        )

        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(grids_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(rating_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(
            GridRating.objects.filter(grid=self.grid, user=self.shared_user).exists()
        )

    def test_unknown_share_id_returns_404(self):
        self.client.force_authenticate(user=self.owner)
        url = reverse(
            "map-area-share-detail",
            kwargs={"area_id": self.area.id, "share_id": 999999},
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_share_from_other_area_cannot_be_deleted(self):
        other_area = MapArea.objects.create(
            name="Other Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            created_by=self.owner,
        )
        other_share = MapAreaShare.objects.create(
            area=other_area,
            user=self.shared_user,
        )
        self.client.force_authenticate(user=self.owner)
        url = reverse(
            "map-area-share-detail",
            kwargs={"area_id": self.area.id, "share_id": other_share.id},
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(MapAreaShare.objects.filter(id=other_share.id).exists())

    def test_shared_user_cannot_delete_share(self):
        share = MapAreaShare.objects.create(area=self.area, user=self.shared_user)
        self.client.force_authenticate(user=self.shared_user)
        url = reverse(
            "map-area-share-detail",
            kwargs={"area_id": self.area.id, "share_id": share.id},
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(MapAreaShare.objects.filter(id=share.id).exists())

    def test_unshared_user_cannot_delete_share(self):
        share = MapAreaShare.objects.create(area=self.area, user=self.shared_user)
        self.client.force_authenticate(user=self.other_user)
        url = reverse(
            "map-area-share-detail",
            kwargs={"area_id": self.area.id, "share_id": share.id},
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(MapAreaShare.objects.filter(id=share.id).exists())

    def test_unauthenticated_user_cannot_delete_share(self):
        share = MapAreaShare.objects.create(area=self.area, user=self.shared_user)
        url = reverse(
            "map-area-share-detail",
            kwargs={"area_id": self.area.id, "share_id": share.id},
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(MapAreaShare.objects.filter(id=share.id).exists())

    def test_area_without_creator_share_cannot_be_deleted_by_regular_user(self):
        no_creator_area = MapArea.objects.create(
            name="No Creator Area",
            north=35.7,
            south=35.6,
            east=139.8,
            west=139.7,
            grid_size_meters=500,
            created_by=None,
        )
        share = MapAreaShare.objects.create(
            area=no_creator_area,
            user=self.shared_user,
        )
        self.client.force_authenticate(user=self.owner)
        url = reverse(
            "map-area-share-detail",
            kwargs={"area_id": no_creator_area.id, "share_id": share.id},
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(MapAreaShare.objects.filter(id=share.id).exists())


class GridRatingCreateViewTests(SerializerTestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.url = reverse("grid-rating-create", kwargs={"grid_id": self.grid.id})

    def test_authenticated_user_can_create_rating(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {"score": 8, "comment": "good place"},
            format="json",
        )
        self.grid.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["rating"]["grid"], self.grid.id)
        self.assertEqual(response.data["rating"]["user"], self.user.id)
        self.assertEqual(response.data["rating"]["score"], 8)
        self.assertEqual(response.data["rating"]["comment"], "good place")
        self.assertEqual(response.data["grid"]["average_user_score"], 8)
        self.assertEqual(response.data["grid"]["rating_count"], 1)
        self.assertEqual(response.data["grid"]["calculated_score"], 5.5)
        self.assertEqual(self.grid.average_user_score, 8)
        self.assertEqual(self.grid.rating_count, 1)
        self.assertEqual(self.grid.calculated_score, 5.5)
        self.assertIsNotNone(self.grid.score_updated_at)

    def test_authenticated_user_can_update_existing_rating(self):
        GridRating.objects.create(
            grid=self.grid,
            user=self.user,
            score=4,
            comment="before",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {"score": 10, "comment": "after"},
            format="json",
        )
        self.grid.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            GridRating.objects.filter(grid=self.grid, user=self.user).count(),
            1,
        )
        self.assertEqual(response.data["rating"]["score"], 10)
        self.assertEqual(response.data["rating"]["comment"], "after")
        self.assertEqual(response.data["grid"]["average_user_score"], 10)
        self.assertEqual(response.data["grid"]["rating_count"], 1)
        self.assertEqual(response.data["grid"]["calculated_score"], 6.5)
        self.assertEqual(self.grid.average_user_score, 10)
        self.assertEqual(self.grid.rating_count, 1)
        self.assertEqual(self.grid.calculated_score, 6.5)

    def test_unauthenticated_user_cannot_create_rating(self):
        response = self.client.post(self.url, {"score": 8}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(GridRating.objects.count(), 0)

    def test_unknown_grid_id_returns_404(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("grid-rating-create", kwargs={"grid_id": 999999})

        response = self.client.post(url, {"score": 8}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_users_grid_returns_404(self):
        other_user = get_user_model().objects.create_user(
            username="otheruser",
            password="test-password",
        )
        other_area = MapArea.objects.create(
            name="Other User Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=other_user,
        )
        other_grid = GridCell.objects.create(
            area=other_area,
            row_index=0,
            col_index=0,
            north=36.7,
            south=36.69,
            east=140.8,
            west=140.79,
            initial_score=9,
        )
        self.client.force_authenticate(user=self.user)
        url = reverse("grid-rating-create", kwargs={"grid_id": other_grid.id})

        response = self.client.post(url, {"score": 8}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(GridRating.objects.count(), 0)

    def test_shared_grid_can_be_rated(self):
        owner = get_user_model().objects.create_user(
            username="owner",
            password="test-password",
        )
        shared_user = get_user_model().objects.create_user(
            username="shareduser",
            password="test-password",
        )
        shared_area = MapArea.objects.create(
            name="Shared Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=owner,
        )
        shared_grid = GridCell.objects.create(
            area=shared_area,
            row_index=0,
            col_index=0,
            north=36.7,
            south=36.69,
            east=140.8,
            west=140.79,
            initial_score=9,
        )
        MapAreaShare.objects.create(area=shared_area, user=shared_user)
        self.client.force_authenticate(user=shared_user)
        url = reverse("grid-rating-create", kwargs={"grid_id": shared_grid.id})

        response = self.client.post(
            url,
            {"score": 7, "comment": "shared rating"},
            format="json",
        )
        rating = GridRating.objects.get(grid=shared_grid, user=shared_user)
        shared_grid.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["rating"]["user"], shared_user.id)
        self.assertEqual(rating.score, 7)
        self.assertEqual(rating.comment, "shared rating")
        self.assertEqual(shared_grid.average_user_score, 7)
        self.assertEqual(shared_grid.rating_count, 1)

    def test_shared_user_can_update_own_rating(self):
        owner = get_user_model().objects.create_user(
            username="owner",
            password="test-password",
        )
        shared_user = get_user_model().objects.create_user(
            username="shareduser",
            password="test-password",
        )
        shared_area = MapArea.objects.create(
            name="Shared Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=owner,
        )
        shared_grid = GridCell.objects.create(
            area=shared_area,
            row_index=0,
            col_index=0,
            north=36.7,
            south=36.69,
            east=140.8,
            west=140.79,
            initial_score=9,
        )
        MapAreaShare.objects.create(area=shared_area, user=shared_user)
        GridRating.objects.create(
            grid=shared_grid,
            user=shared_user,
            score=4,
            comment="before",
        )
        self.client.force_authenticate(user=shared_user)
        url = reverse("grid-rating-create", kwargs={"grid_id": shared_grid.id})

        response = self.client.post(
            url,
            {"score": 8, "comment": "after"},
            format="json",
        )
        rating = GridRating.objects.get(grid=shared_grid, user=shared_user)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(GridRating.objects.filter(grid=shared_grid).count(), 1)
        self.assertEqual(rating.score, 8)
        self.assertEqual(rating.comment, "after")

    def test_grid_without_area_creator_returns_404(self):
        no_creator_area = MapArea.objects.create(
            name="No Creator Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=None,
        )
        no_creator_grid = GridCell.objects.create(
            area=no_creator_area,
            row_index=0,
            col_index=0,
            north=36.7,
            south=36.69,
            east=140.8,
            west=140.79,
            initial_score=9,
        )
        self.client.force_authenticate(user=self.user)
        url = reverse("grid-rating-create", kwargs={"grid_id": no_creator_grid.id})

        response = self.client.post(url, {"score": 8}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(GridRating.objects.count(), 0)

    def test_shared_grid_without_area_creator_can_be_rated(self):
        shared_user = get_user_model().objects.create_user(
            username="shareduser",
            password="test-password",
        )
        no_creator_area = MapArea.objects.create(
            name="Shared No Creator Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=None,
        )
        shared_grid = GridCell.objects.create(
            area=no_creator_area,
            row_index=0,
            col_index=0,
            north=36.7,
            south=36.69,
            east=140.8,
            west=140.79,
            initial_score=9,
        )
        MapAreaShare.objects.create(area=no_creator_area, user=shared_user)
        self.client.force_authenticate(user=shared_user)
        url = reverse("grid-rating-create", kwargs={"grid_id": shared_grid.id})

        response = self.client.post(url, {"score": 8}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            GridRating.objects.filter(grid=shared_grid, user=shared_user).exists()
        )

    def test_unauthorized_grid_does_not_update_score_fields(self):
        other_user = get_user_model().objects.create_user(
            username="otheruser",
            password="test-password",
        )
        other_area = MapArea.objects.create(
            name="Other User Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=other_user,
        )
        other_grid = GridCell.objects.create(
            area=other_area,
            row_index=0,
            col_index=0,
            north=36.7,
            south=36.69,
            east=140.8,
            west=140.79,
            initial_score=9,
            average_user_score=2,
            rating_count=3,
            calculated_score=5.5,
        )
        self.client.force_authenticate(user=self.user)
        url = reverse("grid-rating-create", kwargs={"grid_id": other_grid.id})

        response = self.client.post(url, {"score": 8}, format="json")
        other_grid.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(other_grid.average_user_score, 2)
        self.assertEqual(other_grid.rating_count, 3)
        self.assertEqual(other_grid.calculated_score, 5.5)

    def test_invalid_score_returns_400(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, {"score": 11}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("score", response.data)
        self.assertEqual(GridRating.objects.count(), 0)


class BulkGridRatingCreateViewTests(SerializerTestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.url = reverse("bulk-grid-rating-create")
        self.second_grid = GridCell.objects.create(
            area=self.area,
            row_index=0,
            col_index=1,
            north=35.7,
            south=35.69,
            east=139.79,
            west=139.78,
            initial_score=7,
        )

    def test_authenticated_user_can_create_bulk_ratings(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {
                "grid_ids": [self.grid.id, self.second_grid.id],
                "score": 5,
                "comment": "bulk",
            },
            format="json",
        )
        self.grid.refresh_from_db()
        self.second_grid.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(GridRating.objects.count(), 2)
        self.assertEqual(len(response.data["grids"]), 2)
        self.assertEqual(response.data["grids"][0]["id"], self.grid.id)
        self.assertEqual(response.data["grids"][1]["id"], self.second_grid.id)
        self.assertEqual(self.grid.average_user_score, 5)
        self.assertEqual(self.grid.rating_count, 1)
        self.assertEqual(self.grid.calculated_score, 4)
        self.assertEqual(self.second_grid.average_user_score, 5)
        self.assertEqual(self.second_grid.rating_count, 1)
        self.assertEqual(self.second_grid.calculated_score, 6)

    def test_existing_rating_is_updated_without_creating_duplicate(self):
        GridRating.objects.create(
            grid=self.grid,
            user=self.user,
            score=3,
            comment="before",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {
                "grid_ids": [self.grid.id, self.second_grid.id],
                "score": 9,
                "comment": "after",
            },
            format="json",
        )
        self.grid.refresh_from_db()
        self.second_grid.refresh_from_db()
        rating = GridRating.objects.get(grid=self.grid, user=self.user)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(GridRating.objects.count(), 2)
        self.assertEqual(rating.score, 9)
        self.assertEqual(rating.comment, "after")
        self.assertEqual(self.grid.average_user_score, 9)
        self.assertEqual(self.grid.rating_count, 1)
        self.assertEqual(self.grid.calculated_score, 6)
        self.assertEqual(self.second_grid.average_user_score, 9)
        self.assertEqual(self.second_grid.rating_count, 1)
        self.assertEqual(self.second_grid.calculated_score, 8)

    def test_duplicate_grid_ids_are_processed_once(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {
                "grid_ids": [self.grid.id, self.grid.id],
                "score": 5,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(GridRating.objects.count(), 1)
        self.assertEqual(len(response.data["grids"]), 1)
        self.assertEqual(response.data["grids"][0]["id"], self.grid.id)

    def test_unauthenticated_user_cannot_create_bulk_ratings(self):
        response = self.client.post(
            self.url,
            {"grid_ids": [self.grid.id], "score": 5},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(GridRating.objects.count(), 0)

    def test_empty_grid_ids_returns_400(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {"grid_ids": [], "score": 5},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("grid_ids", response.data)
        self.assertEqual(GridRating.objects.count(), 0)

    def test_unknown_grid_id_returns_400(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {"grid_ids": [self.grid.id, 999999], "score": 5},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("grid_ids", response.data)
        self.assertEqual(GridRating.objects.count(), 0)

    def test_other_users_grid_id_returns_400(self):
        other_user = get_user_model().objects.create_user(
            username="otheruser",
            password="test-password",
        )
        other_area = MapArea.objects.create(
            name="Other User Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=other_user,
        )
        other_grid = GridCell.objects.create(
            area=other_area,
            row_index=0,
            col_index=0,
            north=36.7,
            south=36.69,
            east=140.8,
            west=140.79,
            initial_score=9,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {"grid_ids": [self.grid.id, other_grid.id], "score": 5},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("grid_ids", response.data)
        self.assertEqual(GridRating.objects.count(), 0)

    def test_shared_grid_ids_can_be_bulk_rated(self):
        owner = get_user_model().objects.create_user(
            username="owner",
            password="test-password",
        )
        shared_user = get_user_model().objects.create_user(
            username="shareduser",
            password="test-password",
        )
        shared_area = MapArea.objects.create(
            name="Shared Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=owner,
        )
        shared_grid_1 = GridCell.objects.create(
            area=shared_area,
            row_index=0,
            col_index=0,
            north=36.7,
            south=36.69,
            east=140.8,
            west=140.79,
            initial_score=9,
        )
        shared_grid_2 = GridCell.objects.create(
            area=shared_area,
            row_index=0,
            col_index=1,
            north=36.7,
            south=36.69,
            east=140.79,
            west=140.78,
            initial_score=6,
        )
        MapAreaShare.objects.create(area=shared_area, user=shared_user)
        self.client.force_authenticate(user=shared_user)

        response = self.client.post(
            self.url,
            {
                "grid_ids": [shared_grid_1.id, shared_grid_2.id],
                "score": 7,
                "comment": "shared bulk",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            GridRating.objects.filter(user=shared_user, score=7).count(),
            2,
        )
        self.assertEqual(len(response.data["grids"]), 2)

    def test_own_and_shared_grid_ids_can_be_bulk_rated_together(self):
        owner = get_user_model().objects.create_user(
            username="owner",
            password="test-password",
        )
        shared_area = MapArea.objects.create(
            name="Shared Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=owner,
        )
        shared_grid = GridCell.objects.create(
            area=shared_area,
            row_index=0,
            col_index=0,
            north=36.7,
            south=36.69,
            east=140.8,
            west=140.79,
            initial_score=9,
        )
        MapAreaShare.objects.create(area=shared_area, user=self.user)
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {
                "grid_ids": [self.grid.id, shared_grid.id],
                "score": 6,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            GridRating.objects.filter(grid=self.grid, user=self.user).exists()
        )
        self.assertTrue(
            GridRating.objects.filter(grid=shared_grid, user=self.user).exists()
        )

    def test_grid_without_area_creator_id_returns_400(self):
        no_creator_area = MapArea.objects.create(
            name="No Creator Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=None,
        )
        no_creator_grid = GridCell.objects.create(
            area=no_creator_area,
            row_index=0,
            col_index=0,
            north=36.7,
            south=36.69,
            east=140.8,
            west=140.79,
            initial_score=9,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {"grid_ids": [self.grid.id, no_creator_grid.id], "score": 5},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("grid_ids", response.data)
        self.assertEqual(GridRating.objects.count(), 0)

    def test_shared_grid_without_area_creator_can_be_bulk_rated(self):
        shared_user = get_user_model().objects.create_user(
            username="shareduser",
            password="test-password",
        )
        no_creator_area = MapArea.objects.create(
            name="Shared No Creator Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=None,
        )
        shared_grid = GridCell.objects.create(
            area=no_creator_area,
            row_index=0,
            col_index=0,
            north=36.7,
            south=36.69,
            east=140.8,
            west=140.79,
            initial_score=9,
        )
        MapAreaShare.objects.create(area=no_creator_area, user=shared_user)
        self.client.force_authenticate(user=shared_user)

        response = self.client.post(
            self.url,
            {"grid_ids": [shared_grid.id], "score": 8},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            GridRating.objects.filter(grid=shared_grid, user=shared_user).exists()
        )

    def test_unauthorized_grid_id_does_not_create_any_ratings(self):
        other_user = get_user_model().objects.create_user(
            username="otheruser",
            password="test-password",
        )
        other_area = MapArea.objects.create(
            name="Other User Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=other_user,
        )
        other_grid = GridCell.objects.create(
            area=other_area,
            row_index=0,
            col_index=0,
            north=36.7,
            south=36.69,
            east=140.8,
            west=140.79,
            initial_score=9,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {"grid_ids": [self.grid.id, other_grid.id], "score": 5},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(GridRating.objects.count(), 0)

    def test_unauthorized_grid_id_does_not_update_any_score_fields(self):
        other_user = get_user_model().objects.create_user(
            username="otheruser",
            password="test-password",
        )
        other_area = MapArea.objects.create(
            name="Other User Area",
            north=36.7,
            south=36.6,
            east=140.8,
            west=140.7,
            grid_size_meters=1000,
            created_by=other_user,
        )
        other_grid = GridCell.objects.create(
            area=other_area,
            row_index=0,
            col_index=0,
            north=36.7,
            south=36.69,
            east=140.8,
            west=140.79,
            initial_score=9,
            average_user_score=2,
            rating_count=3,
            calculated_score=5.5,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {"grid_ids": [self.grid.id, other_grid.id], "score": 5},
            format="json",
        )
        self.grid.refresh_from_db()
        other_grid.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.grid.average_user_score, 4)
        self.assertEqual(self.grid.rating_count, 1)
        self.assertEqual(self.grid.calculated_score, 3.5)
        self.assertEqual(other_grid.average_user_score, 2)
        self.assertEqual(other_grid.rating_count, 3)
        self.assertEqual(other_grid.calculated_score, 5.5)

    def test_invalid_score_returns_400(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {"grid_ids": [self.grid.id], "score": 11},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("score", response.data)
        self.assertEqual(GridRating.objects.count(), 0)


class GridCellGenerateViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="testuser",
            password="test-password",
        )
        self.client = APIClient()
        self.area = MapArea.objects.create(
            name="Generate Area",
            north=1.0,
            south=0.85,
            east=1.0,
            west=0.85,
            grid_size_meters=11100,
            created_by=self.user,
        )
        self.url = reverse("grid-cell-generate", kwargs={"area_id": self.area.id})

    def test_authenticated_user_can_generate_grid_cells_for_area(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(GridCell.objects.filter(area=self.area).count(), 4)

    def test_area_creator_can_generate_grid_cells_for_area(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_other_user_cannot_generate_grid_cells_for_area(self):
        other_user = get_user_model().objects.create_user(
            username="otheruser",
            password="test-password",
        )
        self.client.force_authenticate(user=other_user)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.data["detail"],
            "この MapArea の GridCell を生成する権限がありません。",
        )

    def test_other_user_does_not_create_grid_cells(self):
        other_user = get_user_model().objects.create_user(
            username="otheruser",
            password="test-password",
        )
        self.client.force_authenticate(user=other_user)

        self.client.post(self.url)

        self.assertEqual(GridCell.objects.filter(area=self.area).count(), 0)

    def test_area_without_creator_returns_403(self):
        area_without_creator = MapArea.objects.create(
            name="No Creator Area",
            north=1.0,
            south=0.85,
            east=1.0,
            west=0.85,
            grid_size_meters=11100,
            created_by=None,
        )
        url = reverse(
            "grid-cell-generate",
            kwargs={"area_id": area_without_creator.id},
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("detail", response.data)

    def test_area_without_creator_does_not_create_grid_cells(self):
        area_without_creator = MapArea.objects.create(
            name="No Creator Area",
            north=1.0,
            south=0.85,
            east=1.0,
            west=0.85,
            grid_size_meters=11100,
            created_by=None,
        )
        url = reverse(
            "grid-cell-generate",
            kwargs={"area_id": area_without_creator.id},
        )
        self.client.force_authenticate(user=self.user)

        self.client.post(url)

        self.assertEqual(
            GridCell.objects.filter(area=area_without_creator).count(),
            0,
        )

    def test_generate_response_contains_area_and_grids(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url)

        self.assertIn("area", response.data)
        self.assertIn("grids", response.data)
        self.assertEqual(response.data["area"]["id"], self.area.id)
        self.assertEqual(response.data["area"]["name"], self.area.name)
        self.assertEqual(len(response.data["grids"]), 4)

    def test_generated_grids_are_returned_by_row_index_and_col_index(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url)
        positions = [
            (grid["row_index"], grid["col_index"]) for grid in response.data["grids"]
        ]

        self.assertEqual(positions, [(0, 0), (0, 1), (1, 0), (1, 1)])

    def test_unauthenticated_user_cannot_generate_grid_cells(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(GridCell.objects.filter(area=self.area).count(), 0)

    def test_unknown_area_id_returns_404(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("grid-cell-generate", kwargs={"area_id": 999999})

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_area_with_existing_grid_cells_returns_400(self):
        GridCell.objects.create(
            area=self.area,
            row_index=0,
            col_index=0,
            north=1.0,
            south=0.9,
            east=0.95,
            west=0.85,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "この MapArea には既に GridCell があります。",
        )

    def test_area_with_existing_grid_cells_does_not_create_more_cells(self):
        GridCell.objects.create(
            area=self.area,
            row_index=0,
            col_index=0,
            north=1.0,
            south=0.9,
            east=0.95,
            west=0.85,
        )
        self.client.force_authenticate(user=self.user)

        self.client.post(self.url)

        self.assertEqual(GridCell.objects.filter(area=self.area).count(), 1)


class GridCellListViewTests(SerializerTestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.url = reverse("grid-cell-list", kwargs={"area_id": self.area.id})

    def test_authenticated_user_can_get_grid_cells_for_area(self):
        second_grid = GridCell.objects.create(
            area=self.area,
            row_index=0,
            col_index=1,
            north=35.7,
            south=35.69,
            east=139.79,
            west=139.78,
            initial_score=7,
            average_user_score=5,
            rating_count=1,
            calculated_score=6,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["area"]["id"], self.area.id)
        self.assertEqual(response.data["area"]["name"], self.area.name)
        self.assertEqual(len(response.data["grids"]), 2)
        self.assertEqual(response.data["grids"][0]["id"], self.grid.id)
        self.assertEqual(response.data["grids"][1]["id"], second_grid.id)
        self.assertEqual(response.data["grids"][0]["calculated_score"], 3.5)
        self.assertEqual(
            response.data["grids"][0]["auto_score_breakdown"]["base_score"],
            0.6,
        )
        self.assertEqual(response.data["grids"][1]["calculated_score"], 6)
        self.assertIsNone(response.data["grids"][1]["auto_score_breakdown"])

    def test_grid_cells_are_ordered_by_row_index_and_col_index(self):
        grid_col_1 = GridCell.objects.create(
            area=self.area,
            row_index=0,
            col_index=1,
            north=35.7,
            south=35.69,
            east=139.79,
            west=139.78,
            initial_score=7,
        )
        grid_row_1 = GridCell.objects.create(
            area=self.area,
            row_index=1,
            col_index=0,
            north=35.69,
            south=35.68,
            east=139.8,
            west=139.79,
            initial_score=4,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)
        grid_ids = [grid["id"] for grid in response.data["grids"]]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(grid_ids, [self.grid.id, grid_col_1.id, grid_row_1.id])

    def test_area_without_grid_cells_returns_empty_list(self):
        empty_area = MapArea.objects.create(
            name="Empty Area",
            north=35.8,
            south=35.7,
            east=139.9,
            west=139.8,
            grid_size_meters=500,
            created_by=self.user,
        )
        self.client.force_authenticate(user=self.user)
        url = reverse("grid-cell-list", kwargs={"area_id": empty_area.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["area"]["id"], empty_area.id)
        self.assertEqual(response.data["area"]["name"], empty_area.name)
        self.assertEqual(response.data["grids"], [])

    def test_unauthenticated_user_cannot_get_grid_cells(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unknown_area_id_returns_404(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("grid-cell-list", kwargs={"area_id": 999999})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_users_area_grid_cells_return_404(self):
        other_user = get_user_model().objects.create_user(
            username="otheruser",
            password="test-password",
        )
        other_area = MapArea.objects.create(
            name="Other User Area",
            north=35.8,
            south=35.7,
            east=139.9,
            west=139.8,
            grid_size_meters=500,
            created_by=other_user,
        )
        GridCell.objects.create(
            area=other_area,
            row_index=0,
            col_index=0,
            north=35.8,
            south=35.79,
            east=139.9,
            west=139.89,
            initial_score=9,
        )
        self.client.force_authenticate(user=self.user)
        url = reverse("grid-cell-list", kwargs={"area_id": other_area.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_shared_area_grid_cells_can_be_listed(self):
        owner = get_user_model().objects.create_user(
            username="owner",
            password="test-password",
        )
        shared_area = MapArea.objects.create(
            name="Shared Area",
            north=35.8,
            south=35.7,
            east=139.9,
            west=139.8,
            grid_size_meters=500,
            created_by=owner,
        )
        shared_grid = GridCell.objects.create(
            area=shared_area,
            row_index=0,
            col_index=0,
            north=35.8,
            south=35.79,
            east=139.9,
            west=139.89,
            initial_score=9,
            calculated_score=9,
        )
        MapAreaShare.objects.create(area=shared_area, user=self.user)
        self.client.force_authenticate(user=self.user)
        url = reverse("grid-cell-list", kwargs={"area_id": shared_area.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["area"]["id"], shared_area.id)
        self.assertEqual(response.data["area"]["name"], shared_area.name)
        self.assertEqual(len(response.data["grids"]), 1)
        self.assertEqual(response.data["grids"][0]["id"], shared_grid.id)

    def test_area_without_creator_grid_cells_return_404(self):
        no_creator_area = MapArea.objects.create(
            name="No Creator Area",
            north=35.8,
            south=35.7,
            east=139.9,
            west=139.8,
            grid_size_meters=500,
            created_by=None,
        )
        GridCell.objects.create(
            area=no_creator_area,
            row_index=0,
            col_index=0,
            north=35.8,
            south=35.79,
            east=139.9,
            west=139.89,
            initial_score=9,
        )
        self.client.force_authenticate(user=self.user)
        url = reverse("grid-cell-list", kwargs={"area_id": no_creator_area.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_shared_area_without_creator_grid_cells_can_be_listed(self):
        no_creator_area = MapArea.objects.create(
            name="Shared No Creator Area",
            north=35.8,
            south=35.7,
            east=139.9,
            west=139.8,
            grid_size_meters=500,
            created_by=None,
        )
        no_creator_grid = GridCell.objects.create(
            area=no_creator_area,
            row_index=0,
            col_index=0,
            north=35.8,
            south=35.79,
            east=139.9,
            west=139.89,
            initial_score=9,
        )
        MapAreaShare.objects.create(area=no_creator_area, user=self.user)
        self.client.force_authenticate(user=self.user)
        url = reverse("grid-cell-list", kwargs={"area_id": no_creator_area.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["area"]["id"], no_creator_area.id)
        self.assertEqual(len(response.data["grids"]), 1)
        self.assertEqual(response.data["grids"][0]["id"], no_creator_grid.id)

    def test_grid_cells_from_other_area_are_not_included(self):
        other_area = MapArea.objects.create(
            name="Other Area",
            north=35.8,
            south=35.7,
            east=139.9,
            west=139.8,
            grid_size_meters=500,
            created_by=self.user,
        )
        other_grid = GridCell.objects.create(
            area=other_area,
            row_index=0,
            col_index=0,
            north=35.8,
            south=35.79,
            east=139.9,
            west=139.89,
            initial_score=9,
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)
        grid_ids = [grid["id"] for grid in response.data["grids"]]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.grid.id, grid_ids)
        self.assertNotIn(other_grid.id, grid_ids)
