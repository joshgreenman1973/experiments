"""Fetches every source page and checks that the figure cited from it actually
appears. Purely mechanical: it does not judge wording, only presence."""
import json, re, subprocess, sys, os, concurrent.futures as cf
SCRATCH='/private/tmp/claude-501/-Users-joshgreenman-Experiments/6216c55a-d97c-4e85-9ec9-ef006bae7432/scratchpad/verify'
os.makedirs(SCRATCH, exist_ok=True)
src=json.load(open('pairings-src.json'))['items']

def fetch(url, path):
    if os.path.exists(path) and os.path.getsize(path)>200: return open(path,'rb').read()
    cmd=['curl','-sL','--globoff','--max-time','45','-A','Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',url,'-o',path]
    subprocess.run(cmd,capture_output=True)
    return open(path,'rb').read() if os.path.exists(path) else b''

def totext(raw, path):
    if raw[:4]==b'%PDF':
        try:
            import fitz; return ''.join(p.get_text() for p in fitz.open(path))
        except Exception: return ''
    try: s=raw.decode('utf-8','replace')
    except Exception: s=str(raw)
    s=re.sub(r'<script.*?</script>|<style.*?</style>','',s,flags=re.S|re.I)
    import html as H
    return H.unescape(re.sub(r'<[^>]+>',' ',s))

def variants(v):
    """The number as it might be written on the page."""
    out=set()
    if v is None: return out
    for n in {v, round(v)}:
        if isinstance(n,float) and n.is_integer(): n=int(n)
        out.add(f"{n:,}"); out.add(str(n))
        if isinstance(n,int): out.add(f"{n:,}".replace(',','.')); out.add(f"{n:,}".replace(',',' '))
    # scaled forms: 1282000000 -> 1,282 ; 49.703 -> 49,703 ; 3.1e6 -> 3.1
    for div,dec in ((1e9,3),(1e6,3),(1e3,3),(1,3),(1e6,2),(1e9,2),(1,1),(1e6,1),(1e9,1)):
        x=v/div
        if 0.05 <= abs(x) < 1e7:
            for d in range(0,4):
                s=f"{x:,.{d}f}"
                out.add(s); out.add(s.replace(',','.')); out.add(s.replace(',',' '))
                out.add(s.rstrip('0').rstrip('.') if '.' in s else s)
    return {o for o in out if len(o)>=3}

def check(job):
    idx, side, url, val, place = job
    path=os.path.join(SCRATCH, f"{idx}_{side}." + ('pdf' if url.lower().endswith('.pdf') else 'dat'))
    try:
        raw=fetch(url,path)
        if not raw: return (idx,side,place,'FETCH FAILED','')
        t=totext(raw,path); t=re.sub(r'\s+',' ',t)
        if len(t)<80: return (idx,side,place,'EMPTY/BLOCKED','')
        low=t.lower()
        if any(k in low[:1500] for k in ('403 forbidden','access denied','are you a robot','enable javascript','captcha')):
            return (idx,side,place,'BLOCKED','')
        for cand in sorted(variants(val), key=len, reverse=True):
            i=t.find(cand)
            if i>=0: return (idx,side,place,'FOUND',t[max(0,i-90):i+60])
        return (idx,side,place,'NOT FOUND','')
    except Exception as e:
        return (idx,side,place,f'ERR {type(e).__name__}','')

jobs=[]
for i,it in enumerate(src,1):
    jobs.append((i,'nyc',it['nyc_url'],it['nyc_value'],it['place']))
    jobs.append((i,'match',it['match_url'],it['match_value'],it['place']))
res=[]
with cf.ThreadPoolExecutor(max_workers=8) as ex:
    for r in ex.map(check, jobs): res.append(r)
import collections
print(dict(collections.Counter(r[3] for r in res)))
print('\n--- not found on the page (needs a human look):')
for r in res:
    if r[3]=='NOT FOUND': print(f"  {r[0]:>3} {r[1]:<6} {r[2]}")
print('\n--- could not read the page (blocked or failed):')
for r in res:
    if r[3] in ('BLOCKED','EMPTY/BLOCKED','FETCH FAILED') or r[3].startswith('ERR'):
        print(f"  {r[0]:>3} {r[1]:<6} {r[2]:<26} {r[3]}")
json.dump([{'n':r[0],'side':r[1],'place':r[2],'status':r[3],'context':r[4][:220]} for r in res], open('number-presence.json','w'), indent=1)
