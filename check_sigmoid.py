import re
import struct

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

    print("FLOATS:")

    for j in range(0, len(raw) - 3, 4):
        value = struct.unpack("<f", raw[j:j + 4])[0]
        print(f"  [{j // 4}] {value:.9f}")