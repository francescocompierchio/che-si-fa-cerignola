"""Apprendimento operativo deterministico: feedback da risultati verificati.
Non modifica codice, credenziali, grafica o criteri di validazione."""
from collections import Counter
from datetime import timedelta
from urllib.parse import urlencode,urlparse
import re

AREE = {
    "Locali & Serate": ('("dj set" OR karaoke OR apericena)', '("serata latina" OR party OR "dinner show")', '("musica dal vivo" OR "live music" OR brunch)'),
    "Musica & Concerti": ('(concerto OR "musica live" OR "cover band")', '(concerto OR "live music" OR festival)'),
    "Sagre & Food": ('(sagra OR degustazione OR "cena a tema")', '(cenone OR menu OR "cena evento")'),
    "Famiglie & Bambini": ('(bambini OR "laboratorio creativo" OR animazione)', '(mercatini OR "fattoria didattica" OR spettacolo)'),
    "Natura & Escursioni": ('(escursione OR trekking OR "visita guidata")', '(passeggiata OR "attività all’aperto" OR "family day")'),
}

def lacune(eventi,oggi):
    fine=(oggi+timedelta(days=14)).isoformat()
    conteggi=Counter(e.get("categoria") for e in eventi if e.get("citta")=="Cerignola" and e.get("dataFine",e.get("dataInizio",""))>=oggi.isoformat() and e.get("dataInizio","")<=fine)
    return {area:conteggi[area] for area in AREE}

def fonti(memoria,eventi,oggi):
    """Al massimo tre esplorazioni a ciclo: due aree carenti e una a rotazione.
    Query nuove non equivalgono a eventi: valgono sempre le verifiche esistenti."""
    cont=memoria.get("apprendimento",{}).get("cicli",0)
    carenze=lacune(eventi,oggi)
    aree=sorted(AREE,key=lambda a:(carenze[a],0 if a=="Locali & Serate" else 1,a))
    scelte=list(dict.fromkeys(aree[:2]+[list(AREE)[cont%len(AREE)]]))
    out=[]
    for area in scelte:
        varianti=AREE[area]
        indice=cont%len(varianti)
        q=f'Cerignola {varianti[indice]} when:30d'
        out.append({"nome":f"Apprendimento Cerignola - {area} {indice+1}","url":"https://news.google.com/rss/search?"+urlencode({"q":q,"hl":"it","gl":"IT","ceid":"IT:it"}),"solo_cerignola":True,"prioritaria":True,"max_schede_rss":3})
    return out

def misura(risultati,precedenti,pubblicati,duplicati):
    """Premia novità finite realmente in archivio, non il numero grezzo di estrazioni.
    Più fonti possono confermare un evento; ogni fonte riceve al massimo un credito
    per lo stesso record pubblicato. Non è una stima di accuratezza statistica."""
    out={}
    for nome,eventi in risultati.items():
        validi=set()
        nuovi=set()
        locali=set()
        serate=set()
        for e in eventi:
            for i,f in enumerate(pubblicati):
                if not duplicati(e,f) or e.get("dataInizio")!=f.get("dataInizio") or e.get("dataFine")!=f.get("dataFine"):
                    continue
                validi.add(i)
                if not any(duplicati(f,p) for p in precedenti):
                    nuovi.add(i)
                    if f.get("citta")=="Cerignola":
                        locali.add(i)
                        if f.get("categoria")=="Locali & Serate":
                            serate.add(i)
                break
        out[nome]={"eventiUtili":len(validi),"novitaUtili":len(nuovi),"novitaCerignola":len(locali),"nuoveSerateCerignola":len(serate)}
    return out

def aggiorna(memoria,eventi,oggi,now):
    a=memoria.setdefault("apprendimento",{})
    a["cicli"]=int(a.get("cicli",0))+1
    a["lacune14Giorni"]=lacune(eventi,oggi)
    storico=a.get("storico",[])
    if not isinstance(storico,list):
        storico=[]
    storico.append({"timestamp":now,"lacune":a["lacune14Giorni"],"totaleCerignola":sum(e.get("citta")=="Cerignola" for e in eventi)})
    a["storico"]=storico[-336:]  # circa sette giorni a cadenza semioraria
    return a
