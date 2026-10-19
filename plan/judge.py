"""
PHOTOIA - Vision Judge
Evalúa el render final con el mismo cliente de visión del planner (Ollama,
qwen2.5vl:7b) y cierra el loop render -> juez -> re-render.

El juez solo PROPONE ajustes relativos (deltas) para los 3 writers existentes
(exposure, sigmoid, whitebalance); es responsabilidad del llamador pasar
cualquier ajuste propuesto por sanitize_plan antes de aplicarlo.
"""
from pathlib import Path
import json
import re
from typing import Any, Dict, Optional

import requests

from config import load_config
from plan.planner import encode_image_for_vlm

# Límites de seguridad de los deltas que el juez puede proponer por iteración.
# Son más conservadores que los límites globales de sanitize_plan porque
# representan una corrección fina sobre un plan ya aplicado.
ADJUSTMENT_BOUNDS = {
    "exposure_ev": 0.5,
    "sigmoid_contrast": 0.5,
    "sigmoid_skew": 0.3,
    "warmth_shift": 0.1,
    "vibrance": 0.2,
}

NEUTRAL_ADJUSTMENTS: Dict[str, float] = {key: 0.0 for key in ADJUSTMENT_BOUNDS}


def build_judge_prompt(has_reference: bool) -> str:
    if has_reference:
        reference_clause = (
            "La SEGUNDA imagen adjunta es el JPEG de cámara (referencia de punch "
            "de la Nikon); compara el render contra ella para calibrar contraste, "
            "color y nivel de detalle."
        )
    else:
        reference_clause = (
            "No hay JPEG de cámara de referencia disponible; evalúa el render de "
            "forma absoluta con criterio fotográfico profesional."
        )

    return f"""Eres el juez de calidad de PHOTOIA para renders de Darktable.
Evalúa la PRIMERA imagen adjunta (render final). {reference_clause}

CRITERIOS DE EVALUACIÓN:
1. Sin artefactos: dominantes de color, negros aplastados sin detalle, halos de
   contraste local, grano/ruido excesivo.
2. Look natural y balanceado: sin saturación falsa ni aspecto HDR; tonos de piel
   y vegetación creíbles.
3. Punch (contraste, color y detalle) al nivel del JPEG de cámara, cuando hay
   referencia disponible.
4. Viveza de color ("Auto" de Lightroom): colores vivos con punch pero creíbles;
   señala tanto imágenes apagadas/grises que necesitan más viveza como colores
   ya sobre-saturados o con aspecto artificial.
5. Altas luces sin quemar (sin clipping relevante).

Responde ÚNICAMENTE un objeto JSON válido con esta estructura exacta:
```json
{{
  "accept": true,
  "score": 85,
  "issues": ["lista breve de problemas detectados; vacía si no hay"],
  "adjustments": {{
    "exposure_ev": 0.0,
    "sigmoid_contrast": 0.0,
    "sigmoid_skew": 0.0,
    "warmth_shift": 0.0,
    "vibrance": 0.0
  }},
  "reasoning": "Breve explicación de 1-2 frases"
}}
```
Reglas para "adjustments": son DELTAS conservadores (no valores absolutos) que
se sumarán al plan ya aplicado, usando únicamente los 4 writers existentes
(exposure, sigmoid, whitebalance, saturación/viveza vía colorbalancergb). Si
accept es true, deja todos los adjustments en 0.0. Si accept es false, propone
el delta mínimo necesario para corregir los issues detectados, dentro de estos
rangos: exposure_ev entre -0.5 y 0.5, sigmoid_contrast entre -0.5 y 0.5,
sigmoid_skew entre -0.3 y 0.3, warmth_shift entre -0.1 y 0.1, vibrance entre
-0.2 y 0.2 (positivo = más viveza/punch, negativo = reduce saturación si ya es
falsa o excesiva)."""


def _clamp_score(value: Any) -> int:
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        score = 0
    return max(0, min(100, score))


def _clamp_adjustment(value: Any, bound: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(-bound, min(bound, number))


def _fallback_result(reason: str) -> Dict[str, Any]:
    return {
        "accept": True,
        "score": 70,
        "issues": [f"Juez no disponible; se acepta el render por defecto: {reason}"],
        "adjustments": dict(NEUTRAL_ADJUSTMENTS),
        "reasoning": "",
    }


def judge_render(
    render_path: Path,
    camera_jpg: Optional[Path] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evalúa un render con el modelo de visión y devuelve un veredicto:
    {accept, score, issues, adjustments} donde adjustments solo contiene
    deltas para exposure_ev, sigmoid_contrast, sigmoid_skew y warmth_shift.
    Nunca aplica cambios; el llamador debe pasar los adjustments por
    sanitize_plan antes de usarlos con los writers.
    """
    render_path = Path(render_path)
    if not render_path.is_file():
        return _fallback_result(f"No se encontró el render: {render_path}")

    cfg = config if config is not None else load_config()
    models_cfg = cfg.get("models", {})
    model_name = models_cfg.get("judge", models_cfg.get("planner", "qwen2.5vl:7b"))
    ollama_url = models_cfg.get("ollama_url", "http://127.0.0.1:11434")

    has_reference = camera_jpg is not None and Path(camera_jpg).is_file()
    images = [encode_image_for_vlm(render_path, max_dimension=1024)]
    if has_reference:
        images.append(encode_image_for_vlm(Path(camera_jpg), max_dimension=1024))

    prompt = build_judge_prompt(has_reference)

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": images,
            }
        ],
        "stream": False,
        "options": {"temperature": 0.1},
    }

    try:
        response = requests.post(f"{ollama_url}/api/chat", json=payload, timeout=300)
        response.raise_for_status()
        data = response.json()
        raw_text = data.get("message", {}).get("content", "")
    except Exception as error:
        return _fallback_result(str(error))

    json_match = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, re.S)
    if not json_match:
        json_match = re.search(r"(\{.*\})", raw_text, re.S)

    parsed: Dict[str, Any] = {}
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
        except Exception:
            parsed = {}

    if not parsed:
        result = _fallback_result("Respuesta del modelo sin JSON estructurado.")
        result["issues"].append(f"Respuesta cruda: {raw_text[:200]}")
        return result

    accept = bool(parsed.get("accept", False))
    score = _clamp_score(parsed.get("score", 0))

    issues = parsed.get("issues", [])
    if not isinstance(issues, list):
        issues = [issues]
    issues = [str(item) for item in issues]

    raw_adjustments = parsed.get("adjustments", {})
    if not isinstance(raw_adjustments, dict):
        raw_adjustments = {}

    if accept:
        adjustments = dict(NEUTRAL_ADJUSTMENTS)
    else:
        adjustments = {
            key: _clamp_adjustment(raw_adjustments.get(key, 0.0), bound)
            for key, bound in ADJUSTMENT_BOUNDS.items()
        }

    return {
        "accept": accept,
        "score": score,
        "issues": issues,
        "adjustments": adjustments,
        "reasoning": str(parsed.get("reasoning", "")),
    }
