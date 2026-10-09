import io
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


if __name__ == "__main__":
    unittest.main()
