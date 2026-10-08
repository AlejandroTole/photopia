#!/usr/bin/env python3
"""
Resolve whether sigmoid enum slots 4 and 13 are stored as int32 or float32.

Renders a baseline and two variants per slot through darktable-cli, without
modifying the source XMP. Variant A stores int32=1; variant B stores float32=1.
"""
import struct
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageChops

from apply.xmp import (
    find_operation_modules,
    read_xmp,
    replace_module_params,
    select_target_module,
)
from render.darktable_cli import DarktableCli

NEF = Path("_DSC2125.NEF")
XMP = Path("_DSC2125.NEF.xmp")
WORK = Path("work") / "sigmoid_p0"
SIGMOID_LEN = 56
SLOTS = {4: "color_processing", 13: "base_primaries"}
DIFF_CHANGE = 2.0
DIFF_SAME = 0.5


def mean_abs_diff(p1: Path, p2: Path) -> float:
    with Image.open(p1) as image_a, Image.open(p2) as image_b:
        a = image_a.convert("RGB")
        b = image_b.convert("RGB")
    if a.size != b.size:
        a = a.resize(b.size)
    diff = ImageChops.difference(a, b)
    hist = diff.histogram()
    total = sum(
        value * count
        for channel in range(3)
        for value, count in enumerate(hist[channel * 256:(channel + 1) * 256])
    )
    return total / (a.size[0] * a.size[1] * 3)


def build_variant(content: str, target: dict, slot: int, fmt: str, value: int | float) -> str:
    raw = bytearray(bytes.fromhex(target["params"]))
    raw[slot * 4:slot * 4 + 4] = struct.pack(fmt, value)
    return replace_module_params(content, target, bytes(raw).hex())


def classify_slot(diff_int: float | None, diff_float: float | None) -> str:
    if diff_int is not None and diff_float is not None:
        if diff_int > DIFF_CHANGE and diff_float < DIFF_SAME:
            return "int32"
        if diff_float > DIFF_CHANGE and diff_int < DIFF_SAME:
            return "float32"
    return "inconcluso"


def main() -> int:
    for path in (NEF, XMP):
        if not path.exists():
            print(f"ERROR: no se encontro {path} en esta carpeta.")
            return 1

    WORK.mkdir(parents=True, exist_ok=True)
    working_nef = WORK / NEF.name
    shutil.copy2(NEF, working_nef)

    content = read_xmp(XMP)
    modules = find_operation_modules(content, "sigmoid")
    target = select_target_module(modules)
    raw = bytes.fromhex(target["params"])
    if len(raw) != SIGMOID_LEN:
        print(f"ERROR: params sigmoid de {len(raw)} bytes, se esperaban {SIGMOID_LEN}.")
        return 1
    print(f"sigmoid darktable:num={target['num']} enabled={target['enabled']}")
    if target["enabled"] == 0:
        print("ERROR: el modulo sigmoid mas reciente esta deshabilitado; el resultado no seria concluyente.")
        return 2

    for slot, name in SLOTS.items():
        word = raw[slot * 4:slot * 4 + 4]
        print(
            f"slot {slot} ({name}) actual: bytes={word.hex()} "
            f"int32={struct.unpack('<i', word)[0]} "
            f"float32={struct.unpack('<f', word)[0]:.9g}"
        )

    reference_contents = {
        4: content,
        13: build_variant(content, target, 4, "<i", 1),
    }
    reference_paths = {}
    for slot, reference_content in reference_contents.items():
        reference_path = WORK / f"p0_baseline_slot{slot}.xmp"
        reference_path.write_text(reference_content, encoding="utf-8")
        reference_paths[slot] = reference_path

    variants = {}
    for slot in SLOTS:
        for variant, fmt, value in (("int", "<i", 1), ("float", "<f", 1.0)):
            name = f"slot{slot}_{variant}"
            variant_path = WORK / f"p0_{name}.xmp"
            variant_path.write_text(
                build_variant(reference_contents[slot], target, slot, fmt, value),
                encoding="utf-8",
            )
            variants[name] = variant_path

    cli = DarktableCli()
    render_paths = {
        f"baseline_slot{slot}": WORK / f"p0_render_baseline_slot{slot}.jpg"
        for slot in SLOTS
    }
    render_paths.update({
        name: WORK / f"p0_render_{name}.jpg"
        for name in variants
    })
    try:
        references = [
            (f"baseline_slot{slot}", xmp_path)
            for slot, xmp_path in reference_paths.items()
        ]
        for name, xmp_path in [*references, *variants.items()]:
            print(f"Renderizando {name}...")
            cli.render(working_nef, render_paths[name], xmp_path=xmp_path, width=1024, timeout=300)
            print(f"  OK: {render_paths[name]}")
    except Exception as error:
        print(f"ERROR: fallo el render de {name}: {error}")
        return 1

    verdicts = {}
    for slot, field in SLOTS.items():
        baseline = render_paths[f"baseline_slot{slot}"]
        int_diff = mean_abs_diff(baseline, render_paths[f"slot{slot}_int"])
        float_diff = mean_abs_diff(baseline, render_paths[f"slot{slot}_float"])
        verdict = classify_slot(int_diff, float_diff)
        verdicts[slot] = verdict
        print(
            f"slot {slot} ({field}; RGB ratio activo si aplica): "
            f"diff(int32=1)={int_diff:.3f}, "
            f"diff(float32=1.0)={float_diff:.3f} -> {verdict}"
        )

    if all(verdict == "int32" for verdict in verdicts.values()):
        print("VEREDICTO: ambos slots son int32.")
        return 0
    if all(verdict == "float32" for verdict in verdicts.values()):
        print("VEREDICTO: ambos slots son float32.")
        return 0
    if len(set(verdicts.values())) == 1:
        print(f"RESULTADO: ambos slots quedaron {next(iter(verdicts.values()))}.")
    else:
        print(f"RESULTADO MIXTO/INCONCLUSO: {verdicts}")
    print(
        "Un slot es concluyente solo si una codificacion cambia el render "
        f"(diff>{DIFF_CHANGE}) y la otra coincide con baseline (diff<{DIFF_SAME})."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
