"""Redeem a short-lived, device-bound pass; never receive the central session/password."""
import re
from urllib.parse import urlsplit
import httpx


async def redeem(access, ticket, client=None):
    config=access.config();key=access.device_token()
    if not isinstance(ticket,str) or not re.fullmatch('[0-9a-f]{64}',ticket):
        raise ValueError('Passe inválido ou expirado. Abra novamente pela central Windows.')
    url=config.get('url','');parsed=urlsplit(url)
    if not config.get('enabled') or not key or parsed.scheme!='https' or parsed.hostname!='script.google.com' or parsed.port not in (None,443) or parsed.username or parsed.password or parsed.query or parsed.fragment or not re.fullmatch('/macros/s/[A-Za-z0-9_-]+/exec',parsed.path):
        raise ValueError('Configure a plataforma Google e a chave deste D-Max para usar a entrada pela central.')
    own=client is None
    if own:client=httpx.AsyncClient(timeout=30,follow_redirects=False)
    try:
        response=await client.post(url,json={'action':'redeem_login','controller_id':access.store.entities('system')[0]['controller_id'],'key':key,'ticket':ticket})
        if response.status_code in (302,303):
            location=response.headers.get('location','');target=urlsplit(location)
            if target.scheme!='https' or target.hostname!='script.googleusercontent.com' or target.port not in (None,443) or target.username or target.password:raise ValueError('Redirecionamento inválido')
            response=await client.get(location)
        response.raise_for_status()
        if len(response.content)>5_000_000:raise ValueError('Resposta inválida')
        data=response.json();actor=data.get('user',{});snapshot=data.get('snapshot',{})
        if data.get('ok') is not True or snapshot.get('complete') is not True or actor.get('role') not in ('developer','commercial','technician'):raise ValueError('Acesso não autorizado')
        records=snapshot['technicians']+snapshot['accounts']
        match=next((r for r in records if r.get('id')==actor.get('id')),None)
        if not match or any(match.get(k)!=actor.get(k) for k in ('name','role','active','deleted','expires_at')) or not match.get('active') or match.get('deleted') or match.get('must_change'):raise ValueError('Acesso alterado')
        access.apply_snapshot(records,scopes=('technician','developer','commercial'))
        row=access.by_id(actor['id'])
        if not access.usable(row) or row['source']!='directory' or row['must_change']:raise ValueError('Conta indisponível')
        return row
    except (httpx.HTTPError,ValueError,KeyError,TypeError,StopIteration):
        raise ValueError('Não foi possível validar a entrada. Abra o cliente novamente pela central Windows.') from None
    finally:
        if own:await client.aclose()
