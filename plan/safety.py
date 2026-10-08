"""
PHOTOIA - Safety Engine
Safety rules and parameter guardrails extracted from decision_editor.py.
Enforces conservative adjustments, protects highlights/shadows, and prevents false color corrections.
"""
from typing import Dict, Any, List, Tuple


def clamp(val: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, float(val)))


def sanitize_plan(
    proposed: Dict[str, Any],
    analysis: Dict[str, Any],
    limits: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Validates and sanitizes parameter proposals from vision planner according to safety rules.
    Returns: (sanitized_dict, safety_notes)
    """
    sanitized = {}
    notes = []

    # 1. Exposure Safety
    exp_limits = limits.get("exposure_ev", (-1.0, 1.0))
    raw_sensor = analysis.get("raw_sensor", {})
    raw_stats = raw_sensor.get("statistics", {})
    raw_clip = raw_sensor.get("clipping", {})
    rgb_rendered = analysis.get("rgb_rendered", {})
    rgb_clip = rgb_rendered.get("clipping", {})

    proposed_ev = proposed.get("exposure", {}).get("ev", 0.0)
    orig_ev = proposed_ev

    # Rule: Highlight protection
    raw_hl_clip = raw_clip.get("highlight_percent", 0.0)
    rgb_hl_clip = rgb_clip.get("highlight_percent", 0.0)
    if (raw_hl_clip > 0.05 or rgb_hl_clip > 1.0) and proposed_ev > 0.2:
        proposed_ev = min(proposed_ev, 0.2)
        notes.append(f"Exposición recortada a +{proposed_ev:.2f} EV por riesgo de clipping en altas luces.")

    # Rule: Natural dark content check (do not over-boost low RAW values)
    raw_median = raw_stats.get("median", 0.05)
    if raw_median < 0.03 and proposed_ev > 0.7:
        proposed_ev = min(proposed_ev, 0.7)
        notes.append("Exposición limitada a +0.7 EV: contenido oscuro natural detectado en RAW.")

    # Clamp to configured global limits
    clamped_ev = clamp(proposed_ev, exp_limits[0], exp_limits[1])
    if clamped_ev != orig_ev and not notes:
        notes.append(f"Exposición limitada por rangos de seguridad: {orig_ev} -> {clamped_ev} EV")

    sanitized["exposure"] = {
        "ev": round(clamped_ev, 3),
        "black": clamp(proposed.get("exposure", {}).get("black", 0.0), -0.05, 0.05),
    }

    # 2. Sigmoid Safety
    sig_contrast_limits = limits.get("sigmoid_contrast", (0.8, 3.5))
    sig_skew_limits = limits.get("sigmoid_skew", (-0.6, 0.6))

    prop_contrast = proposed.get("sigmoid", {}).get("contrast", 1.5)
    clamped_contrast = clamp(prop_contrast, sig_contrast_limits[0], sig_contrast_limits[1])
    if clamped_contrast != prop_contrast:
        notes.append(f"Contraste Sigmoid ajustado a límites seguros: {prop_contrast} -> {clamped_contrast}")

    prop_skew = proposed.get("sigmoid", {}).get("skew", 0.0)
    clamped_skew = clamp(prop_skew, sig_skew_limits[0], sig_skew_limits[1])

    sanitized["sigmoid"] = {
        "contrast": round(clamped_contrast, 3),
        "skew": round(clamped_skew, 3),
        "target_white": clamp(proposed.get("sigmoid", {}).get("target_white", 100.0), 50.0, 200.0),
        "target_black": clamp(proposed.get("sigmoid", {}).get("target_black", 0.0152), 0.0, 1.0),
        "color_processing": proposed.get("sigmoid", {}).get("color_processing", "per channel"),
        "preserve_hue": clamp(proposed.get("sigmoid", {}).get("preserve_hue", 100.0), 0.0, 100.0),
    }

    # 3. White Balance Safety (Vegetation Rule)
    wb_limits = limits.get("temperature_delta_ratio", (-0.15, 0.15))
    color_spatial = rgb_rendered.get("spatial_color_analysis", {}).get("summary", {})
    green_widespread = color_spatial.get("green_distribution") == "WIDESPREAD"
    possible_green_cast = color_spatial.get("possible_global_green_cast", False)

    prop_warmth = proposed.get("whitebalance", {}).get("warmth_shift", 0.0)
    clamped_warmth = clamp(prop_warmth, wb_limits[0], wb_limits[1])

    # If vegetation is widespread and no true global cast, prevent aggressive tint shifts
    if green_widespread and not possible_green_cast:
        notes.append("Regla de vegetación activa: vegetación detectada, preservando balance de color sin forzar compensación verde/magenta.")

    sanitized["whitebalance"] = {
        "warmth_shift": round(clamped_warmth, 3),
    }

    return sanitized, notes
