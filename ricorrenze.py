"""Ricerca stagionale annuale: le ricorrenze attivano le ricerche, non creano eventi."""
import re
from datetime import date,timedelta
from urllib.parse import urlencode,urlparse

MESI = dict(zip("gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split(),range(1,13)))
FORMATO = re.compile(r"\b(?:concert[oi]|spettacol[oi]|dj\s*set|party|serat[ae]|sfilat[ae]|carri\s+allegorici|festa\s+in\s+piazza|fiera|sagr[ae]|luna\s+park|mercatin[oi]|fuochi\s+pirotecnici|pranz[oi]|cen[ae]|men[uù]|brunch|degustazion[ei]|escursion[ei]|pic\s*nic|laborator[io]+|animazione|festa\s+per\s+bambini|musica\s+dal\s+vivo)\b",re.I)

def pasqua(y):
    a=y%19;b=y//100;c=y%100;d=b//4;e=b%4;f=(b+8)//25;g=(b-f+1)//3
    h=(19*a+b-d-g+15)%30;i=c//4;k=c%4;l=(32+2*e+2*i-h-k)%7;m=(a+11*h+22*l)//451
    v=h+l-7*m+114
    return date(y,v//31,v%31+1)

def calendario(y):
    p=pasqua(y)
    def item(nome,chiave,giorno,prima=45,dopo=3,elasticita=2):
        return dict(nome=nome,chiave=chiave,giorno=giorno,prima=prima,dopo=dopo,elasticita=elasticita)
    return [
        item("Carnevale",r"carnevale|carnevalesc\w*|marted[iì] grasso",p-timedelta(days=47),45,1,18),
        item("San Valentino",r"san valentino",date(y,2,14),35),
        item("Festa della donna",r"festa (?:della|delle) donn[ae]|8 marzo",date(y,3,8),30),
        item("Pasqua e Pasquetta",r"pasqua|pasquetta|luned[iì] dell['’]angelo",p,45,2,2),
        item("Primo maggio",r"primo maggio|1[°º]? maggio",date(y,5,1),30),
        item("Ferragosto",r"ferragosto",date(y,8,15),45,3,3),
        item("Madonna di Ripalta",r"madonna di ripalta|maria\s+(?:ss\.?|santissima)\s+di\s+ripalta|festa patronale|festa di ripalta",date(y,9,8),120,5,14),
        item("Halloween",r"halloween",date(y,10,31),35,2,3),
    ]

def attive(oggi):
    return [x for y in (oggi.year,oggi.year+1) for x in calendario(y)
            if x["giorno"]-timedelta(days=x["prima"])<=oggi<=x["giorno"]+timedelta(days=x["dopo"])]

def tema(testo, ricorrenze):
    return any(re.search(r"\b(?:"+x["chiave"]+r")\b",testo or "",re.I) for x in ricorrenze)

def date_documentate(testo,ricorrenze):
    """Date esplicite con anno; nessuna inferenza da programmi passati o ricorrenze."""
    t=re.sub(r"\s+"," ",testo or "").casefold()
    if not FORMATO.search(t):
        return []
    t=re.sub(r"\b(?:pubblicato|aggiornato|pubblicazione|aggiornamento)\s*(?:il|del|:)?\s*\d{1,2}\s+\w+\s+20\d{2}\b","",t)
    # Un programma multi-data necessita di una scheda per appuntamento.
    if re.search(r"\b(?:dal|dall')\s+\d{1,2}\s+(?:"+"|".join(MESI)+r")\b.*?\b(?:al|fino al)\s+\d{1,2}",t):
        return []
    if re.search(r"\b\d{1,2}\s*(?:,|e|ed|[-–])\s*\d{1,2}\s+(?:"+"|".join(MESI)+r")\b",t):
        return []
    matches=[]
    for m in re.finditer(r"\b(\d{1,2})[°º]?\s+("+"|".join(MESI)+r")\s+(20\d{2})\b",t):
        matches.append((int(m[3]),MESI[m[2]],int(m[1])))
    for m in re.finditer(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b",t):
        matches.append((int(m[3]),int(m[2]),int(m[1])))
    for m in re.finditer(r"\b(20\d{2})-(\d{2})-(\d{2})\b",t):
        matches.append(tuple(map(int,m.groups())))
    if not matches:
        return []
    dates=set()
    for y,m,d in matches:
        try:
            dates.add(date(y,m,d))
        except ValueError:
            return []
    if len(dates)!=1:
        return []
    d=next(iter(dates))
    for m in re.finditer(r"\b(\d{1,2})[°º]?\s+("+"|".join(MESI)+r")\b",t):
        if (int(m[1]),MESI[m[2]])!=(d.day,d.month):
            return []
    return [(d.isoformat(),x["nome"]) for x in ricorrenze
            if tema(t,[x]) and abs((d-x["giorno"]).days)<=x["elasticita"]]

def fonti(oggi,strutture):
    ric=attive(oggi)
    if not ric:
        return [],[]
    rss=[]
    for x in ric:
        nome=x["nome"];anno=x["giorno"].year
        termini={"Carnevale":"(Carnevale OR \"martedì grasso\")","Pasqua e Pasquetta":"(Pasqua OR Pasquetta)","Madonna di Ripalta":"(\"Madonna di Ripalta\" OR \"festa patronale\" OR \"festa di Ripalta\")"}.get(nome,'"'+nome+'"')
        for tag,extra in (("eventi","(concerto OR festa OR serata OR pranzo OR fiera OR locandina OR menu OR spettacolo)"),("social","(site:instagram.com OR site:facebook.com) (evento OR festa OR menu OR locandina OR serata)")):
            q=f"Cerignola {termini} {extra} {anno} when:90d"
            rss.append({"nome":f"Ricorrenze Cerignola - {nome} {tag}","url":"https://news.google.com/rss/search?"+urlencode({"q":q,"hl":"it","gl":"IT","ceid":"IT:it"}),"ricorrenze_annuali":[x],"solo_cerignola":True,"prioritaria":True,"max_schede_rss":3})
    dirette=[]
    for r in strutture:
        url=r.get("sito","")
        if isinstance(url,str) and urlparse(url).scheme=="https" and urlparse(url).hostname:
            dirette.append({"nome":"Ricorrenze sito - "+r["nome"],"url":url,"dominio":urlparse(url).hostname,"sede":r["nome"],"ricorrenze_annuali":ric,"prioritaria":True})
    return dirette,rss
