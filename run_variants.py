"""Matched model/route benchmarks through jev, with resumable, per-row checkpoints.

Examples: python3 run_variants.py --smoke --all
          python3 run_variants.py --all --workers 24
No credentials are loaded by Python; the stable installed jev CLI loads its own keys.
"""
import argparse
import fcntl
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
from dataset import N,C,S,ROUTE,SEV
from jevcall import call
from models import MODELS
ROOT=Path(__file__).resolve().parent
os.environ.setdefault('JEV_BINARY','jev')
BY_ID={m.model:m for m in MODELS}

def utcnow(): return datetime.now(timezone.utc).isoformat()
def fingerprint(items): return hashlib.sha256(json.dumps(items,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def save(path,data):
    tmp=path.with_suffix('.tmp'); tmp.write_text(json.dumps(data,ensure_ascii=False)); tmp.replace(path)
def own_items():
    out=[]
    for i,(text,instructions,gold) in enumerate(N): out.append(dict(id=f'n{i}',kind='noul',state={'text':text},q={'type':'noul','instructions':instructions},gold=gold))
    for i,(text,gold) in enumerate(C): out.append(dict(id=f'c{i}',kind='choice',state={'text':text},q={'type':'choice','instructions':'Which team should handle this ticket?','criteria':{**ROUTE,'unclear':'Not determinable from the text, or spans several areas'}},gold=gold))
    for i,(text,gold) in enumerate(S): out.append(dict(id=f's{i}',kind='score',state={'text':text},q={'type':'score','instructions':'How severe is this for a production customer?','criteria':SEV},gold=gold))
    return out

def public_items(per):
    files=sorted(Path(os.environ.get('JEVBENCH_DIR',ROOT/'jev-bench-data')).glob('*.jsonl'))
    if len(files)!=22: raise RuntimeError('Need all 22 cached test splits; run fetch_jevbench.py first')
    rng=random.Random(7); out=[]
    for file in files:
        with file.open() as stream: out.extend(json.loads(line) for line in rng.sample(list(stream),per))
    return out

def infrastructure(row):
    err=(row.get('err') or '').lower()
    return any(s in err for s in ['keychain','no api key','no key','http 401','http 403','http 402','daily free allocation','insufficient_quota','insufficient credits'])

def needs_retry(row,model):
    if infrastructure(row): return True
    if row.get('unsupported'): return False
    if model.provider=='cloudflare': return False
    if 'upstream_provider' not in row: return True
    return any(t in (row.get('err') or '') for t in ['state must be a string','expected string, received null'])

def invoke(model,state,q,retries=1):
    if (model.model.startswith('respan/') or model.model=='scaledown/classify-1') and not isinstance(state,str): state=json.dumps(state,ensure_ascii=False)
    if model.model=='scaledown/classify-1' and isinstance(q.get('criteria'),dict): q={**q,'criteria':{k:(k if v is None else v) for k,v in q['criteria'].items()}}
    return call(model.provider,{'state':state,'questions':{'q':q}},model=model.model,retries=retries,timeout=90)

def smoke(model,own,version):
    data=dict(prov=model.provider,requested_model=model.model,route=model.route,cli_version=version,date=utcnow(),rows=[])
    for kind in ('noul','choice','score'):
        item=next(r for r in own if r['kind']==kind)
        row=invoke(model,item['state'],item['q']); row.update(kind=kind,id=item['id']);data['rows'].append(row)
        print(f"SMOKE {model.key} {kind}: {'OK '+str(row.get('returned_model')) if row['ok'] else row.get('err')}",flush=True)
        if infrastructure(row): break
    save(ROOT/'results'/f'smoke_{model.stem}.json',data)
    return data

def start(path,model,suite,items,version):
    digest=fingerprint(items)
    if path.exists():
        data=json.loads(path.read_text())
        if data.get('requested_model')!=model.model or data.get('sample_sha256')!=digest or data.get('prov')!=model.provider:
            raise RuntimeError(f'Refusing mismatched checkpoint {path}')
        return data
    return dict(prov=model.provider,requested_model=model.model,route=model.route,suite=suite,cli_version=version,started_at=utcnow(),sample_sha256=digest,status='running',rows=[])

def evaluate(model,own,public,version):
    with (ROOT/"results"/(model.stem+".lock")).open("w") as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return model.key+" already running elsewhere"
        return evaluate_locked(model,own,public,version)

def evaluate_locked(model,own,public,version):
    probe=ROOT/'results'/f'smoke_{model.stem}.json'
    pre=json.loads(probe.read_text()) if probe.exists() else smoke(model,own,version)
    if any(infrastructure(r) for r in pre['rows']) and pre.get('date','')[:10]!=utcnow()[:10]: pre=smoke(model,own,version)
    if any(infrastructure(r) for r in pre['rows']): return model.key+' PAUSED: '+str(pre['rows'][-1].get('err'))
    unsupported={r['kind']:r['err'] for r in pre['rows'] if not r['ok'] and any(t in (r.get('err') or '').lower() for t in ['unsupported','not support','only accepts','only supports','http 404','no endpoints','http 405'])}
    if len(unsupported)==3: return model.key+' unavailable for this API (see smoke results)'
    for suite,items,prefix in [('own',own,''),('public',public,'hf_')]:
        path=ROOT/'results'/f'{prefix}{model.stem}.json';data=start(path,model,suite,items,version)
        if data.get('status')=='complete' and not any(needs_retry(r,model) for r in data['rows']):
            print(model.key+' '+suite+': already complete',flush=True);continue
        data['status']='running';save(path,data)
        total=len(items)*(3 if suite=='own' else 1)
        failures=0
        for index in range(total):
            if index<len(data['rows']) and not needs_retry(data['rows'][index],model) and not (not data['rows'][index]['ok'] and data['rows'][index].get('kind') in unsupported and not data['rows'][index].get('unsupported')): continue
            rep,offset=divmod(index,len(items));item=items[offset]
            if suite=='own':
                state,q=item['state'],item['q'];fields=dict(id=item['id'],kind=item['kind'],gold=item['gold'],rep=rep,warmup=(index==0))
            else:
                try: state=json.loads(item['state'])
                except (ValueError,TypeError): state=item['state']
                q=json.loads(item['question']);fields=dict(id=item['id'],source=item['source'],kind=q['type'],label=item['label'])
            criteria=q.get('criteria')
            fields['options']=list(criteria) if isinstance(criteria,dict) else [str(i) for i in range(len(criteria))] if isinstance(criteria,list) else None
            if q['type'] in unsupported:
                row=dict(ok=False,dt=0,res=None,usage=None,err=unsupported[q['type']],unsupported=True,requested_model=model.model)
            elif (model.model=='togethercomputer/tev1-4b-experimental' and fields['options'] and len(fields['options'])>20) or ((model.provider=='openai-chat' or model.model.startswith('upstage/solar-decide')) and fields['options'] and len(fields['options'])>26):
                row=dict(ok=False,dt=0,res=None,usage=None,err='Unsupported option count for this adapter/route',unsupported=True,requested_model=model.model)
            else: row=invoke(model,state,q,1 if suite=='public' else 0)
            if not row['ok'] and any(t in (row.get('err') or '') for t in ['options per question','single-token labels']): row['unsupported']=True
            if infrastructure(row):
                data.update(status='paused',pause_reason=row['err'],updated_at=utcnow());save(path,data)
                return model.key+' PAUSED: '+row['err']
            row.update(fields,measured_at=utcnow(),cli_version=version)
            if index<len(data['rows']): data['rows'][index]=row
            else: data['rows'].append(row)
            save(path,data)
            failures=failures+1 if not row['ok'] and not row.get('unsupported') and 'decision probabilities' not in (row.get('err') or '') else 0
            if failures>=5:
                data.update(status='paused',pause_reason='five consecutive inference/transport failures');save(path,data)
                return model.key+' stopped: '+str(row.get('err'))
            if index%50==0 or index+1==total:
                print(f"{model.key} {suite}: {index+1}/{total}, failed={sum(not r['ok'] for r in data['rows'])}",flush=True)
        if suite=='own' and 'batch' not in data:
            state={'report':'Data stops arriving after ~6h; restarting the pod fixes it. Customers on the EU cluster notice gaps in dashboards.'}
            qs={f'q{i}':{'type':'noul','instructions':s} for i,s in enumerate(['Is this a resource leak?','Is this a billing issue?','Is a restart a workaround?','Does it affect production customers?','Is data lost permanently?','Is it a UI bug?','Does it need a human decision?','Is the root cause known?','Is it intermittent?','Is it region specific?'])}
            if model.model.startswith('respan/') or model.model=='scaledown/classify-1': state=json.dumps(state,ensure_ascii=False)
            batched=[call(model.provider,{'state':state,'questions':qs},model=model.model) for _ in range(3)]
            separate=[sum(invoke(model,state,q,0)['dt'] for q in qs.values()) for _ in range(2)]
            data.update(batch=[r['dt'] for r in batched if r['ok']],batch_ok=[r['ok'] for r in batched],batch_rows=batched,sep=separate)
        data.update(status='complete',completed_at=utcnow());data.pop('pause_reason',None);save(path,data)
    return model.key+' COMPLETE'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('models',nargs='*',choices=list(BY_ID));parser.add_argument('--all',action='store_true');parser.add_argument('--smoke',action='store_true');parser.add_argument('--per',type=int,default=50);parser.add_argument('--workers',type=int,default=24);parser.add_argument('--exclude-provider',action='append',default=[]);parser.add_argument('--refresh-smoke',action='store_true');args=parser.parse_args()
    selected=MODELS if args.all else [BY_ID[id] for id in args.models]
    selected=[m for m in selected if m.provider not in args.exclude_provider]
    if args.refresh_smoke:
        for m in selected:
            file=ROOT/'results'/f'smoke_{m.stem}.json'
            if file.exists(): file.unlink()
    if not selected: parser.error('Select models or --all')
    own,public=own_items(),public_items(args.per)
    reference=json.loads((ROOT/'results/hf_jev.json').read_text())
    if args.per==50 and [r['id'] for r in reference['rows']]!=[r['id'] for r in public]: raise RuntimeError('Public sample differs from original')
    version=subprocess.check_output([os.environ['JEV_BINARY'],'--version'],text=True).strip()
    print(f'{len(public)} matched public items; SHA256 {fingerprint(public)}',flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs=[pool.submit(smoke,m,own,version) if args.smoke else pool.submit(evaluate,m,own,public,version) for m in selected]
        for future in as_completed(jobs):
            try:
                result=future.result()
                if not args.smoke: print(result,flush=True)
            except Exception as err: print(f'RUN ERROR: {err}',flush=True)

if __name__=='__main__': main()
