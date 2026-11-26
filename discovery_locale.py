"""Discovery locale da feed originali e ricerche di appuntamenti settimanali."""
import re
from datetime import datetime,timedelta
from hashlib import sha256
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode,urlparse

TEMI = re.compile(r"\b(?:karaoke|apericena|aperitiv[oi]|dj[\s-]*set|deejay|latin[oa]|bachata|salsa|kizomba|dinner\s+show|music\s+selection|musica\s+(?:live|dal\s+vivo)|live\s+music|serat[ae]|party|soft\s+clubbing|brunch|cen[ae]|cenon[ei]|veglion[ei]|capodanno|mercatin[oi]|presepe\s+vivente|natale|befana|laborator[io]+|spettacol[oi]|concert[oi]|sagr[ae]|degustazion[ei]|festa)\b",re.I)
SETTIMANA = re.compile(r"\b(?:karaoke|apericena|aperitiv[oi]|dj[\s-]*set|deejay|bachata|salsa|kizomba|dinner\s+show|music\s+selection|musica\s+(?:live|dal\s+vivo)|live\s+music|serat[ae]\s+latin[ae]|soft\s+clubbing|party|brunch)\b",re.I)

def fonti():
    return [
        {"nome":"RSS originale Lanotiziaweb","url":"https://www.lanotiziaweb.it/feed/","dominio":"lanotiziaweb.it","prioritaria":True,"solo_cerignola":True,"feed_editore":True,"max_schede_rss":6},
        {"nome":"RSS originale Marchiodoc","url":"https://www.marchiodoc.it/feed/","dominio":"marchiodoc.it","prioritaria":True,"solo_cerignola":True,"feed_editore":True,"max_schede_rss":6},
        {"nome":"RSS originale Foggia Reporter","url":"https://www.foggiareporter.it/feed","dominio":"foggiareporter.it","prioritaria":True,"solo_cerignola":True,"feed_editore":True,"max_schede_rss":6},
    ]

def settimanali():
    temi=[
        ("Karaoke e ballo",'(karaoke OR bachata OR salsa OR kizomba OR "serata latina")'),
        ("Aperitivi e brunch",'(apericena OR "aperitivo musicale" OR "aperitivo domenicale" OR brunch OR "soft clubbing")'),
        ("DJ e musica live",'("dj set" OR "dinner show" OR "music selection" OR "musica dal vivo" OR "live music")'),
    ]
    return [{"nome":"Cerignola settimanali - "+nome,"url":"https://news.google.com/rss/search?"+urlencode({"q":f'Cerignola {tema} when:21d',"hl":"it","gl":"IT","ceid":"IT:it"}),"solo_cerignola":True,"prioritaria":True,"ricorrente_verificata":True,"focus_serate":True,"max_schede_rss":3} for nome,tema in temi]

CENE_SHOW = re.compile(r"\b(?:cen[ae]\s+(?:con\s+)?(?:spettacol[oi]|musica\s+dal\s+vivo|dj[\s-]*set)|dinner[\s-]+show|apericena\s+(?:con\s+)?(?:dj|live)|pranz[oi]\s+spettacol[oi]|perc[u]?ssioni\s+live|showman)\b", re.I)
CENE_SHOW_QUERY = '("cena spettacolo" OR "cena con spettacolo" OR "dinner show" OR "cena con musica" OR "cena con dj" OR "pranzo spettacolo" OR showman OR "apericena dj")'

def fonti_cene_show(registro):
    """Discovery mirata: i nomi dei locali e dei promoter sono indizi, non eventi."""
    def fonte(nome,comuni,tema,prioritaria=False,alias=()):
        q=f'{comuni} {tema} when:30d'
        return {"nome":nome,"url":"https://news.google.com/rss/search?"+urlencode({"q":q,"hl":"it","gl":"IT","ceid":"IT:it"}),"nightlife":True,"cene_show":True,"prioritaria":prioritaria,"max_schede_rss":4,"alias_ricerca":list(alias)}
    out=[
        fonte("Cena spettacolo Cerignola","Cerignola",CENE_SHOW_QUERY,True),
        fonte("Cena spettacolo Reali Siti","(Stornara OR Stornarella OR Orta Nova OR Carapelle OR San Ferdinando OR Trinitapoli OR Canosa OR Lavello)",CENE_SHOW_QUERY),
        fonte("Cena spettacolo Foggia","Foggia",CENE_SHOW_QUERY),
        fonte("Cena spettacolo costa BAT","(Barletta OR Trani OR Bisceglie OR Andria OR Margherita di Savoia)",CENE_SHOW_QUERY),
        fonte("Cena spettacolo Gargano","(Manfredonia OR Zapponeta OR Siponto)",CENE_SHOW_QUERY),
        fonte("Cena spettacolo Vulture","(Melfi OR Venosa OR Rionero OR Candela OR Ascoli Satriano)",CENE_SHOW_QUERY),
    ]
    out[0]["solo_cerignola"]=True
    for comune,locali in registro.items():
        alias=list(dict.fromkeys(a for r in locali if isinstance(r,dict) for a in r.get("alias",[])+r.get("organizzatori",[]) if isinstance(a,str) and len(a)>=5 and '"' not in a))
        for i in range(0,len(alias),8):
            gruppo=alias[i:i+8]
            nomi="("+" OR ".join('"'+a+'"' for a in gruppo)+")"
            out.append(fonte(f"Promoter e locali {comune} {i//8+1}",comune+" "+nomi,CENE_SHOW_QUERY,comune=="Cerignola",gruppo))
    return out

GUIDE_MOVI_DA = [
    {"nome":"Pugliando", "profilo":"https://www.instagram.com/pugliando_cosa_fare_in_puglia/", "alias":'("pugliando_cosa_fare_in_puglia" OR "Pugliando")'},
    {"nome":"Fuori Social", "profilo":"https://fuori.social/scopri?dove=foggia", "alias":"site:fuori.social"},
    {"nome":"Papido", "profilo":"https://www.papido.it/foggia/", "alias":"site:papido.it"},
    {"nome":"ToDoPuglia", "profilo":"https://todopuglia.it/eventi-puglia/", "alias":"site:todopuglia.it"},
]
def fonti_guide_movida(registro):
    """Ricerche di annunci pubblici indicizzati, mai accesso a Stories o account privati."""
    aree=['(Cerignola OR Foggia OR Stornara OR Stornarella OR Canosa OR "Orta Nova" OR Trinitapoli OR Lavello)', '(Trani OR Barletta OR Bisceglie OR Andria OR Manfredonia OR "Margherita di Savoia")']
    tema='(serata OR discoteca OR karaoke OR "dj set" OR "cena spettacolo" OR "musica dal vivo" OR apericena OR spaghettata)'
    out=[]
    def aggiungi(nome,q,profilo):
        out.append({"nome":nome,"url":"https://news.google.com/rss/search?"+urlencode({"q":q+" when:21d","hl":"it","gl":"IT","ceid":"IT:it"}),"profilo":profilo,"focus_serate":True,"nightlife":True,"max_schede_rss":4})
    for g in GUIDE_MOVI_DA:
        for i,area in enumerate(aree):
            aggiungi("Guida movida "+g["nome"]+" "+str(i+1),g["alias"]+" "+area+" "+tema,g["profilo"])
    # Ricerca anche i singoli locali segnalati, senza richiedere il formato cena-show.
    for comune,locali in registro.items():
        alias=list(dict.fromkeys(a for r in locali for a in r.get("alias",[])+r.get("organizzatori",[]) if isinstance(a,str) and len(a)>=5 and '"' not in a))
        for i in range(0,len(alias),8):
            nomi="("+" OR ".join('"'+a+'"' for a in alias[i:i+8])+")"
            aggiungi("Annunci locali "+comune+" "+str(i//8+1),comune+" "+nomi+" "+tema,"")
            if comune=="Cerignola":
                out[-1]["solo_cerignola"]=True
    # Ricerca locale anche per format emergenti e pubblicazioni indicizzate sui social.
    # Nessun evento viene creato soltanto a partire da un nome o da un giorno ricorrente.
    for comune in ("Cerignola", "Orta Nova", "Canosa di Puglia", "Trani", "Barletta", "Manfredonia", "Bisceglie", "Foggia"):
        aggiungi("Radar weekend "+comune, '"'+comune+'" (venerdì OR sabato OR domenica) ("dj set" OR karaoke OR "dinner show" OR "serata latina" OR "live music" OR "quiz game" OR "tributo live" OR "soft clubbing")',"")
        if comune=="Cerignola":
            out[-1]["solo_cerignola"]=True
            out[-1]["prioritaria"]=True
    return out

def fonti_organizzatori_movida(registro):
    """Discovery per artisti e promoter: mai prova di sede, data o evento."""
    # Evidenze storiche pubbliche, non annunci correnti:
    # https://www.cerignolaviva.it/notizie/festa-della-birra-in-piazza-della-repubblica-a-cerignola-birra-food-giochi-e-musica/
    # https://www.cerignolaviva.it/notizie/notte-fantastica-2024-a-cerignola-guest-star-paola-chiara/
    # https://cerignola.halleyweb.it/zf/index.php/trasparenza/index/detail/categoria/63/page/60/serial/114838/serial-beneficiario/23075/tipo/3
    # https://www.scienzesociali.unifg.it/sites/scienzesociali/files/2025-04/14-16%20Dicembre%202024_Programma-Generale%20Heritage%20of%20the%20Apulian%20Experience.pdf
    # https://www.andreaordinemusic.it/
    nomi_per_comune={"Cerignola":["Neverland Cerignola","Ideando Eventi","Luigi Sgaramella Eventi","Sgaramella Eventi","Andrea Ordine","Antonio Depalma","Nicola Lomuscio","Christian Antonacci"]}
    tema='("dj set" OR deejay OR karaoke OR "musica dal vivo" OR "cena spettacolo" OR party OR "serata" OR apericena)'
    for comune,locali in registro.items():
        for locale in locali:
            for nome in locale.get("organizzatori",[]):
                if isinstance(nome,str) and 5<=len(nome)<=100 and '"' not in nome:
                    nomi_per_comune.setdefault(comune,[]).append(nome)
    out=[]
    for comune,nomi in nomi_per_comune.items():
        unici=list(dict.fromkeys(nomi))
        for i in range(0,len(unici),4):
            gruppo=unici[i:i+4]
            q='"'+comune+'" ('+" OR ".join('"'+n+'"' for n in gruppo)+") "+tema+" when:30d"
            out.append({"nome":"Radar Movida - "+comune+" organizzatori "+str(i//4+1),"url":"https://news.google.com/rss/search?"+urlencode({"q":q,"hl":"it","gl":"IT","ceid":"IT:it"}),"radar_movida":True,"nightlife":True,"focus_serate":True,"prioritaria":comune=="Cerignola","solo_cerignola":comune=="Cerignola","comune_radar":comune,"alias_movida":[],"max_schede_rss":4})
    return out

def alias_locale(testo,registro):
    """Un alias serve soltanto a trovare il candidato, non a provare la sede."""
    testo=testo or ""
    return any(re.search(r"(?<!\w)"+re.escape(a)+r"(?!\w)",testo,re.I)
               for r in registro for a in r.get("alias",[])
               if isinstance(a,str) and len(a.strip())>=5 and a.casefold() not in {"pro loco","il titolo","bar roma","villa eden","motus","nonzai"})

def istante_pubblicazione(valore):
    if not valore:
        return None
    try:
        return parsedate_to_datetime(valore)
    except (ValueError, TypeError, OverflowError):
        try:
            return datetime.fromisoformat(valore.replace("Z", "+00:00"))
        except (ValueError, TypeError, OverflowError):
            return None


def data_pubblicazione(valore):
    ts = istante_pubblicazione(valore)
    return ts.date() if ts is not None else None


def misura_ritardo(soup, url, ora, data_editore=""):
    valori = []
    if soup:
        el = soup.select_one('meta[property="article:published_time"], [itemprop="datePublished"]')
        if el:
            valori.append(el.get("content") or el.get("datetime") or "")
    valori.append(data_editore)
    for valore in valori:
        ts = istante_pubblicazione(valore)
        if ts is None or ts.utcoffset() is None:
            continue
        delta = (ora - ts.astimezone(ZoneInfo("Europe/Rome"))).total_seconds() / 60
        if 0 <= delta <= 180 * 1440:
            return {sha256(url.encode()).hexdigest()[:16]: round(delta, 1)}
    return {}

def data_evento_documentata(testo,d):
    """Rifiuta 'ogni venerdì' o orari di apertura senza singola data esplicita."""
    try:
        dt=datetime.fromisoformat(d).date()
    except (TypeError,ValueError):
        return False
    mesi="gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()
    t= re.sub(r"\s+"," ",testo or "").casefold()
    giorno=rf"0?{dt.day}"
    mese=mesi[dt.month-1]
    numerico=rf"{giorno}[./-]0?{dt.month}"
    return bool(re.search(rf"\b{giorno}\s+{mese}\s+{dt.year}\b|\b{numerico}[./-](?:{dt.year}|{dt.year%100:02d})\b|\b{dt.isoformat()}\b",t))

def data_coerente_pubblicazione(evento,pub):
    if pub is None:
        return True
    try:
        inizio=datetime.fromisoformat(evento["dataInizio"]).date()
        fine=datetime.fromisoformat(evento.get("dataFine",evento["dataInizio"])).date()
    except (KeyError,TypeError,ValueError):
        return False
    return fine>=pub and inizio<=pub+timedelta(days=180)


def titolo_locandina_compatibile(titolo,testo):
    """Almeno due termini distintivi in comune; date e termini generici non bastano."""
    stop={"evento","eventi","cerignola","serata","serate","festa","sabato","venerdì","domenica","novembre","dicembre","gennaio","febbraio","marzo","aprile","maggio","giugno","luglio","agosto","settembre","ottobre","locandina","programma","ingresso","musica","dalle","presso","della","delle","dello","dalla","dalle","dove","quando","news","notizie","party","concerti","concerto"}
    def parole(s):
        return set(re.findall(r"[a-zà-ù]{4,}",str(s or "").casefold()))-stop
    return len(parole(titolo)&parole(testo))>=2
