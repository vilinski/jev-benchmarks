(() => {
  'use strict';
  const D=JSON.parse(document.getElementById('benchmark-data').textContent);
  const all=D.points, stats=D.statistics, $=id=>document.getElementById(id);
  const esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const finite=Number.isFinite, pct=v=>(v*100).toFixed(1)+'%', usd=v=>'$'+v.toFixed(4), ms=v=>Math.round(v).toLocaleString('en-US')+' ms';
  const rate=v=>'$'+Number(v.toFixed(6)), signed=(v,digits=2)=>(v>=0?'+':'−')+Math.abs(v).toFixed(digits);
  const label=p=>p.name+(p.route==='OpenRouter'?' · OR':'');
  const filtered=id=>all.filter(p=>$(id).value==='all'||p.route===$(id).value);
  const metricText={acc:'accuracy',brier:'Brier score',noul:'yes/no accuracy',own:'own-set accuracy'};
  const short=(value,n)=>value.length>n?value.slice(0,Math.max(1,n-1))+'…':value;
  function box(id,rows,gap=35){
    const w=Math.max(340,Math.round($(id).clientWidth||660)),left=w<500?146:w<850?215:270,right=w<500?71:95;
    return {w,left,right,span:w-left-right,top:34,gap,h:48+gap*rows};
  }
  function begin(b,title){return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${b.w} ${b.h}" role="img" aria-label="${esc(title)}">`;}
  function axis(b,max,format,lo=0){
    let s='';
    for(let i=0;i<=4;i++){
      const x=b.left+b.span*i/4,v=lo+(max-lo)*i/4;
      s+=`<line class="chart-guide" x1="${x}" x2="${x}" y1="25" y2="${b.h-12}"/><text class="chart-tick" x="${x}" y="15" text-anchor="middle">${esc(format(v))}</text>`;
    }
    return s;
  }
  function rowStart(b,p,y,title){
    const suffix=p.route==='OpenRouter'?' · OR':'',n=Math.floor((b.left-15)/6.2)-suffix.length;
    return `<g class="chart-row" tabindex="0" aria-label="${esc(title)}"><title>${esc(title)}</title><rect class="row-bg" x="0" y="${y-15}" width="${b.w}" height="${b.gap-1}" rx="5" fill="transparent"/><text class="chart-label" x="0" y="${y+4}">${esc(short(p.name,n)+suffix)}</text>`;
  }
  function bars(id,rows,{format=pct,max=null,unit='',lower=false}={}){
    if(!rows.length){$(id).innerHTML='<p class="empty">No reported measurements for this selection.</p>';return;}
    rows=rows.filter(r=>finite(r.value)).sort((a,b)=>lower?a.value-b.value:b.value-a.value);
    const b=box(id,rows.length),limit=max??(Math.max(...rows.map(r=>r.value))*1.08||1);
    let s=begin(b,unit)+axis(b,limit,format);
    rows.forEach((p,i)=>{
      const y=b.top+i*b.gap,x=b.left+b.span*p.value/limit;
      s+=rowStart(b,p,y,`${label(p)}: ${format(p.value)} ${unit}. ${p.detail||''}`);
      if(p.value>0)s+=`<rect x="${b.left}" y="${y-7}" width="${Math.max(.7,x-b.left)}" height="14" rx="3" fill="${p.color}" opacity=".84"/>`;
      else s+=`<circle cx="${b.left}" cy="${y}" r="3.5" fill="${p.color}"/>`;
      s+=`<text class="chart-number" x="${b.w-3}" y="${y+4}" text-anchor="end">${esc(format(p.value))}</text></g>`;
    });
    $(id).innerHTML=s+'</svg>';
  }
  const datasets=[...new Set(all.flatMap(p=>Object.keys(stats[p.id].public.per)))].sort();
  $('rankDataset').insertAdjacentHTML('beforeend',datasets.map(d=>`<option value="${esc(d)}">${esc(d)}</option>`).join(''));
  function rank(){
    const metric=$('rankMetric').value,dataset=$('rankDataset').value;
    $('rankDataset').disabled=metric!=='acc';
    const per=metric==='acc'&&dataset!=='all';
    const rows=filtered('rankRoute').map(p=>({...p,value:per?stats[p.id].public.per[dataset]:p[metric]})).filter(p=>finite(p.value));
    bars('rankChart',rows,{format:metric==='brier'?v=>v.toFixed(3):pct,max:metric==='brier'?null:1,lower:metric==='brier',unit:per?dataset:metricText[metric]});
    $('rankNote').textContent=per?dataset+': 50 identical questions per complete route. Bars start at zero; hover for exact values.':metric==='own'?'Own set: 60 tasks × 3 repetitions; distinct from public labels. Bars start at zero.':metric==='noul'?'Yes/no accuracy on the same 350 public questions. Bars start at zero.':'Bars start at zero. OR = OpenRouter; unmarked models use the provider. Full coverage and uncertainty remain in the downloads.';
  }
  function latency(){
    const rows=filtered('latencyRoute').filter(p=>finite(p.p50)).sort((a,b)=>a.p50-b.p50),range=$('latencyMode').value==='range';
    const long=p=>p.p95>5*p.p50;
    const b=box('latencyChart',rows.length,36),max=Math.max(1,...rows.map(p=>p.p50),...(range?rows.filter(p=>!long(p)).map(p=>p.p95):[]))*1.12;
    let s=begin(b,'Successful call latency, median and optional p95')+axis(b,max,v=>Math.round(v));
    rows.forEach((p,i)=>{
      const y=b.top+i*b.gap,x=b.left+b.span*p.p50/max,q=stats[p.id].public;
      s+=rowStart(b,p,y,`${label(p)}: p50 ${ms(p.p50)}, p95 ${ms(p.p95)}, p99 ${ms(q.p99*1000)}, min ${ms(q.min*1000)}, max ${ms(q.max*1000)}. ${q.latency_samples} successful timing samples; ${q.retries} retries.`);
      if(range){
        const end=long(p)?b.left+b.span:b.left+b.span*p.p95/max;
        s+=`<line x1="${x}" y1="${y}" x2="${end}" y2="${y}" stroke="${p.color}" stroke-width="2" stroke-opacity=".55" ${long(p)?'stroke-dasharray="3 4"':''}/>`;
        if(long(p))s+=`<path d="M${end-5},${y-4}L${end},${y}L${end-5},${y+4}" fill="none" stroke="${p.color}"/>`;
        else s+=`<line x1="${end}" y1="${y-4}" x2="${end}" y2="${y+4}" stroke="${p.color}"/>`;
      }
      s+=`<circle cx="${x}" cy="${y}" r="4.5" fill="${p.color}"/><text class="chart-number" x="${b.w-3}" y="${y+3}" text-anchor="end">${Math.round(p.p50)}</text>`;
      if(range)s+=`<text class="chart-sub" x="${b.w-3}" y="${y+15}" text-anchor="end">p95 ${Math.round(p.p95).toLocaleString('en-US')}</text>`;
      s+='</g>';
    });
    $('latencyChart').innerHTML=s+'</svg>';
    const omitted=range?rows.filter(long):[];
    $('latencyNote').textContent='Axis and values are milliseconds. '+(range?'Dot = p50; line ends at p95. ':'Switch to “Median → p95” to show the tail. ')+(omitted.length?'Off-scale p95: '+omitted.map(p=>label(p)+' '+ms(p.p95)).join('; ')+'. Arrows preserve readability; the full values remain visible.':'Hover any route for p95, p99, min and max.');
  }
  function billing(){
    const metric=$('billingMetric').value,stack=metric==='cost',rows=all.filter(p=>finite(p[metric])).sort((a,b)=>a[metric]-b[metric]);
    $('billingLegend').style.display=stack?'flex':'none';
    const format=metric.startsWith('price')?rate:usd;
    if(!stack){bars('billingChart',rows.map(p=>({...p,value:p[metric],detail:'Prices checked '+p.priceChecked})),{format,unit:metric.startsWith('price')?'USD per million tokens':'USD per 1,000 calls',lower:true});}
    else{
      const b=box('billingChart',rows.length),max=Math.max(...rows.map(p=>p.cost),.001)*1.08;
      let s=begin(b,'Estimated cost per 1,000 recorded calls, separated by input, cache and output')+axis(b,max,usd);
      rows.forEach((p,i)=>{
        const y=b.top+i*b.gap,parts=[(p.inputTokens-p.cachedTokens)*p.priceIn/1000,p.cachedTokens*p.priceCached/1000,p.outputTokens*p.priceOut/1000],colours=['#466bba','#8ca7de','#c75b98'];
        s+=rowStart(b,p,y,`${label(p)}: ${usd(p.cost)} / 1,000 calls. Input ${usd(parts[0])}; cache ${usd(parts[1])}; output ${usd(parts[2])}. Known usage ${p.usageN}/${p.n} calls; mean tokens ${p.inputTokens.toFixed(1)} input, ${p.cachedTokens.toFixed(1)} cached subset, ${p.outputTokens.toFixed(1)} output.`);
        let x=b.left;
        parts.forEach((value,j)=>{const width=b.span*value/max;if(width>0)s+=`<rect x="${x}" y="${y-7}" width="${width}" height="14" fill="${colours[j]}"/>`;x+=width;});
        if(p.cost===0)s+=`<circle cx="${b.left}" cy="${y}" r="3.5" fill="${p.color}"/>`;
        s+=`<text class="chart-number" x="${b.w-3}" y="${y+4}" text-anchor="end">${usd(p.cost)}</text></g>`;
      });
      $('billingChart').innerHTML=s+'</svg>';
    }
    const missing=all.length-rows.length;
    const note={cost:'USD per 1,000 calls with known usage. Each route uses its own input, cache and output counts; hover for coverage and the cost breakdown. This depends on benchmark request lengths.',priceIn:'Official input prices, USD per million tokens. Independent of the benchmark request length. Output and cache charges are separate.',priceOut:'Official output prices, USD per million tokens. A $0 output price does not mean the input is free.',priceCachedOfficial:'Published cache-read prices, USD per million input tokens. Unpublished rates are unknown, not free.',apiCost:'Cost reported by the API, averaged over calls with reported billing, multiplied by 1,000. This is not the complete account invoice.'};
    $('billingNote').textContent=note[metric]+(missing?' '+missing+' routes omitted because '+(metric==='apiCost'?'API billing was not returned.':'no cache-read price was published.'):'')+' Prices checked 2026-10-15.';
  }
  function coverage(){
    const rows=all.filter(p=>!$('issuesOnly').checked||p.success<p.n).sort((a,b)=>(a.success/a.n)-(b.success/b.n));
    if(!rows.length){$('coverageChart').innerHTML='<p class="empty">Every selected route answered every question.</p>';return;}
    const b=box('coverageChart',rows.length),colours=['#4b9b87','#dfad5b','#c777a1','#d16a66'];
    let s=begin(b,'Public response coverage by status')+axis(b,1,v=>Math.round(v*100)+'%');
    rows.forEach((p,i)=>{
      const y=b.top+i*b.gap,q=stats[p.id].public,parts=[q.success,q.unsupported,q.refused,q.request_errors];
      s+=rowStart(b,p,y,`${label(p)}: ${q.success} answered; ${q.unsupported} unsupported; ${q.refused} refused/invalid; ${q.request_errors} request errors; ${q.n} requests. ${q.infrastructure_excluded} infrastructure failures excluded.`);
      let x=b.left;parts.forEach((value,j)=>{const width=b.span*value/q.n;if(width>0)s+=`<rect x="${x}" y="${y-7}" width="${width}" height="14" fill="${colours[j]}"/>`;x+=width;});
      s+=`<text class="chart-number" x="${b.w-3}" y="${y+4}" text-anchor="end">${pct(q.success/q.n)}</text></g>`;
    });
    $('coverageChart').innerHTML=s+'</svg>';
  }
  function own(){
    const metric=$('ownMetric').value,timing=metric==='batch_mean'||metric==='sequential_mean';
    const rows=all.map(p=>({...p,value:stats[p.id].own?.[metric]})).filter(p=>finite(p.value)).map(p=>({...p,value:p.value*(timing?1000:1)}));
    const format=timing?ms:['decision_flips','ambiguous_abstain'].includes(metric)?pct:v=>v.toFixed(3);
    bars('ownChart',rows,{format,max:['decision_flips','ambiguous_abstain'].includes(metric)?1:null,lower:metric!=='ambiguous_abstain',unit:$('ownMetric').selectedOptions[0].textContent});
    const notes={decision_flips:'Share of items whose top decision changed across available repeated answers. Lower is more stable; stability alone does not establish correctness.',brier:'Own-set Brier score. Lower is better; read with answer coverage.',ambiguous_abstain:'Share of successful ambiguous yes/no tasks returning a probability between 0.25 and 0.75.',severity_mae:'Mean absolute error of the returned score on own-set severity tasks, successful answers only.',batch_mean:'Mean time for one request containing 10 independent questions (three measurements). Conditional on successful batch responses.',sequential_mean:'Mean total time for 10 separate questions (two measurements). Measured separately from the batch requests.'};
    $('ownNote').textContent=notes[metric];
  }
  function routes(){
    const metric=$('routeMetric').value,format=metric==='p50'?ms:metric==='acc'?pct:usd;
    const pairs=D.route_comparisons.filter(p=>p.suite==='public'&&p.direct_complete&&p.gateway_complete);
    if(!pairs.length){$('routeChart').innerHTML='<p class="empty">No complete paired route measurements yet.</p>';return;}
    const rows=pairs.map(pair=>({pair,a:all.find(p=>p.identity===pair.identity&&p.route==='direct'),b:all.find(p=>p.identity===pair.identity&&p.route==='OpenRouter')})).filter(r=>r.a&&r.b&&finite(r.a[metric])&&finite(r.b[metric]));
    const b=box('routeChart',rows.length,94),values=rows.flatMap(r=>[r.a[metric],r.b[metric]]);
    const lo=metric==='acc'?Math.max(0,Math.min(...values)-.025):0,max=metric==='acc'?Math.min(1,Math.max(...values)+.025):Math.max(...values)*1.18||1;
    const X=v=>b.left+(v-lo)/(max-lo)*b.span;
    let s=begin(b,'Provider and OpenRouter, complete matched route comparisons')+axis(b,max,format,lo);
    rows.forEach(({pair,a,b:gateway},i)=>{
      const y=b.top+15+i*b.gap,xa=X(a[metric]),xb=X(gateway[metric]);
      const delta=metric==='p50'?signed(pair.paired_latency_delta_p50*1000,0)+' ms paired median':metric==='acc'?signed(pair.accuracy_delta*100)+' pp':signed(pair.paired_cost_delta_per_1000,5)+' USD / 1K matched successful calls';
      s+=rowStart(b,{...a,name:pair.identity},y,`${pair.identity}: provider ${format(a[metric])}, OpenRouter ${format(gateway[metric])}; OR minus provider ${delta}. ${pair.common} matched questions. Paired accuracy 95% interval ${pair.accuracy_delta_ci.map(v=>signed(v*100)).join(' to ')} pp.`);
      s+=`<line x1="${xa}" y1="${y-5}" x2="${xb}" y2="${y+5}" stroke="#aab7ce" stroke-width="2"/><circle cx="${xa}" cy="${y-5}" r="5" fill="#587694"/><circle cx="${xb}" cy="${y+5}" r="5" fill="#1749c7"/><text class="chart-sub" x="${xa}" y="${y-16}" text-anchor="middle">${esc(format(a[metric]))}</text><text class="chart-sub" x="${xb}" y="${y+23}" text-anchor="middle">${esc(format(gateway[metric]))}</text><text class="chart-sub" x="0" y="${y+36}">OR − provider: ${esc(delta)}</text></g>`;
    });
    $('routeChart').innerHTML=s+'</svg>';
  }
  function pending(){
    if(!D.pending.length){$('pendingRoutes').hidden=true;return;}
    $('pendingRoutes').innerHTML='<div class="eyebrow">Partial measurements / excluded from rankings</div><p class="caption">Cloudflare’s daily free allocation stopped these provider runs. OpenRouter measurements are complete. No paid plan was enabled.</p><div class="pending-grid">'+D.pending.map(p=>`<article class="pending-card"><strong>${esc(p.name)}</strong><span>${p.n.toLocaleString('en-US')} / 1,100 provider questions · ${esc(p.status)}</span><div class="progress"><b style="width:${Math.min(100,p.n/11)}%"></b></div></article>`).join('')+'</div>';
  }
  const actions={rankMetric:rank,rankDataset:rank,rankRoute:rank,latencyMode:latency,latencyRoute:latency,billingMetric:billing,issuesOnly:coverage,ownMetric:own,routeMetric:routes};
  Object.entries(actions).forEach(([id,fn])=>$(id).addEventListener('change',fn));
  function render(){rank();latency();billing();coverage();own();routes();}
  pending();render();
  let resize;
  window.addEventListener('resize',()=>{clearTimeout(resize);resize=setTimeout(render,120);});
})();
