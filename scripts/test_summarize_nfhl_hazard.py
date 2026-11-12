import csv
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from pyproj import Geod
from shapely.geometry import Polygon, box, mapping, shape as shapely_shape
from shapely.ops import unary_union
from streamlit.testing.v1 import AppTest

from scripts.summarize_nfhl_hazard import (
    AREA_GEOD,
    ZIP_CODES,
    _validate_coordinate_transform,
    _validate_geometry,
    load_zcta_geometries,
    query_study_metadata,
    query_zone_features,
    summarize_zcta,
)

ROOT = Path(__file__).resolve().parents[1]


class HazardSummaryTests(unittest.TestCase):
    def test_summary_partitions_mapped_area_and_uses_map_effective_date(self):
        zcta = Polygon([
            (-82.80, 27.70), (-82.70, 27.70),
            (-82.70, 27.80), (-82.80, 27.80), (-82.80, 27.70),
        ])
        features = [
            {
                "properties": {
                    "OBJECTID": 1, "DFIRM_ID": "12103C", "VERSION_ID": "2.4.3.2",
                    "SFHA_TF": "T", "FLD_ZONE": "AE", "ZONE_SUBTY": None,
                },
                "geometry": mapping(Polygon([
                    (-82.80, 27.70), (-82.75, 27.70),
                    (-82.75, 27.80), (-82.80, 27.80), (-82.80, 27.70),
                ])),
            },
            {
                "properties": {
                    "OBJECTID": 2, "DFIRM_ID": "12103C", "VERSION_ID": "2.4.3.2",
                    "SFHA_TF": "F", "FLD_ZONE": "X", "ZONE_SUBTY": None,
                },
                "geometry": mapping(Polygon([
                    (-82.75, 27.70), (-82.70, 27.70),
                    (-82.70, 27.80), (-82.75, 27.80), (-82.75, 27.70),
                ])),
            },
        ]
        studies = {("12103C", "2.4.3.2"): {"INDX_EFFDT": 1629763200000}}

        result = summarize_zcta("33703", zcta, features, studies)

        self.assertAlmostEqual(result["nfhl_mapped_pct_zcta"], 100, places=4)
        self.assertLessEqual(result["nfhl_mapped_area_km2"], result["zcta_area_km2"] + 1e-9)
        self.assertAlmostEqual(result["sfha_pct_zcta"], 50, places=2)
        self.assertAlmostEqual(result["sfha_pct_nfhl_mapped"], 50, places=2)
        self.assertLess(result["not_represented_by_nfhl_zones_km2"], 0.01)
        self.assertEqual(result["nfhl_study_effective_dates"], "2021-08-24")
        self.assertEqual(result["nfhl_dfirm_versions"], "12103C:2.4.3.2")

    def test_summary_reports_area_not_represented_by_zone_polygons(self):
        zcta = Polygon([
            (-82.80, 27.70), (-82.70, 27.70),
            (-82.70, 27.80), (-82.80, 27.80), (-82.80, 27.70),
        ])
        feature = {
            "properties": {
                "OBJECTID": 1, "DFIRM_ID": "12103C", "VERSION_ID": "2.4.3.2",
                "SFHA_TF": "T", "FLD_ZONE": "AE", "ZONE_SUBTY": None,
            },
            "geometry": mapping(Polygon([
                (-82.80, 27.70), (-82.75, 27.70),
                (-82.75, 27.80), (-82.80, 27.80), (-82.80, 27.70),
            ])),
        }
        studies = {("12103C", "2.4.3.2"): {"INDX_EFFDT": 1629763200000}}

        result = summarize_zcta("33706", zcta, [feature], studies)

        self.assertAlmostEqual(result["sfha_pct_zcta"], 50, places=2)
        self.assertAlmostEqual(result["nfhl_mapped_pct_zcta"], 50, places=2)
        self.assertGreater(result["not_represented_by_nfhl_zones_km2"], 0)

    def test_invalid_geometry_is_repaired_and_checked(self):
        bowtie = Polygon([(0, 0), (1, 1), (0, 1), (1, 0), (0, 0)])
        repaired = _validate_geometry(bowtie, "test")
        self.assertTrue(repaired.is_valid)
        self.assertFalse(repaired.is_empty)

    def test_epsg_transform_round_trip_is_verified(self):
        _validate_coordinate_transform(box(-82.8, 27.7, -82.7, 27.8), "test ZCTA")

    def test_duplicate_nfhl_feature_ids_are_rejected(self):
        feature = {
            "properties": {"OBJECTID": 7},
            "geometry": mapping(box(-82.8, 27.7, -82.7, 27.8)),
        }
        with patch("scripts.summarize_nfhl_hazard.request_json", return_value={"features": [feature, feature]}):
            with self.assertRaisesRegex(ValueError, "duplicate OBJECTID"):
                query_zone_features(box(-82.8, 27.7, -82.7, 27.8))

    def test_missing_study_effective_date_is_explicitly_unknown(self):
        zcta = box(-82.8, 27.7, -82.7, 27.8)
        feature = {
            "properties": {
                "OBJECTID": 9, "DFIRM_ID": "12103C", "VERSION_ID": "2.4.3.2",
                "SFHA_TF": "T", "FLD_ZONE": "AE", "ZONE_SUBTY": None,
            },
            "geometry": mapping(zcta),
        }
        with patch("scripts.summarize_nfhl_hazard.request_json", return_value={"features": []}):
            studies = query_study_metadata([feature])
        result = summarize_zcta("33703", zcta, [feature], studies)
        self.assertEqual(result["nfhl_study_effective_dates"], "UNKNOWN (12103C:2.4.3.2)")


class HazardDashboardTests(unittest.TestCase):
    def test_flood_hazard_tab_renders_without_affecting_existing_views(self):
        app = AppTest.from_file(str(ROOT / "dashboard_pilot.py"), default_timeout=30).run()

        self.assertEqual(len(app.exception), 0)
        labels = [tab.label for tab in app.tabs]
        self.assertIn("Flood Hazard Context", labels)
        self.assertIn("2024 ZIP Comparison", labels)
        self.assertIn("2024 Exposure Pilot", labels)
        if (ROOT / "data/processed/nfhl_zcta_hazard_summary.csv").is_file():
            frames = [element.value for element in app.dataframe]
            hazard = next(frame for frame in frames if "Census ZCTA" in frame.columns)
            self.assertEqual(hazard.columns.tolist(), [
                "Census ZCTA", "NFHL area represented (%)", "Mapped SFHA area (km2)",
                "SFHA share of full ZCTA (%)",
            ])
            self.assertEqual(hazard["Census ZCTA"].tolist(), ["33703", "33706", "33708"])


class SavedHazardArtifactTests(unittest.TestCase):
    def test_summary_reconciles_to_retained_source_geometries(self):
        summary_path = ROOT / "data/processed/nfhl_zcta_hazard_summary.csv"
        manifest_path = ROOT / "reports/nfhl_zcta_hazard_metadata.json"
        if not summary_path.is_file() or not manifest_path.is_file():
            self.skipTest("Generated NFHL outputs are not present")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hashes = manifest["input_snapshot_sha256"]
        snapshot = None
        for candidate in (ROOT / "data/raw").glob("nfhl_zcta_hazard_*"):
            if all(
                (candidate / name).is_file()
                and hashlib.sha256((candidate / name).read_bytes()).hexdigest() == digest
                for name, digest in hashes.items()
            ):
                snapshot = candidate
                break
        self.assertIsNotNone(snapshot, "No retained NFHL snapshot matches the manifest hashes")

        with summary_path.open(newline="", encoding="utf-8") as handle:
            summary = {row["zcta5"]: row for row in csv.DictReader(handle)}
        boundaries = load_zcta_geometries()
        self.assertEqual(set(summary), set(ZIP_CODES))
        self.assertEqual(set(boundaries), set(ZIP_CODES))

        for zcta in ZIP_CODES:
            features = json.loads((snapshot / f"nfhl_zones_{zcta}.geojson").read_text(encoding="utf-8"))["features"]
            identifiers = [feature["properties"].get("OBJECTID") for feature in features]
            self.assertTrue(all(identifier is not None for identifier in identifiers))
            self.assertEqual(len(identifiers), len(set(identifiers)))

            boundary = boundaries[zcta]
            by_status = {"T": [], "F": [], "other": []}
            count = 0
            for feature in features:
                geometry = shapely_shape(feature["geometry"])
                if not geometry.is_valid:
                    geometry = geometry.buffer(0)
                self.assertTrue(geometry.is_valid)
                clipped = geometry.intersection(boundary)
                if clipped.is_empty or clipped.area == 0:
                    continue
                status = feature["properties"].get("SFHA_TF")
                by_status[status if status in ("T", "F") else "other"].append(clipped)
                count += 1

            class_unions = {
                status: unary_union(geometries).intersection(boundary) if geometries else None
                for status, geometries in by_status.items()
            }
            mapped_parts = [geometry for geometry in class_unions.values() if geometry is not None]
            mapped = unary_union(mapped_parts).intersection(boundary)
            sfha = class_unions["T"]
            geod = Geod(ellps="GRS80")

            def area(geometry):
                return abs(geod.geometry_area_perimeter(geometry)[0]) if geometry is not None else 0.0

            total_area = area(boundary)
            mapped_raw_area = area(mapped)
            sfha_raw_area = area(sfha)
            mapped_area = min(mapped_raw_area, total_area)
            sfha_area = min(sfha_raw_area, mapped_area)
            row = summary[zcta]
            self.assertEqual(int(row["nfhl_polygon_count"]), count)
            self.assertAlmostEqual(float(row["zcta_area_km2"]), total_area / 1_000_000, delta=1e-8)
            self.assertAlmostEqual(float(row["nfhl_mapped_area_km2"]), mapped_area / 1_000_000, delta=1e-8)
            self.assertAlmostEqual(float(row["sfha_area_km2"]), sfha_area / 1_000_000, delta=1e-8)
            self.assertAlmostEqual(float(row["sfha_pct_zcta"]), sfha_area / total_area * 100, delta=1e-6)
            self.assertAlmostEqual(float(row["nfhl_mapped_area_adjustment_m2"]), mapped_raw_area - mapped_area, delta=1e-5)
            self.assertAlmostEqual(float(row["sfha_area_adjustment_m2"]), sfha_raw_area - sfha_area, delta=1e-5)


if __name__ == "__main__":
    unittest.main()