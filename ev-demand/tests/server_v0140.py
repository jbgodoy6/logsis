"""Local browser fixture; never run as a production entry point."""
import time
from fastapi import HTTPException,Request
from app.main import create_app
from app.store import password_hash
from app import curve
application=create_app(':memory:',background=False,root_password_hash=password_hash('fixture-root-password'))
@application.post('/fixture/accounts')
async def accounts(request:Request):
    if not application.state.access.session(request.cookies.get('ev_session')):raise HTTPException(401)
    application.state.access.apply_snapshot([dict(id='sales-test',name='sales.test',full_name='Comercial teste',role='commercial',password=password_hash('fixture-sales-password'),active=True,deleted=False,expires_at=None,must_change=False,credential_version=1,meta_version=1)],scopes=('developer','commercial'))
    return {'ok':True}
@application.post('/fixture/peak')
async def peak(request:Request):
    user=application.state.access.session(request.cookies.get('ev_session'))
    if not user or user['role']!='root':raise HTTPException(403)
    store=application.state.store;settings=store.settings();now=time.time()
    store._curve_last={}
    curve.record(store,now-.5,dict(at=now-.5,total_kw=100),0,True,settings)
    curve.record(store,now,dict(at=now,total_kw=777),0,True,settings)
    return {'revision':store._curve_revision}
