"""Summarize FEMA NFHL flood-hazard zones by selected Census ZCTAs.

Downloads source features into a new raw snapshot directory and writes a CSV
summary plus a JSON manifest. Existing outputs are never overwritten.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from math import isfinite
from pathlib import Path
import re
import tempfile
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import zipfile

import shapefile
from pyproj import CRS, Geod, Transformer
from shapely.geometry import MultiPolygon, Polygon, shape as shapely_shape
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[1]
ZCTA_ARCHIVE = ROOT / "data" / "raw" / "tl_2025_us_zcta520.zip"
ZCTA_SOURCE_URL = "https://www2.census.gov/geo/tiger/TIGER2025/ZCTA520/tl_2025_us_zcta520.zip"
SERVICE = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"
ZONE_LAYER = 28
STUDY_TABLE = 41
ZIP_CODES = ("33703", "33706", "33708")
SOURCE_CRS = 4269
AREA_CRS = 26917
AREA_GEOD = Geod(ellps="GRS80")
ZONE_FIELDS = ("OBJECTID", "DFIRM_ID", "VERSION_ID", "FLD_ZONE", "SFHA_TF", "ZONE_SUBTY")
STUDY_FIELDS = ("DFIRM_ID", "VERSION_ID", "STUDY_NM", "STATE_NM", "CNTY_NM", "INDX_EFFDT", "DBREV_DT")
PAGE_SIZE = 1000


def request_json(url: str, params: dict[str, object], post: bool = False) -> dict:
    encoded = urlencode(params)
    headers = {"User-Agent": "RiskMap local research workflow"}
    if post:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = Request(
        url if post else f"{url}?{encoded}",
        data=encoded.encode("utf-8") if post else None,
        headers=headers,
    )
    with urlopen(request, timeout=90) as response:
        payload = json.load(response)
    if "error" in payload:
        raise ValueError(f"FEMA NFHL request failed: {payload['error']}")
    return payload


def _validate_geometry(geometry, label: str):
    if geometry.is_empty:
        raise ValueError(f"Empty geometry for {label}")
    if not geometry.is_valid:
        geometry = geometry.buffer(0)
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError(f"Invalid geometry for {label}")
    return geometry


def load_zcta_geometries(archive_path: Path = ZCTA_ARCHIVE) -> dict[str, object]:
    """Read exact 2025 TIGER ZCTA records and verify their declared CRS."""
    if not archive_path.is_file():
        raise FileNotFoundError(f"Missing Census ZCTA archive: {archive_path}")
    basename = "tl_2025_us_zcta520"
    wanted = set(ZIP_CODES)
    with zipfile.ZipFile(archive_path) as archive, tempfile.TemporaryDirectory(prefix="riskmap_zcta_") as temp:
        for extension in (".shp", ".shx", ".dbf", ".prj"):
            member = basename + extension
            if member not in archive.namelist():
                raise ValueError(f"Census archive is missing {member}")
            archive.extract(member, temp)
        crs = CRS.from_wkt((Path(temp) / f"{basename}.prj").read_text(encoding="utf-8"))
        if crs.to_epsg() != SOURCE_CRS:
            raise ValueError(f"Expected Census ZCTA CRS EPSG:{SOURCE_CRS}; found {crs.to_string()}")

        reader = shapefile.Reader(str(Path(temp) / basename), encoding="utf-8")
        try:
            fields = [field[0] for field in reader.fields[1:]]
            if "ZCTA5CE20" not in fields:
                raise ValueError(f"Expected ZCTA5CE20 field; found {fields}")
            index = fields.index("ZCTA5CE20")
            found = {}
            for record_index, record in enumerate(reader.iterRecords()):
                zcta = str(record[index]).strip()
                if zcta in wanted:
                    if zcta in found:
                        raise ValueError(f"Duplicate Census ZCTA geometry: {zcta}")
                    found[zcta] = _validate_geometry(
                        shapely_shape(reader.shape(record_index).__geo_interface__), f"ZCTA {zcta}"
                    )
        finally:
            reader.close()
    if set(found) != wanted:
        raise ValueError(f"Census ZCTA coverage mismatch; found {sorted(found)}")
    return found


def get_layer_metadata() -> dict:
    layer = request_json(f"{SERVICE}/{ZONE_LAYER}", {"f": "pjson"})
    fields = {field["name"] for field in layer.get("fields", [])}
    if layer.get("geometryType") != "esriGeometryPolygon":
        raise ValueError("NFHL Flood Hazard Zones is not a polygon layer")
    source_wkid = layer.get("sourceSpatialReference", {}).get("latestWkid")
    if source_wkid != SOURCE_CRS:
        raise ValueError(f"Expected FEMA NFHL source CRS EPSG:{SOURCE_CRS}; found {source_wkid}")
    missing = set(ZONE_FIELDS) - fields
    if missing:
        raise ValueError(f"NFHL Flood Hazard Zones layer is missing fields: {sorted(missing)}")
    return layer


def _esri_rings(geometry) -> list[list[list[float]]]:
    polygons = [geometry] if isinstance(geometry, Polygon) else list(geometry.geoms)
    rings = []
    for polygon in polygons:
        exterior = [[x, y] for x, y in polygon.exterior.coords]
        if sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(exterior, exterior[1:])) > 0:
            exterior.reverse()
        rings.append(exterior)
        for interior in polygon.interiors:
            hole = [[x, y] for x, y in interior.coords]
            if sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(hole, hole[1:])) < 0:
                hole.reverse()
            rings.append(hole)
    return rings


def query_zone_features(zcta_geometry) -> list[dict]:
    """Fetch all NFHL polygons intersecting one exact Census ZCTA geometry."""
    params = {
        "geometry": json.dumps({
            "rings": _esri_rings(zcta_geometry),
            "spatialReference": {"wkid": SOURCE_CRS},
        }, separators=(",", ":")),
        "geometryType": "esriGeometryPolygon",
        "inSR": str(SOURCE_CRS),
        "outSR": str(SOURCE_CRS),
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": ",".join(ZONE_FIELDS),
        "returnGeometry": "true",
        "f": "geojson",
        "orderByFields": "OBJECTID",
        "resultRecordCount": str(PAGE_SIZE),
    }
    features = []
    seen = set()
    offset = 0
    while True:
        page = request_json(
            f"{SERVICE}/{ZONE_LAYER}/query",
            {**params, "resultOffset": str(offset)},
            post=True,
        )
        page_features = page.get("features")
        if not isinstance(page_features, list):
            raise ValueError("FEMA response did not contain GeoJSON features")
        for feature in page_features:
            properties = feature.get("properties") or {}
            identifier = properties.get("OBJECTID")
            if identifier is None or identifier in seen:
                raise ValueError("NFHL response contains a missing or duplicate OBJECTID")
            if not feature.get("geometry"):
                raise ValueError(f"NFHL feature {identifier} has no geometry")
            seen.add(identifier)
            features.append(feature)
        offset += len(page_features)
        if not page_features or len(page_features) < PAGE_SIZE:
            break
    if not features:
        raise ValueError("FEMA NFHL returned no hazard polygons for a target ZCTA")
    return features


def query_study_metadata(features: list[dict]) -> dict[tuple[str, str], dict]:
    keys = {
        (feature["properties"].get("DFIRM_ID"), feature["properties"].get("VERSION_ID"))
        for feature in features
    }
    if any(not dfirm or not version for dfirm, version in keys):
        raise ValueError("NFHL features contain a missing DFIRM_ID or VERSION_ID")
    if any(not re.fullmatch(r"[A-Z0-9]{6}", dfirm) for dfirm, _ in keys):
        raise ValueError("NFHL returned an unexpected DFIRM_ID")
    keys = sorted(keys)
    dfirm_ids = sorted({dfirm for dfirm, _ in keys})
    where = "DFIRM_ID IN (" + ",".join(f"'{value}'" for value in dfirm_ids) + ")"
    params = {
        "where": where,
        "outFields": ",".join(STUDY_FIELDS),
        "returnGeometry": "false",
        "f": "json",
        "orderByFields": "OBJECTID",
        "resultRecordCount": str(PAGE_SIZE),
    }
    records = []
    offset = 0
    while True:
        page = request_json(
            f"{SERVICE}/{STUDY_TABLE}/query",
            {**params, "resultOffset": str(offset)},
        )
        page_features = page.get("features")
        if not isinstance(page_features, list):
            raise ValueError("FEMA Study_Info response did not contain records")
        records.extend(feature.get("attributes", {}) for feature in page_features)
        offset += len(page_features)
        if not page_features or len(page_features) < PAGE_SIZE:
            break
    by_key = {
        (record.get("DFIRM_ID"), record.get("VERSION_ID")): record
        for record in records
    }
    if len(by_key) != len(records):
        raise ValueError("FEMA Study_Info returned duplicate map-version records")
    return {key: by_key[key] for key in keys if key in by_key}


def _union(geometries):
    return unary_union(geometries) if geometries else None


def _union_clipped(geometries, boundary):
    merged = _union(geometries)
    if merged is None:
        return None
    clipped = merged.intersection(boundary)
    return _validate_geometry(clipped, "union clipped to Census ZCTA") if not clipped.is_empty else None


def _validate_coordinate_transform(geometry, label: str) -> None:
    point = geometry.representative_point()
    forward = Transformer.from_crs(SOURCE_CRS, AREA_CRS, always_xy=True)
    reverse = Transformer.from_crs(AREA_CRS, SOURCE_CRS, always_xy=True)
    x, y = forward.transform(point.x, point.y)
    longitude, latitude = reverse.transform(x, y)
    if (not all(isfinite(value) for value in (x, y, longitude, latitude))
        or abs(longitude - point.x) > 1e-8 or abs(latitude - point.y) > 1e-8):
        raise ValueError(f"Coordinate transformation round-trip failed for {label}")


def _geodesic_area_m2(geometry) -> float:
    return abs(AREA_GEOD.geometry_area_perimeter(geometry)[0]) if geometry is not None else 0.0


def summarize_zcta(zcta: str, zcta_geometry, features: list[dict], study_records: dict) -> dict:
    """Return mutually-exclusive area summaries in square kilometers."""
    _validate_coordinate_transform(zcta_geometry, f"ZCTA {zcta}")
    clipped_by_status = {"T": [], "F": [], "other": []}
    map_keys = set()
    intersecting_feature_count = 0

    for feature in features:
        properties = feature["properties"]
        geometry = _validate_geometry(shapely_shape(feature["geometry"]), f"NFHL feature {properties['OBJECTID']}")
        clipped = geometry.intersection(zcta_geometry)
        if clipped.is_empty or clipped.area == 0:
            continue
        clipped = _validate_geometry(clipped, f"NFHL/ZCTA intersection {properties['OBJECTID']}")
        status = properties.get("SFHA_TF")
        clipped_by_status[status if status in ("T", "F") else "other"].append(clipped)
        map_keys.add((properties["DFIRM_ID"], properties["VERSION_ID"]))
        intersecting_feature_count += 1

    if not intersecting_feature_count:
        raise ValueError(f"No NFHL zone polygons intersect Census ZCTA {zcta}")

    sfha = _union_clipped(clipped_by_status["T"], zcta_geometry)
    non_sfha = _union_clipped(clipped_by_status["F"], zcta_geometry)
    other = _union_clipped(clipped_by_status["other"], zcta_geometry)
    mapped_geometries = [geometry for geometry in (sfha, non_sfha, other) if geometry is not None]
    mapped = _union_clipped(mapped_geometries, zcta_geometry)
    if mapped is None:
        raise ValueError(f"NFHL mapped area is empty for Census ZCTA {zcta}")

    overlap = sfha.intersection(non_sfha) if sfha is not None and non_sfha is not None else None
    raw_sfha_area = _geodesic_area_m2(sfha)
    overlap_area = _geodesic_area_m2(overlap)
    non_sfha_exclusive = _geodesic_area_m2(non_sfha.difference(sfha)) if non_sfha is not None else 0.0
    known_area = _union([geometry for geometry in (sfha, non_sfha) if geometry is not None])
    other_area = _geodesic_area_m2(mapped.difference(known_area)) if known_area is not None else _geodesic_area_m2(mapped)
    total_area = _geodesic_area_m2(zcta_geometry)
    raw_mapped_area = _geodesic_area_m2(mapped)
    tolerance = max(0.000001, total_area * 1e-7)
    if (total_area <= 0 or raw_mapped_area > total_area + tolerance
        or raw_sfha_area > raw_mapped_area + tolerance):
        raise ValueError(
            f"NFHL area exceeds Census ZCTA boundary for {zcta}: "
            f"total={total_area:.6f} m2, mapped={raw_mapped_area:.6f} m2, "
            f"SFHA={raw_sfha_area:.6f} m2, tolerance={tolerance:.6f} m2"
        )
    mapped_area = min(raw_mapped_area, total_area)
    sfha_area = min(raw_sfha_area, mapped_area)
    mapped_adjustment = raw_mapped_area - mapped_area
    sfha_adjustment = raw_sfha_area - sfha_area
    not_mapped_area = _geodesic_area_m2(zcta_geometry.difference(mapped))
    partition_area = sfha_area + non_sfha_exclusive + other_area
    if abs(partition_area - mapped_area) > tolerance:
        raise ValueError(
            f"Area summary failed reconciliation for Census ZCTA {zcta}: "
            f"total={total_area:.6f} m2, mapped={mapped_area:.6f} m2, "
            f"SFHA={sfha_area:.6f} m2, partition={partition_area:.6f} m2, "
            f"tolerance={tolerance:.6f} m2"
        )

    date_values = set()
    for key in map_keys:
        record = study_records.get(key, {})
        if record.get("INDX_EFFDT"):
            date_values.add(
                datetime.fromtimestamp(record["INDX_EFFDT"] / 1000, tz=timezone.utc).date().isoformat()
            )
        else:
            date_values.add(f"UNKNOWN ({key[0]}:{key[1]})")
    date_values = sorted(date_values)
    versions = sorted(f"{dfirm}:{version}" for dfirm, version in map_keys)
    as_km2 = lambda value: value / 1_000_000
    return {
        "zcta5": zcta,
        "geographic_unit": "2020 Census ZCTA boundary in 2025 TIGER/Line release",
        "zcta_area_km2": as_km2(total_area),
        "nfhl_mapped_area_km2": as_km2(mapped_area),
        "nfhl_mapped_area_adjustment_m2": mapped_adjustment,
        "nfhl_mapped_pct_zcta": mapped_area / total_area * 100,
        "sfha_area_km2": as_km2(sfha_area),
        "sfha_area_adjustment_m2": sfha_adjustment,
        "sfha_pct_zcta": sfha_area / total_area * 100,
        "sfha_pct_nfhl_mapped": sfha_area / mapped_area * 100,
        "non_sfha_area_km2": as_km2(non_sfha_exclusive),
        "unclassified_nfhl_area_km2": as_km2(other_area),
        "not_represented_by_nfhl_zones_km2": as_km2(not_mapped_area),
        "sfha_non_sfha_overlap_km2": as_km2(overlap_area),
        "nfhl_polygon_count": intersecting_feature_count,
        "nfhl_study_effective_dates": ";".join(date_values),
        "nfhl_dfirm_versions": ";".join(versions),
    }


def _epoch_date(value):
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat() if value else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(summary_csv: Path, manifest_json: Path, raw_dir: Path) -> None:
    for output in (summary_csv, manifest_json, raw_dir):
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite existing output: {output}")
    print("Checking FEMA NFHL layer metadata...", flush=True)
    layer = get_layer_metadata()
    print("Reading selected Census ZCTA boundaries...", flush=True)
    zctas = load_zcta_geometries()
    raw_features = {}
    for zcta, geometry in zctas.items():
        print(f"Fetching NFHL polygons for Census ZCTA {zcta}...", flush=True)
        raw_features[zcta] = query_zone_features(geometry)
        print(f"  Retrieved {len(raw_features[zcta]):,} candidate polygons.", flush=True)
    relevant_features = {}
    for zcta, features in raw_features.items():
        relevant_features[zcta] = []
        for feature in features:
            geometry = _validate_geometry(
                shapely_shape(feature["geometry"]),
                f"NFHL feature {feature['properties'].get('OBJECTID')}",
            )
            if geometry.intersects(zctas[zcta]):
                relevant_features[zcta].append(feature)
    all_features = [feature for features in relevant_features.values() for feature in features]
    print(f"Resolving effective dates for {len(all_features):,} intersecting NFHL features...", flush=True)
    studies = query_study_metadata(all_features)
    summaries = [
        summarize_zcta(zcta, zctas[zcta], relevant_features[zcta], studies)
        for zcta in ZIP_CODES
    ]

    retrieved_at = datetime.now(timezone.utc)
    print("Saving new source snapshot and summary outputs...", flush=True)
    raw_dir.mkdir(parents=True, exist_ok=False)
    source_hashes = {}
    for zcta, features in raw_features.items():
        raw_path = raw_dir / f"nfhl_zones_{zcta}.geojson"
        raw_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
        source_hashes[raw_path.name] = _sha256(raw_path)

    import csv
    with summary_csv.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)

    study_manifest = []
    used_map_keys = sorted({
        (feature["properties"]["DFIRM_ID"], feature["properties"]["VERSION_ID"])
        for features in relevant_features.values()
        for feature in features
    })
    for key in used_map_keys:
        record = studies.get(key, {})
        study_manifest.append({
            "dfirm_id": key[0],
            "version_id": key[1],
            "study_name": record.get("STUDY_NM"),
            "state": record.get("STATE_NM"),
            "county": record.get("CNTY_NM"),
            "effective_date": _epoch_date(record.get("INDX_EFFDT")),
            "database_revision_date": _epoch_date(record.get("DBREV_DT")),
            "effective_date_status": "available" if record.get("INDX_EFFDT") else "missing from Study_Info",
        })
    manifest = {
        "status": "descriptive mapped-hazard context; not observed flooding or insurance loss",
        "retrieved_at_utc": retrieved_at.isoformat(),
        "sources": {
            "fema_nfhl_service": SERVICE,
            "fema_flood_hazard_zones_layer": f"{SERVICE}/{ZONE_LAYER}",
            "fema_study_info_table": f"{SERVICE}/{STUDY_TABLE}",
            "census_zcta_archive": ZCTA_SOURCE_URL,
            "census_archive_local_path": str(ZCTA_ARCHIVE.relative_to(ROOT)),
        },
        "source_metadata": {
            "nfhl_layer_name": layer.get("name"),
            "nfhl_layer_source_crs_epsg": SOURCE_CRS,
            "nfhl_zcta_feature_counts": {zcta: len(features) for zcta, features in raw_features.items()},
            "study_map_versions": study_manifest,
            "study_effective_date_gaps": [
                f"{item['dfirm_id']}:{item['version_id']}"
                for item in study_manifest if item["effective_date"] is None
            ],
            "geographic_coverage": list(ZIP_CODES),
        },
        "geographic_method": {
            "claims_geography": "reported postal ZIP in FEMA claims records",
            "hazard_geography": "2020 Census ZCTAs from the 2025 TIGER/Line ZCTA archive; not USPS ZIP boundaries",
            "aggregation": "intersect NFHL zone polygons with each complete target ZCTA in EPSG:4269, then union areas by SFHA_TF class",
            "area_measurement": "GRS80 ellipsoidal geodesic area from EPSG:4269 coordinates",
            "coordinate_transform_check": "ZCTA representative points round-trip through EPSG:4269 to EPSG:26917 and back",
            "geodesic_area_tolerance": "1e-7 of the full ZCTA area; mapped/SFHA values are capped at the ZCTA/mapped union only within this tolerance and adjustments are reported",
            "sfha_definition": "NFHL SFHA_TF = T polygon area; denominator is the full Census ZCTA polygon area",
            "overlap_handling": "overlap between SFHA_TF T and F is reported and assigned to SFHA in the exclusive area partition",
            "unrepresented_area": "ZCTA area not covered by a returned Flood Hazard Zones polygon; may include water or data gaps and is not labeled flood-free",
        },
        "field_definitions": {
            "zcta_area_km2": "full selected Census ZCTA polygon geodesic area on the GRS80 ellipsoid",
            "nfhl_mapped_area_km2": "union area of all intersecting NFHL zone polygons clipped to the ZCTA",
            "nfhl_mapped_area_adjustment_m2": "geodesic edge-segmentation excess capped from mapped area when within the stated tolerance",
            "nfhl_mapped_pct_zcta": "NFHL mapped area divided by full ZCTA area, percent",
            "sfha_area_km2": "union area with SFHA_TF = T, clipped to ZCTA",
            "sfha_area_adjustment_m2": "geodesic edge-segmentation excess capped from SFHA area when within the stated tolerance",
            "sfha_pct_zcta": "SFHA area divided by full ZCTA area, percent",
            "sfha_pct_nfhl_mapped": "SFHA area divided by NFHL mapped area, percent",
            "non_sfha_area_km2": "SFHA_TF = F area after subtracting any overlap with SFHA polygons",
            "unclassified_nfhl_area_km2": "mapped area without SFHA_TF equal to T or F",
            "not_represented_by_nfhl_zones_km2": "full ZCTA area less mapped zone union; not proof of no flood hazard",
            "sfha_non_sfha_overlap_km2": "area of overlap between unions of SFHA_TF T and F polygons",
            "nfhl_polygon_count": "number of returned NFHL features with positive-area intersection with the ZCTA",
            "nfhl_study_effective_dates": "semicolon-separated effective dates from linked Study_Info map versions",
            "nfhl_dfirm_versions": "semicolon-separated DFIRM_ID:VERSION_ID values intersecting the ZCTA",
        },
        "input_snapshot_sha256": source_hashes,
    }
    with manifest_json.open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    print(f"Saved {summary_csv}")
    print(f"Saved {manifest_json}")
    print(f"Saved source geometry under {raw_dir}")
    for row in summaries:
        print(f"{row['zcta5']}: {row['sfha_pct_zcta']:.2f}% of full ZCTA area in mapped SFHA")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-csv", type=Path, default=ROOT / "data/processed/nfhl_zcta_hazard_summary.csv")
    parser.add_argument("--manifest-json", type=Path, default=ROOT / "reports/nfhl_zcta_hazard_metadata.json")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=ROOT / "data/raw" / f"nfhl_zcta_hazard_{datetime.now(timezone.utc):%Y%m%d}",
    )
    args = parser.parse_args()
    try:
        run(args.summary_csv, args.manifest_json, args.raw_dir)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()