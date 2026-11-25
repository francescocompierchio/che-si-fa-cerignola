"""Calendario festivo locale: solo date documentate, nessuna ricorrenza presunta."""
import re
from datetime import date
from urllib.parse import urlencode

TEMA = re.compile(r"\b(?:natale|natalizi[oaie]|vigilia|immacolata|santo\s+stefano|epifania|befana|presep[ei]|mercatini|tombolat[ae]|luminarie|villaggio\s+di\s+babbo\s+natale)\b", re.I)
FORMATO = re.compile(r"\b(?:pranz[oi]|cen[ae]|cenon[ei]|men[uù]|serat[ae]|dj\s*set|party|musica|concert[oi]|festa|spettacol[oi]|presep[ei]|mercatini|tombolat[ae]|luminarie|villaggio|laborator[io]+|animazione|degustazion[ei]|brunch)\b", re.I)
GIORNI = {8:"Immacolata",24:"Vigilia di Natale",25:"Natale",26:"Santo Stefano"}
LINK = re.compile(r"natale|natalizi|vigilia|immacolata|santo.?stefano|epifania|befana|presepe|mercatin|tombolat|luminar|locandina|menu|menù",re.I)

def stagione(oggi):
    if oggi.month in (11,12):
        return oggi.year
    if oggi.month == 1 and oggi.day <= 6:
        return oggi.year-1
    return None

def date_documentate(testo, anno):
    t = re.sub(r"\s+", " ", testo or "").casefold()
    if not TEMA.search(t) or not FORMATO.search(t):
        return []
    # Non usare una data di pubblicazione come data dell'appuntamento.
    t = re.sub(r"\b(?:pubblicato|aggiornato|pubblicazione|aggiornamento)\s*(?:il|del|:)?\s*\d{1,2}(?:\s+(?:novembre|dicembre|gennaio)\s+|[./-]\d{1,2}[./-])20\d{2}\b","",t)
    matches=[]
    for m in re.finditer(r"\b(\d{1,2})[°º]?\s+(novembre|dicembre|gennaio)\s+(20\d{2})\b",t):
        matches.append((int(m[3]),{"novembre":11,"dicembre":12,"gennaio":1}[m[2]],int(m[1])))
    for m in re.finditer(r"\b(\d{1,2})[./-](11|12|0?1)[./-](20\d{2})\b",t):
        matches.append((int(m[3]),int(m[2]),int(m[1])))
    for m in re.finditer(r"\b(20\d{2})-(11|12|01)-(\d{2})\b",t):
        matches.append(tuple(map(int,m.groups())))
    # Festività con nome + anno sono date esplicite per convenzione.
    for label,month,day in (("immacolata",12,8),("vigilia di natale",12,24),("pranzo di natale",12,25),("santo stefano",12,26),("epifania",1,6),("befana",1,6)):
        for m in re.finditer(r"\b"+label+r"\s+(20\d{2})\b",t):
            matches.append((int(m[1]),month,day))
    if not matches:
        return []
    out=set()
    for y,m,d in matches:
        try:
            v=date(y,m,d)
        except ValueError:
            return []
        if not date(anno,11,1)<=v<=date(anno+1,1,6):
            return []
        out.add(v.isoformat())
    # Gli intervalli e i programmi con più date richiedono schede separate.
    if re.search(r"\b(?:dal|dall')\s+\d{1,2}\s+(?:novembre|dicembre|gennaio)\b.*?\b(?:al|fino al)\s+\d{1,2}",t):
        return []
    if re.search(r"\b\d{1,2}\s*(?:,|e|ed|[-–])\s*\d{1,2}\s+(?:novembre|dicembre|gennaio)\b",t):
        return []
    # Un giorno esplicito senza anno non deve essere contraddetto dal giorno datato.
    for m in re.finditer(r"\b(\d{1,2})[°º]?\s+(novembre|dicembre|gennaio)\b",t):
        month={"novembre":11,"dicembre":12,"gennaio":1}[m[2]]
        try:
            v=date(anno+1 if month==1 else anno,month,int(m[1])).isoformat()
        except ValueError:
            return []
        if v not in out:
            return []
    return sorted(out)

def fonti(oggi, strutture):
    anno=stagione(oggi)
    if anno is None:
        return []
    temi=[
        ("Vigilia Natale Immacolata", '(Natale OR Vigilia OR Immacolata) (pranzo OR cena OR menu OR serata OR concerto)'),
        ("Santo Stefano", '"Santo Stefano" (pranzo OR menu OR serata OR festa OR dj)'),
        ("Epifania Befana", '(Epifania OR Befana) (festa OR bambini OR laboratorio OR pranzo OR spettacolo)'),
        ("Mercatini Presepi Famiglie", '(mercatini OR "presepe vivente" OR "villaggio di Natale" OR tombola OR luminarie OR "Natale a Palazzo")'),
        ("Social festività", '(site:facebook.com OR site:instagram.com) (Natale OR "Santo Stefano" OR Befana OR presepe) (evento OR locandina OR menu OR serata)'),
        ("Organizzatori locali", '("Fare Rete" OR "Palazzo Fornari" OR "San Giuseppe ONLUS" OR "Moving Music" OR "Bellavita Eventi" OR "Oltre Babele" OR "Pro Loco") (Natale OR presepe OR Befana OR festa)'),
    ]
    for i in range(0,len(strutture),5):
        nomi=" OR ".join('"'+r["nome"].replace('"','')+'"' for r in strutture[i:i+5])
        temi.append(("Sale ricevimenti "+str(i//5+1), f"({nomi}) (Natale OR Vigilia OR Immacolata OR \"Santo Stefano\" OR Epifania OR Befana) (pranzo OR cenone OR menu OR serata)"))
    out=[]
    for nome,tema in temi:
        q=f"Cerignola {tema} ({anno} OR {anno+1}) when:60d"
        out.append({"nome":"Festivita Cerignola - "+nome,"url":"https://news.google.com/rss/search?"+urlencode({"q":q,"hl":"it","gl":"IT","ceid":"IT:it"}),"anno_festivita":anno,"solo_cerignola":True,"prioritaria":True,"max_schede_rss":2})
    return out

def titolo_pasto(testo,d):
    t=testo.casefold()
    if not re.search(r"\b(?:pranzo|cena|cenone|menu|menù|brunch|veglione|dj\s*set|party|serata)\b",t):
        return ""
    day=date.fromisoformat(d)
    nome=GIORNI.get(day.day) if day.month==12 else ("Epifania" if (day.month,day.day)==(1,6) else None)
    if not nome:
        return ""
    if re.search(r"\b(?:pranzo|brunch)\b",t):
        return "Pranzo di "+nome
    if re.search(r"\b(?:cena|cenone)\b",t):
        return "Cena di "+nome
    if re.search(r"\b(?:serata|dj\s*set|party|veglione)\b",t):
        return "Serata di "+nome
    return ""
