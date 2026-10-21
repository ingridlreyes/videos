# Recursos Azure — dos rutas de origen

| Recurso | Uso | Teams | Video externo | Fase |
|---|---|:---:|:---:|---|
| Entra ID y app registration Graph | Acceso aplicación autorizado a grabaciones y transcripciones | Sí | No | Integración Teams |
| Microsoft Graph API | MP4 + VTT con speakers si policy del tenant lo permite | Sí | No | Integración Teams |
| Azure Blob Storage | Videos, transcripciones, capturas, resultados JSON, PPTX y DOCX | Sí | Sí | POC/MVP |
| Azure AI Video Indexer | Transcripción/diarización si no hay transcripción previa válida | Condicional | Condicional | MVP |
| Azure OpenAI (modelo con visión) | Comprensión de capturas + texto, propuesta de pasos y decisiones | Sí | Sí | POC/MVP |
| Azure Container Apps - FastAPI | Contrato REST con frontend externo (tecnología desconocida) | Sí | Sí | MVP |
| Azure Container Apps Jobs | FFmpeg/OpenCV y generación de documentos | Sí | Sí | MVP |
| Durable Functions | Orquestación asíncrona, Job ID, estados, reintentos | Sí | Sí | MVP 5 horas |
| Azure Database for PostgreSQL | Estado del producto, reglas, versiones y feedback | Sí | Sí | MVP |
| Azure Container Registry | Imágenes de API/workers | Sí | Sí | MVP |
| Key Vault + Managed Identity | Secretos, tokens y accesos entre recursos | Sí | Sí | MVP |
| Azure Monitor + Application Insights | Observabilidad, costo y errores | Sí | Sí | MVP |
| Azure AI Vision OCR | OCR visual adicional si mejora calidad respecto a open source | Opt. | Opt. | Benchmark |
| Azure AI Search | Biblioteca consultable de procedimientos | No | No | Futuro |
| Azure Service Bus | Desacoplamiento si aumenta volumen | No | No | Futuro |

## Microsoft Graph

Se requieren permisos de aplicación aprobados por el administrador, por ejemplo `OnlineMeetingTranscript.Read.All` y `OnlineMeetingRecording.Read.All`, junto con las políticas de acceso y los ajustes de Teams que correspondan. El acceso a VTT con nombres de hablantes puede prohibirse en el tenant; solicitar en tal caso contenido sin speakers y bloquear filtrado de instructor hasta resolverlo.

Un enlace de uso compartido de Teams/SharePoint no equivale al ID de reunión de Microsoft Graph. La PoC de descarga directa utiliza organizer user ID + online meeting ID. Una integración real con enlaces de compartición debe resolverlos con permisos adecuados, no tratar el enlace como un archivo público.

## Azure Video Indexer

Usar solo cuando la ruta no tiene transcripción utilizable. `AVI_*` identifica cuenta/ubicación. Para videos largos, cargar a Blob y mandar una URL de acceso **temporal y restringido**, o habilitar la identidad administrada de Video Indexer para acceso a almacenamiento autorizado. La UI local no puede transcribir un MP4 usando Video Indexer sin autenticación y un origen Blob al que el servicio tenga acceso.

## No inventamos las capacidades del frontend

El otro equipo implementa su experiencia con cualquier framework. Nuestro contrato de integración es REST/HTTPS, un Job ID y JSON de procedimientos; se propone un formulario mínimo de feedback por diapositiva/step_id. El editor de diagramas no forma parte del frontend existente.
