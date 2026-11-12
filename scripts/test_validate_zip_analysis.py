import csv
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_zip_analysis.py"
ANNUAL_SOURCE = ROOT / "data" / "processed" / "nfip_loss_concentration_by_year.csv"
ZIP_SOURCE = ROOT / "data" / "processed" / "nfip_zip_loss_severity.csv"


class ZipValidationCommandTests(unittest.TestCase):
    def run_validator(self, annual_path, zip_path):
        return subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                "--annual-path",
                str(annual_path),
                "--zip-path",
                str(zip_path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_valid_saved_inputs_exit_zero(self):
        result = self.run_validator(ANNUAL_SOURCE, ZIP_SOURCE)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ALL VALIDATION CHECKS PASSED", result.stdout)

    def test_invalid_saved_inputs_exit_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            annual_path = Path(directory) / ANNUAL_SOURCE.name
            zip_path = Path(directory) / ZIP_SOURCE.name
            shutil.copyfile(ANNUAL_SOURCE, annual_path)
            shutil.copyfile(ZIP_SOURCE, zip_path)

            rows = []
            with zip_path.open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                fieldnames = reader.fieldnames
                rows = list(reader)
            rows[0]["total_payments"] = str(
                float(rows[0]["total_payments"]) + 1
            )
            with zip_path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            result = self.run_validator(annual_path, zip_path)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("VALIDATION FAILED", result.stdout)


if __name__ == "__main__":
    unittest.main()
