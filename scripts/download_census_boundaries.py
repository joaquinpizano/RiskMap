"""Download and validate the pinned 2025 Census TIGER/Line boundary archives."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "reports" / "census_boundary_source_manifest.json"
RAW_DIR = ROOT / "data" / "raw"
CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_archive(path: Path, record: dict) -> None:
    expected_size = record["size_bytes"]
    if path.stat().st_size != expected_size:
        raise ValueError(f"Unexpected size for {path.name}: {path.stat().st_size} != {expected_size}")
    actual_hash = sha256_file(path)
    if actual_hash.lower() != record["sha256"].lower():
        raise ValueError(f"SHA-256 mismatch for {path.name}: {actual_hash}")
    try:
        with zipfile.ZipFile(path) as archive:
            missing = set(record["required_members"]) - set(archive.namelist())
            if missing:
                raise ValueError(f"{path.name} is missing required members: {sorted(missing)}")
            corrupt = archive.testzip()
            if corrupt:
                raise ValueError(f"Corrupt member in {path.name}: {corrupt}")
    except zipfile.BadZipFile as error:
        raise ValueError(f"Not a valid ZIP archive: {path}") from error


def download_archive(record: dict, output_dir: Path) -> Path:
    target = output_dir / record["filename"]
    if target.exists():
        validate_archive(target, record)
        print(f"Verified existing archive: {target}")
        return target

    output_dir.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f"{target.name}.", suffix=".part", dir=output_dir, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            request = Request(
                record["url"],
                headers={"User-Agent": "RiskMap reproducible Census boundary setup"},
            )
            with urlopen(request, timeout=180) as response:
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) != record["size_bytes"]:
                    raise ValueError(
                        f"Unexpected Content-Length for {target.name}: {content_length}"
                    )
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    temporary.write(chunk)

        validate_archive(temporary_path, record)
        if target.exists():
            raise FileExistsError(f"Refusing to overwrite an archive created during download: {target}")
        temporary_path.rename(target)
        temporary_path = None
        print(f"Downloaded and verified: {target}")
        return target
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=RAW_DIR)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("release") != "2025 TIGER/Line" or not manifest.get("archives"):
        parser.error("Unsupported or empty Census source manifest")
    try:
        for record in manifest["archives"]:
            download_archive(record, args.output_dir)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()