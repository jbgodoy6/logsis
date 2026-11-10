"""Durable, credential-free device metadata piggybacked on authenticated directory sync."""
import asyncio
import time
from .remote_tunnel import public_status,valid_url

def outgoing(access):
    status=public_status()
    url=status.get('url')
    if not url or not valid_url(url) or '.trycloudflare.com' not in url:return None
    previous=access.store.get('remote_registration','current') or {'id':'current','revision':0,'ack_revision':0}
    metadata=dict(site_name=access.store.settings()['site_name'],url=url,connected=bool(status['connected']),
                  heartbeat_at=status.get('heartbeat_at'),provider='cloudflare')
    if metadata!=previous.get('metadata'):
        previous.update(revision=previous['revision']+1,metadata=metadata)
        access.store.put('remote_registration',previous)
    return dict(metadata,revision=previous['revision'])

def acknowledge(access,sent,ack):
    if not sent or not isinstance(ack,dict) or type(ack.get('revision')) is not int:return
    current=access.store.get('remote_registration','current')
    if not current:return
    if ack['revision']>current['revision']:
        # Recovery of an old database must not overwrite a more recent server row.
        current['revision']=ack['revision']
    if ack.get('accepted') is False and ack['revision']>=sent['revision']:
        current['revision']=max(current['revision'],ack['revision'])+1
    if ack.get('accepted') is True and ack['revision']==sent['revision']:
        current.update(ack_revision=sent['revision'],published_at=time.time(),published_url=sent['url'])
    access.store.put('remote_registration',current)

async def watch(access):
    previous=None
    while True:
        state=public_status();current=(state.get('url'),state.get('connected'))
        if current!=previous:
            previous=current
            if state.get('url') and access.wakeup:access.wakeup.set()
        await asyncio.sleep(5)

def publication(access):
    row=access.store.get('remote_registration','current') or {}
    return dict(published_at=row.get('published_at'),published_url=row.get('published_url'),
                pending=bool(row.get('revision',0)>row.get('ack_revision',0)),
                directory_enabled=bool(access.config()['enabled']))
