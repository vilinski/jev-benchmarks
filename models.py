"""One registry entry per hosted model. Price source, route and adapter travel with it."""
from dataclasses import dataclass
import json
from pathlib import Path

@dataclass(frozen=True)
class Model:
    key: str
    label: str
    sub: str
    color: str
    provider: str
    stem: str
    price_in: float
    price_out: float
    price_cached: float
    model: str
    source: str
    adapter: str
    identity: str
    route: str

MODELS = [Model(**row) for row in json.loads((Path(__file__).parent/'model_registry.json').read_text())]
BY_KEY = {m.key:m for m in MODELS}
BY_ID = {m.model:m for m in MODELS}
CHAT = next(m for m in MODELS if m.provider=='openai-chat')
RESULTS = 'results'

def billed_tokens(row):
    """Input includes its cached subset. Never substitute own-set output into public costs."""
    usage=row.get('token_usage') or {}
    if usage:
        incoming=usage.get('input_tokens',usage.get('prompt_tokens',0))
        outgoing=usage.get('output_tokens',usage.get('completion_tokens',0))
        details=usage.get('input_tokens_details',usage.get('prompt_tokens_details',{})) or {}
        cached=min(incoming,details.get('cached_tokens',0))
        return incoming,outgoing,cached
    import re
    found=re.match(r'(\d+) in / (\d+) out',row.get('usage') or '')
    return (int(found[1]),int(found[2]),0) if found else (None,None,None)

def cost_per_call(row,model):
    incoming,outgoing,cached=billed_tokens(row)
    if incoming is None: return None
    return ((incoming-cached)*model.price_in+cached*model.price_cached+outgoing*model.price_out)/1_000_000
