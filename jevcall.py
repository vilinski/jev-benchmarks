"""One `jev run` call: used by the own-set runner and the public-sample runner."""
import json, os, re, subprocess, time

def call(provider, body, retries=0, timeout=120, model=None):
    """Send a System One request body through the jev CLI; returns timing, parsed answers and the usage line."""
    t = time.perf_counter()
    cmd = [os.environ.get("JEV_BINARY", "jev"), "run", "-", "-p", provider, "--retries", str(retries), "--timeout", str(timeout), "--raw"]
    if model:
        body = {**body, "model": model}
        cmd.extend(["--model", model])
    try:
        p = subprocess.run(cmd, input=json.dumps(body), capture_output=True, text=True, timeout=timeout * (retries + 1) + 30)
    except subprocess.TimeoutExpired:
        return dict(ok=False,dt=time.perf_counter()-t,res=None,usage=None,requested_model=model,err="CLI process timeout")
    dt = time.perf_counter() - t
    usage = next((l[6:].strip() for l in p.stderr.splitlines() if l.startswith("usage:")), None)
    try:
        raw = json.loads(p.stdout)
        res = raw.get("answers")
    except ValueError:
        raw = res = None
    return dict(ok=p.returncode == 0 and res is not None, dt=dt, res=res, usage=usage,
                requested_model=model or body.get("model"), returned_model=(raw or {}).get("model"),
                token_usage=(raw or {}).get("usage"),
                request_id=next((l[9:].strip() for l in p.stderr.splitlines() if l.startswith("request:")), None),
                upstream_provider=(raw or {}).get("provider"),
                upstream_models=sorted({v["model"] for v in (raw or {}).get("provider_responses",{}).values() if v.get("model")}),
                retries=sum("retrying in" in line for line in p.stderr.splitlines()),
                raw_response=raw, adapter=(raw or {}).get("adapter"),
                err=None if p.returncode == 0 else re.sub(r"/accounts/[^/]+/", "/accounts/<account>/", p.stderr[-1000:]))
