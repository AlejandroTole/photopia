import math
import struct


# ============================================================
# PHOTOIA - SIGMOID BUILDER
#
# Convierte valores de interfaz en los 14 float32
# que Darktable almacena en darktable:params.
#
# IMPORTANTE:
# Este programa NO modifica ningún XMP.
# Solo genera los 56 bytes / HEX.
# ============================================================


PARAM_NAMES = [
    "middle_grey_contrast",
    "contrast_skewness",
    "display_white_target",
    "display_black_target",
    "color_processing",
    "hue_preservation",
    "red_inset",
    "red_rotation",
    "green_inset",
    "green_rotation",
    "blue_inset",
    "blue_rotation",
    "purity",
    "base_primaries",
]


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
    """
    Fuerza exactamente la representación float32
    utilizada por Darktable.
    """

    return struct.unpack(
        "<f",
        struct.pack(
            "<f",
            float(value)
        )
    )[0]


# ============================================================
# VALIDACION
# ============================================================

def validate_range(name, value, minimum, maximum):

    if not minimum <= value <= maximum:

        raise ValueError(
            f"{name} fuera de rango: "
            f"{value}. "
            f"Rango permitido: "
            f"{minimum} - {maximum}"
        )


# ============================================================
# BUILD
# ============================================================

def build_sigmoid(
    contrast,
    skew,
    target_white,
    target_black,
    color_processing,
    preserve_hue,
    red_attenuation,
    red_rotation,
    green_attenuation,
    green_rotation,
    blue_attenuation,
    blue_rotation,
    recover_purity,
    base_primaries,
):
    """
    Recibe valores tal como los entiende el usuario
    y devuelve 14 float32 internos.
    """

    # --------------------------------------------------------
    # VALIDACIONES BÁSICAS
    # --------------------------------------------------------

    validate_range(
        "contrast",
        contrast,
        0.0,
        10.0,
    )

    validate_range(
        "skew",
        skew,
        -1.0,
        1.0,
    )

    validate_range(
        "target_white",
        target_white,
        0.0,
        100.0,
    )

    validate_range(
        "target_black",
        target_black,
        0.0,
        100.0,
    )

    validate_range(
        "preserve_hue",
        preserve_hue,
        0.0,
        100.0,
    )

    validate_range(
        "red_attenuation",
        red_attenuation,
        0.0,
        100.0,
    )

    validate_range(
        "green_attenuation",
        green_attenuation,
        0.0,
        100.0,
    )

    validate_range(
        "blue_attenuation",
        blue_attenuation,
        0.0,
        100.0,
    )

    validate_range(
        "recover_purity",
        recover_purity,
        0.0,
        100.0,
    )

    # --------------------------------------------------------
    # ENUM COLOR PROCESSING
    # --------------------------------------------------------

    if isinstance(color_processing, str):

        if color_processing not in COLOR_PROCESSING:

            raise ValueError(
                "Color processing desconocido: "
                f"{color_processing}"
            )

        color_processing_value = (
            COLOR_PROCESSING[color_processing]
        )

    else:

        color_processing_value = int(
            color_processing
        )

        if color_processing_value not in (
            0,
            1,
        ):

            raise ValueError(
                "color_processing debe ser "
                "0 o 1."
            )

    # --------------------------------------------------------
    # ENUM BASE PRIMARIES
    # --------------------------------------------------------

    if isinstance(base_primaries, str):

        if base_primaries not in BASE_PRIMARIES:

            raise ValueError(
                "Base primaries desconocido: "
                f"{base_primaries}"
            )

        base_primaries_value = (
            BASE_PRIMARIES[base_primaries]
        )

    else:

        base_primaries_value = int(
            base_primaries
        )

        if base_primaries_value not in (
            0,
            1,
            2,
            3,
            4,
        ):

            raise ValueError(
                "base_primaries debe estar "
                "entre 0 y 4."
            )

    # --------------------------------------------------------
    # ROTACIONES
    # --------------------------------------------------------

    validate_range(
        "red_rotation",
        red_rotation,
        -360.0,
        360.0,
    )

    validate_range(
        "green_rotation",
        green_rotation,
        -360.0,
        360.0,
    )

    validate_range(
        "blue_rotation",
        blue_rotation,
        -360.0,
        360.0,
    )

    # --------------------------------------------------------
    # CONSTRUIR PARAMETROS
    # --------------------------------------------------------

    values = [

        # [0]
        float(contrast),

        # [1]
        float(skew),

        # [2]
        float(target_white),

        # [3]
        float(target_black),

        # [4]
        float(color_processing_value),

        # [5]
        #
        # IMPORTANTE:
        # En tu XMP actual Darktable almacena
        # Preserve hue directamente en escala 0-100.
        #
        float(preserve_hue),

        # [6]
        percent_to_internal(
            red_attenuation
        ),

        # [7]
        degrees_to_radians(
            red_rotation
        ),

        # [8]
        percent_to_internal(
            green_attenuation
        ),

        # [9]
        degrees_to_radians(
            green_rotation
        ),

        # [10]
        percent_to_internal(
            blue_attenuation
        ),

        # [11]
        degrees_to_radians(
            blue_rotation
        ),

        # [12]
        percent_to_internal(
            recover_purity
        ),

        # [13]
        float(base_primaries_value),
    ]

    # --------------------------------------------------------
    # CONVERSION FINAL A FLOAT32
    # --------------------------------------------------------

    return [
        to_float32(value)
        for value in values
    ]


# ============================================================
# FLOAT32 -> HEX
# ============================================================

def values_to_hex(values):

    if len(values) != 14:

        raise ValueError(
            "Se necesitan exactamente "
            "14 parámetros."
        )

    raw = struct.pack(
        "<14f",
        *values
    )

    return raw.hex()


# ============================================================
# MOSTRAR RESULTADO
# ============================================================

def print_result(values):

    print()
    print("=" * 78)
    print("PHOTOIA - SIGMOID BUILDER")
    print("=" * 78)

    print()

    for i, value in enumerate(values):

        print(
            f"[{i:2}] "
            f"{PARAM_NAMES[i]:<24} "
            f"{value:.12f}"
        )

    hex_data = values_to_hex(values)

    print()
    print("=" * 78)
    print("DARKTABLE:PARAMS")
    print("=" * 78)

    print()
    print(hex_data)

    print()
    print(
        f"Bytes: {len(bytes.fromhex(hex_data))}"
    )

    print()
    print("=" * 78)
    print("FIN - NO SE MODIFICO NINGUN XMP")
    print("=" * 78)
    print()


# ============================================================
# PRUEBA CON EL ESTADO ACTUAL
# ============================================================

def main():

    values = build_sigmoid(

        contrast=3.0,

        skew=-0.33,

        target_white=71.61,

        target_black=0.2677,

        color_processing="per channel",

        preserve_hue=70.53,

        red_attenuation=10.4,

        red_rotation=11.8,

        green_attenuation=10.2,

        green_rotation=10.0,

        blue_attenuation=10.2,

        blue_rotation=19.5,

        recover_purity=36.0,

        base_primaries="working profile",
    )

    print_result(values)


if __name__ == "__main__":
    main()