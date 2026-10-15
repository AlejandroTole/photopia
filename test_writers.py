"""Roundtrip tests for exposure, whitebalance and sigmoid writers."""
import struct
import tempfile
import unittest
from pathlib import Path
import shutil

from apply.writers.exposure import apply_exposure, decode_exposure_hex
from apply.writers.sigmoid import apply_sigmoid, decode_sigmoid_hex
from apply.writers.whitebalance import apply_temperature, decode_temperature_hex
from apply.xmp import find_operation_modules, read_xmp, select_target_module
from plan.safety import LOOK_CONTRAST_CEILING, sanitize_plan


TEMPLATE = Path(__file__).resolve().parent / "templates" / "base.NEF.xmp"
# Packed from darktable 5.6.1 src/iop/sharpen.c:
# DT_MODULE_INTROSPECTION(1, dt_iop_sharpen_params_t)
# radius=2.0, amount=0.5, threshold=0.5
SHARPEN_DEFAULT_HEX = struct.pack("<fff", 2.0, 0.5, 0.5).hex()


class SharpenTemplateTests(unittest.TestCase):
    def test_template_has_enabled_sharpen_defaults(self):
        content = read_xmp(TEMPLATE)
        modules = find_operation_modules(content, "sharpen")
        self.assertEqual(len(modules), 1)
        sharpen = modules[0]
        self.assertEqual(sharpen["enabled"], 1)
        self.assertEqual(sharpen["modversion"], 1)
        self.assertEqual(sharpen["params"], SHARPEN_DEFAULT_HEX)
        self.assertIn('darktable:history_end="12"', content)


class WriterRoundtripTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.xmp_path = Path(self.temp_dir.name) / "base.NEF.xmp"
        shutil.copy2(TEMPLATE, self.xmp_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_exposure_write_roundtrip(self):
        success, message, merged = apply_exposure(
            self.xmp_path,
            {"exposure": 0.25, "black": 0.0},
            simulate=False,
            limits={"exposure_ev": [-1.0, 1.0]},
        )
        self.assertTrue(success, message)
        content = read_xmp(self.xmp_path)
        target = select_target_module(find_operation_modules(content, "exposure"))
        params = decode_exposure_hex(target["params"])
        self.assertAlmostEqual(params["exposure"], 0.25, places=3)
        self.assertAlmostEqual(merged["exposure"], 0.25, places=3)

    def test_sigmoid_write_roundtrip(self):
        success, message, merged = apply_sigmoid(
            self.xmp_path,
            {"contrast": 2.0, "skew": -0.1},
            simulate=False,
            limits={"sigmoid_contrast": [0.8, 3.5], "sigmoid_skew": [-0.6, 0.6]},
        )
        self.assertTrue(success, message)
        content = read_xmp(self.xmp_path)
        target = select_target_module(find_operation_modules(content, "sigmoid"))
        params = decode_sigmoid_hex(target["params"])
        self.assertAlmostEqual(params["contrast"], 2.0, places=3)
        self.assertAlmostEqual(params["skew"], -0.1, places=3)
        self.assertAlmostEqual(merged["contrast"], 2.0, places=3)

    def test_whitebalance_write_roundtrip(self):
        success, message, merged = apply_temperature(
            self.xmp_path,
            {"red": 1.85, "blue": 1.42},
            simulate=False,
            limits={"temperature_delta_ratio": [-0.15, 0.15]},
        )
        self.assertTrue(success, message)
        content = read_xmp(self.xmp_path)
        target = select_target_module(find_operation_modules(content, "temperature"))
        params = decode_temperature_hex(target["params"])
        self.assertAlmostEqual(params["red"], 1.85, places=3)
        self.assertAlmostEqual(params["blue"], 1.42, places=3)
        self.assertAlmostEqual(merged["red"], 1.85, places=3)


class SafetyGradeTests(unittest.TestCase):
    def test_default_contrast_is_2_0(self):
        sanitized, _notes = sanitize_plan(
            {},
            {},
            {"sigmoid_contrast": [0.8, 3.5], "sigmoid_skew": [-0.6, 0.6]},
        )
        self.assertAlmostEqual(sanitized["sigmoid"]["contrast"], 2.0, places=3)

    def test_contrast_1_8_stays_inside_limits(self):
        sanitized, notes = sanitize_plan(
            {"sigmoid": {"contrast": 1.8}},
            {},
            {"sigmoid_contrast": [0.8, 3.5], "sigmoid_skew": [-0.6, 0.6]},
        )
        self.assertAlmostEqual(sanitized["sigmoid"]["contrast"], 1.8, places=3)
        self.assertFalse(any("Contraste Sigmoid" in note for note in notes))

    def test_look_ceiling_is_inside_sanitize_limits(self):
        limits = {"sigmoid_contrast": [0.8, 3.5], "sigmoid_skew": [-0.6, 0.6]}
        at_ceiling, _ = sanitize_plan(
            {"sigmoid": {"contrast": LOOK_CONTRAST_CEILING}},
            {},
            limits,
        )
        above, notes = sanitize_plan(
            {"sigmoid": {"contrast": 3.0}},
            {},
            limits,
        )
        self.assertAlmostEqual(at_ceiling["sigmoid"]["contrast"], 2.2, places=3)
        self.assertAlmostEqual(above["sigmoid"]["contrast"], 2.2, places=3)
        self.assertTrue(any("Contraste Sigmoid" in note for note in notes))
        self.assertLessEqual(LOOK_CONTRAST_CEILING, limits["sigmoid_contrast"][1])


if __name__ == "__main__":
    unittest.main()
