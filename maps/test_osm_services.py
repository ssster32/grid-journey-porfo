from math import cos, radians
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import GridCell, MapArea
from .services import (
    METERS_PER_DEGREE,
    build_bounds_from_osm_element,
    build_feature_summaries_for_map_area_from_overpass,
    build_feature_summaries_for_grid_cell_contexts,
    build_feature_summaries_for_grid_cells,
    build_feature_summary_for_grid_cell,
    build_grid_cell_contexts_for_area,
    build_map_feature_from_osm_element,
    build_overpass_bbox_for_map_area,
    build_overpass_query,
    calculate_initial_score_from_feature_summary,
    classify_osm_element,
    determine_initial_score_for_grid_cell,
    fetch_osm_features_from_overpass,
    feature_intersects_grid_cell,
    generate_grid_cells_for_area,
    parse_overpass_elements_to_map_features,
)


class DetermineInitialScoreForGridCellTests(TestCase):
    def setUp(self):
        self.area = MapArea.objects.create(
            name="Feature Summary Area",
            north=10.0,
            south=9.0,
            east=21.0,
            west=19.0,
            grid_size_meters=500,
        )

    def grid_bounds(self):
        return {
            "north": 10.0,
            "south": 9.0,
            "east": 20.0,
            "west": 19.0,
        }

    def create_grid_cell(self, row_index, col_index, north, south, east, west):
        return GridCell.objects.create(
            area=self.area,
            row_index=row_index,
            col_index=col_index,
            north=north,
            south=south,
            east=east,
            west=west,
        )

    def test_build_overpass_bbox_for_map_area_returns_area_bounds(self):
        bbox = build_overpass_bbox_for_map_area(self.area)

        self.assertEqual(
            bbox,
            {
                "north": 10.0,
                "south": 9.0,
                "east": 21.0,
                "west": 19.0,
            },
        )

    def test_build_overpass_bbox_for_map_area_applies_padding(self):
        padding_meters = 500
        bbox = build_overpass_bbox_for_map_area(
            self.area,
            padding_meters=padding_meters,
        )
        center_lat = (self.area.north + self.area.south) / 2
        expected_lat_padding = padding_meters / METERS_PER_DEGREE
        expected_lng_padding = padding_meters / (
            METERS_PER_DEGREE * cos(radians(center_lat))
        )

        self.assertAlmostEqual(bbox["north"], self.area.north + expected_lat_padding)
        self.assertAlmostEqual(bbox["south"], self.area.south - expected_lat_padding)
        self.assertAlmostEqual(bbox["east"], self.area.east + expected_lng_padding)
        self.assertAlmostEqual(bbox["west"], self.area.west - expected_lng_padding)

    def test_build_overpass_bbox_for_map_area_invalid_bounds_raises_value_error(self):
        class InvalidMapArea:
            north = 9.0
            south = 10.0
            east = 21.0
            west = 19.0

        with self.assertRaises(ValueError):
            build_overpass_bbox_for_map_area(InvalidMapArea())

    def test_build_overpass_bbox_for_map_area_invalid_padding_raises_value_error(self):
        for padding_meters in (-1, float("nan"), "abc", True):
            with self.subTest(padding_meters=padding_meters):
                with self.assertRaises(ValueError):
                    build_overpass_bbox_for_map_area(
                        self.area,
                        padding_meters=padding_meters,
                    )

    def test_build_overpass_query_uses_overpass_bbox_order(self):
        query = build_overpass_query(
            {
                "north": 10.0,
                "south": 9.0,
                "east": 21.0,
                "west": 19.0,
            }
        )

        self.assertIn("(9.0,19.0,10.0,21.0)", query)
        self.assertNotIn("(10.0,9.0,21.0,19.0)", query)

    def test_build_overpass_query_targets_supported_features(self):
        query = build_overpass_query(self.grid_bounds())
        expected_filters = (
            'nwr["building"]',
            'nwr["highway"]',
            'nwr["natural"="water"]',
            'nwr["water"]',
            'nwr["waterway"="riverbank"]',
            'nwr["waterway"="river"]',
            'nwr["waterway"="stream"]',
            'nwr["waterway"="canal"]',
            'nwr["landuse"="forest"]',
            'nwr["natural"="wood"]',
            'nwr["leisure"="park"]',
            'nwr["leisure"="garden"]',
            'nwr["natural"="coastline"]',
        )

        self.assertIn("[out:json][timeout:25];", query)
        self.assertIn("out body geom;", query)
        for expected_filter in expected_filters:
            with self.subTest(expected_filter=expected_filter):
                self.assertIn(expected_filter, query)

    def test_build_overpass_query_invalid_bounds_raises_value_error(self):
        invalid_bounds_list = (
            None,
            [],
            {"north": 9.0, "south": 10.0, "east": 21.0, "west": 19.0},
            {"north": 10.0, "south": 9.0, "east": 19.0, "west": 21.0},
            {"north": 10.0, "south": 9.0, "east": 21.0, "west": True},
        )

        for bounds in invalid_bounds_list:
            with self.subTest(bounds=bounds):
                with self.assertRaises(ValueError):
                    build_overpass_query(bounds)

    @patch("maps.services.requests.post")
    def test_fetch_osm_features_from_overpass_posts_query_and_returns_features(
        self,
        mock_post,
    ):
        bounds = self.grid_bounds()
        endpoint = "https://example.test/overpass"
        timeout = 10
        response = Mock(status_code=200)
        response.json.return_value = {
            "elements": [
                {
                    "type": "way",
                    "id": 123,
                    "tags": {"building": "yes"},
                    "bounds": {
                        "north": 10.0,
                        "south": 9.0,
                        "east": 20.0,
                        "west": 19.0,
                    },
                },
            ],
        }
        mock_post.return_value = response

        map_features = fetch_osm_features_from_overpass(
            bounds,
            endpoint=endpoint,
            timeout=timeout,
        )

        mock_post.assert_called_once_with(
            endpoint,
            data=build_overpass_query(bounds).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "text/plain; charset=utf-8",
                "User-Agent": "portfolio-api-map-score/1.0",
            },
            timeout=float(timeout),
        )
        self.assertEqual(
            map_features,
            [
                {
                    "kind": "building",
                    "bounds": {
                        "north": 10.0,
                        "south": 9.0,
                        "east": 20.0,
                        "west": 19.0,
                    },
                    "source": "osm",
                    "source_type": "way",
                    "source_id": 123,
                },
            ],
        )

    @patch("maps.services.requests.post")
    def test_fetch_osm_features_from_overpass_uses_default_endpoint(self, mock_post):
        response = Mock(status_code=200)
        response.json.return_value = {"elements": []}
        mock_post.return_value = response

        fetch_osm_features_from_overpass(self.grid_bounds())

        self.assertEqual(
            mock_post.call_args.args[0],
            "https://overpass-api.de/api/interpreter",
        )

    def test_fetch_osm_features_from_overpass_invalid_endpoint_raises_value_error(self):
        for endpoint in (None, "", "   ", [], 123):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(ValueError):
                    fetch_osm_features_from_overpass(
                        self.grid_bounds(),
                        endpoint=endpoint,
                    )

    def test_fetch_osm_features_from_overpass_invalid_timeout_raises_value_error(self):
        for timeout in (0, -1, float("nan"), float("inf"), True, "abc", None):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    fetch_osm_features_from_overpass(
                        self.grid_bounds(),
                        timeout=timeout,
                    )

    @patch("maps.services.requests.post")
    def test_fetch_osm_features_from_overpass_non_200_raises_value_error(
        self,
        mock_post,
    ):
        response = Mock(status_code=429)
        response.text = "rate limit exceeded " + ("x" * 400)
        mock_post.return_value = response

        with self.assertRaises(ValueError) as context:
            fetch_osm_features_from_overpass(self.grid_bounds())

        error_message = str(context.exception)
        self.assertIn("status_code=429", error_message)
        self.assertIn("response_text=rate limit exceeded", error_message)
        self.assertLessEqual(
            len(error_message.split("response_text=", maxsplit=1)[1]),
            300,
        )

    @patch("maps.services.requests.post")
    def test_fetch_osm_features_from_overpass_invalid_json_raises_value_error(
        self,
        mock_post,
    ):
        response = Mock(status_code=200)
        response.json.side_effect = ValueError("invalid json")
        mock_post.return_value = response

        with self.assertRaises(ValueError):
            fetch_osm_features_from_overpass(self.grid_bounds())

    @patch("maps.services.requests.post")
    def test_fetch_osm_features_from_overpass_invalid_response_shape_raises_value_error(
        self,
        mock_post,
    ):
        invalid_response_data = (
            [],
            {},
            {"elements": None},
            {"elements": {}},
        )

        for response_data in invalid_response_data:
            with self.subTest(response_data=response_data):
                response = Mock(status_code=200)
                response.json.return_value = response_data
                mock_post.return_value = response

                with self.assertRaises(ValueError):
                    fetch_osm_features_from_overpass(self.grid_bounds())

    @patch("maps.services.requests.post")
    def test_fetch_osm_features_from_overpass_request_error_raises_value_error(
        self,
        mock_post,
    ):
        mock_post.side_effect = RuntimeError("network error")

        with self.assertRaises(ValueError):
            fetch_osm_features_from_overpass(self.grid_bounds())

    @patch("maps.services.requests.post")
    def test_fetch_osm_features_from_overpass_invalid_element_raises_value_error(
        self,
        mock_post,
    ):
        response = Mock(status_code=200)
        response.json.return_value = {"elements": [[]]}
        mock_post.return_value = response

        with self.assertRaises(ValueError):
            fetch_osm_features_from_overpass(self.grid_bounds())

    @patch("maps.services.fetch_osm_features_from_overpass")
    def test_build_feature_summaries_for_map_area_from_overpass_returns_summaries(
        self,
        mock_fetch,
    ):
        mock_fetch.return_value = [
            {
                "kind": "building",
                "bounds": {
                    "north": 9.9,
                    "south": 9.8,
                    "east": 19.2,
                    "west": 19.1,
                },
            },
            {
                "kind": "river",
                "bounds": {
                    "north": 9.8,
                    "south": 9.2,
                    "east": 20.5,
                    "west": 19.5,
                },
            },
        ]

        summaries = build_feature_summaries_for_map_area_from_overpass(
            self.area,
            rows=1,
            cols=2,
            lat_step=1.0,
            lng_step=1.0,
        )

        self.assertEqual(set(summaries.keys()), {(0, 0), (0, 1)})
        self.assertEqual(summaries[(0, 0)]["building_count"], 1)
        self.assertEqual(summaries[(0, 1)]["building_count"], 0)
        self.assertTrue(summaries[(0, 0)]["has_river"])
        self.assertTrue(summaries[(0, 1)]["has_river"])
        mock_fetch.assert_called_once_with(
            {
                "north": 10.0,
                "south": 9.0,
                "east": 21.0,
                "west": 19.0,
            }
        )

    @patch("maps.services.fetch_osm_features_from_overpass")
    def test_build_feature_summaries_for_map_area_from_overpass_uses_explicit_grid(
        self,
        mock_fetch,
    ):
        mock_fetch.return_value = [
            {
                "kind": "park",
                "bounds": {
                    "north": 9.4,
                    "south": 9.2,
                    "east": 20.5,
                    "west": 19.5,
                },
            },
        ]

        summaries = build_feature_summaries_for_map_area_from_overpass(
            self.area,
            rows=2,
            cols=1,
            lat_step=0.5,
            lng_step=2.0,
        )

        self.assertEqual(set(summaries.keys()), {(0, 0), (1, 0)})
        self.assertFalse(summaries[(0, 0)]["has_park"])
        self.assertTrue(summaries[(1, 0)]["has_park"])

    @patch("maps.services.fetch_osm_features_from_overpass")
    def test_build_feature_summaries_for_map_area_from_overpass_uses_padding(
        self,
        mock_fetch,
    ):
        mock_fetch.return_value = []
        padding_meters = 500

        build_feature_summaries_for_map_area_from_overpass(
            self.area,
            padding_meters=padding_meters,
            rows=1,
            cols=2,
            lat_step=1.0,
            lng_step=1.0,
        )

        self.assertEqual(
            mock_fetch.call_args.args[0],
            build_overpass_bbox_for_map_area(
                self.area,
                padding_meters=padding_meters,
            ),
        )

    @patch("maps.services.fetch_osm_features_from_overpass")
    def test_build_feature_summaries_for_map_area_from_overpass_fetch_error_raises_value_error(
        self,
        mock_fetch,
    ):
        mock_fetch.side_effect = ValueError("overpass error")

        with self.assertRaises(ValueError):
            build_feature_summaries_for_map_area_from_overpass(
                self.area,
                rows=1,
                cols=2,
                lat_step=1.0,
                lng_step=1.0,
            )

    @patch("maps.services.fetch_osm_features_from_overpass")
    def test_build_feature_summaries_for_map_area_from_overpass_invalid_padding_raises_value_error(
        self,
        mock_fetch,
    ):
        with self.assertRaises(ValueError):
            build_feature_summaries_for_map_area_from_overpass(
                self.area,
                padding_meters=-1,
                rows=1,
                cols=2,
                lat_step=1.0,
                lng_step=1.0,
            )

        mock_fetch.assert_not_called()

    @patch("maps.services.fetch_osm_features_from_overpass")
    def test_build_feature_summaries_for_map_area_from_overpass_invalid_grid_args_raise_value_error(
        self,
        mock_fetch,
    ):
        with self.assertRaises(ValueError):
            build_feature_summaries_for_map_area_from_overpass(
                self.area,
                rows=1,
            )

        mock_fetch.assert_not_called()

    def test_classify_osm_element_returns_supported_kinds(self):
        test_cases = (
            ({"building": "yes"}, "building"),
            ({"highway": "residential"}, "road"),
            ({"natural": "water"}, "water"),
            ({"water": "lake"}, "water"),
            ({"waterway": "riverbank"}, "water"),
            ({"landuse": "forest"}, "forest"),
            ({"natural": "wood"}, "forest"),
            ({"leisure": "park"}, "park"),
            ({"leisure": "garden"}, "park"),
            ({"waterway": "river"}, "river"),
            ({"waterway": "stream"}, "river"),
            ({"waterway": "canal"}, "river"),
            ({"natural": "coastline"}, "coastline"),
        )

        for tags, expected_kind in test_cases:
            with self.subTest(tags=tags):
                self.assertEqual(classify_osm_element(tags), expected_kind)

    def test_classify_osm_element_uses_priority_order(self):
        test_cases = (
            (
                {"natural": "coastline", "waterway": "river", "building": "yes"},
                "coastline",
            ),
            (
                {"waterway": "river", "natural": "water", "building": "yes"},
                "river",
            ),
            (
                {"natural": "water", "landuse": "forest", "building": "yes"},
                "water",
            ),
            (
                {"landuse": "forest", "leisure": "park", "building": "yes"},
                "forest",
            ),
            (
                {"leisure": "park", "highway": "service", "building": "yes"},
                "park",
            ),
            (
                {"highway": "service", "building": "yes"},
                "road",
            ),
        )

        for tags, expected_kind in test_cases:
            with self.subTest(tags=tags):
                self.assertEqual(classify_osm_element(tags), expected_kind)

    def test_classify_osm_element_returns_none_for_unknown_tags(self):
        self.assertIsNone(classify_osm_element({"amenity": "cafe"}))

    def test_classify_osm_element_invalid_tags_raises_value_error(self):
        for tags in (None, [], "building=yes"):
            with self.subTest(tags=tags):
                with self.assertRaises(ValueError):
                    classify_osm_element(tags)

    def test_build_bounds_from_osm_element_returns_normalized_bounds(self):
        bounds = build_bounds_from_osm_element(
            {
                "bounds": {
                    "north": "10.0",
                    "south": "9.0",
                    "east": "20.0",
                    "west": "19.0",
                },
            }
        )

        self.assertEqual(
            bounds,
            {
                "north": 10.0,
                "south": 9.0,
                "east": 20.0,
                "west": 19.0,
            },
        )

    def test_build_bounds_from_osm_element_returns_bounds_from_overpass_bounds(self):
        bounds = build_bounds_from_osm_element(
            {
                "bounds": {
                    "minlat": "9.0",
                    "minlon": "19.0",
                    "maxlat": "10.0",
                    "maxlon": "20.0",
                },
            }
        )

        self.assertEqual(
            bounds,
            {
                "north": 10.0,
                "south": 9.0,
                "east": 20.0,
                "west": 19.0,
            },
        )

    def test_build_bounds_from_osm_element_builds_bounds_from_geometry(self):
        bounds = build_bounds_from_osm_element(
            {
                "geometry": [
                    {"lat": 9.5, "lon": 19.8},
                    {"lat": 10.0, "lon": 19.2},
                    {"lat": 9.2, "lon": 20.1},
                ],
            }
        )

        self.assertEqual(
            bounds,
            {
                "north": 10.0,
                "south": 9.2,
                "east": 20.1,
                "west": 19.2,
            },
        )

    def test_build_bounds_from_osm_element_invalid_bounds_raises_value_error(self):
        invalid_elements = (
            {
                "bounds": {
                    "north": 9.0,
                    "south": 10.0,
                    "east": 20.0,
                    "west": 19.0,
                },
            },
            {
                "bounds": {
                    "minlat": 10.0,
                    "minlon": 19.0,
                    "maxlat": 9.0,
                    "maxlon": 20.0,
                },
            },
            {
                "bounds": {
                    "minlat": 9.0,
                    "minlon": 20.0,
                    "maxlat": 10.0,
                    "maxlon": 19.0,
                },
            },
        )

        for element in invalid_elements:
            with self.subTest(element=element):
                with self.assertRaises(ValueError):
                    build_bounds_from_osm_element(element)

    def test_build_bounds_from_osm_element_invalid_geometry_returns_none(self):
        invalid_elements = (
            {"geometry": []},
            {"geometry": [{"lat": 10.0}]},
            {"geometry": [{"lat": "abc", "lon": 19.0}]},
            {"geometry": [{"lat": 10.0, "lon": 19.0}]},
            {"geometry": [None]},
            {"lat": 10.0, "lon": 19.0},
            {},
        )

        for element in invalid_elements:
            with self.subTest(element=element):
                self.assertIsNone(build_bounds_from_osm_element(element))

    def test_build_bounds_from_osm_element_invalid_element_raises_value_error(self):
        for element in (None, [], "element"):
            with self.subTest(element=element):
                with self.assertRaises(ValueError):
                    build_bounds_from_osm_element(element)

    def test_build_map_feature_from_osm_element_with_building_bounds(self):
        map_feature = build_map_feature_from_osm_element(
            {
                "type": "way",
                "id": 123,
                "tags": {"building": "yes"},
                "bounds": {
                    "north": "10.0",
                    "south": "9.0",
                    "east": "20.0",
                    "west": "19.0",
                },
            }
        )

        self.assertEqual(
            map_feature,
            {
                "kind": "building",
                "bounds": {
                    "north": 10.0,
                    "south": 9.0,
                    "east": 20.0,
                    "west": 19.0,
                },
                "source": "osm",
                "source_type": "way",
                "source_id": 123,
            },
        )

    def test_build_map_feature_from_osm_element_with_geometry(self):
        map_feature = build_map_feature_from_osm_element(
            {
                "type": "way",
                "id": 456,
                "tags": {"highway": "residential"},
                "geometry": [
                    {"lat": 9.5, "lon": 19.8},
                    {"lat": 10.0, "lon": 19.2},
                    {"lat": 9.2, "lon": 20.1},
                ],
            }
        )

        self.assertEqual(map_feature["kind"], "road")
        self.assertEqual(
            map_feature["bounds"],
            {
                "north": 10.0,
                "south": 9.2,
                "east": 20.1,
                "west": 19.2,
            },
        )
        self.assertEqual(map_feature["source"], "osm")
        self.assertEqual(map_feature["source_type"], "way")
        self.assertEqual(map_feature["source_id"], 456)

    def test_build_map_feature_from_osm_element_returns_none_for_unknown_tags(self):
        self.assertIsNone(
            build_map_feature_from_osm_element(
                {
                    "type": "node",
                    "id": 789,
                    "tags": {"amenity": "cafe"},
                    "bounds": {
                        "north": 10.0,
                        "south": 9.0,
                        "east": 20.0,
                        "west": 19.0,
                    },
                }
            )
        )

    def test_build_map_feature_from_osm_element_returns_none_without_bounds(self):
        self.assertIsNone(
            build_map_feature_from_osm_element(
                {
                    "type": "node",
                    "id": 789,
                    "tags": {"building": "yes"},
                }
            )
        )

    def test_build_map_feature_from_osm_element_invalid_element_raises_value_error(self):
        for element in (None, [], "element"):
            with self.subTest(element=element):
                with self.assertRaises(ValueError):
                    build_map_feature_from_osm_element(element)

    def test_parse_overpass_elements_to_map_features_builds_multiple_features(self):
        map_features = parse_overpass_elements_to_map_features(
            [
                {
                    "type": "way",
                    "id": 123,
                    "tags": {"building": "yes"},
                    "bounds": {
                        "north": 10.0,
                        "south": 9.0,
                        "east": 20.0,
                        "west": 19.0,
                    },
                },
                {
                    "type": "way",
                    "id": 456,
                    "tags": {"highway": "residential"},
                    "geometry": [
                        {"lat": 9.5, "lon": 19.8},
                        {"lat": 10.0, "lon": 19.2},
                        {"lat": 9.2, "lon": 20.1},
                    ],
                },
            ]
        )

        self.assertEqual(len(map_features), 2)
        self.assertEqual(map_features[0]["kind"], "building")
        self.assertEqual(map_features[0]["source_id"], 123)
        self.assertEqual(map_features[1]["kind"], "road")
        self.assertEqual(map_features[1]["source_id"], 456)

    def test_parse_overpass_elements_to_map_features_skips_unknown_tags(self):
        map_features = parse_overpass_elements_to_map_features(
            [
                {
                    "type": "node",
                    "id": 789,
                    "tags": {"amenity": "cafe"},
                    "bounds": {
                        "north": 10.0,
                        "south": 9.0,
                        "east": 20.0,
                        "west": 19.0,
                    },
                },
                {
                    "type": "way",
                    "id": 123,
                    "tags": {"building": "yes"},
                    "bounds": {
                        "north": 10.0,
                        "south": 9.0,
                        "east": 20.0,
                        "west": 19.0,
                    },
                },
            ]
        )

        self.assertEqual(len(map_features), 1)
        self.assertEqual(map_features[0]["kind"], "building")

    def test_parse_overpass_elements_to_map_features_skips_missing_bounds(self):
        map_features = parse_overpass_elements_to_map_features(
            [
                {
                    "type": "way",
                    "id": 123,
                    "tags": {"building": "yes"},
                },
                {
                    "type": "way",
                    "id": 456,
                    "tags": {"highway": "residential"},
                    "bounds": {
                        "north": 10.0,
                        "south": 9.0,
                        "east": 20.0,
                        "west": 19.0,
                    },
                },
            ]
        )

        self.assertEqual(len(map_features), 1)
        self.assertEqual(map_features[0]["kind"], "road")

    def test_parse_overpass_elements_to_map_features_skips_invalid_bounds(self):
        map_features = parse_overpass_elements_to_map_features(
            [
                {
                    "type": "way",
                    "id": 123,
                    "tags": {"building": "yes"},
                    "bounds": {
                        "north": 10.0,
                        "south": 10.0,
                        "east": 20.0,
                        "west": 19.0,
                    },
                },
                {
                    "type": "way",
                    "id": 456,
                    "tags": {"highway": "residential"},
                    "bounds": {
                        "north": 10.0,
                        "south": 9.0,
                        "east": 20.0,
                        "west": 19.0,
                    },
                },
            ]
        )

        self.assertEqual(len(map_features), 1)
        self.assertEqual(map_features[0]["kind"], "road")
        self.assertEqual(map_features[0]["source_id"], 456)

    def test_parse_overpass_elements_to_map_features_returns_empty_list(self):
        map_features = parse_overpass_elements_to_map_features(
            [
                {
                    "type": "node",
                    "id": 789,
                    "tags": {"amenity": "cafe"},
                },
                {
                    "type": "way",
                    "id": 123,
                    "tags": {"building": "yes"},
                },
            ]
        )

        self.assertEqual(map_features, [])

    def test_parse_overpass_elements_to_map_features_returns_empty_list_for_invalid_bounds(
        self,
    ):
        map_features = parse_overpass_elements_to_map_features(
            [
                {
                    "type": "way",
                    "id": 123,
                    "tags": {"building": "yes"},
                    "bounds": {
                        "north": 10.0,
                        "south": 10.0,
                        "east": 20.0,
                        "west": 19.0,
                    },
                },
                {
                    "type": "way",
                    "id": 456,
                    "tags": {"amenity": "cafe"},
                    "bounds": {
                        "north": 10.0,
                        "south": 9.0,
                        "east": 20.0,
                        "west": 19.0,
                    },
                },
            ]
        )

        self.assertEqual(map_features, [])

    def test_parse_overpass_elements_to_map_features_invalid_elements_raises_value_error(
        self,
    ):
        for elements in (None, {}, "elements"):
            with self.subTest(elements=elements):
                with self.assertRaises(ValueError):
                    parse_overpass_elements_to_map_features(elements)

    def test_parse_overpass_elements_to_map_features_invalid_element_raises_value_error(
        self,
    ):
        with self.assertRaises(ValueError):
            parse_overpass_elements_to_map_features([{"tags": {"building": "yes"}}, []])

    def test_feature_intersects_grid_cell_when_bboxes_overlap(self):
        self.assertTrue(
            feature_intersects_grid_cell(
                {
                    "north": 10.5,
                    "south": 9.5,
                    "east": 20.5,
                    "west": 19.5,
                },
                self.grid_bounds(),
            )
        )

    def test_feature_does_not_intersect_when_only_touching_boundary(self):
        self.assertFalse(
            feature_intersects_grid_cell(
                {
                    "north": 10.5,
                    "south": 10.0,
                    "east": 20.0,
                    "west": 19.0,
                },
                self.grid_bounds(),
            )
        )

    def test_build_feature_summary_counts_buildings_and_roads(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "building",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
                {
                    "kind": "building",
                    "bounds": {
                        "north": 9.7,
                        "south": 9.6,
                        "east": 19.4,
                        "west": 19.3,
                    },
                },
                {
                    "kind": "road",
                    "bounds": {
                        "north": 9.5,
                        "south": 9.4,
                        "east": 19.6,
                        "west": 19.5,
                    },
                },
            ],
        )

        self.assertEqual(summary["building_count"], 2)
        self.assertEqual(summary["road_count"], 1)

    def test_build_feature_summary_sets_water_and_forest_ratios(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "water",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
                {
                    "kind": "forest",
                    "bounds": {
                        "north": 10.5,
                        "south": 8.5,
                        "east": 20.5,
                        "west": 18.5,
                    },
                },
            ],
        )

        self.assertEqual(summary["water_coverage_ratio"], 0.5)
        self.assertEqual(summary["forest_coverage_ratio"], 1.0)

    def test_build_feature_summary_sets_boolean_features(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "park",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
                {
                    "kind": "river",
                    "bounds": {
                        "north": 9.7,
                        "south": 9.6,
                        "east": 19.4,
                        "west": 19.3,
                    },
                },
                {
                    "kind": "coastline",
                    "bounds": {
                        "north": 9.5,
                        "south": 9.4,
                        "east": 19.6,
                        "west": 19.5,
                    },
                },
            ],
        )

        self.assertTrue(summary["has_park"])
        self.assertTrue(summary["has_river"])
        self.assertTrue(summary["is_coastal"])

    def test_build_feature_summary_ignores_unknown_kind_and_non_intersections(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "unknown",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
                {
                    "kind": "building",
                    "bounds": {
                        "north": 11.0,
                        "south": 10.5,
                        "east": 19.5,
                        "west": 19.4,
                    },
                },
            ],
        )

        self.assertEqual(
            summary,
            {
                "building_count": 0,
                "road_count": 0,
                "water_coverage_ratio": 0.0,
                "forest_coverage_ratio": 0.0,
                "has_park": False,
                "has_river": False,
                "is_coastal": False,
            },
        )

    def test_build_feature_summary_invalid_input_raises_value_error(self):
        invalid_inputs = (
            ({"north": 1, "south": 1, "east": 1, "west": 0}, []),
            (self.grid_bounds(), None),
            (self.grid_bounds(), [{"kind": "building", "bounds": None}]),
        )

        for grid_cell_bounds, map_features in invalid_inputs:
            with self.subTest(grid_cell_bounds=grid_cell_bounds, map_features=map_features):
                with self.assertRaises(ValueError):
                    build_feature_summary_for_grid_cell(
                        grid_cell_bounds,
                        map_features,
                    )

    def test_build_feature_summaries_for_grid_cells_returns_position_keys(self):
        grid_cells = [
            self.create_grid_cell(0, 0, 10.0, 9.0, 20.0, 19.0),
            self.create_grid_cell(0, 1, 10.0, 9.0, 21.0, 20.0),
        ]

        summaries = build_feature_summaries_for_grid_cells(grid_cells, [])

        self.assertEqual(set(summaries.keys()), {(0, 0), (0, 1)})

    def test_build_feature_summaries_for_grid_cells_builds_each_summary(self):
        grid_cells = [
            self.create_grid_cell(0, 0, 10.0, 9.0, 20.0, 19.0),
            self.create_grid_cell(0, 1, 10.0, 9.0, 21.0, 20.0),
        ]
        map_features = [
            {
                "kind": "building",
                "bounds": {
                    "north": 9.9,
                    "south": 9.8,
                    "east": 19.2,
                    "west": 19.1,
                },
            },
            {
                "kind": "road",
                "bounds": {
                    "north": 9.9,
                    "south": 9.8,
                    "east": 20.2,
                    "west": 20.1,
                },
            },
        ]

        summaries = build_feature_summaries_for_grid_cells(grid_cells, map_features)

        self.assertEqual(summaries[(0, 0)]["building_count"], 1)
        self.assertEqual(summaries[(0, 0)]["road_count"], 0)
        self.assertEqual(summaries[(0, 1)]["building_count"], 0)
        self.assertEqual(summaries[(0, 1)]["road_count"], 1)

    def test_build_feature_summaries_for_grid_cells_applies_spanning_feature(self):
        grid_cells = [
            self.create_grid_cell(0, 0, 10.0, 9.0, 20.0, 19.0),
            self.create_grid_cell(0, 1, 10.0, 9.0, 21.0, 20.0),
        ]
        map_features = [
            {
                "kind": "river",
                "bounds": {
                    "north": 9.8,
                    "south": 9.2,
                    "east": 20.5,
                    "west": 19.5,
                },
            },
        ]

        summaries = build_feature_summaries_for_grid_cells(grid_cells, map_features)

        self.assertTrue(summaries[(0, 0)]["has_river"])
        self.assertTrue(summaries[(0, 1)]["has_river"])

    def test_build_feature_summaries_for_grid_cells_empty_cell_gets_empty_summary(self):
        grid_cells = [
            self.create_grid_cell(0, 0, 10.0, 9.0, 20.0, 19.0),
            self.create_grid_cell(0, 1, 10.0, 9.0, 21.0, 20.0),
        ]
        map_features = [
            {
                "kind": "building",
                "bounds": {
                    "north": 9.9,
                    "south": 9.8,
                    "east": 19.2,
                    "west": 19.1,
                },
            },
        ]

        summaries = build_feature_summaries_for_grid_cells(grid_cells, map_features)

        self.assertEqual(
            summaries[(0, 1)],
            {
                "building_count": 0,
                "road_count": 0,
                "water_coverage_ratio": 0.0,
                "forest_coverage_ratio": 0.0,
                "has_park": False,
                "has_river": False,
                "is_coastal": False,
            },
        )

    def test_build_feature_summaries_for_grid_cell_contexts_builds_each_summary(self):
        grid_cell_contexts = [
            {
                "row_index": 0,
                "col_index": 0,
                "north": 10.0,
                "south": 9.0,
                "east": 20.0,
                "west": 19.0,
            },
            {
                "row_index": 0,
                "col_index": 1,
                "north": 10.0,
                "south": 9.0,
                "east": 21.0,
                "west": 20.0,
            },
        ]
        map_features = [
            {
                "kind": "building",
                "bounds": {
                    "north": 9.9,
                    "south": 9.8,
                    "east": 19.2,
                    "west": 19.1,
                },
            },
            {
                "kind": "road",
                "bounds": {
                    "north": 9.9,
                    "south": 9.8,
                    "east": 20.2,
                    "west": 20.1,
                },
            },
        ]

        summaries = build_feature_summaries_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )

        self.assertEqual(set(summaries.keys()), {(0, 0), (0, 1)})
        self.assertEqual(summaries[(0, 0)]["building_count"], 1)
        self.assertEqual(summaries[(0, 0)]["road_count"], 0)
        self.assertEqual(summaries[(0, 1)]["building_count"], 0)
        self.assertEqual(summaries[(0, 1)]["road_count"], 1)

    def test_build_feature_summaries_for_grid_cell_contexts_applies_spanning_feature(
        self,
    ):
        grid_cell_contexts = [
            {
                "row_index": 0,
                "col_index": 0,
                "north": 10.0,
                "south": 9.0,
                "east": 20.0,
                "west": 19.0,
            },
            {
                "row_index": 0,
                "col_index": 1,
                "north": 10.0,
                "south": 9.0,
                "east": 21.0,
                "west": 20.0,
            },
        ]
        map_features = [
            {
                "kind": "river",
                "bounds": {
                    "north": 9.8,
                    "south": 9.2,
                    "east": 20.5,
                    "west": 19.5,
                },
            },
        ]

        summaries = build_feature_summaries_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )

        self.assertTrue(summaries[(0, 0)]["has_river"])
        self.assertTrue(summaries[(0, 1)]["has_river"])

    def test_build_feature_summaries_for_grid_cell_contexts_empty_context_gets_empty_summary(
        self,
    ):
        grid_cell_contexts = [
            {
                "row_index": 0,
                "col_index": 0,
                "north": 10.0,
                "south": 9.0,
                "east": 20.0,
                "west": 19.0,
            },
            {
                "row_index": 0,
                "col_index": 1,
                "north": 10.0,
                "south": 9.0,
                "east": 21.0,
                "west": 20.0,
            },
        ]
        map_features = [
            {
                "kind": "building",
                "bounds": {
                    "north": 9.9,
                    "south": 9.8,
                    "east": 19.2,
                    "west": 19.1,
                },
            },
        ]

        summaries = build_feature_summaries_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )

        self.assertEqual(
            summaries[(0, 1)],
            {
                "building_count": 0,
                "road_count": 0,
                "water_coverage_ratio": 0.0,
                "forest_coverage_ratio": 0.0,
                "has_park": False,
                "has_river": False,
                "is_coastal": False,
            },
        )

    def test_build_feature_summaries_for_grid_cell_contexts_invalid_input_raises_value_error(
        self,
    ):
        valid_context = {
            "row_index": 0,
            "col_index": 0,
            "north": 10.0,
            "south": 9.0,
            "east": 20.0,
            "west": 19.0,
        }
        invalid_inputs = (
            (None, []),
            ([None], []),
            ([{**valid_context, "row_index": True}], []),
            ([{**valid_context, "col_index": "0"}], []),
            ([{**valid_context, "north": 9.0}], []),
            ([valid_context], None),
        )

        for grid_cell_contexts, map_features in invalid_inputs:
            with self.subTest(
                grid_cell_contexts=grid_cell_contexts,
                map_features=map_features,
            ):
                with self.assertRaises(ValueError):
                    build_feature_summaries_for_grid_cell_contexts(
                        grid_cell_contexts,
                        map_features,
                    )

    def test_grid_context_feature_summary_returns_auto_score(self):
        feature_summary = {
            "building_count": 20,
            "road_count": 10,
            "has_park": True,
            "has_river": True,
            "is_coastal": True,
            "water_coverage_ratio": 0.1,
        }
        expected_score = calculate_initial_score_from_feature_summary(feature_summary)

        score = determine_initial_score_for_grid_cell(
            region_feature_level=0,
            grid_context={"feature_summary": feature_summary},
        )

        self.assertEqual(score, expected_score)
        self.assertGreater(score, 2.5)

    def test_grid_context_without_feature_summary_returns_region_feature_fallback(self):
        score = determine_initial_score_for_grid_cell(
            region_feature_level=1.5,
            grid_context={"row_index": 0, "col_index": 0},
        )

        self.assertEqual(score, 1.5)

    def test_invalid_grid_context_feature_summary_raises_value_error(self):
        with self.assertRaises(ValueError):
            determine_initial_score_for_grid_cell(
                region_feature_level=1,
                grid_context={"feature_summary": {"building_count": -1}},
            )

    def test_feature_summary_buildings_and_roads_returns_middle_score(self):
        score = calculate_initial_score_from_feature_summary(
            {
                "building_count": 12,
                "road_count": 6,
            }
        )

        self.assertGreaterEqual(score, 1.0)
        self.assertLess(score, 2.0)
        self.assertIsInstance(score, float)

    def test_feature_summary_multiple_features_returns_high_score(self):
        score = calculate_initial_score_from_feature_summary(
            {
                "building_count": 20,
                "road_count": 10,
                "has_park": True,
                "has_river": True,
                "is_coastal": True,
                "water_coverage_ratio": 0.1,
            }
        )

        self.assertGreaterEqual(score, 2.5)
        self.assertLessEqual(score, 3.0)

    def test_feature_summary_full_water_returns_low_score(self):
        score = calculate_initial_score_from_feature_summary(
            {
                "water_coverage_ratio": 0.99,
            }
        )

        self.assertGreaterEqual(score, 0.0)
        self.assertLess(score, 1.0)

    def test_feature_summary_forest_only_returns_low_score(self):
        score = calculate_initial_score_from_feature_summary(
            {
                "forest_coverage_ratio": 0.98,
            }
        )

        self.assertGreaterEqual(score, 0.0)
        self.assertLess(score, 1.0)

    def test_feature_summary_score_is_clamped_to_0_to_3(self):
        high_score = calculate_initial_score_from_feature_summary(
            {
                "building_count": 999,
                "road_count": 999,
                "has_park": True,
                "has_river": True,
                "is_coastal": True,
                "water_coverage_ratio": 0.2,
                "forest_coverage_ratio": 0.2,
            }
        )
        low_score = calculate_initial_score_from_feature_summary(
            {
                "water_coverage_ratio": 1.0,
                "forest_coverage_ratio": 1.0,
            }
        )

        self.assertEqual(high_score, 3.0)
        self.assertEqual(low_score, 0.0)

    def test_invalid_feature_summary_raises_value_error(self):
        invalid_summaries = (
            None,
            [],
            {"building_count": -1},
            {"road_count": float("inf")},
            {"water_coverage_ratio": 1.1},
            {"forest_coverage_ratio": -0.1},
            {"building_count": True},
        )
        for feature_summary in invalid_summaries:
            with self.subTest(feature_summary=feature_summary):
                with self.assertRaises(ValueError):
                    calculate_initial_score_from_feature_summary(feature_summary)

    def test_region_feature_level_0_to_3_are_returned_as_float(self):
        for region_feature_level in (0, 1, 2, 3):
            with self.subTest(region_feature_level=region_feature_level):
                score = determine_initial_score_for_grid_cell(
                    region_feature_level=region_feature_level,
                    grid_context={"row_index": 0, "col_index": 0},
                )

                self.assertEqual(score, float(region_feature_level))
                self.assertIsInstance(score, float)

    def test_decimal_region_feature_level_is_returned_as_float(self):
        score = determine_initial_score_for_grid_cell(
            region_feature_level=1.75,
            grid_context={"row_index": 0, "col_index": 0},
        )

        self.assertEqual(score, 1.75)
        self.assertIsInstance(score, float)

    def test_invalid_region_feature_level_raises_value_error(self):
        for region_feature_level in (-0.1, 3.1, float("inf"), "abc", True):
            with self.subTest(region_feature_level=region_feature_level):
                with self.assertRaises(ValueError):
                    determine_initial_score_for_grid_cell(
                        region_feature_level=region_feature_level,
                    )


class GenerateGridCellsFeatureSummaryTests(TestCase):
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

    def test_feature_summary_sets_initial_score_for_matching_grid_cell(self):
        self.area.region_feature_level = 1
        self.area.save(update_fields=["region_feature_level"])
        feature_summary = {
            "building_count": 20,
            "road_count": 10,
            "has_park": True,
            "has_river": True,
            "is_coastal": True,
            "water_coverage_ratio": 0.1,
        }
        expected_score = calculate_initial_score_from_feature_summary(feature_summary)

        generate_grid_cells_for_area(
            self.area,
            feature_summaries_by_position={(0, 0): feature_summary},
        )
        auto_score_grid = GridCell.objects.get(
            area=self.area,
            row_index=0,
            col_index=0,
        )
        fallback_grid = GridCell.objects.get(
            area=self.area,
            row_index=0,
            col_index=1,
        )

        self.assertEqual(auto_score_grid.initial_score, expected_score)
        self.assertEqual(auto_score_grid.calculated_score, expected_score)
        self.assertEqual(fallback_grid.initial_score, 1.0)
        self.assertEqual(fallback_grid.calculated_score, 1.0)

    def test_context_feature_summaries_can_drive_generated_initial_scores(self):
        self.area.region_feature_level = 2
        self.area.save(update_fields=["region_feature_level"])
        grid_cell_contexts = build_grid_cell_contexts_for_area(self.area)
        map_features = [
            {
                "kind": "building",
                "bounds": {
                    "north": 0.99,
                    "south": 0.98,
                    "east": 0.87,
                    "west": 0.86,
                },
            },
        ]
        feature_summaries = build_feature_summaries_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )
        expected_score = calculate_initial_score_from_feature_summary(
            feature_summaries[(0, 0)]
        )

        generate_grid_cells_for_area(
            self.area,
            feature_summaries_by_position=feature_summaries,
        )
        auto_score_grid = GridCell.objects.get(
            area=self.area,
            row_index=0,
            col_index=0,
        )

        self.assertEqual(auto_score_grid.initial_score, expected_score)
        self.assertEqual(auto_score_grid.calculated_score, expected_score)
        self.assertNotEqual(auto_score_grid.initial_score, 2.0)

    def test_missing_feature_summary_uses_region_feature_level_fallback(self):
        self.area.region_feature_level = 2
        self.area.save(update_fields=["region_feature_level"])

        grid_cells = generate_grid_cells_for_area(
            self.area,
            feature_summaries_by_position={},
        )

        for grid_cell in grid_cells:
            self.assertEqual(grid_cell.initial_score, 2.0)
            self.assertEqual(grid_cell.calculated_score, 2.0)

    def test_invalid_feature_summary_by_position_raises_value_error(self):
        with self.assertRaises(ValueError):
            generate_grid_cells_for_area(
                self.area,
                feature_summaries_by_position={
                    (0, 0): {"building_count": -1},
                },
            )

        self.assertEqual(GridCell.objects.filter(area=self.area).count(), 0)

    def test_feature_summaries_by_position_must_be_dict(self):
        with self.assertRaises(ValueError):
            generate_grid_cells_for_area(
                self.area,
                feature_summaries_by_position=[],
            )

        self.assertEqual(GridCell.objects.filter(area=self.area).count(), 0)
