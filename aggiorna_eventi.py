#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHE SI FA CERIGNOLA - motore v3.
Tre chiamate Gemini territoriali per gli eventi; scraping JSON-LD senza Gemini;
luoghi/attività soltanto su richiesta; stop immediato su HTTP 429.
"""
import os, re, json, time, logging, tempfile
from datetime import datetime, timedelta
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
import requests
from bs4 import BeautifulSoup

BASE = os.path.dirname(os.path.abspath(__file__))
EVENTI = os.path.join(BASE, 'eventi.json')
LUOGHI = os.path.join(BASE, 'luoghi_da_verificare.json')
ATTIVITA = os.path.join(BASE, 'attivita_da_verificare.json')
REPORT = os.path.join(BASE, 'report_copertura.json')
API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.8-flash').strip()
MAX_DAYS = int(os.environ.get('MAX_FUTURE_DAYS', '120'))
SCRAPING = os.environ.get('ENABLE_SCRAPING', '1').lower() not in {'0','false','no'}
RUN_PERMANENTI = os.environ.get('RUN_PERMANENTI', '0').lower() in {'1','true','yes'}
MAX_ARTICLES = int(os.environ.get('MAX_ARTICLES_PER_SOURCE', '12'))
API_URL = 'https://generativelanguage.googleapis.com/v1beta/interactions'
API_REVISION = '2026-05-20'

logging.basicConfig(level=os.environ.get('LOG_LEVEL','INFO').upper(),
                    format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger('che-si-fa-v3')
S = requests.Session()
S.headers.update({'User-Agent':'Mozilla/5.0 (compatible; CheSiFaCerignolaBot/3.0; +https://francescocompierchio.github.io/che-si-fa-cerignola/)',
                  'Accept-Language':'it-IT,it;q=0.9,en;q=0.7'})

FONTI = [
 ('https://www.cerignolaviva.it/eventi/','Cerignola'),
 ('https://www.foggiatoday.it/eventi/','Foggia'),
 ('https://www.foggiatoday.it/eventi/weekend/','Foggia'),
 ('https://www.barlettaviva.it/eventi/','Barletta'),
 ('https://www.traniviva.it/eventi/','Trani'),
 ('https://www.bisceglieviva.it/eventi/','Bisceglie'),
 ('https://www.andriaviva.it/eventi/','Andria'),
 ('https://www.manfredonianews.it/category/eventi/','Manfredonia'),
]
COMUNI = [
 'Cerignola','Stornara','Stornarella','San Ferdinando di Puglia','Orta Nova','Trinitapoli',
 'Canosa di Puglia','Ordona','Carapelle','Margherita di Savoia','Lavello','Ascoli Satriano',
 'Zapponeta','Castelluccio dei Sauri','Barletta','Candela','Minervino Murge','Foggia','Melfi',
 'Venosa','Deliceto','Rapolla','Andria','Barile','Palazzo San Gervasio',"Rocchetta Sant'Antonio",
 "Sant'Agata di Puglia",'Manfredonia','Rionero in Vulture','Trani','Bovino','Lacedonia','Monticchio',
 'Spinazzola','Monteverde','Montemilone','Atella','Troia','Accadia','Aquilonia','Lucera','Bisceglie',
 'Molfetta','San Severo','Vieste','Mattinata','Monte Sant\'Angelo'
]
AREE_RICERCA = [
 ('Cerignola e prima cintura', ['Cerignola','Stornara','Stornarella','San Ferdinando di Puglia','Orta Nova','Trinitapoli','Canosa di Puglia','Ordona','Carapelle','Margherita di Savoia','Lavello','Ascoli Satriano','Zapponeta','Castelluccio dei Sauri','Candela','Minervino Murge']),
 ('Capitanata e area BAT', ['Barletta','Foggia','Andria','Trani','Bisceglie','Molfetta','San Severo','Manfredonia','Lucera','Troia','Bovino','Deliceto','Accadia',"Sant'Agata di Puglia","Rocchetta Sant'Antonio"]),
 ('Gargano e area Basilicata', ['Melfi','Venosa','Rapolla','Barile','Palazzo San Gervasio','Rionero in Vulture','Lacedonia','Monticchio','Spinazzola','Monteverde','Montemilone','Atella','Aquilonia','Vieste','Mattinata',"Monte Sant'Angelo"])
]

ALIASES = {
 'san ferdinando':'San Ferdinando di Puglia','san ferdinando di puglia':'San Ferdinando di Puglia',
 'canosa':'Canosa di Puglia','canosa di puglia':'Canosa di Puglia','minervino':'Minervino Murge',
 'minervino murge':'Minervino Murge','rionero':'Rionero in Vulture','rionero in vulture':'Rionero in Vulture',
 'laghi di monticchio':'Monticchio',"monte sant'angelo":"Monte Sant'Angelo",
 "sant'agata di puglia":"Sant'Agata di Puglia","rocchetta sant'antonio":"Rocchetta Sant'Antonio",
 'castelluccio dei sauri':'Castelluccio dei Sauri','margherita di savoia':'Margherita di Savoia',
 'palazzo san gervasio':'Palazzo San Gervasio'
}
CATEGORIE = ['Locali & Serate','Attività serali','Musica & Concerti','Sagre & Food',
             'Famiglie & Bambini','Natura & Escursioni','Attività diurne','Altro']
MAPPA_CAT = {
 'serate':'Locali & Serate','locali':'Locali & Serate','club':'Locali & Serate',
 'aperitivo':'Locali & Serate','dj set':'Locali & Serate','discoteca':'Locali & Serate',
 'attività serali':'Attività serali','attivita serali':'Attività serali','apericena':'Attività serali',
 'karaoke':'Attività serali','quiz night':'Attività serali','musica':'Musica & Concerti',
 'concerti':'Musica & Concerti','teatro':'Musica & Concerti','spettacolo':'Musica & Concerti',
 'cabaret':'Musica & Concerti','fiera':'Sagre & Food','sagra':'Sagre & Food','food':'Sagre & Food',
 'mercatino':'Sagre & Food','degustazione':'Sagre & Food','famiglie':'Famiglie & Bambini',
 'bambini':'Famiglie & Bambini','laboratorio bambini':'Famiglie & Bambini','natura':'Natura & Escursioni',
 'escursioni':'Natura & Escursioni','trekking':'Natura & Escursioni','passeggiata':'Natura & Escursioni',
 'attività diurne':'Attività diurne','attivita diurne':'Attività diurne','visita guidata':'Attività diurne'
}
ESCLUDI = ['incidente','omicidio','rapina','arresto','arresti','cronaca','morto','ferito','meteo',
 'allerta','elezioni','sciopero','consiglio comunale','indagine di mercato','presentazione del libro',
 'presentazione libro','convegno','seminario','tavola rotonda','messa','processione','funerale',
 'raccolta fondi','beneficenza']
STOP = set('il lo la i gli le un uno una di a da in con su per tra fra del dello della dei degli delle al allo alla ai agli alle dal dallo dalla nel nello nella sul sulla e ed o che si fa evento serata grande'.split())


def now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo('Europe/Rome')).replace(tzinfo=None)
    except Exception: return datetime.now()
def today(): return now().strftime('%Y-%m-%d')
def future(): return (now()+timedelta(days=MAX_DAYS)).strftime('%Y-%m-%d')
def norm(v): return re.sub(r'\s+',' ',str(v or '')).strip()
def urlnorm(u):
    u=norm(u)
    if not u.startswith(('http://','https://')): return ''
    try:
        p=urlparse(u)
        if not p.netloc: return ''
        q=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True)
           if not k.lower().startswith('utm_') and k.lower() not in {'fbclid','gclid'}]
        return urlunparse((p.scheme.lower(),p.netloc.lower(),p.path or '/',p.params,urlencode(q),''))
    except Exception: return ''
def same_domain(a,b):
    x=(urlparse(a).hostname or '').lower().removeprefix('www.')
    y=(urlparse(b).hostname or '').lower().removeprefix('www.')
    return bool(x and y and (x==y or x.endswith('.'+y) or y.endswith('.'+x)))
def parse_date(v):
    s=norm(v)[:10]
    try: return datetime.strptime(s,'%Y-%m-%d').date() if re.fullmatch(r'\d{4}-\d{2}-\d{2}',s) else None
    except ValueError: return None
def valid_time(v):
    s=norm(v)[:5]
    if not re.fullmatch(r'\d{2}:\d{2}',s): return ''
    h,m=map(int,s.split(':'))
    return s if 0<=h<=23 and 0<=m<=59 else ''
def extract_time(v):
    m=re.search(r'(?:ore\s*)?(\d{1,2})[:.](\d{2})',norm(v),re.I)
    if not m: return ''
    h,mi=map(int,m.groups())
    return f'{h:02d}:{mi:02d}' if 0<=h<=23 and 0<=mi<=59 else ''
def city(ev,default='Cerignola'):
    raw=norm(ev.get('citta'))
    if raw: return ALIASES.get(raw.lower(),raw.title())
    txt=' '.join(norm(ev.get(k)) for k in ('luogo','titolo','descrizione')).lower()
    for a in sorted(ALIASES,key=len,reverse=True):
        if re.search(rf'(?<!\w){re.escape(a)}(?!\w)',txt): return ALIASES[a]
    for c in sorted(COMUNI,key=len,reverse=True):
        if re.search(rf'(?<!\w){re.escape(c.lower())}(?!\w)',txt): return c
    return default
def category(v):
    s=norm(v).lower()
    if s in MAPPA_CAT: return MAPPA_CAT[s]
    return next((c for c in CATEGORIE if c.lower()==s),'Altro')
def priority(c):
    c=norm(c).lower()
    if c=='cerignola': return 0
    if c in {'stornara','stornarella','san ferdinando di puglia','orta nova','trinitapoli','canosa di puglia','ordona','carapelle','margherita di savoia','lavello','ascoli satriano'}: return 1
    if c in {'zapponeta','castelluccio dei sauri','barletta','candela','minervino murge','foggia','melfi','venosa','deliceto','rapolla','andria','barile','palazzo san gervasio',"rocchetta sant'antonio","sant'agata di puglia",'manfredonia','rionero in vulture','trani','bovino','lacedonia','monticchio','spinazzola','monteverde','montemilone','atella','troia','accadia','aquilonia','lucera','bisceglie'}: return 2
    return 3
def band(c): return ['Cerignola','Prima cintura (fascia orientativa)','Seconda cintura (fascia orientativa)','Altra area / distanza da verificare'][priority(c)]
def specific_url(u): return bool(u) and urlparse(u).path.rstrip('/').lower() not in ('','/eventi','/eventi/weekend','/category/eventi')
def load_json(path,default=None):
    try:
        with open(path,encoding='utf-8') as f: return json.load(f)
    except FileNotFoundError: return [] if default is None else default
    except Exception as e: log.warning('Lettura %s fallita: %s',path,e); return [] if default is None else default
def atomic_json(path,data):
    fd,tmp=tempfile.mkstemp(prefix='tmp_',suffix='.json',dir=BASE)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2); f.write('\n')
        os.replace(tmp,path)
    except Exception:
        try: os.remove(tmp)
        except OSError: pass
        raise
def clean_event(raw,default_city,allowed):
    e=dict(raw or {}); e['tipoContenuto']='evento'; e['citta']=city(e,default_city)
    e['categoria']=category(e.get('categoria')); e['titolo']=norm(e.get('titolo'))[:120]
    e['luogo']=norm(e.get('luogo'))[:180]; e['descrizione']=norm(e.get('descrizione'))[:500]
    e['dataInizio']=norm(e.get('dataInizio'))[:10]; e['dataFine']=norm(e.get('dataFine') or e.get('dataInizio'))[:10]
    e['dataTesto']=norm(e.get('dataTesto'))[:120]; e['oraInizio']=valid_time(e.get('oraInizio')) or extract_time(e.get('dataTesto'))
    e['oraFine']=valid_time(e.get('oraFine')); e['costo']=norm(e.get('costo')) or 'Da verificare'
    e['indirizzoMappa']=norm(e.get('indirizzoMappa')) or f"{e['luogo']}, {e['citta']}"
    u=urlnorm(e.get('fonteUrl')); allowed={urlnorm(x) for x in allowed if urlnorm(x)}
    e['fonteUrl']=u if u in allowed else ''; e['statoVerifica']='fonte_trovata' if e['fonteUrl'] else 'da_verificare'
    e['ultimaVerifica']=now().strftime('%Y-%m-%d %H:%M:%S'); e['fasciaTerritoriale']=band(e['citta'])
    return e
def valid_event(e):
    start=parse_date(e.get('dataInizio')); end=parse_date(e.get('dataFine') or e.get('dataInizio'))
    if len(norm(e.get('titolo')))<5 or not norm(e.get('luogo')) or not start or not end: return False
    if end<now().date() or start>(now()+timedelta(days=MAX_DAYS)).date() or end<start: return False
    return not any(x in norm(e.get('titolo')).lower() for x in ESCLUDI)
def tokens(s,c=''):
    s=re.sub(r'[^a-z0-9àèéìòù\s]',' ',(s or '').lower()); ct=set(re.sub(r'[^a-z0-9àèéìòù\s]',' ',(c or '').lower()).split())
    return {w for w in s.split() if len(w)>=3 and w not in STOP and w not in ct}
def duplicate(a,b):
    if norm(a.get('citta')).lower()!=norm(b.get('citta')).lower(): return False
    ai,af=parse_date(a.get('dataInizio')),parse_date(a.get('dataFine') or a.get('dataInizio'))
    bi,bf=parse_date(b.get('dataInizio')),parse_date(b.get('dataFine') or b.get('dataInizio'))
    if not all((ai,af,bi,bf)) or not ((abs((ai-bi).days)<=1 and abs((af-bf).days)<=1) or max(ai,bi)<=min(af,bf)): return False
    x=re.sub(r'[^a-z0-9\s]','',norm(a.get('titolo')).lower()).strip(); y=re.sub(r'[^a-z0-9\s]','',norm(b.get('titolo')).lower()).strip()
    if not x or not y: return False
    if min(len(x),len(y))>=10 and (x in y or y in x): return True
    if SequenceMatcher(None,x,y).ratio()>=.78: return True
    tx,ty=tokens(x,a.get('citta')),tokens(y,b.get('citta'))
    if tx and ty:
        inter=len(tx&ty); return inter/len(tx|ty)>=.58 or (inter>=2 and inter/min(len(tx),len(ty))>=.85)
    return False
def merge_event(old,new):
    out=dict(old)
    for k,limit in [('titolo',120),('descrizione',500),('luogo',180)]:
        if len(norm(new.get(k)))>len(norm(out.get(k))) and len(norm(new.get(k)))<=limit: out[k]=norm(new.get(k))
    if out.get('costo') in ('','Da verificare') and new.get('costo') not in ('','Da verificare'): out['costo']=new['costo']
    if not specific_url(out.get('fonteUrl')) and specific_url(new.get('fonteUrl')):
        out['fonteUrl']=new['fonteUrl']; out['statoVerifica']=new.get('statoVerifica','fonte_trovata')
    for k in ('oraInizio','oraFine','indirizzoMappa'):
        if not out.get(k) and new.get(k): out[k]=new[k]
    out['ultimaVerifica']=new.get('ultimaVerifica',out.get('ultimaVerifica',''))
    return out

# ---------------- Scraping strutturato, senza chiamate Gemini ----------------
def expand_jsonld(x):
    if isinstance(x,list): return sum((expand_jsonld(i) for i in x),[])
    if isinstance(x,dict): return sum((expand_jsonld(i) for i in x['@graph']),[]) if isinstance(x.get('@graph'),list) else [x]
    return []
def jsonld_events(soup,default_city,page_url):
    out=[]
    for tag in soup.find_all('script',type='application/ld+json'):
        try:
            raw=tag.string or tag.get_text(); data=json.loads(raw) if raw else None
            for o in expand_jsonld(data):
                typ=o.get('@type',[]); typ=typ if isinstance(typ,list) else [typ]
                if not any('event' in str(t).lower() for t in typ): continue
                loc=o.get('location') or {}; loc=loc[0] if isinstance(loc,list) and loc else loc
                venue=norm(loc.get('name')) if isinstance(loc,dict) else norm(loc)
                addr=loc.get('address') or {} if isinstance(loc,dict) else {}
                c=norm(addr.get('addressLocality')) if isinstance(addr,dict) else ''
                street=norm(addr.get('streetAddress')) if isinstance(addr,dict) else ''
                start=norm(o.get('startDate')); end=norm(o.get('endDate')) or start
                if not o.get('name') or not start or not venue: continue
                out.append({'tipoContenuto':'evento','citta':c or default_city,'categoria':category(o.get('description')),
                    'titolo':norm(o.get('name')),'dataTesto':f"Dal {start[:10]}",'dataInizio':start[:10],
                    'dataFine':end[:10],'oraInizio':extract_time(start),'oraFine':extract_time(end),
                    'luogo':venue,'indirizzoMappa':', '.join(x for x in (street,venue,c or default_city) if x),
                    'costo':'Da verificare','descrizione':norm(o.get('description'))[:450] or f'Evento in programma presso {venue}.',
                    'fonteUrl':urlnorm(o.get('url') or page_url)})
        except Exception as ex: log.debug('JSON-LD non leggibile: %s',ex)
    return out
def scrape_source(page,default_city):
    try:
        r=S.get(page,timeout=18); r.raise_for_status(); r.encoding=r.apparent_encoding or 'utf-8'
        soup=BeautifulSoup(r.text,'html.parser')
    except Exception as ex: log.warning('Scraping fallito %s: %s',page,ex); return [],{'jsonld':0,'url':0}
    found=jsonld_events(soup,default_city,page); links=[]
    for a in soup.find_all('a',href=True):
        u=urlnorm(urljoin(page,a.get('href',''))); title=norm(a.get_text(' ',strip=True))
        if not u or not same_domain(u,page) or u==urlnorm(page) or len(title)<12: continue
        path=urlparse(u).path.lower()
        if any(x in path for x in ('/tag/','/author/','/page/','privacy','cookie','login','contatti')): continue
        if any(k in (title+' '+path).lower() for k in ('event','serat','concert','sagra','mercatin','teatro','spettacol','bambin','famigl','escursion','festival','festa','weekend','natale')) and u not in links: links.append(u)
    for u in links[:MAX_ARTICLES]:
        try:
            r=S.get(u,timeout=12); r.raise_for_status(); r.encoding=r.apparent_encoding or 'utf-8'
            found.extend(jsonld_events(BeautifulSoup(r.text,'html.parser'),default_city,u))
        except Exception as ex: log.debug('Articolo non letto %s: %s',u,ex)
        time.sleep(.2)
    return found,{'jsonld':len(found),'url':1+min(len(links),MAX_ARTICLES)}

# ---------------- Gemini: una chiamata diretta con Google Search ----------------
def interaction_text_and_urls(data):
    texts=[]; urls=set()
    for step in data.get('steps',[]) if isinstance(data,dict) else []:
        if not isinstance(step,dict): continue
        for block in step.get('content',[]) if isinstance(step.get('content'),list) else []:
            if not isinstance(block,dict): continue
            if block.get('type')=='text' and block.get('text'): texts.append(block['text'])
            for ann in block.get('annotations',[]) or []:
                if isinstance(ann,dict):
                    candidates=[ann.get('url'),ann.get('uri')]
                    for key in ('url_citation','source'):
                        if isinstance(ann.get(key),dict): candidates.append(ann[key].get('url'))
                    urls.update(urlnorm(x) for x in candidates if urlnorm(x))
        if step.get('type')=='model_output' and isinstance(step.get('text'),str): texts.append(step['text'])
    if isinstance(data,dict) and data.get('output_text'): texts.append(str(data['output_text']))
    return '\n'.join(dict.fromkeys(texts)).strip(),urls
def call_gemini(prompt,label,search=True):
    if not API_KEY: return '',set(),False,'chiave_assente'
    payload={'model':MODEL,'input':prompt}
    if search: payload['tools']=[{'type':'google_search'}]
    headers={'Content-Type':'application/json','x-goog-api-key':API_KEY,'Api-Revision':API_REVISION}
    for attempt in range(2):
        try:
            r=S.post(API_URL,headers=headers,json=payload,timeout=150)
            if r.status_code==429:
                log.error('%s: HTTP 429, quota raggiunta. Stop senza fallback.',label)
                return '',set(),False,'limite_429'
            if r.status_code in (500,502,503,504) and attempt==0:
                time.sleep(8); continue
            if r.status_code!=200:
                log.error('%s: HTTP %s: %s',label,r.status_code,r.text[:600])
                return '',set(),False,f'http_{r.status_code}'
            text,urls=interaction_text_and_urls(r.json())
            if not text: return '',urls,False,'output_vuoto'
            log.info('%s: %s caratteri, %s URL citati',label,len(text),len(urls))
            return text,urls,True,'ok'
        except requests.RequestException as ex:
            if attempt==0: time.sleep(5); continue
            log.error('%s: errore rete: %s',label,ex); return '',set(),False,'errore_rete'
    return '',set(),False,'errore_server'
def parse_json_output(text):
    if not text: return None
    s=re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$','',text.strip(),flags=re.I)
    try: return json.loads(s)
    except json.JSONDecodeError: pass
    starts=[i for i in (s.find('['),s.find('{')) if i>=0]
    if not starts: return None
    start=min(starts); opening=s[start]; closing=']' if opening=='[' else '}'; depth=0; quoted=False; escaped=False
    for i in range(start,len(s)):
        ch=s[i]
        if quoted:
            if escaped: escaped=False
            elif ch=='\\': escaped=True
            elif ch=='"': quoted=False
        elif ch=='"': quoted=True
        elif ch==opening: depth+=1
        elif ch==closing:
            depth-=1
            if depth==0:
                try: return json.loads(s[start:i+1])
                except json.JSONDecodeError: return None
    return None
def event_prompt(area_name, towns):
    return f'''Sei il ricercatore web del portale locale Che Si Fa Cerignola. Oggi: {today()}. Cerca eventi tra oggi e {future()}.
AREA DI QUESTA RICERCA: {area_name}. Cerca singolarmente questi comuni: {", ".join(towns)}.
Categorie: locali/serate/DJ set/aperitivi; concerti/musica/teatro/spettacoli; sagre/mercatini/fiere/feste/food; famiglie e bambini; escursioni guidate non agonistiche; visite guidate/laboratori/esperienze diurne.
Usa Google Search, privilegiando fonti ufficiali di Comuni, Pro Loco, associazioni, organizzatori, locali e testate locali. Dai priorità a Cerignola e dintorni, non limitarti ai capoluoghi.
Inserisci solo appuntamenti pubblici con data certa, futura o in corso. Ogni evento deve avere la pagina specifica che conferma proprio quell'evento. Vietate pagine generiche di categoria. Non inventare date, luoghi, orari, prezzi o link. Escludi cronaca, politica, celebrazioni religiose, beneficenza, convegni professionali, presentazioni editoriali e sport agonistico. Non duplicare.
Restituisci ESCLUSIVAMENTE un array JSON valido, senza markdown. Se nessun risultato verificabile, [].
Ogni oggetto deve avere queste chiavi: tipoContenuto="evento", citta, categoria (una tra {', '.join(CATEGORIE)}), titolo, dataTesto, dataInizio (YYYY-MM-DD), dataFine (YYYY-MM-DD), oraInizio (HH:MM o vuoto), oraFine (HH:MM o vuoto), luogo, indirizzoMappa, costo ("Da verificare" se ignoto), descrizione, fonteUrl (URL esatto della pagina specifica citata da Search).'''
def find_events():
    all_events=[]; all_cited=set(); area_stats={}; failures=[]
    # Tre ricerche territoriali mirate: meno chiamate del vecchio sistema (22),
    # ma copertura più gestibile rispetto a un'unica richiesta su 47 comuni.
    for area_name,towns in AREE_RICERCA:
        text,cited,ok,status=call_gemini(event_prompt(area_name,towns),f'Ricerca eventi - {area_name}')
        all_cited.update(cited)
        if not ok:
            area_stats[area_name]={'stato':status,'candidatiValidi':0,'urlCitati':len(cited)}
            failures.append(area_name+': '+status)
            if status=='limite_429':
                # Non proseguire: il progetto ha raggiunto la quota del giorno.
                break
            continue
        data=parse_json_output(text)
        if not isinstance(data,list):
            area_stats[area_name]={'stato':'json_non_valido','candidatiValidi':0,'urlCitati':len(cited)}
            failures.append(area_name+': json_non_valido')
            continue
        valid_count=0
        for raw in data:
            if not isinstance(raw,dict): continue
            e=clean_event(raw,'Cerignola',cited)
            if valid_event(e) and e.get('fonteUrl') and specific_url(e['fonteUrl']):
                all_events.append(e); valid_count+=1
            else:
                log.info('Scartato candidato senza dati/fonte verificabili: %s',norm(raw.get('titolo'))[:80])
        area_stats[area_name]={'stato':'ok','candidatiValidi':valid_count,'urlCitati':len(cited)}
    status='ok' if not failures else ('limite_429' if any('limite_429' in x for x in failures) else 'parziale')
    return all_events,all_cited,status,area_stats

def find_permanents():
    prompt=f'''Cerca luoghi permanenti visitabili e attività/esperienze prenotabili o ricorrenti in questi comuni: {", ".join(COMUNI)}. Oggi {today()}.
Usa Google Search e fonti ufficiali/gestori. Non inventare aperture, disponibilità, prezzi, orari, telefoni o indirizzi. Distingui luoghi da attività.
Restituisci SOLO un oggetto JSON con due array "luoghi" e "attivita". Luoghi: oggetti con nome,citta,indirizzo,descrizione,categoria,urlUfficiale,fonteUrl. Attività: nome,citta,luogo,descrizione,categoria,disponibilita,prezzo,urlUfficiale,fonteUrl. URL specifici citati. Se vuoti, array vuoti.'''
    text,cited,ok,status=call_gemini(prompt,'Ricerca luoghi e attività')
    if not ok: return [],[],cited,status
    data=parse_json_output(text)
    if not isinstance(data,dict): return [],[],cited,'json_non_valido'
    def clean(items,kind):
        out=[]
        for raw in items if isinstance(items,list) else []:
            if not isinstance(raw,dict): continue
            x=dict(raw); x['tipoContenuto']=kind; x['nome']=norm(x.get('nome'))[:150]
            x['citta']=city({'citta':x.get('citta'),'luogo':x.get('luogo'),'titolo':x.get('nome'),'descrizione':x.get('descrizione')})
            x['descrizione']=norm(x.get('descrizione'))[:500]; x['categoria']=norm(x.get('categoria'))[:100]
            x['fonteUrl']=urlnorm(x.get('fonteUrl')) if urlnorm(x.get('fonteUrl')) in cited else ''
            x['urlUfficiale']=urlnorm(x.get('urlUfficiale')) if urlnorm(x.get('urlUfficiale')) in cited else ''
            x['statoVerifica']='da_verificare'; x['ultimaVerifica']=now().strftime('%Y-%m-%d %H:%M:%S'); x['fasciaTerritoriale']=band(x['citta'])
            if x['nome'] and x['fonteUrl']: out.append(x)
        return out
    return clean(data.get('luoghi'),'luogo'),clean(data.get('attivita'),'attivita'),cited,'ok'
def dedup_permanent(items):
    out=[]; seen=set()
    for x in items:
        k=(x.get('tipoContenuto'),norm(x.get('nome')).lower(),norm(x.get('citta')).lower())
        if k[1] and k not in seen: seen.add(k); out.append(x)
    return out

def main():
    log.info('Avvio motore v3 | data=%s | modello=%s',today(),MODEL)
    old=load_json(EVENTI,[])
    if not isinstance(old,list): log.error('eventi.json non è un array: stop.'); return
    consolidated=[]
    for raw in old:
        if not isinstance(raw,dict): continue
        e=clean_event(raw,raw.get('citta') or 'Cerignola',{raw.get('fonteUrl','')})
        if valid_event(e):
            i=next((i for i,x in enumerate(consolidated) if duplicate(x,e)),None)
            if i is None: consolidated.append(e)
            else: consolidated[i]=merge_event(consolidated[i],e)
    scrape=[]; scrape_stats={}; errors=[]
    if SCRAPING:
        for page,c in FONTI:
            items,stats=scrape_source(page,c); scrape_stats[c+' | '+page]=stats
            for raw in items:
                e=clean_event(raw,c,{raw.get('fonteUrl',''),page})
                if valid_event(e) and e.get('fonteUrl') and specific_url(e['fonteUrl']): scrape.append(e)
    gemini,cited,status,area_stats=find_events()
    if status!='ok': errors.append('Ricerca Gemini eventi: '+status)
    added=updated=0
    for e in scrape+gemini:
        i=next((i for i,x in enumerate(consolidated) if duplicate(x,e)),None)
        if i is None: consolidated.append(e); added+=1
        else:
            merged=merge_event(consolidated[i],e)
            if merged!=consolidated[i]: consolidated[i]=merged; updated+=1
    final=sorted(consolidated,key=lambda x:(x.get('dataInizio','9999-12-31'),priority(x.get('citta')),x.get('titolo','').lower()))
    atomic_json(EVENTI,final)
    places=load_json(LUOGHI,[]); activities=load_json(ATTIVITA,[])
    if RUN_PERMANENTI:
        p,a,purls,pstatus=find_permanents()
        if pstatus=='ok':
            places=dedup_permanent((places if isinstance(places,list) else [])+p)
            activities=dedup_permanent((activities if isinstance(activities,list) else [])+a)
            atomic_json(LUOGHI,places); atomic_json(ATTIVITA,activities)
        else: errors.append('Ricerca luoghi/attività: '+pstatus)
    city_counts=Counter(x.get('citta','Sconosciuta') for x in final)
    cat_counts=Counter(x.get('categoria','Altro') for x in final)
    bands=Counter(x.get('fasciaTerritoriale',band(x.get('citta'))) for x in final)
    specific=sum(1 for x in final if specific_url(x.get('fonteUrl')))
    report={'aggiornatoAl':now().strftime('%Y-%m-%d %H:%M:%S'),'dataRiferimento':today(),'versioneMotore':'3.0',
      'modelloGemini':MODEL,'totaleEventiAttivi':len(final),'nuoviAggiunti':added,'aggiornati':updated,
      'coperturaTerritorialeOrientativa':dict(bands),'ripartizioneCategorie':dict(cat_counts.most_common()),
      'topComuni':dict(city_counts.most_common(25)),'urlSpecifici':specific,
      'percentualeUrlSpecifici':round(specific/len(final)*100,1) if final else 0,'urlCitatiGemini':len(cited),
      'ricercheAgenti':area_stats,
      'fontiScraping':scrape_stats,'candidatiLuoghiDaVerificare':len(places) if isinstance(places,list) else 0,
      'candidatiAttivitaDaVerificare':len(activities) if isinstance(activities,list) else 0,'errori':errors,
      'nota':'v3: tre chiamate Gemini territoriali per la ricerca quotidiana eventi; scraping senza Gemini. Luoghi/attività solo con RUN_PERMANENTI=1 e revisione manuale.'}
    atomic_json(REPORT,report)
    log.info('FINE | eventi=%s | nuovi=%s | aggiornati=%s | URL Search=%s',len(final),added,updated,len(cited))

if __name__=='__main__': main()
