"""Collect current KSHSAA team schedules; retain prior verified results.
Run: pip install requests beautifulsoup4 && python scripts/collect.py --gender boys --year 2026
Site layout may change; inspect output and review conflicts before publication.
"""
import argparse, datetime as dt, json, re, time
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
BASE='https://www.kshsaa.org/Public/Soccer/'
CLASSES=('6A','5A','4-1A')
MONTHS={m:i for i,m in enumerate(('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'),1)}
HEADERS={'User-Agent':'KansasSoccerIndependentRankings/0.1 (educational rankings; low-rate requests)'}

def get(session,url):
    r=session.get(url,timeout=25);r.raise_for_status();time.sleep(1.5);return BeautifulSoup(r.text,'html.parser')

def discover(session,gender):
    endpoint=f'{gender.title()}SchedulesByTeam.cfm'
    found={}
    for cls in CLASSES:
        url=BASE+endpoint+'?Class='+cls
        soup=get(session,url)
        for option in soup.select('option'):
            value=option.get('value','').strip();name=option.get_text(' ',strip=True)
            if value.isdigit() and len(name)>3 and not name.lower().startswith(('select','choose')):
                found[value]={'id':value,'name':name,'classification':cls}
        for a in soup.select('a[href]'):
            href=urljoin(url,a['href']);p=urlparse(href)
            if p.path.lower().endswith(endpoint.lower()):
                q=parse_qs(p.query);sid=q.get('SchoolSelect',[''])[0]
                if sid.isdigit():found.setdefault(sid,{'id':sid,'name':a.get_text(' ',strip=True),'classification':cls})
    return {k:v for k,v in found.items() if v['name'] and len(v['name'])>3}

def parse_page(soup,team,year,url):
    text=soup.get_text(' ',strip=True)
    m=re.search(r'([\w .,&\'\-]+?)\s+BOYS SOCCER SEASON SCHEDULE|([\w .,&\'\-]+?)\s+GIRLS SOCCER SEASON SCHEDULE',text,re.I)
    if m:
        label=(m.group(1) or m.group(2)).strip()
        if len(label)<100:team['name']=label
    games=[]
    for tr in soup.select('tr'):
        cells=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'],recursive=False)]
        if len(cells)<4:continue
        date_match=re.search(r'\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+([A-Za-z]{3})\s+(\d{1,2})',cells[0])
        if not date_match:continue
        month=MONTHS.get(date_match.group(1).title())
        if not month:continue
        day=int(date_match.group(2));match_year=year if month>=7 else year+1 if month<=2 else year
        if match_year!=year:continue
        date=f'{year}-{month:02}-{day:02}'
        opponent=cells[1].strip()
        if not opponent:continue
        joined=' '.join(cells[2:]);score=re.search(r'\b(\d{1,2})\s*[-–]\s*(\d{1,2})\b',joined)
        if not score:continue
        location=next((x.strip().upper() for x in cells[2:] if x.strip().upper() in ('H','V','N')),None)
        games.append({'date':date,'opponent':opponent,'gf':int(score.group(1)),'ga':int(score.group(2)),'location':location,'source':url})
    return games

def main():
    p=argparse.ArgumentParser();p.add_argument('--gender',choices=['boys','girls'],required=True);p.add_argument('--year',type=int,required=True);p.add_argument('--max-teams',type=int,default=0);args=p.parse_args()
    path=ROOT/'data'/f'{args.gender}-{args.year}.json';path.parent.mkdir(exist_ok=True)
    old=json.loads(path.read_text()) if path.exists() else {'gender':args.gender,'year':args.year,'teams':[],'games':[]}
    teams={t['id']:t for t in old['teams']};games={ (g['date'],*sorted([g['home'],g['away']])):g for g in old['games']}
    session=requests.Session();session.headers.update(HEADERS)
    discovered=discover(session,args.gender)
    if not discovered:raise RuntimeError('No team selectors discovered; site markup requires review. Archive unchanged.')
    teams.update(discovered)
    name_to_id={re.sub(r'[^a-z0-9]','',t['name'].lower().replace(' hs','')):sid for sid,t in teams.items()}
    conflicts=[];unmatched=[];seen=0
    for sid,team in discovered.items():
        if args.max_teams and seen>=args.max_teams:break
        url=BASE+f'{args.gender.title()}SchedulesByTeam.cfm?Class={team["classification"]}&SchoolSelect={sid}'
        try:rows=parse_page(get(session,url),team,args.year,url)
        except Exception as e:conflicts.append({'url':url,'error':str(e)});continue
        seen+=1
        for r in rows:
            opponent=re.sub(r'[^a-z0-9]','',r['opponent'].lower().replace(' hs',''))
            oid=name_to_id.get(opponent)
            if not oid or oid==sid:
                unmatched.append({'team':team['name'],'opponent':r['opponent'],'date':r['date']});continue
            if r['location']=='V':home,away=oid,sid;hg,ag=r['ga'],r['gf']
            else:home,away=sid,oid;hg,ag=r['gf'],r['ga']
            key=(r['date'],*sorted([home,away]))
            new={'date':r['date'],'home':home,'away':away,'homeGoals':hg,'awayGoals':ag,'source':r['source']}
            if key in games and (games[key]['homeGoals'],games[key]['awayGoals']) != (hg,ag) and (games[key]['home'],games[key]['away'])==(home,away):
                conflicts.append({'existing':games[key],'reported':new});continue
            games.setdefault(key,new) # Never overwrite archived results automatically
    out={'gender':args.gender,'year':args.year,'teams':sorted(teams.values(),key=lambda x:x['name']),'games':sorted(games.values(),key=lambda x:x['date'])}
    # Avoid publishing partial or unreviewed initial datasets automatically.
    if not out['games']:raise RuntimeError('No verified parsable games; archive unchanged.')
    path.write_text(json.dumps(out,indent=2)+'\n')
    report=ROOT/'data'/f'{args.gender}-{args.year}-review.json'
    report.write_text(json.dumps({'fetchedTeams':seen,'games':len(out['games']),'unmatched':unmatched,'conflicts':conflicts},indent=2)+'\n')
    print(f'Wrote {path}: {len(out["games"])} games; {len(unmatched)} unmatched; {len(conflicts)} conflicts. Review {report}.')
if __name__=='__main__':main()
