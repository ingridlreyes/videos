"""Normalize Teams WebVTT, a diarized JSON file or Video Indexer insights.

Outputs a shared, vendor-neutral transcript schema. No speaker identity is inferred.
"""
from __future__ import annotations
import html
import json
import re
from pathlib import Path
from typing import Any

TIME_RANGE = re.compile(r"^\s*(-?\d{1,3}:\d{2}(?::\d{2})?[.,]\d{1,3})\s*-->\s*(-?\d{1,3}:\d{2}(?::\d{2})?[.,]\d{1,3})")
VOICE = re.compile(r"<v(?:\.[^ >]+)?\s+([^>]+)>", re.I)
TAG = re.compile(r"<[^>]*>")


def seconds(stamp: str | float | int) -> float:
    if isinstance(stamp,(int,float)): return float(stamp)
    parts=str(stamp).strip().replace(',', '.').split(':')
    if len(parts) not in (2,3):
        raise ValueError(f'Timestamp inválido: {stamp}')
    nums=[float(p) for p in parts]
    return round((nums[-3]*3600 if len(nums)==3 else 0)+nums[-2]*60+nums[-1],3)


def vtt_to_segments(content: str, *, source: str='teams_vtt') -> list[dict]:
    """Accept Teams VTT or speaker-unattributed Graph text timecoded format.

    Supports <v Name>text</v>, HTML entities, cue numbers, multiline cues,
    and positive/negative timeline offsets. No fabricated speaker identity.
    """
    content=content.lstrip('\ufeff').replace('\r\n','\n').replace('\r','\n')
    blocks=re.split(r'\n\s*\n',content)
    output=[]
    for block in blocks:
        lines=[line.strip() for line in block.strip().split('\n')]
        idx=next((j for j,line in enumerate(lines) if TIME_RANGE.search(line)),None)
        if idx is None: continue
        match=TIME_RANGE.search(lines[idx]);start,end=seconds(match.group(1)),seconds(match.group(2))
        if end < start: continue
        body=' '.join(lines[idx+1:]).strip()
        voice=VOICE.search(body)
        speaker=html.unescape(voice.group(1).strip()) if voice else None
        txt=html.unescape(TAG.sub('',body)).strip()
        txt=re.sub(r'\s+',' ',txt)
        if txt:
            output.append({'speaker':speaker,'start':start,'end':end,'text':txt,'source':source})
    return sorted(output,key=lambda x:x['start'])


def normalize_json(data: Any, *, source: str='provided_json') -> list[dict]:
    if isinstance(data,dict): data=data.get('segments',data.get('transcript',[]))
    if not isinstance(data,list): raise ValueError('Se esperaba lista JSON de segmentos')
    out=[]
    for row in data:
        if not isinstance(row,dict): continue
        start=seconds(row.get('start',row.get('second',0)))
        end=seconds(row.get('end',start))
        txt=str(row.get('text','')).strip()
        if end<start or not txt: continue
        out.append({'speaker':row.get('speaker',row.get('speaker_id')),
                    'start':start,'end':end,'text':txt,'source':source})
    return sorted(out,key=lambda x:x['start'])


def indexer_to_segments(data: dict) -> list[dict]:
    """Map Azure AI Video Indexer transcript insight instances into same schema."""
    if 'videos' in data:
        tracks=[v.get('insights',{}) for v in data.get('videos',[])]
    else: tracks=[data.get('insights',data)]
    out=[]
    for ins in tracks:
        for row in ins.get('transcript',[]):
            for inst in row.get('instances',[]):
                start=seconds(inst.get('start','00:00:00.000'))
                end=seconds(inst.get('end',start))
                if end<start:continue
                text=str(row.get('text','')).strip()
                if not text:continue
                speaker=row.get('speakerId')
                # A numeric speakerId is not a confirmed human identity.
                out.append({'speaker':str(speaker) if speaker is not None else None,
                            'start':start,'end':end,'text':text,'source':'video_indexer'})
    return sorted(out,key=lambda x:x['start'])


def read_transcript(file_path: str | Path | None) -> list[dict]:
    if not file_path: return []
    path=Path(file_path)
    text=path.read_text(encoding='utf-8-sig')
    if path.suffix.lower() in ('.vtt','.srt','.txt'):
        return vtt_to_segments(text,source='teams_vtt' if path.suffix.lower()=='.vtt' else 'supplied_text')
    data=json.loads(text)
    if isinstance(data,dict) and ('videos' in data or 'insights' in data):
        return indexer_to_segments(data)
    return normalize_json(data)


def route(source_type: str, has_transcript: bool, *, provider_available=True) -> dict:
    """Deterministic routing, never pretends missing transcription is complete."""
    if source_type not in ('teams','external'): raise ValueError('source_type debe ser teams/external')
    if has_transcript:
        return {'path':'reuse_transcript', 'requires_indexer':False,'state':'ready'}
    return {'path':'video_indexer','requires_indexer':True,
            'state':'indexer_required' if provider_available else 'needs_provider_configuration'}


def transcript_audit(rows: list[dict]) -> dict:
    names=sorted({str(r['speaker']) for r in rows if r.get('speaker') not in (None,'','unknown')})
    return {'segments':len(rows),'speakers':names,'has_speaker_attribution':bool(names),
            'requires_instructor_confirmation':bool(names),
            'warning':None if names else 'No hay atribución de hablantes. No se debe aplicar filtro de instructor.'}
