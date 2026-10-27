import re,sys,urllib.request,urllib.parse,html,http.cookiejar
U='https://www.nycenet.edu/offices/d_chanc_oper/budget/dbor/galaxy/galaxybudgetsummaryto/default.aspx'
out=sys.argv[1]; fy=sys.argv[2]
cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)); op.addheaders=[('User-Agent','Mozilla/5.0')]
def hidden(s): return dict(re.findall(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"',s))
for code in sys.argv[3:]:
    s=op.open(U).read().decode('utf-8','ignore')
    f=hidden(s); f.update({'School_Code':code,'Fiscal_Year':fy,'Enter':'Enter'})
    r=op.open(U,urllib.parse.urlencode(f).encode()).read().decode('utf-8','ignore')
    r=re.sub(r'<(script|style).*?</\1>','',r,flags=re.S)
    r=re.sub(r'</t[dh]>','\t',r); r=re.sub(r'</tr>|<br\s*/?>|</div>|</p>|</h\d>','\n',r)
    t=html.unescape(re.sub(r'<[^>]+>','',r)); t=re.sub(r'[ \t]*\n\s*','\n',t)
    open(f'{out}/{code}_FY{fy}.txt','w').write(t)
    i=t.find('School Site'); print(code, 'len',len(t), t[i:i+300].replace('\n',' | ') if i>0 else 'NO SITE TOTAL')
