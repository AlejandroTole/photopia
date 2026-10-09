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
- [Darktable](https://www.darktable.org/) (requerido para ejecutar el modo batch y renderizar RAW)
- [Ollama](https://ollama.ai/) con modelos de visión compatibles (ej. Qwen2-VL, LLaVA)

## Modo batch

Coloca fotos RAW en `fotos para editar/` y ejecuta `python photoia.py`. Cada foto usa
exclusivamente su propio sidecar (`<foto>.NEF.xmp`, o la extensión RAW correspondiente);
los sidecars sin una foto asociada se anuncian en consola y se ignoran. Si falta el
sidecar, PHOTOIA crea uno desde `templates/base.NEF.xmp`, inicializa el balance de
blancos con los valores as-shot de la cámara y fija la exposición inicial en 0 EV.
Los JPEG se guardan en `resultados/` como `<foto>_editado.jpg`.
