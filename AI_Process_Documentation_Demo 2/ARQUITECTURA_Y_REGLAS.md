# AI Process Documentation — Arquitectura actualizada v0.2

## Principio

**Dos rutas de entrada, un pipeline de interpretación, una fuente de datos y generadores comunes.** El usuario elige Teams o archivo externo; reutilizamos transcripciones ya disponibles para evitar análisis redundante. El frontend pertenece a otro equipo: solo nos comunicamos mediante API REST. `app.py` es una interfaz demostrativa de ingeniería, no el frontend de producción.

## Ruta A: Teams

1. El backend autorizado obtiene MP4 y VTT mediante Microsoft Graph, con permisos del tenant y del usuario organizador según la modalidad de permiso.
2. Parsea etiquetas de hablantes `<v ...>` y timestamps en `transcript_ingestion.py`. Si Teams solo entrega texto sin speakers, no inventa identidades ni filtra voz principal automáticamente.
3. Si falta transcripción, activa el proceso alternativo de indexación/transcripción con consentimiento y acceso autorizados.
4. FFmpeg/OpenCV recuperan fotogramas originales y cambios de pantalla. Se unen audio y evidencia temporal según una línea temporal revisable. Hay que calibrar desfase VTT vs MP4 en el MVP.

## Ruta B: MP4 externo

1. La API autoriza carga por bloques directamente a Blob (la PoC local permite cargar MP4 manualmente en Gradio).
2. Si el usuario proporciona VTT/JSON normalizado, reutilizarlo.
3. Si no, indexar video desde Blob usando Azure AI Video Indexer en un trabajo asíncrono (SAS de solo lectura de corta duración o identidad administrada según configuración). `video_indexer.py` contiene el adaptador; `azure_blob.py` realiza subida de MP4 con identidad de Azure cuando está configurada.
4. Los insights reales del indexador se normalizan al mismo esquema de Teams.

## Pipeline único posterior

- **Orquestador:** Durable Functions coordina trabajos idempotentes, reintentos, estados y segmentos paralelos; no bloquea HTTP. Este orquestador es **diseño de MVP**, no está implementado en la PoC local.
- **Visual:** Container Apps Jobs ejecutan FFmpeg/OpenCV, OCR sobre candidatos seleccionados y extracción de imágenes originales.
- **Texto:** motor de reglas separa instructor confirmado de preguntas y contexto; no inventa identidad si no existe atribución.
- **IA:** Azure OpenAI interpreta paquetes de transcripción + frames, produce pasos como `observed/inferred/ambiguous` con evidencia y coordenadas; la PoC tiene la llamada opcional al modelo, sin prueba real contra recursos Azure.
- **Representación:** JSON versionable con fuente, speaker, intervalo, imagen y cada paso. PostgreSQL es el repositorio transaccional previsto; Blob almacena artefactos.
- **Corrección:** feedback desde revisión de PPTX por API, localización del `step_id`, propuesta de ajuste y aprobación. No necesita editor completo en el frontend. En PoC se edita JSON; el endpoint corporativo es solo contrato propuesto.
- **Documentos:** `python-pptx` genera capturas con callouts nativos editables; `python-docx` guía con capturas anotadas e instrucciones. Las versiones nuevas se regeneran desde JSON sin revisar el video entero cuando no cambia la evidencia.

## Prioridad operacional

No se deberá enviar un video completo de cinco horas a un LLM. La extracción visual y la indexación pueden trabajarse en paralelo y en segmentos; conservar timestamps absolutos, umbrales de revisión y rutas seguras al archivo fuente. Los supuestos de rendimiento (menos de 3 horas de análisis automático para 5 horas de video) requieren benchmark real y no son garantías.

## Diagramas

1. `diagrams/arquitectura_dual_azure.mmd` — servicio por capa y dos rutas.
2. `diagrams/decision_ingestion.mmd` — decisión, fallback y ausencia de speaker attribution.
3. `diagrams/revision_feedback.mmd` — feedback de presentación sin editor corporativo completo.

## Fuentes

- https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/meeting-transcripts/overview-transcripts
- https://learn.microsoft.com/en-us/graph/api/calltranscript-get?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/api/callrecording-get?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/azure/azure-video-indexer/upload-index-media
- https://learn.microsoft.com/en-us/azure/azure-video-indexer/storage-behind-firewall
- https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-fan-in-fan-out
