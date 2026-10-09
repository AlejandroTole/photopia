"""
PHOTOIA - Darktable CLI Headless Wrapper
Renders RAW files to JPEG via darktable-cli without GUI interaction.
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
from typing import Optional


STANDARD_WINDOWS_PATHS = [
    Path(r"C:\Program Files\darktable\bin\darktable-cli.exe"),
    Path(r"C:\Program Files (x86)\darktable\bin\darktable-cli.exe"),
]


def find_darktable_cli(configured_path: Optional[str] = None) -> Path:
    """
    Locates darktable-cli binary from configuration, PATH, or standard locations.
    """
    if configured_path:
        p = Path(configured_path)
        if p.is_file():
            return p

    which_dt = shutil.which("darktable-cli")
    if which_dt:
        return Path(which_dt)

    for p in STANDARD_WINDOWS_PATHS:
        if p.is_file():
            return p

    raise FileNotFoundError(
        "No se encontró darktable-cli. Verifica la instalación de Darktable "
        "o especifica la ruta en config.yaml."
    )


def check_available() -> str:
    """
    Verifies that darktable-cli exists and returns its version string.
    Raises RuntimeError or FileNotFoundError if not found or execution fails.
    """
    cli_path = find_darktable_cli()
    try:
        result = subprocess.run(
            [cli_path.resolve().as_posix(), "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"darktable-cli falló al obtener la versión (código {result.returncode}).\n"
                f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            )
        version_output = result.stdout.strip() or result.stderr.strip()
        return version_output
    except Exception as e:
        if isinstance(e, (FileNotFoundError, RuntimeError)):
            raise
        raise RuntimeError(f"No se pudo ejecutar darktable-cli en {cli_path}: {e}")


class DarktableCli:
    def __init__(self, cli_path: Optional[str] = None):
        self.cli_path = find_darktable_cli(cli_path)

    def render(
        self,
        input_image: Path,
        output_image: Path,
        xmp_path: Optional[Path] = None,
        width: Optional[int] = None,
        height: int = 0,
        hq: bool = True,
        quality: int = 90,
        timeout: int = 120,
    ) -> Path:
        """
        Renders an image via darktable-cli headless.
        """
        input_path = Path(input_image).resolve()
        output_path = Path(output_image).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not input_path.exists():
            raise FileNotFoundError(f"Archivo de entrada no encontrado: {input_path}")

        with tempfile.TemporaryDirectory(
            prefix=".photoia-render-",
            dir=output_path.parent,
        ) as temp_dir:
            rendered_path = Path(temp_dir) / output_path.name
            cmd = [self.cli_path.resolve().as_posix(), input_path.as_posix()]

            if xmp_path is not None:
                resolved_xmp = Path(xmp_path).resolve()
                if not resolved_xmp.exists():
                    raise FileNotFoundError(f"Sidecar XMP no encontrado: {resolved_xmp}")
                cmd.append(resolved_xmp.as_posix())

            cmd.append(rendered_path.as_posix())

            if width is not None and width > 0:
                cmd.extend(["--width", str(width)])
            if height > 0:
                cmd.extend(["--height", str(height)])

            cmd.extend(["--hq", "true" if hq else "false"])
            cmd.extend(["--apply-custom-presets", "false"])
            cmd.extend(["--core", "--conf", f"plugins/imageio/format/jpeg/quality={quality}"])

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"darktable-cli falló con código {result.returncode}.\n"
                    f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
                )

            if not rendered_path.exists() or rendered_path.stat().st_size == 0:
                raise RuntimeError(
                    "darktable-cli finalizó pero el archivo de salida no fue creado: "
                    f"{rendered_path}"
                )

            os.replace(rendered_path, output_path)

        return output_path


def render(
    nef_path,
    xmp_path_or_None=None,
    output_path=None,
    width=None,
):
    """
    Runs darktable-cli headless; if width is given, exports downscaled for previews.
    """
    cli = DarktableCli()
    return cli.render(
        input_image=Path(nef_path),
        output_image=Path(output_path),
        xmp_path=Path(xmp_path_or_None) if xmp_path_or_None is not None else None,
        width=width,
        height=0,
        hq=True,
        quality=90,
    )


if __name__ == "__main__":
    print("=" * 60)
    print("PHOTOIA - DARKTABLE CLI SMOKE TEST")
    print("=" * 60)
    try:
        version = check_available()
        print(f"OK: darktable-cli disponible.")
        print(f"Versión:\n{version}")

        nef_file = Path("_DSC2125.NEF")
        if not nef_file.exists():
            print(f"ERROR: No se encontró la imagen RAW de prueba: {nef_file}")
            raise SystemExit(1)

        work_dir = Path("work")
        work_dir.mkdir(parents=True, exist_ok=True)
        baseline_out = work_dir / "baseline_test.jpg"

        print(f"Renderizando baseline (sin XMP) a {baseline_out}...")
        render(
            nef_path=nef_file,
            xmp_path_or_None=None,
            output_path=baseline_out,
            width=1024,
        )
        print(f"OK: Renderizado exitoso: {baseline_out.resolve()}")
    except Exception as e:
        print("\n" + "=" * 60)
        print("ERROR EN DARKTABLE-CLI:")
        print(str(e))
        print("=" * 60)
        print("\nSi darktable-cli no está instalado en este equipo, por favor instálelo antes de continuar.")
        raise SystemExit(1)
