"""A tested charging setpoint is a minimum candidate; a low meter sample is not."""
import math
import time


def context(charger, port):
    return {k:charger.get(k,default) for k,default in (
        ('id',''),('model',''),('transport',''),('charge_type','unknown'),('rate_unit','W'),
        ('voltage',230),('phases',3),('max_kw',0),('connector_max_kw',0),('min_kw',0)
    )}|{'firmware':port.get('firmware',''),'serial':port.get('serial','')}


def key(port):
    return port['key']+'|'+str(port.get('vehicle_id') or '')


def electrical_floor(charger):
    if charger.get('charge_type')=='AC':
        return 6*charger['voltage']*charger['phases']/1000
    return 0.0


def effective_minimum(store,charger,port):
    record=store.get('minimum',key(port))
    floor=electrical_floor(charger)
    learned=record and not record.get('needs_revalidation') and record.get('context')==context(charger,port) and record.get('minimum_kw')
    if not isinstance(learned,(float,int)) or not math.isfinite(learned) or learned<=0:
        learned=None
    if learned and charger.get('charge_type')=='DC' and charger.get('rate_unit')=='A':
        amps=record.get('minimum_a')
        fresh=0<=time.time()-port.get('voltage_at',0)<=store.settings()['freshness_s']
        if not amps or not fresh or not port.get('voltage_v'):learned=None
        else:learned=max(learned,amps*port['voltage_v']/1000)
    minimum=max(floor,learned if learned is not None else charger['min_kw'])
    return minimum,learned


def evaluate(test,charger,port,now,freshness):
    cap=test['cap_kw'];accepted=test.get('accepted_at')
    if cap<.001:return False,'zero ou valor abaixo da resolução não define mínimo de recarga'
    if charger.get('charge_type') not in ('AC','DC'):return False,'informe AC ou DC antes de memorizar'
    if cap+1e-6<electrical_floor(charger):return False,'abaixo da referência de 6 A para AC'
    if not accepted or test.get('interrupted'):return False,'limite não sustentado ou comando não aceito'
    if test.get('context')!=context(charger,port):return False,'configuração, firmware ou equipamento mudou'
    if not port['running'] or not port['connected'] or port.get('session_id')!=test.get('session_id') or port.get('vehicle_id')!=test.get('vehicle_id'):
        return False,'sessão ou veículo mudou'
    if charger['transport']=='ocpp' and (port.get('ocpp_status')!='Charging' or port.get('error_code','NoError')!='NoError'):
        return False,'carregador não confirmou recarga sem falhas'
    values=[s for s in test['observations'] if s['at']>=accepted+5]
    if len(values)<3 or values[-1]['at']-values[0]['at']<10 or not 0<=now-values[-1]['at']<=freshness:
        return False,'sem três medições atuais e estáveis após acomodação'
    if charger.get('charge_type')=='DC' and charger.get('rate_unit')=='A':
        tail=values[-3:];amps=port.get('accepted_profile_current_a')
        if not amps or tail[0]['at']<port.get('accepted_profile_at',accepted)+5 or tail[-1]['at']-tail[0]['at']<10 or any(s.get('amps')!=amps for s in tail):
            return False,'corrente DC ainda não estabilizada no perfil confirmado'
    tolerance=cap*.1+.001
    if any(not s.get('valid',False) or s['kw']<cap*.8 or s['kw']>cap+tolerance for s in values):
        return False,'potência não sustentou o limite de teste'
    return True,'menor limite testado e sustentado; não é estimativa pela menor leitura'
