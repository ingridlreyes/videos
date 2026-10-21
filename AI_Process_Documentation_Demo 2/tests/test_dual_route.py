from pathlib import Path
from transcript_ingestion import vtt_to_segments,normalize_json,indexer_to_segments,transcript_audit,route,read_transcript
from graph_teams import TeamsGraphClient,GraphTeamsError

ROOT=Path(__file__).resolve().parents[1]

def test_teams_vtt_extracts_speakers_and_times():
    rows=read_transcript(ROOT/'examples/teams_transcript_example.vtt')
    assert len(rows)==3 and rows[0]['speaker']=='Instructora'
    assert rows[0]['start']==1.0 and rows[2]['end']==10.0
    assert 'Participante' in transcript_audit(rows)['speakers']


def test_unattributed_graph_text_does_not_invent_speaker():
    rows=vtt_to_segments('00:00:01.000 --> 00:00:03.000\nTexto sin speaker.\n')
    assert rows[0]['speaker'] is None
    assert not transcript_audit(rows)['has_speaker_attribution']


def test_html_entities_voice_tag_and_multiline():
    rows=vtt_to_segments('WEBVTT\n\n3\n00:01:01.050 --> 00:01:02.550\n<v Ana López>Guardar &amp; continuar\nen el menú.</v>\n')
    assert rows[0]['speaker']=='Ana López'
    assert rows[0]['text']=='Guardar & continuar en el menú.'
    assert rows[0]['start']==61.05


def test_indexer_insights_maps_to_same_schema():
    rows=read_transcript(ROOT/'examples/video_indexer_insights_example.json')
    assert len(rows)==2
    assert rows[0]['speaker']=='2' and rows[0]['start']==3
    assert rows[0]['source']=='video_indexer'


def test_source_routing_and_missing_transcript():
    assert route('teams',True)['path']=='reuse_transcript'
    assert route('external',True)['path']=='reuse_transcript'
    assert route('teams',False)['requires_indexer']
    assert route('external',False,provider_available=False)['state']=='needs_provider_configuration'


def test_segment_json_normalization():
    assert normalize_json([{'speaker':'S1','start':3,'end':5,'text':'Guardar'}])[0]['text']=='Guardar'

class Response:
    def __init__(self,status_code=200,body=None,content=None):
        self.status_code=status_code
        self._body=body if body is not None else {}
        self.content=content if content is not None else b''
    def json(self):return self._body
    def close(self):pass
    def iter_content(self,chunk_size=1024):yield self.content

class Session:
    def __init__(self):self.calls=[]
    def get(self,url,headers,**kwargs):
        self.calls.append((url,headers['Accept']))
        if url.endswith('/recordings'):
            return Response(body={'value':[{'id':'r1'}]})
        if url.endswith('/transcripts'):
            return Response(body={'value':[{'id':'t1'}]})
        if url.endswith('/t1/content'):
            return Response(content=b'WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<v Instructor>Hola</v>')
        if url.endswith('/r1/content'):return Response(content=b'mock_mp4_test_only')
        return Response(status_code=404,body={'error':{'code':'not_found'}})

def test_graph_adapter_fetches_both_artifacts_without_network(tmp_path):
    s=Session()
    g=TeamsGraphClient(token_provider=lambda:'MOCK_TOKEN',session=s)
    result=g.download('user-guid','meeting/id',tmp_path)
    assert Path(result['video_path']).exists() and Path(result['transcript_path']).exists()
    assert read_transcript(result['transcript_path'])[0]['speaker']=='Instructor'
    assert '%2F' in s.calls[0][0]

def test_team_speaker_attribution_disabled_uses_text_only():
    class PolicySession(Session):
        def get(self,url,headers,**kwargs):
            self.calls.append((url,headers['Accept']))
            if headers['Accept']=='text/vtt':
                return Response(status_code=403,body={'error':{
                    'code':'Forbidden','innerError':{'code':'SpeakerAttributionNotAllowed'}}})
            return Response(content=b'00:00:01.000 --> 00:00:02.000\nTexto sin hablante.')
    s=PolicySession()
    g=TeamsGraphClient(token_provider=lambda:'MOCK_TOKEN',session=s)
    vtt,format_name=g.fetch_transcript('organizer','meeting','tid')
    assert format_name=='unattributed'
    assert vtt_to_segments(vtt)[0]['speaker'] is None


def test_graph_permission_error_not_masked():
    class DeniedSession(Session):
        def get(self,url,headers,**kwargs):
            return Response(status_code=403,body={'error':{'innerError':{'code':'GraphAccessToTranscriptsDisabled'}}})
    g=TeamsGraphClient(token_provider=lambda:'MOCK_TOKEN',session=DeniedSession())
    try:g.fetch_transcript('organizer','meeting','tid')
    except GraphTeamsError as e:assert 'GraphAccessToTranscriptsDisabled' in str(e)
    else:assert False
