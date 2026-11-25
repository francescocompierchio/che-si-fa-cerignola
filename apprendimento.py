"""Apprendimento operativo deterministico: feedback da risultati verificati.
Non modifica codice, credenziali, grafica o criteri di validazione."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlencode,urlparse
import re
import json
from pathlib import Path
from math import log, sqrt

AREE = {
    "Locali & Serate": ('("dj set" OR karaoke OR apericena)', '("serata latina" OR party OR "dinner show" OR "cena spettacolo" OR showman)', '("musica dal vivo" OR "live music" OR brunch)'),
    "Musica & Concerti": ('(concerto OR "musica live" OR "cover band")', '(concerto OR "live music" OR festival)'),
    "Sagre & Food": ('(sagra OR degustazione OR "cena a tema")', '(cenone OR menu OR "cena evento")'),
    "Famiglie & Bambini": ('(bambini OR "laboratorio creativo" OR animazione)', '(mercatini OR "fattoria didattica" OR spettacolo)'),
    "Natura & Escursioni": ('(escursione OR trekking OR "visita guidata")', '(passeggiata OR "attività all’aperto" OR "family day")'),
}

def lacune(eventi,oggi):
    fine=(oggi+timedelta(days=14)).isoformat()
    conteggi=Counter(e.get("categoria") for e in eventi if e.get("citta")=="Cerignola" and e.get("dataFine",e.get("dataInizio",""))>=oggi.isoformat() and e.get("dataInizio","")<=fine)
    return {area:conteggi[area] for area in AREE}

def editoriali(percorso="index.html"):
    """Legge l'archivio editoriale statico esclusivamente per misurare la copertura.
    Non modifica il frontend e non presume di vedere Firebase."""
    try:
        testo=Path(percorso).read_text(encoding="utf-8")
        m=re.search(r"const eventiEditoriali = (\[[\s\S]*?\]);",testo)
        dati=json.loads(m.group(1)) if m else []
        return [e for e in dati if isinstance(e,dict) and e.get("tipoContenuto")=="evento"] if isinstance(dati,list) else []
    except (OSError,ValueError):
        return []

def copertura_unita(archivio,editoriali,duplicati):
    """Priorità editoriale, senza toccare i record pubblicati."""
    out=[]
    for e in editoriali+archivio:
        if not isinstance(e,dict) or e.get("tipoContenuto")!="evento":
            continue
        if not any(e.get("dataInizio")==x.get("dataInizio") and e.get("dataFine")==x.get("dataFine") and duplicati(e,x) for x in out):
            out.append(e)
    return out

def variante(memoria,area,cont):
    """Bilancia esplorazione periodica e rendimento osservato; mai solo volume."""
    varianti=AREE[area]
    n=len(varianti)
    if cont%3==0:
        return (cont//3)%n
    fonti=memoria.get("fonti",{})
    dati=[fonti.get(f"Apprendimento Cerignola - {area} {i+1}",{}) for i in range(n)]
    totale=sum(max(0,int(x.get("tentativi",0))) for x in dati)
    def valore(i):
        x=dati[i]
        prove=max(0,int(x.get("tentativi",0)))
        return float(x.get("valoreAppreso",0))+sqrt(2*log(totale+2)/(prove+1))
    return max(range(n),key=lambda i:(valore(i),-i))

def segnali(eventi,concordanze,noti):
    """Indicatori osservabili, non probabilità di verità né pubblicazione automatica."""
    domini={}
    for e in eventi:
        if e.get("citta")!="Cerignola":
            continue
        u=str(e.get("fonteUrl") or "")
        host=(urlparse(u).hostname or "").lower().removeprefix("www.")
        if host and host not in noti and not any(host.endswith("."+n) for n in noti):
            domini.setdefault(host,set()).add(u)
    return {"concordanze":len(concordanze),"conLocandina":sum(bool(e.get("locandinaUrl")) for e in eventi),
            "senzaPrezzoDocumentato":sum(not e.get("costo") or bool(re.search(r"non indicat|non specificat|consulta|verific|da definire",str(e.get("costo")),re.I)) for e in eventi),
            "fontiDaValutare":[{"dominio":h,"schede":len(urls),"esempi":sorted(urls)[:2]} for h,urls in sorted(domini.items(),key=lambda x:(-len(x[1]),x[0]))[:12]]}

def fascia(now):
    """Orario della scoperta, non orario di pubblicazione del locale."""
    dt=datetime.fromtimestamp(now,timezone.utc).astimezone(ZoneInfo("Europe/Rome"))
    return ("weekend" if dt.weekday()>=4 else "feriale")+f"-{dt.hour//6*6:02d}"

def profilo_temporale(prima,dati,now):
    profilo={k:dict(v) for k,v in prima.get("fasce",{}).items() if isinstance(v,dict)}
    if dati.get("stato")!="ok":
        return profilo
    k=fascia(now)
    b=profilo.setdefault(k,{"prove":0,"novita":0.0})
    # Media esponenziale con numerosità limitata, per adattarsi ai cambiamenti.
    b["prove"]=min(100,int(b.get("prove",0))+1)
    b["novita"]=round(0.85*float(b.get("novita",0))+0.15*min(10,int(dati.get("novitaCerignola",0))+int(dati.get("nuoveSerateCerignola",0))),3)
    return profilo

def bonus_temporale(dati,now):
    b=dati.get("fasce",{}).get(fascia(now),{})
    if int(b.get("prove",0))<8:
        return 0.0
    return min(2.0,max(0.0,float(b.get("novita",0))))

def candidati_fonti(memoria,diagnostica,noti,now):
    """Raccoglie solo domini dichiarati da feed: candidati non attendibili.
    Non visita nuovi host, non aggiunge automaticamente fonti al crawler."""
    registro=memoria.setdefault("apprendimento",{}).setdefault("dominiCandidati",{})
    for nome,dati in diagnostica.items():
        if dati.get("stato")!="ok":
            continue
        for host in dati.get("dominiCandidati",[])[:15]:
            if not isinstance(host,str) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,180}\.[a-z]{2,24}",host):
                continue
            if any(host==n or host.endswith("."+n) for n in noti):
                continue
            b=registro.setdefault(host,{"primeSegnalazioni":now,"fonti":[],"osservazioni":0,"ultimoCiclo":0})
            if b.get("ultimoCiclo")!=now:
                b["osservazioni"]=min(999,int(b.get("osservazioni",0))+1)
            b["ultimoCiclo"]=now
            b["fonti"]=sorted(set(b.get("fonti",[])+[nome]))[:10]
    # Nessun inventario illimitato; rimuove i candidati non osservati da un mese.
    recenti=[(h,v) for h,v in registro.items() if now-v.get("ultimoCiclo",0)<=30*86400 and not any(h==n or h.endswith("."+n) for n in noti)]
    recenti.sort(key=lambda x:(-x[1].get("osservazioni",0),-len(x[1].get("fonti",[])),x[0]))
    memoria["apprendimento"]["dominiCandidati"]=dict(recenti[:100])
    return [{"dominio":h,"cicliOsservati":v["osservazioni"],"ricerche":len(v["fonti"])} for h,v in recenti[:15]]

def fonti(memoria,eventi,oggi):
    """Al massimo tre esplorazioni a ciclo: due aree carenti e una a rotazione.
    Query nuove non equivalgono a eventi: valgono sempre le verifiche esistenti."""
    cont=memoria.get("apprendimento",{}).get("cicli",0)
    carenze=lacune(eventi,oggi)
    aree=sorted(AREE,key=lambda a:(carenze[a],0 if a=="Locali & Serate" else 1,a))
    # Riserva una ricerca alla movida, anche quando qualche evento editoriale è già presente.
    scelte=list(dict.fromkeys(["Locali & Serate",aree[0],list(AREE)[cont%len(AREE)]]))
    if len(scelte)<3:
        scelte.extend(x for x in aree if x not in scelte)
    scelte=scelte[:3]
    out=[]
    for area in scelte:
        varianti=AREE[area]
        indice=variante(memoria,area,cont)
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
    storico.append({"timestamp":now,"lacune":a["lacune14Giorni"],"totaleCerignola":sum(e.get("citta")=="Cerignola" and e.get("dataFine","")>=oggi.isoformat() for e in eventi)})
    a["storico"]=storico[-336:]  # circa sette giorni a cadenza semioraria
    return a
