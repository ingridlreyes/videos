"""Optional Azure AI Video Indexer adapter for an arbitrary video without transcript.

Uses Azure ARM access token + Video Indexer API. Caller uploads video to its own
private Azure Blob first; URL must be authorized for Video Indexer to read.
No fake transcription in local/offline mode.
"""
from __future__ import annotations
import os
from urllib.parse import quote
import requests
from transcript_ingestion import indexer_to_segments

class VideoIndexerError(RuntimeError):pass


def arm_token():
    try:from azure.identity import DefaultAzureCredential
    except ImportError as e:raise VideoIndexerError('Se requiere azure-identity en el backend.') from e
    return DefaultAzureCredential(exclude_interactive_browser_credential=True).get_token('https://management.azure.com/.default').token

class AzureVideoIndexerClient:
    def __init__(self, subscription_id=None,resource_group=None,account_name=None,account_id=None,location=None,token_provider=arm_token,session=None):
        self.subscription_id=subscription_id or os.getenv('AVI_SUBSCRIPTION_ID')
        self.resource_group=resource_group or os.getenv('AVI_RESOURCE_GROUP')
        self.account_name=account_name or os.getenv('AVI_ACCOUNT_NAME')
        self.account_id=account_id or os.getenv('AVI_ACCOUNT_ID')
        self.location=location or os.getenv('AVI_LOCATION')
        if not all([self.subscription_id,self.resource_group,self.account_name,self.account_id,self.location]):
            raise VideoIndexerError('Configura AVI_SUBSCRIPTION_ID, AVI_RESOURCE_GROUP, AVI_ACCOUNT_NAME, AVI_ACCOUNT_ID y AVI_LOCATION.')
        self.token_provider=token_provider;self.session=session or requests.Session()

    def access_token(self,permission='Contributor'):
        url=('https://management.azure.com/subscriptions/'+quote(self.subscription_id,safe='')+'/resourceGroups/'+
             quote(self.resource_group,safe='')+'/providers/Microsoft.VideoIndexer/accounts/'+
             quote(self.account_name,safe='')+'/generateAccessToken')
        r=self.session.post(url,params={'api-version':'2025-04-01'},json={'permissionType':permission,'scope':'Account'},
                            headers={'Authorization':f'Bearer {self.token_provider()}'},timeout=60)
        try:r.raise_for_status();return r.json()['accessToken']
        finally:r.close()

    def base(self):
        return f'https://api.videoindexer.ai/{quote(self.location,safe="")}/Accounts/{quote(self.account_id,safe="")}'

    def submit(self,video_url,name='video_externo',managed_identity=False):
        if not video_url.startswith('https://'):raise VideoIndexerError('El origen debe ser un Blob HTTPS autorizado, no un enlace arbitrario.')
        params={'name':name[:75],'videoUrl':video_url,'privacy':'Private','streamingPreset':'NoStreaming',
                'accessToken':self.access_token('Contributor')}
        if managed_identity:params['useManagedIdentityToDownloadVideo']='true'
        r=self.session.post(self.base()+'/Videos',params=params,timeout=120)
        try:r.raise_for_status();return {'video_id':r.json().get('id'),'state':'submitted'}
        finally:r.close()

    def get_insights(self,video_id):
        r=self.session.get(self.base()+'/Videos/'+quote(str(video_id),safe='')+'/Index',
                           params={'accessToken':self.access_token('Reader')},timeout=90)
        try:r.raise_for_status();return r.json()
        finally:r.close()

    def segments(self,video_id):
        ins=self.get_insights(video_id)
        return {'state':ins.get('state','Unknown'),'segments':indexer_to_segments(ins)}
