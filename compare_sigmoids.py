import re
import struct
import math


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

        raw = bytes.fromhex(
            match.group("params")
        )

        values = struct.unpack(
            "<14f",
            raw
        )

        results.append({
            "num": num,
            "enabled": enabled,
            "values": values,
            "hex": match.group("params"),
        })

    return results


def print_value(index, value):

    if index in (7, 9, 11):

        print(
            f"{PARAM_NAMES[index]:<24} "
            f"{value:>14.9f}  "
            f"{math.degrees(value):>10.4f}°"
        )

    elif index in (6, 8, 10, 12):

        print(
            f"{PARAM_NAMES[index]:<24} "
            f"{value:>14.9f}  "
            f"{value * 100:>10.4f}%"
        )

    else:

        print(
            f"{PARAM_NAMES[index]:<24} "
            f"{value:>14.9f}"
        )


def compare(a, b):

    print()
    print("=" * 78)
    print(
        f"COMPARACION: num={a['num']} "
        f"-> num={b['num']}"
    )
    print("=" * 78)

    changes = 0

    for i in range(14):

        old = a["values"][i]
        new = b["values"][i]

        if old != new:

            changes += 1

            print()
            print(
                f"[{i}] {PARAM_NAMES[i]}"
            )
            print(
                f"    anterior: "
                f"{old:.12f}"
            )
            print(
                f"    nuevo:    "
                f"{new:.12f}"
            )

            if i in (6, 8, 10, 12):

                print(
                    f"    UI anterior: "
                    f"{old * 100:.6f}%"
                )

                print(
                    f"    UI nuevo:    "
                    f"{new * 100:.6f}%"
                )

            elif i in (7, 9, 11):

                print(
                    f"    grados anterior: "
                    f"{math.degrees(old):.6f}°"
                )

                print(
                    f"    grados nuevo:    "
                    f"{math.degrees(new):.6f}°"
                )

    print()

    if changes == 0:

        print("No hay cambios.")

    else:

        print(
            f"Parametros modificados: {changes}"
        )


def main():

    with open(
        XMP_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        xmp = f.read()

    sigmoids = extract_sigmoids(xmp)

    sigmoids.sort(
        key=lambda item: item["num"]
    )

    print()
    print("=" * 78)
    print("PHOTOIA - COMPARADOR DE SIGMOIDS")
    print("=" * 78)

    print()
    print(
        f"Sigmoids encontrados: "
        f"{len(sigmoids)}"
    )

    selected = [
        item
        for item in sigmoids
        if item["num"] in (30, 31, 32)
    ]

    for item in selected:

        print()
        print(
            f"darktable:num={item['num']} "
            f"enabled={item['enabled']}"
        )

        for i, value in enumerate(
            item["values"]
        ):

            print_value(
                i,
                value
            )

    if len(selected) >= 2:

        for i in range(
            len(selected) - 1
        ):

            compare(
                selected[i],
                selected[i + 1]
            )

    print()
    print("=" * 78)
    print("FIN")
    print("=" * 78)
    print()


if __name__ == "__main__":
    main()