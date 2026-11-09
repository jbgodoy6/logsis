-- Execute once as the project owner in Supabase SQL Editor. No public read access.
create schema if not exists dmax;
revoke all on schema dmax from public, anon, authenticated;
create table if not exists dmax.controllers (
 id text primary key, site_name text not null, token_hash text not null,
 enabled boolean not null default true, last_contact_at timestamptz,
 observed_at timestamptz, plant jsonb
);
create table if not exists dmax.chargers (
 controller_id text not null references dmax.controllers(id), id text not null,
 name text not null, max_kw double precision not null, registered boolean not null default true,
 primary key(controller_id,id)
);
create table if not exists dmax.minutes (
 controller_id text not null references dmax.controllers(id), source text not null, time timestamptz not null,
 avg_kw double precision, min_kw double precision, max_kw double precision, energy_kwh double precision,
 primary key(controller_id,source,time)
);
create table if not exists dmax.events (
 controller_id text not null references dmax.controllers(id), id text not null,
 time timestamptz not null, kind text not null, payload jsonb not null,
 primary key(controller_id,id)
);
create index if not exists minutes_time on dmax.minutes(time);
create index if not exists events_time on dmax.events(time);
alter table dmax.controllers enable row level security;
alter table dmax.chargers enable row level security;
alter table dmax.minutes enable row level security;
alter table dmax.events enable row level security;

create or replace function public.dmax_ingest(p_controller text, p_token text, p_records jsonb)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
 c dmax.controllers%rowtype; r jsonb; p jsonb; item jsonb; ack jsonb := '[]'; observed timestamptz;
begin
 if p_token is null or p_controller is null or length(p_token) < 32 or length(p_token) > 512 or p_controller !~ '^[A-Za-z0-9_-]{1,100}$' then
  raise exception 'Unauthorized' using errcode='28000';
 end if;
 select * into c from dmax.controllers where id=p_controller for update;
 if not found or not c.enabled or c.token_hash <> encode(sha256(convert_to(p_token,'UTF8')),'hex') then
  raise exception 'Unauthorized' using errcode='28000';
 end if;
 if coalesce(jsonb_typeof(p_records),'') <> 'array' or jsonb_array_length(p_records) > 200 then
  raise exception 'Invalid batch';
 end if;
 for r in select value from jsonb_array_elements(p_records) loop
  if r->>'id' is null or r->>'id' !~ '^[0-9a-f]{32}$' or jsonb_typeof(r->'payload') <> 'object'
     or jsonb_typeof(r->'ts') <> 'number' or length(r->>'kind') > 80 then raise exception 'Invalid record'; end if;
  p := r->'payload';
  if r->>'kind'='plant_state' then
   if coalesce(p->>'schema_version','') <> '1' or jsonb_typeof(p->'chargers') <> 'array' or jsonb_array_length(p->'chargers') > 60
    or jsonb_typeof(p->'meter'->'readings') <> 'array' or jsonb_array_length(p->'meter'->'readings') > 32
    or length(p->>'site_name') > 100 then raise exception 'Invalid plant'; end if;
   observed := to_timestamp((p->>'observed_at')::double precision);
   if observed > now()+interval '5 minutes' then raise exception 'Clock ahead'; end if;
   if c.observed_at is null or observed >= c.observed_at then
    update dmax.controllers set plant=p, site_name=p->>'site_name', observed_at=observed where id=p_controller;
    update dmax.chargers set registered=false where controller_id=p_controller;
    for item in select value from jsonb_array_elements(p->'chargers') loop
     if item->>'id' is null or length(item->>'id') > 100 or length(item->>'name') > 100
       or jsonb_typeof(item->'connectors') <> 'array' or jsonb_array_length(item->'connectors') > 8
       then raise exception 'Invalid charger'; end if;
     insert into dmax.chargers(controller_id,id,name,max_kw) values(p_controller,item->>'id',item->>'name',(item->>'max_kw')::double precision)
      on conflict(controller_id,id) do update set name=excluded.name,max_kw=excluded.max_kw,registered=true;
    end loop;
    c.observed_at := observed;
   end if;
  elsif r->>'kind'='minute' then
   insert into dmax.minutes values(p_controller,p->>'source',to_timestamp((p->>'minute_utc')::double precision),
    (p->>'avg_kw')::double precision,(p->>'min_kw')::double precision,(p->>'max_kw')::double precision,(p->>'energy_kwh')::double precision)
    on conflict do nothing;
  elsif r->>'kind' in ('session_start','session_end','connected','disconnected','ocpp_status','ocpp_boot','ocpp_connected','ocpp_disconnected','limit_changed','reconciliation_required','session_reconciled') then
   insert into dmax.events values(p_controller,r->>'id',to_timestamp((r->>'ts')::double precision),r->>'kind',p) on conflict do nothing;
  elsif r->>'kind' <> 'local_audit' then
   raise exception 'Unknown record type';
  end if;
  ack := ack || jsonb_build_array(r->>'id');
 end loop;
 update dmax.controllers set last_contact_at=now() where id=p_controller;
 return jsonb_build_object('acknowledged_ids',ack);
end $$;
revoke all on function public.dmax_ingest(text,text,jsonb) from public,anon,authenticated;
grant execute on function public.dmax_ingest(text,text,jsonb) to service_role;

-- Grafana only receives views. token_hash is never exposed.
create or replace view dmax.v_sites as
 select id as controller_id,site_name,last_contact_at,observed_at,
 coalesce(enabled and last_contact_at > now()-interval '150 seconds' and observed_at > now()-interval '150 seconds',false) as controller_online,
 (plant->>'limit_kw')::double precision as limit_kw,(plant->>'margin_kw')::double precision as margin_kw,
 (plant->>'ev_kw')::double precision as ev_kw,(plant->>'other_kw')::double precision as other_kw,
 plant->>'mode' as mode from dmax.controllers;
create or replace view dmax.v_ports as
 select c.id as controller_id,c.site_name,ch.id as charger_id,ch.name as charger_name,ch.max_kw,
 port->>'id' as port_id,(port->>'connector')::integer as connector,
 s.controller_online, coalesce((port->>'online')::boolean,false) and s.controller_online as online,
 case when not s.controller_online then 'Dados desatualizados'
  when not coalesce((port->>'online')::boolean,false) then 'Offline' else port->>'status' end as status,
 coalesce((port->>'alarm')::boolean,false) as alarm,
 case when coalesce((port->>'alarm')::boolean,false) then 2 when not s.controller_online or not coalesce((port->>'online')::boolean,false) then 0 else 1 end as equipment_state,
 case when s.controller_online and coalesce((port->>'online')::boolean,false) and coalesce((port->>'plugged')::boolean,false) then 1 else 0 end as vehicle_state,
 coalesce(port->>'vehicle_name','Veículo não identificado') as vehicle_name,port->>'vehicle_id' as vehicle_id,
 (port->>'plugged')::boolean as last_plugged,port->>'error_code' as error_code,
 case when s.controller_online and (port->>'online')::boolean then (port->>'power_kw')::double precision end as power_kw,
 (port->>'limit_kw')::double precision as applied_kw,(port->>'energy_kwh')::double precision as energy_kwh,
 (port->>'soc')::double precision as soc,to_timestamp((port->>'sample_at')::double precision) as sampled_at,
 c.last_contact_at,c.observed_at
 from dmax.controllers c join dmax.v_sites s on s.controller_id=c.id
 cross join lateral jsonb_array_elements(coalesce(c.plant->'chargers','[]')) charger
 join dmax.chargers ch on ch.controller_id=c.id and ch.id=charger->>'id' and ch.registered
 cross join lateral jsonb_array_elements(charger->'connectors') port;
create or replace view dmax.v_meter as
 select c.id as controller_id,c.site_name,r->>'measurement' as measurement,r->>'label' as label,r->>'unit' as unit,
 s.controller_online and coalesce((c.plant->'meter'->>'fresh')::boolean,false) and not coalesce((r->>'error')::boolean,true) as fresh,
 case when s.controller_online and (c.plant->'meter'->>'fresh')::boolean and not (r->>'error')::boolean then (r->>'value')::double precision end as value,
 to_timestamp((r->>'at')::double precision) as sampled_at,c.observed_at
 from dmax.controllers c join dmax.v_sites s on s.controller_id=c.id
 cross join lateral jsonb_array_elements(coalesce(c.plant->'meter'->'readings','[]')) r;

-- Run daily via Supabase Cron (SQL below in guide). Limit raw retention for free-tier pilots.
create or replace function public.dmax_cleanup() returns void language sql security definer set search_path='' as $$
 delete from dmax.minutes where time < now()-interval '7 days';
 delete from dmax.events where time < now()-interval '30 days';
$$;
revoke all on function public.dmax_cleanup() from public,anon,authenticated;
