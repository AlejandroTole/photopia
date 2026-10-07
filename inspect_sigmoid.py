import re

filename = "_DSC2125.NEF.xmp"

with open(filename, encoding="utf-8") as f:
    x = f.read()

pattern = r'(<rdf:li[^>]*>.*?darktable:operation="sigmoid".*?</rdf:li>)'

matches = re.findall(pattern, x, re.S)

print("BLOQUES SIGMOID:", len(matches))
print()

for i, block in enumerate(matches):
    print("=" * 80)
    print("SIGMOID", i + 1)
    print("=" * 80)
    print(block)
    print()