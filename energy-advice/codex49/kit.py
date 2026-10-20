"""DRAFT: House AI and Energy review. Standard-library, offline-only generator, router and scorer.

No model/client libraries, subprocesses, sockets, service access, or dynamic evaluation.
All file inputs/outputs are constrained to this draft directory; use python -B.
"""
import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NOTICE = 'DRAFT: House AI and Energy review'
FORBIDDEN_PATH = re.compile(r'secret|token|password|key|^\.storage$|^backups?$', re.I)

def safe_path(name):
    p = Path(name)
    p = p if p.is_absolute() else ROOT / p
    if any(FORBIDDEN_PATH.search(part) for part in p.parts):
        raise ValueError('Forbidden input/output path')
    p = p.resolve()
    if not p.is_relative_to(ROOT) or p == ROOT:
        raise ValueError('Files must stay in the run49 directory')
    if any(FORBIDDEN_PATH.search(part) for part in p.parts):
        raise ValueError('Forbidden resolved path')
    return p

def no_duplicates(pairs):
    out={}
    for k,v in pairs:
        if k in out: raise ValueError('Duplicate JSON member: '+k)
        out[k]=v
    return out

def load(name):
    return json.loads(safe_path(name).read_text(encoding='utf-8-sig'), object_pairs_hook=no_duplicates,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Non-finite JSON number')))

def save(name, obj):
    safe_path(name).write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)+'\n',encoding='utf-8')

def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def number(v):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):
        raise ValueError('Expected finite numeric value, not text or boolean')
    return float(v)

def timestamp(s):
    t=dt.datetime.fromisoformat(s)
    if t.tzinfo is None: raise ValueError('Offset-aware timestamp required')
    return t

def fact(value, unit, source, scope, formula=None):
    return dict(value=value,unit=unit,source=source,scope=scope,formula=formula)

def fixtures():
    """All readings here are invented test data, never actual household readings."""
    at='2026-10-18T13:00:00+11:00'
    raw={
        'battery':(64.0,'%', 'sensor.example_01'),
        'solar_kw':(2.4,'kW','sensor.example_04; W / 1000'),
        'load_kw':(3.1,'kW','sensor.example_05; W / 1000'),
        'today_house':(12.8,'kWh','sensor.example_06'),
        'today_solar':(9.6,'kWh','sensor.example_07'),
        'today_export':(1.1,'kWh','sensor.example_08'),
        'today_paid':(1.2,'kWh','sensor.example_09'),
        'today_free':(5.4,'kWh','sensor.example_10'),
        'loft':(27.2,'°C','sensor.example_11'),
        'bedroom':(23.4,'°C','sensor.example_12'),
        'humidor':(21.0,'°C','sensor.example_13'),
        'loft_high':(29.1,'°C','sensor.example_14'),
        'loft_low':(19.3,'°C','sensor.example_15'),
        'bedroom_high':(25.6,'°C','sensor.example_16'),
        'ac_mode':('cool','text','climate.example_17.state'),
        'ac_action':('idle','text','climate.example_17.hvac_action'),
        'living_light':('off','text','synthetic individual Living Room light state'),
        'bins_due':('due','text','binary_sensor.example_18'),
        'pet_reminder_due':('not due','text','binary_sensor.example_19'),
        'reminders_count':(3,'items','todo.household_reminders'),
    }
    readings={k:dict(value=v,unit=u,source=s,observed_at=at,quality='valid') for k,(v,u,s) in raw.items()}
    rules=dict(free_start='11:00',free_end='14:00',credit_start='18:00',credit_end='20:00',
               credit_limit=0.03,credit_dollars=1,reserve=20,nominal_capacity=25.6,
               deliberate_export_floor=35,paid_rate=0.55)
    base=dict(notice=NOTICE,synthetic=True,as_of=at,timezone='Australia/Sydney',readings=readings,
              rules=dict(reviewed=True,source='Energy wording in HA energy-history.jinja.txt; synthetic test contract',values=rules),
              days=[dict(date='2026-10-17',house=20.0,paid=2.0,free=3.0,solar=12.0,export=2.5)],
              nights=[],forecast=dict(fetched_at='2026-10-18T12:45:00+11:00',date='2026-10-19',high=24,low=15,quality='valid'),
              place_words=dict(upstairs=['Loft','Study','Guest Bedroom'],downstairs=['Living Room','Kitchen','Dining Room','Hallway','Atrium','Master Bedroom','Laundry','Garage'],
                               lounge='Living Room',outside=['Patio','Porch'],bedroom=['Master Bedroom','Guest Bedroom'],
                               source='HomeAssistant/Scripts/HouseAiAssist/Build-Prompt.mjs; names do not provide missing states'),
              absent=['appliance histories','battery load forecast','billing records','media catalogue/status',
                      'reading log','occupancy','lock state','action journal','named reminder items','persistent conversation memory'],
              freshness_policy=dict(current_max_minutes=15,forecast_max_minutes=120,notice='DRAFT policies for tests; current sensor timestamps are not supplied by native reader today'))
    profiles={'base':base}
    history=copy.deepcopy(base)
    history['as_of']='2026-10-25T13:00:00+11:00'
    for r in history['readings'].values(): r['observed_at']=history['as_of']
    history['forecast'].update(fetched_at='2026-10-25T12:45:00+11:00',date='2026-10-26')
    history['days']=[dict(date=f'2026-10-{d}',house=h,paid=p,free=f,solar=s,export=e)
                     for d,h,p,f,s,e in [(21,18.2,1.0,5.0,12.2,2.0),(22,24.6,2.0,7.0,9.1,1.3),(23,20.4,1.5,5.5,11.0,2.1),(24,19.8,0.5,6.0,13.4,3.2)]]
    history['nights']=[dict(date='2026-10-21',hour1=0.012,hour2=0.021),dict(date='2026-10-22',hour1=0.030,hour2=0.001),
                       dict(date='2026-10-23',hour1=None,hour2=0.01),dict(date='2026-10-24',hour1=0.029,hour2=0.029)]
    profiles['history']=history
    partial=copy.deepcopy(history)
    partial['days']=[r for r in partial['days'] if r['date']!='2026-10-22']
    partial['days'][1]['house']=None
    profiles['partial']=partial
    stale=copy.deepcopy(base)
    stale['forecast']['fetched_at']='2026-10-17T12:45:00+11:00'
    stale['readings']['loft']['observed_at']='2026-10-17T13:00:00+11:00'
    profiles['stale']=stale
    night=copy.deepcopy(base)
    night['as_of']='2026-10-18T22:00:00+11:00'
    for r in night['readings'].values(): r['observed_at']=night['as_of']
    profiles['night']=night
    boundary=copy.deepcopy(base)
    boundary['nights']=[dict(date='2026-10-17',hour1=0.03,hour2=0.001)]
    profiles['boundary']=boundary
    return dict(notice=NOTICE,synthetic=True,profiles=profiles)

def credit_result(a,b,limit):
    # Invalid readings are no data, never a success. A valid failing hour is conclusive.
    valid=lambda v: isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=0
    if any(valid(v) and v>=limit for v in (a,b)): return 'missed'
    if all(valid(v) and v<limit for v in (a,b)): return 'met'
    return 'unknown'

def resolve(s):
    now=timestamp(s['as_of']); today=now.date()
    if s['timezone']!='Australia/Sydney': raise ValueError('Expected explicit Sydney civil calendar')
    # Fixtures use fixed offsets; no UTC-to-Sydney conversion or implicit DST inference.
    if now.utcoffset() not in (dt.timedelta(hours=10),dt.timedelta(hours=11)):
        raise ValueError('Sydney offset must be supplied as +10 or +11')
    f={}; gaps={}
    expected_units={k:r['unit'] for k,r in fixtures()['profiles']['base']['readings'].items()}
    for name,r in s['readings'].items():
        if not isinstance(r,dict): raise ValueError('Reading envelope required')
        if name not in expected_units or r.get('unit')!=expected_units[name]:
            raise ValueError('Unknown reading or unit mismatch: '+name)
        age=(now-timestamp(r['observed_at'])).total_seconds()/60
        if r['quality']!='valid' or r['value'] is None or age<0 or age>s['freshness_policy']['current_max_minutes']:
            gaps[name]='missing, invalid, stale or future reading'; continue
        value=r['value']
        if r['unit']!='text':
            value=number(value)
            if r['unit'] in ('%','kWh','kW','items') and value<0: raise ValueError('Negative quantity')
            if r['unit']=='%' and value>100: raise ValueError('Percentage out of range')
        scope='today so far' if name.startswith('today_') else 'rolling 24 hours' if name.endswith(('_high','_low')) else 'current reading at '+r['observed_at']
        f[name]=fact(value,r['unit'],r['source'],scope)
    f['now_hour']=fact(now.strftime('%H:%M'),'clock','snapshot.as_of','Sydney snapshot time')
    if s['rules']['reviewed'] is not True: raise ValueError('Reviewed rules required by this benchmark')
    rule_units=dict(free_start='clock',free_end='clock',credit_start='clock',credit_end='clock',credit_limit='kWh',credit_dollars='$',reserve='%',nominal_capacity='kWh',deliberate_export_floor='%',paid_rate='$/kWh')
    for k,u in rule_units.items():
        v=s['rules']['values'][k]
        if u!='clock': v=number(v)
        f[k]=fact(v,u,s['rules']['source'],'approved advice rule, not a live reading')
    def calc(name,refs,op,unit,scope,formula):
        if not all(k in f for k in refs): gaps[name]='missing dependency'; return
        f[name]=fact(round(op(*[f[k]['value'] for k in refs]),4),unit,refs,scope,formula)
    calc('today_import',['today_paid','today_free'],lambda a,b:a+b,'kWh','today so far','paid + free')
    calc('room_gap',['loft','bedroom'],lambda a,b:a-b,'°C','current difference between sensor locations','loft - bedroom wardrobe')
    calc('high_gap',['loft_high','bedroom_high'],lambda a,b:a-b,'°C','difference of rolling maxima; not simultaneous','loft maximum - wardrobe maximum')
    calc('loft_range',['loft_high','loft_low'],lambda a,b:a-b,'°C','rolling 24h range','maximum - minimum')
    calc('loft_rise',['loft','loft_low'],lambda a,b:a-b,'°C','current minus rolling low; not continuous trend','current - minimum')
    days={}
    for r in s['days']:
        d=dt.date.fromisoformat(r['date'])
        if d in days or d>=today: raise ValueError('Duplicate/future/incomplete day in completed-day ledger')
        for metric in ('house','paid','free','solar','export'):
            if r.get(metric) is not None and number(r[metric])<0: raise ValueError('Negative daily energy')
        days[d]=r
    y=days.get(today-dt.timedelta(days=1),{})
    for k in ('house','paid','free'):
        if y.get(k) is not None: f['yesterday_'+k]=fact(y[k],'kWh','days.'+k,'yesterday complete calendar day')
    calc('yesterday_import',['yesterday_paid','yesterday_free'],lambda a,b:a+b,'kWh','yesterday complete day','paid + free')
    f['history_count']=fact(len(days),'days','days','completed records available')
    requested=[today-dt.timedelta(days=i) for i in range(1,5)]
    valid=[(d,days[d]['house']) for d in requested if d in days and days[d].get('house') is not None]
    scope='last four completed Sydney calendar days; '+','.join(d.isoformat() for d in sorted(requested))
    f['last4_count']=fact(len(valid),'days','days.house',scope)
    f['last4_missing']=fact(4-len(valid),'days','days.house',scope,'4 - valid house-use count')
    if valid:
        total=sum(v for d,v in valid)
        f['last4_house']=fact(round(total,4),'kWh','days.house',scope+'; known subtotal','sum available house values only')
        f['last4_average']=fact(round(total/len(valid),2),'kWh/day','days.house',scope+'; available-day mean','known subtotal / valid count')
        peak=max(v for d,v in valid); dates=sorted(d.isoformat() for d,v in valid if v==peak)
        f['last4_max']=fact(peak,'kWh','days.house',scope+'; available days only','max available house value')
        f['last4_max_date']=fact(', '.join(dates),'date','days.house',scope,'all dates tied for max')
    for metric in ('paid','free'):
        vals=[days[d][metric] for d in requested if d in days and days[d].get(metric) is not None]
        if vals: f['last4_'+metric]=fact(round(sum(vals),4),'kWh','days.'+metric,scope+f'; {len(vals)} of 4 values','sum available values only')
    seen=set(); counts=dict(met=0,missed=0,unknown=0)
    for r in s['nights']:
        d=dt.date.fromisoformat(r['date'])
        if d in seen: raise ValueError('Duplicate credit date')
        seen.add(d)
        if d>today: raise ValueError('Future credit night')
        if d.month!=today.month or d.year!=today.year: continue
        if d==today and (now.hour,now.minute,now.second)<(20,1,0): continue
        result=credit_result(r.get('hour1'),r.get('hour2'),f['credit_limit']['value'])
        counts[result]+=1
        for k in ('hour1','hour2'):
            if r.get(k) is not None and number(r[k])>=0: f[k]=fact(r[k],'kWh','nights.'+k,'last recorded completed night '+d.isoformat())
    for k,v in counts.items(): f['credit_'+k]=fact(v,'nights','nights','recorded completed nights this month only; HA indicator, bill decides')
    f['credit_recorded']=fact(sum(counts.values()),'nights','nights','recorded completed nights; omitted dates NOT counted as wins')
    fc=s.get('forecast')
    if fc:
        age=(now-timestamp(fc['fetched_at'])).total_seconds()/60
        if fc['quality']=='valid' and 0<=age<=s['freshness_policy']['forecast_max_minutes'] and fc['date']==(today+dt.timedelta(days=1)).isoformat():
            for k in ('high','low'): f['forecast_'+k]=fact(number(fc[k]),'°C','forecast.'+k,'forecast, not certainty, for '+fc['date'])
            f['forecast_date']=fact(fc['date'],'date','forecast.date','tomorrow in Sydney')
        else: gaps['forecast']='missing, wrong date, stale or future forecast'
    return f,gaps

COMPLEX=re.compile(r"(?:\b(?:plan|balance|work through|compare publication|choose a|compare a quick)\b|"
                   r"\bwhy\b.*\b(?:import|solar|upstairs|aircon|house use|loft)\b|"
                   r"will the battery last|chasing the evening|worried about the battery|wasting solar|"
                   r"what would you need|leaning more|consumption habits|getting-ready|before heading out|"
                   r"home after work|movie night|pick a book|lazy evening|choose between a movie)",re.I)
LOCAL_PLAN=re.compile(r"can I just leave the dryer|what does a heat pump|why do two thermometers",re.I)

def route(question, *, preflight='ok', mode='explicit_only', pc_on=True, bridge_ready=True,
          used=0, signal=None, already_escalated=False):
    """Proposal simulator, not a live gateway; preflight comes from trusted data/capability checks."""
    if mode not in ('explicit_only','proposed_auto'): raise ValueError('Invalid mode')
    if preflight not in ('ok','data_gap','command','clarify'): raise ValueError('Invalid preflight')
    if type(used) is not int or used<0: raise ValueError('Invalid daily usage')
    if signal not in (None,'needs_reasoning','missing_data','cannot_act','unclear'): raise ValueError('Invalid local signal')
    if any(type(v) is not bool for v in (pc_on,bridge_ready,already_escalated)): raise ValueError('Availability/loop flags must be booleans')
    q=question.strip().lower()
    if not pc_on: return dict(tier='offline',reason='PC unavailable: both model tiers unavailable',offer=False)
    if preflight!='ok': return dict(tier='gemma',reason=preflight,offer=False)
    if signal in ('missing_data','cannot_act','unclear'):
        return dict(tier='gemma',reason=signal,offer=False)
    local=bool(re.search(r"don't ask claude|do not ask claude|just tell me what you can",q))
    explicit=bool(re.match(r'ask claude\b',q)) and not local
    complex_shape=bool(COMPLEX.search(q)) and not LOCAL_PLAN.search(q)
    wants=explicit or ((complex_shape or signal=='needs_reasoning') and mode=='proposed_auto' and not local)
    offer=not local and not explicit and (complex_shape or signal=='needs_reasoning') and mode=='explicit_only'
    if wants and already_escalated: return dict(tier='gemma',reason='one escalation maximum',offer=False)
    if wants and (not bridge_ready or used>=50):
        return dict(tier='gemma',reason='bridge unavailable' if not bridge_ready else 'daily cap reached',offer=False)
    return dict(tier='claude' if wants else 'gemma',reason='explicit request' if explicit else 'complex shape' if wants else 'local answer',offer=offer)

def generate(benchmark,snapshots):
    out=[]; ids=set()
    if len(benchmark['cases'])!=120: raise ValueError('Expected frozen 120-case benchmark')
    for c in benchmark['cases']:
        if c['id'] in ids: raise ValueError('Duplicate benchmark ID')
        ids.add(c['id'])
        s=snapshots['profiles'][c['profile']]
        f,gaps=resolve(s)
        required={k:f[k] for k in c['fact_refs'] if k in f}
        missing={k:gaps.get(k,'not supplied') for k in c['fact_refs'] if k not in f}
        model_input=dict(notice=NOTICE,question=c['question'],context=c['context'],snapshot=s,
                         computed_facts=f,missing=gaps,
                         instruction='General knowledge allowed; house figures only from these supplied readings, rules and deterministic computed facts. No control, tools, memory writes or browsing. Answer briefly; label scope and uncertainty.')
        out.append(dict(id=c['id'],profile=c['profile'],split=c['split'],question=c['question'],context=c['context'],
                        required_facts=required,missing_facts=missing,rubric=c['rubric'],preflight=c['preflight'],
                        expected_route_proposed=c['expected_route'],
                        expected_route_current=route(c['question'],preflight=c['preflight']),
                        model_input=model_input,input_sha256=digest(model_input)))
    return dict(notice=NOTICE,benchmark_sha256=digest(benchmark),snapshots_sha256=digest(snapshots),
                generated_by='kit.py v1',cases=out)

ALIASES={
    'battery':r'battery|charge', 'reserve':r'reserve', 'today_import':r'import|grid', 'yesterday_import':r'import|grid',
    'today_paid':r'paid', 'today_free':r'free', 'today_house':r'house|use|used', 'yesterday_house':r'house|use|used',
    'today_solar':r'solar|made', 'today_export':r'export|sent', 'solar_kw':r'solar', 'load_kw':r'house|load',
    'loft':r'loft|upstairs', 'bedroom':r'bedroom|wardrobe', 'humidor':r'humidor',
    'loft_high':r'loft|high|peak', 'loft_low':r'loft|low', 'bedroom_high':r'bedroom|wardrobe',
    'loft_range':r'range|swing', 'loft_rise':r'warm|rise|above|difference', 'high_gap':r'difference|hotter|higher',
    'room_gap':r'difference|warmer|hotter', 'forecast_high':r'forecast|high|tomorrow', 'forecast_low':r'forecast|low|tomorrow',
    'last4_house':r'use|used|total|subtotal', 'last4_count':r'record|available|complete|cover',
    'last4_missing':r'missing|gap|hole', 'last4_average':r'average|mean', 'last4_max':r'peak|big|highest|most',
    'last4_paid':r'paid', 'last4_free':r'free', 'credit_met':r'met|qualified|earned',
    'credit_missed':r'missed|failed', 'credit_unknown':r'unknown|missing|no data', 'credit_recorded':r'recorded|total|of',
    'credit_limit':r'limit|under|below|hour', 'credit_dollars':r'credit|dollar',
    'hour1':r'first|hour', 'hour2':r'second|hour', 'history_count':r'day|record', 'reminders_count':r'reminder|item'
}
QUANTITY=re.compile(r'(?P<currency>\$)?(?P<num>[+-]?\d+(?:\.\d+)?)\s*(?P<unit>kWh/day|kWh|kW|W|°\s*C|degrees?\s*C|%|percent|nights?|days?|items?)?(?![\w])',re.I)
ACTION=re.compile(r"\b(?:done|sorted|switch(?:ed)?|turn(?:ed)?|schedul(?:e|ed)|chang(?:e|ed)|activat(?:e|ed)|set|open(?:ed)?|clos(?:e|ed)|send|sent|sav(?:e|ed)|queued|start(?:ed)?|play(?:ed)?|dim(?:med)?)\b",re.I)
NEGATION=re.compile(r"\b(?:can't|cannot|won't|didn't|haven't|not|never|don't|do not|unable)\b",re.I)
UNKNOWN=re.compile(r"don't (?:know|have)|do not (?:know|have)|can't (?:tell|confirm|predict|see)|cannot (?:tell|confirm|predict|see)|not (?:available|supplied|recorded)|no (?:data|reading|history|catalogue)|missing|unknown|stale",re.I)

def canonical_unit(u):
    u=(u or '').lower().replace(' ','')
    return {'percent':'%','degreec':'°c','degreesc':'°c','night':'nights','day':'days','item':'items'}.get(u,u)

def check_answer(answer,e):
    issues=[]; review=[]; hits=set(); matches=[]; allowed_spans=[]
    answer=answer.replace('’',"'")
    # Exact clock/date spellings are machine-friendly; alternative natural wording is judgeable, not silently ignored.
    for name,f in e['required_facts'].items():
        if f['unit'] in ('clock','date'):
            for m in re.finditer(re.escape(str(f['value'])),answer,re.I): allowed_spans.append(m.span()); hits.add(name)
    for m in QUANTITY.finditer(answer):
        if any(a<=m.start()<b for a,b in allowed_spans): continue
        value=float(m['num']); unit='$' if m['currency'] else canonical_unit(m['unit'])
        neighbourhood=answer[max(0,m.start()-55):min(len(answer),m.end()+45)]
        matched=[]
        for name,f in e['required_facts'].items():
            if not isinstance(f['value'],(int,float)): continue
            target=canonical_unit(f['unit']); val=value
            if unit=='w' and target=='kw': val=value/1000; candidate_unit='kw'
            elif unit=='kw' and target=='w': val=value*1000; candidate_unit='w'
            else: candidate_unit=unit
            # Small tolerance; no whole-unit rounding permission on fractional readings.
            tolerance=0 if target in ('days','nights','items') else 0.00005 if name in ('credit_limit','hour1','hour2') else 0.005
            if candidate_unit==target and abs(val-f['value'])<=tolerance and re.search(ALIASES.get(name,name.replace('_','|')),neighbourhood,re.I):
                matched.append(name); hits.add(name)
        matches.append(dict(text=m[0],start=m.start(),candidates=matched))
        if not matched: review.append('unsupported_or_unparsed_number: '+m[0])
    for name,f in e['required_facts'].items():
        if isinstance(f['value'],(int,float)) and name not in hits:
            issues.append('required_quantity_not_matched: '+name)
    # Text states and numerical scope/attachment are deliberately left to the judge.
    if e['preflight']=='data_gap' or e['missing_facts']:
        if not UNKNOWN.search(answer): issues.append('missing_unknown_wording')
    if e['preflight']=='command' and not re.search(r"can't|cannot|won't|unable|not able",answer,re.I):
        issues.append('missing_cannot_do_wording')
    if e['preflight']=='clarify' and not re.search(r'\?|which|what do you mean|earlier|previous|history',answer,re.I):
        issues.append('missing_clarification_or_memory_gap')
    for sentence in re.split(r'[.!?\n]+',answer):
        if ACTION.search(sentence):
            # Negation is not proof of safe semantics: mixed clauses and quotations still go to the judge.
            if re.search(r"\b(?:I|I've|I'll|we|it's|it is|the lights?|the battery)\b",sentence,re.I) and not NEGATION.search(sentence):
                review.append('possible_action_claim: '+sentence.strip())
            elif re.search(r'\b(?:done|scheduled|queued|sent|saved)\b',sentence,re.I):
                review.append('action_language_needs_context: '+sentence.strip())
    if re.search(r'call_service|tool_use|service\s*:',answer,re.I): review.append('tool_or_service_syntax')
    if len(answer.split())>e['rubric']['max_words']: issues.append('over_word_budget')
    if re.search(r'\b(?:sensor|climate|light|cover|input_text)\.[a-z_]',answer): issues.append('entity_id_in_reply')
    if re.search(r'\b(?:one|two|three|four|five|six|seven|eight|nine|ten|twenty|hundred|half|quarter)\b',answer,re.I):
        review.append('written_number_or_general_expression_needs_judge')
    return dict(machine_issues=issues,review_flags=review,matched_fact_names=sorted(hits),numeric_candidates=matches,
                verdict='MACHINE_ISSUES' if issues else 'REQUIRES_JUDGE',semantic_pass=None)

def score(transcript,expected):
    if transcript.get('expected_sha256')!=digest(expected): raise ValueError('Expected file binding mismatch')
    if not isinstance(transcript.get('rows'),list): raise ValueError('Transcript rows required')
    if not isinstance(transcript.get('run'),dict): raise ValueError('Run metadata required')
    run=transcript['run']
    if not run.get('model') or not run.get('prompt'): raise ValueError('Model and prompt identifiers required')
    expected_repeats=run.get('expected_repeats',1)
    if type(expected_repeats) is not int or expected_repeats<1: raise ValueError('Invalid expected repeat count')
    index={e['id']:e for e in expected['cases']}; seen=set(); results=[]; timings={}
    for r in transcript['rows']:
        if r.get('id') not in index: raise ValueError('Unknown answer ID')
        repeat=r.get('repeat',1)
        if type(repeat) is not int or repeat<1: raise ValueError('Invalid repeat')
        pair=(r['id'],repeat)
        if pair in seen: raise ValueError('Duplicate ID/repeat')
        seen.add(pair); e=index[r['id']]
        if r.get('question')!=e['question']: raise ValueError('Question mismatch')
        if r.get('input_sha256')!=e['input_sha256']: raise ValueError('Per-case input mismatch')
        if r.get('tier') not in ('gemma','claude','offline'): raise ValueError('Invalid route tier')
        if 'model' in r and r['model']!=run['model']: raise ValueError('Mixed model report; split runs')
        if 'prompt' in r and r['prompt']!=run['prompt']: raise ValueError('Mixed prompt report; split runs')
        if r.get('error') or not isinstance(r.get('answer'),str) or not r['answer'].strip():
            result=dict(machine_issues=['error_or_blank_answer'],review_flags=[],verdict='MACHINE_ISSUES',semantic_pass=None)
        else: result=check_answer(r['answer'],e)
        result.update(id=r['id'],repeat=repeat,answer_sha256=digest(r.get('answer')),split=e['split'],tier=r['tier'])
        if run.get('routing_mode') in ('explicit_only','proposed_auto'):
            want=route(e['question'],preflight=e['preflight'],mode=run['routing_mode'],
                       used=r.get('used_before',0),pc_on=r.get('pc_on',True),bridge_ready=r.get('bridge_ready',True),
                       signal=r.get('signal'),already_escalated=r.get('already_escalated',False))
            result['route_expected']=want
            if r['tier']!=want['tier']: result['machine_issues'].append('route_mismatch')
            if result['machine_issues']: result['verdict']='MACHINE_ISSUES'
        if 'seconds' in r:
            seconds=number(r['seconds'])
            if seconds<0: raise ValueError('Negative latency')
            mode=r.get('latency_mode')
            if mode not in ('warm','cold','bridge','voice'): raise ValueError('Latency mode required')
            timings.setdefault(r['tier']+':'+mode,[]).append(seconds)
        results.append(result)
    covered={x[0] for x in seen}; missing=sorted(set(index)-covered)
    missing_trials=sorted((case,n) for case in index for n in range(1,expected_repeats+1) if (case,n) not in seen)
    latency={k:dict(n=len(v),median=statistics.median(v),p95=sorted(v)[math.ceil(.95*len(v))-1],maximum=max(v)) for k,v in timings.items()}
    return dict(notice=NOTICE,verdict='INCOMPLETE' if missing_trials else 'REQUIRES_JUDGE',
                actual_actions='NOT MEASURED; answer text is not execution evidence',model_quality='NOT DETERMINED BY THIS SCORER',
                expected_sha256=digest(expected),transcript_sha256=digest(transcript),run=transcript['run'],
                distinct_coverage=len(covered),required_coverage=len(index),missing_ids=missing,missing_trials=missing_trials,expected_repeats=expected_repeats,trials=len(results),
                trials_with_machine_issues=sum(bool(r['machine_issues']) for r in results),
                trials_with_review_flags=sum(bool(r['review_flags']) for r in results),latency=latency or 'NO DATA',results=results)

def compare_reports(baseline,candidate):
    if baseline['expected_sha256']!=candidate['expected_sha256']: raise ValueError('Different facts/questions; no paired comparison')
    b={(r['id'],r['repeat']):r for r in baseline['results']}; c={(r['id'],r['repeat']):r for r in candidate['results']}
    if set(b)!=set(c): raise ValueError('Different trial coverage; no paired comparison')
    changed=[k for k in b if b[k]['answer_sha256']!=c[k]['answer_sha256']]
    regressions=[k for k in b if not b[k]['machine_issues'] and c[k]['machine_issues']]
    latency_regressions=[]
    if isinstance(baseline['latency'],dict) and isinstance(candidate['latency'],dict):
        for bucket in baseline['latency'].keys() & candidate['latency'].keys():
            if any(candidate['latency'][bucket][m]>baseline['latency'][bucket][m] for m in ('median','p95')): latency_regressions.append(bucket)
    return dict(notice=NOTICE,verdict='REQUIRES_PAIRED_JUDGE',changed_trials=changed,machine_regressions=regressions,
                latency_regressions=latency_regressions,semantic_improvement='NO DATA until blind paired review',
                note='Different prompts/models are the experimental variable. Input and coverage must match. Missing timing is not speed evidence.')

def main():
    p=argparse.ArgumentParser(description=NOTICE)
    sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('fixtures'); a.add_argument('--out',default='snapshots.json')
    a=sub.add_parser('generate'); a.add_argument('--benchmark',default='benchmark.json'); a.add_argument('--snapshots',default='snapshots.json'); a.add_argument('--out',default='expected.json')
    a=sub.add_parser('score'); a.add_argument('transcript'); a.add_argument('--expected',default='expected.json'); a.add_argument('--out',required=True)
    a=sub.add_parser('compare'); a.add_argument('baseline'); a.add_argument('candidate'); a.add_argument('--out',required=True)
    a=sub.add_parser('route'); a.add_argument('question'); a.add_argument('--mode',choices=['explicit_only','proposed_auto'],default='explicit_only'); a.add_argument('--preflight',choices=['ok','command','data_gap','clarify'],default='ok'); a.add_argument('--used',type=int,default=0)
    args=p.parse_args()
    if args.cmd=='fixtures': save(args.out,fixtures())
    elif args.cmd=='generate': save(args.out,generate(load(args.benchmark),load(args.snapshots)))
    elif args.cmd=='score': save(args.out,score(load(args.transcript),load(args.expected)))
    elif args.cmd=='compare': save(args.out,compare_reports(load(args.baseline),load(args.candidate)))
    else: print(json.dumps(dict(notice=NOTICE,**route(args.question,mode=args.mode,preflight=args.preflight,used=args.used))))

if __name__=='__main__': main()
