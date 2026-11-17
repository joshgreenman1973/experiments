import csv, gzip, glob, os, math, collections, json
from datetime import datetime
from zoneinfo import ZoneInfo
NY=ZoneInfo('America/New_York')
days={d['date']:d for d in json.load(open('days.json'))['days']}
CTRL=['B44','B44+','B46','B46+','B35','B6']
DUR=('2026-10-13','2026-11-06'); AFT=('2026-11-09','2026-11-16')
def hav(a,b,c,d):
    R=6371000; p1,p2=math.radians(a),math.radians(c); dp=p2-p1; dl=math.radians(d-b)
    return 2*R*math.asin(math.sqrt(math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2))
acc=collections.defaultdict(lambda:[0.0,0.0])
for f in sorted(glob.glob('extracts/*.csv.gz')):
    d=os.path.basename(f)[:10]
    if not (DUR[0]<=d<=AFT[1]) or days.get(d,{}).get('dayType')!='weekday': continue
    fx=collections.defaultdict(list)
    with gzip.open(f,'rt') as fh:
        for r in csv.DictReader(fh):
            if r['route'] in CTRL and 'LAYOVER' not in r['phase'].upper():
                fx[(r['vid'],r['route'])].append((int(r['t']),float(r['lat']),float(r['lon'])))
    for (v,rt),L in fx.items():
        L=sorted(set(L))
        for (t1,a,b),(t2,c,e) in zip(L,L[1:]):
            dt=t2-t1
            if dt<15 or dt>180: continue
            m=hav(a,b,c,e)
            if m/dt>22: continue
            hr=datetime.fromtimestamp(t1,NY).hour
            if 7<=hr<19:
                per='during' if d<=DUR[1] else 'after'
                acc[(rt.rstrip('+'),per,hr)][0]+=m; acc[(rt.rstrip('+'),per,hr)][1]+=dt
for rt in sorted({k[0] for k in acc}):
    out=[]
    for per in ('during','after'):
        sp=[acc[(rt,per,h)][0]/acc[(rt,per,h)][1]*2.23694 for h in range(7,19) if acc[(rt,per,h)][1]>0]
        out.append(len(sp)/sum(1/s for s in sp))
    print(rt, f"{out[0]:.2f} -> {out[1]:.2f}  {out[1]-out[0]:+.2f}")
