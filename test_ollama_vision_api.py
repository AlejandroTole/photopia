import base64
import os
import requests


MODEL = "qwen2.5vl:32b"
IMAGE_FILE = "_DSC2125.JPG"
URL = "http://127.0.0.1:11434/api/chat"


print()
print("=" * 72)
print("PHOTOIA - OLLAMA VISION API TEST")
print("=" * 72)

if not os.path.exists(IMAGE_FILE):

    print()
    print("ERROR: No existe:")
    print(IMAGE_FILE)
    print()

    raise SystemExit(1)


with open(
    IMAGE_FILE,
    "rb"
) as f:

    image_base64 = base64.b64encode(
        f.read()
    ).decode("utf-8")


payload = {
    "model": MODEL,
    "stream": False,
    "messages": [
        {
            "role": "user",
            "content": (
                "Describe brevemente esta "
                "fotografía. Responde en una "
                "sola frase."
            ),
            "images": [
                image_base64
            ],
        }
    ],
}


print()
print(f"Modelo: {MODEL}")
print(f"Imagen: {IMAGE_FILE}")
print()
print("Enviando solicitud...")

try:

    response = requests.post(
        URL,
        json=payload,
        timeout=300,
    )

except requests.exceptions.ConnectionError as error:

    print()
    print("ERROR DE CONEXION")
    print(error)
    raise SystemExit(1)

except requests.exceptions.Timeout:

    print()
    print("ERROR: timeout.")
    raise SystemExit(1)


print()
print("=" * 72)
print(f"HTTP STATUS: {response.status_code}")
print("=" * 72)

print()
print("RESPUESTA RAW DE OLLAMA:")
print("-" * 72)

print(response.text)

print()

if response.ok:

    try:

        data = response.json()

        print("=" * 72)
        print("RESPUESTA INTERPRETADA")
        print("=" * 72)

        print()
        print(
            data.get(
                "message",
                {}
            ).get(
                "content",
                "(sin message.content)"
            )
        )

    except Exception as error:

        print()
        print(
            "No se pudo interpretar JSON:"
        )
        print(error)

print()