import json
from pathlib import Path
from apply.writers.sigmoid import pack_sigmoid_params, unpack_sigmoid_params


BASE_DIR = Path(__file__).resolve().parent

DECISION_FILE = BASE_DIR / "validated_decision.json"
XMP_FILE = BASE_DIR / "_DSC2125.NEF.xmp"


BLENDOP_PARAMS = (
    "gz08eJxjYGBgYAFiCQYYOOHEgAZY0QWAgBGLGANDgz0Ej1Q+"
    "dlAx68oBEMbFxwX+AwGIBgCbGCeh"
)

BLENDOP_VERSION = "14"


# ============================================================
# DARKTABLE SIGMOID
# ============================================================
#
# Para esta prueba NO usamos el valor de PHOTOIA.
# Forzamos sigmoid = 8.0 para comprobar si Darktable
# realmente aplica el parámetro contenido en el XMP.
#
# Si esta prueba produce una imagen diferente al baseline,
# sabremos que el mecanismo XMP funciona y después podremos
# volver a conectar PHOTOIA con el valor real.
#
SIGMOID_TEST_VALUE = 8.0


# Parámetros base de Darktable 5.x sigmoid.
#
# El primer float es el contraste.
# Los demás parámetros permanecen iguales.
#
BASE_PARAMS = (
    "6ce7eb3f"
    "00000000"
    "0000c842"
    "6c09793c"
    "00000000"
    "0000c842"
    "00000000"
    "00000000"
    "00000000"
    "00000000"
    "00000000"
    "00000000"
    "00000000"
    "00000000"
)


def load_decision():
    """
    Comprueba que exista la decisión validada de PHOTOIA.
    """

    if not DECISION_FILE.exists():
        raise FileNotFoundError(
            f"No existe el archivo:\n{DECISION_FILE}"
        )

    with DECISION_FILE.open(
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


def build_params(sigmoid_value):
    """
    Construye los 56 bytes del parámetro sigmoid.

    El primer float es el valor de contraste.
    """

    values = list(unpack_sigmoid_params(bytes.fromhex(BASE_PARAMS)))
    values[0] = float(sigmoid_value)
    params = pack_sigmoid_params(values).hex()

    if len(params) != 112:
        raise RuntimeError(
            "ERROR: params debe tener exactamente "
            "112 caracteres hexadecimales."
        )

    return params


def create_xmp(params):

    xmp_text = f'''<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta
    xmlns:x="adobe:ns:meta/"
    x:xmptk="PHOTOIA">

  <rdf:RDF
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">

    <rdf:Description
        xmlns:darktable="http://darktable.sf.net/"
        xmlns:dc="http://purl.org/dc/elements/1.1/"
        xmlns:xmp="http://ns.adobe.com/xap/1.0/"
        xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"
        darktable:xmp_version="4"
        darktable:raw_params="0"
        darktable:auto_presets_applied="0"
        darktable:history_end="0"
        darktable:iop_order_version="2">

      <darktable:masks_history>
        <rdf:Seq/>
      </darktable:masks_history>

      <darktable:history>
        <rdf:Seq>

          <rdf:li
              darktable:num="0"
              darktable:operation="sigmoid"
              darktable:enabled="1"
              darktable:modversion="3"
              darktable:params="{params}"
              darktable:multi_name=""
              darktable:multi_name_hand_edited="0"
              darktable:multi_priority="0"
              darktable:blendop_version="{BLENDOP_VERSION}"
              darktable:blendop_params="{BLENDOP_PARAMS}"/>

        </rdf:Seq>
      </darktable:history>

    </rdf:Description>

  </rdf:RDF>

</x:xmpmeta>
'''

    XMP_FILE.write_text(
        xmp_text,
        encoding="utf-8"
    )


def main():

    print("=" * 60)
    print("PHOTOIA - DARKTABLE SIGMOID TEST")
    print("=" * 60)

    # --------------------------------------------------------
    # Comprobar decisión PHOTOIA
    # --------------------------------------------------------

    decision = load_decision()

    adjustments = decision.get(
        "adjustments",
        {}
    )

    photoia_contrast = float(
        adjustments.get(
            "contrast",
            0
        )
    )

    # --------------------------------------------------------
    # PRUEBA
    # --------------------------------------------------------

    sigmoid_value = SIGMOID_TEST_VALUE

    params = build_params(
        sigmoid_value
    )

    create_xmp(
        params
    )

    # --------------------------------------------------------
    # INFORMACIÓN
    # --------------------------------------------------------

    print()
    print("DECISIÓN PHOTOIA")
    print("-" * 60)

    print(
        f"PHOTOIA contrast : "
        f"{photoia_contrast:.3f}"
    )

    print()
    print("PRUEBA FORZADA")
    print("-" * 60)

    print(
        f"Sigmoid Darktable: "
        f"{sigmoid_value:.3f}"
    )

    print()
    print("XMP GENERADO")
    print("-" * 60)

    print(
        f"{XMP_FILE}"
    )

    print()
    print("METADATOS DARKTABLE")
    print("-" * 60)

    print(
        "xmp_version          : 4"
    )

    print(
        "raw_params           : 0"
    )

    print(
        "auto_presets_applied : 0"
    )

    print(
        "history_end          : 0"
    )

    print(
        "iop_order_version    : 2"
    )

    print()
    print("VALIDACIÓN")
    print("-" * 60)

    print(
        f"params hex chars : "
        f"{len(params)}"
    )

    print(
        f"params bytes     : "
        f"{len(params) // 2}"
    )

    print(
        f"blendop chars    : "
        f"{len(BLENDOP_PARAMS)}"
    )

    print()
    print("RAW modificado     : NO")
    print("Darktable ejecutado: NO")

    print()
    print("=" * 60)
    print("XMP GENERADO CORRECTAMENTE")
    print("=" * 60)


if __name__ == "__main__":
    main()