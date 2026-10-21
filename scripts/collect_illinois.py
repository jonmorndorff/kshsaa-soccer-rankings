"""Collect current Illinois boys soccer records for Kansas KSPI (IHSA-hosted MaxPreps feeds).

Run after the Kansas collector. Never overwrite existing valid Illinois records with
an empty or partial scrape. IHSA notes regular-season stats are supplied by MaxPreps.
"""
import argparse, json, re, time
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
BASE="https://www.ihsa.org"
INDEX=BASE+"/sports/boys-soccer"
PROFILE=re.compile(r"/sports/boys-soccer/maxpreps-schools/SOB/\d+/20\d\d-\d\d",re.I)
RECORD=re.compile(r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?\b")
ALIASES={
 "normalcommunitywest":"normalwest",
 "normalwest":"normalwest",
 "normalcommunitywesths":"normalwest",
}
def norm(s):
 s=re.sub(r"\b(high school|hs|school)\b","",str(s).lower())
 return re.sub(r"[^a-z0-9]","",s)
def canonical(s):
 key=norm(s)
 return ALIASES.get(key,key)
def fetch(session,url):
 r=session.get(url,timeout=35);r.raise_for_status()
 if "text/html" not in r.headers.get("content-type","text/html"):raise ValueError("Not HTML")
 time.sleep(.35)
 return BeautifulSoup(r.text,"html.parser")
def discover(session,year):
 """Discover profile links from IHSA boys-soccer pages, not guessed school IDs."""
 season=f"{year}-{str(year+1)[-2:]}"
 seeds=[INDEX,INDEX+"/regular-season",INDEX+"/maxpreps-schools",BASE+"/sports/boys-soccer/maxpreps-schools/SOB"]
 found=set()
 for url in seeds:
  try:soup=fetch(session,url)
  except requests.RequestException as exc:
   print(f"Directory unavailable: {url}: {exc}");continue
  for a in soup.find_all("a",href=True):
   u=urljoin(url,a["href"]).split("?")[0]
   if PROFILE.search(u) and u.endswith("/"+season):found.add(u)
 return sorted(found)
def parse(soup,url,year):
 """Read the actual IHSA team header and the Overall record.

 IHSA page headings are 'Dunlap', 'Belleville East', etc. The season appears
 as 2026-27, and the record appears on the following line as 14-4-1.
 """
 text=soup.get_text(" ",strip=True)
 if f"{year}-{str(year+1)[-2:]}" not in text:return None
 h=soup.find("h1")
 if not h:return None
 name=h.get_text(" ",strip=True)
 if not name or len(name)>110:return None
 m=re.search(r"\\bOverall\\s+(\\d{1,2})\\s*[-–]\\s*(\\d{1,2})(?:\\s*[-–]\\s*(\\d{1,2}))?\\b",text,re.I)
 if not m:return None
 w,l,t=int(m.group(1)),int(m.group(2)),int(m.group(3) or 0)
 if not 1<=w+l+t<=35:return None
 return dict(name=name,wins=w,losses=l,ties=t,source=url,provider="IHSA / MaxPreps")
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--year",type=int,default=2026)
 p.add_argument("--min-records",type=int,default=1)
 args=p.parse_args()
 path=ROOT/"data"/f"boys-{args.year}.json"
 data=json.loads(path.read_text(encoding="utf-8"))
 if data.get("gender")!="boys" or data.get("year")!=args.year:raise SystemExit("Wrong Kansas season")
 session=requests.Session()
 session.headers.update({"User-Agent":"KansasSoccerPowerIndex/1.0 (educational research; low-rate requests)"})
 urls=discover(session,args.year)
 # No fabricated profile identifiers. A stable seed can be extended with verified IHSA links.
 urls=sorted(set(urls+[
  f"{BASE}/sports/boys-soccer/maxpreps-schools/SOB/0425/{args.year}-{str(args.year+1)[-2:]}",
  f"{BASE}/sports/boys-soccer/maxpreps-schools/SOB/0209/{args.year}-{str(args.year+1)[-2:]}",
  f"{BASE}/sports/boys-soccer/maxpreps-schools/SOB/2328/{args.year}-{str(args.year+1)[-2:]}"
 ]))
 records={}
 for url in urls:
  try:r=parse(fetch(session,url),url,args.year)
  except (requests.RequestException,ValueError) as exc:
   print(f"Skipping {url}: {exc}");continue
  if r:records[canonical(r["name"])]=r
 # Keep previous records if discovery is incomplete.
 old={canonical(r["name"]):r for r in data.get("illinoisRecords",[]) if r.get("name")}
 old.update(records)
 if len(old)<args.min_records:raise SystemExit(f"Only {len(old)} Illinois records found; preserving existing data")
 data["illinoisRecords"]=sorted(old.values(),key=lambda r:r["name"])
 path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 review={"fetchedProfiles":len(urls),"freshRecords":len(records),"totalRecords":len(old),
         "externalOpponentNames":[g.get("opponent") for g in data.get("externalGames",[]) if "normal community west" in g.get("opponent","").lower()]}
 (ROOT/"data"/f"boys-{args.year}-illinois-review.json").write_text(json.dumps(review,indent=2)+"\n",encoding="utf-8")
 print(f"Illinois: {len(records)} current records fetched, {len(old)} retained total")
if __name__=="__main__":main()
