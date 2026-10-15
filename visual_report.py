"""Visual benchmark presentation; raw statistics remain downloadable as JSON and CSV."""
import json
import re
from site_lib import esc,meta,PROFILE,REPO

def percent(x): return '—' if x is None else f'{x:.1%}'
def millis(x): return '—' if x is None else f'{x*1000:,.0f} ms'

def release_cards(data):
    cards=[]
    for pair in data.get('version_comparisons',[]):
        if pair['suite']!='public' or not pair['complete']:continue
        a=data['statistics'][pair['old']]['public'];b=data['statistics'][pair['new']]['public']
        title='TypeSafe' if pair['route']=='direct' else 'OpenRouter'
        delta=pair['accuracy_delta']*100
        lo,hi=pair['accuracy_delta_ci']
        conclusion='No clear accuracy change on this sample.' if lo<=0<=hi else 'Accuracy improved on this sample.' if lo>0 else 'Accuracy decreased on this sample.'
        cards.append(f'''<article class="release-route"><div class="eyebrow">{title} · {pair['common']:,} matched questions</div>
          <div class="release-score">{percent(a['acc'])}<span class="arrow">→</span><strong>{percent(b['acc'])}</strong></div>
          <p class="effect">{delta:+.2f} percentage points <span>accuracy</span></p>
          <div class="release-facts"><p><span>Median latency</span><b>{millis(a['p50'])} → {millis(b['p50'])}</b></p><p><span>Brier · lower is better</span><b>{a['brier']:.3f} → {b['brier']:.3f}</b></p><p><span>Cost / 1,000 calls</span><b>${a['cost']:.4f} → ${b['cost']:.4f}</b></p></div><p class="caption">{conclusion}</p>
          <details><summary>Paired evidence and versions</summary><p>Accuracy difference: {delta:+.2f} pp; paired bootstrap 95% interval {lo*100:+.2f} to {hi*100:+.2f} pp. Median of paired latency differences: {millis(pair['paired_latency_delta_p50'])}; mean: {millis(pair['paired_latency_delta_mean'])}.</p><p>{esc(', '.join(pair['old_models']))} → {esc(', '.join(pair['new_models']))}. Measurements began {esc(pair['old_started'])} and {esc(pair['new_started'])}. Different measurement times can affect latency; this is not a simultaneous experiment.</p></details></article>''')
    return ''.join(cards) or '<p class="caption">New-version measurements are still in progress. No previous result is relabelled as Jev 1.14.</p>'

def render(data,url,root):
    title='Decision model benchmark: Jev 1.14, accuracy, speed and cost'
    seo=meta(url,title,'A visual comparison of decision models: Jev 1.14 versus 1.13, accuracy, latency, token billing and provider versus OpenRouter routes.','Decision model benchmark: visual accuracy rankings and measured Jev 1.14 comparison',kind='article',modified=data['date'],ld={'@type':'TechArticle','headline':title,'citation':['https://typesafe.ai/blog/jev-1-14','https://huggingface.co/datasets/Praveenrajus/jev-bench',REPO]},social_title='Jev 1.14, measured',social_desc='Decision models compared visually: accuracy, speed, cost and API routes.')
    scatter=(root/'section.html').read_text()
    for key,value in {'__PTS__':json.dumps(data['points']),'__PENDING__':json.dumps(data['pending']),'__MODEL_COUNT__':str(len({m['identity'] for m in data['models']})),'{NOW}':data['date'],'{NPUB}':str(data['npub']),'{PER}':str(data['per']),'__PRICE_NOTE__':(root/'price-note.html').read_text()}.items():scatter=scatter.replace(key,value)
    scatter=scatter.replace('<main class="app" id="decision-models">','<section class="panel app tradeoff" id="tradeoff">').replace('</main>','</section>')
    scatter=re.sub(r'<header>.*?</header>','<header class="section-head"><div><div class="eyebrow">01 / The trade-off</div><h2>How much intelligence for the price?</h2><p class="caption">One labelled point per model and API route. Switch between token prices, measured request cost and speed.</p></div><a class="text-link" href="/decision-models/">Standalone chart ↗</a></header>',scatter,count=1,flags=re.S)
    template=(root/'report-visual.html').read_text()
    tokens={'__TITLE__':esc(title),'__SEO__':seo,'__DATE__':data['date'],'__MODELS__':str(len({m['identity'] for m in data['models']})),'__ROUTES__':str(len(data['points'])),'__RELEASE_CARDS__':release_cards(data),'__SCATTER__':scatter,'__REPORT_DATA__':json.dumps(data,separators=(',',':')).replace('<','\\u003c'),'__SCRIPT__':(root/'report-visual.js').read_text(),'__PROFILE__':PROFILE,'__REPO__':REPO}
    for key,value in tokens.items():template=template.replace(key,value)
    return template
