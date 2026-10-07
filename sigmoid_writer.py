import argparse
import datetime
import json
import math
import os
import re
import shutil
import struct
import sys


XMP_FILE = "_DSC2125.NEF.xmp"
PLAN_FILE = "edit_plan.json"


COLOR_PROCESSING = {
    "per channel": 0,
    "RGB ratio": 1,
}

BASE_PRIMARIES = {
    "working profile": 0,
    "Rec2020": 1,
    "Display P3": 2,
    "Adobe RGB (compatible)": 3,
    "sRGB": 4,
}


# ============================================================
# CONVERSIONES
# ============================================================

def percent_to_internal(value):
    return float(value) / 100.0


def degrees_to_radians(value):
    return math.radians(float(value))


def to_float32(value):
    return struct.unpack(
        "<f",
        struct.pack("<f", float(value))
    )[0]


# ============================================================
# CARGAR PLAN
# ============================================================

def load_plan(path):

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            plan = json.load(f)

    except FileNotFoundError:

        raise RuntimeError(
            f"No existe el plan: {path}"
        )

    except json.JSONDecodeError as error:

        raise RuntimeError(
            f"JSON inválido en {path}: {error}"
        )

    if plan.get("version") != 1:

        raise RuntimeError(
            "version del plan debe ser 1."
        )

    target = plan.get("target")

    if not isinstance(target, dict):

        raise RuntimeError(
            "Falta el bloque target."
        )

    if target.get("operation") != "sigmoid":

        raise RuntimeError(
            "target.operation debe ser 'sigmoid'."
        )

    sigmoid = plan.get("sigmoid")

    if not isinstance(sigmoid, dict):

        raise RuntimeError(
            "Falta el bloque sigmoid."
        )

    required = [
        "contrast",
        "skew",
        "target_white",
        "target_black",
        "color_processing",
        "preserve_hue",
        "red_attenuation",
        "red_rotation",
        "green_attenuation",
        "green_rotation",
        "blue_attenuation",
        "blue_rotation",
        "recover_purity",
        "base_primaries",
    ]

    missing = [
        field
        for field in required
        if field not in sigmoid
    ]

    if missing:

        raise RuntimeError(
            "Faltan campos en sigmoid: "
            + ", ".join(missing)
        )

    return plan


# ============================================================
# CONSTRUIR 14 PARAMETROS
# ============================================================

def build_params(plan):

    s = plan["sigmoid"]

    # --------------------------------------------------------
    # VALIDACIONES
    # --------------------------------------------------------

    ranges = {
        "contrast": (0.0, 10.0),
        "skew": (-1.0, 1.0),
        "target_white": (0.0, 100.0),
        "target_black": (0.0, 100.0),
        "preserve_hue": (0.0, 100.0),
        "red_attenuation": (0.0, 100.0),
        "green_attenuation": (0.0, 100.0),
        "blue_attenuation": (0.0, 100.0),
        "recover_purity": (0.0, 100.0),
        "red_rotation": (-360.0, 360.0),
        "green_rotation": (-360.0, 360.0),
        "blue_rotation": (-360.0, 360.0),
    }

    for name, (minimum, maximum) in ranges.items():

        try:
            value = float(s[name])
        except (TypeError, ValueError):
            raise RuntimeError(
                f"{name} debe ser numérico."
            )

        if not minimum <= value <= maximum:

            raise RuntimeError(
                f"{name}={value} fuera de rango "
                f"({minimum} - {maximum})."
            )

    color_name = s["color_processing"]

    if color_name not in COLOR_PROCESSING:

        raise RuntimeError(
            f"color_processing inválido: {color_name}"
        )

    base_name = s["base_primaries"]

    if base_name not in BASE_PRIMARIES:

        raise RuntimeError(
            f"base_primaries inválido: {base_name}"
        )

    # --------------------------------------------------------
    # PARAMETROS
    # --------------------------------------------------------

    values = [

        # [0]
        float(s["contrast"]),

        # [1]
        float(s["skew"]),

        # [2]
        float(s["target_white"]),

        # [3]
        float(s["target_black"]),

        # [4]
        float(COLOR_PROCESSING[color_name]),

        # [5]
        float(s["preserve_hue"]),

        # [6]
        percent_to_internal(
            s["red_attenuation"]
        ),

        # [7]
        degrees_to_radians(
            s["red_rotation"]
        ),

        # [8]
        percent_to_internal(
            s["green_attenuation"]
        ),

        # [9]
        degrees_to_radians(
            s["green_rotation"]
        ),

        # [10]
        percent_to_internal(
            s["blue_attenuation"]
        ),

        # [11]
        degrees_to_radians(
            s["blue_rotation"]
        ),

        # [12]
        percent_to_internal(
            s["recover_purity"]
        ),

        # [13]
        float(BASE_PRIMARIES[base_name]),
    ]

    return [
        to_float32(value)
        for value in values
    ]


# ============================================================
# PARAMETROS -> HEX
# ============================================================

def params_to_hex(values):

    raw = struct.pack(
        "<14f",
        *values
    )

    if len(raw) != 56:

        raise RuntimeError(
            "darktable:params debe tener 56 bytes."
        )

    return raw.hex()


# ============================================================
# ENCONTRAR SIGMOIDS
# ============================================================

def find_sigmoids(xmp):

    pattern = re.compile(
        r'<rdf:li\b'
        r'(?P<attrs>[^>]*)'
        r'darktable:operation="sigmoid"'
        r'(?P<attrs2>[^>]*)'
        r'darktable:params="(?P<params>[0-9a-fA-F]+)"'
        r'[^>]*>',
        re.S,
    )

    results = []

    for match in pattern.finditer(xmp):

        attrs = (
            match.group("attrs")
            + match.group("attrs2")
        )

        num_match = re.search(
            r'darktable:num="(\d+)"',
            attrs
        )

        enabled_match = re.search(
            r'darktable:enabled="(\d+)"',
            attrs
        )

        num = (
            int(num_match.group(1))
            if num_match
            else -1
        )

        enabled = (
            int(enabled_match.group(1))
            if enabled_match
            else None
        )

        results.append({
            "num": num,
            "enabled": enabled,
            "params": match.group("params"),
            "match": match,
        })

    return results


# ============================================================
# SELECCIONAR SIGMOID
# ============================================================

def select_target(sigmoids, requested_num):

    if requested_num is None:

        sigmoids.sort(
            key=lambda item: item["num"]
        )

        return sigmoids[-1]

    matches = [
        item
        for item in sigmoids
        if item["num"] == requested_num
    ]

    if len(matches) != 1:

        raise RuntimeError(
            f"No se encontró exactamente un "
            f"Sigmoid con darktable:num="
            f"{requested_num}."
        )

    return matches[0]


# ============================================================
# REEMPLAZAR SOLO PARAMS
# ============================================================

def replace_params(
    xmp,
    target,
    new_hex
):

    match = target["match"]

    start = match.start("params")
    end = match.end("params")

    return (
        xmp[:start]
        + new_hex
        + xmp[end:]
    )


# ============================================================
# LEER PARAMETROS
# ============================================================

def read_sigmoid(
    xmp,
    num
):

    sigmoids = find_sigmoids(xmp)

    if not sigmoids:

        raise RuntimeError(
            "No se encontraron Sigmoid."
        )

    target = select_target(
        sigmoids,
        num
    )

    raw = bytes.fromhex(
        target["params"]
    )

    if len(raw) != 56:

        raise RuntimeError(
            "El Sigmoid no contiene 56 bytes."
        )

    values = struct.unpack(
        "<14f",
        raw
    )

    return target, values


# ============================================================
# VERIFICAR
# ============================================================

def verify_values(
    actual,
    expected
):

    for index in range(14):

        difference = abs(
            actual[index]
            - expected[index]
        )

        if difference > 0.00001:

            return (
                False,
                f"Índice {index}, "
                f"diferencia={difference}"
            )

    return True, "OK"


# ============================================================
# BACKUP
# ============================================================

def create_backup(path):

    timestamp = datetime.datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup = (
        f"{path}.backup.{timestamp}"
    )

    shutil.copy2(
        path,
        backup
    )

    return backup


# ============================================================
# ESCRITURA ATOMICA
# ============================================================

def atomic_write(
    path,
    content
):

    temp_path = path + ".photoia_tmp"

    with open(
        temp_path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(content)
        f.flush()
        os.fsync(
            f.fileno()
        )

    os.replace(
        temp_path,
        path
    )


# ============================================================
# MOSTRAR RESUMEN
# ============================================================

def print_summary(values):

    names = [
        "Contrast",
        "Skew",
        "Target white",
        "Target black",
        "Color processing",
        "Preserve hue",
        "Red attenuation",
        "Red rotation",
        "Green attenuation",
        "Green rotation",
        "Blue attenuation",
        "Blue rotation",
        "Recover purity",
        "Base primaries",
    ]

    print()

    for name, value in zip(
        names,
        values
    ):

        print(
            f"{name:<20} {value:.12f}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "PHOTOIA - aplica edit_plan.json "
            "al Sigmoid de Darktable"
        )
    )

    parser.add_argument(
        "--plan",
        default=PLAN_FILE,
        help="Archivo JSON del plan.",
    )

    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "Escribe el XMP real. "
            "Sin esta bandera solo simula."
        ),
    )

    args = parser.parse_args()

    print()
    print("=" * 78)
    print("PHOTOIA - SIGMOID PLAN WRITER")
    print("=" * 78)

    # --------------------------------------------------------
    # XMP
    # --------------------------------------------------------

    if not os.path.exists(XMP_FILE):

        print()
        print(
            f"ERROR: No existe {XMP_FILE}"
        )

        return 1

    # --------------------------------------------------------
    # PLAN
    # --------------------------------------------------------

    try:

        plan = load_plan(
            args.plan
        )

        expected_values = build_params(
            plan
        )

    except RuntimeError as error:

        print()
        print(
            f"ERROR: {error}"
        )

        return 1

    requested_num = (
        plan["target"].get(
            "darktable_num"
        )
    )

    # --------------------------------------------------------
    # LEER XMP
    # --------------------------------------------------------

    with open(
        XMP_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        original_xmp = f.read()

    # --------------------------------------------------------
    # ENCONTRAR OBJETIVO
    # --------------------------------------------------------

    try:

        target, current_values = read_sigmoid(
            original_xmp,
            requested_num
        )

    except RuntimeError as error:

        print()
        print(
            f"ERROR: {error}"
        )

        return 1

    print()
    print(
        f"Sigmoid objetivo: "
        f"darktable:num={target['num']}"
    )

    print(
        f"enabled: {target['enabled']}"
    )

    # --------------------------------------------------------
    # NUEVOS PARAMETROS
    # --------------------------------------------------------

    print()
    print("PARAMETROS PROPUESTOS")
    print("-" * 78)

    print_summary(
        expected_values
    )

    new_hex = params_to_hex(
        expected_values
    )

    print()
    print("HEX ACTUAL")
    print("-" * 78)
    print(
        target["params"]
    )

    print()
    print("HEX PROPUESTO")
    print("-" * 78)
    print(
        new_hex
    )

    # --------------------------------------------------------
    # PROPUESTA EN MEMORIA
    # --------------------------------------------------------

    proposed_xmp = replace_params(
        original_xmp,
        target,
        new_hex
    )

    if len(proposed_xmp) != len(original_xmp):

        print()
        print(
            "ERROR CRITICO: cambió el tamaño "
            "del XMP."
        )

        return 1

    # --------------------------------------------------------
    # VALIDACION PREVIA
    # --------------------------------------------------------

    proposed_target, proposed_values = (
        read_sigmoid(
            proposed_xmp,
            target["num"]
        )
    )

    ok, message = verify_values(
        proposed_values,
        expected_values
    )

    if not ok:

        print()
        print(
            "ERROR: falló la verificación previa."
        )

        print(
            message
        )

        return 1

    print()
    print(
        "Verificación previa: OK"
    )

    # --------------------------------------------------------
    # SIMULACION
    # --------------------------------------------------------

    if not args.write:

        print()
        print("=" * 78)
        print("MODO SIMULACION")
        print("=" * 78)

        print()
        print(
            "El XMP REAL NO fue modificado."
        )

        print()

        return 0

    # --------------------------------------------------------
    # ESCRITURA
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("MODO ESCRITURA REAL")
    print("=" * 78)

    backup = create_backup(
        XMP_FILE
    )

    print()
    print(
        f"Backup: {backup}"
    )

    try:

        atomic_write(
            XMP_FILE,
            proposed_xmp
        )

        # ----------------------------------------------------
        # RELEER DESDE DISCO
        # ----------------------------------------------------

        with open(
            XMP_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            written_xmp = f.read()

        written_target, written_values = (
            read_sigmoid(
                written_xmp,
                target["num"]
            )
        )

        # ----------------------------------------------------
        # VERIFICAR VALORES
        # ----------------------------------------------------

        ok, message = verify_values(
            written_values,
            expected_values
        )

        if not ok:

            raise RuntimeError(
                "La verificación final falló: "
                + message
            )

        # ----------------------------------------------------
        # VERIFICAR NUM
        # ----------------------------------------------------

        if (
            written_target["num"]
            != target["num"]
        ):

            raise RuntimeError(
                "darktable:num cambió."
            )

        # ----------------------------------------------------
        # VERIFICAR OTROS SIGMOIDS
        # ----------------------------------------------------

        old_sigmoids = find_sigmoids(
            original_xmp
        )

        new_sigmoids = find_sigmoids(
            written_xmp
        )

        if len(old_sigmoids) != len(new_sigmoids):

            raise RuntimeError(
                "Cambió el número de módulos Sigmoid."
            )

        old_sigmoids.sort(
            key=lambda item: item["num"]
        )

        new_sigmoids.sort(
            key=lambda item: item["num"]
        )

        for old, new in zip(
            old_sigmoids,
            new_sigmoids
        ):

            if old["num"] != new["num"]:

                raise RuntimeError(
                    "Cambió un darktable:num."
                )

            if old["num"] == target["num"]:

                continue

            if (
                old["params"].lower()
                != new["params"].lower()
            ):

                raise RuntimeError(
                    f"El Sigmoid num={old['num']} "
                    "también cambió."
                )

        print()
        print("=" * 78)
        print("ESCRITURA COMPLETADA")
        print("=" * 78)

        print()
        print(
            "Verificación final: OK"
        )

        print(
            f"Solo cambió darktable:params "
            f"del Sigmoid num={target['num']}."
        )

        print()
        print(
            f"Backup: {backup}"
        )

        print()

        return 0

    except Exception as error:

        print()
        print("=" * 78)
        print("ERROR DURANTE LA ESCRITURA")
        print("=" * 78)

        print()
        print(error)

        print()
        print(
            "Restaurando backup..."
        )

        try:

            shutil.copy2(
                backup,
                XMP_FILE
            )

            print(
                "Rollback completado."
            )

        except Exception as rollback_error:

            print()
            print(
                "ERROR CRITICO DURANTE ROLLBACK:"
            )

            print(
                rollback_error
            )

            return 2

        print()

        return 1


if __name__ == "__main__":
    sys.exit(main())