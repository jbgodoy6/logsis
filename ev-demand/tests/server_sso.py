"""Loopback browser fixture; Google and device credentials are fictitious."""
import json
import httpx
from app.main import create_app
from app.store import password_hash

application=create_app(':memory:',background=False,root_password_hash=password_hash('fixture-root-pass'))
access=application.state.access
access.configure({'enabled':True,'url':'https://script.google.com/macros/s/fixture/exec','interval_s':300})
access.set_device_token('fixture-device-key')
actor=dict(id='SSO-DEV',name='sso.dev',full_name='Desenvolvedor SSO',role='developer',active=True,deleted=False,expires_at=None,password=password_hash('fixture-sso-pass'),must_change=False,activation_hash=None,credential_version=1,meta_version=1)
used=False
def transport(request):
    global used
    data=json.loads(request.content)
    if used or data.get('ticket')!='a'*64:return httpx.Response(200,json={'ok':False,'code':401})
    used=True
    public={k:actor[k] for k in ('id','name','full_name','role','active','deleted','expires_at')}
    return httpx.Response(200,json={'ok':True,'user':public,'snapshot':{'complete':True,'technicians':[],'accounts':[actor]}})
application.state.sso_client=httpx.AsyncClient(transport=httpx.MockTransport(transport))
