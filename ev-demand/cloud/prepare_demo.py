"""Prepare an isolated PostgreSQL + Grafana demo with fresh random credentials."""
from pathlib import Path
import json
import os
import secrets
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.plant_demo import fixture, preview
from app.telemetry import plant_snapshot

root=Path(__file__).resolve().parent
(root/'grafana').chmod(0o755)
(root/'grafana/assets').chmod(0o755)
for asset in (root/'grafana/assets').iterdir(): asset.chmod(0o644)
(root/'grafana/dmax-planta.json').chmod(0o644)
private=root/'.demo'
if private.exists():
    raise SystemExit('Pasta .demo já existe. Preserve suas senhas; use docker compose up sem executar novamente este preparo.')
private.mkdir(mode=0o700)
password=secrets.token_hex(24);viewer=secrets.token_hex(24);admin=secrets.token_urlsafe(24);token=secrets.token_urlsafe(32)
for name,value in [('postgres-password',password),('grafana-password',admin)]:
    f=private/name;f.write_text(value);f.chmod(0o444)
(private/'environment').write_text('DEMO_POSTGRES_PASSWORD='+password+'\n')
(private/'environment').chmod(0o600)
plant=plant_snapshot(fixture());payload=json.dumps(plant,ensure_ascii=False).replace("'","''")
init="create role anon; create role authenticated; create role service_role;\n"
init+=(root/'supabase/schema.sql').read_text()
init+="\ncreate role dmax_viewer login password '"+viewer+"';\ngrant usage on schema dmax to dmax_viewer;\ngrant select on dmax.v_sites,dmax.v_ports,dmax.v_meter,dmax.minutes,dmax.events to dmax_viewer;\n"
# Table RLS on minutes/events has no implicit public policies.
init+="create policy viewer_minutes on dmax.minutes for select to dmax_viewer using (true);\ncreate policy viewer_events on dmax.events for select to dmax_viewer using (true);\n"
init+="insert into dmax.controllers(id,site_name,token_hash) values ('demo-energycube','DEMONSTRAÇÃO',encode(sha256(convert_to('"+token+"','UTF8')),'hex'));\n"
init+="select public.dmax_ingest('demo-energycube','"+token+"','"+json.dumps([dict(id=secrets.token_hex(16),ts=time.time(),kind='plant_state',payload=plant)],ensure_ascii=False).replace("'","''")+"'::jsonb);\n"
(private/'init.sql').write_text(init)
(private/'datasource.yaml').write_text('''apiVersion: 1
datasources:
  - name: D-Max PostgreSQL
    uid: dmax-pg
    type: grafana-postgresql-datasource
    access: proxy
    url: postgres:5432
    user: dmax_viewer
    isDefault: true
    jsonData:
      database: dmax
      sslmode: disable
      postgresVersion: 1600
      timescaledb: false
    secureJsonData:
      password: '''+viewer+'\n')
(private/'dashboard.yaml').write_text('''apiVersion: 1
providers:
  - name: D-Max
    folder: EnergyCube
    type: file
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dmax-dashboards
''')
(private/'feed.sql').write_text("""update dmax.controllers set last_contact_at=now(),observed_at=now(),plant=jsonb_set(plant,'{observed_at}',to_jsonb(extract(epoch from now())::double precision)) where id='demo-energycube';
insert into dmax.minutes select 'demo-energycube','site',date_trunc('minute',now()),847.2,820.5,865.4,14.12 on conflict do nothing;
""")
for f in private.iterdir():
    if f.name not in ('environment',): f.chmod(0o444)
preview(root/'previa-planta.html')
print('Demo preparada. Senha do Grafana salva em cloud/.demo/grafana-password. Usuário: admin. Não publique a pasta .demo.')
