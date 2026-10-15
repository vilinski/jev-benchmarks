"""Measured statistics and paired route comparisons. Missing measurements stay missing."""
import collections
import json
import math
from pathlib import Path
import random
import statistics as st
from models import MODELS,billed_tokens,cost_per_call
ROOT=Path(__file__).parent

def mean(xs): return st.mean(xs) if xs else None

def percentile(xs,q):
    if not xs: return None
    xs=sorted(xs); i=(len(xs)-1)*q;lo=int(i);hi=math.ceil(i)
    return xs[lo]+(xs[hi]-xs[lo])*(i-lo)

def ci(xs,seed=7,runs=2000):
    if not xs: return [None,None]
    rng=random.Random(seed)
    means=sorted(sum(rng.choices(xs,k=len(xs)))/len(xs) for _ in range(runs))
    return [means[int(runs*.025)],means[int(runs*.975)]]

def infrastructure(row):
    err=(row.get('err') or '').lower()
    return any(t in err for t in ['keychain','http 401','http 403','http 402','daily free allocation','insufficient_quota','insufficient credits','no api key'])

def unsupported(row):
    """Capability failures are distinct from transport errors and refusals."""
    err=(row.get('err') or '').lower()
    return bool(row.get('unsupported') or 'single-token labels' in err or 'options per question' in err)

def answer(row):
    a=(row.get('res') or {}).get('q') if row.get('ok') else None
    return a if a and a.get('type')!='refusal' else None

def score(row,own=False):
    """Uniform accuracy/Brier fallback for errors, refusals and unsupported requests."""
    a=answer(row);kind=row['kind'];gold=row['gold'] if own else row['label']
    if gold is None: return None
    if kind=='noul':
        g=bool(gold) if own else str(gold)=='1'
        p=a['noul'] if a else .5
        return (0.5 if p==.5 else float((p>.5)==g)),2*(p-int(g))**2
    opts=row.get('options')
    if kind=='score':
        gold=str(int(gold))
        opts=opts or [str(i) for i in range(len(a['probabilities']))] if a else opts
    else: gold=str(gold)
    if not opts and a: opts=list(a['probabilities'])
    if not opts: return None
    values=[a['probabilities'].get(o,0) for o in opts] if a else [1/len(opts)]*len(opts)
    total=sum(values)
    if total>0 and abs(total-1)<=.05: values=[v/total for v in values]
    top=max(values);ties=[o for o,v in zip(opts,values) if v==top]
    credit=1/len(ties) if gold in ties else 0
    return credit,sum((v-int(o==gold))**2 for o,v in zip(opts,values))

def suite(data,model,own=False):
    original=data.get('rows',[]);rows=[r for r in original if not infrastructure(r)];good=[r for r in rows if answer(r) is not None]
    lat=[r['dt'] for r in good if not (own and r.get('warmup'))]
    attempted=[r['dt'] for r in rows if r.get('dt',0)>0 and not (own and r.get('warmup'))]
    nunsupported=sum(unsupported(r) for r in rows)
    usage=[r for r in rows if billed_tokens(r)[0] is not None]
    tokens=[billed_tokens(r) for r in usage]
    costs=[cost_per_call(r,model) for r in usage]
    api=[r['token_usage']['cost'] for r in usage if isinstance((r.get('token_usage') or {}).get('cost'),(int,float))]
    scored=[(r,score(r,own)) for r in rows];scored=[(r,s) for r,s in scored if s is not None]
    groups=collections.defaultdict(list);kinds=collections.defaultdict(list);cal=collections.defaultdict(list)
    for r,s in scored:
        groups[r.get('source','own')].append(s[0]);kinds[r['kind']].append(s[0]);cal[r['kind']].append(s[1])
    credits=[s[0] for _,s in scored]
    nuls=[s[0] for r,s in scored if r['kind']=='noul']
    nci=ci(nuls)
    mae=[];amb=[];conf_correct=[];conf_wrong=[];byid=collections.defaultdict(list)
    for r in good:
        a=answer(r)
        if own:
            byid[r['id']].append(a)
            if r['kind']=='score': mae.append(abs(a['score']-r['gold']))
            if r['kind']=='noul' and r['gold'] is None: amb.append(abs(a['noul']-.5)<.25)
        itemscore=score(r,own)
        if itemscore:
            c=max(a['noul'],1-a['noul']) if r['kind']=='noul' else a.get('confidence')
            if c is not None: (conf_correct if itemscore[0]==1 else conf_wrong).append(c)
    flips=[];sds=[]
    for id,answers in byid.items():
        if len(answers)<2: continue
        if id.startswith('n'): vals=[a['noul'] for a in answers];dec=[v>.5 for v in vals]
        elif id.startswith('s'): vals=[a['score'] for a in answers];dec=[max(a['probabilities'],key=a['probabilities'].get) for a in answers]
        else: vals=[a.get('confidence',0) for a in answers];dec=[a['choice'] for a in answers]
        flips.append(len(set(dec))>1);sds.append(st.pstdev(vals))
    return dict(n=len(rows),infrastructure_excluded=len(original)-len(rows),success=len(good),scored=len(scored),unanswered=len(rows)-len(good),fail=len(rows)-len(good)-nunsupported,request_errors=sum(not r.get('ok') and not unsupported(r) for r in rows),unsupported=nunsupported,unsupported_not_called=sum(unsupported(r) and r.get('dt',0)==0 for r in rows),refused=sum(bool(r.get('ok') and not answer(r)) for r in rows),
        acc=mean(credits),answered_acc=mean([s[0] for r,s in scored if answer(r)]),ci=ci(credits),brier=mean([s[1] for _,s in scored]),per={k:mean(v) for k,v in groups.items()},accuracy_by_kind={k:mean(v) for k,v in kinds.items()},brier_by_kind={k:mean(v) for k,v in cal.items()},
        noul_acc=mean(nuls),noul_ci=nci,noul_n=len(nuls),p50=percentile(lat,.5),p90=percentile(lat,.9),p95=percentile(lat,.95),p99=percentile(lat,.99),min=min(lat) if lat else None,max=max(lat) if lat else None,mean=mean(lat),stddev=st.pstdev(lat) if lat else None,
        attempted_latency=dict(n=len(attempted),p50=percentile(attempted,.5),p95=percentile(attempted,.95),p99=percentile(attempted,.99),mean=mean(attempted),max=max(attempted) if attempted else None),
        latency_samples=len(lat),retries=sum(r.get('retries',0) for r in rows),usage_samples=len(usage),input=mean([t[0] for t in tokens]),output=mean([t[1] for t in tokens]),cached=mean([t[2] for t in tokens]),
        cost=mean(costs)*1000 if costs else None,api_cost=mean(api)*1000 if api else None,api_cost_samples=len(api),known_total_list_cost=sum(costs),known_total_api_cost=sum(api) if api else None,
        cli_versions=sorted({r.get('cli_version',data.get('cli_version','unrecorded')) for r in rows}),
        models=sorted({v for r in rows for v in (r.get('upstream_models') or [r.get('returned_model')]) if v}),upstreams=sorted({r['upstream_provider'] for r in rows if r.get('upstream_provider')}),
        started_at=data.get('started_at'),completed_at=data.get('completed_at'),status=data.get('status'),sample_sha256=data.get('sample_sha256'),
        severity_mae=mean(mae),ambiguous_abstain=mean(amb),confidence_correct=mean(conf_correct),confidence_wrong=mean(conf_wrong),decision_flips=mean(flips),run_stddev=mean(sds),batch_mean=mean(data.get('batch',[])),sequential_mean=mean(data.get('sep',[])))

def load():
    analyses={};raw={}
    for model in MODELS:
        suites={};raws={}
        for name,prefix in [('own',''),('public','hf_')]:
            path=ROOT/'results'/f'{prefix}{model.stem}.json'
            if path.exists():
                data=json.loads(path.read_text());suites[name]=suite(data,model,name=='own');raws[name]=data
        analyses[model.key]=suites;raw[model.key]=raws
    return analyses,raw

def paired_routes(raw):
    """Join exact question IDs, never zip different incomplete sample prefixes."""
    out=[]
    for direct in [m for m in MODELS if m.route=='direct']:
        gateway=next((m for m in MODELS if m.route=='OpenRouter' and m.identity==direct.identity),None)
        if not gateway: continue
        for name in ['own','public']:
            a=raw[direct.key].get(name,{});b=raw[gateway.key].get(name,{})
            def key(r):return (r['id'],r.get('rep',0))
            da={key(r):r for r in a.get('rows',[]) if not infrastructure(r)};db={key(r):r for r in b.get('rows',[]) if not infrastructure(r)}
            common=sorted(da.keys()&db.keys());diff=[];dt=[];same=[];cost=[]
            for id in common:
                x,y=da[id],db[id];sx,sy=score(x,name=='own'),score(y,name=='own')
                if sx and sy: diff.append(sy[0]-sx[0])
                if answer(x) and answer(y):
                    if not (name=='own' and (x.get('warmup') or y.get('warmup'))): dt.append(y['dt']-x['dt'])
                    ax,ay=answer(x),answer(y)
                    def selected(r,a):
                        if r['kind']=='noul':return a['noul']>.5
                        return max(a['probabilities'],key=a['probabilities'].get)
                    same.append(selected(x,ax)==selected(y,ay))
                    cx,cy=cost_per_call(x,direct),cost_per_call(y,gateway)
                    if cx is not None and cy is not None:cost.append((cy-cx)*1000)
            out.append(dict(identity=direct.identity,suite=name,common=len(common),accuracy_pairs=len(diff),accuracy_delta=mean(diff),accuracy_delta_ci=ci(diff),paired_latency_n=len(dt),paired_latency_delta_p50=percentile(dt,.5),paired_latency_delta_mean=mean(dt),paired_latency_delta_ci=ci(dt),decision_agreement=mean(same),paired_cost_delta_per_1000=mean(cost),direct_models=sorted({r.get('returned_model') for r in da.values() if r.get('returned_model')}),gateway_models=sorted({r.get('returned_model') for r in db.values() if r.get('returned_model')}),direct_started=a.get('started_at'),gateway_started=b.get('started_at'),direct_complete=a.get('status')=='complete',gateway_complete=b.get('status')=='complete'))
    return out

def paired_versions(raw):
    """Compare pinned Jev releases on exact item IDs within the same API route."""
    out=[]
    for route in ('direct','OpenRouter'):
        old=next((m for m in MODELS if m.identity=='Jev 1.13' and m.route==route),None)
        new=next((m for m in MODELS if m.identity=='Jev 1.14' and m.route==route),None)
        if not old or not new: continue
        for name in ('public','own'):
            a=raw[old.key].get(name,{});b=raw[new.key].get(name,{})
            key=lambda r:(r['id'],r.get('rep',0))
            da={key(r):r for r in a.get('rows',[]) if not infrastructure(r)}
            db={key(r):r for r in b.get('rows',[]) if not infrastructure(r)}
            common=sorted(da.keys()&db.keys());diff=[];brier=[];lat=[];cost=[]
            for item in common:
                x,y=da[item],db[item];sx,sy=score(x,name=='own'),score(y,name=='own')
                if sx is not None and sy is not None:
                    diff.append(sy[0]-sx[0]);brier.append(sy[1]-sx[1])
                if answer(x) and answer(y) and not (name=='own' and (x.get('warmup') or y.get('warmup'))):
                    lat.append(y['dt']-x['dt'])
                cx,cy=cost_per_call(x,old),cost_per_call(y,new)
                if cx is not None and cy is not None: cost.append((cy-cx)*1000)
            if common:
                out.append(dict(old=old.key,new=new.key,route=route,suite=name,common=len(common),accuracy_pairs=len(diff),accuracy_delta=mean(diff),accuracy_delta_ci=ci(diff),brier_delta=mean(brier),paired_latency_delta_p50=percentile(lat,.5),paired_latency_delta_mean=mean(lat),paired_latency_delta_ci=ci(lat),paired_latency_n=len(lat),cost_delta_per_1000=mean(cost),complete=a.get('status')=='complete' and b.get('status')=='complete',old_models=sorted({r.get('returned_model') for r in da.values() if r.get('returned_model')}),new_models=sorted({r.get('returned_model') for r in db.values() if r.get('returned_model')}),old_started=a.get('started_at'),new_started=b.get('started_at')))
    return out
