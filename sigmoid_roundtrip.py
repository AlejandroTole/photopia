import math
import struct


# ============================================================
# PHOTOIA - SIGMOID ROUND TRIP
#
# UI -> valor interno Darktable -> float32 XMP
#     -> valor recuperado
#
# ESTE PROGRAMA NO MODIFICA NINGUN XMP.
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


# ============================================================
# CONVERSIONES
# ============================================================

def percent_to_fraction(value):
    return value / 100.0


def fraction_to_percent(value):
    return value * 100.0


def degrees_to_radians(value):
    return math.radians(value)


def radians_to_degrees(value):
    return math.degrees(value)


# ============================================================
# EMPAQUETAR COMO DARKTABLE/XMP FLOAT32
# ============================================================

def to_float32(value):
    """
    Simula exactamente la precisión float32
    utilizada en los parámetros del XMP.
    """

    return struct.unpack(
        "<f",
        struct.pack("<f", float(value))
    )[0]


# ============================================================
# CONSTRUIR LOS 14 PARAMETROS
# ============================================================

def build_internal_values():

    # ========================================================
    # VALORES DE INTERFAZ ACTUALES
    # ========================================================

    contrast = 3.000
    skew = -0.330

    target_white = 71.61
    target_black = 0.2677

    color_processing = 0

    preserve_hue = 70.53

    red_attenuation = 10.4
    red_rotation = 11.8

    green_attenuation = 10.2
    green_rotation = 10.0

    blue_attenuation = 10.2
    blue_rotation = 19.5

    recover_purity = 36.0

    base_primaries = 0

    # ========================================================
    # CONVERSIONES
    # ========================================================

    values = [

        # [0]
        contrast,

        # [1]
        skew,

        # [2]
        target_white,

        # [3]
        target_black,

        # [4]
        color_processing,

        # [5]
        #
        # IMPORTANTE:
        # Tu XMP demuestra que Preserve hue se almacena
        # directamente en la escala 0-100.
        #
        preserve_hue,

        # [6]
        #
        # Attenuation sí usa 0-1 internamente.
        #
        percent_to_fraction(red_attenuation),

        # [7]
        degrees_to_radians(red_rotation),

        # [8]
        percent_to_fraction(green_attenuation),

        # [9]
        degrees_to_radians(green_rotation),

        # [10]
        percent_to_fraction(blue_attenuation),

        # [11]
        degrees_to_radians(blue_rotation),

        # [12]
        percent_to_fraction(recover_purity),

        # [13]
        base_primaries,
    ]

    return values


# ============================================================
# FLOAT32
# ============================================================

def convert_to_float32(values):

    return [
        to_float32(value)
        for value in values
    ]


# ============================================================
# RECUPERAR VALORES DE INTERFAZ
# ============================================================

def internal_to_ui(values):

    ui = [

        # [0]
        values[0],

        # [1]
        values[1],

        # [2]
        values[2],

        # [3]
        values[3],

        # [4]
        int(round(values[4])),

        # [5]
        #
        # Preserve hue permanece 0-100.
        #
        values[5],

        # [6]
        fraction_to_percent(values[6]),

        # [7]
        radians_to_degrees(values[7]),

        # [8]
        fraction_to_percent(values[8]),

        # [9]
        radians_to_degrees(values[9]),

        # [10]
        fraction_to_percent(values[10]),

        # [11]
        radians_to_degrees(values[11]),

        # [12]
        fraction_to_percent(values[12]),

        # [13]
        int(round(values[13])),
    ]

    return ui


# ============================================================
# MOSTRAR
# ============================================================

def print_results(original, float32_values, recovered):

    print()
    print("=" * 78)
    print("PHOTOIA - SIGMOID 14 PARAMETER ROUND TRIP")
    print("=" * 78)

    print()
    print(
        f"{'IDX':>3}  "
        f"{'PARAMETRO':<24} "
        f"{'ORIGINAL':>16} "
        f"{'FLOAT32':>16} "
        f"{'RECUPERADO':>16}"
    )

    print("-" * 78)

    for i in range(14):

        print(
            f"{i:>3}  "
            f"{PARAM_NAMES[i]:<24} "
            f"{original[i]:>16.9f} "
            f"{float32_values[i]:>16.9f} "
            f"{recovered[i]:>16.9f}"
        )

    print()
    print("=" * 78)
    print("COMPARACION CON EL XMP ACTUAL")
    print("=" * 78)

    # Valores que actualmente sabemos que tiene tu XMP
    current_xmp = [
        2.999999523163,
        -0.329999983311,
        71.609992980957,
        0.267699986696,
        0.0,
        70.529991149902,
        0.104000002146,
        0.205948859453,
        0.101999998093,
        0.174532920122,
        0.101999998093,
        0.340339154005,
        0.360000014305,
        0.0,
    ]

    print()
    print(
        f"{'IDX':>3}  "
        f"{'PARAMETRO':<24} "
        f"{'XMP ACTUAL':>18} "
        f"{'GENERADO':>18} "
        f"{'DIFERENCIA':>16}"
    )

    print("-" * 88)

    all_close = True

    for i in range(14):

        difference = (
            float32_values[i]
            - current_xmp[i]
        )

        # Tolerancia razonable para esta comparación.
        if abs(difference) > 0.00001:
            all_close = False

        print(
            f"{i:>3}  "
            f"{PARAM_NAMES[i]:<24} "
            f"{current_xmp[i]:>18.12f} "
            f"{float32_values[i]:>18.12f} "
            f"{difference:>16.12f}"
        )

    print()

    if all_close:

        print(
            "RESULTADO: OK"
        )

        print(
            "Los 14 parametros reconstruyen "
            "los valores del XMP dentro de la "
            "tolerancia establecida."
        )

    else:

        print(
            "RESULTADO: REVISAR"
        )

        print(
            "Uno o mas parametros no coinciden "
            "con el XMP actual."
        )

    print()

    print("=" * 78)
    print("FIN")
    print("=" * 78)
    print()


# ============================================================
# MAIN
# ============================================================

def main():

    original = build_internal_values()

    float32_values = convert_to_float32(
        original
    )

    recovered = internal_to_ui(
        float32_values
    )

    print_results(
        original,
        float32_values,
        recovered
    )


if __name__ == "__main__":
    main()