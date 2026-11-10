"""Isolated browser fixture; never shipped in runtime ZIPs. Run with random fixture keys."""
import os
import sys
import secrets
import time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi import Request, HTTPException
from serial.tools import list_ports
from app.main import create_app
from app.store import password_hash
from app.telemetry import MEASUREMENTS
import app.main
import app.services
from test_v090 import envelope, TOKEN, NOTICE_SECONDS
import uvicorn

if not os.environ.get('DMAX_TEST_ROOT') or not os.environ.get('DMAX_TEST_DBPATH'):
    raise RuntimeError('Use o executor de testes com credenciais e banco efêmeros')
list_ports.comports=lambda:[SimpleNamespace(device='/dev/ttyUSB0',description='FT232R USB UART')]
async def read(config):
    values={'power_total_kw':200,'energy_import_kwh':1605,'current_l1_a':120,'current_l2_a':118,'current_l3_a':119,
            'voltage_l1_v':230,'voltage_l2_v':231,'voltage_l3_v':229,'frequency_hz':59.99,'power_factor':.99,
            'power_l1_kw':67,'power_l2_kw':66,'power_l3_kw':67}
    return [dict(measurement=r['measurement'],label=MEASUREMENTS[r['measurement']][0],unit=MEASUREMENTS[r['measurement']][1],
                 value=values[r['measurement']],at=time.time(),error=None) for r in config['registers'] if r['enabled']]
app.main.read_meter=read;app.services.read_meter=read
application=create_app(os.environ['DMAX_TEST_DBPATH'],root_password_hash=password_hash(os.environ['DMAX_TEST_ROOT']))

@application.post('/fixture/{action}')
async def fixture(action:str, request:Request):
    if not secrets.compare_digest(request.headers.get('X-Fixture-Key',''),os.environ['DMAX_TEST_ROOT']):
        raise HTTPException(403)
    data=await request.json();engine=application.state.engine;store=application.state.store
    if action=='notice':
        state=data['state'];revision=data['revision']
        issued=time.time()-NOTICE_SECONDS-1 if state=='expired' else time.time()
        return engine.subscription.receive(envelope(store,state='regular' if state=='regular' else 'pending',revision=revision,issued=issued),TOKEN)
    if action=='remote-catalog':
        import app.remote_clients
        application.state.catalog_count=getattr(application.state,'catalog_count',0)
        if data.get('query'):return {'count':application.state.catalog_count}
        application.state.catalog_url=data.get('url','https://cliente-um.trycloudflare.com')
        async def catalog(access,client=None):
            application.state.catalog_count+=1
            return dict(clients=[dict(controller_id='CLIENTE-UM',site_name='Cliente Um · Garagem',url=application.state.catalog_url,updated_at=time.time(),connected=True)],fetched_at=time.time())
        app.remote_clients.fetch=catalog
        return {'ok':True}
    if action=='curve':
        now=time.time()
        with store.db:
            store.db.execute('DELETE FROM curve_points')
            for n in range(100):
                for mode in ('physical','simulation'):
                    store.db.execute('INSERT INTO curve_points VALUES (?,?,?,?,?,?,?,?)',(now-600+n*5,mode,500+100*__import__('math').sin(n/8),100+30*__import__('math').cos(n/10),400+100*__import__('math').sin(n/8)-30*__import__('math').cos(n/10),900,now-600+n*5,'valid'))
        return {'now':now}
    if action=='sessions':
        store.put('vehicle',dict(id='PDF-TEST',name='Veículo teste PDF',plate='TESTE',identifiers=[],priority=False))
        cid=store.entities('charger')[0]['id']
        for n in range(25):
            store.put('session',dict(id='PDF-'+str(n),port=cid+':1',vehicle_id='PDF-TEST',started_at=1794236400+n*3600,
                ended_at=1794238200+n*3600,energy_kwh=10.125,peak_kw=320,mode='simulator',quality='measured'))
        return {'ok':True}
    raise HTTPException(404)

if __name__=='__main__':uvicorn.run(application,host='127.0.0.1',port=8111,log_level='warning')
