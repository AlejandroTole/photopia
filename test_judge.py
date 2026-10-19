"""Tests for plan.judge.judge_render: closes the render -> judge loop."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from plan.judge import judge_render


TEST_CONFIG = {
    "models": {
        "planner": "qwen2.5vl:7b",
        "judge": "qwen2.5vl:7b",
        "ollama_url": "http://127.0.0.1:11434",
    },
}


def _make_fake_response(payload_text: str) -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"message": {"content": payload_text}}
    return response


class JudgeRenderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.render_path = Path(self.temp_dir.name) / "render.jpg"
        Image.new("RGB", (64, 64), color=(120, 110, 100)).save(self.render_path, format="JPEG")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_good_render_is_accepted_with_no_adjustments(self):
        good_response_text = (
            "```json\n"
            "{\n"
            '  "accept": true,\n'
            '  "score": 92,\n'
            '  "issues": [],\n'
            '  "adjustments": {\n'
            '    "exposure_ev": 0.0,\n'
            '    "sigmoid_contrast": 0.0,\n'
            '    "sigmoid_skew": 0.0,\n'
            '    "warmth_shift": 0.0\n'
            "  },\n"
            '  "reasoning": "Render natural, bien balanceado, sin artefactos."\n'
            "}\n"
            "```"
        )
        with patch("plan.judge.requests.post", return_value=_make_fake_response(good_response_text)) as mock_post:
            verdict = judge_render(self.render_path, camera_jpg=None, config=TEST_CONFIG)

        mock_post.assert_called_once()
        self.assertTrue(verdict["accept"])
        self.assertEqual(verdict["score"], 92)
        self.assertEqual(verdict["issues"], [])
        self.assertEqual(
            verdict["adjustments"],
            {
                "exposure_ev": 0.0,
                "sigmoid_contrast": 0.0,
                "sigmoid_skew": 0.0,
                "warmth_shift": 0.0,
            },
        )

    def test_bad_render_is_rejected_with_clamped_adjustments(self):
        bad_response_text = (
            "```json\n"
            "{\n"
            '  "accept": false,\n'
            '  "score": 35,\n'
            '  "issues": ["Dominante de color verde", "Altas luces quemadas", "Negros aplastados"],\n'
            '  "adjustments": {\n'
            '    "exposure_ev": -0.9,\n'
            '    "sigmoid_contrast": -2.0,\n'
            '    "sigmoid_skew": 0.9,\n'
            '    "warmth_shift": -0.5\n'
            "  },\n"
            '  "reasoning": "Clipping en altas luces y dominante verde generalizada."\n'
            "}\n"
            "```"
        )
        with patch("plan.judge.requests.post", return_value=_make_fake_response(bad_response_text)) as mock_post:
            verdict = judge_render(self.render_path, camera_jpg=None, config=TEST_CONFIG)

        mock_post.assert_called_once()
        self.assertFalse(verdict["accept"])
        self.assertEqual(verdict["score"], 35)
        self.assertEqual(len(verdict["issues"]), 3)
        # Adjustments must be clamped to the judge's conservative bounds,
        # regardless of how extreme the model's raw proposal was.
        self.assertEqual(verdict["adjustments"]["exposure_ev"], -0.5)
        self.assertEqual(verdict["adjustments"]["sigmoid_contrast"], -0.5)
        self.assertEqual(verdict["adjustments"]["sigmoid_skew"], 0.3)
        self.assertEqual(verdict["adjustments"]["warmth_shift"], -0.1)

    def test_missing_render_returns_safe_fallback(self):
        verdict = judge_render(Path(self.temp_dir.name) / "missing.jpg", config=TEST_CONFIG)
        self.assertTrue(verdict["accept"])
        self.assertEqual(verdict["adjustments"], {
            "exposure_ev": 0.0,
            "sigmoid_contrast": 0.0,
            "sigmoid_skew": 0.0,
            "warmth_shift": 0.0,
        })
        self.assertTrue(any("Juez no disponible" in issue for issue in verdict["issues"]))

    def test_ollama_connection_error_returns_safe_fallback(self):
        with patch("plan.judge.requests.post", side_effect=ConnectionError("no route")):
            verdict = judge_render(self.render_path, config=TEST_CONFIG)
        self.assertTrue(verdict["accept"])
        self.assertTrue(any("Juez no disponible" in issue for issue in verdict["issues"]))

    def test_includes_camera_reference_image_when_available(self):
        camera_jpg = Path(self.temp_dir.name) / "camera.jpg"
        Image.new("RGB", (64, 64), color=(80, 90, 100)).save(camera_jpg, format="JPEG")
        good_response_text = (
            '{"accept": true, "score": 80, "issues": [], '
            '"adjustments": {"exposure_ev": 0.0, "sigmoid_contrast": 0.0, '
            '"sigmoid_skew": 0.0, "warmth_shift": 0.0}}'
        )
        with patch("plan.judge.requests.post", return_value=_make_fake_response(good_response_text)) as mock_post:
            judge_render(self.render_path, camera_jpg=camera_jpg, config=TEST_CONFIG)

        sent_payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(len(sent_payload["messages"][0]["images"]), 2)


if __name__ == "__main__":
    unittest.main()
