"""Discovery locale da feed originali e ricerche di appuntamenti settimanali."""
import re
from datetime import datetime,timedelta
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
    return [{"nome":"Cerignola settimanali - "+nome,"url":"https://news.google.com/rss/search?"+urlencode({"q":f'Cerignola {tema} when:21d',"hl":"it","gl":"IT","ceid":"IT:it"}),"solo_cerignola":True,"prioritaria":True,"ricorrente_verificata":True,"max_schede_rss":3} for nome,tema in temi]

def alias_locale(testo,registro):
    """Un alias serve soltanto a trovare il candidato, non a provare la sede."""
    testo=testo or ""
    return any(re.search(r"(?<!\w)"+re.escape(a)+r"(?!\w)",testo,re.I)
               for r in registro for a in r.get("alias",[])
               if isinstance(a,str) and len(a.strip())>=5 and a.casefold() not in {"pro loco","il titolo","bar roma","villa eden","motus","nonzai"})

def data_pubblicazione(valore):
    if not valore:
        return None
    try:
        return parsedate_to_datetime(valore).date()
    except (ValueError,TypeError,OverflowError):
        try:
            return datetime.fromisoformat(valore.replace("Z","+00:00")).date()
        except (ValueError,TypeError,OverflowError):
            return None

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
