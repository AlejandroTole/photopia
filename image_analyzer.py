import rawpy
import numpy as np
import json
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

IMAGE_FILE = "_DSC2125.NEF"
OUTPUT_FILE = "image_analysis.json"

GRID_ROWS = 4
GRID_COLS = 4


# ============================================================
# FUNCIONES GENERALES
# ============================================================

def percentile(values, p):
    return float(np.percentile(values, p))


def safe_mean(values):
    if values.size == 0:
        return 0.0
    return float(np.mean(values))


def safe_median(values):
    if values.size == 0:
        return 0.0
    return float(np.median(values))


# ============================================================
# RAW SENSOR
# ============================================================

def build_black_level_map(raw):
    raw_pattern = raw.raw_pattern
    black_levels = np.array(
        raw.black_level_per_channel,
        dtype=np.float32
    )

    h, w = raw.raw_image_visible.shape

    black_map = np.zeros((h, w), dtype=np.float32)

    for y in range(h):
        for x in range(w):
            channel = raw_pattern[y % 2, x % 2]
            black_map[y, x] = black_levels[channel]

    return black_map


def analyze_raw_sensor(raw):
    raw_data = raw.raw_image_visible.astype(np.float32)

    black_map = build_black_level_map(raw)

    white_level = float(raw.white_level)

    denominator = white_level - black_map

    sensor_signal = (
        raw_data - black_map
    ) / denominator

    sensor_signal = np.clip(
        sensor_signal,
        0.0,
        1.0
    )

    flat = sensor_signal.ravel()

    shadow_mask = flat <= 0.01
    highlight_mask = flat >= 0.995

    result = {
        "resolution": {
            "width": int(raw_data.shape[1]),
            "height": int(raw_data.shape[0])
        },

        "black_level_per_channel": [
            float(x)
            for x in raw.black_level_per_channel
        ],

        "white_level": white_level,

        "color_description": str(raw.color_desc),

        "raw_pattern": raw.raw_pattern.tolist(),

        "statistics": {
            "mean": safe_mean(flat),
            "median": safe_median(flat),
            "p01": percentile(flat, 1),
            "p05": percentile(flat, 5),
            "p95": percentile(flat, 95),
            "p99": percentile(flat, 99)
        },

        "clipping": {
            "shadow_percent": float(
                np.mean(shadow_mask) * 100
            ),

            "highlight_percent": float(
                np.mean(highlight_mask) * 100
            )
        }
    }

    shadow_clip = result["clipping"]["shadow_percent"]
    highlight_clip = result["clipping"]["highlight_percent"]

    if highlight_clip >= 1.0:
        warning = "SIGNIFICANT_SENSOR_HIGHLIGHT_CLIPPING"

    elif shadow_clip >= 30.0:
        warning = "HIGH_RAW_SHADOW_CLIPPING"

    else:
        warning = "NO_SIGNIFICANT_SENSOR_CLIPPING"

    result["warning"] = warning

    return sensor_signal, result


# ============================================================
# ANÁLISIS ESPACIAL RAW
# ============================================================

def analyze_region(data):

    flat = data.ravel()

    shadow = float(
        np.mean(flat <= 0.01) * 100
    )

    highlight = float(
        np.mean(flat >= 0.995) * 100
    )

    mean_value = safe_mean(flat)

    if highlight >= 5:
        classification = "HIGHLIGHT_HEAVY"

    elif shadow >= 50 and mean_value < 0.08:
        classification = "VERY_DARK"

    elif shadow >= 25 and mean_value < 0.15:
        classification = "DARK"

    elif mean_value < 0.20:
        classification = "LOW_MID"

    elif mean_value > 0.65:
        classification = "HIGH_MID"

    else:
        classification = "NORMAL"

    return {
        "mean": mean_value,
        "median": safe_median(flat),
        "p01": percentile(flat, 1),
        "p05": percentile(flat, 5),
        "p25": percentile(flat, 25),
        "p50": percentile(flat, 50),
        "p75": percentile(flat, 75),
        "p95": percentile(flat, 95),
        "p99": percentile(flat, 99),

        "shadow_clipping_percent": shadow,
        "highlight_clipping_percent": highlight,

        "classification": classification
    }


def analyze_spatial_raw(sensor_signal):

    h, w = sensor_signal.shape

    regions = []

    region_height = h // GRID_ROWS
    region_width = w // GRID_COLS

    for row in range(GRID_ROWS):

        for col in range(GRID_COLS):

            y1 = row * region_height
            y2 = (
                (row + 1) * region_height
                if row < GRID_ROWS - 1
                else h
            )

            x1 = col * region_width
            x2 = (
                (col + 1) * region_width
                if col < GRID_COLS - 1
                else w
            )

            region = sensor_signal[
                y1:y2,
                x1:x2
            ]

            stats = analyze_region(region)

            stats["row"] = row
            stats["col"] = col

            regions.append(stats)

    return regions


def summarize_spatial_regions(regions):

    classifications = {}

    for region in regions:

        classification = region["classification"]

        classifications[classification] = (
            classifications.get(classification, 0) + 1
        )

    means = [
        region["mean"]
        for region in regions
    ]

    return {
        "region_count": len(regions),

        "darkest_region_mean": float(
            min(means)
        ),

        "brightest_region_mean": float(
            max(means)
        ),

        "mean_region_luminance": float(
            np.mean(means)
        ),

        "classification_counts": classifications,

        "average_shadow_clipping_percent": float(
            np.mean([
                region["shadow_clipping_percent"]
                for region in regions
            ])
        ),

        "average_highlight_clipping_percent": float(
            np.mean([
                region["highlight_clipping_percent"]
                for region in regions
            ])
        )
    }


# ============================================================
# RGB PROCESADO
# ============================================================

def analyze_rgb(rgb):

    rgb_float = rgb.astype(np.float32) / 255.0

    r = rgb_float[:, :, 0]
    g = rgb_float[:, :, 1]
    b = rgb_float[:, :, 2]

    luminance = (
        0.2126 * r +
        0.7152 * g +
        0.0722 * b
    )

    flat_lum = luminance.ravel()

    shadow_mask = flat_lum <= 0.01
    highlight_mask = flat_lum >= 0.99

    mean_r = safe_mean(r.ravel())
    mean_g = safe_mean(g.ravel())
    mean_b = safe_mean(b.ravel())

    channel_average = (
        mean_r +
        mean_g +
        mean_b
    ) / 3.0

    red_difference = mean_r - channel_average
    green_difference = mean_g - channel_average
    blue_difference = mean_b - channel_average

    differences = {
        "RED": abs(red_difference),
        "GREEN": abs(green_difference),
        "BLUE": abs(blue_difference)
    }

    strongest_cast = max(
        differences,
        key=differences.get
    )

    return {
        "resolution": {
            "width": int(rgb.shape[1]),
            "height": int(rgb.shape[0])
        },

        "luminance": {
            "mean": safe_mean(flat_lum),
            "median": safe_median(flat_lum),
            "p01": percentile(flat_lum, 1),
            "p05": percentile(flat_lum, 5),
            "p95": percentile(flat_lum, 95),
            "p99": percentile(flat_lum, 99)
        },

        "clipping": {
            "shadow_percent": float(
                np.mean(shadow_mask) * 100
            ),

            "highlight_percent": float(
                np.mean(highlight_mask) * 100
            )
        },

        "channels": {
            "red_mean": mean_r,
            "green_mean": mean_g,
            "blue_mean": mean_b,

            "red_difference": float(red_difference),
            "green_difference": float(green_difference),
            "blue_difference": float(blue_difference)
        },

        "color_cast": strongest_cast,

        "green_dominance": float(
            mean_g - ((mean_r + mean_b) / 2.0)
        ),

        "luminance_array": luminance
    }


# ============================================================
# CLASIFICACIÓN RGB ESPACIAL
# ============================================================

def classify_rgb_region(mean_value, shadow, highlight):

    if highlight >= 5:
        return "HIGHLIGHT_HEAVY"

    elif shadow >= 50 and mean_value < 0.08:
        return "VERY_DARK"

    elif shadow >= 25 and mean_value < 0.18:
        return "DARK"

    elif mean_value < 0.30:
        return "LOW_MID"

    elif mean_value > 0.75:
        return "HIGH_MID"

    else:
        return "NORMAL"


# ============================================================
# RGB ESPACIAL DE LUMINANCIA
# ============================================================

def analyze_spatial_rgb(luminance):

    h, w = luminance.shape

    regions = []

    region_height = h // GRID_ROWS
    region_width = w // GRID_COLS

    for row in range(GRID_ROWS):

        for col in range(GRID_COLS):

            y1 = row * region_height
            y2 = (
                (row + 1) * region_height
                if row < GRID_ROWS - 1
                else h
            )

            x1 = col * region_width
            x2 = (
                (col + 1) * region_width
                if col < GRID_COLS - 1
                else w
            )

            region = luminance[
                y1:y2,
                x1:x2
            ]

            flat = region.ravel()

            mean_value = safe_mean(flat)

            shadow = float(
                np.mean(flat <= 0.01) * 100
            )

            highlight = float(
                np.mean(flat >= 0.99) * 100
            )

            classification = classify_rgb_region(
                mean_value,
                shadow,
                highlight
            )

            regions.append({
                "row": row,
                "col": col,

                "mean": mean_value,
                "median": safe_median(flat),

                "p01": percentile(flat, 1),
                "p05": percentile(flat, 5),
                "p25": percentile(flat, 25),
                "p50": percentile(flat, 50),
                "p75": percentile(flat, 75),
                "p95": percentile(flat, 95),
                "p99": percentile(flat, 99),

                "shadow_clipping_percent": shadow,
                "highlight_clipping_percent": highlight,

                "classification": classification
            })

    return regions


def summarize_spatial_rgb(regions):

    classifications = {}

    for region in regions:

        classification = region["classification"]

        classifications[classification] = (
            classifications.get(classification, 0) + 1
        )

    means = [
        region["mean"]
        for region in regions
    ]

    return {
        "region_count": len(regions),

        "darkest_region_mean": float(
            min(means)
        ),

        "brightest_region_mean": float(
            max(means)
        ),

        "mean_region_luminance": float(
            np.mean(means)
        ),

        "classification_counts": classifications
    }


# ============================================================
# NUEVO: ANÁLISIS ESPACIAL DE COLOR
# ============================================================

def analyze_spatial_color(rgb):

    rgb_float = rgb.astype(np.float32) / 255.0

    h, w, _ = rgb_float.shape

    regions = []

    region_height = h // GRID_ROWS
    region_width = w // GRID_COLS

    for row in range(GRID_ROWS):

        for col in range(GRID_COLS):

            y1 = row * region_height
            y2 = (
                (row + 1) * region_height
                if row < GRID_ROWS - 1
                else h
            )

            x1 = col * region_width
            x2 = (
                (col + 1) * region_width
                if col < GRID_COLS - 1
                else w
            )

            region = rgb_float[
                y1:y2,
                x1:x2
            ]

            r = region[:, :, 0]
            g = region[:, :, 1]
            b = region[:, :, 2]

            mean_r = safe_mean(r.ravel())
            mean_g = safe_mean(g.ravel())
            mean_b = safe_mean(b.ravel())

            average_rb = (
                mean_r +
                mean_b
            ) / 2.0

            green_dominance = (
                mean_g - average_rb
            )

            channel_mean = (
                mean_r +
                mean_g +
                mean_b
            ) / 3.0

            green_relative = (
                green_dominance /
                max(channel_mean, 0.001)
            )

            red_dominance = (
                mean_r -
                ((mean_g + mean_b) / 2.0)
            )

            blue_dominance = (
                mean_b -
                ((mean_r + mean_g) / 2.0)
            )

            if green_dominance >= 0.06:
                color_class = "GREEN_DOMINANT"

            elif red_dominance >= 0.06:
                color_class = "RED_DOMINANT"

            elif blue_dominance >= 0.06:
                color_class = "BLUE_DOMINANT"

            else:
                color_class = "BALANCED"

            regions.append({
                "row": row,
                "col": col,

                "red_mean": mean_r,
                "green_mean": mean_g,
                "blue_mean": mean_b,

                "green_dominance": float(
                    green_dominance
                ),

                "green_relative": float(
                    green_relative
                ),

                "red_dominance": float(
                    red_dominance
                ),

                "blue_dominance": float(
                    blue_dominance
                ),

                "color_classification": color_class
            })

    return regions


def summarize_spatial_color(regions):

    green_values = [
        r["green_dominance"]
        for r in regions
    ]

    red_values = [
        r["red_dominance"]
        for r in regions
    ]

    blue_values = [
        r["blue_dominance"]
        for r in regions
    ]

    green_regions = [
        r for r in regions
        if r["color_classification"] == "GREEN_DOMINANT"
    ]

    red_regions = [
        r for r in regions
        if r["color_classification"] == "RED_DOMINANT"
    ]

    blue_regions = [
        r for r in regions
        if r["color_classification"] == "BLUE_DOMINANT"
    ]

    balanced_regions = [
        r for r in regions
        if r["color_classification"] == "BALANCED"
    ]

    mean_green = float(
        np.mean(green_values)
    )

    std_green = float(
        np.std(green_values)
    )

    mean_red = float(
        np.mean(red_values)
    )

    mean_blue = float(
        np.mean(blue_values)
    )

    # --------------------------------------------------------
    # Uniformidad del verde
    # --------------------------------------------------------

    green_fraction = (
        len(green_regions) /
        len(regions)
    )

    if green_fraction >= 0.75 and std_green < 0.025:
        green_distribution = "GLOBAL_UNIFORM"

    elif green_fraction >= 0.75:
        green_distribution = "GLOBAL_VARIABLE"

    elif green_fraction >= 0.40:
        green_distribution = "WIDESPREAD"

    elif green_fraction > 0:
        green_distribution = "LOCALIZED"

    else:
        green_distribution = "NONE"

    # --------------------------------------------------------
    # Posible dominante de WB
    # --------------------------------------------------------

    possible_global_green_cast = (
        green_fraction >= 0.75
        and mean_green >= 0.06
        and std_green < 0.035
    )

    possible_global_red_cast = (
        len(red_regions) / len(regions) >= 0.75
        and mean_red >= 0.06
    )

    possible_global_blue_cast = (
        len(blue_regions) / len(regions) >= 0.75
        and mean_blue >= 0.06
    )

    return {
        "region_count": len(regions),

        "mean_green_dominance": mean_green,

        "green_dominance_std": std_green,

        "mean_red_dominance": mean_red,

        "mean_blue_dominance": mean_blue,

        "green_dominant_regions": len(
            green_regions
        ),

        "red_dominant_regions": len(
            red_regions
        ),

        "blue_dominant_regions": len(
            blue_regions
        ),

        "balanced_regions": len(
            balanced_regions
        ),

        "green_dominant_fraction": float(
            green_fraction
        ),

        "green_distribution": green_distribution,

        "possible_global_green_cast": bool(
            possible_global_green_cast
        ),

        "possible_global_red_cast": bool(
            possible_global_red_cast
        ),

        "possible_global_blue_cast": bool(
            possible_global_blue_cast
        )
    }


# ============================================================
# MAIN
# ============================================================

def main():

    image_path = Path(IMAGE_FILE)

    if not image_path.exists():

        print(
            f"ERROR: No se encontró "
            f"{image_path.resolve()}"
        )

        return

    print("=" * 60)
    print("PHOTOIA - IMAGE ANALYZER")
    print("=" * 60)

    print(f"Fotografía: {IMAGE_FILE}")
    print()

    print("Leyendo RAW...")

    with rawpy.imread(str(image_path)) as raw:

        # ----------------------------------------------------
        # RAW SENSOR
        # ----------------------------------------------------

        sensor_signal, raw_analysis = (
            analyze_raw_sensor(raw)
        )

        print()
        print(
            "Analizando distribución espacial RAW..."
        )

        raw_regions = analyze_spatial_raw(
            sensor_signal
        )

        raw_spatial_summary = (
            summarize_spatial_regions(
                raw_regions
            )
        )

        # ----------------------------------------------------
        # RGB
        # ----------------------------------------------------

        print("Procesando RGB...")

        rgb = raw.postprocess(
            use_camera_wb=True,
            half_size=True,
            output_bps=8,
            no_auto_bright=False
        )

    print(
        f"Imagen RGB procesada: {rgb.shape}"
    )

    # --------------------------------------------------------
    # RGB GLOBAL
    # --------------------------------------------------------

    rgb_analysis = analyze_rgb(rgb)

    luminance = rgb_analysis.pop(
        "luminance_array"
    )

    # --------------------------------------------------------
    # RGB ESPACIAL
    # --------------------------------------------------------

    print()
    print(
        "Analizando distribución espacial RGB..."
    )

    rgb_regions = analyze_spatial_rgb(
        luminance
    )

    rgb_spatial_summary = (
        summarize_spatial_rgb(
            rgb_regions
        )
    )

    # --------------------------------------------------------
    # COLOR ESPACIAL
    # --------------------------------------------------------

    print()
    print(
        "Analizando distribución espacial del color..."
    )

    color_regions = analyze_spatial_color(
        rgb
    )

    color_spatial_summary = (
        summarize_spatial_color(
            color_regions
        )
    )

    # ========================================================
    # RESULTADO FINAL
    # ========================================================

    result = {

        "image": IMAGE_FILE,

        "raw_sensor": {

            **raw_analysis,

            "spatial_analysis": {

                "grid": {
                    "rows": GRID_ROWS,
                    "cols": GRID_COLS
                },

                "summary": raw_spatial_summary,

                "regions": raw_regions
            }
        },

        "rgb_rendered": {

            **rgb_analysis,

            "spatial_analysis": {

                "grid": {
                    "rows": GRID_ROWS,
                    "cols": GRID_COLS
                },

                "summary": rgb_spatial_summary,

                "regions": rgb_regions
            },

            "spatial_color_analysis": {

                "summary": color_spatial_summary,

                "regions": color_regions
            }
        }
    }

    # --------------------------------------------------------
    # GUARDAR JSON
    # --------------------------------------------------------

    output_path = Path(OUTPUT_FILE)

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            result,
            f,
            indent=2,
            ensure_ascii=False
        )

    # ========================================================
    # CONSOLA
    # ========================================================

    print()
    print("=" * 60)
    print("ANALISIS RAW")
    print("=" * 60)

    print(
        f"Resolución sensor: "
        f"{raw_analysis['resolution']['width']} x "
        f"{raw_analysis['resolution']['height']}"
    )

    print(
        f"Black levels: "
        f"{raw_analysis['black_level_per_channel']}"
    )

    print(
        f"White level: "
        f"{raw_analysis['white_level']}"
    )

    print(
        f"RAW mean: "
        f"{raw_analysis['statistics']['mean']:.6f}"
    )

    print(
        f"RAW median: "
        f"{raw_analysis['statistics']['median']:.6f}"
    )

    print(
        f"RAW P01: "
        f"{raw_analysis['statistics']['p01']:.6f}"
    )

    print(
        f"RAW P99: "
        f"{raw_analysis['statistics']['p99']:.6f}"
    )

    print(
        f"RAW shadow clipping: "
        f"{raw_analysis['clipping']['shadow_percent']:.4f}%"
    )

    print(
        f"RAW highlight clipping: "
        f"{raw_analysis['clipping']['highlight_percent']:.4f}%"
    )

    print(
        f"RAW warning: "
        f"{raw_analysis['warning']}"
    )

    # ========================================================
    # RAW ESPACIAL
    # ========================================================

    print()
    print("=" * 60)
    print("ANALISIS ESPACIAL RAW")
    print("=" * 60)

    print(
        f"Regiones: "
        f"{raw_spatial_summary['region_count']}"
    )

    print(
        f"Región más oscura: "
        f"{raw_spatial_summary['darkest_region_mean']:.6f}"
    )

    print(
        f"Región más clara: "
        f"{raw_spatial_summary['brightest_region_mean']:.6f}"
    )

    print("Clasificación de regiones:")

    for key, value in sorted(
        raw_spatial_summary[
            "classification_counts"
        ].items()
    ):

        print(
            f"  {key}: {value}"
        )

    # ========================================================
    # RGB
    # ========================================================

    print()
    print("=" * 60)
    print("ANALISIS RGB")
    print("=" * 60)

    print(
        f"RGB mean luminance: "
        f"{rgb_analysis['luminance']['mean']:.6f}"
    )

    print(
        f"RGB median luminance: "
        f"{rgb_analysis['luminance']['median']:.6f}"
    )

    print(
        f"RGB P01: "
        f"{rgb_analysis['luminance']['p01']:.6f}"
    )

    print(
        f"RGB P99: "
        f"{rgb_analysis['luminance']['p99']:.6f}"
    )

    print(
        f"RGB shadow clipping: "
        f"{rgb_analysis['clipping']['shadow_percent']:.4f}%"
    )

    print(
        f"RGB highlight clipping: "
        f"{rgb_analysis['clipping']['highlight_percent']:.4f}%"
    )

    print(
        f"RGB color cast: "
        f"{rgb_analysis['color_cast']}"
    )

    print(
        f"RGB green difference: "
        f"{rgb_analysis['channels']['green_difference']:.6f}"
    )

    # ========================================================
    # RGB ESPACIAL
    # ========================================================

    print()
    print("=" * 60)
    print("ANALISIS ESPACIAL RGB")
    print("=" * 60)

    print(
        f"Regiones: "
        f"{rgb_spatial_summary['region_count']}"
    )

    print(
        f"Región más oscura: "
        f"{rgb_spatial_summary['darkest_region_mean']:.6f}"
    )

    print(
        f"Región más clara: "
        f"{rgb_spatial_summary['brightest_region_mean']:.6f}"
    )

    print("Clasificación de regiones:")

    for key, value in sorted(
        rgb_spatial_summary[
            "classification_counts"
        ].items()
    ):

        print(
            f"  {key}: {value}"
        )

    # ========================================================
    # COLOR ESPACIAL
    # ========================================================

    print()
    print("=" * 60)
    print("ANALISIS ESPACIAL DEL COLOR")
    print("=" * 60)

    print(
        f"Dominancia verde promedio: "
        f"{color_spatial_summary['mean_green_dominance']:.6f}"
    )

    print(
        f"Variación de dominancia verde: "
        f"{color_spatial_summary['green_dominance_std']:.6f}"
    )

    print(
        f"Regiones verdes: "
        f"{color_spatial_summary['green_dominant_regions']}/"
        f"{color_spatial_summary['region_count']}"
    )

    print(
        f"Regiones rojas: "
        f"{color_spatial_summary['red_dominant_regions']}/"
        f"{color_spatial_summary['region_count']}"
    )

    print(
        f"Regiones azules: "
        f"{color_spatial_summary['blue_dominant_regions']}/"
        f"{color_spatial_summary['region_count']}"
    )

    print(
        f"Regiones balanceadas: "
        f"{color_spatial_summary['balanced_regions']}/"
        f"{color_spatial_summary['region_count']}"
    )

    print(
        f"Distribución verde: "
        f"{color_spatial_summary['green_distribution']}"
    )

    print(
        f"Posible dominante verde global: "
        f"{color_spatial_summary['possible_global_green_cast']}"
    )

    print(
        f"Posible dominante roja global: "
        f"{color_spatial_summary['possible_global_red_cast']}"
    )

    print(
        f"Posible dominante azul global: "
        f"{color_spatial_summary['possible_global_blue_cast']}"
    )

    # ========================================================
    # GUARDADO
    # ========================================================

    print()
    print("=" * 60)
    print("ANALISIS GUARDADO")
    print("=" * 60)

    print(
        f"Archivo: "
        f"{output_path.resolve()}"
    )

    print()
    print("=" * 60)
    print("PHOTOIA - IMAGE ANALYZER TERMINADO")
    print("=" * 60)


if __name__ == "__main__":
    main()