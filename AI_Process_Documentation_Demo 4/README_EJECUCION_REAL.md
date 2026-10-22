# AI Process Documentation — demo ejecutable con video REAL (5 min)

## Alcance real
Procesa un MP4 de ~5 minutos: extrae audio, transcribe con Azure OpenAI (o reutiliza VTT/JSON), selecciona capturas con OpenCV, envía paquetes de transcripción + imágenes al modelo multimodal, genera JSON con evidencias y produce PPTX con **recuadros editables** y DOCX. Si no hay evidencia de acciones, **no inventa pasos**. Los documentos siempre requieren aprobación humana.

### Modelos recomendados
- **Transcripción**: `gpt-4o-transcribe-diarize` (si el deployment existe en tu región). Ofrece segmentos y hablantes; confirmar el instructor y continuidad entre fragmentos. Si usas Teams, sube el VTT y se omite transcripción.
- **Interpretación visual**: `gpt-5.4-mini` con visión como punto de partida. Para evaluaciones complejas compara con `gpt-5.4` cambiando `AZURE_VISION_DEPLOYMENT`. Su disponibilidad, límites y costo dependen de región/deployment.
- **Visión determinista**: FFmpeg/OpenCV locales. El modelo no conoce eventos de clic exactos y la ubicación de botones es una hipótesis que se debe revisar.

## Ejecutar
1. Instala Python 3.11+, FFmpeg (Mac: `brew install ffmpeg`; Windows: `winget install Gyan.FFmpeg`).
2. `python -m venv .venv && source .venv/bin/activate` (Windows: `.venv\\Scripts\\activate`).
3. `pip install -r requirements-real.txt`.
4. `cp .env.example .env` y configura URL, API Key y nombres de deployments de Azure OpenAI.
5. `python web_real.py` y abre la URL que aparece en consola; carga un MP4 real de 5 minutos.
6. Alternativa CLI: `python run_real.py --video /ruta/demo.mp4 --rules "Tomar instrucciones del instructor y omitir preguntas"`.
7. Con transcripción de Teams: `python run_real.py --video /ruta/video.mp4 --transcript /ruta/reunion.vtt --speaker "Nombre instructor"`.

**Las credenciales nunca se incluyen en el ZIP.** Es necesario provisionar deployments reales y autorizar acceso; sin ellos la IA no producirá procedimientos. `--no-ai` verifica extracción y almacenamiento, no simula resultados de IA.

## Azure Blob Storage (opcional, implementado)
1. Crear una Storage Account con Blob; usar contenedores privados `raw`, `analysis`, `delivery` (el código los crea si la identidad tiene permisos).
2. En `.env`: `USE_AZURE_BLOB=true` y `AZURE_STORAGE_ACCOUNT_URL=https://...blob.core.windows.net`.
3. En desarrollo: `az login` y asignar rol `Storage Blob Data Contributor` a tu usuario. En Azure, asignar ese rol a la Managed Identity del backend. Alternativamente utilizar `AZURE_STORAGE_CONNECTION_STRING` únicamente en pruebas, almacenándola fuera del repositorio.
4. Los objetos se guardan bajo `raw/<project_id>/`, `analysis/<project_id>/`, `delivery/<project_id>/`. **Los originales no se sobreescriben**.
5. Esto es sincronización Blob desde un pipeline local, no aún una cola distribuida de Durable Functions. Para videos de horas, migrar a workers y orquestación asíncrona.

## Scripts y funciones
- `run_real.py`: entrada CLI; `main()` recibe parámetros y dispara el análisis.
- `web_real.py`: UI Gradio **sólo demo del backend**; `process()` orquesta llamada desde el navegador.
- `real_pipeline.py`: núcleo de ejecución; cada función lleva docstring. `split_audio()` extrae bloques, `transcribe_audio()` usa el deployment de audio, `infer_steps()` analiza imágenes y texto, `save_artifact()` conserva los archivos en Blob opcional, `run_pipeline()` genera archivos finales.
- `poc_core.py`: extracción de cambios y generadores PPTX/DOCX reutilizados, con rectángulos **nativos** de PowerPoint.
- `transcript_ingestion.py`: parseo de Teams VTT/JSON; no requiere Video Indexer.

## Limitaciones transparentes
- El backend acepta transcripciones Teams suministradas en VTT; **la integración automatizada Microsoft Graph no está conectada a credenciales de un tenant en esta demo** (hay adaptador existente en `graph_teams.py`).
- No prueba tiempos de video de cinco horas ni Durable Functions. Máximo configurable recomendado en demo: seis minutos.
- Frames se seleccionan mediante diferencias visuales; acciones rápidas pueden perderse, y boxes inferidos pueden ser imprecisos.
- Si una grabación contiene credenciales o datos personales, deben anonimizarse **antes** de enviarlos al modelo. Este MVP no hace enmascaramiento automático verificable.
- La transcripción sin atribución real no permite filtrar al instructor sin riesgo de excluir contenido relevante.
- Las validaciones de tipo/estructura de salida LLM son básicas; un despliegue empresarial requiere schema estricto, validación por evidencia y evaluación.

## Diagrama de arquitectura
`diagrams/arquitectura_demo_openai.mmd` describe exclusivamente el pipeline Azure OpenAI y Blob Storage.
