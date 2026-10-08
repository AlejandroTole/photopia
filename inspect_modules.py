import re, struct
from pathlib import Path

for xmp_path in Path('.').glob('*.xmp'):
    content = xmp_path.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'darktable:operation="colorbalancergb"[^>]*darktable:params="([0-9a-fA-F]+)"', content):
        hex_data = m.group(1)
        raw = bytes.fromhex(hex_data)
        n_floats = len(raw) // 4
        print(f"File: {xmp_path.name} | Op: colorbalancergb | Bytes: {len(raw)} | Floats ({n_floats}):")
        if len(raw) % 4 == 0 and n_floats > 0:
            vals = struct.unpack(f"<{n_floats}f", raw)
            for i, v in enumerate(vals):
                print(f"  [{i:2}] {v}")
