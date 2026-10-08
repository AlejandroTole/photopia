import re
import math
from apply.writers.sigmoid import (
    SLOT_BASE_PRIMARIES,
    SLOT_COLOR_PROCESSING,
    unpack_sigmoid_params,
)

XMP_FILE = "_DSC2125.NEF.xmp"

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
    0: "per channel",
    1: "RGB ratio",
}

BASE_PRIMARIES = {
    0: "working profile",
    1: "Rec2020",
    2: "Display P3",
    3: "Adobe RGB (compatible)",
    4: "sRGB",
}


def decode_sigmoid_params(hex_data):
    raw = bytes.fromhex(hex_data)

    if len(raw) != 56:
        raise ValueError(
            f"Se esperaban 56 bytes, pero llegaron {len(raw)}."
        )

    return unpack_sigmoid_params(raw)


def extract_sigmoids(xmp):

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
            attrs,
        )

        enabled_match = re.search(
            r'darktable:enabled="(\d+)"',
            attrs,
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

        params = match.group("params")

        try:
            values = decode_sigmoid_params(params)
        except Exception as error:
            print()
            print("ERROR decodificando Sigmoid:")
            print(error)
            continue

        results.append(
            {
                "num": num,
                "enabled": enabled,
                "params": params,
                "values": values,
            }
        )

    return results


def percent(value):
    return value * 100.0


def degrees(value):
    return math.degrees(value)


def print_current(item):

    values = item["values"]

    print()
    print("=" * 72)
    print("PHOTOIA - ESTADO ACTUAL DEL SIGMOID")
    print("=" * 72)

    print()
    print(f"darktable:num:     {item['num']}")
    print(f"enabled:           {item['enabled']}")

    print()
    print("CONTROLES")
    print("-" * 72)

    print(f"Contrast:          {values[0]:.9f}")
    print(f"Skew:              {values[1]:.9f}")
    print(f"Target white:      {values[2]:.9f}")
    print(f"Target black:      {values[3]:.9f}")

    color_index = values[SLOT_COLOR_PROCESSING]
    color_name = COLOR_PROCESSING.get(
        color_index,
        f"UNKNOWN ({values[4]:.9f})"
    )

    print(
        f"Color processing:  {color_name}"
        f"   [internal {values[SLOT_COLOR_PROCESSING]:d}]"
    )

    print(f"Preserve hue:      {values[5]:.9f}")

    print()
    print("RED")
    print("-" * 72)

    print(
        f"Attenuation:       {values[6]:.9f}"
        f"  [internal]"
    )

    print(
        f"Attenuation UI:    {percent(values[6]):.6f}%"
    )

    print(
        f"Rotation:          {degrees(values[7]):.6f}°"
        f"  ({values[7]:.9f} rad)"
    )

    print()
    print("GREEN")
    print("-" * 72)

    print(
        f"Attenuation:       {values[8]:.9f}"
        f"  [internal]"
    )

    print(
        f"Attenuation UI:    {percent(values[8]):.6f}%"
    )

    print(
        f"Rotation:          {degrees(values[9]):.6f}°"
        f"  ({values[9]:.9f} rad)"
    )

    print()
    print("BLUE")
    print("-" * 72)

    print(
        f"Attenuation:       {values[10]:.9f}"
        f"  [internal]"
    )

    print(
        f"Attenuation UI:    {percent(values[10]):.6f}%"
    )

    print(
        f"Rotation:          {degrees(values[11]):.6f}°"
        f"  ({values[11]:.9f} rad)"
    )

    print()
    print("COLOR")
    print("-" * 72)

    print(
        f"Recover purity:    "
        f"{percent(values[12]):.6f}%"
        f"  [internal {values[12]:.9f}]"
    )

    base_index = values[SLOT_BASE_PRIMARIES]

    base_name = BASE_PRIMARIES.get(
        base_index,
        f"UNKNOWN ({values[13]:.9f})"
    )

    print(
        f"Base primaries:    {base_name}"
        f"   [internal {values[SLOT_BASE_PRIMARIES]:d}]"
    )


def print_raw_values(item):

    values = item["values"]

    print()
    print("=" * 72)
    print("VALORES INTERNOS EXACTOS")
    print("=" * 72)

    for i, value in enumerate(values):

        print(
            f"[{i:2}] "
            f"{PARAM_NAMES[i]:<24} "
            f"{value:.12f}"
        )


def print_history(sigmoids):

    print()
    print("=" * 72)
    print("HISTORIAL SIGMOID")
    print("=" * 72)

    for item in sigmoids:

        values = item["values"]

        print()
        print(
            f"num={item['num']:>3} "
            f"enabled={item['enabled']} "
            f"contrast={values[0]:.6f} "
            f"skew={values[1]:.6f}"
        )


def main():

    try:

        with open(
            XMP_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            xmp = f.read()

    except FileNotFoundError:

        print()
        print("ERROR: No se encontró:")
        print(XMP_FILE)
        print()

        return 1

    sigmoids = extract_sigmoids(xmp)

    print()
    print("=" * 72)
    print("PHOTOIA - SIGMOID PARSER")
    print("=" * 72)

    print()
    print(
        f"SIGMOID encontrados: "
        f"{len(sigmoids)}"
    )

    if not sigmoids:

        print()
        print(
            "ERROR: No se encontraron "
            "módulos Sigmoid."
        )

        return 1

    sigmoids.sort(
        key=lambda item: item["num"]
    )

    current = sigmoids[-1]

    print_current(current)
    print_raw_values(current)
    print_history(sigmoids)

    print()
    print("=" * 72)
    print("FIN")
    print("=" * 72)
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())