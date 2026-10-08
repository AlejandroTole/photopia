"""
PHOTOIA - Vision Planner (v2)
Calls Ollama (qwen2.5vl:7b) to propose editing parameters based on
the neutral baseline render and image analysis metrics.
"""
from pathlib import Path
import base64
import json
import re
from typing import Dict, Any, Tuple, Optional, List
from PIL import Image
import requests
import io

from plan.safety import sanitize_plan


def encode_image_for_vlm(image_path: Path, max_dimension: int = 1024) -> str:
    """
    Downscales image to max_dimension and returns base64 string for efficient VLM processing.
    """
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_dimension:
            scale = max_dimension / max(w, h)
            new_size = (int(w * scale), int(h * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")


def build_planner_prompt(analysis: Dict[str, Any]) -> str:
    raw_stats = analysis.get("raw_sensor", {}).get("statistics", {})
    raw_clip = analysis.get("raw_sensor", {}).get("clipping", {})
    rgb_stats = analysis.get("rgb_rendered", {}).get("luminance", {})
    rgb_clip = analysis.get("rgb_rendered", {}).get("clipping", {})
    color_summary = analysis.get("rgb_rendered", {}).get("spatial_color_analysis", {}).get("summary", {})

    metrics_summary = {
        "raw_mean": raw_stats.get("mean", 0.0),
        "raw_median": raw_stats.get("median", 0.0),
        "raw_shadow_clip_pct": raw_clip.get("shadow_percent", 0.0),
        "raw_highlight_clip_pct": raw_clip.get("highlight_percent", 0.0),
        "rgb_mean_luminance": rgb_stats.get("mean", 0.0),
        "rgb_median_luminance": rgb_stats.get("median", 0.0),
        "rgb_highlight_clip_pct": rgb_clip.get("highlight_percent", 0.0),
        "green_distribution": color_summary.get("green_distribution", "UNKNOWN"),
        "possible_green_cast": color_summary.get("possible_global_green_cast", False),
    }

    prompt = f"""Eres el planificador fotográfico de PHOTOIA para Darktable.
Analiza la imagen adjunta (render neutro baseline) junto con las siguientes métricas objetivas del sensor y del espacio de color:

MÉTRICAS:
{json.dumps(metrics_summary, indent=2)}

REGLAS DE REVELADO (Look profesional, natural y equilibrado):
1. Exposición (exposure EV):
   - Solo ajusta si es necesario (+0.1 a +0.7 si está subexpuesta, o 0.0 si es adecuada).
   - Evita quemar altas luces si rgb_highlight_clip_pct ya es relevante.
2. Curva tonal Sigmoid:
   - contrast: típicamente entre 1.2 y 2.2 (default 1.5). Si la escena es muy plana, sube a 1.6-1.8.
   - skew: entre -0.3 y 0.3. Negativo protege altas luces, positivo aclara sombras.
3. Balance de Blancos (whitebalance warmth_shift):
   - Ajuste sutil: entre -0.05 y +0.05 (positivo = más cálido, negativo = más frío).
   - Si la escena contiene vegetación (green_distribution WIDESPREAD), NO corrijas a magenta.
4. Conservadurismo:
   - Cambios pequeños y justificados. Nunca exagerar.

Responde ÚNICAMENTE un objeto JSON válido con la siguiente estructura exacta:
```json
{{
  "exposure": {{
    "ev": 0.3,
    "black": 0.0
  }},
  "sigmoid": {{
    "contrast": 1.6,
    "skew": -0.1
  }},
  "whitebalance": {{
    "warmth_shift": 0.0
  }},
  "reasoning": "Breve explicación técnica de 1-2 frases"
}}
```"""
    return prompt


def plan_edit(
    baseline_image_path: Path,
    analysis: Dict[str, Any],
    config: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Executes vision-based editing plan generation using Ollama.
    Returns: (sanitized_plan, safety_notes)
    """
    model_name = config.get("models", {}).get("planner", "qwen2.5vl:7b")
    ollama_url = config.get("models", {}).get("ollama_url", "http://127.0.0.1:11434")
    limits = config.get("limits", {})

    b64_img = encode_image_for_vlm(baseline_image_path, max_dimension=1024)
    prompt = build_planner_prompt(analysis)

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [b64_img],
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.2,
        },
    }

    try:
        response = requests.post(f"{ollama_url}/api/chat", json=payload, timeout=300)
        response.raise_for_status()
        data = response.json()
        raw_text = data.get("message", {}).get("content", "")
    except Exception as e:
        # Fallback to sensible neutral plan if model is unavailable
        raw_text = ""
        fallback_plan = {
            "exposure": {"ev": 0.3, "black": 0.0},
            "sigmoid": {"contrast": 1.5, "skew": 0.0},
            "whitebalance": {"warmth_shift": 0.0},
            "reasoning": f"Fallback automático debido a error con Ollama: {e}",
        }
        sanitized, notes = sanitize_plan(fallback_plan, analysis, limits)
        notes.append(f"ADVERTENCIA: Usando plan fallback seguro: {e}")
        return sanitized, notes

    # Extract JSON from model text
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, re.S)
    if not json_match:
        json_match = re.search(r"(\{.*\})", raw_text, re.S)

    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
        except Exception:
            parsed = {}
    else:
        parsed = {}

    if not parsed:
        parsed = {
            "exposure": {"ev": 0.2, "black": 0.0},
            "sigmoid": {"contrast": 1.5, "skew": 0.0},
            "whitebalance": {"warmth_shift": 0.0},
            "reasoning": "Plan neutro por defecto (respuesta de modelo no contenía JSON estructurado).",
        }

    sanitized, notes = sanitize_plan(parsed, analysis, limits)
    sanitized["reasoning"] = parsed.get("reasoning", "Ajuste equilibrado propuesto por modelo.")

    return sanitized, notes
