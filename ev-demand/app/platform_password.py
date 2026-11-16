"""Self-service password change for global accounts, confirmed by the platform."""
from urllib.parse import urlsplit
import re
import httpx


async def change(access,actor,current,new,client=None):
    if not 8<=len(new)<=200 or new in (current,'12345678'):raise ValueError('Escolha outra senha com 8 a 200 caracteres')
    config=access.config();url=config.get('url','');u=urlsplit(url)
    if not config.get('enabled') or u.scheme!='https' or u.hostname!='script.google.com' or u.port not in (None,443) or u.username or u.password or u.query or u.fragment or not re.fullmatch('/macros/s/[A-Za-z0-9_-]+/exec',u.path):raise ValueError('A troca desta conta exige conexão com a plataforma Google')
    own=client is None
    if own:client=httpx.AsyncClient(timeout=120,follow_redirects=False)
    async def call(action,fields):
        response=await client.post(url,json={'action':action,**fields})
        if response.status_code in (302,303):
            location=response.headers.get('location','');target=urlsplit(location)
            if target.scheme!='https' or target.hostname!='script.googleusercontent.com' or target.port not in (None,443) or target.username or target.password:raise ValueError('Resposta inválida')
            response=await client.get(location)
        response.raise_for_status()
        if len(response.content)>1_000_000:raise ValueError('Resposta inválida')
        data=response.json()
        if data.get('ok') is not True:raise ValueError('Troca não autorizada')
        return data
    try:
        login=await call('desktop_login',{'name':actor['name'],'password':current})
        if login.get('user',{}).get('id')!=actor['id']:raise ValueError('Identidade alterada')
        changed=await call('desktop_change_password',{'token':login['token'],'fields':{'password':new,'confirmation':new}})
        if changed.get('user',{}).get('id')!=actor['id'] or changed['user'].get('must_change'):raise ValueError('Troca não confirmada')
        with access.db:
            access.revoke(actor['name'])
            access.db.execute('DELETE FROM account_leases WHERE user_id=?',(actor['id'],))
        try:await call('desktop_logout',{'token':changed['token']})
        except (ValueError,httpx.HTTPError,KeyError,TypeError):pass
    except (ValueError,httpx.HTTPError,KeyError,TypeError):raise ValueError('Não foi possível confirmar a troca na plataforma. Confira a senha atual e a conexão.') from None
    finally:
        if own:await client.aclose()
