"""Normalize Teams WebVTT and diarized JSON transcripts.

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



def read_transcript(file_path: str | Path | None) -> list[dict]:
    if not file_path: return []
    path=Path(file_path)
    text=path.read_text(encoding='utf-8-sig')
    if path.suffix.lower() in ('.vtt','.srt','.txt'):
        return vtt_to_segments(text,source='teams_vtt' if path.suffix.lower()=='.vtt' else 'supplied_text')
    data=json.loads(text)
    return normalize_json(data)



def transcript_audit(rows: list[dict]) -> dict:
    names=sorted({str(r['speaker']) for r in rows if r.get('speaker') not in (None,'','unknown')})
    return {'segments':len(rows),'speakers':names,'has_speaker_attribution':bool(names),
            'requires_instructor_confirmation':bool(names),
            'warning':None if names else 'No hay atribución de hablantes. No se debe aplicar filtro de instructor.'}
