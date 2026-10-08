import re
from apply.writers.sigmoid import (
    SLOT_BASE_PRIMARIES,
    SLOT_COLOR_PROCESSING,
    unpack_sigmoid_params,
)

filename = "_DSC2125.NEF.xmp"

with open(filename, encoding="utf-8") as f:
    x = f.read()

pattern = r'darktable:operation="sigmoid".*?darktable:params="([0-9a-f]+)"'

p = re.findall(pattern, x, re.S)

print("SIGMOID ENCONTRADOS:", len(p))
print()

for i, hexdata in enumerate(p):
    print("=" * 60)
    print("SIGMOID", i + 1)
    print("BYTES:", len(hexdata) // 2)
    print("HEX:", hexdata)

    raw = bytes.fromhex(hexdata)

    if len(raw) != 56:
        print(f"ERROR: el módulo contiene {len(raw)} bytes, se esperaban 56.")
        continue

    values = unpack_sigmoid_params(raw)
    print("PARAMETROS:")
    for index, value in enumerate(values):
        kind = "int32" if index in (SLOT_COLOR_PROCESSING, SLOT_BASE_PRIMARIES) else "float32"
        print(f"  [{index}] {kind}: {value}")