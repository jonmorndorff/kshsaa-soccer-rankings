"""Collect official MSHSAA boys soccer records for KSPI."""
import argparse,json,re,time
from pathlib import Path
from urllib.parse import urljoin,urlparse,parse_qs
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
URL="https://www.mshsaa.org/Activities/SeasonRecords.aspx?alg=33"
def norm(name):
    name=re.sub(r"\b(high school|hs|school)\b","",str(name).lower())
    return re.sub(r"[^a-z0-9]","",name)
def collect(session):
    response=session.get(URL,timeout=35);response.raise_for_status()
    soup=BeautifulSoup(response.text,"html.parser")
    records=[];seen=set()
    for tr in soup.select("tr"):
        cells=tr.find_all("td",recursive=False)
        if len(cells)<5:continue
        a=cells[0].find("a",href=True)
        if not a:continue
        href=urljoin(URL,a["href"]);sid=parse_qs(urlparse(href).query).get("s",[""])[0]
        if not sid.isdigit() or sid in seen:continue
        values=[c.get_text(" ",strip=True) for c in cells]
        candidates=[]
        for j in range(1,len(values)-3):
            trio=values[j:j+3];pct=values[j+3].rstrip("%").strip()
            if not all(re.fullmatch(r"\d{1,3}",v) for v in trio):continue
            if not re.fullmatch(r"\d{1,3}(?:\.\d+)?",pct):continue
            w,l,t=map(int,trio);n=w+l+t
            if n<=40 and abs((100*(w+.5*t)/n if n else 0)-float(pct))<.16:candidates.append((w,l,t))
        if len(set(candidates))!=1:continue
        w,l,t=candidates[0];seen.add(sid)
        records.append(dict(id=sid,name=a.get_text(" ",strip=True),wins=w,losses=l,ties=t,source=href))
    return records
def main():
    p=argparse.ArgumentParser();p.add_argument("--year",type=int,default=2026);args=p.parse_args()
    path=ROOT/"data"/f"boys-{args.year}.json"
    data=json.loads(path.read_text(encoding="utf-8"))
    if data.get("gender")!="boys" or data.get("year")!=args.year:raise SystemExit("Wrong Kansas season")
    session=requests.Session();session.headers.update({"User-Agent":"KansasSoccerPowerIndex/1.0 (research)"})
    records=collect(session)
    if len(records)<150:raise SystemExit(f"Only {len(records)} MSHSAA records; preserving old data")
    by_name={}
    for r in records:by_name.setdefault(norm(r["name"]),[]).append(r)
    matched=[];unmatched=set()
    for g in data.get("externalGames",[]):
        name=g.get("opponent","")
        choices=by_name.get(norm(name),[])
        if len(choices)!=1:choices=by_name.get(norm(name.split(",")[0]),[])
        if len(choices)==1:matched.append(dict(team=g["team"],date=g["date"],opponent=name,missouriSchoolId=choices[0]["id"]))
        else:unmatched.add(name)
    data["missouriRecords"]=records
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    report=ROOT/"data"/f"boys-{args.year}-missouri-review.json"
    report.write_text(json.dumps(dict(records=len(records),matchedExternalGames=len(matched),matches=matched,unmatchedOpponentNames=sorted(unmatched)),indent=2)+"\n",encoding="utf-8")
    print(f"Collected {len(records)} Missouri records; matched {len(matched)} external Kansas games")
if __name__=="__main__":main()
