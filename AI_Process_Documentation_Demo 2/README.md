# AI Process Documentation — PoC actualizada (Teams + videos externos)

**Versión:** 0.2 — entrada dual, motor documental común. Se trata de una demostración funcional local, no de un sistema ya desplegado en Azure. No depende del framework del frontend empresarial.

## Qué cambió

- **Ruta A / Teams:** reutiliza un MP4 y un archivo VTT de Microsoft Teams, con marcas de tiempo y etiquetas de hablantes; o importa recursos mediante Microsoft Graph con credenciales y permisos correctos.
- **Ruta B / video externo:** acepta MP4 más transcripción opcional. Si falta, usa Azure AI Video Indexer mediante una URL autorizada de Azure Blob y recupera después sus insights; no fingimos que una foto contiene audio.
- **Motor común:** `transcript_ingestion.py` normaliza Teams VTT, JSON segmentado e insights de Video Indexer al mismo esquema (`speaker`, `start`, `end`, `text`, `source`). El análisis visual y el generador documental son los mismos.
- **Salidas:** PowerPoint con **recuadros nativos editables**, DOCX (marcas compuestas en la captura), pasos en JSON y evidencia temporal.
- **Sin attribution de Teams:** se conserva texto, pero se deshabilita filtrado automático por instructor hasta que exista identificación confirmada.

## Ejecutar sin Azure

Requiere Python 3.11+, entorno virtual recomendado.

```bash
python -m pip install -r requirements.txt
python app.py
```

Abrir la pestaña **Ejemplo ficticio** para crear documentos sin claves. Las imágenes y el MP4 sintéticos son ilustrativos. Para probar Teams con artefactos locales usa `examples/teams_transcript_example.vtt` y `assets/video_demo_ficticio.mp4`; los hablantes son ficticios.

En las pestañas principales: elegir origen, adjuntar MP4 + transcripción, escribir **nombre/ID exacto del instructor** y extraer frames. Si tienes un deployment multimodal de Azure OpenAI puedes proponer instrucciones sobre los fotogramas, pero **todas siguen sujetas a revisión humana**.

Limitación de la PoC: inspecciona una ventana de hasta 15 minutos y selecciona como máximo 24 capturas. Para videos de hasta cinco horas la arquitectura de producción necesita Blob, Durable Functions y workers paralelos. No existe medición real aquí del rendimiento a cinco horas.

## Habilitar Microsoft Graph

```bash
python -m pip install -r requirements-azure.txt
# Para prueba local con permisos de aplicación se requiere
# AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
# o una identidad administrada en Azure con autorización del administrador.
```

`graph_teams.py` usa DefaultAzureCredential en backend (identidad administrada en Azure o credenciales de aplicación por variables de entorno), **nunca** un token pegado en el frontend. El administrador debe configurar permisos de aplicación `OnlineMeetingTranscript.Read.All` y `OnlineMeetingRecording.Read.All`, consentimiento y política de acceso. El cliente requiere `organizer user ID` + `online meeting ID`, y usa endpoints v1.0 para listar/descargar los MP4 y VTT. La API puede restringir ciertos tipos de reuniones según tenant y modalidad.

Cuando `SpeakerAttributionNotAllowed`, reintenta la transcripción sin hablantes. Si `GraphAccessToTranscriptsDisabled`, no existe solución desde la petición: solicitar habilitación al administrador o usar el procesamiento audiovisual alternativo con autorización.

## Habilitar Video Indexer para videos externos (opcional)

Instala `requirements-azure.txt`, configura las variables `AVI_*` indicadas en `.env.example` **en el entorno real (no pegar secretos en la interfaz)**. Se debe crear un recurso Azure AI Video Indexer pagado y autorizar acceso al video almacenado en Blob. En la pestaña de video externo, ingresar URL Blob **de acceso controlado** o bien pulsar "Subir MP4 externo a Blob e iniciar indexación" (requiere `AZURE_STORAGE_ACCOUNT_URL`, `AZURE_BLOB_CONTAINER` y los roles correspondientes); luego consultar el Video Indexer ID y cargar su transcripción normalizada. Este flujo no es instantáneo; no se mantienen peticiones HTTP abiertas hasta finalizar. Se incluye la alternativa de importar un JSON real de insights sin llamar al servicio.

`AzureVideoIndexerClient` implementa obtención del token con API ARM, envío por URL, consulta de index y normalización. No está probado contra un recurso Azure de esta sesión; necesita credenciales, cuotas y permisos reales. Los secretos se administran en Azure Key Vault/identidades administradas en producción.

## Habilitar sugerencia multimodal Azure OpenAI

Variables `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_KEY`; deployment debe aceptar imágenes. Después de extraer fotogramas, pulsar "Proponer pasos con Azure OpenAI". No se ha probado contra un deployment Azure real; requiere acceso configurado. Si no hay un instructor validado en la transcripción, la PoC no permite proponer pasos a partir de voz. Esto evita mezclar participantes.

## Arquitectura y recursos

- `diagrams/arquitectura_dual_azure.mmd`: arquitectura completa, frontend externo.
- `diagrams/decision_ingestion.mmd`: decisión Teams/externo y fallback.
- `diagrams/revision_feedback.mmd`: correcciones sobre entregables.
- `REQUERIMIENTOS_AZURE.md`: aprovisionamiento, roles y fases.
- `CONTRATO_FRONTEND.md`: endpoints propuestos para integración (aún no implementados como servicio).
- `graph_teams.py`: adaptador Microsoft Graph.
- `video_indexer.py`: adaptador Azure AI Video Indexer.
- `transcript_ingestion.py`: normalización de resultados de audio/transcripción.
- `app.py`: PoC Gradio local.
- `poc_core.py`: análisis visual de cambios y exportadores.
- `tests/test_dual_route.py`: pruebas aisladas para parser, router y cliente Graph mock.

## Comprobación

```bash
python -m pytest -q tests
python generate_example.py
```

## Aclaraciones importantes

1. **Un enlace de Teams no garantiza acceso por Graph.** Debe estar autorizado y resolverse como reunión/artefacto mediante la identidad empresarial adecuada.
2. El VTT puede no identificar hablantes por política de privacidad del tenant; en ese caso no prometemos filtro de instructor.
3. Un fotograma no prueba que ocurrió un clic; el LLM sugiere un paso con evidencia e incertidumbre, nunca interacción confirmada por telemetría inexistente.
4. Las grabaciones pueden mostrar credenciales o datos personales. La PoC **no automatiza el enmascaramiento**, así que utiliza videos sintéticos/autorizados y no envíes contenido sensible al LLM sin políticas corporativas y redacción previa.
5. Las rutas de audio convergen en JSON común, pero el pipeline masivo asíncrono y endpoints corporativos del documento de arquitectura quedan **por implementar**. No se afirma producción funcional.

## Fuentes técnicas oficiales

- [Teams: transcripts y recordings vía Graph](https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/meeting-transcripts/overview-transcripts)
- [Graph: transcripción individual y formatos VTT](https://learn.microsoft.com/en-us/graph/api/calltranscript-get?view=graph-rest-1.0)
- [Graph: grabación individual](https://learn.microsoft.com/en-us/graph/api/callrecording-get?view=graph-rest-1.0)
- [Azure Video Indexer: carga e indexación](https://learn.microsoft.com/en-us/azure/azure-video-indexer/upload-index-media)
- [Azure Video Indexer: access token via ARM](https://learn.microsoft.com/en-us/rest/api/videoindexer/generate/access-token?view=rest-videoindexer-2025-04-01)
