# Proyecto limpio — Azure OpenAI sin Azure AI Video Indexer

**Entrada principal:** `python web_real.py` o `python run_real.py --video tu.mp4`.

1. `pip install -r requirements-real.txt` (también debes instalar FFmpeg).
2. Copia `.env.example` a `.env` y agrega únicamente las credenciales de Azure OpenAI.
3. No necesitas ninguna credencial ni recurso de Azure AI Video Indexer.
4. Para Azure Blob opcional, configura `USE_AZURE_BLOB=true` y la URL de tu cuenta.
5. Para reutilizar Teams VTT, pasa `--transcript reunion.vtt` junto al MP4.

**Nota:** el adaptador de Microsoft Graph no está integrado al flujo principal de la demo; el VTT se adjunta manualmente. La demo está diseñada para videos cortos; el escalado de cinco horas requerirá orquestación distribuida.

Consulta `README_EJECUCION_REAL.md` para explicación de scripts, funciones, limitaciones y pruebas.
