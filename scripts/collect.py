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
CLASSES=('6A','5A','4-3-2-1A')
MONTHS={m:i for i,m in enumerate(('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'),1)}
HEADERS={'User-Agent':'KansasSoccerIndependentRankings/0.1 (educational rankings; low-rate requests)'}

def get(session,url):
    r=session.get(url,timeout=25);r.raise_for_status();time.sleep(1.5);return BeautifulSoup(r.text,'html.parser')

API_BASE='https://kshsaa-api.kshsaa.org/standings/Soccer/ByClassAndGender/'

def discover(session,gender,year):
    """Use the official standings API for school IDs and classifications.

    Fail closed if any class is missing, malformed, or belongs to another season.
    """
    gender_id=1 if gender=='boys' else 2  # Confirm girls ID before enabling spring collection.
    if gender=='girls':
        raise RuntimeError('Girls API gender identifier has not been verified yet; archive unchanged.')
    expected_season=f'{year}-{year+1}' if gender=='boys' else f'{year-1}-{year}'
    found={}
    for cls in CLASSES:
        url=f'{API_BASE}{cls}/{gender_id}'
        response=session.get(url,timeout=30)
        response.raise_for_status()
        payload=response.json()
        if not isinstance(payload,dict) or not isinstance(payload.get('standingsData'),list):
            raise RuntimeError(f'Invalid standings API response for {cls}: {url}')
        season=payload.get('yearData',{}).get('Description')
        if season != expected_season:
            raise RuntimeError(f'Unexpected season for {cls}: {season!r} (expected {expected_season!r}); archive unchanged.')
        rows=payload['standingsData']
        if not rows:
            raise RuntimeError(f'Empty standings for {cls}; archive unchanged.')
        for item in rows:
            sid=str(item.get('SchoolID','')).strip()
            name=str(item.get('SchoolName','')).strip()
            actual=item.get('SchoolClass')
            # KSHSAA's combined 4-3-2-1A endpoint may label individual
            # schools 4-1A or 3-2-1A; retain the shared ranking class.
            accepted = {'4-3-2-1A', '4-1A', '3-2-1A'} if cls == '4-3-2-1A' else {cls}
            if not sid.isdigit() or not name or actual not in accepted:
                raise RuntimeError(f'Invalid school entry in {cls} standings: {item!r}')
            if sid in found:
                raise RuntimeError(f'School {sid} occurs in multiple classifications; archive unchanged.')
            found[sid]={'id':sid,'name':name,'classification':cls,
                        'wins':item.get('TtlWins'), 'losses':item.get('TtlLosses'),
                        'ties':item.get('TtlTies'), 'goalsFor':item.get('TtlGoals'),
                        'goalsAgainst':item.get('OppTtlGoals')}
        time.sleep(1.5)
    return found

# Official 2026 KSHSAA East Regional lists, transcribed from the six
# regional standings tables supplied by the coach on October 20, 2026.
# All other schools in each classification are West.
OFFICIAL_EAST_2026 = {
    "6A": [
        "Blue Valley West HS",
        "Shawnee Mission West HS",
        "JC Harmon HS",
        "Olathe Northwest HS",
        "Shawnee Mission South HS",
        "Olathe West HS",
        "Gardner Edgerton HS",
        "Blue Valley North HS",
        "Olathe East HS",
        "Overland Park-Blue Valley HS",
        "Olathe South HS",
        "Blue Valley Northwest HS",
        "Mill Valley HS",
        "Shawnee Mission East HS",
        "Wyandotte HS",
        "Shawnee Mission Northwest HS",
        "Olathe North HS",
        "Shawnee Mission North HS"
    ],
    "5A": [
        "Blue Valley Southwest HS",
        "Turner HS",
        "Pittsburg HS",
        "De Soto HS",
        "Piper HS",
        "Sumner Academy",
        "Bonner Springs HS",
        "St. James Academy",
        "Shawnee Heights HS",
        "Kansas City-Washington HS",
        "St. Thomas Aquinas HS",
        "Seaman HS",
        "Spring Hill HS",
        "Highland Park HS",
        "FL Schlagle HS",
        "Basehor-Linwood HS",
        "Lansing HS",
        "Leavenworth HS"
    ],
    "4-3-2-1A": [
        "Maranatha Christian Academy",
        "Bishop Miege HS",
        "Heritage Christian Academy",
        "Louisburg HS",
        "Ottawa HS",
        "Eudora HS",
        "Bishop Ward HS",
        "Field Kindley HS",
        "Maur Hill-Mount Academy",
        "Tonganoxie HS",
        "Paola HS",
        "Baldwin HS",
        "Parsons HS",
        "Kansas City Christian HS",
        "Bishop Seabury Academy",
        "Atchison HS",
        "Fort Scott HS"
    ]
}

def assign_regions(session, teams, year):
    """Assign official regional groups without geographical guesswork."""
    if year != 2026:
        print('No verified regional assignment list for this year; leaving unassigned.')
        return
    def norm(s):
        return re.sub(r'[^a-z0-9]', '', s.lower())
    for cls, names in OFFICIAL_EAST_2026.items():
        actual={norm(t['name']):t for t in teams.values() if t['classification']==cls}
        missing=[name for name in names if norm(name) not in actual]
        if missing:
            raise RuntimeError(f'Cannot match official East regional schools in {cls}: {missing}')
        for t in teams.values():
            if t['classification']==cls:
                t['region']='East' if norm(t['name']) in {norm(n) for n in names} else 'West'
        print(f'Official {cls} regions: {len(names)} East, {sum(t["classification"]==cls for t in teams.values())-len(names)} West')

def parse_page(soup, team, year, url):
    """Parse the six DIV columns in KSHSAA's regular-season schedule."""
    heading=soup.find(string=re.compile(r'(BOYS|GIRLS) SOCCER SEASON SCHEDULE', re.I))
    if heading:
        name_tag=heading.find_previous('div')
        if name_tag:
            label=name_tag.get_text(' ',strip=True)
            if label and len(label)<100 and 'SOCCER' not in label.upper():
                team['name']=label
    games=[]
    schedule=[]
    full_schedule=[]
    for container in soup.find_all('div'):
        cols=container.find_all('div',recursive=False)
        if len(cols) not in (5,6):continue
        date_text=cols[0].get_text(' ',strip=True)
        dm=re.fullmatch(r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+([A-Za-z]{3})\s+(\d{1,2})',date_text)
        if not dm:continue
        month=MONTHS.get(dm.group(1).title())
        if not month:continue
        # Boys play in fall; girls play in spring. The supplied year is
        # the fall year for boys and spring year for girls.
        match_year=year if (month>=7 or args_gender_is_girls(url)) else year+1
        if match_year!=year:continue
        day=int(dm.group(2))
        try:date=dt.date(match_year,month,day).isoformat()
        except ValueError:continue
        opponent=cols[2].get_text(' ',strip=True)
        opponent_link=cols[2].find('a',href=True)
        opponent_id=parse_qs(urlparse(opponent_link['href']).query).get('SchoolSelect',[''])[0] if opponent_link else ''
        location=cols[3].get_text(' ',strip=True).upper()
        outcome=cols[4].get_text(' ',strip=True).upper() if len(cols)==6 else ''
        score_text=cols[5].get_text(' ',strip=True) if len(cols)==6 else cols[4].get_text(' ',strip=True)
        score=re.match(r'^(\d{1,2})\s*[-–]\s*(\d{1,2})(?:\s*\(.*\))?$',score_text)
        if opponent and location in ('H','V','N'):
            full_schedule.append({'date':date,'opponent':opponent,'location':location,'result':outcome if outcome in ('W','L','T') else '', 'score':score_text if outcome in ('W','L','T') else '', 'source':url})
        # KSHSAA displays unplayed fixtures as a blank W/L/T with 0-0 score.
        # The placeholder 0-0 is NOT a completed draw.
        if opponent and outcome not in ('W','L','T') and location in ('H','V','N') and (not score or (score.group(1)=='0' and score.group(2)=='0')):
            schedule.append({'date':date,'opponent':opponent,'location':location if location in ('H','V','N') else '', 'source':url})
        if not opponent or not score or outcome not in ('W','L','T') or location not in ('H','V','N'):
            continue
        gf,ga=map(int,score.groups())
        if (outcome=='W' and gf<=ga) or (outcome=='L' and gf>=ga) or (outcome=='T' and gf!=ga):
            continue
        games.append({'date':date,'opponent':opponent,'gf':gf,'ga':ga,
                      'location':location,'opponent_id':opponent_id,'result':outcome,'overtime':'(OT)' in score_text.upper(),
                      'source':url})
    return games,schedule,full_schedule

def args_gender_is_girls(url):
    return 'GirlsSchedulesByTeam' in url

def main():
    p=argparse.ArgumentParser();p.add_argument('--gender',choices=['boys','girls'],required=True);p.add_argument('--year',type=int,required=True);p.add_argument('--max-teams',type=int,default=0);args=p.parse_args()
    path=ROOT/'data'/f'{args.gender}-{args.year}.json';path.parent.mkdir(exist_ok=True)
    old=json.loads(path.read_text()) if path.exists() else {'gender':args.gender,'year':args.year,'teams':[],'games':[]}
    teams={t['id']:t for t in old['teams']};games={ (g['date'],*sorted([g['home'],g['away']])):g for g in old['games']}
    session=requests.Session();session.headers.update(HEADERS)
    discovered=discover(session,args.gender,args.year)
    if not discovered:raise RuntimeError('No team selectors discovered; site markup requires review. Archive unchanged.')
    # Retain archived game records, but do not keep stale or misclassified
    # team entries from earlier failed collection attempts.
    teams=discovered.copy()
    assign_regions(session,teams,args.year)
    name_to_id={}
    for sid,t in teams.items():
        key=re.sub(r'[^a-z0-9]','',t['name'].lower().replace(' hs',''))
        name_to_id[key]=sid
    conflicts=[];unmatched=[];seen=0; disputed_keys=set();upcoming={};full_schedules={};external_games={}
    for sid,team in discovered.items():
        if args.max_teams and seen>=args.max_teams:break
        url=BASE+f'{args.gender.title()}SchedulesByTeam.cfm?Class={team["classification"]}&SchoolSelect={sid}'
        try:rows,fixtures,full=parse_page(get(session,url),team,args.year,url)
        except Exception as e:conflicts.append({'url':url,'error':str(e)});continue
        seen+=1
        upcoming[sid]=fixtures
        full_schedules[sid]=full
        for r in rows:
            opponent=re.sub(r'[^a-z0-9]','',r['opponent'].lower().replace(' hs',''))
            oid=r.get('opponent_id') if r.get('opponent_id') in teams else name_to_id.get(opponent)
            if not oid or oid==sid:
                # Preserve verified final results against opponents outside our
                # KSHSAA standings universe. Never invent opponent classifications.
                if not oid:
                    external_key=re.sub(r'[^a-z0-9]','',r['opponent'].lower())
                    external_games[(sid,r['date'],external_key)]={
                        'team':sid,'date':r['date'],'opponent':r['opponent'],
                        'opponentKey':external_key,'gf':r['gf'],'ga':r['ga'],
                        'source':r['source']}
                unmatched.append({'team':team['name'],'opponent':r['opponent'],'date':r['date']});continue
            if r['location']=='V':home,away=oid,sid;hg,ag=r['ga'],r['gf']
            elif r['location']=='H':home,away=sid,oid;hg,ag=r['gf'],r['ga']
            else:
                # Neutral sites do not identify a home team; use stable ID ordering.
                home,away=sorted((sid,oid));hg,ag=(r['gf'],r['ga']) if home==sid else (r['ga'],r['gf'])
            key=(r['date'],*sorted([home,away]))
            new={'date':r['date'],'home':home,'away':away,'homeGoals':hg,'awayGoals':ag,'source':r['source']}
            if key in games and (games[key]['home'],games[key]['away'],games[key]['homeGoals'],games[key]['awayGoals']) != (home,away,hg,ag):
                conflicts.append({'existing':games[key],'reported':new});disputed_keys.add(key);continue
            games.setdefault(key,new) # Never overwrite archived results automatically
    # Exclude disputed fixtures entirely rather than trusting either inconsistent report.
    for key in disputed_keys:
        games.pop(key,None)
    out={'gender':args.gender,'year':args.year,'teams':sorted(teams.values(),key=lambda x:x['name']),'games':sorted(games.values(),key=lambda x:x['date']),'upcoming':upcoming,'schedules':full_schedules,'externalGames':sorted(external_games.values(),key=lambda x:(x['date'],x['team']))}
    # Avoid publishing partial or unreviewed initial datasets automatically.
    if not out['games']:raise RuntimeError('No verified parsable games; archive unchanged.')
    score_conflicts=[x for x in conflicts if 'reported' in x]
    fetch_errors=[x for x in conflicts if 'error' in x]
    if (not args.max_teams and seen < max(100, int(len(discovered)*0.95))):
        report=ROOT/'data'/f'{args.gender}-{args.year}-review.json'
        report.write_text(json.dumps({'fetchedTeams':seen,'games':len(out['games']),'unmatched':unmatched,'conflicts':conflicts},indent=2)+'\n')
        raise RuntimeError(f'{len(score_conflicts)} score conflicts, {len(fetch_errors)} fetch errors, {seen}/{len(discovered)} schedules collected. Archive unchanged.')
    path.write_text(json.dumps(out,indent=2)+'\n')
    report=ROOT/'data'/f'{args.gender}-{args.year}-review.json'
    report.write_text(json.dumps({'fetchedTeams':seen,'games':len(out['games']),'unmatched':unmatched,'conflicts':conflicts},indent=2)+'\n')
    print(f'Wrote {path}: {len(out["games"])} games; {len(unmatched)} unmatched; {len(disputed_keys)} disputed fixtures excluded; {len(fetch_errors)} fetch warnings. Review {report}.')
if __name__=='__main__':main()
