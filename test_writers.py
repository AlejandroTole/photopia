"""Roundtrip tests for exposure, whitebalance, sigmoid and saturation writers."""
import struct
import tempfile
import unittest
from pathlib import Path
import shutil

from apply.writers.exposure import apply_exposure, decode_exposure_hex
from apply.writers.saturation import apply_vibrance, decode_colorbalance_hex
from apply.writers.sigmoid import apply_sigmoid, decode_sigmoid_hex
from apply.writers.whitebalance import apply_temperature, decode_temperature_hex
from apply.xmp import find_operation_modules, read_xmp, select_target_module
from plan.safety import (
    LOOK_CONTRAST_CEILING,
    SATURATION_GLOBAL_LOOK_CEILING,
    VIBRANCE_LOOK_CEILING,
    sanitize_plan,
)


TEMPLATE = Path(__file__).resolve().parent / "templates" / "base.NEF.xmp"
# Packed from darktable 5.6.1 src/iop/sharpen.c:
# DT_MODULE_INTROSPECTION(1, dt_iop_sharpen_params_t)
# Tuned template: radius=2.0 (default), amount=0.4, threshold=0.2
SHARPEN_DEFAULT_HEX = struct.pack("<fff", 2.0, 0.4, 0.2).hex()


class SharpenTemplateTests(unittest.TestCase):
    def test_template_has_enabled_sharpen_defaults(self):
        content = read_xmp(TEMPLATE)
        modules = find_operation_modules(content, "sharpen")
        self.assertEqual(len(modules), 1)
        sharpen = modules[0]
        self.assertEqual(sharpen["enabled"], 1)
        self.assertEqual(sharpen["modversion"], 1)
        self.assertEqual(sharpen["params"], SHARPEN_DEFAULT_HEX)
        self.assertIn('darktable:history_end="13"', content)

    def test_template_has_enabled_colorbalancergb_real_defaults(self):
        # Defaults taken from darktable 5.6.1 src/iop/colorbalancergb.c
        # $DEFAULT: annotations for a freshly-added dt_iop_colorbalancergb_params_t
        # (modversion 5): all zero except the fall-off weights (1.0), the two
        # grey fulcrums (0.1845) and saturation_formula (1 = darktable UCS).
        content = read_xmp(TEMPLATE)
        modules = find_operation_modules(content, "colorbalancergb")
        self.assertEqual(len(modules), 1)
        colorbalance = modules[0]
        self.assertEqual(colorbalance["enabled"], 1)
        self.assertEqual(colorbalance["modversion"], 5)
        params = decode_colorbalance_hex(colorbalance["params"])
        self.assertEqual(params["vibrance"], 0.0)
        self.assertEqual(params["saturation_global"], 0.0)
        self.assertEqual(params["shadows_weight"], 1.0)
        self.assertEqual(params["highlights_weight"], 1.0)
        self.assertAlmostEqual(params["mask_grey_fulcrum"], 0.1845, places=4)
        self.assertAlmostEqual(params["grey_fulcrum"], 0.1845, places=4)
        self.assertEqual(params["saturation_formula"], 1)


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

    def test_vibrance_write_roundtrip(self):
        success, message, merged = apply_vibrance(
            self.xmp_path,
            {"vibrance": 0.25, "saturation_global": 0.1},
            simulate=False,
            limits={"saturation_vibrance": [-0.3, 0.5], "saturation_global": [-0.2, 0.3]},
        )
        self.assertTrue(success, message)
        content = read_xmp(self.xmp_path)
        target = select_target_module(find_operation_modules(content, "colorbalancergb"))
        params = decode_colorbalance_hex(target["params"])
        self.assertAlmostEqual(params["vibrance"], 0.25, places=3)
        self.assertAlmostEqual(params["saturation_global"], 0.1, places=3)
        self.assertAlmostEqual(merged["vibrance"], 0.25, places=3)
        # Untouched knobs must survive the roundtrip unchanged.
        self.assertAlmostEqual(params["grey_fulcrum"], 0.1845, places=4)
        self.assertEqual(params["saturation_formula"], 1)

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

    def test_default_vibrance_is_zero(self):
        sanitized, _notes = sanitize_plan(
            {},
            {},
            {"saturation_vibrance": [-0.3, 0.5], "saturation_global": [-0.2, 0.3]},
        )
        self.assertEqual(sanitized["saturation"]["vibrance"], 0.0)
        self.assertEqual(sanitized["saturation"]["saturation_global"], 0.0)

    def test_vibrance_look_ceiling_caps_aggressive_proposals(self):
        limits = {"saturation_vibrance": [-0.3, 0.5], "saturation_global": [-0.2, 0.3]}
        sanitized, _notes = sanitize_plan(
            {"saturation": {"vibrance": 0.5, "saturation_global": 0.3}},
            {},
            limits,
        )
        self.assertAlmostEqual(sanitized["saturation"]["vibrance"], VIBRANCE_LOOK_CEILING, places=3)
        self.assertAlmostEqual(
            sanitized["saturation"]["saturation_global"], SATURATION_GLOBAL_LOOK_CEILING, places=3
        )

    def test_color_cast_blocks_aggressive_vibrance(self):
        limits = {"saturation_vibrance": [-0.3, 0.5], "saturation_global": [-0.2, 0.3]}
        analysis = {
            "rgb_rendered": {
                "spatial_color_analysis": {
                    "summary": {"possible_global_green_cast": True}
                }
            }
        }
        sanitized, notes = sanitize_plan(
            {"saturation": {"vibrance": 0.3, "saturation_global": 0.15}},
            analysis,
            limits,
        )
        self.assertLessEqual(sanitized["saturation"]["vibrance"], 0.1)
        self.assertLessEqual(sanitized["saturation"]["saturation_global"], 0.05)
        self.assertTrue(any("Dominante de color global" in note for note in notes))

    def test_blown_highlights_cap_vibrance(self):
        limits = {"saturation_vibrance": [-0.3, 0.5], "saturation_global": [-0.2, 0.3]}
        analysis = {
            "rgb_rendered": {
                "clipping": {"highlight_percent": 2.0},
            }
        }
        sanitized, notes = sanitize_plan(
            {"saturation": {"vibrance": 0.3}},
            analysis,
            limits,
        )
        self.assertAlmostEqual(sanitized["saturation"]["vibrance"], 0.15, places=3)
        self.assertTrue(any("Viveza limitada a 0.15" in note for note in notes))


if __name__ == "__main__":
    unittest.main()
