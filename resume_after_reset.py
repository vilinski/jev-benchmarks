"""Resume direct Cloudflare once at its next UTC reset, then rebuild the local review artifacts."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--at',required=True);parser.add_argument('--coding-page',required=True);parser.add_argument('--stage-to',required=True);parser.add_argument('--preview',required=True);args=parser.parse_args()
    deadline=datetime.fromisoformat(args.at)
    if deadline.tzinfo is None:raise ValueError('Explicit UTC offset required')
    print('Direct Cloudflare continuation at '+deadline.isoformat(),flush=True)
    while True:
        remaining=(deadline-datetime.now(timezone.utc)).total_seconds()
        if remaining<=0:break
        time.sleep(min(30,remaining))
    def run(*argv):subprocess.run([sys.executable,*argv],cwd=ROOT,check=True)
    run(str(ROOT/'run_variants.py'),'clef','clef-flash','clef-omni','--refresh-smoke','--workers','3')
    run(str(ROOT/'report.py'))
    run(str(ROOT/'site.py'),args.coding_page)
    run(str(ROOT/'stage_site.py'),args.stage_to,'--preview',args.preview)
    data=json.loads((ROOT/'data.json').read_text())
    note='\n## UTC-reset continuation '+datetime.now(timezone.utc).isoformat()+'\n\n'+str(len(data['points']))+' complete route benchmarks. Remaining partial runs: '+json.dumps(data['pending'])+'\n'
    with (ROOT/'RESUME.md').open('a') as out:out.write(note)
    print('Local report and preview refreshed; no remote deployment',flush=True)

if __name__=='__main__':main()
