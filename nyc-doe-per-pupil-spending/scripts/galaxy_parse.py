import re,sys,json
HDR=('Assignment\t','Title\t','Grade\t','Subject\t','Total\t','Organizational Category\t')
def money(l):
    m=re.search(r'\$\s*([\d,]+)',l); return int(m.group(1).replace(',','')) if m else None
def pos(l):
    p=l.split('\t'); 
    try: return float(p[-2]) if len(p)>=3 else 0.0
    except: return 0.0
def parse(path):
    L=open(path).read().split('\n')
    secs=[]; cur=None; mode='body'; site=None; sitetot={}; grand=None
    i=0
    while i<len(L):
        l=L[i].strip()
        if l=='School Site': mode='site'; i+=1; continue
        if l=='All Sites': mode='grand'; i+=1; continue
        if l.startswith('Fiscal Year 2026 Budget'): mode='hdr'; i+=1; continue
        if mode=='site':
            if '$' in l and not l.startswith('97K') and not l.startswith('13K') and not l.startswith('15K') or ('$' in l and '\t' in l and 'Positions' not in l and l.split('\t')[0] in (site,)): sitetot[l.split('\t')[0]]=money(l)
            i+=1; continue
        if mode=='grand':
            if '$' in l: grand=(pos(l),money(l))
            i+=1; continue
        if mode=='hdr':
            if l in ('Main School',) or re.match(r'^K\d{3} - K369',l): site=l; mode='body'
            i+=1; continue
        if mode=='body':
            nxt=L[i+1].strip() if i+1<len(L) else ''
            if '$' not in l and l and nxt.startswith(HDR):
                cur={'site':site,'sec':l,'lines':[],'total':None}; secs.append(cur); i+=2; continue
            if '$' not in l and l and '\t' not in l and cur is not None and nxt and '$' in nxt and not nxt.startswith(HDR):
                # header-less section (e.g. Sixth period coverage)
                pass
            if '$' in l and cur is not None:
                f=l.split('\t')[0]
                if re.search(r'Total$',f.strip()) or f.strip().endswith(' Total') or (len(l.split('\t'))>1 and l.split('\t')[1]=='Total'):
                    cur['total']=(pos(l),money(l))
                elif 'Sub-Total' not in l:
                    cur['lines'].append((pos(l),money(l),l))
        i+=1
    for s in secs:
        if s['total'] is None: s['total']=(sum(x[0] for x in s['lines']),sum(x[1] for x in s['lines']))
    return secs,sitetot,grand
if __name__=='__main__':
    for code in sys.argv[2:]:
        secs,st,g=parse(f'{sys.argv[1]}/{code}_FY2026.txt')
        tot=sum(s['total'][1] for s in secs)
        print('==',code,'sections sum',tot,'site totals',st,'grand',g)
        agg={}
        for s in secs: agg[s['sec']]=agg.get(s['sec'],[0,0]); agg[s['sec']][0]+=s['total'][0]; agg[s['sec']][1]+=s['total'][1]
        for k,v in agg.items(): print('   %-45s %6.1f %12s'%(k,v[0],f'{v[1]:,}'))
