"""Generate visual report and reproducible chart/statistics downloads from saved calls."""
from dataclasses import asdict
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import json
import os
from pathlib import Path
from models import MODELS
from statistics_routes import load,paired_routes,paired_versions
from site_lib import esc,og_frame,SITE
from visual_report import render

ROOT=Path(__file__).parent
NOW=datetime.now(ZoneInfo('Europe/Berlin')).date().isoformat()
URL=os.environ.get('REPORT_URL',SITE+'/jev-benchmark/').strip()
analyses,raw=load();pairs=paired_routes(raw);versions=paired_versions(raw)
exclusions=json.loads((ROOT/'excluded_models.json').read_text()) if (ROOT/'excluded_models.json').exists() else []
catalog_path=ROOT/'pricing/openrouter-decisions-2026-10-15-jev114.json'
if not catalog_path.exists(): catalog_path=ROOT/'pricing/openrouter-decisions-2026-10-15.json'
catalog={r['id']:r.get('pricing',{}) for r in json.loads(catalog_path.read_text())['data']}

def published_cache_rate(m):
    if m.route=='OpenRouter':
        value=catalog.get(m.model,{}).get('input_cache_read')
        return float(value)*1_000_000 if value is not None else None
    return m.price_cached if m.provider in {'celeris','openai-chat'} else None

points=[];pending=[]
for m in MODELS:
    h=analyses[m.key].get('public');o=analyses[m.key].get('own')
    if not h or h['status']!='complete' or h['n']!=1100:
        pending.append(dict(id=m.key,name=m.label,route=m.route,n=h['n'] if h else 0,status=h['status'] if h else 'not started'))
        continue
    points.append(dict(id=m.key,name=m.label,identity=m.identity,route=m.route,sub=m.sub,color=m.color,acc=h['acc'],lo=h['ci'][0],hi=h['ci'][1],brier=h['brier'],p50=h['p50']*1000 if h['p50'] is not None else None,p95=h['p95']*1000 if h['p95'] is not None else None,cost=h['cost'],apiCost=h['api_cost'],fail=h['fail'],unsupported=h['unsupported'],n=h['n'],success=h['success'],own=o['acc'] if o else None,noul=h['noul_acc'],noulLo=h['noul_ci'][0],noulHi=h['noul_ci'][1],noulN=h['noul_n'],priceIn=m.price_in,priceOut=m.price_out,priceCached=m.price_cached,priceCachedOfficial=published_cache_rate(m),priceSource=m.source,priceChecked='2026-10-15',inputTokens=h['input'],outputTokens=h['output'],cachedTokens=h['cached'],usageN=h['usage_samples'],models=h['models'],upstreams=h['upstreams'],date=h['completed_at'],adapter=m.adapter))
D=dict(date=NOW,npub=1100,per=50,hw=round(sum((p['hi']-p['lo'])*50 for p in points)/len(points),1) if points else 0,points=points,pending=pending,models=[asdict(m) for m in MODELS],statistics=analyses,route_comparisons=pairs,version_comparisons=versions,exclusions=exclusions,release=dict(model='Jev 1.14',released='2026-10-14',source='https://typesafe.ai/blog/jev-1-14',price_checked='2026-10-15'))
(ROOT/'data.json').write_text(json.dumps(D,indent=2,allow_nan=False))
with (ROOT/'statistics.csv').open('w',newline='') as out:
    fields=['model','route','suite','status','n','success','fail','unsupported','request_errors','refused','infrastructure_excluded','scored','acc','brier','p50','p95','p99','mean','min','max','input','output','cached','cost','api_cost','known_total_list_cost','known_total_api_cost','retries','attempted_p50','attempted_p95','attempted_p99','cli_versions','started_at','completed_at']
    writer=csv.DictWriter(out,fieldnames=fields,lineterminator="\n");writer.writeheader()
    for m in MODELS:
        for suite,s in analyses[m.key].items():
            writer.writerow({f:({'model':m.model,'route':m.route,'suite':suite}.get(f,s['attempted_latency'].get(f.removeprefix('attempted_')) if f.startswith('attempted_') else '; '.join(s['cli_versions']) if f=='cli_versions' else s.get(f))) for f in fields})
(ROOT/'report.html').write_text(render(D,URL,ROOT))
body=''
top=sorted(points,key=lambda p:-p['acc'])[:7]
for i,p in enumerate(top):
    y=236+i*46;label=p['name']+(' · OR' if p['route']=='OpenRouter' else '')
    body+=f'<text x="64" y="{y+24}" font-size="21" fill="#eee">{esc(label)}</text><rect x="455" y="{y}" width="{380*p["acc"]:.0f}" height="28" rx="5" fill="{p["color"]}"/><text x="875" y="{y+23}" font-size="23" fill="#ccc">{p["acc"]:.1%}</text>'
og_frame('og','DECISION MODEL LAB','Jev 1.14, measured',f'{len(points)} complete routes · accuracy, speed and token billing','#1749c7',body,footer='1,100 matched public questions per complete run · '+NOW)
print(f'Built visual report: {len(points)} complete routes; {len(pending)} pending/partial; statistics exported')
