"""Generate a device-specific token and owner SQL locally. Prints no secrets."""
import argparse
import hashlib
from pathlib import Path
import re
import secrets

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--id',required=True,help='Identificador mostrado em Configurações > Integração com a nuvem')
p.add_argument('--site',required=True)
p.add_argument('--output',type=Path,default=Path('credenciais-dmax'))
a=p.parse_args()
if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',a.id) or not 1 <= len(a.site) <= 100:
    p.error('Identificador ou nome inválido')
a.output.mkdir(mode=0o700,parents=True,exist_ok=False)
token=secrets.token_urlsafe(32);password=secrets.token_urlsafe(24)
site=a.site.replace("'","''")
files={
 'token-controlador.env':'EV_CLOUD_TOKEN='+token+'\n',
 'cadastrar-controlador.sql':"insert into dmax.controllers(id,site_name,token_hash) values ('"+a.id+"','"+site+"','"+hashlib.sha256(token.encode()).hexdigest()+"');\n",
 'grafana-leitura.sql':"create role dmax_viewer login password '"+password+"';\ngrant usage on schema dmax to dmax_viewer;\ngrant select on dmax.v_sites,dmax.v_ports,dmax.v_meter,dmax.minutes,dmax.events to dmax_viewer;\ncreate policy viewer_minutes on dmax.minutes for select to dmax_viewer using (true);\ncreate policy viewer_events on dmax.events for select to dmax_viewer using (true);\n",
 'senha-grafana-banco.txt':password+'\n'}
for name,text in files.items():
    f=a.output/name;f.write_text(text);f.chmod(0o600)
print('Credenciais exclusivas salvas em '+str(a.output.resolve())+'. Não publique essa pasta nem envie os arquivos no chat.')
