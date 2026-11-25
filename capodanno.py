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

def stagione(oggi):
    if oggi.month in (11, 12):
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
