#!/usr/bin/env python3
"""PHOTOIA: procesamiento por lote de fotos RAW."""
import argparse
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

import rawpy
from analyze.image_analyzer import analyze_image
from apply.writers.exposure import apply_exposure
from apply.writers.sigmoid import apply_sigmoid
from apply.writers.whitebalance import apply_temperature
from apply.xmp import atomic_write, create_backup, read_xmp, restore_backup
from config import load_config
from plan.planner import plan_edit
from plan.safety import sanitize_plan
from render.darktable_cli import DarktableCli


RAW_EXTENSIONS = {".nef", ".arw", ".cr2", ".dng", ".raf"}
INPUT_DIR = Path("fotos para editar")
OUTPUT_DIR = Path("resultados")
XMP_TEMPLATE = Path(__file__).resolve().parent / "templates" / "base.NEF.xmp"


def bootstrap_xmp(
    image_file: Path,
    xmp_path: Path,
    work_dir: Path,
    limits: Dict[str, Any],
) -> None:
    if not XMP_TEMPLATE.is_file():
        raise FileNotFoundError(f"No se encontró la plantilla XMP: {XMP_TEMPLATE}")

    bootstrap_path = work_dir / "photoia_run" / f"{image_file.name}.bootstrap.xmp"
    bootstrap_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(XMP_TEMPLATE, bootstrap_path)

    try:
        with rawpy.imread(str(image_file)) as raw:
            camera_whitebalance = raw.camera_whitebalance
            if camera_whitebalance is None or len(camera_whitebalance) < 3:
                raise ValueError(
                    "rawpy no proporcionó coeficientes de balance de blancos "
                    "as-shot completos."
                )
            red, green, blue = (
                float(camera_whitebalance[0]),
                float(camera_whitebalance[1]),
                float(camera_whitebalance[2]),
            )

        if not all(math.isfinite(value) and value > 0 for value in (red, green, blue)):
            raise ValueError(
                "rawpy devolvió coeficientes de balance de blancos no válidos."
            )

        wb_updates = {
            "red": red / green,
            "blue": blue / green,
        }
        success, message, _ = apply_temperature(
            bootstrap_path,
            wb_updates,
            simulate=False,
            limits=limits,
        )
        if not success:
            raise RuntimeError(f"No se pudo escribir el balance de blancos: {message}")

        success, message, _ = apply_exposure(
            bootstrap_path,
            {"exposure": 0.0},
            simulate=False,
            limits=limits,
        )
        if not success:
            raise RuntimeError(f"No se pudo fijar exposure a 0.0 EV: {message}")

        atomic_write(xmp_path, read_xmp(bootstrap_path))
        print(
            "  XMP inicializado desde la plantilla: "
            f"WB rojo {wb_updates['red']:.4f}, azul {wb_updates['blue']:.4f}; "
            "exposure 0.0 EV."
        )
    except Exception as error:
        bootstrap_path.unlink(missing_ok=True)
        raise RuntimeError(f"No se pudo generar el XMP inicial: {error}") from error


def process_photo(
    image_path: Path,
    config: Dict[str, Any],
) -> Tuple[bool, str]:
    image_file = image_path.resolve()
    if not image_file.is_file():
        return False, f"No se encontró el archivo: {image_file}"
    if image_file.suffix.lower() not in RAW_EXTENSIONS:
        return False, f"Formato RAW no compatible: {image_file.name}"

    source_xmp = image_file.with_name(f"{image_file.name}.xmp")
    work_dir = Path(config.get("paths", {}).get("work_dir", "./work")).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not source_xmp.is_file():
        try:
            bootstrap_xmp(
                image_file,
                source_xmp,
                work_dir,
                config.get("limits", {}),
            )
        except Exception as error:
            return False, str(error)

    stage_dir = work_dir / "photoia_run"
    stage_dir.mkdir(parents=True, exist_ok=True)
    staged_xmp = stage_dir / f"{image_file.name}.xmp"
    shutil.copy2(source_xmp, staged_xmp)

    analysis_path = work_dir / f"{image_file.stem}_analysis.json"
    plan_path = work_dir / f"{image_file.stem}_plan.json"
    baseline = stage_dir / f"{image_file.name}_baseline.jpg"
    output_path = OUTPUT_DIR / f"{image_file.stem}_editado.jpg"
    darktable = DarktableCli(config.get("paths", {}).get("darktable_cli"))

    try:
        print(f"\nProcesando {image_file.name}...")
        print("  [1/5] Analizando la fotografía...")
        analysis = analyze_image(
            image_file,
            output_path=analysis_path,
            verbose=False,
        )

        print("  [2/5] Renderizando referencia para el plan...")
        darktable.render(
            input_image=image_file,
            output_image=baseline,
            xmp_path=staged_xmp,
            width=2048,
            hq=True,
            quality=92,
        )

        print("  [3/5] Calculando y validando el plan...")
        proposed_plan, planner_notes = plan_edit(baseline, analysis, config)
        plan, safety_notes = sanitize_plan(
            proposed_plan,
            analysis,
            config.get("limits", {}),
        )
        plan["reasoning"] = proposed_plan.get(
            "reasoning",
            "Ajuste fotográfico equilibrado.",
        )
        safety_notes = list(dict.fromkeys([*planner_notes, *safety_notes]))
        plan_path.write_text(
            json.dumps(plan, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        backup = create_backup(staged_xmp)
        limits = config.get("limits", {})
        writers = (
            ("exposure", apply_exposure, plan.get("exposure", {})),
            ("whitebalance", apply_temperature, plan.get("whitebalance", {})),
            ("sigmoid", apply_sigmoid, plan.get("sigmoid", {})),
        )
        applied: Dict[str, Dict[str, Any]] = {}

        print("  [4/5] Aplicando exposure, balance de blancos y sigmoid...")
        for module_name, writer, updates in writers:
            try:
                success, message, values = writer(
                    staged_xmp,
                    updates,
                    simulate=False,
                    limits=limits,
                )
            except Exception as error:
                try:
                    restore_backup(backup, staged_xmp)
                except Exception as rollback_error:
                    raise RuntimeError(
                        f"Falló el módulo {module_name} y no se pudo restaurar "
                        f"el XMP de trabajo: {rollback_error}"
                    ) from error
                raise RuntimeError(
                    f"Falló el módulo {module_name}; se restauró el XMP de trabajo. "
                    f"Detalle: {error}"
                ) from error

            if not success:
                try:
                    restore_backup(backup, staged_xmp)
                except Exception as rollback_error:
                    raise RuntimeError(
                        f"Falló el módulo {module_name} ({message}) y no se pudo "
                        f"restaurar el XMP de trabajo: {rollback_error}"
                    )
                raise RuntimeError(
                    f"Falló el módulo {module_name}; se restauró el XMP de trabajo. "
                    f"Detalle: {message}"
                )

            applied[module_name] = values

        print(f"  [5/5] Renderizando {output_path}...")
        darktable.render(
            input_image=image_file,
            output_image=output_path,
            xmp_path=staged_xmp,
            width=2048,
            hq=True,
            quality=92,
        )

        print("  Ajustes aplicados:")
        print(f"    Exposure: EV {applied['exposure']['exposure']:+.3f}")
        print(
            "    Balance de blancos: "
            f"rojo {applied['whitebalance']['red']:.4f}, "
            f"azul {applied['whitebalance']['blue']:.4f}"
        )
        print(
            "    Sigmoid: "
            f"contraste {applied['sigmoid']['contrast']:.3f}, "
            f"skew {applied['sigmoid']['skew']:+.3f}, "
            f"color_processing {applied['sigmoid']['color_processing']}, "
            f"base_primaries {applied['sigmoid']['base_primaries']}"
        )
        if safety_notes:
            print("  Notas de seguridad:")
            for note in safety_notes:
                print(f"    - {note}")
        print(f"  Imagen generada: {output_path}")
        print(f"  Análisis: {analysis_path}")
        print(f"  Plan: {plan_path}")
        return True, ""
    except Exception as error:
        return False, str(error)


def run_pipeline(image_path: Path | None = None) -> int:
    try:
        config = load_config()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        if image_path is not None:
            photos = [Path(image_path)]
        else:
            INPUT_DIR.mkdir(parents=True, exist_ok=True)
            photos = sorted(
                (
                    path
                    for path in INPUT_DIR.iterdir()
                    if path.is_file() and path.suffix.lower() in RAW_EXTENSIONS
                ),
                key=lambda path: path.name.casefold(),
            )
            if not photos:
                print(
                    f"No hay archivos RAW compatibles en '{INPUT_DIR}'. "
                    "Añade fotos .NEF, .ARW, .CR2, .DNG o .RAF con su XMP."
                )
                return 1
    except Exception as error:
        print(f"ERROR al preparar el lote: {error}", file=sys.stderr)
        return 1

    failures = []
    processed = 0
    seen_stems = set()
    for photo in photos:
        stem_key = photo.stem.casefold()
        if stem_key in seen_stems:
            failures.append(
                (photo.name, "Hay otra foto con el mismo nombre base; se evita pisar salidas.")
            )
            print(f"\nAVISO: {photo.name}: {failures[-1][1]}")
            continue
        seen_stems.add(stem_key)

        try:
            success, reason = process_photo(photo, config)
        except Exception as error:
            success, reason = False, str(error)
        if success:
            processed += 1
        else:
            failures.append((photo.name, reason))
            print(f"\nFALLO: {photo.name}: {reason}", file=sys.stderr)

    print("\nResumen del lote")
    print(f"  Fotos procesadas correctamente: {processed} de {len(photos)}")
    print(f"  Fotos fallidas: {len(failures)}")
    if failures:
        for name, reason in failures:
            print(f"    - {name}: {reason}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PHOTOIA: procesamiento individual o por lote de fotos RAW."
    )
    parser.add_argument(
        "image",
        nargs="?",
        help=(
            "Ruta de una foto RAW; si se omite, procesa todos los RAW "
            "de 'fotos para editar/'."
        ),
    )
    args = parser.parse_args()
    return run_pipeline(Path(args.image) if args.image else None)


if __name__ == "__main__":
    sys.exit(main())
