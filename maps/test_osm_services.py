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
    PARK_WATERFRONT_COMBO_CONTEXT_BONUS,
    ROAD_BASE_SCORE_MAX_BONUS,
    PUBLIC_TRANSPORT_STATION_CONTEXT_BONUS,
    HIGH_CONTEXT_3_CONTEXT_BONUS,
    HIGH_CONTEXT_4_CONTEXT_BONUS,
    HIGH_CONTEXT_5_CONTEXT_BONUS,
    STATION_PROXIMITY_MID_CONTEXT_BONUS,
    STATION_PROXIMITY_NEAR_CONTEXT_BONUS,
    SURFACE_RAILWAY_CONTEXT_BONUS,
    SURFACE_STATION_CONTEXT_BONUS,
    SUBWAY_STATION_CONTEXT_BONUS,
    MOTORWAY_CONTEXT_BONUS,
    TRUNK_CONTEXT_BONUS,
    WATERFRONT_CONTEXT_BONUS,
    build_bounds_from_osm_element,
    build_auto_score_breakdown_from_feature_summary,
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
    classify_expressway_feature_type,
    classify_landmark_feature_type,
    classify_osm_element,
    classify_railway_feature_surface_type,
    classify_station_feature_type,
    determine_initial_score_for_grid_cell,
    fetch_osm_features_from_overpass,
    feature_intersects_grid_cell,
    generate_grid_cells_for_area,
    is_large_waterway_river_bounds_for_map_area,
    parse_overpass_elements_to_map_features,
    summarize_effective_expressway_feature_matches_for_grid_cell_contexts,
    summarize_castle_proximity_for_grid_cell_contexts,
    summarize_expressway_bounds_for_grid_cell_contexts,
    summarize_expressway_feature_matches_for_grid_cell_contexts,
    summarize_landmark_feature_matches_for_grid_cell_contexts,
    summarize_river_feature_matches_for_grid_cell_contexts,
    summarize_railway_feature_matches_for_grid_cell_contexts,
    summarize_station_proximity_for_grid_cell_contexts,
    summarize_station_feature_matches_for_grid_cell_contexts,
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
            'nwr["railway"="station"]',
            'nwr["railway"="halt"]',
            'nwr["station"="subway"]',
            'nwr["public_transport"="station"]',
            'nwr["amenity"="bus_station"]',
            'nwr["railway"="rail"]',
            'nwr["railway"="subway"]',
            'nwr["railway"="light_rail"]',
            'nwr["railway"="tram"]',
            'nwr["highway"="motorway"]',
            'nwr["highway"="motorway_link"]',
            'nwr["highway"="trunk"]',
            'nwr["highway"="trunk_link"]',
            'nwr["tourism"="attraction"]',
            'nwr["tourism"="museum"]',
            'nwr["tourism"="gallery"]',
            'nwr["tourism"="viewpoint"]',
            'nwr["historic"="castle"]',
            'nwr["historic"="monument"]',
            'nwr["historic"="memorial"]',
            'nwr["historic"="ruins"]',
            'nwr["historic"="archaeological_site"]',
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
            {
                "kind": "railway",
                "source_railway": "rail",
                "bounds": {
                    "north": 9.7,
                    "south": 9.3,
                    "east": 20.4,
                    "west": 19.6,
                },
            },
            {
                "kind": "station",
                "source_railway": "station",
                "bounds": {
                    "north": 9.6,
                    "south": 9.4,
                    "east": 20.4,
                    "west": 19.6,
                },
            },
            {
                "kind": "expressway",
                "source_highway": "motorway",
                "bounds": {
                    "north": 9.5,
                    "south": 9.3,
                    "east": 20.4,
                    "west": 19.6,
                },
            },
            {
                "kind": "landmark",
                "source_historic": "castle",
                "bounds": {
                    "north": 9.4,
                    "south": 9.2,
                    "east": 20.4,
                    "west": 19.6,
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
        self.assertEqual(summaries[(0, 0)]["surface_railway_count"], 1)
        self.assertEqual(summaries[(0, 1)]["surface_railway_count"], 1)
        self.assertEqual(summaries.railway_summary["railway_features"], 1)
        self.assertEqual(summaries.railway_summary["surface_railway_cells"], 2)
        self.assertEqual(summaries[(0, 0)]["railway_station_count"], 1)
        self.assertEqual(summaries[(0, 1)]["railway_station_count"], 1)
        self.assertEqual(summaries.station_summary["station_features"], 1)
        self.assertEqual(summaries.station_summary["railway_station_cells"], 2)
        self.assertEqual(
            summaries.station_proximity_summary["station_proximity_features"],
            1,
        )
        self.assertEqual(summaries[(0, 0)]["historic_castle_count"], 1)
        self.assertEqual(summaries[(0, 1)]["historic_castle_count"], 1)
        self.assertEqual(summaries.landmark_summary["landmark_features"], 1)
        self.assertEqual(summaries.landmark_summary["historic_castle_cells"], 2)
        self.assertEqual(summaries.castle_proximity_summary["castle_features"], 1)
        self.assertEqual(summaries[(0, 0)]["motorway_count"], 1)
        self.assertEqual(summaries[(0, 1)]["motorway_count"], 1)
        self.assertEqual(summaries.expressway_summary["expressway_features"], 1)
        self.assertEqual(summaries.expressway_summary["motorway_cells"], 2)
        self.assertEqual(
            summaries.expressway_bounds_summary["expressway_features"],
            1,
        )
        self.assertEqual(summaries.expressway_bounds_summary["motorway_cells"], 2)
        self.assertGreater(
            summaries.expressway_bounds_summary["expressway_max_overlap"],
            0,
        )
        self.assertEqual(
            summaries.effective_expressway_summary["effective_expressway_features"],
            1,
        )
        self.assertEqual(
            summaries.effective_expressway_summary["effective_motorway_cells"],
            2,
        )
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
            ({"railway": "rail"}, "railway"),
            ({"railway": "subway"}, "railway"),
            ({"railway": "light_rail"}, "railway"),
            ({"railway": "tram"}, "railway"),
            ({"railway": "station"}, "station"),
            ({"railway": "halt"}, "station"),
            ({"station": "subway"}, "station"),
            ({"public_transport": "station"}, "station"),
            ({"amenity": "bus_station"}, "station"),
            ({"highway": "motorway"}, "expressway"),
            ({"highway": "motorway_link"}, "expressway"),
            ({"highway": "trunk"}, "expressway"),
            ({"highway": "trunk_link"}, "expressway"),
            ({"tourism": "attraction"}, "landmark"),
            ({"tourism": "museum"}, "landmark"),
            ({"tourism": "gallery"}, "landmark"),
            ({"tourism": "viewpoint"}, "landmark"),
            ({"historic": "castle"}, "landmark"),
            ({"historic": "monument"}, "landmark"),
            ({"historic": "memorial"}, "landmark"),
            ({"historic": "ruins"}, "landmark"),
            ({"historic": "archaeological_site"}, "landmark"),
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
                {"railway": "station", "railway:ref": "A", "highway": "service"},
                "station",
            ),
            (
                {"railway": "rail", "highway": "service", "building": "yes"},
                "railway",
            ),
            (
                {"highway": "motorway", "building": "yes"},
                "expressway",
            ),
            (
                {"tourism": "museum", "building": "yes"},
                "landmark",
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
        self.assertEqual(map_feature["source_highway"], "residential")

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

    def test_build_map_feature_from_osm_element_keeps_railway_source_tags(self):
        map_feature = build_map_feature_from_osm_element(
            {
                "type": "way",
                "id": 901,
                "tags": {
                    "railway": "subway",
                    "tunnel": "yes",
                    "layer": "-1",
                    "bridge": "no",
                },
                "bounds": {
                    "north": 10.0,
                    "south": 9.0,
                    "east": 20.0,
                    "west": 19.0,
                },
            }
        )

        self.assertEqual(map_feature["kind"], "railway")
        self.assertEqual(map_feature["source_railway"], "subway")
        self.assertEqual(map_feature["source_tunnel"], "yes")
        self.assertEqual(map_feature["source_layer"], "-1")
        self.assertEqual(map_feature["source_bridge"], "no")

    def test_build_map_feature_from_osm_element_keeps_station_source_tags(self):
        map_feature = build_map_feature_from_osm_element(
            {
                "type": "node",
                "id": 902,
                "tags": {
                    "railway": "station",
                    "station": "subway",
                    "public_transport": "station",
                    "amenity": "bus_station",
                },
                "bounds": {
                    "north": 10.0,
                    "south": 9.0,
                    "east": 20.0,
                    "west": 19.0,
                },
            }
        )

        self.assertEqual(map_feature["kind"], "station")
        self.assertEqual(map_feature["source_railway"], "station")
        self.assertEqual(map_feature["source_station"], "subway")
        self.assertEqual(map_feature["source_public_transport"], "station")
        self.assertEqual(map_feature["source_amenity"], "bus_station")

    def test_build_map_feature_from_osm_element_keeps_expressway_source_tags(self):
        map_feature = build_map_feature_from_osm_element(
            {
                "type": "way",
                "id": 903,
                "tags": {"highway": "motorway"},
                "bounds": {
                    "north": 10.0,
                    "south": 9.0,
                    "east": 20.0,
                    "west": 19.0,
                },
            }
        )

        self.assertEqual(map_feature["kind"], "expressway")
        self.assertEqual(map_feature["source_highway"], "motorway")

    def test_build_map_feature_from_osm_element_keeps_landmark_source_tags(self):
        map_feature = build_map_feature_from_osm_element(
            {
                "type": "way",
                "id": 904,
                "tags": {"tourism": "museum", "historic": "castle"},
                "bounds": {
                    "north": 10.0,
                    "south": 9.0,
                    "east": 20.0,
                    "west": 19.0,
                },
            }
        )

        self.assertEqual(map_feature["kind"], "landmark")
        self.assertEqual(map_feature["source_tourism"], "museum")
        self.assertEqual(map_feature["source_historic"], "castle")

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

    def test_classify_railway_feature_surface_type_returns_expected_type(self):
        test_cases = (
            ({"source_railway": "subway"}, "underground"),
            ({"source_railway": "rail", "source_tunnel": "yes"}, "underground"),
            ({"source_railway": "rail", "source_tunnel": "true"}, "underground"),
            (
                {
                    "source_railway": "rail",
                    "source_tunnel": "building_passage",
                },
                "underground",
            ),
            ({"source_railway": "rail", "source_layer": "-1"}, "underground"),
            ({"source_railway": "rail"}, "surface"),
            ({"source_railway": "light_rail"}, "surface"),
            ({"source_railway": "tram"}, "surface"),
            ({"source_railway": "rail", "source_layer": "abc"}, "surface"),
            ({"source_railway": "station"}, "unknown"),
            ({}, "unknown"),
        )

        for feature, expected_type in test_cases:
            with self.subTest(feature=feature):
                self.assertEqual(
                    classify_railway_feature_surface_type(feature),
                    expected_type,
                )

    def test_classify_railway_feature_surface_type_invalid_feature_raises_value_error(
        self,
    ):
        for feature in (None, [], "railway"):
            with self.subTest(feature=feature):
                with self.assertRaises(ValueError):
                    classify_railway_feature_surface_type(feature)

    def test_classify_station_feature_type_returns_expected_type(self):
        test_cases = (
            ({"source_railway": "station"}, "railway_station"),
            ({"source_railway": "halt"}, "railway_halt"),
            ({"source_station": "subway"}, "subway_station"),
            ({"source_amenity": "bus_station"}, "bus_station"),
            (
                {"source_public_transport": "station"},
                "public_transport_station",
            ),
            ({}, "unknown"),
        )

        for feature, expected_type in test_cases:
            with self.subTest(feature=feature):
                self.assertEqual(
                    classify_station_feature_type(feature),
                    expected_type,
                )

    def test_classify_station_feature_type_prefers_subway_station(self):
        station_type = classify_station_feature_type(
            {
                "source_railway": "station",
                "source_station": "subway",
                "source_public_transport": "station",
            }
        )

        self.assertEqual(station_type, "subway_station")

    def test_classify_station_feature_type_invalid_feature_raises_value_error(self):
        for feature in (None, [], "station"):
            with self.subTest(feature=feature):
                with self.assertRaises(ValueError):
                    classify_station_feature_type(feature)

    def test_classify_landmark_feature_type_returns_expected_type(self):
        test_cases = (
            ({"source_tourism": "attraction"}, "tourism_attraction"),
            ({"source_tourism": "museum"}, "tourism_museum"),
            ({"source_tourism": "gallery"}, "tourism_gallery"),
            ({"source_tourism": "viewpoint"}, "tourism_viewpoint"),
            ({"source_historic": "castle"}, "historic_castle"),
            ({"source_historic": "monument"}, "historic_monument"),
            ({"source_historic": "memorial"}, "historic_memorial"),
            ({"source_historic": "ruins"}, "historic_ruins"),
            (
                {"source_historic": "archaeological_site"},
                "historic_archaeological_site",
            ),
            ({"source_tourism": "hotel"}, "unknown"),
            ({}, "unknown"),
        )

        for feature, expected_type in test_cases:
            with self.subTest(feature=feature):
                self.assertEqual(
                    classify_landmark_feature_type(feature),
                    expected_type,
                )

    def test_classify_landmark_feature_type_prefers_tourism_type(self):
        landmark_type = classify_landmark_feature_type(
            {
                "source_tourism": "museum",
                "source_historic": "castle",
            }
        )

        self.assertEqual(landmark_type, "tourism_museum")

    def test_classify_landmark_feature_type_invalid_feature_raises_value_error(self):
        for feature in (None, [], "landmark"):
            with self.subTest(feature=feature):
                with self.assertRaises(ValueError):
                    classify_landmark_feature_type(feature)

    def test_classify_expressway_feature_type_returns_expected_type(self):
        test_cases = (
            ({"source_highway": "motorway"}, "motorway"),
            ({"source_highway": "motorway_link"}, "motorway_link"),
            ({"source_highway": "trunk"}, "trunk"),
            ({"source_highway": "trunk_link"}, "trunk_link"),
            ({"source_highway": "residential"}, "unknown"),
            ({}, "unknown"),
        )

        for feature, expected_type in test_cases:
            with self.subTest(feature=feature):
                self.assertEqual(
                    classify_expressway_feature_type(feature),
                    expected_type,
                )

    def test_classify_expressway_feature_type_invalid_feature_raises_value_error(
        self,
    ):
        for feature in (None, [], "expressway"):
            with self.subTest(feature=feature):
                with self.assertRaises(ValueError):
                    classify_expressway_feature_type(feature)

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
        self.assertEqual(summary["surface_railway_count"], 0)
        self.assertEqual(summary["underground_railway_count"], 0)
        self.assertEqual(summary["unknown_railway_count"], 0)
        self.assertEqual(summary["railway_station_count"], 0)
        self.assertEqual(summary["railway_halt_count"], 0)
        self.assertEqual(summary["subway_station_count"], 0)
        self.assertEqual(summary["bus_station_count"], 0)
        self.assertEqual(summary["public_transport_station_count"], 0)
        self.assertEqual(summary["unknown_station_count"], 0)
        self.assertEqual(summary["motorway_count"], 0)
        self.assertEqual(summary["motorway_link_count"], 0)
        self.assertEqual(summary["trunk_count"], 0)
        self.assertEqual(summary["trunk_link_count"], 0)
        self.assertEqual(summary["unknown_expressway_count"], 0)

    def test_build_feature_summary_counts_railways_by_surface_type(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "railway",
                    "source_railway": "rail",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
                {
                    "kind": "railway",
                    "source_railway": "subway",
                    "bounds": {
                        "north": 9.7,
                        "south": 9.6,
                        "east": 19.4,
                        "west": 19.3,
                    },
                },
                {
                    "kind": "railway",
                    "source_railway": "station",
                    "bounds": {
                        "north": 9.5,
                        "south": 9.4,
                        "east": 19.6,
                        "west": 19.5,
                    },
                },
                {
                    "kind": "railway",
                    "source_railway": "rail",
                    "bounds": {
                        "north": 8.9,
                        "south": 8.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
            ],
        )

        self.assertEqual(summary["surface_railway_count"], 1)
        self.assertEqual(summary["underground_railway_count"], 1)
        self.assertEqual(summary["unknown_railway_count"], 1)

    def test_build_feature_summary_underground_and_unknown_railways_do_not_affect_initial_score(
        self,
    ):
        empty_summary = build_feature_summary_for_grid_cell(self.grid_bounds(), [])
        railway_summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "railway",
                    "source_railway": "subway",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
                {
                    "kind": "railway",
                    "source_railway": "station",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
            ],
        )
        empty_breakdown = calculate_initial_score_breakdown_from_feature_summary(
            empty_summary
        )
        railway_breakdown = calculate_initial_score_breakdown_from_feature_summary(
            railway_summary
        )

        self.assertEqual(
            calculate_initial_score_from_feature_summary(railway_summary),
            calculate_initial_score_from_feature_summary(empty_summary),
        )
        for key in ("base_score", "diversity_bonus", "context_bonus", "penalty"):
            with self.subTest(key=key):
                self.assertEqual(railway_breakdown[key], empty_breakdown[key])

    def test_build_feature_summary_counts_stations_by_type(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "station",
                    "source_railway": "station",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
                {
                    "kind": "station",
                    "source_railway": "halt",
                    "bounds": {
                        "north": 9.8,
                        "south": 9.7,
                        "east": 19.3,
                        "west": 19.2,
                    },
                },
                {
                    "kind": "station",
                    "source_station": "subway",
                    "bounds": {
                        "north": 9.7,
                        "south": 9.6,
                        "east": 19.4,
                        "west": 19.3,
                    },
                },
                {
                    "kind": "station",
                    "source_amenity": "bus_station",
                    "bounds": {
                        "north": 9.6,
                        "south": 9.5,
                        "east": 19.5,
                        "west": 19.4,
                    },
                },
                {
                    "kind": "station",
                    "source_public_transport": "station",
                    "bounds": {
                        "north": 9.5,
                        "south": 9.4,
                        "east": 19.6,
                        "west": 19.5,
                    },
                },
                {
                    "kind": "station",
                    "bounds": {
                        "north": 9.4,
                        "south": 9.3,
                        "east": 19.7,
                        "west": 19.6,
                    },
                },
                {
                    "kind": "station",
                    "source_railway": "station",
                    "bounds": {
                        "north": 8.9,
                        "south": 8.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
            ],
        )

        self.assertEqual(summary["railway_station_count"], 1)
        self.assertEqual(summary["railway_halt_count"], 1)
        self.assertEqual(summary["subway_station_count"], 1)
        self.assertEqual(summary["bus_station_count"], 1)
        self.assertEqual(summary["public_transport_station_count"], 1)
        self.assertEqual(summary["unknown_station_count"], 1)
        self.assertEqual(summary["station_cluster_count"], 0)
        self.assertEqual(summary["dense_station_cluster_count"], 0)

    def test_build_feature_summary_counts_station_clusters_by_center_distance(self):
        center_lat = 9.5
        center_lng = 19.5
        station_step = 100 / METERS_PER_DEGREE

        def station_bounds(lat_offset):
            center = center_lat + lat_offset
            return {
                "north": center + 0.0001,
                "south": center - 0.0001,
                "east": center_lng + 0.0001,
                "west": center_lng - 0.0001,
            }

        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "station",
                    "source_railway": "station",
                    "bounds": station_bounds(0),
                },
                {
                    "kind": "station",
                    "source_station": "subway",
                    "bounds": station_bounds(station_step),
                },
                {
                    "kind": "station",
                    "source_public_transport": "station",
                    "bounds": station_bounds(station_step * 2),
                },
                {
                    "kind": "station",
                    "source_amenity": "bus_station",
                    "bounds": station_bounds(station_step * 3),
                },
                {
                    "kind": "station",
                    "bounds": station_bounds(station_step * 4),
                },
            ],
        )

        self.assertEqual(summary["railway_station_count"], 1)
        self.assertEqual(summary["subway_station_count"], 1)
        self.assertEqual(summary["public_transport_station_count"], 1)
        self.assertEqual(summary["bus_station_count"], 1)
        self.assertEqual(summary["unknown_station_count"], 1)
        self.assertEqual(summary["station_cluster_count"], 3)
        self.assertEqual(summary["dense_station_cluster_count"], 3)

    def test_build_feature_summary_counts_landmarks_by_type(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "landmark",
                    "source_tourism": "attraction",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
                {
                    "kind": "landmark",
                    "source_tourism": "museum",
                    "bounds": {
                        "north": 9.8,
                        "south": 9.7,
                        "east": 19.3,
                        "west": 19.2,
                    },
                },
                {
                    "kind": "landmark",
                    "source_tourism": "gallery",
                    "bounds": {
                        "north": 9.7,
                        "south": 9.6,
                        "east": 19.4,
                        "west": 19.3,
                    },
                },
                {
                    "kind": "landmark",
                    "source_tourism": "viewpoint",
                    "bounds": {
                        "north": 9.6,
                        "south": 9.5,
                        "east": 19.5,
                        "west": 19.4,
                    },
                },
                {
                    "kind": "landmark",
                    "source_historic": "castle",
                    "bounds": {
                        "north": 9.5,
                        "south": 9.4,
                        "east": 19.6,
                        "west": 19.5,
                    },
                },
                {
                    "kind": "landmark",
                    "source_historic": "monument",
                    "bounds": {
                        "north": 9.4,
                        "south": 9.3,
                        "east": 19.7,
                        "west": 19.6,
                    },
                },
                {
                    "kind": "landmark",
                    "source_historic": "memorial",
                    "bounds": {
                        "north": 9.3,
                        "south": 9.2,
                        "east": 19.8,
                        "west": 19.7,
                    },
                },
                {
                    "kind": "landmark",
                    "source_historic": "ruins",
                    "bounds": {
                        "north": 9.2,
                        "south": 9.1,
                        "east": 19.9,
                        "west": 19.8,
                    },
                },
                {
                    "kind": "landmark",
                    "source_historic": "archaeological_site",
                    "bounds": {
                        "north": 9.1,
                        "south": 9.0,
                        "east": 20.0,
                        "west": 19.9,
                    },
                },
                {
                    "kind": "landmark",
                    "source_tourism": "hotel",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.8,
                        "west": 19.7,
                    },
                },
                {
                    "kind": "landmark",
                    "source_historic": "castle",
                    "bounds": {
                        "north": 8.9,
                        "south": 8.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
            ],
        )

        self.assertEqual(summary["tourism_attraction_count"], 1)
        self.assertEqual(summary["tourism_museum_count"], 1)
        self.assertEqual(summary["tourism_gallery_count"], 1)
        self.assertEqual(summary["tourism_viewpoint_count"], 1)
        self.assertEqual(summary["historic_castle_count"], 1)
        self.assertEqual(summary["historic_monument_count"], 1)
        self.assertEqual(summary["historic_memorial_count"], 1)
        self.assertEqual(summary["historic_ruins_count"], 1)
        self.assertEqual(summary["historic_archaeological_site_count"], 1)
        self.assertEqual(summary["unknown_landmark_count"], 1)

    def test_build_feature_summary_landmarks_add_initial_score_context_bonus(self):
        empty_summary = build_feature_summary_for_grid_cell(self.grid_bounds(), [])
        landmark_summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "landmark",
                    "source_tourism": "attraction",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
            ],
        )
        empty_breakdown = calculate_initial_score_breakdown_from_feature_summary(
            empty_summary
        )
        landmark_breakdown = calculate_initial_score_breakdown_from_feature_summary(
            landmark_summary
        )

        self.assertTrue(landmark_breakdown["has_landmark_context"])
        self.assertEqual(landmark_breakdown["landmark_context_bonus"], 0.35)
        self.assertEqual(
            landmark_breakdown["tourism_attraction_context_bonus"],
            0.35,
        )
        self.assertAlmostEqual(
            landmark_breakdown["context_bonus"],
            empty_breakdown["context_bonus"] + 0.35,
        )
        for key in ("base_score", "diversity_bonus", "penalty"):
            with self.subTest(key=key):
                self.assertEqual(landmark_breakdown[key], empty_breakdown[key])
        self.assertEqual(
            calculate_initial_score_from_feature_summary(landmark_summary),
            landmark_breakdown["clamped_score"],
        )

    def test_build_feature_summary_sets_castle_proximity_for_neighbor_cell(self):
        grid_cell_bounds = {
            "north": 10.0001,
            "south": 9.9999,
            "east": 20.0001,
            "west": 19.9999,
        }
        castle_center_lat = 10.0 + (300 / METERS_PER_DEGREE)
        summary = build_feature_summary_for_grid_cell(
            grid_cell_bounds,
            [
                {
                    "kind": "landmark",
                    "source_historic": "castle",
                    "bounds": {
                        "north": castle_center_lat + 0.00001,
                        "south": castle_center_lat - 0.00001,
                        "east": 20.00001,
                        "west": 19.99999,
                    },
                },
            ],
        )

        self.assertEqual(summary["historic_castle_count"], 0)
        self.assertEqual(summary["castle_near_proximity_count"], 0)
        self.assertEqual(summary["castle_mid_proximity_count"], 1)
        self.assertEqual(summary["castle_far_proximity_count"], 0)

    def test_build_feature_summary_sets_station_proximity_for_neighbor_cell(self):
        grid_cell_bounds = {
            "north": 10.0001,
            "south": 9.9999,
            "east": 20.0001,
            "west": 19.9999,
        }
        station_center_lat = 10.0 + (200 / METERS_PER_DEGREE)
        summary = build_feature_summary_for_grid_cell(
            grid_cell_bounds,
            [
                {
                    "kind": "station",
                    "source_railway": "station",
                    "bounds": {
                        "north": station_center_lat + 0.00001,
                        "south": station_center_lat - 0.00001,
                        "east": 20.00001,
                        "west": 19.99999,
                    },
                },
            ],
        )

        self.assertEqual(summary["railway_station_count"], 0)
        self.assertEqual(summary["station_proximity_near_count"], 0)
        self.assertEqual(summary["station_proximity_mid_count"], 1)

    def test_build_feature_summary_counts_expressways_by_type(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "expressway",
                    "source_highway": "motorway",
                    "bounds": {
                        "north": 9.9,
                        "south": 9.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
                {
                    "kind": "expressway",
                    "source_highway": "motorway_link",
                    "bounds": {
                        "north": 9.8,
                        "south": 9.7,
                        "east": 19.3,
                        "west": 19.2,
                    },
                },
                {
                    "kind": "expressway",
                    "source_highway": "trunk",
                    "bounds": {
                        "north": 9.7,
                        "south": 9.6,
                        "east": 19.4,
                        "west": 19.3,
                    },
                },
                {
                    "kind": "expressway",
                    "source_highway": "trunk_link",
                    "bounds": {
                        "north": 9.6,
                        "south": 9.5,
                        "east": 19.5,
                        "west": 19.4,
                    },
                },
                {
                    "kind": "expressway",
                    "source_highway": "residential",
                    "bounds": {
                        "north": 9.5,
                        "south": 9.4,
                        "east": 19.6,
                        "west": 19.5,
                    },
                },
                {
                    "kind": "expressway",
                    "source_highway": "motorway",
                    "bounds": {
                        "north": 8.9,
                        "south": 8.8,
                        "east": 19.2,
                        "west": 19.1,
                    },
                },
            ],
        )

        self.assertEqual(summary["motorway_count"], 1)
        self.assertEqual(summary["motorway_link_count"], 1)
        self.assertEqual(summary["trunk_count"], 1)
        self.assertEqual(summary["trunk_link_count"], 1)
        self.assertEqual(summary["unknown_expressway_count"], 1)

    def test_build_feature_summary_excludes_large_bounds_expressways(self):
        summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "expressway",
                    "source_highway": "motorway",
                    "bounds": {
                        "north": 15.5,
                        "south": 4.5,
                        "east": 19.1,
                        "west": 18.9,
                    },
                },
                {
                    "kind": "expressway",
                    "source_highway": "trunk",
                    "bounds": {
                        "north": 9.5,
                        "south": 9.0,
                        "east": 19.5,
                        "west": 19.0,
                    },
                },
            ],
        )

        self.assertEqual(summary["motorway_count"], 0)
        self.assertEqual(summary["trunk_count"], 1)

    def test_build_feature_summary_large_and_unknown_expressways_do_not_affect_initial_score(
        self,
    ):
        empty_summary = build_feature_summary_for_grid_cell(self.grid_bounds(), [])
        expressway_summary = build_feature_summary_for_grid_cell(
            self.grid_bounds(),
            [
                {
                    "kind": "expressway",
                    "source_highway": "motorway",
                    "bounds": {
                        "north": 15.5,
                        "south": 4.5,
                        "east": 19.1,
                        "west": 18.9,
                    },
                },
                {
                    "kind": "expressway",
                    "source_highway": "residential",
                    "bounds": {
                        "north": 9.8,
                        "south": 9.7,
                        "east": 19.3,
                        "west": 19.2,
                    },
                },
            ],
        )
        empty_breakdown = calculate_initial_score_breakdown_from_feature_summary(
            empty_summary
        )
        expressway_breakdown = calculate_initial_score_breakdown_from_feature_summary(
            expressway_summary
        )

        self.assertEqual(
            calculate_initial_score_from_feature_summary(expressway_summary),
            calculate_initial_score_from_feature_summary(empty_summary),
        )
        self.assertEqual(expressway_summary["motorway_count"], 0)
        self.assertEqual(expressway_summary["unknown_expressway_count"], 1)
        for key in ("base_score", "diversity_bonus", "context_bonus", "penalty"):
            with self.subTest(key=key):
                self.assertEqual(
                    expressway_breakdown[key],
                    empty_breakdown[key],
                )

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
                "surface_railway_count": 0,
                "underground_railway_count": 0,
                "unknown_railway_count": 0,
                "railway_station_count": 0,
                "railway_halt_count": 0,
                "subway_station_count": 0,
                "bus_station_count": 0,
                "public_transport_station_count": 0,
                "unknown_station_count": 0,
                "station_cluster_count": 0,
                "dense_station_cluster_count": 0,
                "station_proximity_near_count": 0,
                "station_proximity_mid_count": 0,
                "motorway_count": 0,
                "motorway_link_count": 0,
                "trunk_count": 0,
                "trunk_link_count": 0,
                "unknown_expressway_count": 0,
                "tourism_attraction_count": 0,
                "tourism_museum_count": 0,
                "tourism_gallery_count": 0,
                "tourism_viewpoint_count": 0,
                "historic_castle_count": 0,
                "historic_monument_count": 0,
                "historic_memorial_count": 0,
                "historic_ruins_count": 0,
                "historic_archaeological_site_count": 0,
                "unknown_landmark_count": 0,
                "castle_near_proximity_count": 0,
                "castle_mid_proximity_count": 0,
                "castle_far_proximity_count": 0,
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
                "surface_railway_count": 0,
                "underground_railway_count": 0,
                "unknown_railway_count": 0,
                "railway_station_count": 0,
                "railway_halt_count": 0,
                "subway_station_count": 0,
                "bus_station_count": 0,
                "public_transport_station_count": 0,
                "unknown_station_count": 0,
                "station_cluster_count": 0,
                "dense_station_cluster_count": 0,
                "station_proximity_near_count": 0,
                "station_proximity_mid_count": 0,
                "motorway_count": 0,
                "motorway_link_count": 0,
                "trunk_count": 0,
                "trunk_link_count": 0,
                "unknown_expressway_count": 0,
                "tourism_attraction_count": 0,
                "tourism_museum_count": 0,
                "tourism_gallery_count": 0,
                "tourism_viewpoint_count": 0,
                "historic_castle_count": 0,
                "historic_monument_count": 0,
                "historic_memorial_count": 0,
                "historic_ruins_count": 0,
                "historic_archaeological_site_count": 0,
                "unknown_landmark_count": 0,
                "castle_near_proximity_count": 0,
                "castle_mid_proximity_count": 0,
                "castle_far_proximity_count": 0,
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
                "surface_railway_count": 0,
                "underground_railway_count": 0,
                "unknown_railway_count": 0,
                "railway_station_count": 0,
                "railway_halt_count": 0,
                "subway_station_count": 0,
                "bus_station_count": 0,
                "public_transport_station_count": 0,
                "unknown_station_count": 0,
                "station_cluster_count": 0,
                "dense_station_cluster_count": 0,
                "station_proximity_near_count": 0,
                "station_proximity_mid_count": 0,
                "motorway_count": 0,
                "motorway_link_count": 0,
                "trunk_count": 0,
                "trunk_link_count": 0,
                "unknown_expressway_count": 0,
                "tourism_attraction_count": 0,
                "tourism_museum_count": 0,
                "tourism_gallery_count": 0,
                "tourism_viewpoint_count": 0,
                "historic_castle_count": 0,
                "historic_monument_count": 0,
                "historic_memorial_count": 0,
                "historic_ruins_count": 0,
                "historic_archaeological_site_count": 0,
                "unknown_landmark_count": 0,
                "castle_near_proximity_count": 0,
                "castle_mid_proximity_count": 0,
                "castle_far_proximity_count": 0,
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

    def test_summarize_railway_feature_matches_returns_zero_without_railway(self):
        railway_summary = summarize_railway_feature_matches_for_grid_cell_contexts(
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
            railway_summary,
            {
                "railway_features": 0,
                "surface_railway_features": 0,
                "underground_railway_features": 0,
                "unknown_railway_features": 0,
                "railway_cells": 0,
                "surface_railway_cells": 0,
                "underground_railway_cells": 0,
                "unknown_railway_cells": 0,
            },
        )

    def test_summarize_railway_feature_matches_counts_features_and_cells(self):
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
                "kind": "railway",
                "source_railway": "rail",
                "bounds": {
                    "north": 9.8,
                    "south": 9.2,
                    "east": 20.2,
                    "west": 19.8,
                },
            },
            {
                "kind": "railway",
                "source_railway": "subway",
                "bounds": {
                    "north": 9.7,
                    "south": 9.3,
                    "east": 20.8,
                    "west": 20.2,
                },
            },
            {
                "kind": "railway",
                "source_railway": "station",
                "bounds": {
                    "north": 9.6,
                    "south": 9.4,
                    "east": 19.7,
                    "west": 19.3,
                },
            },
        ]

        railway_summary = summarize_railway_feature_matches_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )

        self.assertEqual(railway_summary["railway_features"], 3)
        self.assertEqual(railway_summary["surface_railway_features"], 1)
        self.assertEqual(railway_summary["underground_railway_features"], 1)
        self.assertEqual(railway_summary["unknown_railway_features"], 1)
        self.assertEqual(railway_summary["railway_cells"], 2)
        self.assertEqual(railway_summary["surface_railway_cells"], 2)
        self.assertEqual(railway_summary["underground_railway_cells"], 1)
        self.assertEqual(railway_summary["unknown_railway_cells"], 1)

    def test_summarize_railway_feature_matches_invalid_input_raises_value_error(self):
        valid_context = {
            "row_index": 0,
            "col_index": 0,
            "north": 10.0,
            "south": 9.0,
            "east": 20.0,
            "west": 19.0,
        }
        valid_feature = {
            "kind": "railway",
            "source_railway": "rail",
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
                    summarize_railway_feature_matches_for_grid_cell_contexts(
                        grid_cell_contexts,
                        map_features,
                    )

    def test_summarize_station_feature_matches_returns_zero_without_station(self):
        station_summary = summarize_station_feature_matches_for_grid_cell_contexts(
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
            station_summary,
            {
                "station_features": 0,
                "railway_station_features": 0,
                "railway_halt_features": 0,
                "subway_station_features": 0,
                "bus_station_features": 0,
                "public_transport_station_features": 0,
                "unknown_station_features": 0,
                "station_cells": 0,
                "railway_station_cells": 0,
                "railway_halt_cells": 0,
                "subway_station_cells": 0,
                "bus_station_cells": 0,
                "public_transport_station_cells": 0,
                "unknown_station_cells": 0,
                "station_cluster_cells": 0,
                "dense_station_cluster_cells": 0,
                "major_station_cluster_cells": 0,
                "station_cluster_count_avg": 0.0,
                "station_cluster_count_max": 0,
                "dense_station_cluster_count_max": 0,
                "major_station_cluster_count_max": 0,
            },
        )

    def test_summarize_station_feature_matches_counts_features_and_cells(self):
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
                "kind": "station",
                "source_railway": "station",
                "bounds": {
                    "north": 9.8,
                    "south": 9.2,
                    "east": 20.2,
                    "west": 19.8,
                },
            },
            {
                "kind": "station",
                "source_railway": "halt",
                "bounds": {
                    "north": 9.7,
                    "south": 9.3,
                    "east": 20.8,
                    "west": 20.2,
                },
            },
            {
                "kind": "station",
                "source_station": "subway",
                "bounds": {
                    "north": 9.6,
                    "south": 9.4,
                    "east": 19.7,
                    "west": 19.3,
                },
            },
            {
                "kind": "station",
                "source_amenity": "bus_station",
                "bounds": {
                    "north": 9.6,
                    "south": 9.4,
                    "east": 20.7,
                    "west": 20.3,
                },
            },
            {
                "kind": "station",
                "source_public_transport": "station",
                "bounds": {
                    "north": 8.8,
                    "south": 8.6,
                    "east": 19.7,
                    "west": 19.3,
                },
            },
            {
                "kind": "station",
                "bounds": {
                    "north": 9.5,
                    "south": 9.4,
                    "east": 19.7,
                    "west": 19.3,
                },
            },
        ]

        station_summary = summarize_station_feature_matches_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )

        self.assertEqual(station_summary["station_features"], 6)
        self.assertEqual(station_summary["railway_station_features"], 1)
        self.assertEqual(station_summary["railway_halt_features"], 1)
        self.assertEqual(station_summary["subway_station_features"], 1)
        self.assertEqual(station_summary["bus_station_features"], 1)
        self.assertEqual(station_summary["public_transport_station_features"], 1)
        self.assertEqual(station_summary["unknown_station_features"], 1)
        self.assertEqual(station_summary["station_cells"], 2)
        self.assertEqual(station_summary["railway_station_cells"], 2)
        self.assertEqual(station_summary["railway_halt_cells"], 1)
        self.assertEqual(station_summary["subway_station_cells"], 1)
        self.assertEqual(station_summary["bus_station_cells"], 1)
        self.assertEqual(station_summary["public_transport_station_cells"], 0)
        self.assertEqual(station_summary["unknown_station_cells"], 1)
        self.assertEqual(station_summary["station_cluster_cells"], 0)
        self.assertEqual(station_summary["dense_station_cluster_cells"], 0)
        self.assertEqual(station_summary["major_station_cluster_cells"], 0)
        self.assertEqual(station_summary["station_cluster_count_avg"], 0.0)
        self.assertEqual(station_summary["station_cluster_count_max"], 0)
        self.assertEqual(station_summary["dense_station_cluster_count_max"], 0)
        self.assertEqual(station_summary["major_station_cluster_count_max"], 0)

    def test_summarize_station_feature_matches_logs_center_distance_clusters(self):
        center_lat = 9.5
        center_lng = 19.5
        station_step = 100 / METERS_PER_DEGREE
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

        def station_bounds(lat_offset):
            center = center_lat + lat_offset
            return {
                "north": center + 0.0001,
                "south": center - 0.0001,
                "east": center_lng + 0.0001,
                "west": center_lng - 0.0001,
            }

        map_features = [
            {
                "kind": "station",
                "source_railway": "station",
                "bounds": station_bounds(0),
            },
            {
                "kind": "station",
                "source_railway": "halt",
                "bounds": station_bounds(station_step),
            },
            {
                "kind": "station",
                "source_station": "subway",
                "bounds": station_bounds(station_step * 2),
            },
            {
                "kind": "station",
                "source_public_transport": "station",
                "bounds": station_bounds(station_step * 3),
            },
            {
                "kind": "station",
                "source_amenity": "bus_station",
                "bounds": station_bounds(station_step * 4),
            },
            {
                "kind": "station",
                "bounds": station_bounds(station_step * 5),
            },
        ]

        station_summary = summarize_station_feature_matches_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )

        self.assertEqual(station_summary["station_cluster_cells"], 1)
        self.assertEqual(station_summary["dense_station_cluster_cells"], 1)
        self.assertEqual(station_summary["major_station_cluster_cells"], 1)
        self.assertEqual(station_summary["station_cluster_count_avg"], 4.0)
        self.assertEqual(station_summary["station_cluster_count_max"], 4)
        self.assertEqual(station_summary["dense_station_cluster_count_max"], 4)
        self.assertEqual(station_summary["major_station_cluster_count_max"], 4)

    def test_summarize_station_feature_matches_excludes_unscored_station_clusters(
        self,
    ):
        center_lat = 9.5
        center_lng = 19.5
        station_step = 100 / METERS_PER_DEGREE

        def station_bounds(lat_offset):
            center = center_lat + lat_offset
            return {
                "north": center + 0.0001,
                "south": center - 0.0001,
                "east": center_lng + 0.0001,
                "west": center_lng - 0.0001,
            }

        station_summary = summarize_station_feature_matches_for_grid_cell_contexts(
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
                    "kind": "station",
                    "source_amenity": "bus_station",
                    "bounds": station_bounds(0),
                },
                {
                    "kind": "station",
                    "bounds": station_bounds(station_step),
                },
            ],
        )

        self.assertEqual(station_summary["station_cluster_cells"], 0)
        self.assertEqual(station_summary["dense_station_cluster_cells"], 0)
        self.assertEqual(station_summary["major_station_cluster_cells"], 0)
        self.assertEqual(station_summary["station_cluster_count_max"], 0)
        self.assertEqual(station_summary["dense_station_cluster_count_max"], 0)
        self.assertEqual(station_summary["major_station_cluster_count_max"], 0)

    def test_summarize_station_proximity_returns_zero_without_scored_station(self):
        station_proximity_summary = summarize_station_proximity_for_grid_cell_contexts(
            [
                {
                    "row_index": 0,
                    "col_index": 0,
                    "north": 10.0,
                    "south": 9.99,
                    "east": 20.0,
                    "west": 19.99,
                },
            ],
            [
                {
                    "kind": "station",
                    "source_amenity": "bus_station",
                    "bounds": {
                        "north": 10.0,
                        "south": 9.99,
                        "east": 20.0,
                        "west": 19.99,
                    },
                },
                {
                    "kind": "station",
                    "source_station": "subway",
                    "bounds": {
                        "north": 10.0,
                        "south": 9.99,
                        "east": 20.0,
                        "west": 19.99,
                    },
                },
                {
                    "kind": "station",
                    "bounds": {
                        "north": 10.0,
                        "south": 9.99,
                        "east": 20.0,
                        "west": 19.99,
                    },
                },
            ],
        )

        self.assertEqual(
            station_proximity_summary,
            {
                "station_proximity_features": 0,
                "station_proximity_near_cells": 0,
                "station_proximity_mid_cells": 0,
                "station_proximity_cells": 0,
                "station_proximity_station_cells": 0,
                "station_proximity_non_station_cells": 0,
                "station_proximity_min_distance_m": 0.0,
                "station_proximity_avg_distance_m": 0.0,
                "station_proximity_max_distance_m": 0.0,
            },
        )

    def test_summarize_station_proximity_counts_distance_bands_and_station_cells(
        self,
    ):
        station_center_lat = 10.0
        station_center_lng = 20.0
        distance_offsets = (
            0,
            200 / METERS_PER_DEGREE,
            350 / METERS_PER_DEGREE,
        )

        def grid_cell_context(index, lat_offset):
            center_lat = station_center_lat + lat_offset
            return {
                "row_index": 0,
                "col_index": index,
                "north": center_lat + 0.00001,
                "south": center_lat - 0.00001,
                "east": station_center_lng + 0.00001,
                "west": station_center_lng - 0.00001,
            }

        station_proximity_summary = summarize_station_proximity_for_grid_cell_contexts(
            [
                grid_cell_context(index, lat_offset)
                for index, lat_offset in enumerate(distance_offsets)
            ],
            [
                {
                    "kind": "station",
                    "source_railway": "station",
                    "bounds": {
                        "north": station_center_lat + 0.00001,
                        "south": station_center_lat - 0.00001,
                        "east": station_center_lng + 0.00001,
                        "west": station_center_lng - 0.00001,
                    },
                },
                {
                    "kind": "station",
                    "source_amenity": "bus_station",
                    "bounds": {
                        "north": station_center_lat + 0.00001,
                        "south": station_center_lat - 0.00001,
                        "east": station_center_lng + 0.00001,
                        "west": station_center_lng - 0.00001,
                    },
                },
            ],
        )

        self.assertEqual(station_proximity_summary["station_proximity_features"], 1)
        self.assertEqual(
            station_proximity_summary["station_proximity_near_cells"],
            1,
        )
        self.assertEqual(
            station_proximity_summary["station_proximity_mid_cells"],
            1,
        )
        self.assertEqual(station_proximity_summary["station_proximity_cells"], 2)
        self.assertEqual(
            station_proximity_summary["station_proximity_station_cells"],
            1,
        )
        self.assertEqual(
            station_proximity_summary["station_proximity_non_station_cells"],
            1,
        )
        self.assertAlmostEqual(
            station_proximity_summary["station_proximity_min_distance_m"],
            0.0,
        )
        self.assertAlmostEqual(
            station_proximity_summary["station_proximity_avg_distance_m"],
            100.0,
        )
        self.assertAlmostEqual(
            station_proximity_summary["station_proximity_max_distance_m"],
            200.0,
        )

    def test_summarize_landmark_feature_matches_returns_zero_without_landmark(self):
        landmark_summary = summarize_landmark_feature_matches_for_grid_cell_contexts(
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
            landmark_summary,
            {
                "landmark_features": 0,
                "landmark_cells": 0,
                "tourism_attraction_features": 0,
                "tourism_attraction_cells": 0,
                "tourism_museum_features": 0,
                "tourism_museum_cells": 0,
                "tourism_gallery_features": 0,
                "tourism_gallery_cells": 0,
                "tourism_viewpoint_features": 0,
                "tourism_viewpoint_cells": 0,
                "historic_castle_features": 0,
                "historic_castle_cells": 0,
                "historic_monument_features": 0,
                "historic_monument_cells": 0,
                "historic_memorial_features": 0,
                "historic_memorial_cells": 0,
                "historic_ruins_features": 0,
                "historic_ruins_cells": 0,
                "historic_archaeological_site_features": 0,
                "historic_archaeological_site_cells": 0,
                "unknown_landmark_features": 0,
                "unknown_landmark_cells": 0,
            },
        )

    def test_summarize_landmark_feature_matches_counts_features_and_cells(self):
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
                "kind": "landmark",
                "source_tourism": "attraction",
                "bounds": {
                    "north": 9.8,
                    "south": 9.2,
                    "east": 20.2,
                    "west": 19.8,
                },
            },
            {
                "kind": "landmark",
                "source_tourism": "museum",
                "bounds": {
                    "north": 9.7,
                    "south": 9.3,
                    "east": 20.8,
                    "west": 20.2,
                },
            },
            {
                "kind": "landmark",
                "source_tourism": "gallery",
                "bounds": {
                    "north": 9.6,
                    "south": 9.4,
                    "east": 19.7,
                    "west": 19.3,
                },
            },
            {
                "kind": "landmark",
                "source_tourism": "viewpoint",
                "bounds": {
                    "north": 9.5,
                    "south": 9.4,
                    "east": 20.7,
                    "west": 20.3,
                },
            },
            {
                "kind": "landmark",
                "source_historic": "castle",
                "bounds": {
                    "north": 9.4,
                    "south": 9.3,
                    "east": 19.7,
                    "west": 19.3,
                },
            },
            {
                "kind": "landmark",
                "source_historic": "monument",
                "bounds": {
                    "north": 9.3,
                    "south": 9.2,
                    "east": 19.7,
                    "west": 19.3,
                },
            },
            {
                "kind": "landmark",
                "source_historic": "memorial",
                "bounds": {
                    "north": 9.2,
                    "south": 9.1,
                    "east": 19.7,
                    "west": 19.3,
                },
            },
            {
                "kind": "landmark",
                "source_historic": "ruins",
                "bounds": {
                    "north": 9.1,
                    "south": 9.0,
                    "east": 19.7,
                    "west": 19.3,
                },
            },
            {
                "kind": "landmark",
                "source_historic": "archaeological_site",
                "bounds": {
                    "north": 8.9,
                    "south": 8.8,
                    "east": 19.7,
                    "west": 19.3,
                },
            },
            {
                "kind": "landmark",
                "source_tourism": "hotel",
                "bounds": {
                    "north": 9.1,
                    "south": 9.0,
                    "east": 20.7,
                    "west": 20.3,
                },
            },
        ]

        landmark_summary = summarize_landmark_feature_matches_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )

        self.assertEqual(landmark_summary["landmark_features"], 10)
        self.assertEqual(landmark_summary["landmark_cells"], 2)
        self.assertEqual(landmark_summary["tourism_attraction_features"], 1)
        self.assertEqual(landmark_summary["tourism_attraction_cells"], 2)
        self.assertEqual(landmark_summary["tourism_museum_features"], 1)
        self.assertEqual(landmark_summary["tourism_museum_cells"], 1)
        self.assertEqual(landmark_summary["tourism_gallery_features"], 1)
        self.assertEqual(landmark_summary["tourism_gallery_cells"], 1)
        self.assertEqual(landmark_summary["tourism_viewpoint_features"], 1)
        self.assertEqual(landmark_summary["tourism_viewpoint_cells"], 1)
        self.assertEqual(landmark_summary["historic_castle_features"], 1)
        self.assertEqual(landmark_summary["historic_castle_cells"], 1)
        self.assertEqual(landmark_summary["historic_monument_features"], 1)
        self.assertEqual(landmark_summary["historic_monument_cells"], 1)
        self.assertEqual(landmark_summary["historic_memorial_features"], 1)
        self.assertEqual(landmark_summary["historic_memorial_cells"], 1)
        self.assertEqual(landmark_summary["historic_ruins_features"], 1)
        self.assertEqual(landmark_summary["historic_ruins_cells"], 1)
        self.assertEqual(
            landmark_summary["historic_archaeological_site_features"],
            1,
        )
        self.assertEqual(landmark_summary["historic_archaeological_site_cells"], 0)
        self.assertEqual(landmark_summary["unknown_landmark_features"], 1)
        self.assertEqual(landmark_summary["unknown_landmark_cells"], 1)

    def test_summarize_castle_proximity_returns_zero_without_castle(self):
        castle_summary = summarize_castle_proximity_for_grid_cell_contexts(
            [
                {
                    "row_index": 0,
                    "col_index": 0,
                    "north": 10.0,
                    "south": 9.99,
                    "east": 20.0,
                    "west": 19.99,
                },
            ],
            [
                {
                    "kind": "landmark",
                    "source_historic": "monument",
                    "bounds": {
                        "north": 10.0,
                        "south": 9.99,
                        "east": 20.0,
                        "west": 19.99,
                    },
                },
            ],
        )

        self.assertEqual(
            castle_summary,
            {
                "castle_features": 0,
                "castle_near_cells": 0,
                "castle_mid_cells": 0,
                "castle_far_cells": 0,
                "castle_proximity_cells": 0,
                "castle_min_distance_m": 0.0,
                "castle_avg_distance_m": 0.0,
                "castle_max_distance_m": 0.0,
            },
        )

    def test_summarize_castle_proximity_counts_non_overlapping_distance_bands(self):
        castle_center_lat = 10.0
        castle_center_lng = 20.0
        distance_offsets = (
            0,
            300 / METERS_PER_DEGREE,
            600 / METERS_PER_DEGREE,
            900 / METERS_PER_DEGREE,
        )

        def grid_cell_context(index, lat_offset):
            center_lat = castle_center_lat + lat_offset
            return {
                "row_index": 0,
                "col_index": index,
                "north": center_lat + 0.00001,
                "south": center_lat - 0.00001,
                "east": castle_center_lng + 0.00001,
                "west": castle_center_lng - 0.00001,
            }

        castle_summary = summarize_castle_proximity_for_grid_cell_contexts(
            [
                grid_cell_context(index, lat_offset)
                for index, lat_offset in enumerate(distance_offsets)
            ],
            [
                {
                    "kind": "landmark",
                    "source_historic": "castle",
                    "bounds": {
                        "north": castle_center_lat + 0.00001,
                        "south": castle_center_lat - 0.00001,
                        "east": castle_center_lng + 0.00001,
                        "west": castle_center_lng - 0.00001,
                    },
                },
                {
                    "kind": "landmark",
                    "source_tourism": "viewpoint",
                    "bounds": {
                        "north": castle_center_lat + 0.00001,
                        "south": castle_center_lat - 0.00001,
                        "east": castle_center_lng + 0.00001,
                        "west": castle_center_lng - 0.00001,
                    },
                },
            ],
        )

        self.assertEqual(castle_summary["castle_features"], 1)
        self.assertEqual(castle_summary["castle_near_cells"], 1)
        self.assertEqual(castle_summary["castle_mid_cells"], 1)
        self.assertEqual(castle_summary["castle_far_cells"], 1)
        self.assertEqual(castle_summary["castle_proximity_cells"], 3)
        self.assertAlmostEqual(castle_summary["castle_min_distance_m"], 0.0)
        self.assertAlmostEqual(castle_summary["castle_avg_distance_m"], 300.0)
        self.assertAlmostEqual(castle_summary["castle_max_distance_m"], 600.0)

    def test_summarize_expressway_feature_matches_returns_zero_without_expressway(
        self,
    ):
        expressway_summary = (
            summarize_expressway_feature_matches_for_grid_cell_contexts(
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
                        "kind": "road",
                        "bounds": {
                            "north": 9.9,
                            "south": 9.8,
                            "east": 19.2,
                            "west": 19.1,
                        },
                    },
                ],
            )
        )

        self.assertEqual(
            expressway_summary,
            {
                "expressway_features": 0,
                "motorway_features": 0,
                "motorway_link_features": 0,
                "trunk_features": 0,
                "trunk_link_features": 0,
                "unknown_expressway_features": 0,
                "expressway_cells": 0,
                "motorway_cells": 0,
                "motorway_link_cells": 0,
                "trunk_cells": 0,
                "trunk_link_cells": 0,
                "unknown_expressway_cells": 0,
            },
        )

    def test_summarize_expressway_feature_matches_counts_features_and_cells(self):
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
                "kind": "expressway",
                "source_highway": "motorway",
                "bounds": {
                    "north": 9.8,
                    "south": 9.2,
                    "east": 20.2,
                    "west": 19.8,
                },
            },
            {
                "kind": "expressway",
                "source_highway": "motorway_link",
                "bounds": {
                    "north": 9.7,
                    "south": 9.3,
                    "east": 20.8,
                    "west": 20.2,
                },
            },
            {
                "kind": "expressway",
                "source_highway": "trunk",
                "bounds": {
                    "north": 9.6,
                    "south": 9.4,
                    "east": 19.7,
                    "west": 19.3,
                },
            },
            {
                "kind": "expressway",
                "source_highway": "trunk_link",
                "bounds": {
                    "north": 9.6,
                    "south": 9.4,
                    "east": 20.7,
                    "west": 20.3,
                },
            },
            {
                "kind": "expressway",
                "source_highway": "residential",
                "bounds": {
                    "north": 9.5,
                    "south": 9.4,
                    "east": 19.7,
                    "west": 19.3,
                },
            },
        ]

        expressway_summary = (
            summarize_expressway_feature_matches_for_grid_cell_contexts(
                grid_cell_contexts,
                map_features,
            )
        )

        self.assertEqual(expressway_summary["expressway_features"], 5)
        self.assertEqual(expressway_summary["motorway_features"], 1)
        self.assertEqual(expressway_summary["motorway_link_features"], 1)
        self.assertEqual(expressway_summary["trunk_features"], 1)
        self.assertEqual(expressway_summary["trunk_link_features"], 1)
        self.assertEqual(expressway_summary["unknown_expressway_features"], 1)
        self.assertEqual(expressway_summary["expressway_cells"], 2)
        self.assertEqual(expressway_summary["motorway_cells"], 2)
        self.assertEqual(expressway_summary["motorway_link_cells"], 1)
        self.assertEqual(expressway_summary["trunk_cells"], 1)
        self.assertEqual(expressway_summary["trunk_link_cells"], 1)
        self.assertEqual(expressway_summary["unknown_expressway_cells"], 1)

    def test_summarize_expressway_bounds_returns_zero_without_expressway(self):
        bounds_summary = summarize_expressway_bounds_for_grid_cell_contexts(
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
                    "kind": "road",
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
                "expressway_features": 0,
                "expressway_cells": 0,
                "expressway_avg_overlap": 0.0,
                "expressway_max_overlap": 0.0,
                "expressway_large_bounds_features": 0,
                "expressway_large_bounds_cells": 0,
                "motorway_features": 0,
                "motorway_cells": 0,
                "motorway_avg_overlap": 0.0,
                "motorway_max_overlap": 0.0,
                "motorway_link_features": 0,
                "motorway_link_cells": 0,
                "motorway_link_avg_overlap": 0.0,
                "motorway_link_max_overlap": 0.0,
                "trunk_features": 0,
                "trunk_cells": 0,
                "trunk_avg_overlap": 0.0,
                "trunk_max_overlap": 0.0,
                "trunk_link_features": 0,
                "trunk_link_cells": 0,
                "trunk_link_avg_overlap": 0.0,
                "trunk_link_max_overlap": 0.0,
                "unknown_expressway_features": 0,
                "unknown_expressway_cells": 0,
                "unknown_expressway_avg_overlap": 0.0,
                "unknown_expressway_max_overlap": 0.0,
            },
        )

    def test_summarize_expressway_bounds_counts_overlap_and_large_bounds(self):
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
                "kind": "expressway",
                "source_highway": "motorway",
                "bounds": {
                    "north": 10.0,
                    "south": 9.0,
                    "east": 20.5,
                    "west": 19.5,
                },
            },
            {
                "kind": "expressway",
                "source_highway": "motorway",
                "bounds": {
                    "north": 15.5,
                    "south": 4.5,
                    "east": 19.1,
                    "west": 18.9,
                },
            },
            {
                "kind": "expressway",
                "source_highway": "motorway_link",
                "bounds": {
                    "north": 9.5,
                    "south": 9.0,
                    "east": 20.5,
                    "west": 20.0,
                },
            },
            {
                "kind": "expressway",
                "source_highway": "trunk",
                "bounds": {
                    "north": 9.5,
                    "south": 9.0,
                    "east": 19.5,
                    "west": 19.0,
                },
            },
            {
                "kind": "expressway",
                "source_highway": "trunk_link",
                "bounds": {
                    "north": 9.5,
                    "south": 9.0,
                    "east": 20.4,
                    "west": 20.0,
                },
            },
            {
                "kind": "expressway",
                "source_highway": "residential",
                "bounds": {
                    "north": 9.2,
                    "south": 9.1,
                    "east": 19.2,
                    "west": 19.1,
                },
            },
        ]

        bounds_summary = summarize_expressway_bounds_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )

        self.assertEqual(bounds_summary["expressway_features"], 6)
        self.assertEqual(bounds_summary["expressway_cells"], 2)
        self.assertAlmostEqual(bounds_summary["expressway_avg_overlap"], 0.5)
        self.assertAlmostEqual(bounds_summary["expressway_max_overlap"], 0.5)
        self.assertEqual(bounds_summary["expressway_large_bounds_features"], 1)
        self.assertEqual(bounds_summary["expressway_large_bounds_cells"], 1)
        self.assertEqual(bounds_summary["motorway_features"], 2)
        self.assertEqual(bounds_summary["motorway_cells"], 2)
        self.assertAlmostEqual(bounds_summary["motorway_avg_overlap"], 0.5)
        self.assertAlmostEqual(bounds_summary["motorway_max_overlap"], 0.5)
        self.assertEqual(bounds_summary["motorway_link_features"], 1)
        self.assertEqual(bounds_summary["motorway_link_cells"], 1)
        self.assertAlmostEqual(bounds_summary["motorway_link_avg_overlap"], 0.25)
        self.assertAlmostEqual(bounds_summary["motorway_link_max_overlap"], 0.25)
        self.assertEqual(bounds_summary["trunk_features"], 1)
        self.assertEqual(bounds_summary["trunk_cells"], 1)
        self.assertAlmostEqual(bounds_summary["trunk_avg_overlap"], 0.25)
        self.assertAlmostEqual(bounds_summary["trunk_max_overlap"], 0.25)
        self.assertEqual(bounds_summary["trunk_link_features"], 1)
        self.assertEqual(bounds_summary["trunk_link_cells"], 1)
        self.assertAlmostEqual(bounds_summary["trunk_link_avg_overlap"], 0.2)
        self.assertAlmostEqual(bounds_summary["trunk_link_max_overlap"], 0.2)
        self.assertEqual(bounds_summary["unknown_expressway_features"], 1)
        self.assertEqual(bounds_summary["unknown_expressway_cells"], 1)
        self.assertAlmostEqual(
            bounds_summary["unknown_expressway_avg_overlap"],
            0.01,
        )
        self.assertAlmostEqual(
            bounds_summary["unknown_expressway_max_overlap"],
            0.01,
        )

    def test_summarize_expressway_bounds_invalid_input_raises_value_error(self):
        valid_context = {
            "row_index": 0,
            "col_index": 0,
            "north": 10.0,
            "south": 9.0,
            "east": 20.0,
            "west": 19.0,
        }
        valid_feature = {
            "kind": "expressway",
            "source_highway": "motorway",
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
                    summarize_expressway_bounds_for_grid_cell_contexts(
                        grid_cell_contexts,
                        map_features,
                    )

    def test_summarize_effective_expressway_returns_zero_without_expressway(self):
        summary = summarize_effective_expressway_feature_matches_for_grid_cell_contexts(
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
            [],
        )

        self.assertEqual(summary["effective_expressway_features"], 0)
        self.assertEqual(summary["effective_expressway_cells"], 0)
        self.assertEqual(summary["effective_expressway_avg_overlap"], 0.0)
        self.assertEqual(summary["effective_motorway_features"], 0)
        self.assertEqual(summary["filtered_expressway_large_bounds_features"], 0)
        self.assertEqual(summary["filtered_expressway_large_bounds_cells"], 0)

    def test_summarize_effective_expressway_excludes_large_bounds(self):
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
                "kind": "expressway",
                "source_highway": "motorway",
                "bounds": {
                    "north": 10.0,
                    "south": 9.0,
                    "east": 20.5,
                    "west": 19.5,
                },
            },
            {
                "kind": "expressway",
                "source_highway": "motorway",
                "bounds": {
                    "north": 15.5,
                    "south": 4.5,
                    "east": 19.1,
                    "west": 18.9,
                },
            },
            {
                "kind": "expressway",
                "source_highway": "trunk",
                "bounds": {
                    "north": 9.5,
                    "south": 9.0,
                    "east": 19.5,
                    "west": 19.0,
                },
            },
        ]

        summary = summarize_effective_expressway_feature_matches_for_grid_cell_contexts(
            grid_cell_contexts,
            map_features,
        )

        self.assertEqual(summary["effective_expressway_features"], 2)
        self.assertEqual(summary["effective_expressway_cells"], 2)
        self.assertAlmostEqual(summary["effective_expressway_avg_overlap"], 0.5)
        self.assertAlmostEqual(summary["effective_expressway_max_overlap"], 0.5)
        self.assertEqual(summary["effective_motorway_features"], 1)
        self.assertEqual(summary["effective_motorway_cells"], 2)
        self.assertAlmostEqual(summary["effective_motorway_avg_overlap"], 0.5)
        self.assertEqual(summary["effective_trunk_features"], 1)
        self.assertEqual(summary["effective_trunk_cells"], 1)
        self.assertAlmostEqual(summary["effective_trunk_avg_overlap"], 0.25)
        self.assertEqual(summary["filtered_expressway_large_bounds_features"], 1)
        self.assertEqual(summary["filtered_expressway_large_bounds_cells"], 1)

    def test_summarize_effective_expressway_invalid_input_raises_value_error(self):
        valid_context = {
            "row_index": 0,
            "col_index": 0,
            "north": 10.0,
            "south": 9.0,
            "east": 20.0,
            "west": 19.0,
        }
        valid_feature = {
            "kind": "expressway",
            "source_highway": "motorway",
            "bounds": {
                "north": 9.9,
                "south": 9.8,
                "east": 19.2,
                "west": 19.1,
            },
        }

        for grid_cell_contexts, map_features in (
            (None, []),
            ([None], []),
            ([valid_context], None),
            ([valid_context], [None]),
            ([valid_context], [{**valid_feature, "bounds": None}]),
        ):
            with self.subTest(
                grid_cell_contexts=grid_cell_contexts,
                map_features=map_features,
            ):
                with self.assertRaises(ValueError):
                    summarize_effective_expressway_feature_matches_for_grid_cell_contexts(
                        grid_cell_contexts,
                        map_features,
                    )

    def test_summarize_station_and_expressway_feature_matches_invalid_input_raises_value_error(
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
        valid_station_feature = {
            "kind": "station",
            "source_railway": "station",
            "bounds": {
                "north": 9.9,
                "south": 9.8,
                "east": 19.2,
                "west": 19.1,
            },
        }
        valid_expressway_feature = {
            "kind": "expressway",
            "source_highway": "motorway",
            "bounds": {
                "north": 9.9,
                "south": 9.8,
                "east": 19.2,
                "west": 19.1,
            },
        }
        valid_landmark_feature = {
            "kind": "landmark",
            "source_tourism": "attraction",
            "bounds": {
                "north": 9.9,
                "south": 9.8,
                "east": 19.2,
                "west": 19.1,
            },
        }
        valid_castle_feature = {
            **valid_landmark_feature,
            "source_tourism": None,
            "source_historic": "castle",
        }
        test_cases = (
            (
                summarize_station_feature_matches_for_grid_cell_contexts,
                None,
                [],
            ),
            (
                summarize_station_feature_matches_for_grid_cell_contexts,
                [None],
                [],
            ),
            (
                summarize_station_feature_matches_for_grid_cell_contexts,
                [valid_context],
                None,
            ),
            (
                summarize_station_feature_matches_for_grid_cell_contexts,
                [valid_context],
                [None],
            ),
            (
                summarize_station_feature_matches_for_grid_cell_contexts,
                [valid_context],
                [{**valid_station_feature, "bounds": None}],
            ),
            (
                summarize_station_proximity_for_grid_cell_contexts,
                None,
                [],
            ),
            (
                summarize_station_proximity_for_grid_cell_contexts,
                [None],
                [],
            ),
            (
                summarize_station_proximity_for_grid_cell_contexts,
                [valid_context],
                None,
            ),
            (
                summarize_station_proximity_for_grid_cell_contexts,
                [valid_context],
                [None],
            ),
            (
                summarize_station_proximity_for_grid_cell_contexts,
                [valid_context],
                [{**valid_station_feature, "bounds": None}],
            ),
            (
                summarize_expressway_feature_matches_for_grid_cell_contexts,
                None,
                [],
            ),
            (
                summarize_expressway_feature_matches_for_grid_cell_contexts,
                [None],
                [],
            ),
            (
                summarize_expressway_feature_matches_for_grid_cell_contexts,
                [valid_context],
                None,
            ),
            (
                summarize_expressway_feature_matches_for_grid_cell_contexts,
                [valid_context],
                [None],
            ),
            (
                summarize_expressway_feature_matches_for_grid_cell_contexts,
                [valid_context],
                [{**valid_expressway_feature, "bounds": None}],
            ),
            (
                summarize_landmark_feature_matches_for_grid_cell_contexts,
                None,
                [],
            ),
            (
                summarize_landmark_feature_matches_for_grid_cell_contexts,
                [None],
                [],
            ),
            (
                summarize_landmark_feature_matches_for_grid_cell_contexts,
                [valid_context],
                None,
            ),
            (
                summarize_landmark_feature_matches_for_grid_cell_contexts,
                [valid_context],
                [None],
            ),
            (
                summarize_landmark_feature_matches_for_grid_cell_contexts,
                [valid_context],
                [{**valid_landmark_feature, "bounds": None}],
            ),
            (
                summarize_castle_proximity_for_grid_cell_contexts,
                None,
                [],
            ),
            (
                summarize_castle_proximity_for_grid_cell_contexts,
                [None],
                [],
            ),
            (
                summarize_castle_proximity_for_grid_cell_contexts,
                [valid_context],
                None,
            ),
            (
                summarize_castle_proximity_for_grid_cell_contexts,
                [valid_context],
                [None],
            ),
            (
                summarize_castle_proximity_for_grid_cell_contexts,
                [valid_context],
                [{**valid_castle_feature, "bounds": None}],
            ),
        )

        for summary_function, grid_cell_contexts, map_features in test_cases:
            with self.subTest(
                summary_function=summary_function.__name__,
                grid_cell_contexts=grid_cell_contexts,
                map_features=map_features,
            ):
                with self.assertRaises(ValueError):
                    summary_function(grid_cell_contexts, map_features)

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
        self.assertLess(score, 2.7)

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
        self.assertLess(score, 2.7)
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
            "grid_size_multiplier",
            "feature_category_count",
            "surface_railway_count",
            "underground_railway_count",
            "unknown_railway_count",
            "railway_station_count",
            "railway_halt_count",
            "subway_station_count",
            "bus_station_count",
            "public_transport_station_count",
            "unknown_station_count",
            "motorway_count",
            "motorway_link_count",
            "trunk_count",
            "trunk_link_count",
            "unknown_expressway_count",
            "tourism_attraction_count",
            "tourism_museum_count",
            "tourism_gallery_count",
            "tourism_viewpoint_count",
            "historic_castle_count",
            "historic_monument_count",
            "historic_memorial_count",
            "historic_ruins_count",
            "historic_archaeological_site_count",
            "unknown_landmark_count",
            "castle_near_proximity_count",
            "castle_mid_proximity_count",
            "castle_far_proximity_count",
            "station_proximity_near_count",
            "station_proximity_mid_count",
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
            "has_surface_railway_context",
            "surface_railway_context_bonus",
            "has_surface_station_context",
            "surface_station_context_bonus",
            "has_subway_station_context",
            "subway_station_context_bonus",
            "has_public_transport_station_context",
            "public_transport_station_context_bonus",
            "scored_station_count",
            "station_cluster_count",
            "dense_station_cluster_count",
            "station_density_bonus",
            "has_dense_station_cluster_context",
            "has_major_station_cluster_context",
            "has_station_proximity_context",
            "has_station_proximity_near_context",
            "has_station_proximity_mid_context",
            "station_proximity_bonus",
            "is_station_proximity_station_cell",
            "has_motorway_context",
            "motorway_context_bonus",
            "has_trunk_context",
            "trunk_context_bonus",
            "has_landmark_context",
            "landmark_context_bonus",
            "tourism_attraction_context_bonus",
            "tourism_museum_context_bonus",
            "tourism_gallery_context_bonus",
            "tourism_viewpoint_context_bonus",
            "historic_castle_context_bonus",
            "historic_monument_context_bonus",
            "historic_memorial_context_bonus",
            "historic_ruins_context_bonus",
            "historic_archaeological_site_context_bonus",
            "has_castle_proximity_context",
            "has_castle_near_proximity_context",
            "has_castle_mid_proximity_context",
            "has_castle_far_proximity_context",
            "castle_proximity_bonus",
            "is_castle_proximity_skipped_castle_cell",
            "is_likely_unreachable_water_cell",
            "has_waterfront_context",
            "has_park_waterfront_combo_context",
            "park_waterfront_combo_bonus",
            "context_candidate_count",
            "has_high_context_3_context",
            "has_high_context_4_context",
            "has_high_context_5_context",
            "high_context_bonus",
            "has_water_penalty",
            "has_unreachable_water_penalty",
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

    def test_auto_score_breakdown_keeps_compact_display_fields(self):
        breakdown = build_auto_score_breakdown_from_feature_summary(
            {
                "building_count": 20,
                "has_park": True,
                "water_coverage_ratio": 0.2,
                "tourism_attraction_count": 1,
            }
        )

        for key in (
            "base_score",
            "diversity_bonus",
            "context_bonus",
            "penalty",
            "raw_score",
            "clamped_score",
        ):
            with self.subTest(key=key):
                self.assertIn(key, breakdown)
        self.assertIn("bonuses", breakdown)
        self.assertIn("flags", breakdown)
        self.assertIn("counts", breakdown)
        self.assertTrue(breakdown["flags"]["has_landmark_context"])
        self.assertTrue(breakdown["flags"]["has_park_waterfront_combo_context"])
        self.assertGreater(breakdown["bonuses"]["landmark_context_bonus"], 0)
        self.assertGreater(
            breakdown["bonuses"]["park_waterfront_combo_bonus"],
            0,
        )
        self.assertGreaterEqual(breakdown["counts"]["context_candidate_count"], 1)

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

    def test_feature_summary_breakdown_adds_surface_railway_context_bonus(self):
        without_railway = calculate_initial_score_breakdown_from_feature_summary({})
        with_surface_railway = calculate_initial_score_breakdown_from_feature_summary(
            {"surface_railway_count": 1}
        )

        self.assertTrue(with_surface_railway["has_surface_railway_context"])
        self.assertEqual(
            with_surface_railway["surface_railway_context_bonus"],
            SURFACE_RAILWAY_CONTEXT_BONUS,
        )
        self.assertAlmostEqual(
            with_surface_railway["context_bonus"],
            without_railway["context_bonus"] + SURFACE_RAILWAY_CONTEXT_BONUS,
        )
        self.assertGreater(
            calculate_initial_score_from_feature_summary(
                {"building_count": 1, "surface_railway_count": 1}
            ),
            calculate_initial_score_from_feature_summary({"building_count": 1}),
        )

    def test_feature_summary_breakdown_surface_railway_does_not_affect_other_factors(
        self,
    ):
        without_railway = calculate_initial_score_breakdown_from_feature_summary({})
        with_surface_railway = calculate_initial_score_breakdown_from_feature_summary(
            {"surface_railway_count": 1}
        )

        for key in ("base_score", "diversity_bonus", "penalty"):
            with self.subTest(key=key):
                self.assertEqual(with_surface_railway[key], without_railway[key])

    def test_feature_summary_breakdown_ignores_underground_and_unknown_railways(self):
        without_railway = calculate_initial_score_breakdown_from_feature_summary({})
        with_underground_railway = (
            calculate_initial_score_breakdown_from_feature_summary(
                {"underground_railway_count": 1}
            )
        )
        with_unknown_railway = calculate_initial_score_breakdown_from_feature_summary(
            {"unknown_railway_count": 1}
        )

        self.assertFalse(with_underground_railway["has_surface_railway_context"])
        self.assertFalse(with_unknown_railway["has_surface_railway_context"])
        self.assertEqual(
            with_underground_railway["surface_railway_context_bonus"],
            0.0,
        )
        self.assertEqual(with_unknown_railway["surface_railway_context_bonus"], 0.0)
        self.assertEqual(
            with_underground_railway["clamped_score"],
            without_railway["clamped_score"],
        )
        self.assertEqual(
            with_unknown_railway["clamped_score"],
            without_railway["clamped_score"],
        )

    def test_feature_summary_breakdown_keeps_old_summary_without_railway_counts(self):
        breakdown = calculate_initial_score_breakdown_from_feature_summary(
            {"building_count": 1}
        )

        self.assertEqual(breakdown["surface_railway_count"], 0.0)
        self.assertEqual(breakdown["underground_railway_count"], 0.0)
        self.assertEqual(breakdown["unknown_railway_count"], 0.0)
        self.assertEqual(breakdown["railway_station_count"], 0.0)
        self.assertEqual(breakdown["railway_halt_count"], 0.0)
        self.assertEqual(breakdown["subway_station_count"], 0.0)
        self.assertEqual(breakdown["bus_station_count"], 0.0)
        self.assertEqual(breakdown["public_transport_station_count"], 0.0)
        self.assertEqual(breakdown["unknown_station_count"], 0.0)
        self.assertEqual(breakdown["motorway_count"], 0.0)
        self.assertEqual(breakdown["motorway_link_count"], 0.0)
        self.assertEqual(breakdown["trunk_count"], 0.0)
        self.assertEqual(breakdown["trunk_link_count"], 0.0)
        self.assertEqual(breakdown["unknown_expressway_count"], 0.0)
        self.assertEqual(breakdown["tourism_attraction_count"], 0.0)
        self.assertEqual(breakdown["tourism_museum_count"], 0.0)
        self.assertEqual(breakdown["tourism_gallery_count"], 0.0)
        self.assertEqual(breakdown["tourism_viewpoint_count"], 0.0)
        self.assertEqual(breakdown["historic_castle_count"], 0.0)
        self.assertEqual(breakdown["historic_monument_count"], 0.0)
        self.assertEqual(breakdown["historic_memorial_count"], 0.0)
        self.assertEqual(breakdown["historic_ruins_count"], 0.0)
        self.assertEqual(breakdown["historic_archaeological_site_count"], 0.0)
        self.assertEqual(breakdown["unknown_landmark_count"], 0.0)
        self.assertEqual(breakdown["castle_near_proximity_count"], 0.0)
        self.assertEqual(breakdown["castle_mid_proximity_count"], 0.0)
        self.assertEqual(breakdown["castle_far_proximity_count"], 0.0)
        self.assertEqual(breakdown["station_proximity_near_count"], 0.0)
        self.assertEqual(breakdown["station_proximity_mid_count"], 0.0)
        self.assertFalse(breakdown["has_surface_railway_context"])
        self.assertFalse(breakdown["has_surface_station_context"])
        self.assertEqual(breakdown["surface_station_context_bonus"], 0.0)
        self.assertFalse(breakdown["has_subway_station_context"])
        self.assertEqual(breakdown["subway_station_context_bonus"], 0.0)
        self.assertFalse(breakdown["has_public_transport_station_context"])
        self.assertEqual(breakdown["public_transport_station_context_bonus"], 0.0)
        self.assertEqual(breakdown["scored_station_count"], 0.0)
        self.assertEqual(breakdown["station_cluster_count"], 0.0)
        self.assertEqual(breakdown["dense_station_cluster_count"], 0.0)
        self.assertEqual(breakdown["station_density_bonus"], 0.0)
        self.assertFalse(breakdown["has_dense_station_cluster_context"])
        self.assertFalse(breakdown["has_major_station_cluster_context"])
        self.assertFalse(breakdown["has_station_proximity_context"])
        self.assertFalse(breakdown["has_station_proximity_near_context"])
        self.assertFalse(breakdown["has_station_proximity_mid_context"])
        self.assertEqual(breakdown["station_proximity_bonus"], 0.0)
        self.assertFalse(breakdown["is_station_proximity_station_cell"])
        self.assertFalse(breakdown["has_motorway_context"])
        self.assertEqual(breakdown["motorway_context_bonus"], 0.0)
        self.assertFalse(breakdown["has_trunk_context"])
        self.assertEqual(breakdown["trunk_context_bonus"], 0.0)
        self.assertFalse(breakdown["has_landmark_context"])
        self.assertEqual(breakdown["landmark_context_bonus"], 0.0)
        self.assertEqual(breakdown["tourism_attraction_context_bonus"], 0.0)
        self.assertEqual(breakdown["tourism_museum_context_bonus"], 0.0)
        self.assertEqual(breakdown["tourism_gallery_context_bonus"], 0.0)
        self.assertEqual(breakdown["tourism_viewpoint_context_bonus"], 0.0)
        self.assertEqual(breakdown["historic_castle_context_bonus"], 0.0)
        self.assertEqual(breakdown["historic_monument_context_bonus"], 0.0)
        self.assertEqual(breakdown["historic_memorial_context_bonus"], 0.0)
        self.assertEqual(breakdown["historic_ruins_context_bonus"], 0.0)
        self.assertEqual(
            breakdown["historic_archaeological_site_context_bonus"],
            0.0,
        )
        self.assertFalse(breakdown["has_castle_proximity_context"])
        self.assertFalse(breakdown["has_castle_near_proximity_context"])
        self.assertFalse(breakdown["has_castle_mid_proximity_context"])
        self.assertFalse(breakdown["has_castle_far_proximity_context"])
        self.assertEqual(breakdown["castle_proximity_bonus"], 0.0)
        self.assertFalse(breakdown["is_castle_proximity_skipped_castle_cell"])
        self.assertFalse(breakdown["has_park_waterfront_combo_context"])
        self.assertEqual(breakdown["park_waterfront_combo_bonus"], 0.0)
        self.assertEqual(breakdown["context_candidate_count"], 0)
        self.assertFalse(breakdown["has_high_context_3_context"])
        self.assertFalse(breakdown["has_high_context_4_context"])
        self.assertFalse(breakdown["has_high_context_5_context"])
        self.assertEqual(breakdown["high_context_bonus"], 0.0)

    def test_feature_summary_breakdown_adds_surface_station_context_bonus(self):
        without_station = calculate_initial_score_breakdown_from_feature_summary({})
        station_count_keys = (
            "railway_station_count",
            "railway_halt_count",
        )

        for station_count_key in station_count_keys:
            with self.subTest(station_count_key=station_count_key):
                with_station = (
                    calculate_initial_score_breakdown_from_feature_summary(
                        {station_count_key: 1}
                    )
                )

                self.assertTrue(with_station["has_surface_station_context"])
                self.assertFalse(with_station["has_subway_station_context"])
                self.assertFalse(
                    with_station["has_public_transport_station_context"]
                )
                self.assertEqual(
                    with_station["surface_station_context_bonus"],
                    SURFACE_STATION_CONTEXT_BONUS,
                )
                self.assertEqual(
                    with_station["subway_station_context_bonus"],
                    0.0,
                )
                self.assertEqual(
                    with_station["public_transport_station_context_bonus"],
                    0.0,
                )
                self.assertAlmostEqual(
                    with_station["context_bonus"],
                    without_station["context_bonus"]
                    + SURFACE_STATION_CONTEXT_BONUS,
                )
                self.assertGreater(
                    calculate_initial_score_from_feature_summary(
                        {"building_count": 1, station_count_key: 1}
                    ),
                    calculate_initial_score_from_feature_summary(
                        {"building_count": 1}
                    ),
                )

    def test_feature_summary_breakdown_adds_subway_station_context_bonus(self):
        without_station = calculate_initial_score_breakdown_from_feature_summary({})
        with_subway_station = calculate_initial_score_breakdown_from_feature_summary(
            {"subway_station_count": 1}
        )

        self.assertFalse(with_subway_station["has_surface_station_context"])
        self.assertTrue(with_subway_station["has_subway_station_context"])
        self.assertFalse(
            with_subway_station["has_public_transport_station_context"]
        )
        self.assertEqual(with_subway_station["surface_station_context_bonus"], 0.0)
        self.assertEqual(
            with_subway_station["subway_station_context_bonus"],
            SUBWAY_STATION_CONTEXT_BONUS,
        )
        self.assertEqual(
            with_subway_station["public_transport_station_context_bonus"],
            0.0,
        )
        self.assertAlmostEqual(
            with_subway_station["context_bonus"],
            without_station["context_bonus"] + SUBWAY_STATION_CONTEXT_BONUS,
        )

    def test_feature_summary_breakdown_adds_public_transport_station_context_bonus(
        self,
    ):
        without_station = calculate_initial_score_breakdown_from_feature_summary({})
        with_public_transport_station = (
            calculate_initial_score_breakdown_from_feature_summary(
                {"public_transport_station_count": 1}
            )
        )

        self.assertFalse(
            with_public_transport_station["has_surface_station_context"]
        )
        self.assertFalse(with_public_transport_station["has_subway_station_context"])
        self.assertTrue(
            with_public_transport_station[
                "has_public_transport_station_context"
            ]
        )
        self.assertEqual(
            with_public_transport_station["surface_station_context_bonus"],
            0.0,
        )
        self.assertEqual(
            with_public_transport_station["subway_station_context_bonus"],
            0.0,
        )
        self.assertEqual(
            with_public_transport_station[
                "public_transport_station_context_bonus"
            ],
            PUBLIC_TRANSPORT_STATION_CONTEXT_BONUS,
        )
        self.assertAlmostEqual(
            with_public_transport_station["context_bonus"],
            without_station["context_bonus"]
            + PUBLIC_TRANSPORT_STATION_CONTEXT_BONUS,
        )

    def test_feature_summary_breakdown_adds_multiple_station_context_bonuses(self):
        without_station = calculate_initial_score_breakdown_from_feature_summary({})
        with_station_types = calculate_initial_score_breakdown_from_feature_summary(
            {
                "railway_station_count": 1,
                "subway_station_count": 1,
                "public_transport_station_count": 1,
            }
        )

        self.assertTrue(with_station_types["has_surface_station_context"])
        self.assertTrue(with_station_types["has_subway_station_context"])
        self.assertTrue(with_station_types["has_public_transport_station_context"])
        self.assertEqual(with_station_types["scored_station_count"], 3.0)
        self.assertEqual(with_station_types["station_cluster_count"], 0.0)
        self.assertEqual(with_station_types["dense_station_cluster_count"], 0.0)
        self.assertFalse(with_station_types["has_dense_station_cluster_context"])
        self.assertFalse(with_station_types["has_major_station_cluster_context"])
        self.assertEqual(with_station_types["station_density_bonus"], 0.0)
        self.assertAlmostEqual(
            with_station_types["context_bonus"],
            without_station["context_bonus"]
            + SURFACE_STATION_CONTEXT_BONUS
            + SUBWAY_STATION_CONTEXT_BONUS
            + PUBLIC_TRANSPORT_STATION_CONTEXT_BONUS,
        )

    def test_feature_summary_breakdown_does_not_use_station_count_for_density_bonus(
        self,
    ):
        without_station = calculate_initial_score_breakdown_from_feature_summary({})
        with_two_stations = calculate_initial_score_breakdown_from_feature_summary(
            {
                "railway_station_count": 1,
                "public_transport_station_count": 1,
            }
        )

        self.assertEqual(with_two_stations["scored_station_count"], 2.0)
        self.assertFalse(with_two_stations["has_dense_station_cluster_context"])
        self.assertFalse(with_two_stations["has_major_station_cluster_context"])
        self.assertEqual(with_two_stations["station_density_bonus"], 0.0)
        self.assertAlmostEqual(
            with_two_stations["context_bonus"],
            without_station["context_bonus"]
            + SURFACE_STATION_CONTEXT_BONUS
            + PUBLIC_TRANSPORT_STATION_CONTEXT_BONUS,
        )

    def test_feature_summary_breakdown_adds_dense_station_cluster_density_bonus(
        self,
    ):
        without_station = calculate_initial_score_breakdown_from_feature_summary({})
        with_dense_cluster = calculate_initial_score_breakdown_from_feature_summary(
            {
                "railway_station_count": 1,
                "dense_station_cluster_count": 2,
            }
        )

        self.assertEqual(with_dense_cluster["scored_station_count"], 1.0)
        self.assertEqual(with_dense_cluster["dense_station_cluster_count"], 2.0)
        self.assertTrue(with_dense_cluster["has_dense_station_cluster_context"])
        self.assertFalse(with_dense_cluster["has_major_station_cluster_context"])
        self.assertEqual(with_dense_cluster["station_density_bonus"], 0.40)
        self.assertAlmostEqual(
            with_dense_cluster["context_bonus"],
            without_station["context_bonus"]
            + SURFACE_STATION_CONTEXT_BONUS
            + 0.40,
        )

    def test_feature_summary_breakdown_adds_major_station_cluster_density_bonus(
        self,
    ):
        without_station = calculate_initial_score_breakdown_from_feature_summary({})
        with_major_cluster = calculate_initial_score_breakdown_from_feature_summary(
            {
                "railway_station_count": 1,
                "station_cluster_count": 3,
            }
        )

        self.assertEqual(with_major_cluster["station_cluster_count"], 3.0)
        self.assertFalse(with_major_cluster["has_dense_station_cluster_context"])
        self.assertTrue(with_major_cluster["has_major_station_cluster_context"])
        self.assertEqual(with_major_cluster["station_density_bonus"], 0.30)
        self.assertAlmostEqual(
            with_major_cluster["context_bonus"],
            without_station["context_bonus"]
            + SURFACE_STATION_CONTEXT_BONUS
            + 0.30,
        )

    def test_feature_summary_breakdown_caps_station_cluster_density_bonus(self):
        with_station_clusters = calculate_initial_score_breakdown_from_feature_summary(
            {
                "railway_station_count": 1,
                "station_cluster_count": 5,
                "dense_station_cluster_count": 5,
            }
        )

        self.assertTrue(
            with_station_clusters["has_dense_station_cluster_context"]
        )
        self.assertTrue(
            with_station_clusters["has_major_station_cluster_context"]
        )
        self.assertEqual(with_station_clusters["station_density_bonus"], 0.70)

    def test_feature_summary_breakdown_does_not_score_bus_station_context(self):
        without_station = calculate_initial_score_breakdown_from_feature_summary({})
        with_bus_station = calculate_initial_score_breakdown_from_feature_summary(
            {"bus_station_count": 1}
        )

        self.assertEqual(with_bus_station["bus_station_count"], 1.0)
        self.assertFalse(with_bus_station["has_surface_station_context"])
        self.assertFalse(with_bus_station["has_subway_station_context"])
        self.assertFalse(with_bus_station["has_public_transport_station_context"])
        self.assertEqual(with_bus_station["surface_station_context_bonus"], 0.0)
        self.assertEqual(with_bus_station["subway_station_context_bonus"], 0.0)
        self.assertEqual(
            with_bus_station["public_transport_station_context_bonus"],
            0.0,
        )
        self.assertEqual(with_bus_station["scored_station_count"], 0.0)
        self.assertEqual(with_bus_station["station_cluster_count"], 0.0)
        self.assertEqual(with_bus_station["dense_station_cluster_count"], 0.0)
        self.assertEqual(with_bus_station["station_density_bonus"], 0.0)
        self.assertFalse(with_bus_station["has_dense_station_cluster_context"])
        self.assertFalse(with_bus_station["has_major_station_cluster_context"])
        self.assertEqual(
            with_bus_station["clamped_score"],
            without_station["clamped_score"],
        )

    def test_feature_summary_breakdown_station_does_not_affect_other_factors(self):
        without_station = calculate_initial_score_breakdown_from_feature_summary({})
        with_station = calculate_initial_score_breakdown_from_feature_summary(
            {"railway_station_count": 1}
        )

        for key in ("base_score", "diversity_bonus", "penalty"):
            with self.subTest(key=key):
                self.assertEqual(with_station[key], without_station[key])

    def test_feature_summary_breakdown_adds_station_proximity_context_bonus(self):
        without_proximity = calculate_initial_score_breakdown_from_feature_summary({})
        proximity_cases = (
            (
                {"station_proximity_near_count": 1},
                "has_station_proximity_near_context",
                STATION_PROXIMITY_NEAR_CONTEXT_BONUS,
            ),
            (
                {"station_proximity_mid_count": 1},
                "has_station_proximity_mid_context",
                STATION_PROXIMITY_MID_CONTEXT_BONUS,
            ),
        )

        for feature_summary, context_key, expected_bonus in proximity_cases:
            with self.subTest(feature_summary=feature_summary):
                with_proximity = calculate_initial_score_breakdown_from_feature_summary(
                    feature_summary
                )

                self.assertTrue(with_proximity["has_station_proximity_context"])
                self.assertTrue(with_proximity[context_key])
                self.assertFalse(with_proximity["is_station_proximity_station_cell"])
                self.assertEqual(
                    with_proximity["station_proximity_bonus"],
                    expected_bonus,
                )
                self.assertAlmostEqual(
                    with_proximity["context_bonus"],
                    without_proximity["context_bonus"] + expected_bonus,
                )

    def test_feature_summary_breakdown_skips_station_proximity_on_station_cell(self):
        with_station_cell = calculate_initial_score_breakdown_from_feature_summary(
            {
                "railway_station_count": 1,
                "station_proximity_near_count": 1,
            }
        )

        self.assertTrue(with_station_cell["has_surface_station_context"])
        self.assertTrue(with_station_cell["is_station_proximity_station_cell"])
        self.assertFalse(with_station_cell["has_station_proximity_context"])
        self.assertFalse(with_station_cell["has_station_proximity_near_context"])
        self.assertEqual(with_station_cell["station_proximity_bonus"], 0.0)
        self.assertAlmostEqual(
            with_station_cell["context_bonus"],
            SURFACE_STATION_CONTEXT_BONUS,
        )

    def test_feature_summary_breakdown_station_proximity_does_not_affect_other_factors(
        self,
    ):
        without_proximity = calculate_initial_score_breakdown_from_feature_summary({})
        with_proximity = calculate_initial_score_breakdown_from_feature_summary(
            {"station_proximity_near_count": 1}
        )

        for key in ("base_score", "diversity_bonus", "penalty"):
            with self.subTest(key=key):
                self.assertEqual(with_proximity[key], without_proximity[key])

    def test_feature_summary_breakdown_ignores_unknown_station(self):
        without_station = calculate_initial_score_breakdown_from_feature_summary({})
        with_unknown_station = calculate_initial_score_breakdown_from_feature_summary(
            {"unknown_station_count": 1}
        )

        self.assertFalse(with_unknown_station["has_surface_station_context"])
        self.assertEqual(with_unknown_station["surface_station_context_bonus"], 0.0)
        self.assertFalse(with_unknown_station["has_subway_station_context"])
        self.assertEqual(with_unknown_station["subway_station_context_bonus"], 0.0)
        self.assertFalse(
            with_unknown_station["has_public_transport_station_context"]
        )
        self.assertEqual(
            with_unknown_station["public_transport_station_context_bonus"],
            0.0,
        )
        self.assertEqual(with_unknown_station["scored_station_count"], 0.0)
        self.assertEqual(with_unknown_station["station_cluster_count"], 0.0)
        self.assertEqual(with_unknown_station["dense_station_cluster_count"], 0.0)
        self.assertEqual(with_unknown_station["station_density_bonus"], 0.0)
        self.assertFalse(with_unknown_station["has_dense_station_cluster_context"])
        self.assertFalse(with_unknown_station["has_major_station_cluster_context"])
        self.assertEqual(
            with_unknown_station["clamped_score"],
            without_station["clamped_score"],
        )

    def test_feature_summary_breakdown_adds_motorway_context_bonus(self):
        without_motorway = calculate_initial_score_breakdown_from_feature_summary({})
        motorway_count_keys = (
            "motorway_count",
            "motorway_link_count",
        )

        for motorway_count_key in motorway_count_keys:
            with self.subTest(motorway_count_key=motorway_count_key):
                with_motorway = (
                    calculate_initial_score_breakdown_from_feature_summary(
                        {motorway_count_key: 1}
                    )
                )

                self.assertTrue(with_motorway["has_motorway_context"])
                self.assertFalse(with_motorway["has_trunk_context"])
                self.assertEqual(
                    with_motorway["motorway_context_bonus"],
                    MOTORWAY_CONTEXT_BONUS,
                )
                self.assertEqual(
                    with_motorway["trunk_context_bonus"],
                    0.0,
                )
                self.assertAlmostEqual(
                    with_motorway["context_bonus"],
                    without_motorway["context_bonus"] + MOTORWAY_CONTEXT_BONUS,
                )
                self.assertGreater(
                    calculate_initial_score_from_feature_summary(
                        {"building_count": 1, motorway_count_key: 1}
                    ),
                    calculate_initial_score_from_feature_summary(
                        {"building_count": 1}
                    ),
                )

    def test_feature_summary_breakdown_adds_trunk_context_bonus(self):
        without_trunk = calculate_initial_score_breakdown_from_feature_summary({})
        trunk_count_keys = (
            "trunk_count",
            "trunk_link_count",
        )

        for trunk_count_key in trunk_count_keys:
            with self.subTest(trunk_count_key=trunk_count_key):
                with_trunk = calculate_initial_score_breakdown_from_feature_summary(
                    {trunk_count_key: 1}
                )

                self.assertFalse(with_trunk["has_motorway_context"])
                self.assertTrue(with_trunk["has_trunk_context"])
                self.assertEqual(with_trunk["motorway_context_bonus"], 0.0)
                self.assertEqual(
                    with_trunk["trunk_context_bonus"],
                    TRUNK_CONTEXT_BONUS,
                )
                self.assertAlmostEqual(
                    with_trunk["context_bonus"],
                    without_trunk["context_bonus"] + TRUNK_CONTEXT_BONUS,
                )
                self.assertGreater(
                    calculate_initial_score_from_feature_summary(
                        {"building_count": 1, trunk_count_key: 1}
                    ),
                    calculate_initial_score_from_feature_summary(
                        {"building_count": 1}
                    ),
                )

    def test_feature_summary_breakdown_adds_motorway_and_trunk_context_bonuses(
        self,
    ):
        without_expressway = calculate_initial_score_breakdown_from_feature_summary({})
        with_motorway_and_trunk = calculate_initial_score_breakdown_from_feature_summary(
            {"motorway_count": 1, "trunk_count": 1}
        )

        self.assertTrue(with_motorway_and_trunk["has_motorway_context"])
        self.assertTrue(with_motorway_and_trunk["has_trunk_context"])
        self.assertEqual(
            with_motorway_and_trunk["motorway_context_bonus"],
            MOTORWAY_CONTEXT_BONUS,
        )
        self.assertEqual(
            with_motorway_and_trunk["trunk_context_bonus"],
            TRUNK_CONTEXT_BONUS,
        )
        self.assertAlmostEqual(
            with_motorway_and_trunk["context_bonus"],
            without_expressway["context_bonus"]
            + MOTORWAY_CONTEXT_BONUS
            + TRUNK_CONTEXT_BONUS,
        )

    def test_feature_summary_breakdown_expressway_does_not_affect_other_factors(self):
        without_expressway = calculate_initial_score_breakdown_from_feature_summary({})
        with_expressway = calculate_initial_score_breakdown_from_feature_summary(
            {"motorway_count": 1}
        )

        for key in ("base_score", "diversity_bonus", "penalty"):
            with self.subTest(key=key):
                self.assertEqual(with_expressway[key], without_expressway[key])

    def test_feature_summary_breakdown_ignores_unknown_expressway(self):
        without_expressway = calculate_initial_score_breakdown_from_feature_summary({})
        with_unknown_expressway = calculate_initial_score_breakdown_from_feature_summary(
            {"unknown_expressway_count": 1}
        )

        self.assertFalse(with_unknown_expressway["has_motorway_context"])
        self.assertEqual(with_unknown_expressway["motorway_context_bonus"], 0.0)
        self.assertFalse(with_unknown_expressway["has_trunk_context"])
        self.assertEqual(with_unknown_expressway["trunk_context_bonus"], 0.0)
        self.assertEqual(
            with_unknown_expressway["clamped_score"],
            without_expressway["clamped_score"],
        )

    def test_feature_summary_breakdown_adds_landmark_context_bonus_by_type(self):
        without_landmark = calculate_initial_score_breakdown_from_feature_summary({})
        landmark_cases = (
            (
                "tourism_attraction_count",
                "tourism_attraction_context_bonus",
                0.35,
            ),
            ("tourism_museum_count", "tourism_museum_context_bonus", 0.20),
            ("tourism_gallery_count", "tourism_gallery_context_bonus", 0.10),
            ("tourism_viewpoint_count", "tourism_viewpoint_context_bonus", 0.40),
            ("historic_castle_count", "historic_castle_context_bonus", 0.80),
            (
                "historic_monument_count",
                "historic_monument_context_bonus",
                0.20,
            ),
            (
                "historic_memorial_count",
                "historic_memorial_context_bonus",
                0.15,
            ),
            ("historic_ruins_count", "historic_ruins_context_bonus", 0.40),
            (
                "historic_archaeological_site_count",
                "historic_archaeological_site_context_bonus",
                0.45,
            ),
        )

        for count_key, bonus_key, expected_bonus in landmark_cases:
            with self.subTest(count_key=count_key):
                with_landmark = (
                    calculate_initial_score_breakdown_from_feature_summary(
                        {count_key: 1}
                    )
                )

                self.assertTrue(with_landmark["has_landmark_context"])
                self.assertEqual(with_landmark[bonus_key], expected_bonus)
                self.assertEqual(
                    with_landmark["landmark_context_bonus"],
                    expected_bonus,
                )
                self.assertAlmostEqual(
                    with_landmark["context_bonus"],
                    without_landmark["context_bonus"] + expected_bonus,
                )
                self.assertGreater(
                    calculate_initial_score_from_feature_summary(
                        {"building_count": 1, count_key: 1}
                    ),
                    calculate_initial_score_from_feature_summary(
                        {"building_count": 1}
                    ),
                )

    def test_feature_summary_breakdown_caps_landmark_context_bonus(self):
        with_landmarks = calculate_initial_score_breakdown_from_feature_summary(
            {
                "historic_castle_count": 1,
                "tourism_viewpoint_count": 1,
                "historic_archaeological_site_count": 1,
            }
        )

        self.assertTrue(with_landmarks["has_landmark_context"])
        self.assertEqual(with_landmarks["historic_castle_context_bonus"], 0.80)
        self.assertEqual(with_landmarks["tourism_viewpoint_context_bonus"], 0.40)
        self.assertEqual(
            with_landmarks["historic_archaeological_site_context_bonus"],
            0.45,
        )
        self.assertEqual(with_landmarks["landmark_context_bonus"], 1.0)

    def test_feature_summary_breakdown_adds_castle_proximity_context_bonus_by_band(
        self,
    ):
        without_castle = calculate_initial_score_breakdown_from_feature_summary({})
        proximity_cases = (
            (
                "castle_near_proximity_count",
                "has_castle_near_proximity_context",
                0.65,
            ),
            (
                "castle_mid_proximity_count",
                "has_castle_mid_proximity_context",
                0.35,
            ),
            (
                "castle_far_proximity_count",
                "has_castle_far_proximity_context",
                0.15,
            ),
        )

        for count_key, context_key, expected_bonus in proximity_cases:
            with self.subTest(count_key=count_key):
                with_proximity = (
                    calculate_initial_score_breakdown_from_feature_summary(
                        {count_key: 1}
                    )
                )

                self.assertTrue(with_proximity["has_castle_proximity_context"])
                self.assertTrue(with_proximity[context_key])
                self.assertEqual(
                    with_proximity["castle_proximity_bonus"],
                    expected_bonus,
                )
                self.assertAlmostEqual(
                    with_proximity["context_bonus"],
                    without_castle["context_bonus"] + expected_bonus,
                )

    def test_feature_summary_breakdown_skips_castle_proximity_on_castle_cell(self):
        with_castle_cell = calculate_initial_score_breakdown_from_feature_summary(
            {
                "historic_castle_count": 1,
                "castle_near_proximity_count": 1,
            }
        )

        self.assertTrue(with_castle_cell["has_landmark_context"])
        self.assertEqual(with_castle_cell["landmark_context_bonus"], 0.80)
        self.assertFalse(with_castle_cell["has_castle_proximity_context"])
        self.assertEqual(with_castle_cell["castle_proximity_bonus"], 0.0)
        self.assertTrue(
            with_castle_cell["is_castle_proximity_skipped_castle_cell"]
        )
        self.assertAlmostEqual(with_castle_cell["context_bonus"], 0.80)

    def test_feature_summary_breakdown_castle_proximity_does_not_affect_other_factors(
        self,
    ):
        without_castle = calculate_initial_score_breakdown_from_feature_summary({})
        with_castle_proximity = calculate_initial_score_breakdown_from_feature_summary(
            {"castle_near_proximity_count": 1}
        )

        for key in ("base_score", "diversity_bonus", "penalty"):
            with self.subTest(key=key):
                self.assertEqual(with_castle_proximity[key], without_castle[key])

    def test_feature_summary_breakdown_landmark_does_not_affect_other_factors(self):
        without_landmark = calculate_initial_score_breakdown_from_feature_summary({})
        with_landmark = calculate_initial_score_breakdown_from_feature_summary(
            {"historic_castle_count": 1}
        )

        for key in ("base_score", "diversity_bonus", "penalty"):
            with self.subTest(key=key):
                self.assertEqual(with_landmark[key], without_landmark[key])

    def test_feature_summary_breakdown_ignores_unknown_landmark(self):
        without_landmark = calculate_initial_score_breakdown_from_feature_summary({})
        with_unknown_landmark = (
            calculate_initial_score_breakdown_from_feature_summary(
                {"unknown_landmark_count": 1}
            )
        )

        self.assertEqual(with_unknown_landmark["unknown_landmark_count"], 1.0)
        self.assertFalse(with_unknown_landmark["has_landmark_context"])
        self.assertEqual(with_unknown_landmark["landmark_context_bonus"], 0.0)
        self.assertEqual(
            with_unknown_landmark["clamped_score"],
            without_landmark["clamped_score"],
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
        self.assertTrue(water_breakdown["has_unreachable_water_penalty"])
        self.assertTrue(water_breakdown["is_likely_unreachable_water_cell"])
        self.assertFalse(water_breakdown["has_waterfront_context"])
        self.assertTrue(water_breakdown["has_empty_cell_penalty"])
        self.assertTrue(forest_breakdown["has_forest_penalty"])
        self.assertTrue(forest_breakdown["has_empty_cell_penalty"])

    def test_feature_summary_breakdown_limits_water_penalty_to_unreachable_water(self):
        for feature_summary in (
            {"water_coverage_ratio": 0.95, "building_count": 1},
            {"water_coverage_ratio": 0.95, "road_count": 1},
            {"water_coverage_ratio": 0.95, "has_park": True},
            {"water_coverage_ratio": 0.95, "has_river": True},
        ):
            with self.subTest(feature_summary=feature_summary):
                breakdown = calculate_initial_score_breakdown_from_feature_summary(
                    feature_summary
                )

                self.assertFalse(breakdown["has_water_penalty"])
                self.assertFalse(breakdown["has_unreachable_water_penalty"])
                self.assertFalse(breakdown["is_likely_unreachable_water_cell"])
                self.assertTrue(breakdown["has_waterfront_context"])

    def test_feature_summary_breakdown_adds_waterfront_context_bonus(self):
        for reachable_context in ({"has_river": True},):
            with self.subTest(reachable_context=reachable_context):
                without_water = calculate_initial_score_breakdown_from_feature_summary(
                    reachable_context
                )
                with_water = calculate_initial_score_breakdown_from_feature_summary(
                    {
                        **reachable_context,
                        "water_coverage_ratio": 0.2,
                    }
                )

                self.assertTrue(with_water["has_waterfront_context"])
                self.assertAlmostEqual(
                    with_water["context_bonus"],
                    without_water["context_bonus"] + WATERFRONT_CONTEXT_BONUS,
                )

    def test_feature_summary_breakdown_adds_park_waterfront_combo_context_bonus(self):
        without_water = calculate_initial_score_breakdown_from_feature_summary(
            {"has_park": True}
        )
        with_park_waterfront = calculate_initial_score_breakdown_from_feature_summary(
            {
                "has_park": True,
                "water_coverage_ratio": 0.2,
            }
        )

        self.assertTrue(with_park_waterfront["has_waterfront_context"])
        self.assertTrue(
            with_park_waterfront["has_park_waterfront_combo_context"]
        )
        self.assertEqual(
            with_park_waterfront["park_waterfront_combo_bonus"],
            PARK_WATERFRONT_COMBO_CONTEXT_BONUS,
        )
        self.assertAlmostEqual(
            with_park_waterfront["context_bonus"],
            without_water["context_bonus"]
            + WATERFRONT_CONTEXT_BONUS
            + PARK_WATERFRONT_COMBO_CONTEXT_BONUS,
        )

    def test_feature_summary_breakdown_uses_road_only_for_waterfront_reachability(self):
        road_only = calculate_initial_score_breakdown_from_feature_summary(
            {"road_count": 1}
        )
        road_waterfront = calculate_initial_score_breakdown_from_feature_summary(
            {
                "road_count": 1,
                "water_coverage_ratio": 0.2,
            }
        )

        self.assertEqual(road_waterfront["road_base_bonus"], 0.0)
        self.assertEqual(
            road_waterfront["feature_category_count"],
            road_only["feature_category_count"] + 1,
        )
        self.assertTrue(road_waterfront["has_waterfront_context"])
        self.assertAlmostEqual(
            road_waterfront["context_bonus"],
            road_only["context_bonus"] + WATERFRONT_CONTEXT_BONUS,
        )

    def test_feature_summary_breakdown_without_water_has_no_waterfront_context(self):
        breakdown = calculate_initial_score_breakdown_from_feature_summary(
            {
                "building_count": 1,
                "has_park": True,
            }
        )

        self.assertFalse(breakdown["has_waterfront_context"])

    def test_feature_summary_breakdown_adds_high_context_bonus_by_context_count(self):
        context_cases = (
            (
                {
                    "surface_railway_count": 1,
                    "motorway_count": 1,
                    "trunk_count": 1,
                },
                3,
                HIGH_CONTEXT_3_CONTEXT_BONUS,
            ),
            (
                {
                    "surface_railway_count": 1,
                    "motorway_count": 1,
                    "trunk_count": 1,
                    "tourism_museum_count": 1,
                },
                4,
                HIGH_CONTEXT_4_CONTEXT_BONUS,
            ),
            (
                {
                    "surface_railway_count": 1,
                    "public_transport_station_count": 1,
                    "motorway_count": 1,
                    "trunk_count": 1,
                    "tourism_museum_count": 1,
                },
                5,
                HIGH_CONTEXT_5_CONTEXT_BONUS,
            ),
        )

        for feature_summary, expected_count, expected_bonus in context_cases:
            with self.subTest(expected_count=expected_count):
                breakdown = calculate_initial_score_breakdown_from_feature_summary(
                    feature_summary
                )

                self.assertEqual(
                    breakdown["context_candidate_count"],
                    expected_count,
                )
                self.assertEqual(breakdown["high_context_bonus"], expected_bonus)
                self.assertEqual(
                    breakdown["has_high_context_3_context"],
                    expected_count >= 3,
                )
                self.assertEqual(
                    breakdown["has_high_context_4_context"],
                    expected_count >= 4,
                )
                self.assertEqual(
                    breakdown["has_high_context_5_context"],
                    expected_count >= 5,
                )

    def test_feature_summary_breakdown_high_context_bonus_does_not_affect_other_factors(
        self,
    ):
        without_high_context = calculate_initial_score_breakdown_from_feature_summary(
            {}
        )
        with_high_context = calculate_initial_score_breakdown_from_feature_summary(
            {
                "surface_railway_count": 1,
                "motorway_count": 1,
                "trunk_count": 1,
            }
        )

        for key in ("base_score", "diversity_bonus", "penalty"):
            with self.subTest(key=key):
                self.assertEqual(with_high_context[key], without_high_context[key])

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
            {"surface_railway_count": -1},
            {"underground_railway_count": float("inf")},
            {"unknown_railway_count": True},
            {"railway_station_count": -1},
            {"railway_halt_count": float("inf")},
            {"subway_station_count": True},
            {"bus_station_count": -1},
            {"public_transport_station_count": float("nan")},
            {"unknown_station_count": True},
            {"station_cluster_count": -1},
            {"dense_station_cluster_count": float("inf")},
            {"station_proximity_near_count": -1},
            {"station_proximity_mid_count": float("inf")},
            {"motorway_count": -1},
            {"motorway_link_count": float("inf")},
            {"trunk_count": True},
            {"trunk_link_count": -1},
            {"unknown_expressway_count": float("nan")},
            {"tourism_attraction_count": -1},
            {"tourism_museum_count": float("inf")},
            {"tourism_gallery_count": True},
            {"tourism_viewpoint_count": float("nan")},
            {"historic_castle_count": -1},
            {"historic_monument_count": float("inf")},
            {"historic_memorial_count": True},
            {"historic_ruins_count": float("nan")},
            {"historic_archaeological_site_count": -1},
            {"unknown_landmark_count": True},
            {"castle_near_proximity_count": -1},
            {"castle_mid_proximity_count": float("inf")},
            {"castle_far_proximity_count": True},
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
            {"surface_railway_count": -1},
            {"underground_railway_count": float("inf")},
            {"unknown_railway_count": True},
            {"railway_station_count": -1},
            {"railway_halt_count": float("inf")},
            {"subway_station_count": True},
            {"bus_station_count": -1},
            {"public_transport_station_count": float("nan")},
            {"unknown_station_count": True},
            {"station_cluster_count": -1},
            {"dense_station_cluster_count": float("inf")},
            {"station_proximity_near_count": -1},
            {"station_proximity_mid_count": float("inf")},
            {"motorway_count": -1},
            {"motorway_link_count": float("inf")},
            {"trunk_count": True},
            {"trunk_link_count": -1},
            {"unknown_expressway_count": float("nan")},
            {"tourism_attraction_count": -1},
            {"tourism_museum_count": float("inf")},
            {"tourism_gallery_count": True},
            {"tourism_viewpoint_count": float("nan")},
            {"historic_castle_count": -1},
            {"historic_monument_count": float("inf")},
            {"historic_memorial_count": True},
            {"historic_ruins_count": float("nan")},
            {"historic_archaeological_site_count": -1},
            {"unknown_landmark_count": True},
            {"castle_near_proximity_count": -1},
            {"castle_mid_proximity_count": float("inf")},
            {"castle_far_proximity_count": True},
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
        expected_score = calculate_initial_score_from_feature_summary(
            feature_summary,
            grid_size_meters=self.area.grid_size_meters,
        )

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
            feature_summaries[(0, 0)],
            grid_size_meters=self.area.grid_size_meters,
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
