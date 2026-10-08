#!/usr/bin/env python3
"""PHOTOIA one-pass RAW editing pipeline."""
import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

from analyze.image_analyzer import analyze_image
from apply.writers.exposure import apply_exposure
from apply.writers.sigmoid import apply_sigmoid
from apply.writers.whitebalance import apply_temperature
from apply.xmp import create_backup, restore_backup
from config import load_config
from plan.planner import plan_edit
from plan.safety import sanitize_plan
from render.darktable_cli import DarktableCli


def run_pipeline(image_path: Path = Path("_DSC2125.NEF")) -> int:
    stage = "configuración"
    try:
        config = load_config()
        image_file = Path(image_path).resolve()
        if not image_file.is_file():
            raise FileNotFoundError(f"No se encontró el NEF: {image_file}")

        source_xmp = image_file.with_name(f"{image_file.name}.xmp")
        if not source_xmp.is_file():
            raise FileNotFoundError(f"No se encontró el sidecar XMP: {source_xmp}")

        work_dir = Path(config.get("paths", {}).get("work_dir", "./work")).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)

        # Darktable may rewrite a sidecar while rendering, so it only sees these copies.
        stage_dir = work_dir / "photoia_run"
        stage_dir.mkdir(parents=True, exist_ok=True)
        staged_nef = stage_dir / image_file.name
        staged_xmp = stage_dir / f"{image_file.name}.xmp"
        shutil.copy2(image_file, staged_nef)
        shutil.copy2(source_xmp, staged_xmp)

        darktable = DarktableCli(config.get("paths", {}).get("darktable_cli"))

        stage = "análisis de la fotografía"
        print(f"[1/5] Analizando {image_file.name}...")
        analysis_path = work_dir / "analysis.json"
        analysis = analyze_image(image_file, output_path=analysis_path, verbose=False)

        stage = "render de referencia"
        baseline = stage_dir / "baseline.jpg"
        print("[2/5] Renderizando referencia para el plan...")
        darktable.render(
            input_image=staged_nef,
            output_image=baseline,
            xmp_path=staged_xmp,
            width=2048,
            hq=True,
            quality=92,
        )

        stage = "planificación y seguridad"
        print("[3/5] Calculando y validando el plan...")
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

        plan_path = work_dir / "plan.json"
        plan_path.write_text(
            json.dumps(plan, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        stage = "aplicación de ajustes"
        xmp_backup = create_backup(staged_xmp)
        limits = config.get("limits", {})
        writers = (
            (
                "exposure",
                apply_exposure,
                plan.get("exposure", {}),
            ),
            (
                "whitebalance",
                apply_temperature,
                plan.get("whitebalance", {}),
            ),
            (
                "sigmoid",
                apply_sigmoid,
                plan.get("sigmoid", {}),
            ),
        )
        applied: Dict[str, Dict[str, Any]] = {}

        print("[4/5] Aplicando exposure, balance de blancos y sigmoid...")
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
                    restore_backup(xmp_backup, staged_xmp)
                except Exception as rollback_error:
                    raise RuntimeError(
                        f"Falló el writer {module_name} y no se pudo restaurar "
                        f"el XMP de trabajo: {rollback_error}"
                    ) from error
                raise RuntimeError(
                    f"Falló el writer {module_name}; se restauró el XMP de trabajo. "
                    f"Detalle: {error}"
                ) from error

            if not success:
                try:
                    restore_backup(xmp_backup, staged_xmp)
                except Exception as rollback_error:
                    raise RuntimeError(
                        f"El writer {module_name} falló ({message}) y no se pudo "
                        f"restaurar el XMP de trabajo: {rollback_error}"
                    )
                raise RuntimeError(
                    f"El writer {module_name} falló; se restauró el XMP de trabajo. "
                    f"Detalle: {message}"
                )

            applied[module_name] = values

        stage = "render final"
        output_path = work_dir / "output.jpg"
        print("[5/5] Renderizando work/output.jpg...")
        darktable.render(
            input_image=staged_nef,
            output_image=output_path,
            xmp_path=staged_xmp,
            width=2048,
            hq=True,
            quality=92,
        )

        print("\nResumen de ajustes")
        print(f"  Exposure: EV {applied['exposure']['exposure']:+.3f}")
        print(
            "  Balance de blancos: "
            f"rojo {applied['whitebalance']['red']:.4f}, "
            f"azul {applied['whitebalance']['blue']:.4f}"
        )
        print(
            "  Sigmoid: "
            f"contraste {applied['sigmoid']['contrast']:.3f}, "
            f"skew {applied['sigmoid']['skew']:+.3f}, "
            f"color_processing {applied['sigmoid']['color_processing']}, "
            f"base_primaries {applied['sigmoid']['base_primaries']}"
        )
        if safety_notes:
            print("  Notas de seguridad:")
            for note in safety_notes:
                print(f"    - {note}")
        print(f"  Archivo generado: {output_path}")
        print(f"  Plan: {plan_path}")
        return 0

    except Exception as error:
        print(f"ERROR durante {stage}: {error}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PHOTOIA: análisis y edición RAW en una sola pasada."
    )
    parser.add_argument(
        "image",
        nargs="?",
        default="_DSC2125.NEF",
        help="Ruta del NEF de entrada (por defecto: _DSC2125.NEF).",
    )
    args = parser.parse_args()
    return run_pipeline(Path(args.image))


if __name__ == "__main__":
    sys.exit(main())
