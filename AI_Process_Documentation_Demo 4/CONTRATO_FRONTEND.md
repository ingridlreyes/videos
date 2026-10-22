# Contrato REST para el equipo del frontend (propuesto, todavía no desplegado)

El frontend es responsabilidad de otro equipo. No presupone React.

## Entradas

**POST /api/v1/jobs**

```json
{
  "source_type": "teams",
  "source": {"organizer_user_id":"...", "online_meeting_id":"..."},
  "instructor_speaker": "Instructor confirmado",
  "rules": {"only_instructor_steps":true,"questions":"appendix"},
  "outputs": ["pptx", "docx"]
}
```

Para video externo, `source_type="external"` y `source.blob_id` apuntará a un Blob cargado mediante URL SAS emitida por nuestro backend. Se admite opcionalmente `source.transcript_blob_id` para evitar doble transcripción. No se envían gigabytes al endpoint JSON ni claves del proveedor desde el frontend.

**Respuesta 202 Accepted**

```json
{"job_id":"job_123","status":"queued","status_url":"/api/v1/jobs/job_123"}
```

**GET /api/v1/jobs/{job_id}**: `queued`, `importing`, `transcribing`, `extracting_frames`, `interpreting`, `review_required`, `generating`, `complete`, `failed`; incluye contadores sin porcentajes ficticios.

**GET /api/v1/jobs/{job_id}/procedures**: pasos + `step_id`, `source_type`, `transcript_source`, `speaker_attributed`, `timestamp`, `frame_id`, `bbox`, `interpretation_status`, `validation_status`, `evidence_refs`.

**POST /api/v1/jobs/{job_id}/feedback**:

```json
{"procedure_id":"p01","step_id":"s03","slide_number":4,"comment":"Antes de Guardar falta una validación","type":"missing_step"}
```

La IA propone corrección respaldada en evidencia; el revisor aprueba antes de generar una nueva versión. La PoC local incluye edición de JSON, no un editor del frontend empresarial.

**POST /api/v1/jobs/{job_id}/exports** genera versiones PPTX/DOCX desde el JSON aprobado; **GET /api/v1/jobs/{job_id}/exports** devuelve rutas de descarga autorizadas.

**Seguridad requerida en producción:** Entra ID, RBAC por proyecto, autorización backend en cada acción, aislamiento de tenants, SAS breves, redacción de datos sensibles, auditoría y límites de carga/solicitudes.
