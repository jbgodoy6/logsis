"""Root-triggered remote directory query; never runs in background sync."""
import math
import time
from urllib.parse import urlsplit
import httpx
from .remote_tunnel import valid_url

class DirectoryUnavailable(ValueError):pass

async def fetch(access,client=None):
    config=access.config();token=access.device_token()
    if not config['enabled'] or not config['url'] or not token:
        raise DirectoryUnavailable('Configure a plataforma e a chave deste D-Max em Técnicos globais.')
    url=config['url'].rstrip('/')
    if urlsplit(url).hostname!='script.google.com':
        raise DirectoryUnavailable('A busca de clientes exige a implantação Google Apps Script atualizada.')
    own=client is None
    if own:client=httpx.AsyncClient(timeout=15,follow_redirects=False)
    try:
        response=await client.post(url,json=dict(action='remote_directory',controller_id=access.store.entities('system')[0]['controller_id'],key=token))
        if response.status_code in (302,303):
            target=urlsplit(response.headers.get('location',''))
            if target.scheme!='https' or target.hostname!='script.googleusercontent.com' or target.username or target.password or target.port not in (None,443):
                raise ValueError('Redirect recusado')
            response=await client.get(response.headers['location'])
        response.raise_for_status()
        if len(response.content)>1_000_000:raise ValueError('Resposta muito grande')
        data=response.json()
        if data.get('ok') is not True:
            if data.get('code')==403:
                raise DirectoryUnavailable('Autorize este equipamento no menu D-Max → Permitir busca de clientes remotos da planilha.')
            raise DirectoryUnavailable('Atualize a implantação do Apps Script e confira a autorização deste equipamento.')
        records=data.get('clients')
        if not isinstance(records,list) or len(records)>1000:raise ValueError('Lista inválida')
        result=[];seen=set()
        for row in records:
            identifier=row.get('controller_id');name=row.get('site_name');url=row.get('url');stamp=row.get('updated_at');connected=row.get('connected')
            if not isinstance(identifier,str) or not identifier or len(identifier)>100 or identifier in seen:raise ValueError('Identidade inválida')
            if not isinstance(name,str) or not name.strip() or len(name)>100:raise ValueError('Nome inválido')
            if not valid_url(url) or urlsplit(url).hostname.endswith('.tunnl.gg'):raise ValueError('URL inválida')
            if type(stamp) not in (float,int) or not math.isfinite(stamp) or stamp<1 or stamp>time.time()+300 or type(connected) is not bool:raise ValueError('Estado inválido')
            seen.add(identifier);result.append(dict(controller_id=identifier,site_name=name,url=url,updated_at=stamp,connected=connected))
        return dict(clients=sorted(result,key=lambda r:(r['site_name'].casefold(),r['controller_id'])),fetched_at=time.time())
    except DirectoryUnavailable:raise
    except (httpx.HTTPError,ValueError,TypeError,AttributeError):
        raise DirectoryUnavailable('Não foi possível atualizar os clientes. Confira a plataforma e tente abrir esta aba novamente.') from None
    finally:
        if own:await client.aclose()
