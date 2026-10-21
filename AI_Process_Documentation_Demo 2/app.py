"""AI Process Documentation local proof-of-concept — dual ingestion.

Teams: Graph or recording + VTT. External: upload video + optional transcript
or AI Video Indexer insights. Both feed same reviewable procedure JSON and
editable documents. Production asynchronous deployment documented separately.
"""
import json
import os
import tempfile
from pathlib import Path
import gradio as gr
from poc_core import (ROOT,OUT,load_process,generate,source_image,
                      extract_candidate_frames,analyze_screen_azure)
from transcript_ingestion import read_transcript,transcript_audit,route

DEFAULT_RULES=('Solo instrucciones del instructor validado. Preguntas de participantes fuera del flujo. '
               'No inventar clics ni botones. Preservar timestamps. Datos sensibles: revisión obligatoria.')


def read_rows(path):
    if not path:return []
    try:return read_transcript(path)
    except Exception as exc:raise gr.Error(f'No se pudo leer la transcripción: {exc}') from exc


def nearby(rows,second,instructor):
    if not rows:return ''
    if not instructor or instructor.strip() not in {str(row.get('speaker')) for row in rows}:
        return ''
    return ' '.join(str(row['text']) for row in rows if str(row.get('speaker'))==str(instructor.strip())
                    and abs(float(row['start'])-second)<=18)[:1600]


def scan(video,transcript,source,instructor,rules,interval,maxdur):
    if not video:raise gr.Error('Adjunta un MP4 antes de analizar.')
    rows=read_rows(transcript)
    decision=route(source,bool(rows),provider_available=bool(os.getenv('AVI_ACCOUNT_ID')))
    audit=transcript_audit(rows)
    frames,duration=extract_candidate_frames(video,float(interval),float(maxdur),24,max_gap_seconds=12)
    if not frames:raise gr.Error('No se pudieron obtener capturas del MP4.')
    selected=instructor.strip() if instructor else ''
    is_confirmed=selected in audit['speakers']
    for st in frames:
        st['transcript_instructor']=nearby(rows,float(st['second']),selected) if is_confirmed else ''
        st['transcript_source']=rows[0]['source'] if rows else None
        st['evidence_type']='frame_observed_action_unverified'
    data={'title':'Borrador de procedimiento — '+('Teams' if source=='teams' else 'video externo'),
          'source_type':source,'transcript_route':decision['path'],'transcript_audit':audit,
          'goal':'Reconstruir únicamente acciones respaldadas por evidencias.',
          'prerequisites':'Acceso autorizado al sistema; identidad del instructor validada.',
          'rules_summary':rules,'rules':[rules],'steps':frames,
          'instructor_speaker':selected if is_confirmed else None,
          'review_required':True}
    cards=[(f['image'],f['time']+' · POR REVISAR') for f in frames]
    notes=[f'Duración detectada: {duration/60:.1f} min. Ventana examinada: hasta {maxdur/60:.1f} min.',
           f'{len(frames)} capturas candidatas, {audit["segments"]} segmentos transcritos.',
           'Las capturas no demuestran clics ni interacciones exactas.']
    if not rows:notes.append('SIN TRANSCRIPCIÓN: usar Video Indexer o adjuntar VTT/JSON antes de reconstruir pasos hablados.')
    if not is_confirmed:notes.append('INSTRUCTOR NO VALIDADO: selecciona el nombre/ID exacto del listado; no se aplicó filtro.')
    if audit['warning']:notes.append(audit['warning'])
    return cards,json.dumps(data,ensure_ascii=False,indent=2),'  '.join(notes)


def enrich(json_text,transcript,instructor,rules):
    data=json.loads(json_text)
    rows=read_rows(transcript)
    audit=transcript_audit(rows)
    if not instructor or instructor.strip() not in audit['speakers']:
        raise gr.Error('Antes de usar las instrucciones del instructor, confirma su nombre/ID exacto en la transcripción.')
    n=0
    for st in data['steps']:
        context=nearby(rows,float(st.get('second',0)),instructor)
        if not context:continue
        obs=analyze_screen_azure(str(source_image(st)),context,rules)
        st.update(obs)
        st['review_required']=True  # LLM suggestions always require review
        st['interpretation_status']='inferred'
        n+=1
    return json.dumps(data,ensure_ascii=False,indent=2),f'Azure analizó {n} capturas con audio del instructor. Revisa la evidencia y geometría.'


def final_generate(json_text):
    try:
        data=json.loads(json_text)
        if not data.get('steps'):raise ValueError('No hay pasos')
        for s in data['steps']:
            if not source_image(s).is_file():raise ValueError('No existe la imagen asociada a un paso')
        suffix='Teams_Borrador' if data.get('source_type')=='teams' else 'Video_Externo_Borrador'
        ppt,doc=generate(data,suffix)
        return ppt,doc,'Borradores exportados con revisión obligatoria. Guarda una versión aprobada antes de publicar.'
    except Exception as e:raise gr.Error(f'No se pudieron crear documentos: {e}')


def graph_download(user_id,meeting_id):
    if not user_id or not meeting_id:raise gr.Error('Introduce organizer user ID y online meeting ID de Microsoft Graph.')
    try:
        from graph_teams import TeamsGraphClient
        dest=Path(tempfile.mkdtemp(prefix='teams_graph_',dir=OUT))
        result=TeamsGraphClient().download(user_id,meeting_id,dest)
        note='Grabación recuperada con Microsoft Graph. '
        note+= ('Transcripción con hablantes descargada.' if result.get('transcript_format')=='text/vtt' else
                'Transcripción sin atribución de hablantes.' if result.get('transcript_path') else
                'No hay transcripción disponible: usar ruta alternativa Video Indexer.')
        return result['video_path'],result['transcript_path'],note
    except Exception as exc:raise gr.Error(f'Importación Graph no completada: {exc}')


def vi_upload_from_local(video_path,name,managed_identity):
    if not video_path:raise gr.Error('Primero selecciona un MP4 externo.')
    try:
        from azure_blob import upload_video
        from video_indexer import AzureVideoIndexerClient
        item=upload_video(video_path,managed_identity_for_indexer=bool(managed_identity))
        vi=AzureVideoIndexerClient().submit(item['transient_url'],name or 'video_externo',bool(managed_identity))
        return vi['video_id'],'Video subido al Blob privado e indexación solicitada. Estado: submitted; consulta el ID cuando termine.'
    except Exception as exc:
        raise gr.Error(f'No fue posible subir o indexar el MP4: {exc}')


def vi_submit(sas_url,name,managed_identity):
    if not sas_url:raise gr.Error('Proporciona una URL HTTPS de Blob autorizada; un MP4 cargado localmente no es accesible por Video Indexer.')
    try:
        from video_indexer import AzureVideoIndexerClient
        r=AzureVideoIndexerClient().submit(sas_url,name or 'video_externo',bool(managed_identity))
        return r['video_id'],f'Indexación enviada; ID={r["video_id"]}. Consulta después los insights; no hay transcripción disponible todavía.'
    except Exception as exc:raise gr.Error(f'Video Indexer no pudo iniciar: {exc}')


def vi_fetch(video_id):
    if not video_id:raise gr.Error('Falta Video Indexer video ID.')
    try:
        from video_indexer import AzureVideoIndexerClient
        r=AzureVideoIndexerClient().segments(video_id)
        if r['state'].lower() not in ('processed','processedwithwarnings') or not r['segments']:
            return None, f'Estado en Video Indexer: {r["state"]}; segmentos disponibles: {len(r["segments"])}. Vuelve a consultar cuando termine.'
        fn=OUT/f'video_indexer_{str(video_id)[:32]}.json'
        fn.write_text(json.dumps(r['segments'],ensure_ascii=False,indent=2),encoding='utf-8')
        return str(fn),f'Video Indexer procesó {len(r["segments"])} segmentos. Archivo normalizado listo para adjuntar.'
    except Exception as exc:raise gr.Error(f'No se pudo consultar el indexador: {exc}')


def initial_demo():
    data=load_process()
    return [(str(source_image(s)),s['title']) for s in data['steps']],json.dumps(data,ensure_ascii=False,indent=2)


def sample_generate():
    a,b=generate(load_process(),'Demo')
    return a,b,'Ejemplo sintético generado; no representa análisis de una reunión real.'


def workflow(source,video_component,transcript_component):
    gr.Markdown('**Límite PoC:** escanea hasta 15 minutos en modo local. Videos de 5 horas requieren Blob + orquestación asíncrona en Azure. No se realiza transcripción inventada.')
    video=video_component
    transcript=transcript_component
    with gr.Row():
        speaker=gr.Textbox(label='Nombre / ID exacto del instructor según transcripción (confirmado por usuario)',value='Instructor')
        interval=gr.Slider(2,15,value=3,step=1,label='Intervalo entre frames (segundos)')
        maxdur=gr.Slider(60,900,value=600,step=60,label='Duración máxima que analizará la demo (segundos)')
    rules=gr.Textbox(label='Reglas de documentación',value=DEFAULT_RULES,lines=2)
    scanbtn=gr.Button('1 · Extraer frames + relacionar transcripción',variant='primary')
    frames=gr.Gallery(label='Frames candidatos',columns=3,height=290)
    status=gr.Markdown()
    steps=gr.Code(label='JSON unificado de procedimiento — edita y valida antes de exportar',language='json',lines=19,interactive=True)
    scanbtn.click(lambda v,t,s,r,i,m: scan(v,t,source,s,r,i,m),
                  inputs=[video,transcript,speaker,rules,interval,maxdur],outputs=[frames,steps,status])
    ai=gr.Button('2 · Opcional: proponer pasos con Azure OpenAI')
    ai.click(enrich,inputs=[steps,transcript,speaker,rules],outputs=[steps,status])
    button=gr.Button('3 · Generar PPTX y DOCX revisables',variant='primary')
    with gr.Row():
        ppt=gr.File(label='PowerPoint')
        doc=gr.File(label='Guía Word')
    button.click(final_generate,inputs=[steps],outputs=[ppt,doc,status])


with gr.Blocks(title='AI Process Documentation · Teams + Video externo') as app:
    gr.Markdown('# AI Process Documentation · Dos rutas, un único motor documental\n'
                '**Teams → Graph + VTT**; **video externo → transcripción adjunta o Video Indexer**. '
                'La IA opcional necesita un deployment de Azure OpenAI con visión. '
                'No identifica clics exactos ni sustituye la revisión humana.')
    with gr.Tab('01 · Teams (MP4 + VTT / Graph)'):
        gr.Markdown('Reutiliza transcripción de Teams cuando exista. Graph requiere permisos de aplicación y políticas del tenant; no basta pegar un enlace público.')
        with gr.Accordion('Importación directa con Microsoft Graph (opcional, configuración de Azure)',open=False):
            user=gr.Textbox(label='Organizer user ID (Microsoft Entra ID)')
            meeting=gr.Textbox(label='Online meeting ID (Microsoft Graph)')
            fetch=gr.Button('Importar MP4 + VTT desde Graph')
            graph_msg=gr.Markdown()
        teams_video=gr.Video(label='Grabación Teams MP4',sources=['upload'],format='mp4')
        teams_transcript=gr.File(label='Transcripción Teams .vtt, .txt o .json',file_types=['.vtt','.txt','.json'],type='filepath')
        fetch.click(graph_download,inputs=[user,meeting],outputs=[teams_video,teams_transcript,graph_msg])
        workflow('teams',teams_video,teams_transcript)

    with gr.Tab('02 · Video externo / MP4'):
        gr.Markdown('Puedes adjuntar VTT/JSON. Si falta transcripción, enviar el video a Video Indexer desde un Blob autorizado. No se vuelve a transcribir si ya aportaste texto utilizable.')
        external_video=gr.Video(label='MP4 externo',sources=['upload'],format='mp4')
        external_transcript=gr.File(label='Transcripción VTT/JSON o insights JSON de Video Indexer (opcional)',
                                    file_types=['.vtt','.json','.txt'],type='filepath')
        with gr.Accordion('Azure AI Video Indexer · sólo cuando falta transcripción (opcional)',open=False):
            vi_blob=gr.Textbox(label='Blob URL HTTPS autorizado (SAS temporal o cuenta con identidad administrada)',type='password')
            vi_name=gr.Textbox(label='Nombre del video',value='sesion_externa')
            vi_mi=gr.Checkbox(label='Video Indexer usará Managed Identity para Blob protegido por firewall',value=False)
            vi_id=gr.Textbox(label='Video Indexer video ID')
            vi_upload=gr.Button('Subir MP4 externo a Blob e iniciar indexación',variant='primary')
            vi_send=gr.Button('Alternativamente: indexar Blob URL ya existente')
            vi_get=gr.Button('Recuperar transcripción cuando termine')
            vi_msg=gr.Markdown()
            vi_upload.click(vi_upload_from_local,inputs=[external_video,vi_name,vi_mi],outputs=[vi_id,vi_msg])
            vi_send.click(vi_submit,inputs=[vi_blob,vi_name,vi_mi],outputs=[vi_id,vi_msg])
            vi_get.click(vi_fetch,inputs=[vi_id],outputs=[external_transcript,vi_msg])
        workflow('external',external_video,external_transcript)

    with gr.Tab('03 · Ejemplo ficticio disponible sin Azure'):
        gal=gr.Gallery(columns=2,label='Capturas ficticias')
        spec=gr.Code(language='json',label='JSON ficticio')
        gr.Button('Ver ejemplo').click(initial_demo,outputs=[gal,spec])
        b=gr.Button('Generar PPT y Word de ejemplo',variant='primary')
        with gr.Row():
            f1=gr.File(label='PowerPoint')
            f2=gr.File(label='Word')
        msg=gr.Markdown()
        b.click(sample_generate,outputs=[f1,f2,msg])
    gr.Markdown('**Seguridad:** autorizar grabaciones, ocultar datos sensibles antes de inferencia y publicación. '
                '**Producción:** integración por API REST con el frontend de otro equipo; la UI Gradio es solo una PoC.')

if __name__=='__main__':app.launch(server_name='127.0.0.1',share=False,inbrowser=True)
