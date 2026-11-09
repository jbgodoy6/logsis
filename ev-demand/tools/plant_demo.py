"""Synthetic showroom fixture. Never imported by the running controller."""
from pathlib import Path
import base64
import json
import time
import sys
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.plant_view import render_plant
from app.telemetry import plant_snapshot


def fixture():
    now=time.time()
    state=dict(time=now,settings=dict(site_name='EnergyCube · Garagem corporativa',mode='simulation',limit_kw=1200.0,margin_kw=60.0,freshness_s=15),
       vehicles=[dict(id='v1',name='BYD Dolphin · Frota 07'),dict(id='v2',name='Volvo EX30 · Diretoria'),dict(id='v3',name='Renault Kwid E-Tech · Frota 12')],
       sessions=[dict(id='s1',energy_kwh=42.8),dict(id='s2',energy_kwh=8.6)],
       meter=dict(at=now,total_kw=847.2,readings=[dict(measurement=m,label=l,unit=u,value=v,at=now,error='') for m,l,u,v in [
        ('power_total_kw','Potência ativa total','kW',847.2),('voltage_l1_v','Tensão L1–N','V',220.4),
        ('current_l1_a','Corrente L1','A',1284.6),('frequency_hz','Frequência','Hz',60.01),('power_factor','Fator de potência','',0.98),('energy_import_kwh','Energia importada','kWh',184523.8)]]),
       summary=dict(ev_kw=65.5,other_kw=781.7),fault='',chargers=[],ports=[])
    for i,(name,online,plugged,running,alarm,power,vehicle) in enumerate([
        ('Estação 01 · Entrada',True,True,True,False,65.5,'v1'),
        ('Estação 02 · Diretoria',True,True,False,True,0.0,'v2'),
        ('Estação 03 · Visitantes',False,False,False,False,0.0,None),
        ('Estação 04 · Expansão',True,False,False,False,0.0,None),
        ('Estação 05 · Frota',True,True,False,False,0.0,'v3')],1):
        cid=f'EC-{i:02}'
        state['chargers'].append(dict(id=cid,name=name,max_kw=320.0,enabled=True,online=online))
        state['ports'].append(dict(key=cid+':1',charger=cid,connector=1,connected=plugged,running=running,
            ocpp_status='Faulted' if alarm else 'Charging' if running else 'Available',error_code='GroundFailure' if alarm else 'NoError',
            sample_at=now,power_kw=power,limit_kw=200.0 if running else 0.0,vehicle_id=vehicle,
            session_id='s1' if i==1 else 's2' if i==2 else None,soc=64 if running else None))
    return state


def preview(output):
    root=Path(__file__).resolve().parents[1]
    state=fixture()
    css=(root/'app/static/plant.css').read_text()
    logo=base64.b64encode((root/'app/static/d-max-logo.png').read_bytes()).decode()
    html='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>D-Max · Prévia da planta</title><style>*{box-sizing:border-box}body{margin:0;background:#f3f6fa;font-family:Arial,sans-serif}.demo-bar{display:flex;align-items:center;justify-content:space-between;padding:14px 35px;background:#092a4b;color:#caddec;font-size:12px}.demo-bar img{width:160px;background:white;border-radius:9px;padding:8px}.demo-main{max-width:1480px;margin:auto;padding:30px}.demo-bar b{color:#ffc627}</style><style>'''+css+'''</style><div class="demo-bar"><img alt="D-Max by EnergyCube" src="data:image/png;base64,'''+logo+'''"><span><b>DEMONSTRAÇÃO</b> · Dados fictícios para avaliação visual</span></div><main class="demo-main">'''+render_plant(state)+'</main></html>'
    Path(output).write_text(html)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='cloud/previa-planta.html');args=parser.parse_args()
    preview(args.output)
