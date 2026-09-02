"""Fetch every raw source for the neglected-lots map into build/raw/.
Keyless Socrata; retries 403/429/5xx/timeouts (403 = per-IP throttling, not policy).
Fails loudly if any source comes back empty."""
import json, sys, time, os, urllib.request, urllib.parse
HERE=os.path.dirname(os.path.abspath(__file__)); RAW=os.path.join(HERE,"..","build","raw")
os.makedirs(RAW,exist_ok=True)
SOC="https://data.cityofnewyork.us/resource/"
ARC="https://services5.arcgis.com/GfwWNkhOj9bNBqoJ/arcgis/rest/services/MAPPLUTO/FeatureServer/0/query"
UA={"User-Agent":"nyc-neglected-lots build (josh.greenman@gmail.com)"}
WINDOW_START="2024-09-01"   # 24 months back from the 311 max (2026-08-31); see methodology

def get(url, data=None, tries=8, timeout=300):
    for i in range(tries):
        try:
            req=urllib.request.Request(url,data=data,headers=UA)
            with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)
        except Exception as e:
            wait=min(120, 5*(2**i)); print(f"   retry {i+1} after {type(e).__name__}: {str(e)[:120]} (sleep {wait}s)",flush=True); time.sleep(wait)
    raise SystemExit(f"FATAL: gave up on {url[:140]}")

def socrata(ds, params, page=50000, order=":id"):
    rows=[]; off=0
    while True:
        p=dict(params); p.update({"$limit":page,"$offset":off,"$order":order})
        chunk=get(SOC+ds+".json?"+urllib.parse.urlencode(p))
        rows+=chunk; print(f"   {ds}: {len(rows)} rows",flush=True)
        if len(chunk)<page: break
        off+=page
    if not rows: raise SystemExit(f"FATAL: {ds} returned 0 rows for {params}")
    return rows

def save(name, obj):
    with open(os.path.join(RAW,name),"w") as f: json.dump(obj,f)
    print(f"== saved {name}",flush=True)

def done(name): return os.path.exists(os.path.join(RAW,name))

NEGLECT=("Dirty Condition","Illegal Dumping","Lot Condition","Graffiti","Derelict Vehicles","Rodent")
DSNY_CHARGES=("DIRTY SIDEWALK","DIRTY AREA","LOOSE RUBBISH 1ST OCCURRENCE","LOOSE RUBBISH 2ND OCCURRENCE",
 "FAILURE TO CLEAN 18 INCHES INTO STREET","DIRTY SIDEWALK COMM MAN INDUSTRIAL MIXED USE 1ST","DIRTY AREA COMM MAN INDUSTRIAL MIXED USE 1ST",
 "FAIL TO CLEAN 18 INCH INTO STREET COMM MAN INDUSTRIAL MIXED USE 1ST","DIRTY SIDEWALK DIRTY AREA VACANT LOT","SIDEWALK OBSTRUCTION VACANT LOT",
 "FAILURE TO CLEAN 18 INCHES INTO STREET VACANT LOT","DIRTY SDWLK FAIL TO CLEAN 18 IN STRT SDWLK OBSTR VACANT LOT REPEAT",
 "ILLEGAL DUMPING OWNER OF VEHICLE 1ST OFFENSE","ILLEGAL DUMPING OPERATOR OF VEHICLE 1ST OFFENSE","ILLEGAL DUMPING CITIZEN COMPLAINANT - 1ST OFFENSE",
 "IMPROPER DISPOSAL - 1ST OFFENSE","IMPROPER DISPOSAL--BEDDING 1ST OCCURRENCE")
def inlist(vals): return "("+",".join("'"+v.replace("'","''")+"'" for v in vals)+")"

if not done("pluto_vacant.json"):
    print("PLUTO vacant land");
    save("pluto_vacant.json", socrata("64uk-42ks",{"$select":"bbl,borough,block,lot,address,ownername,ownertype,lotarea,zonedist1,cd,council,latitude,longitude,bldgclass,yearbuilt,numbldgs,assessland,assesstot,zipcode","$where":"landuse='11'"}))

if not done("c311.json"):
    print("311 neglect complaints, 24 months")
    save("c311.json", socrata("erm2-nwe9",{"$select":"unique_key,created_date,complaint_type,descriptor,bbl,incident_address,borough,latitude,longitude,status","$where":f"created_date>='{WINDOW_START}' AND complaint_type in {inlist(NEGLECT)}"}))
if not done("c311_lot_resolutions.json"):
    print("311 Lot Condition resolutions")
    save("c311_lot_resolutions.json", socrata("erm2-nwe9",{"$select":"unique_key,created_date,bbl,status,closed_date,resolution_description","$where":f"created_date>='{WINDOW_START}' AND complaint_type='Lot Condition'"}))

if not done("oath.json"):
    print("OATH sanitation summonses, 24 months")
    save("oath.json", socrata("jz4z-kudi",{"$select":"ticket_number,violation_date,issuing_agency,violation_location_borough,violation_location_block_no,violation_location_lot_no,violation_location_house,violation_location_street_name,charge_1_code_description,hearing_result,hearing_status","$where":f"violation_date>='{WINDOW_START}' AND issuing_agency in ('SANITATION OTHERS','DOS - ENFORCEMENT AGENTS','SANITATION POLICE') AND charge_1_code_description in {inlist(DSNY_CHARGES)}"}))

if not done("rodent.json"):
    print("Rodent inspections failed, 24 months")
    save("rodent.json", socrata("p937-wjvj",{"$select":"job_id,inspection_date,inspection_type,result,bbl,latitude,longitude,house_number,street_name,borough","$where":f"inspection_date>='{WINDOW_START}' AND result like 'Failed for Rat Activity%'"}))

if not done("aep.json"):
    save("aep.json", socrata("hcir-3275",{"$where":"current_status='AEP Active'"}))
if not done("ucp.json"):
    save("ucp.json", socrata("xpbf-ithr",{"$where":"current_status='Active'"}))
if not done("vacate.json"):
    save("vacate.json", socrata("tb8q-a3ar",{"$where":"actual_rescind_date is null AND vacate_type='Entire Building'"}))
if not done("stalled.json"):
    st=socrata("i296-73x5",{"$select":"dobrundate,borough_name,community_board,bin,house_number,street_name,complaint_number,date_complaint_received","$where":"dobrundate=(SELECT max(dobrundate))"} ) if False else None
    latest=get(SOC+"i296-73x5.json?"+urllib.parse.urlencode({"$select":"max(dobrundate) as mx"}))[0]["mx"]
    st=socrata("i296-73x5",{"$select":"dobrundate,borough_name,community_board,bin,house_number,street_name,complaint_number,date_complaint_received","$where":f"dobrundate='{latest}'"})
    bins=sorted({r["bin"] for r in st if r.get("bin")})
    fp=socrata("5zhs-2jue",{"$select":"bin,base_bbl","$where":"bin in "+inlist(bins)})
    save("stalled.json", {"run":latest,"sites":st,"footprints":fp})
if not done("facades.json"):
    save("facades.json", socrata("xubg-57si",{"$select":"tr6_no,bin,block,lot,borough,house_no,street_name,filing_status,current_status,filing_date,submitted_on,cycle","$where":"cycle='9'"}))
if not done("taxlien.json"):
    save("taxlien.json", socrata("9rz4-mjek",{"$where":"month='2025-06-01T00:00:00.000' AND cycle='Final Sale'"}))
if not done("lotsmart.json"):
    print("DSNY LotSmart history: every dated lot record (2010-2021)")
    save("lotsmart.json", socrata("r4c5-ndkx",{"$select":"lotid,inspectionrequestid,lotentrydate,inspectiondate,requestdate,privateind,inspectorfindings,coordinatex,coordinatey,boroid,block,house1,streetaddress,lotstatusreason","$where":"lotentrydate is not null"}))

if not done("pluto_polys.geojson"):
    print("MapPLUTO polygons for vacant land (ArcGIS)")
    feats=[]; off=0
    while True:
        p={"where":"LandUse='11'","outFields":"BBL,OwnerType,LotArea,Borough","f":"geojson","outSR":"4326","geometryPrecision":5,"resultOffset":off,"resultRecordCount":2000,"orderByFields":"OBJECTID"}
        g=get(ARC+"?"+urllib.parse.urlencode(p))
        feats+=g.get("features",[]); print(f"   polys {len(feats)}",flush=True)
        if len(g.get("features",[]))<2000: break
        off+=2000
    if not feats: raise SystemExit("FATAL: no polygons")
    save("pluto_polys.geojson", {"type":"FeatureCollection","features":feats})
print("ALL RAW DONE")
