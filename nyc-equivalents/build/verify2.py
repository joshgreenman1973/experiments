"""Second full verification sweep. Fetches every source page and checks the cited
figure appears, with per-host handling for sites that block plain scripts."""
import json, re, subprocess, os, html, concurrent.futures as cf
SC='/private/tmp/claude-501/-Users-joshgreenman-Experiments/6216c55a-d97c-4e85-9ec9-ef006bae7432/scratchpad/v2'
os.makedirs(SC, exist_ok=True)
src=json.load(open('pairings-src.json'))['items']
UA_BROWSER='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
UA_SEC='NYC-equivalents fact-check josh.greenman@gmail.com'
KEY=subprocess.run(['security','find-generic-password','-s','CENSUS_API_KEY','-w'],capture_output=True,text=True).stdout.strip()

def rewrite(url):
    """Some hosts refuse scripts on the HTML but serve the same data elsewhere."""
    m=re.search(r'fred\.stlouisfed\.org/series/([A-Z0-9]+)',url)
    if m: return f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={m.group(1)}', None
    if 'api.census.gov' in url and KEY and 'key=' not in url:
        return url+('&' if '?' in url else '?')+'key='+KEY, None
    return url, None

def fetch(url, path):
    url2,_=rewrite(url)
    ua = UA_SEC if 'sec.gov' in url2 else UA_BROWSER
    if not (os.path.exists(path) and os.path.getsize(path)>200):
        subprocess.run(['curl','-sL','--globoff','--max-time','60','-A',ua,
                        '-H','Accept-Language: en-US,en;q=0.9',url2,'-o',path],capture_output=True)
    return open(path,'rb').read() if os.path.exists(path) else b''

def totext(raw, path):
    if raw[:4]==b'%PDF':
        try:
            import fitz; return ''.join(p.get_text() for p in fitz.open(path))
        except Exception: return ''
    if raw[:2]==b'PK':
        try:
            import openpyxl, io
            wb=openpyxl.load_workbook(path,data_only=True,read_only=True); out=[]
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    out.append(' '.join(str(c) for c in row if c is not None))
            return ' '.join(out)
        except Exception: return ''
    s=raw.decode('utf-8','replace')
    s=re.sub(r'<script.*?</script>|<style.*?</style>','',s,flags=re.S|re.I)
    return html.unescape(re.sub(r'<[^>]+>',' ',s))

def variants(v):
    out=set()
    if v is None: return out
    for n in {v, round(v)}:
        if isinstance(n,float) and n.is_integer(): n=int(n)
        out.add(f"{n:,}"); out.add(str(n))
        out.add(f"{n:,}".replace(',','.')); out.add(f"{n:,}".replace(',',' '))
    for div in (1e12,1e9,1e6,1e3,1):
        x=v/div
        if 0.05 <= abs(x) < 1e7:
            for d in range(0,4):
                s=f"{x:,.{d}f}"
                for c in (s, s.replace(',','.'), s.replace(',',' ')):
                    out.add(c)
                    if '.' in c: out.add(c.rstrip('0').rstrip('.'))
    return {o for o in out if len(o)>=3}

def check(job):
    idx, side, url, val, place = job
    ext='pdf' if url.lower().endswith('.pdf') else ('xlsx' if url.lower().endswith('.xlsx') else 'dat')
    path=os.path.join(SC, f"{idx}_{side}.{ext}")
    raw=fetch(url,path)
    if not raw: return (idx,side,place,'FETCH FAILED','')
    t=re.sub(r'\s+',' ',totext(raw,path))
    if len(t)<80: return (idx,side,place,'UNREADABLE','')
    low=t.lower()[:2000]
    if any(k in low for k in ('403 forbidden','access denied','request blocked','are you a robot','undeclared automated tool','missing key','captcha')):
        return (idx,side,place,'BLOCKED','')
    for cand in sorted(variants(val), key=len, reverse=True):
        i=t.find(cand)
        if i>=0: return (idx,side,place,'FOUND',t[max(0,i-100):i+70])
    return (idx,side,place,'NOT FOUND',t[:150])

jobs=[]
for i,it in enumerate(src,1):
    jobs.append((i,'nyc',it['nyc_url'],it['nyc_value'],it['place']))
    jobs.append((i,'match',it['match_url'],it['match_value'],it['place']))
res=[]
with cf.ThreadPoolExecutor(max_workers=8) as ex:
    for r in ex.map(check, jobs): res.append(r)
import collections
print(dict(collections.Counter(r[3] for r in res)))
for status in ('NOT FOUND','BLOCKED','UNREADABLE','FETCH FAILED'):
    rows=[r for r in res if r[3]==status]
    if rows:
        print(f"\n--- {status} ({len(rows)})")
        for r in rows: print(f"  {r[0]:>3} {r[1]:<6} {r[2]}")
json.dump([{'n':r[0],'side':r[1],'place':r[2],'status':r[3],'ctx':r[4][:200]} for r in res],
          open('verify2.json','w'), indent=1)
