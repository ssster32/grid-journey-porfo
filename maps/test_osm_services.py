from math import cos, radians
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import GridCell, MapArea
from .services import (
    BASE_INITIAL_SCORE,
    BUILDING_BASE_SCORE_MAX_BONUS,
    BUILDING_COUNT_FOR_MAX_BASE_SCORE,
    METERS_PER_DEGREE,
    MIN_FOREST_COVERAGE_RATIO_FOR_SCORE,
    MIN_RIVER_COVERAGE_RATIO_FOR_HAS_RIVER,
    ROAD_BASE_SCORE_MAX_BONUS,
    build_bounds_from_osm_element,
    build_feature_summaries_for_map_area_from_overpass,
    build_feature_summaries_for_grid_cell_contexts,
    build_feature_summaries_for_grid_cells,
    build_feature_summary_for_grid_cell,
    build_grid_cell_contexts_for_area,
    build_map_feature_from_osm_element,
    build_overpass_bbox_for_map_area,
    build_overpass_query,
    calculate_bounds_overlap_ratio,
    calculate_bounds_size_ratios,
    calculate_initial_score_breakdown_from_feature_summary,
    calculate_initial_score_from_feature_summary,
    classify_osm_element,
    determine_initial_score_for_grid_cell,
    fetch_osm_features_from_overpass,
    feature_intersects_grid_cell,
    generate_grid_cells_for_area,
    is_large_waterway_river_bounds_for_map_area,
    parse_overpass_elements_to_map_features,
    summarize_river_feature_matches_for_grid_cell_contexts,
    summarize_waterway_feature_matches_for_grid_cell_contexts,
    summarize_waterway_river_bounds_for_map_area,
    should_use_river_feature_for_grid_cell,
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
    def test_build_feature_summaries_for_map_area_from_overpass_skips_large_waterway_river(
        self,
        mock_fetch,
    ):
        mock_fetch.return_value = [
            {
                "kind": "river",
                "source_waterway": "river",
                "bounds": {
                    "north": 10.0,
                    "south": 9.0,
                    "east": 21.0,
                    "west": 19.0,
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

        self.assertFalse(summaries[(0, 0)]["has_river"])
        self.assertFalse(summaries[(0, 1)]["has_river"])
        self.assertEqual(summaries[(0, 0)]["river_coverage_ratio"], 0.0)
        self.assertEqual(summaries[(0, 1)]["river_coverage_ratio"], 0.0)
        self.assertEqual(summaries.river_summary["river_cells"], 2)
        self.assertEqual(summaries.waterway_summary["waterway_river_features"], 1)
        self.assertEqual(summaries.waterway_summary["waterway_river_cells"], 2)
        self.assertEqual(
            summaries.waterway_river_bounds_summary[
                "waterway_river_bounds_features"
            ],
            1,
        )
        self.assertEqual(
            summaries.waterway_river_bounds_summary[
                "waterway_river_bounds_large_area_features"
            ],
            1,
        )
        self.assertEqual(
            summaries.waterway_river_bounds_summary[
                "waterway_river_bounds_filtered_features"
            ],
            1,
        )
        self.assertEqual(
            summaries.waterway_river_bounds_summary[
                "waterway_river_bounds_filtered_cells"
            ],
            2,
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
        self.assertEqual(summaries[(0, 0)]["park_coverage_ratio"], 0.0)
        self.assertTrue(summaries[(1, 0)]["has_park"])
        self.assertAlmostEqual(summaries[(1, 0)]["park_coverage_ratio"], 0.2)

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

    def test_build_map_feature_from_osm_element_keeps_source_waterway(self):
        map_feature = build_map_feature_from_osm_element(
            {
                "type": "way",
                "id": 789,
                "tags": {"waterway": "canal"},
                "bounds": {
                    "north": 10.0,
                    "south": 9.0,
                    "east": 20.0,
                    "west": 19.0,
                },
            }
        )

        self.assertEqual(map_feature["kind"], "river")
        self.assertEqual(map_feature["source_waterway"], "canal")

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

    def test_calculate_bounds_overlap_ratio_returns_one_when_feature_covers_grid_cell(
        self,
    ):
        ratio = calculate_bounds_overlap_ratio(
            {
                "north": 10.5,
                "south": 8.5,
                "east": 20.5,
                "west": 18.5,
            },
            self.grid_bounds(),
        )

        self.assertEqual(ratio, 1.0)

    def test_calculate_bounds_overlap_ratio_returns_half_for_half_overlap(self):
        ratio = calculate_bounds_overlap_ratio(
            {
                "north": 10.0,
                "south": 9.0,
                "east": 19.5,
                "west": 18.5,
            },
            self.grid_bounds(),
        )

        self.assertEqual(ratio, 0.5)

    def test_calculate_bounds_overlap_ratio_returns_zero_when_not_overlapping(self):
        ratio = calculate_bounds_overlap_ratio(
            {
                "north": 11.0,
                "south": 10.5,
                "east": 20.0,
                "west": 19.0,
            },
            self.grid_bounds(),
        )

        self.assertEqual(ratio, 0.0)

    def test_calculate_bounds_overlap_ratio_returns_zero_when_only_touching_boundary(
        self,
    ):
        ratio = calculate_bounds_overlap_ratio(
            {
                "north": 10.5,
                "south": 10.0,
                "east": 20.0,
                "west": 19.0,
            },
            self.grid_bounds(),
        )

        self.assertEqual(ratio, 0.0)

    def test_calculate_bounds_overlap_ratio_invalid_bounds_raises_value_error(self):
        invalid_bounds_list = (
            None,
            [],
            {"north": 9.0, "south": 10.0, "east": 20.0, "west": 19.0},
            {"north": 10.0, "south": 9.0, "east": 19.0, "west": 20.0},
            {"north": 10.0, "south": 9.0, "east": 20.0, "west": True},
        )

        for invalid_bounds in invalid_bounds_list:
            with self.subTest(invalid_bounds=invalid_bounds):
                with self.assertRaises(ValueError):
                    calculate_bounds_overlap_ratio(
                        invalid_bounds,
                        self.grid_bounds(),
                    )

        with self.assertRaises(ValueError):
            calculate_bounds_overlap_ratio(
                self.grid_bounds(),
                {"north": 1.0, "south": 1.0, "east": 2.0, "west": 1.0},
            )

    def test_calculate_bounds_size_ratios_returns_one_for_same_size_bounds(self):
        ratios = calculate_bounds_size_ratios(
            {
                "north": 10.0,
                "south": 9.0,
                "east": 20.0,
                "west": 19.0,
            },
            self.grid_bounds(),
        )

        self.assertEqual(
            ratios,
            {
                "height_ratio": 1.0,
                "width_ratio": 1.0,
                "area_ratio": 1.0,
            },
        )

    def test_calculate_bounds_size_ratios_returns_larger_feature_ratios(self):
        ratios = calculate_bounds_size_ratios(
            {
                "north": 10.5,
                "south": 8.5,
                "east": 22.5,
                "west": 17.5,
            },
            self.grid_bounds(),
        )

        self.assertEqual(ratios["height_ratio"], 2.0)
        self.assertEqual(ratios["width_ratio"], 5.0)
        self.assertEqual(ratios["area_ratio"], 10.0)

    def test_calculate_bounds_size_ratios_returns_smaller_feature_ratios(self):
        ratios = calculate_bounds_size_ratios(
            {
                "north": 9.75,
                "south": 9.25,
                "east": 19.25,
                "west": 19.0,
            },
            self.grid_bounds(),
        )

        self.assertEqual(ratios["height_ratio"], 0.5)
        self.assertEqual(ratios["width_ratio"], 0.25)
        self.assertEqual(ratios["area_ratio"], 0.125)

    def test_calculate_bounds_size_ratios_invalid_bounds_raises_value_error(self):
        invalid_bounds_list = (
            None,
            [],
            {"north": 9.0, "south": 10.0, "east": 20.0, "west": 19.0},
            {"north": 10.0, "south": 9.0, "east": 19.0, "west": 20.0},
            {"north": 10.0, "south": 9.0, "east": 20.0, "west": True},
        )

        for invalid_bounds in invalid_bounds_list:
            with self.subTest(invalid_bounds=invalid_bounds):
                with self.assertRaises(ValueError):
                    calculate_bounds_size_ratios(
                        invalid_bounds,
                        self.grid_bounds(),
                    )

        with self.assertRaises(ValueError):
            calculate_bounds_size_ratios(
                self.grid_bounds(),
                {"north": 1.0, "south": 1.0, "east": 2.0, "west": 1.0},
            )

    def test_should_use_river_feature_for_grid_cell_skips_map_sized_waterway_river(
        self,
    ):
        should_use = should_use_river_feature_for_grid_cell(
            {
                "kind": "river",
                "source_waterway": "river",
                "bounds": self.map_area_bounds(),
            },
            self.map_area_bounds(),
        )

        self.assertFalse(should_use)

    def test_is_large_waterway_river_bounds_for_map_area_uses_area_ratio_threshold(
        self,
    ):
        self.assertTrue(
            is_large_waterway_river_bounds_for_map_area(
                self.map_area_bounds(),
                self.map_area_bounds(),
            )
        )
        self.assertFalse(
            is_large_waterway_river_bounds_for_map_area(
                {
                    "north": 9.8,
                    "south": 9.2,
                    "east": 19.8,
                    "west": 19.2,
                },
                self.map_area_bounds(),
            )
        )

    def test_should_use_river_feature_for_grid_cell_keeps_non_waterway_river_targets(
        self,
    ):
        for source_waterway in ("stream", "canal", None):
            with self.subTest(source_waterway=source_waterway):
                feature = {
                    "kind": "river",
                    "bounds": self.map_area_bounds(),
                }
                if source_waterway is not None:
                    feature["source_waterway"] = source_waterway

                self.assertTrue(
                    should_use_river_feature_for_grid_cell(
                        feature,
                        self.map_area_bounds(),
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

    def test_build_feature_summary_does_not_count_road_when_area_ratio_is_too_large(
        self,
    ):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "road",
                    "bounds": {
                        "north": 12.0,
                        "south": 7.0,
                        "east": 22.0,
                        "west": 17.0,
                    },
                },
            ],
        )

        self.assertEqual(summary["road_count"], 0)

    def test_build_feature_summary_does_not_count_road_when_height_ratio_is_too_large(
        self,
    ):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "road",
                    "bounds": {
                        "north": 15.5,
                        "south": 4.5,
                        "east": 19.5,
                        "west": 19.0,
                    },
                },
            ],
        )

        self.assertEqual(summary["road_count"], 0)

    def test_build_feature_summary_does_not_count_road_when_width_ratio_is_too_large(
        self,
    ):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "road",
                    "bounds": {
                        "north": 9.5,
                        "south": 9.0,
                        "east": 25.5,
                        "west": 14.5,
                    },
                },
            ],
        )

        self.assertEqual(summary["road_count"], 0)

    def test_build_feature_summary_counts_road_at_size_ratio_thresholds(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "road",
                    "bounds": {
                        "north": 14.5,
                        "south": 4.5,
                        "east": 20.0,
                        "west": 18.0,
                    },
                },
            ],
        )

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

        self.assertAlmostEqual(summary["water_coverage_ratio"], 0.01)
        self.assertEqual(summary["forest_coverage_ratio"], 1.0)
        self.assertEqual(summary["park_coverage_ratio"], 0.0)

    def test_build_feature_summary_uses_max_natural_overlap_ratios(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "water",
                    "bounds": {
                        "north": 10.0,
                        "south": 9.0,
                        "east": 19.25,
                        "west": 18.75,
                    },
                },
                {
                    "kind": "water",
                    "bounds": {
                        "north": 10.0,
                        "south": 9.0,
                        "east": 19.5,
                        "west": 18.5,
                    },
                },
                {
                    "kind": "forest",
                    "bounds": {
                        "north": 9.5,
                        "south": 9.0,
                        "east": 20.0,
                        "west": 19.0,
                    },
                },
                {
                    "kind": "forest",
                    "bounds": {
                        "north": 9.25,
                        "south": 9.0,
                        "east": 20.0,
                        "west": 19.0,
                    },
                },
                {
                    "kind": "park",
                    "bounds": {
                        "north": 10.0,
                        "south": 9.0,
                        "east": 19.25,
                        "west": 18.75,
                    },
                },
                {
                    "kind": "park",
                    "bounds": {
                        "north": 10.0,
                        "south": 9.0,
                        "east": 19.5,
                        "west": 18.5,
                    },
                },
            ],
        )

        self.assertEqual(summary["water_coverage_ratio"], 0.5)
        self.assertEqual(summary["forest_coverage_ratio"], 0.5)
        self.assertEqual(summary["park_coverage_ratio"], 0.5)
        self.assertTrue(summary["has_park"])

    def test_build_feature_summary_keeps_has_park_for_small_park_overlap(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "park",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.04,
                        "west": 19.0,
                    },
                },
            ],
        )

        self.assertAlmostEqual(summary["park_coverage_ratio"], 0.004)
        self.assertTrue(summary["has_park"])

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
                        "north": 9.9,
                        "south": 9.5,
                        "east": 19.5,
                        "west": 19.1,
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
        self.assertAlmostEqual(summary["park_coverage_ratio"], 0.01)
        self.assertAlmostEqual(summary["river_coverage_ratio"], 0.16)

    def test_build_feature_summary_marks_normal_size_river(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "river",
                    "bounds": {
                        "north": 9.8,
                        "south": 9.2,
                        "east": 19.8,
                        "west": 19.2,
                    },
                },
            ],
        )

        self.assertTrue(summary["has_river"])
        self.assertAlmostEqual(summary["river_coverage_ratio"], 0.36)

    def test_build_feature_summary_marks_large_river_with_enough_overlap(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "river",
                    "bounds": {
                        "north": 15.0,
                        "south": 5.0,
                        "east": 19.1,
                        "west": 18.6,
                    },
                },
            ],
        )

        self.assertTrue(summary["has_river"])
        self.assertAlmostEqual(summary["river_coverage_ratio"], 0.1)

    def test_build_feature_summary_does_not_mark_large_river_with_small_overlap(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "river",
                    "bounds": {
                        "north": 15.5,
                        "south": 4.5,
                        "east": 19.04,
                        "west": 18.54,
                    },
                },
            ],
        )

        self.assertFalse(summary["has_river"])
        self.assertEqual(summary["river_coverage_ratio"], 0.0)

    def test_build_feature_summary_keeps_river_coverage_without_marking_small_touch(
        self,
    ):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "river",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.04,
                        "west": 19.0,
                    },
                },
            ],
        )

        self.assertAlmostEqual(summary["river_coverage_ratio"], 0.004)
        self.assertFalse(summary["has_river"])

    def test_build_feature_summary_marks_river_at_size_ratio_thresholds(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "river",
                    "bounds": {
                        "north": 14.5,
                        "south": 4.5,
                        "east": 20.0,
                        "west": 18.0,
                    },
                },
            ],
        )

        self.assertTrue(summary["has_river"])
        self.assertEqual(summary["river_coverage_ratio"], 1.0)

    def test_build_feature_summary_keeps_river_behavior_without_map_area_bounds(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "river",
                    "source_waterway": "river",
                    "bounds": {
                        "north": 10.0,
                        "south": 9.0,
                        "east": 21.0,
                        "west": 19.0,
                    },
                },
            ],
        )

        self.assertTrue(summary["has_river"])
        self.assertEqual(summary["river_coverage_ratio"], 1.0)

    def test_build_feature_summary_skips_large_waterway_river_for_map_area(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "river",
                    "source_waterway": "river",
                    "bounds": {
                        "north": 10.0,
                        "south": 9.0,
                        "east": 21.0,
                        "west": 19.0,
                    },
                },
            ],
            map_area_bounds={
                "north": 10.0,
                "south": 9.0,
                "east": 21.0,
                "west": 19.0,
            },
        )

        self.assertFalse(summary["has_river"])
        self.assertEqual(summary["river_coverage_ratio"], 0.0)

    def test_build_feature_summary_uses_small_waterway_river_for_map_area(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "river",
                    "source_waterway": "river",
                    "bounds": {
                        "north": 9.8,
                        "south": 9.2,
                        "east": 19.8,
                        "west": 19.2,
                    },
                },
            ],
            map_area_bounds={
                "north": 10.0,
                "south": 9.0,
                "east": 21.0,
                "west": 19.0,
            },
        )

        self.assertTrue(summary["has_river"])
        self.assertAlmostEqual(summary["river_coverage_ratio"], 0.36)

    def test_build_feature_summary_keeps_large_stream_and_canal_for_map_area(self):
        for source_waterway in ("stream", "canal"):
            with self.subTest(source_waterway=source_waterway):
                summary = build_feature_summary_for_grid_cell(
                    self.grid_bounds(),
                    [
                        {
                            "kind": "river",
                            "source_waterway": source_waterway,
                            "bounds": {
                                "north": 10.0,
                                "south": 9.0,
                                "east": 21.0,
                                "west": 19.0,
                            },
                        },
                    ],
                    map_area_bounds={
                        "north": 10.0,
                        "south": 9.0,
                        "east": 21.0,
                        "west": 19.0,
                    },
                )

                self.assertTrue(summary["has_river"])
                self.assertEqual(summary["river_coverage_ratio"], 1.0)

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
                "park_coverage_ratio": 0.0,
                "river_coverage_ratio": 0.0,
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
                "park_coverage_ratio": 0.0,
                "river_coverage_ratio": 0.0,
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

    def test_build_feature_summaries_for_grid_cell_contexts_uses_map_area_bounds(
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
                "source_waterway": "river",
                "bounds": {
                    "north": 10.0,
                    "south": 9.0,
                    "east": 21.0,
                    "west": 19.0,
                },
            },
        ]

        summaries = build_feature_summaries_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
            map_area_bounds={
                "north": 10.0,
                "south": 9.0,
                "east": 21.0,
                "west": 19.0,
            },
        )

        self.assertFalse(summaries[(0, 0)]["has_river"])
        self.assertFalse(summaries[(0, 1)]["has_river"])

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
                "park_coverage_ratio": 0.0,
                "river_coverage_ratio": 0.0,
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

    def test_summarize_river_feature_matches_returns_zero_without_river(self):
        river_summary = summarize_river_feature_matches_for_grid_cell_contexts(
            [
                {
                    "row_index": 0,
                    "col_index": 0,
                    "north": 10.0,
                    "south": 9.0,
                    "east": 20.0,
                    "west": 19.0,
                },
            ],
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
            ],
        )

        self.assertEqual(
            river_summary,
            {
                "river_cells": 0,
                "river_avg_overlap": 0.0,
                "river_max_overlap": 0.0,
                "river_large_bounds_cells": 0,
                "river_small_overlap_cells": 0,
            },
        )

    def test_summarize_river_feature_matches_counts_normal_river_overlap(self):
        river_summary = summarize_river_feature_matches_for_grid_cell_contexts(
            [
                {
                    "row_index": 0,
                    "col_index": 0,
                    "north": 10.0,
                    "south": 9.0,
                    "east": 20.0,
                    "west": 19.0,
                },
            ],
            [
                {
                    "kind": "river",
                    "bounds": {
                        "north": 9.8,
                        "south": 9.2,
                        "east": 19.8,
                        "west": 19.2,
                    },
                },
            ],
        )

        self.assertEqual(river_summary["river_cells"], 1)
        self.assertAlmostEqual(river_summary["river_avg_overlap"], 0.36)
        self.assertAlmostEqual(river_summary["river_max_overlap"], 0.36)
        self.assertEqual(river_summary["river_large_bounds_cells"], 0)
        self.assertEqual(river_summary["river_small_overlap_cells"], 0)

    def test_summarize_river_feature_matches_counts_large_river_bounds(self):
        river_summary = summarize_river_feature_matches_for_grid_cell_contexts(
            [
                {
                    "row_index": 0,
                    "col_index": 0,
                    "north": 10.0,
                    "south": 9.0,
                    "east": 20.0,
                    "west": 19.0,
                },
            ],
            [
                {
                    "kind": "river",
                    "bounds": {
                        "north": 15.5,
                        "south": 4.5,
                        "east": 19.1,
                        "west": 18.6,
                    },
                },
            ],
        )

        self.assertEqual(river_summary["river_cells"], 1)
        self.assertAlmostEqual(river_summary["river_avg_overlap"], 0.1)
        self.assertAlmostEqual(river_summary["river_max_overlap"], 0.1)
        self.assertEqual(river_summary["river_large_bounds_cells"], 1)
        self.assertEqual(river_summary["river_small_overlap_cells"], 0)

    def test_summarize_river_feature_matches_counts_small_overlap(self):
        river_summary = summarize_river_feature_matches_for_grid_cell_contexts(
            [
                {
                    "row_index": 0,
                    "col_index": 0,
                    "north": 10.0,
                    "south": 9.0,
                    "east": 20.0,
                    "west": 19.0,
                },
            ],
            [
                {
                    "kind": "river",
                    "bounds": {
                        "north": 15.5,
                        "south": 4.5,
                        "east": 19.04,
                        "west": 18.54,
                    },
                },
            ],
        )

        self.assertEqual(river_summary["river_cells"], 0)
        self.assertEqual(river_summary["river_avg_overlap"], 0.0)
        self.assertEqual(river_summary["river_max_overlap"], 0.0)
        self.assertEqual(river_summary["river_large_bounds_cells"], 1)
        self.assertEqual(river_summary["river_small_overlap_cells"], 1)

    def test_summarize_waterway_feature_matches_returns_zero_without_waterway(self):
        waterway_summary = summarize_waterway_feature_matches_for_grid_cell_contexts(
            [
                {
                    "row_index": 0,
                    "col_index": 0,
                    "north": 10.0,
                    "south": 9.0,
                    "east": 20.0,
                    "west": 19.0,
                },
            ],
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
            ],
        )

        self.assertEqual(
            waterway_summary,
            {
                "waterway_river_features": 0,
                "waterway_river_cells": 0,
                "waterway_stream_features": 0,
                "waterway_stream_cells": 0,
                "waterway_canal_features": 0,
                "waterway_canal_cells": 0,
                "waterway_unknown_features": 0,
                "waterway_unknown_cells": 0,
            },
        )

    def test_summarize_waterway_feature_matches_counts_feature_types(self):
        grid_cell_contexts = [
            {
                "row_index": 0,
                "col_index": 0,
                "north": 10.0,
                "south": 9.0,
                "east": 20.0,
                "west": 19.0,
            },
        ]
        map_features = [
            {
                "kind": "river",
                "source_waterway": "river",
                "bounds": {
                    "north": 9.9,
                    "south": 9.8,
                    "east": 19.2,
                    "west": 19.1,
                },
            },
            {
                "kind": "river",
                "source_waterway": "stream",
                "bounds": {
                    "north": 9.7,
                    "south": 9.6,
                    "east": 19.4,
                    "west": 19.3,
                },
            },
            {
                "kind": "river",
                "source_waterway": "canal",
                "bounds": {
                    "north": 9.5,
                    "south": 9.4,
                    "east": 19.6,
                    "west": 19.5,
                },
            },
            {
                "kind": "river",
                "source_waterway": "ditch",
                "bounds": {
                    "north": 9.3,
                    "south": 9.2,
                    "east": 19.8,
                    "west": 19.7,
                },
            },
            {
                "kind": "river",
                "bounds": {
                    "north": 9.2,
                    "south": 9.1,
                    "east": 19.9,
                    "west": 19.8,
                },
            },
        ]

        waterway_summary = summarize_waterway_feature_matches_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )

        self.assertEqual(waterway_summary["waterway_river_features"], 1)
        self.assertEqual(waterway_summary["waterway_stream_features"], 1)
        self.assertEqual(waterway_summary["waterway_canal_features"], 1)
        self.assertEqual(waterway_summary["waterway_unknown_features"], 2)

    def test_summarize_waterway_feature_matches_counts_cells_once_per_type(self):
        waterway_summary = summarize_waterway_feature_matches_for_grid_cell_contexts(
            [
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
            ],
            [
                {
                    "kind": "river",
                    "source_waterway": "canal",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.3,
                        "west": 19.1,
                    },
                },
                {
                    "kind": "river",
                    "source_waterway": "canal",
                    "bounds": {
                        "north": 9.7,
                        "south": 9.6,
                        "east": 19.5,
                        "west": 19.2,
                    },
                },
                {
                    "kind": "river",
                    "source_waterway": "stream",
                    "bounds": {
                        "north": 9.8,
                        "south": 9.2,
                        "east": 20.5,
                        "west": 19.5,
                    },
                },
            ],
        )

        self.assertEqual(waterway_summary["waterway_canal_features"], 2)
        self.assertEqual(waterway_summary["waterway_canal_cells"], 1)
        self.assertEqual(waterway_summary["waterway_stream_features"], 1)
        self.assertEqual(waterway_summary["waterway_stream_cells"], 2)

    def test_summarize_waterway_feature_matches_invalid_input_raises_value_error(self):
        valid_context = {
            "row_index": 0,
            "col_index": 0,
            "north": 10.0,
            "south": 9.0,
            "east": 20.0,
            "west": 19.0,
        }
        valid_feature = {
            "kind": "river",
            "source_waterway": "canal",
            "bounds": {
                "north": 9.9,
                "south": 9.8,
                "east": 19.2,
                "west": 19.1,
            },
        }
        invalid_inputs = (
            (None, []),
            ([None], []),
            ([{**valid_context, "north": 9.0}], []),
            ([valid_context], None),
            ([valid_context], [None]),
            ([valid_context], [{**valid_feature, "bounds": None}]),
        )

        for grid_cell_contexts, map_features in invalid_inputs:
            with self.subTest(
                grid_cell_contexts=grid_cell_contexts,
                map_features=map_features,
            ):
                with self.assertRaises(ValueError):
                    summarize_waterway_feature_matches_for_grid_cell_contexts(
                        grid_cell_contexts,
                        map_features,
                    )

    def map_area_bounds(self):
        return {
            "north": 10.0,
            "south": 9.0,
            "east": 20.0,
            "west": 19.0,
        }

    def test_summarize_waterway_river_bounds_returns_zero_without_river(self):
        bounds_summary = summarize_waterway_river_bounds_for_map_area(
            self.map_area_bounds(),
            [
                {
                    "kind": "river",
                    "source_waterway": "canal",
                    "bounds": {
                        "north": 10.5,
                        "south": 8.5,
                        "east": 20.5,
                        "west": 18.5,
                    },
                },
                {
                    "kind": "building",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
            ],
        )

        self.assertEqual(
            bounds_summary,
            {
                "waterway_river_bounds_features": 0,
                "waterway_river_bounds_intersecting_map_features": 0,
                "waterway_river_bounds_covering_map_features": 0,
                "waterway_river_bounds_large_area_features": 0,
                "waterway_river_bounds_filtered_features": 0,
                "waterway_river_bounds_filtered_cells": 0,
                "waterway_river_bounds_max_area_ratio_to_map": 0.0,
                "waterway_river_bounds_max_height_ratio_to_map": 0.0,
                "waterway_river_bounds_max_width_ratio_to_map": 0.0,
            },
        )

    def test_summarize_waterway_river_bounds_counts_only_river_features(self):
        bounds_summary = summarize_waterway_river_bounds_for_map_area(
            self.map_area_bounds(),
            [
                {
                    "kind": "river",
                    "source_waterway": "river",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
                {
                    "kind": "river",
                    "source_waterway": "river",
                    "bounds": {
                        "north": 9.7,
                        "south": 9.6,
                        "east": 19.4,
                        "west": 19.3,
                    },
                },
                {
                    "kind": "river",
                    "source_waterway": "stream",
                    "bounds": {
                        "north": 9.5,
                        "south": 9.4,
                        "east": 19.6,
                        "west": 19.5,
                    },
                },
                {
                    "kind": "river",
                    "source_waterway": "canal",
                    "bounds": {
                        "north": 9.3,
                        "south": 9.2,
                        "east": 19.8,
                        "west": 19.7,
                    },
                },
            ],
        )

        self.assertEqual(bounds_summary["waterway_river_bounds_features"], 2)

    def test_summarize_waterway_river_bounds_counts_intersections_and_covering(self):
        bounds_summary = summarize_waterway_river_bounds_for_map_area(
            self.map_area_bounds(),
            [
                {
                    "kind": "river",
                    "source_waterway": "river",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
                {
                    "kind": "river",
                    "source_waterway": "river",
                    "bounds": {
                        "north": 11.0,
                        "south": 10.5,
                        "east": 20.0,
                        "west": 19.0,
                    },
                },
                {
                    "kind": "river",
                    "source_waterway": "river",
                    "bounds": {
                        "north": 10.5,
                        "south": 8.5,
                        "east": 20.5,
                        "west": 18.5,
                    },
                },
            ],
        )

        self.assertEqual(
            bounds_summary["waterway_river_bounds_intersecting_map_features"],
            2,
        )
        self.assertEqual(
            bounds_summary["waterway_river_bounds_covering_map_features"],
            1,
        )

    def test_summarize_waterway_river_bounds_tracks_max_size_ratios(self):
        bounds_summary = summarize_waterway_river_bounds_for_map_area(
            self.map_area_bounds(),
            [
                {
                    "kind": "river",
                    "source_waterway": "river",
                    "bounds": {
                        "north": 10.5,
                        "south": 8.5,
                        "east": 20.5,
                        "west": 18.5,
                    },
                },
                {
                    "kind": "river",
                    "source_waterway": "river",
                    "bounds": {
                        "north": 12.0,
                        "south": 9.0,
                        "east": 19.25,
                        "west": 19.0,
                    },
                },
            ],
        )

        self.assertEqual(
            bounds_summary["waterway_river_bounds_large_area_features"],
            1,
        )
        self.assertEqual(
            bounds_summary["waterway_river_bounds_max_area_ratio_to_map"],
            4.0,
        )
        self.assertEqual(
            bounds_summary["waterway_river_bounds_max_height_ratio_to_map"],
            3.0,
        )
        self.assertEqual(
            bounds_summary["waterway_river_bounds_max_width_ratio_to_map"],
            2.0,
        )

    def test_summarize_waterway_river_bounds_counts_large_area_threshold(self):
        bounds_summary = summarize_waterway_river_bounds_for_map_area(
            self.map_area_bounds(),
            [
                {
                    "kind": "river",
                    "source_waterway": "river",
                    "bounds": {
                        "north": 10.0,
                        "south": 9.0,
                        "east": 20.0,
                        "west": 19.0,
                    },
                },
            ],
        )

        self.assertEqual(
            bounds_summary["waterway_river_bounds_large_area_features"],
            1,
        )

    def test_summarize_waterway_river_bounds_counts_filtered_features_and_cells(self):
        bounds_summary = summarize_waterway_river_bounds_for_map_area(
            {
                "north": 10.0,
                "south": 9.0,
                "east": 21.0,
                "west": 19.0,
            },
            [
                {
                    "kind": "river",
                    "source_waterway": "river",
                    "bounds": {
                        "north": 10.0,
                        "south": 9.0,
                        "east": 21.0,
                        "west": 19.0,
                    },
                },
                {
                    "kind": "river",
                    "source_waterway": "river",
                    "bounds": {
                        "north": 9.8,
                        "south": 9.2,
                        "east": 19.8,
                        "west": 19.2,
                    },
                },
            ],
            grid_cell_contexts=[
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
            ],
        )

        self.assertEqual(
            bounds_summary["waterway_river_bounds_filtered_features"],
            1,
        )
        self.assertEqual(
            bounds_summary["waterway_river_bounds_filtered_cells"],
            2,
        )

    def test_summarize_waterway_river_bounds_invalid_input_raises_value_error(self):
        valid_feature = {
            "kind": "river",
            "source_waterway": "river",
            "bounds": {
                "north": 9.9,
                "south": 9.8,
                "east": 19.2,
                "west": 19.1,
            },
        }
        invalid_inputs = (
            (None, []),
            ({"north": 9.0, "south": 10.0, "east": 20.0, "west": 19.0}, []),
            (self.map_area_bounds(), None),
            (self.map_area_bounds(), [None]),
            (self.map_area_bounds(), [{**valid_feature, "bounds": None}]),
        )

        for map_area_bounds, map_features in invalid_inputs:
            with self.subTest(
                map_area_bounds=map_area_bounds,
                map_features=map_features,
            ):
                with self.assertRaises(ValueError):
                    summarize_waterway_river_bounds_for_map_area(
                        map_area_bounds,
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
        self.assertGreater(score, 2.0)
        self.assertLess(score, 2.5)

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

        self.assertGreaterEqual(score, 0.5)
        self.assertLess(score, 1.0)
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

        self.assertGreaterEqual(score, 2.0)
        self.assertLess(score, 2.5)
        self.assertLessEqual(score, 3.0)

    def test_feature_summary_river_coverage_ratio_can_enable_river_score(self):
        score = calculate_initial_score_from_feature_summary(
            {
                "building_count": 20,
                "river_coverage_ratio": 0.06,
            }
        )

        self.assertGreater(score, 1.0)

    def test_feature_summary_has_river_without_coverage_ratio_keeps_compatibility(self):
        score = calculate_initial_score_from_feature_summary(
            {
                "building_count": 20,
                "has_river": True,
            }
        )

        self.assertGreater(score, 1.0)

    def test_feature_summary_park_coverage_ratio_keeps_park_score_compatibility(self):
        score_with_ratio = calculate_initial_score_from_feature_summary(
            {
                "building_count": 20,
                "has_park": True,
                "park_coverage_ratio": 0.02,
            }
        )
        score_without_ratio = calculate_initial_score_from_feature_summary(
            {
                "building_count": 20,
                "has_park": True,
            }
        )

        self.assertEqual(score_with_ratio, score_without_ratio)

    def test_feature_summary_ignores_forest_below_score_threshold(self):
        score_without_forest = calculate_initial_score_from_feature_summary(
            {
                "building_count": 20,
            }
        )
        score_with_small_forest = calculate_initial_score_from_feature_summary(
            {
                "building_count": 20,
                "forest_coverage_ratio": MIN_FOREST_COVERAGE_RATIO_FOR_SCORE - 0.01,
            }
        )

        self.assertEqual(score_with_small_forest, score_without_forest)

    def test_feature_summary_scores_forest_at_score_threshold(self):
        score_without_forest = calculate_initial_score_from_feature_summary(
            {
                "building_count": 20,
            }
        )
        score_with_scored_forest = calculate_initial_score_from_feature_summary(
            {
                "building_count": 20,
                "forest_coverage_ratio": MIN_FOREST_COVERAGE_RATIO_FOR_SCORE,
            }
        )

        self.assertGreater(score_with_scored_forest, score_without_forest)

    def test_feature_summary_forest_threshold_keeps_existing_summary_compatible(self):
        score = calculate_initial_score_from_feature_summary(
            {
                "building_count": 20,
            }
        )

        self.assertGreater(score, 0.0)

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

        self.assertLessEqual(high_score, 3.0)
        self.assertEqual(low_score, 0.0)

    def test_feature_summary_breakdown_returns_expected_keys(self):
        breakdown = calculate_initial_score_breakdown_from_feature_summary(
            {
                "building_count": 20,
                "road_count": 10,
                "has_park": True,
                "has_river": True,
                "is_coastal": True,
                "water_coverage_ratio": 0.1,
                "forest_coverage_ratio": MIN_FOREST_COVERAGE_RATIO_FOR_SCORE,
            }
        )
        expected_keys = {
            "base_score",
            "building_base_bonus",
            "road_base_bonus",
            "diversity_bonus",
            "context_bonus",
            "penalty",
            "raw_score",
            "clamped_score",
            "feature_category_count",
            "has_building",
            "has_road",
            "has_park",
            "has_river",
            "has_water",
            "has_scored_forest",
            "is_coastal",
            "has_park_context",
            "has_river_context",
            "has_forest_context",
            "has_coastal_context",
            "has_water_penalty",
            "has_forest_penalty",
            "has_empty_cell_penalty",
        }

        self.assertEqual(set(breakdown.keys()), expected_keys)

    def test_feature_summary_score_returns_breakdown_clamped_score(self):
        feature_summary = {
            "building_count": 12,
            "road_count": 6,
            "has_park": True,
            "river_coverage_ratio": 0.06,
            "forest_coverage_ratio": MIN_FOREST_COVERAGE_RATIO_FOR_SCORE,
        }
        score = calculate_initial_score_from_feature_summary(feature_summary)
        breakdown = calculate_initial_score_breakdown_from_feature_summary(
            feature_summary
        )

        self.assertEqual(score, breakdown["clamped_score"])

    def test_feature_summary_breakdown_tracks_base_bonuses_and_categories(self):
        breakdown = calculate_initial_score_breakdown_from_feature_summary(
            {
                "building_count": 10,
                "road_count": 5,
                "has_park": True,
                "river_coverage_ratio": MIN_RIVER_COVERAGE_RATIO_FOR_HAS_RIVER,
                "is_coastal": True,
                "water_coverage_ratio": 0.2,
                "forest_coverage_ratio": MIN_FOREST_COVERAGE_RATIO_FOR_SCORE,
            }
        )

        self.assertAlmostEqual(breakdown["building_base_bonus"], 0.2)
        self.assertAlmostEqual(breakdown["road_base_bonus"], 0.0)
        self.assertAlmostEqual(breakdown["base_score"], 0.4)
        self.assertEqual(breakdown["feature_category_count"], 6)
        self.assertTrue(breakdown["has_building"])
        self.assertTrue(breakdown["has_road"])
        self.assertTrue(breakdown["has_park"])
        self.assertTrue(breakdown["has_river"])
        self.assertTrue(breakdown["has_water"])
        self.assertTrue(breakdown["has_scored_forest"])
        self.assertTrue(breakdown["is_coastal"])

    def test_feature_summary_breakdown_does_not_score_roads(self):
        without_road = calculate_initial_score_breakdown_from_feature_summary({})
        with_road = calculate_initial_score_breakdown_from_feature_summary(
            {"road_count": 10}
        )

        self.assertTrue(with_road["has_road"])
        self.assertEqual(with_road["road_base_bonus"], ROAD_BASE_SCORE_MAX_BONUS)
        self.assertEqual(with_road["base_score"], without_road["base_score"])
        self.assertEqual(
            with_road["feature_category_count"],
            without_road["feature_category_count"],
        )

    def test_feature_summary_breakdown_uses_weaker_building_base_bonus(self):
        max_building_breakdown = calculate_initial_score_breakdown_from_feature_summary(
            {"building_count": BUILDING_COUNT_FOR_MAX_BASE_SCORE}
        )
        extra_building_breakdown = (
            calculate_initial_score_breakdown_from_feature_summary(
                {"building_count": BUILDING_COUNT_FOR_MAX_BASE_SCORE * 2}
            )
        )

        self.assertAlmostEqual(max_building_breakdown["base_score"], 0.6)
        self.assertEqual(
            max_building_breakdown["building_base_bonus"],
            BUILDING_BASE_SCORE_MAX_BONUS,
        )
        self.assertEqual(
            extra_building_breakdown["building_base_bonus"],
            BUILDING_BASE_SCORE_MAX_BONUS,
        )
        self.assertAlmostEqual(
            max_building_breakdown["base_score"],
            BASE_INITIAL_SCORE + BUILDING_BASE_SCORE_MAX_BONUS,
        )

    def test_feature_summary_breakdown_tracks_context_and_penalties(self):
        context_breakdown = calculate_initial_score_breakdown_from_feature_summary(
            {
                "building_count": 20,
                "has_park": True,
                "has_river": True,
                "is_coastal": True,
                "forest_coverage_ratio": MIN_FOREST_COVERAGE_RATIO_FOR_SCORE,
            }
        )
        water_breakdown = calculate_initial_score_breakdown_from_feature_summary(
            {
                "water_coverage_ratio": 0.99,
            }
        )
        forest_breakdown = calculate_initial_score_breakdown_from_feature_summary(
            {
                "forest_coverage_ratio": 0.99,
            }
        )

        self.assertTrue(context_breakdown["has_park_context"])
        self.assertTrue(context_breakdown["has_river_context"])
        self.assertTrue(context_breakdown["has_forest_context"])
        self.assertTrue(context_breakdown["has_coastal_context"])
        self.assertTrue(water_breakdown["has_water_penalty"])
        self.assertTrue(water_breakdown["has_empty_cell_penalty"])
        self.assertTrue(forest_breakdown["has_forest_penalty"])
        self.assertTrue(forest_breakdown["has_empty_cell_penalty"])

    def test_invalid_feature_summary_breakdown_raises_value_error(self):
        invalid_summaries = (
            None,
            [],
            {"building_count": -1},
            {"road_count": float("inf")},
            {"water_coverage_ratio": 1.1},
            {"forest_coverage_ratio": -0.1},
            {"park_coverage_ratio": 1.1},
            {"river_coverage_ratio": 1.1},
            {"building_count": True},
        )
        for feature_summary in invalid_summaries:
            with self.subTest(feature_summary=feature_summary):
                with self.assertRaises(ValueError):
                    calculate_initial_score_breakdown_from_feature_summary(
                        feature_summary
                    )

    def test_invalid_feature_summary_raises_value_error(self):
        invalid_summaries = (
            None,
            [],
            {"building_count": -1},
            {"road_count": float("inf")},
            {"water_coverage_ratio": 1.1},
            {"forest_coverage_ratio": -0.1},
            {"park_coverage_ratio": 1.1},
            {"river_coverage_ratio": 1.1},
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
