"""Copy generated static assets into the owner's website checkout and make an offline preview."""
import argparse
import base64
import html
import json
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parent

def stage(target,preview):
    target=Path(target).resolve()
    if target.name!='ai.vilinski.dev':raise ValueError('Target must be the ai.vilinski.dev directory')
    files=['index.html','og.png','data.json','statistics.csv','pricing-audit.json']
    data=json.loads((ROOT/'data.json').read_text())
    ids=[p['id'] for p in data['points']]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate chart point IDs')
    for directory in ['decision-models','jev-benchmark']:
        out=target/directory;out.mkdir(parents=True,exist_ok=True)
        for name in files:
            source=ROOT/'site'/directory/name
            if not source.is_file():raise FileNotFoundError(source)
            temp=out/(name+'.tmp');shutil.copy2(source,temp);temp.replace(out/name)
    if preview:
        pages=[]
        for directory in ['decision-models','jev-benchmark']:
            content=(target/directory/'index.html').read_text()
            for name,mime in [('data.json','application/json'),('statistics.csv','text/csv'),('pricing-audit.json','application/json')]:
                encoded=base64.b64encode((target/directory/name).read_bytes()).decode()
                content=content.replace('href="'+name+'"','href="data:'+mime+';base64,'+encoded+'" download="'+name+'"')
            pages.append(content)
        doc='<!doctype html><html><head><meta charset="utf-8"><title>Decision models — local preview</title><style>body{margin:0;background:var(--agterm-background,#16171a);color:var(--agterm-foreground,#eee);font:14px system-ui}nav{padding:8px;display:flex;gap:8px}button{padding:7px 12px;border:1px solid #8885;border-radius:6px;background:transparent;color:inherit;cursor:pointer}iframe{width:100%;height:calc(100vh - 55px);border:0;display:none}iframe.active{display:block}</style></head><body><nav><button data-page="0">Model explorer</button><button data-page="1">Visual benchmark report</button><span>Local HTML preview</span></nav>'
        for i,page in enumerate(pages):doc+='<iframe id="p'+str(i)+'" class="'+('active' if i==0 else '')+'" srcdoc="'+html.escape(page,quote=True)+'"></iframe>'
        doc+="""<script>const show=n=>{document.querySelectorAll('iframe').forEach((f,i)=>f.classList.toggle('active',i===n));};document.querySelectorAll('button').forEach(b=>b.onclick=()=>show(+b.dataset.page));document.querySelectorAll('iframe').forEach(f=>f.onload=()=>f.contentDocument.addEventListener('click',e=>{const a=e.target.closest('a');if(!a)return;const href=a.getAttribute('href');if(href==='/jev-benchmark/'||href==='/decision-models/'){e.preventDefault();show(href==='/jev-benchmark/'?1:0);}}));</script></body></html>"""
        Path(preview).write_text(doc)
    progress=target.parents[2]/'decision-models-progress.md'
    progress.write_text('# Decision model comparison — current local review\n\n'+str(len(data['points']))+' complete route benchmarks, '+str(len({p["identity"] for p in data['points']}))+' models.\n\nPartial routes: '+json.dumps(data['pending'],ensure_ascii=False)+'\n\nFull sources, checkpoints and next steps: '+str(ROOT/'RESUME.md')+'\nLocal HTML and statistics are staged. No remote deployment.\n')
    print(f'Staged {len(data["points"])} complete routes, {len(data["pending"])} partial/pending; no remote deployment')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('target');parser.add_argument('--preview');args=parser.parse_args();stage(args.target,args.preview)
