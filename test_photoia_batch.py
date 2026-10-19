import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import photoia
from render.darktable_cli import DarktableCli


class BatchSidecarTests(unittest.TestCase):
    def test_batch_reports_and_ignores_orphan_xmp(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "fotos para editar"
            input_dir.mkdir()
            photo = input_dir / "selected.NEF"
            photo.touch()
            (input_dir / "orphan.NEF.xmp").touch()
            output_dir = root / "resultados"
            errors = io.StringIO()

            with (
                patch.object(photoia, "INPUT_DIR", input_dir),
                patch.object(photoia, "OUTPUT_DIR", output_dir),
                patch.object(photoia, "load_config", return_value={}),
                patch.object(photoia, "process_photo", return_value=(True, "")) as process,
                redirect_stderr(errors),
            ):
                result = photoia.run_pipeline()

            self.assertEqual(result, 0)
            process.assert_called_once_with(photo, {})
            self.assertIn("orphan.NEF.xmp", errors.getvalue())
            self.assertIn("se ignora", errors.getvalue())

    def test_missing_sidecar_bootstraps_only_exact_photo_pair(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "fotos para editar"
            input_dir.mkdir()
            photo = input_dir / "selected.NEF"
            photo.touch()
            decoy_sidecar = input_dir / "another.NEF.xmp"
            decoy_sidecar.write_text("unrelated sidecar", encoding="utf-8")
            output_dir = root / "resultados"
            work_dir = root / "work"

            def create_matching_sidecar(_photo, xmp_path, _work_dir, _limits):
                xmp_path.write_text("matching sidecar", encoding="utf-8")

            config = {"paths": {"work_dir": str(work_dir)}}
            with (
                patch.object(photoia, "OUTPUT_DIR", output_dir),
                patch.object(photoia, "bootstrap_xmp", side_effect=create_matching_sidecar) as bootstrap,
                patch.object(photoia, "DarktableCli"),
                patch.object(photoia, "analyze_image", side_effect=RuntimeError("stop after pairing")),
            ):
                success, reason = photoia.process_photo(photo, config)

            expected_sidecar = photo.with_name(f"{photo.name}.xmp")
            bootstrap.assert_called_once_with(
                photo.resolve(),
                expected_sidecar,
                work_dir.resolve(),
                {},
            )
            self.assertFalse(success)
            self.assertIn("stop after pairing", reason)
            self.assertEqual(expected_sidecar.read_text(encoding="utf-8"), "matching sidecar")
            self.assertEqual(decoy_sidecar.read_text(encoding="utf-8"), "unrelated sidecar")

    def test_render_replaces_existing_output_with_fresh_render(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "photo.NEF"
            source.touch()
            output = root / "photo.jpg"
            output.write_bytes(b"stale render")
            cli = DarktableCli.__new__(DarktableCli)
            cli.cli_path = root / "darktable-cli.exe"

            def render_to_temporary_output(command, **_kwargs):
                rendered_path = Path(command[2])
                self.assertNotEqual(rendered_path, output.resolve())
                self.assertEqual(output.read_bytes(), b"stale render")
                rendered_path.write_bytes(b"fresh render")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch(
                "render.darktable_cli.subprocess.run",
                side_effect=render_to_temporary_output,
            ):
                result = cli.render(source, output)

            self.assertEqual(result, output.resolve())
            self.assertEqual(output.read_bytes(), b"fresh render")
            self.assertEqual(list(root.glob(".photoia-render-*")), [])


class JudgeLoopTests(unittest.TestCase):
    """Verifica el loop render -> juez -> re-render en process_photo."""

    BASE_LIMITS = {
        "max_iterations": 3,
        "exposure_ev": [-1.0, 1.0],
        "exposure_black": [-0.05, 0.05],
        "sigmoid_contrast": [0.8, 3.5],
        "sigmoid_skew": [-0.6, 0.6],
        "sigmoid_preserve_hue": [0.0, 100.0],
        "temperature_delta_ratio": [-0.15, 0.15],
    }

    def _make_staged_source(self, root: Path) -> Path:
        input_dir = root / "fotos para editar"
        input_dir.mkdir(parents=True, exist_ok=True)
        photo = input_dir / "loop.NEF"
        photo.write_bytes(b"fake-raw")
        source_xmp = input_dir / "loop.NEF.xmp"
        shutil.copy2(photoia.XMP_TEMPLATE, source_xmp)
        return photo

    def _run_with_judge_sequence(self, judge_results, root: Path):
        photo = self._make_staged_source(root)
        output_dir = root / "resultados"
        work_dir = root / "work"
        config = {
            "paths": {"work_dir": str(work_dir)},
            "limits": dict(self.BASE_LIMITS),
        }

        fixed_plan = {
            "exposure": {"ev": 0.3, "black": 0.0},
            "sigmoid": {"contrast": 2.0, "skew": 0.0},
            "whitebalance": {"warmth_shift": 0.0},
        }

        render_counter = {"n": 0}

        class FakeDarktableCli:
            def __init__(self, *_args, **_kwargs):
                pass

            def render(
                self,
                input_image,
                output_image,
                xmp_path=None,
                width=None,
                hq=True,
                quality=90,
                timeout=120,
            ):
                output_image = Path(output_image)
                output_image.parent.mkdir(parents=True, exist_ok=True)
                if output_image.name.endswith("_editado.jpg"):
                    content = f"render-iter-{render_counter['n']}".encode()
                    render_counter["n"] += 1
                else:
                    content = b"baseline"
                output_image.write_bytes(content)
                return output_image

        with (
            patch.object(photoia, "OUTPUT_DIR", output_dir),
            patch.object(photoia, "analyze_image", return_value={}),
            patch.object(photoia, "plan_edit", return_value=(fixed_plan, [])),
            patch.object(photoia, "DarktableCli", FakeDarktableCli),
            patch.object(photoia, "judge_render", side_effect=judge_results),
        ):
            success, reason = photoia.process_photo(photo, config)

        output_path = output_dir / "loop_editado.jpg"
        return success, reason, output_path

    def test_loop_accepts_directly_without_retrying(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            judge_results = [
                {
                    "accept": True,
                    "score": 88,
                    "issues": [],
                    "adjustments": {
                        "exposure_ev": 0.0,
                        "sigmoid_contrast": 0.0,
                        "sigmoid_skew": 0.0,
                        "warmth_shift": 0.0,
                    },
                },
            ]
            success, reason, output_path = self._run_with_judge_sequence(judge_results, root)

            self.assertTrue(success, reason)
            self.assertEqual(output_path.read_bytes(), b"render-iter-0")

    def test_loop_retries_then_accepts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            judge_results = [
                {
                    "accept": False,
                    "score": 50,
                    "issues": ["Negros aplastados"],
                    "adjustments": {
                        "exposure_ev": 0.1,
                        "sigmoid_contrast": 0.05,
                        "sigmoid_skew": 0.0,
                        "warmth_shift": 0.0,
                    },
                },
                {
                    "accept": True,
                    "score": 90,
                    "issues": [],
                    "adjustments": {
                        "exposure_ev": 0.0,
                        "sigmoid_contrast": 0.0,
                        "sigmoid_skew": 0.0,
                        "warmth_shift": 0.0,
                    },
                },
            ]
            success, reason, output_path = self._run_with_judge_sequence(judge_results, root)

            self.assertTrue(success, reason)
            self.assertEqual(output_path.read_bytes(), b"render-iter-1")

    def test_loop_delivers_best_score_when_never_accepted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            neutral_adjustments = {
                "exposure_ev": 0.0,
                "sigmoid_contrast": 0.0,
                "sigmoid_skew": 0.0,
                "warmth_shift": 0.0,
            }
            judge_results = [
                {"accept": False, "score": 60, "issues": ["a"], "adjustments": dict(neutral_adjustments)},
                {"accept": False, "score": 75, "issues": ["b"], "adjustments": dict(neutral_adjustments)},
                {"accept": False, "score": 65, "issues": ["c"], "adjustments": dict(neutral_adjustments)},
            ]
            success, reason, output_path = self._run_with_judge_sequence(judge_results, root)

            self.assertTrue(success, reason)
            # El loop se detiene tras 3 iteraciones sin aceptar ninguna, pero
            # entrega la de mayor score (iteración 1 = "render-iter-1"), no la
            # última renderizada ("render-iter-2").
            self.assertEqual(output_path.read_bytes(), b"render-iter-1")


if __name__ == "__main__":
    unittest.main()
