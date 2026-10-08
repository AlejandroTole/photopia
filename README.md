# Photopia (PHOTOIA)

Sistema automatizado de edición de fotografía RAW asistido por Inteligencia Artificial para **Darktable**.

## Descripción

Photopia analiza imágenes fotográficas en formato RAW utilizando modelos de visión (como Qwen y LLaVA mediante Ollama) para determinar decisiones de revelado digital y generar o modificar archivos `.xmp` de Darktable automáticamente, con especial énfasis en el módulo de mapeo tonal **Sigmoid**.

## Componentes principales

- **Análisis de imagen**: Evaluación de histograma, balance, contraste y contenido visual mediante modelos de visión (`analyze/image_analyzer.py`, `test_ollama_vision_api.py`).
- **Planificación de edición**: Generación y validación de planes de revelado fotográfico (`qwen_edit_planner.py`, `validate_edit_plan.py`, `decision_editor.py`).
- **Mapeo tonal Sigmoid**: Lectura, cálculo, codificación y empaquetado de parámetros para el módulo Sigmoid de Darktable (`sigmoid_builder.py`, `sigmoid_writer.py`, `sigmoid_converter.py`, `parse_sigmoid.py`).
- **Generación de XMP**: Creación y actualización de sidecars `.xmp` compatibles con Darktable (`darktable_xmp_generator.py`).
- **Previsualización**: Generación de previsualizaciones y comparación de parámetros (`preview_engine.py`, `compare_sigmoids.py`).

## Requisitos

- Python 3.10+
- [Darktable](https://www.darktable.org/) (opcional, para renderizado y procesamiento de XMP)
- [Ollama](https://ollama.ai/) con modelos de visión compatibles (ej. Qwen2-VL, LLaVA)
