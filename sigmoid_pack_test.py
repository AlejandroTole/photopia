import re
import struct


XMP_FILE = "_DSC2125.NEF.xmp"


# ============================================================
# EXTRAER SIGMOIDS
# ============================================================

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

        num = (
            int(num_match.group(1))
            if num_match
            else -1
        )

        params = match.group("params")

        results.append(
            {
                "num": num,
                "params": params,
            }
        )

    return results


# ============================================================
# HEX -> 14 FLOAT32
# ============================================================

def unpack_params(hex_data):

    raw = bytes.fromhex(hex_data)

    if len(raw) != 56:
        raise ValueError(
            f"Se esperaban 56 bytes, "
            f"pero llegaron {len(raw)}."
        )

    return list(
        struct.unpack(
            "<14f",
            raw
        )
    )


# ============================================================
# 14 FLOAT32 -> HEX
# ============================================================

def pack_params(values):

    if len(values) != 14:
        raise ValueError(
            "Sigmoid necesita exactamente "
            "14 parámetros."
        )

    raw = struct.pack(
        "<14f",
        *values
    )

    return raw.hex()


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 72)
    print("PHOTOIA - SIGMOID PACK TEST")
    print("=" * 72)

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

    if not sigmoids:

        print()
        print(
            "ERROR: No se encontraron "
            "módulos Sigmoid."
        )
        print()

        return 1

    # Ordenar por darktable:num
    sigmoids.sort(
        key=lambda item: item["num"]
    )

    current = sigmoids[-1]

    original_hex = current["params"]

    values = unpack_params(
        original_hex
    )

    rebuilt_hex = pack_params(
        values
    )

    print()
    print(
        f"Sigmoid seleccionado: "
        f"darktable:num={current['num']}"
    )

    print()
    print("HEX ORIGINAL")
    print("-" * 72)
    print(original_hex)

    print()
    print("HEX RECONSTRUIDO")
    print("-" * 72)
    print(rebuilt_hex)

    print()
    print("=" * 72)

    if original_hex.lower() == rebuilt_hex.lower():

        print("RESULTADO: EXACT MATCH")
        print()
        print(
            "Los 56 bytes del Sigmoid fueron "
            "decodificados y reconstruidos "
            "sin ninguna alteración."
        )

    else:

        print("RESULTADO: ERROR")
        print()
        print(
            "El HEX reconstruido no coincide "
            "con el HEX original."
        )

        # Mostrar posiciones diferentes
        print()
        print("DIFERENCIAS:")

        for i, (a, b) in enumerate(
            zip(
                original_hex.lower(),
                rebuilt_hex.lower()
            )
        ):

            if a != b:

                print(
                    f"Posición {i}: "
                    f"original={a} "
                    f"reconstruido={b}"
                )

    print("=" * 72)
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())