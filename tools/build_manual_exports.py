"""Build reviewable manual-model dashboards and a cross-reference CSV."""
from pathlib import Path
import csv,io,json,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from logsis_studio.core import Project,available_models
folder=ROOT/'CONTROLADORES_MANUAL_M1';folder.mkdir(exist_ok=True)
output=io.StringIO(newline='');writer=csv.writer(output,delimiter=';',lineterminator='\n')
writer.writerow(['Modelo','Nome','Família manual','MDB','Índice BIN','Coluna SQL','Medição','Função lógica','Endereço','FNC LogSis','Bit zero-based','Divisor','Unidade','Base'])
with zipfile.ZipFile(ROOT/'LOGSIS_CONTROLADORES_MANUAL_M1.zip','w',zipfile.ZIP_DEFLATED) as archive:
 for model in available_models():
  p=Project.new(model)
  if p.profile.kind=='legacy':continue
  d=p.dashboard('id_'+model.lower(),p.profile.label,'zKW_ld27k',p.dashboard_template()['uid'])
  serialized=json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
  name=model+'_M1.json';(folder/name).write_text(serialized);archive.writestr(name,serialized)
  archive.writestr(model+'_MAPA.csv',p.csv_bytes())
  for c in p.profile.channels:writer.writerow([model,p.profile.label,p.profile.manual_family,f'MDB{c.number:02}',c.index,c.column,c.name,c.role,c.params['ADDR'],c.params['FNC'],c.params['BIT'],c.divisor,c.unit,'GenComm 2.93; conforme família, disponibilidade por firmware'])
 content=('\ufeff'+output.getvalue()).encode('utf-8')
 (ROOT/'LOGSIS_STUDIO_8_MAPA_MANUAL.csv').write_bytes(content);archive.writestr('MAPA_COMPLETO.csv',content)
 archive.writestr('LEIA-ME.txt','Dashboards M1 conforme o manual GenComm 2.93. Defina Id_Logsis e o datasource da sua planta. Para implantar, prefira exportar BIN + Grafana pelo LogSis Studio 8; cada JSON corresponde ao mapa do seu modelo. LEDs não são retorno físico de disjuntor. Recursos dependem do equipamento/firmware.\n')
print('7 modelos e mapa CSV exportados')
