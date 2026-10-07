import json
import sys


PLAN_FILE = "edit_plan.json"


REQUIRED_SIGMOID_FIELDS = [
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


COLOR_PROCESSING = {
    "per channel",
    "RGB ratio",
}


BASE_PRIMARIES = {
    "working profile",
    "Rec2020",
    "Display P3",
    "Adobe RGB (compatible)",
    "sRGB",
}


def require_number(data, field):
    value = data[field]

    if not isinstance(value, (int, float)):
        raise ValueError(
            f"{field} debe ser numérico."
        )

    return float(value)


def validate_range(field, value, minimum, maximum):

    if not minimum <= value <= maximum:
        raise ValueError(
            f"{field}={value} fuera de rango "
            f"({minimum} - {maximum})."
        )


def main():

    print()
    print("=" * 78)
    print("PHOTOIA - EDIT PLAN VALIDATOR")
    print("=" * 78)

    try:
        with open(
            PLAN_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            plan = json.load(f)

    except FileNotFoundError:

        print()
        print(
            f"ERROR: No existe {PLAN_FILE}"
        )
        return 1

    except json.JSONDecodeError as error:

        print()
        print(
            "ERROR: JSON inválido."
        )
        print(error)
        return 1

    # --------------------------------------------------------
    # VERSION
    # --------------------------------------------------------

    if plan.get("version") != 1:
        raise ValueError(
            "version debe ser 1."
        )

    # --------------------------------------------------------
    # TARGET
    # --------------------------------------------------------

    target = plan.get("target")

    if not isinstance(target, dict):
        raise ValueError(
            "Falta target."
        )

    if target.get("operation") != "sigmoid":
        raise ValueError(
            "target.operation debe ser 'sigmoid'."
        )

    darktable_num = target.get(
        "darktable_num"
    )

    if not isinstance(
        darktable_num,
        int
    ):

        raise ValueError(
            "darktable_num debe ser entero."
        )

    if darktable_num < 0:
        raise ValueError(
            "darktable_num no puede ser negativo."
        )

    # --------------------------------------------------------
    # SIGMOID
    # --------------------------------------------------------

    sigmoid = plan.get("sigmoid")

    if not isinstance(
        sigmoid,
        dict
    ):

        raise ValueError(
            "Falta el bloque sigmoid."
        )

    missing = [
        field
        for field in REQUIRED_SIGMOID_FIELDS
        if field not in sigmoid
    ]

    if missing:

        raise ValueError(
            "Faltan campos: "
            + ", ".join(missing)
        )

    # --------------------------------------------------------
    # RANGOS
    # --------------------------------------------------------

    validate_range(
        "contrast",
        require_number(
            sigmoid,
            "contrast"
        ),
        0.0,
        10.0,
    )

    validate_range(
        "skew",
        require_number(
            sigmoid,
            "skew"
        ),
        -1.0,
        1.0,
    )

    validate_range(
        "target_white",
        require_number(
            sigmoid,
            "target_white"
        ),
        0.0,
        100.0,
    )

    validate_range(
        "target_black",
        require_number(
            sigmoid,
            "target_black"
        ),
        0.0,
        100.0,
    )

    validate_range(
        "preserve_hue",
        require_number(
            sigmoid,
            "preserve_hue"
        ),
        0.0,
        100.0,
    )

    for field in (
        "red_attenuation",
        "green_attenuation",
        "blue_attenuation",
        "recover_purity",
    ):

        validate_range(
            field,
            require_number(
                sigmoid,
                field
            ),
            0.0,
            100.0,
        )

    for field in (
        "red_rotation",
        "green_rotation",
        "blue_rotation",
    ):

        validate_range(
            field,
            require_number(
                sigmoid,
                field
            ),
            -360.0,
            360.0,
        )

    # --------------------------------------------------------
    # ENUMS
    # --------------------------------------------------------

    color_processing = sigmoid[
        "color_processing"
    ]

    if color_processing not in COLOR_PROCESSING:

        raise ValueError(
            "color_processing inválido: "
            f"{color_processing}"
        )

    base_primaries = sigmoid[
        "base_primaries"
    ]

    if base_primaries not in BASE_PRIMARIES:

        raise ValueError(
            "base_primaries inválido: "
            f"{base_primaries}"
        )

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

    print()
    print("PLAN VALIDO")
    print("-" * 78)

    print(
        f"Sigmoid objetivo: num={darktable_num}"
    )

    print(
        f"Contrast:          "
        f"{sigmoid['contrast']}"
    )

    print(
        f"Skew:              "
        f"{sigmoid['skew']}"
    )

    print(
        f"Target white:      "
        f"{sigmoid['target_white']}"
    )

    print(
        f"Target black:      "
        f"{sigmoid['target_black']}"
    )

    print(
        f"Color processing:  "
        f"{color_processing}"
    )

    print(
        f"Preserve hue:      "
        f"{sigmoid['preserve_hue']}%"
    )

    print(
        f"Red attenuation:   "
        f"{sigmoid['red_attenuation']}%"
    )

    print(
        f"Green attenuation: "
        f"{sigmoid['green_attenuation']}%"
    )

    print(
        f"Blue attenuation:  "
        f"{sigmoid['blue_attenuation']}%"
    )

    print(
        f"Recover purity:    "
        f"{sigmoid['recover_purity']}%"
    )

    print(
        f"Base primaries:    "
        f"{base_primaries}"
    )

    print()
    print("=" * 78)
    print("VALIDACION COMPLETADA")
    print("=" * 78)
    print()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())

    except ValueError as error:

        print()
        print("=" * 78)
        print("PLAN INVALIDO")
        print("=" * 78)

        print()
        print(error)
        print()

        sys.exit(1)