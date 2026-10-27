"""Isolated SQL/browser fixture: integer BIN slots -> decoded Grafana queries.

Does not connect to controllers or production systems. Requires the existing
local logsis-postgres / logsis-grafana development containers.
"""
import io,json,struct,subprocess,sys,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from logsis_studio.core import Project,available_models,BinDocument


def wire_float(value):
    bits=int.from_bytes(struct.pack('>f',value),'big');wire=(bits&65535)<<16|bits>>16
    return wire if wire<2**31 else wire-2**32


def fixture(project,previous=False):
    values=[]
    for c in project.profile.channels:
        role=c.role;div=c.divisor
        v=1
        if '_v_' in role:v=(380 if role.endswith(('l1l2','l2l3','l3l1')) else 220)*div
        elif role.endswith('_frequency'):v=60*div
        elif '_fp' in role:v=int(.95*div)
        elif '_kw' in role:v=53*div
        elif '_kva' in role and '_kvar' not in role:v=56*div
        elif '_kvar' in role:v=18*div
        elif '_i_' in role:v=80*div
        elif role=='battery':v=24.8*div
        elif role=='rpm':v=1800
        elif role=='coolant':v=82*div
        elif role=='oil_pressure':v=4.5*div
        elif role=='hour_meter':v=99 if previous else 100
        elif role=='hours_hi':v=0
        elif role=='hours_lo':v=99 if previous else 100
        elif role=='hours_minutes':v=0 if previous else 30
        elif role.startswith('energy_') or '_energy_' in role:v=900 if previous else 1000
        elif role.startswith('maintenance_days_'):v=25
        elif role.startswith('maintenance_'):v=48
        elif role.startswith(('alarm_count','alarm_unack','alarm_active_ack','service_alarm_')):v=0
        elif role=='mode_word':v=1<<3
        elif role=='status_word':v=(5<<11)|(1<<8)|(1<<9) if project.profile.application=='SGC420' else (1<<4)|(1<<12)|(1<<6)
        elif role=='service_word':v=0
        elif role=='fail_class_word':v=0
        elif role=='input_word':v=1<<15
        elif role.startswith('alarm_word_'):v=0x1111 if project.profile.application=='SGC420' else 0
        elif role=='mode_manual':v=0
        elif role=='mode_auto':v=1
        if c.codec=='float32_cdab':v=wire_float(v)
        v=int(v)
        values.append(v)
    return values


def query(sql):
    run=subprocess.run(['docker','exec','-i','logsis-postgres','psql','-U','postgres','-d','logsis','-X','-qAt','-v','ON_ERROR_STOP=1'],input='SET jit=off;\n'+sql,text=True,capture_output=True)
    if run.returncode:raise RuntimeError(run.stderr[:5000])
    return [json.loads(x) for x in run.stdout.splitlines() if x.startswith('{')]


def resolve(sql,dashboard,table):
    for v in dashboard['templating']['list']:sql=sql.replace('${'+v['name']+':sqlstring}',"'"+v['query'].replace("'","''")+"'")
    return sql.replace('$Id_Logsis',table).replace('$__timeFilter("time")','"time" BETWEEN \'2026-10-23T12:00Z\' AND \'2026-10-23T13:00Z\'').replace('$__timeFrom()',"'2026-10-23T12:00Z'::timestamptz").replace('$__timeTo()',"'2026-10-23T13:00Z'::timestamptz")


def main():
    report={'result':'pending','scope':'Documental, BIN integer payload and isolated PostgreSQL/Grafana synthetic tests. No physical controller test.','models':[]}
    for model in available_models():
        p=Project.new(model)
        if p.profile.vendor!='DEIF':continue
        table='studio9_'+model.lower();rs={c.role:c for c in p.profile.channels}
        # The exported BIN is also verified, rather than assuming profile ordering.
        with zipfile.ZipFile(io.BytesIO(p.bundle_bytes(table,'Teste '+p.profile.label))) as archive:
            params=BinDocument.from_bytes(archive.read(model+'.bin')).params
            d=json.loads(archive.read(model+'_GRAFANA.json'))
        for c in p.profile.channels:
            assert params[f'MDBA_ADDR{c.index}']==c.params['ADDR']
            assert params[f'MDBA_BIT{c.index}']==c.params['BIT']
        # Dedicated local development tables only, never the user's plants.
        sql='CREATE TABLE IF NOT EXISTS '+table+'(time timestamptz,gsm_rssi numeric,"WiFi_rssi" numeric,'+','.join(c.column+' numeric' for c in p.profile.channels)+');'
        sql+=''.join('ALTER TABLE '+table+' ADD COLUMN IF NOT EXISTS '+c.column+' numeric;' for c in p.profile.channels)
        sql+='TRUNCATE '+table+';'
        for time,previous in [('2026-10-23T11:59Z',True),('2026-10-23T12:30Z',False)]:
            sql+=f"INSERT INTO {table} VALUES ('{time}',-53,-58,"+','.join(map(str,fixture(p,previous)))+');'
        query(sql)
        first=d['panels'][0]['targets'][0]['rawSql']
        result=query('SELECT row_to_json(q) FROM ('+resolve(first,d,table)+') q;')[0]
        assert result['MODE']=='AUTO',(model,result['MODE'])
        assert result['LAST_TIME']=='23/10 09:30',(model,result['LAST_TIME'])
        assert result['GSM']==-53 and result['WIFI']==-58
        assert result['ALARM_LEVEL']==0,(model,result['ALARM_LEVEL'])
        if model=='CGC412':assert result['B1'] is None and result['V_mains'] is None
        if model=='SGC420_MKII':
            assert result['INPUT_A']==1 and result['INPUT_P']==0
            assert result['HOURS']==100.5
        for role in ['gen_kw','load_kw','mains_kw']:
            if role in rs:assert result['MDB'+f'{rs[role].number:02}']==53
        for role in ['gen_kva','load_kva','mains_kva']:
            if role in rs:assert result['MDB'+f'{rs[role].number:02}']==56
        for role in ['gen_kvar','load_kvar','mains_kvar']:
            if role in rs:assert result['MDB'+f'{rs[role].number:02}']==18
        for role in ['energy_gen','energy_mains']:
            if role in rs:
                assert result['MDB'+f'{rs[role].number:02}']==100 if model=='SGC420_MKII' else result['MDB'+f'{rs[role].number:02}']==1000
        results=[]
        for panel in d['panels']:
            if panel['type']=='stat':
                period=query('SELECT row_to_json(q) FROM ('+resolve(panel['targets'][0]['rawSql'],d,table)+') q;')[0]
                expected=1.5 if 'HORAS /' in panel['title'] and model=='SGC420_MKII' else 1 if 'HORAS /' in panel['title'] else 10 if model=='SGC420_MKII' else 100
                assert abs(period['VALUE']-expected)<.0001,(model,panel['title'],period,expected)
                assert period['STATUS']=='OK'
                results.append({'title':panel['title'],'value':period['VALUE']})
            elif panel['type']=='table':query('SELECT row_to_json(q) FROM ('+resolve(panel['targets'][0]['rawSql'],d,table)+') q;')
            for child in panel.get('panels',[]):
                for t in child.get('targets',[]):query('SELECT row_to_json(q) FROM ('+resolve(t['rawSql'],d,table)+') q;')
        # Keep the synthetic fixtures available for responsive-browser tests.
        d['uid']='studio9-'+model.lower().replace('_','-')
        request=urllib.request.Request('http://127.0.0.1:3300/api/dashboards/db',data=json.dumps({'dashboard':d,'overwrite':True}).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request) as response:json.load(response)
        # Null rows/missing optional fields must remain unknown, not healthy.
        unset=','.join(c.column+'=NULL' for c in p.profile.channels)
        null=query('BEGIN;UPDATE '+table+' SET '+unset+';SELECT row_to_json(q) FROM ('+resolve(first,d,table)+') q;ROLLBACK;')[0]
        assert null['MODE']=='SEM DADOS' and null['ALARM_LEVEL'] is None,(model,null['MODE'],null['ALARM_LEVEL'])
        edges=['dados ausentes permanecem desconhecidos']
        def change(changes):
            assignments=','.join(rs[role].column+'='+str(value) for role,value in changes.items())
            return query('BEGIN;UPDATE '+table+' SET '+assignments+';SELECT row_to_json(q) FROM ('+resolve(first,d,table)+') q;ROLLBACK;')[0]
        if model=='SGC420_MKII':
            # Maintenance alone must not paint the generator as an electrical alarm.
            assert change({'alarm_word_76':0x1211,'status_word':(5<<11)|(1<<1)})['ALARM_LEVEL']==0
            assert change({'alarm_word_72':0x1112})['ALARM_LEVEL']==1
            assert change({'alarm_word_72':0x1114})['ALARM_LEVEL']==2
            assert change({'alarm_word_72':0x1113})['ALARM_LEVEL']==3
            c=rs['energy_gen'];alias='MDB'+f'{c.number:02}'
            assert change({'energy_gen':0x00007fc0})[alias] is None
            # A real FLOAT whose CDAB integer is negative must retain its bits.
            rawbits=wire_float(12345.67)
            assert rawbits<0
            expected=struct.unpack('>f',struct.pack('>f',12345.67))[0]/10
            assert abs(change({'energy_gen':rawbits})[alias]-expected)<1e-6
            edges+=['manutenção isolada não colore gerador','warning/trip/shutdown','NaN → nulo','inteiro negativo → bits FLOAT preservados']
        elif 'fail_class_word' in rs:
            assert change({'fail_class_word':2})['ALARM_LEVEL']==1
            if p.profile.application=='GEN':
                assert change({'fail_class_word':1<<2})['ALARM_LEVEL']==2
                assert change({'fail_class_word':1<<4})['ALARM_LEVEL']==3
                assert change({'fail_class_word':2,'alarm_word_1015':1,'service_alarm_1':1})['ALARM_LEVEL']==0
            edges+=['classe de falha nativa','manutenção separada']
        if 'mode_word' in rs and p.profile.application not in ['ATS']:
            manualbit=1 if model.startswith('CGC') else 2
            assert change({'mode_word':(1<<manualbit)|(1<<3)})['MODE']=='INCOERENTE'
            edges+=['modos conflitantes']
        report['models'].append({'model':model,'channels':p.profile.count,'periods':results,'edges':edges,'passed':True})
        print(model,'passed',flush=True)
    report['result']='passed';(ROOT/'LOGSIS_STUDIO_9_VALIDACAO_SQL.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
