from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import GridCell, GridRating, MapArea
from .serializers import (
    BulkGridRatingSerializer,
    GridCellScoreSerializer,
    GridRatingCreateSerializer,
    GridRatingResponseSerializer,
    MapAreaSerializer,
)
from .services import update_grid_cell_score


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
        self.assertEqual(data["average_user_score"], 4)
        self.assertEqual(data["rating_count"], 1)
        self.assertEqual(data["calculated_score"], 3.5)
        self.assertIn("score_updated_at", data)


class MapAreaSerializerTests(TestCase):
    def test_valid_map_area_data_is_valid(self):
        serializer = MapAreaSerializer(
            data={
                "name": "Tokyo Station Area",
                "description": "manual area",
                "north": 35.7,
                "south": 35.6,
                "east": 139.8,
                "west": 139.7,
                "grid_size_meters": 500,
                "source": "manual",
            }
        )

        self.assertTrue(serializer.is_valid())

    def test_north_must_be_greater_than_south(self):
        serializer = MapAreaSerializer(
            data={
                "name": "Tokyo Station Area",
                "north": 35.6,
                "south": 35.6,
                "east": 139.8,
                "west": 139.7,
                "grid_size_meters": 500,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("north", serializer.errors)

    def test_east_must_be_greater_than_west(self):
        serializer = MapAreaSerializer(
            data={
                "name": "Tokyo Station Area",
                "north": 35.7,
                "south": 35.6,
                "east": 139.7,
                "west": 139.7,
                "grid_size_meters": 500,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("east", serializer.errors)


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


class MapAreaCreateViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="testuser",
            password="test-password",
        )
        self.client = APIClient()
        self.url = reverse("map-area-list-create")
        self.valid_payload = {
            "name": "Tokyo Station Area",
            "description": "manual area",
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
        self.assertEqual(response.data["name"], "Tokyo Station Area")
        self.assertEqual(response.data["description"], "manual area")
        self.assertEqual(response.data["north"], 35.7)
        self.assertEqual(response.data["south"], 35.6)
        self.assertEqual(response.data["east"], 139.8)
        self.assertEqual(response.data["west"], 139.7)
        self.assertEqual(response.data["grid_size_meters"], 500)
        self.assertEqual(response.data["source"], "manual")
        self.assertEqual(response.data["created_by"], self.user.id)
        self.assertIn("created_at", response.data)
        self.assertIn("updated_at", response.data)
        self.assertEqual(area.created_by, self.user)

    def test_unauthenticated_user_cannot_create_map_area(self):
        response = self.client.post(self.url, self.valid_payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(MapArea.objects.count(), 0)

    def test_blank_name_returns_400(self):
        self.client.force_authenticate(user=self.user)
        payload = {**self.valid_payload, "name": ""}

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data)
        self.assertEqual(MapArea.objects.count(), 0)

    def test_north_less_than_or_equal_to_south_returns_400(self):
        self.client.force_authenticate(user=self.user)
        payload = {**self.valid_payload, "north": 35.6}

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("north", response.data)
        self.assertEqual(MapArea.objects.count(), 0)

    def test_east_less_than_or_equal_to_west_returns_400(self):
        self.client.force_authenticate(user=self.user)
        payload = {**self.valid_payload, "east": 139.7}

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("east", response.data)
        self.assertEqual(MapArea.objects.count(), 0)

    def test_grid_size_meters_less_than_or_equal_to_zero_returns_400(self):
        self.client.force_authenticate(user=self.user)
        payload = {**self.valid_payload, "grid_size_meters": 0}

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("grid_size_meters", response.data)
        self.assertEqual(MapArea.objects.count(), 0)

    def test_missing_required_field_returns_400(self):
        self.client.force_authenticate(user=self.user)
        payload = self.valid_payload.copy()
        payload.pop("north")

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("north", response.data)
        self.assertEqual(MapArea.objects.count(), 0)

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
        self.assertIn("created_at", response.data["areas"][0])
        self.assertIn("updated_at", response.data["areas"][0])

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
        self.assertEqual(response.data["grids"][1]["calculated_score"], 6)

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
