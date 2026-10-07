import math


# ============================================================
# CONVERSIONES DARKTABLE SIGMOID
# Interfaz <-> valor almacenado en XMP
# ============================================================


def percent_to_internal(value_percent):
    """
    Porcentaje de interfaz -> valor interno 0.0 - 1.0
    """

    return value_percent / 100.0


def internal_to_percent(value_internal):
    """
    Valor interno 0.0 - 1.0 -> porcentaje de interfaz
    """

    return value_internal * 100.0


def degrees_to_radians(value_degrees):
    """
    Grados de interfaz -> radianes internos
    """

    return math.radians(value_degrees)


def radians_to_degrees(value_radians):
    """
    Radianes internos -> grados de interfaz
    """

    return math.degrees(value_radians)


def direct_to_internal(value):
    """
    Parámetros que se almacenan prácticamente 1:1.
    """

    return float(value)


def internal_to_direct(value):
    """
    Parámetros almacenados prácticamente 1:1.
    """

    return float(value)


# ============================================================
# DEMOSTRACION
# ============================================================

def main():

    print()
    print("=" * 72)
    print("PHOTOIA - SIGMOID CONVERTER TEST")
    print("=" * 72)

    # --------------------------------------------------------
    # CONTRAST
    # --------------------------------------------------------

    contrast_ui = 3.000

    contrast_internal = direct_to_internal(
        contrast_ui
    )

    print()
    print("CONTRAST")
    print("-" * 72)
    print(
        f"UI:       {contrast_ui:.6f}"
    )
    print(
        f"Internal: {contrast_internal:.9f}"
    )

    # --------------------------------------------------------
    # SKEW
    # --------------------------------------------------------

    skew_ui = -0.330

    skew_internal = direct_to_internal(
        skew_ui
    )

    print()
    print("SKEW")
    print("-" * 72)
    print(
        f"UI:       {skew_ui:.6f}"
    )
    print(
        f"Internal: {skew_internal:.9f}"
    )

    # --------------------------------------------------------
    # PRESERVE HUE
    # --------------------------------------------------------

    hue_ui = 70.53

    hue_internal = percent_to_internal(
        hue_ui
    )

    print()
    print("PRESERVE HUE")
    print("-" * 72)
    print(
        f"UI:       {hue_ui:.6f}%"
    )
    print(
        f"Internal: {hue_internal:.9f}"
    )
    print(
        f"Back UI:  "
        f"{internal_to_percent(hue_internal):.6f}%"
    )

    # --------------------------------------------------------
    # RED ATTENUATION
    # --------------------------------------------------------

    red_attenuation_ui = 10.4

    red_attenuation_internal = percent_to_internal(
        red_attenuation_ui
    )

    print()
    print("RED ATTENUATION")
    print("-" * 72)
    print(
        f"UI:       {red_attenuation_ui:.6f}%"
    )
    print(
        f"Internal: "
        f"{red_attenuation_internal:.9f}"
    )

    # --------------------------------------------------------
    # GREEN ATTENUATION
    # --------------------------------------------------------

    green_attenuation_ui = 10.2

    green_attenuation_internal = percent_to_internal(
        green_attenuation_ui
    )

    print()
    print("GREEN ATTENUATION")
    print("-" * 72)
    print(
        f"UI:       {green_attenuation_ui:.6f}%"
    )
    print(
        f"Internal: "
        f"{green_attenuation_internal:.9f}"
    )

    # --------------------------------------------------------
    # BLUE ATTENUATION
    # --------------------------------------------------------

    blue_attenuation_ui = 10.2

    blue_attenuation_internal = percent_to_internal(
        blue_attenuation_ui
    )

    print()
    print("BLUE ATTENUATION")
    print("-" * 72)
    print(
        f"UI:       {blue_attenuation_ui:.6f}%"
    )
    print(
        f"Internal: "
        f"{blue_attenuation_internal:.9f}"
    )

    # --------------------------------------------------------
    # RED ROTATION
    # --------------------------------------------------------

    red_rotation_ui = 11.8

    red_rotation_internal = degrees_to_radians(
        red_rotation_ui
    )

    print()
    print("RED ROTATION")
    print("-" * 72)
    print(
        f"UI:       {red_rotation_ui:.6f}°"
    )
    print(
        f"Internal: "
        f"{red_rotation_internal:.12f} rad"
    )

    # --------------------------------------------------------
    # GREEN ROTATION
    # --------------------------------------------------------

    green_rotation_ui = 10.0

    green_rotation_internal = degrees_to_radians(
        green_rotation_ui
    )

    print()
    print("GREEN ROTATION")
    print("-" * 72)
    print(
        f"UI:       {green_rotation_ui:.6f}°"
    )
    print(
        f"Internal: "
        f"{green_rotation_internal:.12f} rad"
    )

    # --------------------------------------------------------
    # BLUE ROTATION
    # --------------------------------------------------------

    blue_rotation_ui = 19.5

    blue_rotation_internal = degrees_to_radians(
        blue_rotation_ui
    )

    print()
    print("BLUE ROTATION")
    print("-" * 72)
    print(
        f"UI:       {blue_rotation_ui:.6f}°"
    )
    print(
        f"Internal: "
        f"{blue_rotation_internal:.12f} rad"
    )

    # --------------------------------------------------------
    # RECOVER PURITY
    # --------------------------------------------------------

    purity_ui = 36.0

    purity_internal = percent_to_internal(
        purity_ui
    )

    print()
    print("RECOVER PURITY")
    print("-" * 72)
    print(
        f"UI:       {purity_ui:.6f}%"
    )
    print(
        f"Internal: {purity_internal:.9f}"
    )

    # --------------------------------------------------------
    # FIN
    # --------------------------------------------------------

    print()
    print("=" * 72)
    print("CONVERSION TEST COMPLETE")
    print("=" * 72)
    print()


if __name__ == "__main__":
    main()