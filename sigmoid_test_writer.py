import os
import re
import struct
import math


# ============================================================
# PHOTOIA - SIGMOID TEST WRITER
#
# PROPOSITO:
#   1. Leer el XMP original.
#   2. Generar un nuevo darktable:params.
#   3. Crear una COPIA de prueba del XMP.
#   4. Modificar SOLO los params del ultimo Sigmoid.
#
# NUNCA modifica el XMP original.
# ============================================================


SOURCE_XMP = "_DSC2125.NEF.xmp"
TEST_XMP = "_DSC2125.TEST.NEF.xmp"


# ============================================================
# PARAMETROS QUE QUEREMOS ESCRIBIR
# ============================================================

TEST_VALUES = {
    "contrast": 3.0,
    "skew": -0.33,

    "target_white": 71.61,
    "target_black": 0.2677,

    "color_processing": 0,

    "preserve_hue": 70.53,

    "red_attenuation": 10.4,
    "red_rotation": 11.8,

    "green_attenuation": 10.2,
    "green_rotation": 10.0,

    "blue_attenuation": 10.2,
    "blue_rotation": 19.5,

    "recover_purity": 36.0,

    "base_primaries": 0,
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
        struct.pack(
            "<f",
            float(value)
        )
    )[0]


# ============================================================
# CONSTRUIR LOS 14 FLOAT32
# ============================================================

def build_params():

    values = [

        # [0]
        TEST_VALUES["contrast"],

        # [1]
        TEST_VALUES["skew"],

        # [2]
        TEST_VALUES["target_white"],

        # [3]
        TEST_VALUES["target_black"],

        # [4]
        TEST_VALUES["color_processing"],

        # [5]
        TEST_VALUES["preserve_hue"],

        # [6]
        percent_to_internal(
            TEST_VALUES["red_attenuation"]
        ),

        # [7]
        degrees_to_radians(
            TEST_VALUES["red_rotation"]
        ),

        # [8]
        percent_to_internal(
            TEST_VALUES["green_attenuation"]
        ),

        # [9]
        degrees_to_radians(
            TEST_VALUES["green_rotation"]
        ),

        # [10]
        percent_to_internal(
            TEST_VALUES["blue_attenuation"]
        ),

        # [11]
        degrees_to_radians(
            TEST_VALUES["blue_rotation"]
        ),

        # [12]
        percent_to_internal(
            TEST_VALUES["recover_purity"]
        ),

        # [13]
        TEST_VALUES["base_primaries"],
    ]

    return [
        to_float32(value)
        for value in values
    ]


# ============================================================
# FLOAT32 -> HEX
# ============================================================

def params_to_hex(values):

    raw = struct.pack(
        "<14f",
        *values
    )

    if len(raw) != 56:
        raise ValueError(
            "El Sigmoid debe ocupar exactamente 56 bytes."
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
        r'(?P<rest>[^>]*)>',
        re.S,
    )

    matches = []

    for match in pattern.finditer(xmp):

        attrs = (
            match.group("attrs")
            + match.group("attrs2")
        )

        num_match = re.search(
            r'darktable:num="(\d+)"',
            attrs
        )

        num = (
            int(num_match.group(1))
            if num_match
            else -1
        )

        matches.append(
            {
                "match": match,
                "num": num,
                "params": match.group("params"),
            }
        )

    return matches


# ============================================================
# REEMPLAZAR SOLO PARAMS
# ============================================================

def replace_latest_sigmoid_params(
    xmp,
    new_hex
):

    sigmoids = find_sigmoids(xmp)

    if not sigmoids:

        raise RuntimeError(
            "No se encontraron módulos Sigmoid."
        )

    sigmoids.sort(
        key=lambda item: item["num"]
    )

    latest = sigmoids[-1]

    match = latest["match"]

    old_params = latest["params"]

    old_start = match.start("params")
    old_end = match.end("params")

    new_xmp = (
        xmp[:old_start]
        + new_hex
        + xmp[old_end:]
    )

    return (
        new_xmp,
        latest["num"],
        old_params,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 78)
    print("PHOTOIA - SIGMOID TEST WRITER")
    print("=" * 78)

    # --------------------------------------------------------
    # VERIFICAR ARCHIVO ORIGINAL
    # --------------------------------------------------------

    if not os.path.exists(SOURCE_XMP):

        print()
        print(
            "ERROR: No existe el XMP original:"
        )
        print(SOURCE_XMP)
        print()

        return 1

    # --------------------------------------------------------
    # EVITAR SOBRESCRIBIR LA PRUEBA
    # --------------------------------------------------------

    if os.path.exists(TEST_XMP):

        print()
        print(
            f"ERROR: Ya existe el archivo de prueba:"
        )
        print(TEST_XMP)
        print()
        print(
            "Elimínalo manualmente si quieres "
            "generar una prueba nueva."
        )
        print()

        return 1

    # --------------------------------------------------------
    # LEER ORIGINAL
    # --------------------------------------------------------

    with open(
        SOURCE_XMP,
        "r",
        encoding="utf-8"
    ) as f:

        original_xmp = f.read()

    original_size = len(original_xmp)

    # --------------------------------------------------------
    # GENERAR PARAMS
    # --------------------------------------------------------

    values = build_params()

    new_hex = params_to_hex(
        values
    )

    # --------------------------------------------------------
    # REEMPLAZAR ULTIMO SIGMOID
    # --------------------------------------------------------

    (
        test_xmp,
        sigmoid_num,
        old_hex,
    ) = replace_latest_sigmoid_params(
        original_xmp,
        new_hex
    )

    # --------------------------------------------------------
    # VERIFICACIONES
    # --------------------------------------------------------

    if old_hex.lower() == new_hex.lower():

        print()
        print(
            "ADVERTENCIA: el HEX generado "
            "es igual al original."
        )

    if len(test_xmp) != original_size:

        raise RuntimeError(
            "El tamaño del XMP cambió. "
            "Abortando."
        )

    # --------------------------------------------------------
    # CONTAR OCURRENCIAS
    # --------------------------------------------------------

    old_count = original_xmp.count(
        old_hex
    )

    new_count = test_xmp.count(
        new_hex
    )

    if old_count < 1:

        raise RuntimeError(
            "No se pudo localizar el HEX original."
        )

    if new_count < 1:

        raise RuntimeError(
            "El nuevo HEX no quedó presente."
        )

    # --------------------------------------------------------
    # GUARDAR SOLO LA COPIA DE PRUEBA
    # --------------------------------------------------------

    with open(
        TEST_XMP,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(test_xmp)

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

    print()
    print(
        f"Sigmoid modificado: "
        f"darktable:num={sigmoid_num}"
    )

    print()
    print("HEX ORIGINAL")
    print("-" * 78)
    print(old_hex)

    print()
    print("HEX NUEVO")
    print("-" * 78)
    print(new_hex)

    print()
    print("ARCHIVO ORIGINAL")
    print("-" * 78)
    print(
        os.path.abspath(
            SOURCE_XMP
        )
    )

    print()
    print("ARCHIVO DE PRUEBA")
    print("-" * 78)
    print(
        os.path.abspath(
            TEST_XMP
        )
    )

    print()
    print("=" * 78)
    print("RESULTADO: COPIA DE PRUEBA CREADA")
    print("=" * 78)

    print()
    print(
        "El XMP original NO fue modificado."
    )

    print()
    print(
        "El único cambio realizado en la copia "
        "fue el darktable:params del último Sigmoid."
    )

    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())