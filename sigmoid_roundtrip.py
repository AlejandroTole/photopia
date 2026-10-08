import math
from apply.writers.sigmoid import (
    SLOT_BASE_PRIMARIES,
    SLOT_COLOR_PROCESSING,
    pack_sigmoid_params,
    unpack_sigmoid_params,
)


# ============================================================
# PHOTOIA - SIGMOID ROUND TRIP
#
# UI -> parámetros tipados Darktable/XMP
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
# EMPAQUETAR COMO DARKTABLE/XMP
# ============================================================

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
# REPRESENTACION DARKTABLE/XMP
# ============================================================

def roundtrip_serialized_params(values):

    return list(unpack_sigmoid_params(pack_sigmoid_params(values)))


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
        values[SLOT_COLOR_PROCESSING],

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
        values[SLOT_BASE_PRIMARIES],
    ]

    return ui


# ============================================================
# MOSTRAR
# ============================================================

def print_results(original, serialized_values, recovered):

    print()
    print("=" * 78)
    print("PHOTOIA - SIGMOID 14 PARAMETER ROUND TRIP")
    print("=" * 78)

    print()
    print(
        f"{'IDX':>3}  "
        f"{'PARAMETRO':<24} "
        f"{'ORIGINAL':>16} "
        f"{'SERIALIZADO':>16} "
        f"{'RECUPERADO':>16}"
    )

    print("-" * 78)

    for i in range(14):
        if i in (SLOT_COLOR_PROCESSING, SLOT_BASE_PRIMARIES):
            original_display = f"{int(original[i]):d}"
            serialized_display = f"{int(serialized_values[i]):d}"
            recovered_display = f"{int(recovered[i]):d}"
        else:
            original_display = f"{original[i]:.9f}"
            serialized_display = f"{serialized_values[i]:.9f}"
            recovered_display = f"{recovered[i]:.9f}"

        print(
            f"{i:>3}  "
            f"{PARAM_NAMES[i]:<24} "
            f"{original_display:>16} "
            f"{serialized_display:>16} "
            f"{recovered_display:>16}"
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
            serialized_values[i]
            - current_xmp[i]
        )

        # Tolerancia razonable para esta comparación.
        if abs(difference) > 0.00001:
            all_close = False

        print(
            f"{i:>3}  "
            f"{PARAM_NAMES[i]:<24} "
            f"{current_xmp[i]:>18.12f} "
            f"{serialized_values[i]:>18.12f} "
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

    serialized_values = roundtrip_serialized_params(
        original
    )

    recovered = internal_to_ui(
        serialized_values
    )

    print_results(
        original,
        serialized_values,
        recovered
    )


if __name__ == "__main__":
    main()