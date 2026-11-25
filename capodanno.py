"""Ricerca stagionale prudente. Un'anagrafica non è prova di un evento."""
import json
import re
from pathlib import Path
from urllib.parse import urlencode, urlparse

TEMA = re.compile(r"\b(?:capodanno|cenon[ei]|veglion[ei]|san\s+silvestro|new\s+year(?:'s)?\s+eve)\b", re.I)
FORMATO = re.compile(r"\b(?:cenon[ei]|veglion[ei]|pranzo|gran\s+gala|dj\s*set|party|musica|menu|menù|cena|festa|serata)\b", re.I)

def registro():
    try:
        data = json.loads(Path(__file__).with_name("fonti_capodanno.json").read_text(encoding="utf-8"))
        return [r for r in data if isinstance(r, dict) and r.get("nome")] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []

def registro_esteso():
    try:
        extra=json.loads(Path(__file__).with_name("fonti_capodanno_estese.json").read_text(encoding="utf-8"))
    except (OSError,ValueError):
        extra=[]
    return registro()+[r for r in extra if isinstance(r,dict) and r.get("nome") and r.get("alias")]

def registro_dintorni():
    return [{"nome":"Posta Bassi","alias":["Posta Bassi","Postabassi"],"citta":"Foggia","sito":"https://www.postabassi.it/eventi-speciali/"},{"nome":"Regiohotel Manfredi","alias":["Regiohotel Manfredi","Regiohotel"],"citta":"Manfredonia","sito":"https://regiohotel.it/it/promo/capodanno-benessere-con-spa-in-puglia"},{"nome":"Sala Fontana","alias":["Sala Fontana"],"citta":"San Ferdinando di Puglia","evidenza":"https://www.puglia.com/salafontana/"}]

COMUNI_RADAR = ["Stornara","Stornarella","San Ferdinando di Puglia","Orta Nova","Canosa di Puglia","Trinitapoli","Carapelle","Ordona","Margherita di Savoia","Lavello","Ascoli Satriano","Barletta","Foggia","Manfredonia","Andria","Trani","Candela","Minervino Murge","Melfi","Venosa","Zapponeta","Rionero in Vulture"]

def stagione(oggi):
    if oggi.month in (10, 11, 12):
        return oggi.year
    if oggi.month == 1 and oggi.day == 1:
        return oggi.year - 1
    return None

def date_documentate(testo, anno):
    """Anno esplicito e giorno esplicito; rifiuta locandine di anni precedenti."""
    t = re.sub(r"\s+", " ", testo or "").lower()
    if not TEMA.search(t) or not FORMATO.search(t):
        return []
    a, b = str(anno), str(anno + 1)
    dec = r"(?:31\s+dicembre|31[./-]12)"
    gen = r"(?:0?1[°º]?\s+gennaio|0?1[./-]0?1)"
    for pattern, expected in ((dec,a),(gen,b)):
        if any(y != expected for y in re.findall(r"\b"+pattern+r"\s*[/.-]?\s*(20\d{2})\b",t)):
            return []
    # Rifiuta anche slogan di una vecchia edizione.
    anni_slogan = re.findall(r"\b(?:capodanno|new\s+year(?:'s)?(?:\s+eve)?)\s*(20\d{2})\b",t)
    if any(y != b for y in anni_slogan):
        return []
    stagione_ok = bool(re.search(r"\bcapodanno\s*"+b+r"\b|\b"+a+r"\s*[/–-]\s*(?:"+b+r"|"+b[-2:]+r")\b",t))
    out = []
    if re.search(r"\b"+dec+r"\s*[/.-]?\s*(?:"+a+r"|"+a[-2:]+r")\b",t) or re.search(r"\b"+a+r"-12-31\b",t) or (stagione_ok and re.search(r"\b"+dec+r"\b",t)):
        out.append(a+"-12-31")
    if re.search(r"\b"+gen+r"\s*[/.-]?\s*(?:"+b+r"|"+b[-2:]+r")\b",t) or re.search(r"\b"+b+r"-01-01\b",t) or (stagione_ok and re.search(r"\b"+gen+r"\b",t)):
        out.append(b+"-01-01")
    return out

def fonti(oggi, dati=None):
    anno = stagione(oggi)
    if anno is None:
        return [], []
    dati = registro() if dati is None else dati
    dirette, rss = [], []
    for r in dati:
        url = r.get("sito", "")
        if isinstance(url,str) and urlparse(url).scheme == "https" and urlparse(url).hostname:
            dirette.append({"nome": "Capodanno sito - "+r["nome"], "url":url,
                            "dominio":urlparse(url).hostname,"sede":r["nome"],
                            "anno_capodanno":anno,"prioritaria":True})
    for i in range(0,len(dati),4):
        nomi = " OR ".join('"'+a.replace('"','')+'"' for r in dati[i:i+4] for a in r["alias"])
        q = f'Cerignola ({nomi}) (capodanno OR cenone OR veglione OR "San Silvestro" OR "new year") ({anno} OR {anno+1}) when:60d'
        rss.append({"nome":f"Capodanno strutture Cerignola {i//4+1}",
                    "url":"https://news.google.com/rss/search?"+urlencode({"q":q,"hl":"it","gl":"IT","ceid":"IT:it"}),
                    "anno_capodanno":anno,"solo_cerignola":True,"prioritaria":True,"max_schede_rss":3})
    for nome, filtro in (("web",""),("social","(site:instagram.com OR site:facebook.com)")):
        q=f'Cerignola {filtro} (capodanno OR cenone OR veglione OR "San Silvestro" OR "new year") ({anno} OR {anno+1}) when:60d'
        rss.append({"nome":"Capodanno Cerignola "+nome,
                    "url":"https://news.google.com/rss/search?"+urlencode({"q":q,"hl":"it","gl":"IT","ceid":"IT:it"}),
                    "anno_capodanno":anno,"solo_cerignola":True,"prioritaria":True,"max_schede_rss":4})
    return dirette,rss

def radar_esteso(oggi):
    anno=stagione(oggi)
    if anno is None:
        return [],[]
    dirette,rss=fonti(oggi,registro_esteso())
    def feed(nome,q,comune,locale=False):
        return {"nome":nome,"url":"https://news.google.com/rss/search?"+urlencode({"q":q,"hl":"it","gl":"IT","ceid":"IT:it"}),"anno_capodanno":anno,"prioritaria":locale,"solo_cerignola":locale,"focus_serate":True,"max_schede_rss":6 if locale else 3,"comune_capodanno":comune}
    tema='(capodanno OR cenone OR veglione OR "San Silvestro" OR "31 dicembre" OR "1 gennaio")'
    for nome,query in [
        ("ristoranti", "(ristorante OR trattoria OR pizzeria OR braceria OR osteria)"),
        ("ricevimenti", "(villa OR sala OR ricevimenti OR tenuta OR resort)"),
        ("agriturismi", "(agriturismo OR masseria OR hotel OR relais)"),
        ("movida", "(pub OR club OR discoteca OR rooftop OR dj OR aperitivo)"),
        ("menu e prenotazioni", '(menu OR menù OR prenota OR prenotazioni OR locandina OR prezzo)'),
        ("Instagram Facebook", "(site:instagram.com OR site:facebook.com)"),
        ("portali specializzati", "(site:cenonecapodanno.com OR site:capodanno31.com OR site:capodannofoggia.com OR site:iltaccodibacco.it)")]:
        rss.append(feed("Radar Capodanno Cerignola "+nome,"Cerignola "+tema+" "+query+" when:90d","Cerignola",True))
    for f in dirette+rss:
        f["focus_serate"]=True
        f["max_schede_rss"]=6
        if f.get("solo_cerignola"):
            f["comune_capodanno"]="Cerignola"
    for r in registro_dintorni():
        if r.get("sito"):
            dirette.append({"nome":"Capodanno dintorni sito - "+r["nome"],"url":r["sito"],"dominio":urlparse(r["sito"]).hostname,"sede":r["nome"],"comune_capodanno":r["citta"],"anno_capodanno":anno,"focus_serate":True})
        rss.append(feed("Radar Capodanno struttura "+r["nome"],'"'+r["citta"]+'" "'+r["nome"]+'" '+tema+" when:90d",r["citta"]))
    # Portali di settore: link diretti, mai pubblicare offerte senza sede e data.
    for nome,url,comune in [
        ("Capodanno Foggia","https://www.capodannofoggia.com/","Foggia"),
        ("Cenone Capodanno Foggia","https://www.cenonecapodanno.com/foggia/","Foggia"),
        ("Capodanno31 Barletta","https://www.capodanno31.com/offerte/capodanno-gran-cenone-con-delitto-al-ristorante-al-tettuccio-bt/","Barletta")]:
        dirette.append({"nome":"Radar portale "+nome,"url":url,"dominio":urlparse(url).hostname,"comune_capodanno":comune,"anno_capodanno":anno,"focus_serate":True})
    for comune in COMUNI_RADAR:
        rss.append(feed("Radar Capodanno "+comune,'"'+comune+'" '+tema+' (ristorante OR agriturismo OR sala OR hotel OR festa OR dj OR piazza) when:90d',comune))
    return dirette,rss
