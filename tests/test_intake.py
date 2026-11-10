import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from cadkin.tools.intake import fetch_asset, inspect_path, inspect_step

STEP = b"""ISO-10303-21;
HEADER; FILE_SCHEMA(('AUTOMOTIVE_DESIGN')); ENDSEC;
DATA;
#1=PRODUCT('x','Slider; O''Brien','',(#2));
/* #99=PRODUCT('fake','fake','',()); */
#2=(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.));
#3=NEXT_ASSEMBLY_USAGE_OCCURRENCE('a','','',#4,#5,$);
ENDSEC; END-ISO-10303-21;
"""


class IntakeTests(unittest.TestCase):
    def test_strings_comments_units_and_count_semantics(self):
        result = inspect_step(STEP)
        self.assertEqual(result["simple_entity_counts"]["PRODUCT"], 1)
        self.assertEqual(result["product_definitions"][0]["name"], "Slider; O'Brien")
        self.assertEqual(result["si_unit_declarations"], ["SI_UNIT(.MILLI.,.METRE.)"])
        self.assertNotIn("joints", result)
        self.assertNotIn("instance_count", result)

    def test_truncated_or_non_step_input_rejected(self):
        for data in (b"not step", STEP[:-30]):
            with self.assertRaises(ValueError):
                inspect_step(data)

    def test_archive_inspection_never_extracts_members(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "test.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../outside.step", STEP)
            result = inspect_path(path)
            self.assertEqual(len(result["step_files"]), 1)
            self.assertEqual([p.name for p in Path(root).iterdir()], ["test.zip"])

    def test_archive_size_limit(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "test.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("a.step", STEP)
            with patch("cadkin.tools.intake.MAX_BYTES", 10), self.assertRaises(ValueError):
                inspect_path(path)

    def test_download_checksum_and_existing_output_protection(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            config, target = root / "source.json", root / "data.zip"
            spec = {"download_url": "https://example.org/model.zip",
                    "sha256": hashlib.sha256(STEP).hexdigest(), "size_bytes": len(STEP)}
            config.write_text(json.dumps(spec), encoding="utf-8")
            with patch("cadkin.tools.intake.urlopen", return_value=io.BytesIO(STEP)):
                fetch_asset(config, target)
            self.assertEqual(target.read_bytes(), STEP)
            with self.assertRaises(ValueError):
                fetch_asset(config, target)
            target.unlink()
            spec["sha256"] = "0" * 64
            config.write_text(json.dumps(spec), encoding="utf-8")
            with patch("cadkin.tools.intake.urlopen", return_value=io.BytesIO(STEP)), self.assertRaises(ValueError):
                fetch_asset(config, target)
            self.assertFalse(target.exists())
            self.assertEqual([p.name for p in root.iterdir()], ["source.json"])


if __name__ == "__main__":
    unittest.main()
