"""Upload arbitrary MP4 to private Azure Blob, optionally issue short read-only SAS.

This adapter runs on backend using Azure credentials. The frontend never handles
Azure account keys and cannot mint privileged SAS. For large files production
should instead request short-lived upload permissions and ingest directly.
"""
from __future__ import annotations
import os
import uuid
from pathlib import Path
from datetime import datetime,timedelta,timezone

class AzureBlobError(RuntimeError):pass


def upload_video(path: str | Path, *, managed_identity_for_indexer: bool=False):
    # Optional production dependencies are imported only when this route is used.
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient,BlobSasPermissions,ContentSettings,generate_blob_sas
    path=Path(path)
    if not path.is_file():raise AzureBlobError('No se encontró MP4 local')
    if path.suffix.lower()!='.mp4':raise AzureBlobError('Se requiere MP4')
    account_url=os.getenv('AZURE_STORAGE_ACCOUNT_URL','').rstrip('/')
    container=os.getenv('AZURE_BLOB_CONTAINER','recordings')
    if not account_url.startswith('https://') or '.blob.core.windows.net' not in account_url:
        raise AzureBlobError('Configura AZURE_STORAGE_ACCOUNT_URL=https://ACCOUNT.blob.core.windows.net')
    credential=DefaultAzureCredential(exclude_interactive_browser_credential=True)
    storage=BlobServiceClient(account_url=account_url,credential=credential)
    blob_name=f'uploads/{uuid.uuid4().hex}/{path.name[:80]}'
    blob=storage.get_blob_client(container,blob_name)
    with path.open('rb') as fd:
        blob.upload_blob(fd,overwrite=False,content_settings=ContentSettings(content_type='video/mp4'),max_concurrency=4)
    if managed_identity_for_indexer:
        # VI must have Storage Blob Data Reader on the container and MI access configured.
        return {'blob_url':blob.url,'transient_url':blob.url,'managed_identity':True,'blob_name':blob_name}
    start=datetime.now(timezone.utc)-timedelta(minutes=5)
    expiry=datetime.now(timezone.utc)+timedelta(hours=8)
    # Service identity needs Storage Blob Delegator in addition to data write permissions.
    udkey=storage.get_user_delegation_key(key_start_time=start,key_expiry_time=expiry)
    sas=generate_blob_sas(account_name=storage.account_name,container_name=container,blob_name=blob_name,
                          user_delegation_key=udkey,permission=BlobSasPermissions(read=True),
                          start=start,expiry=expiry,protocol='https')
    return {'blob_url':blob.url,'transient_url':f'{blob.url}?{sas}',
            'managed_identity':False,'blob_name':blob_name}
