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

# Obiettivi operativi, non quote di eventi da pubblicare.
ZONE_WEEKEND = {
    "Cerignola": ("Cerignola", 3),
    "Reali Siti": ('(Stornara OR Stornarella OR "Orta Nova" OR Carapelle OR "San Ferdinando di Puglia" OR Trinitapoli OR "Canosa di Puglia")', 2),
    "Costa BAT": ("(Barletta OR Trani OR Bisceglie OR Andria)", 4),
    "Gargano": ("(Manfredonia OR Zapponeta)", 2),
    "Foggia": ("Foggia", 2),
}
COMUNI_ZONE = {
    "Cerignola": {"Cerignola"},
    "Reali Siti": {"Stornara","Stornarella","Orta Nova","Carapelle","San Ferdinando di Puglia","Trinitapoli","Canosa di Puglia"},
    "Costa BAT": {"Barletta","Trani","Bisceglie","Andria"},
    "Gargano": {"Manfredonia","Zapponeta"},
    "Foggia": {"Foggia"},
}
TEMI_WEEKEND = (
    '("dj set" OR discoteca OR "club night" OR party)',
    '(karaoke OR "dinner show" OR "cena spettacolo" OR apericena)',
    '("musica dal vivo" OR "serata latina" OR "soft clubbing" OR "quiz game")',
)

def finestra_weekend(oggi):
    venerdi = oggi + timedelta(days=(4-oggi.weekday())%7)
    if oggi.weekday() >= 5:
        venerdi = oggi - timedelta(days=oggi.weekday()-4)
    return max(oggi,venerdi), venerdi+timedelta(days=2)

def lacune_weekend(eventi, oggi):
    inizio,fine=finestra_weekend(oggi)
    out={}
    for zona, (_, obiettivo) in ZONE_WEEKEND.items():
        eventi_zona=[e for e in eventi if e.get("citta") in COMUNI_ZONE[zona]
                     and e.get("categoria")=="Locali & Serate"
                     and inizio.isoformat() <= e.get("dataInizio","") <= fine.isoformat()]
        # Un target mancante avvia ricerche, non genera eventi.
        out[zona]={"eventi":len(eventi_zona),"obiettivo":obiettivo,"mancanti":max(0,obiettivo-len(eventi_zona))}
    return out

def fonti_adattive_weekend(memoria,eventi,oggi):
    lacune=lacune_weekend(eventi,oggi)
    cont=int(memoria.get("apprendimento",{}).get("cicli",0))
    budget=3 if oggi.weekday()>=2 else 1
    mancanti=[z for z,d in lacune.items() if d["mancanti"]]
    # Cerignola prima, poi lacune relative; a parita' ruota le aree.
    zone=list(ZONE_WEEKEND)
    mancanti.sort(key=lambda z:(z!="Cerignola",-lacune[z]["mancanti"]/lacune[z]["obiettivo"],(zone.index(z)-cont)%len(zone)))
    out=[]
    fonti_nel_passato=memoria.get("fonti",{})
    for zona in mancanti[:budget]:
        def valore(i):
            dati=fonti_nel_passato.get(f"Radar adattivo {zona} {i+1}",{})
            return float(dati.get("valoreAppreso",0))+sqrt(2*log(cont+2)/(int(dati.get("tentativi",0))+1))
        indice=cont%len(TEMI_WEEKEND) if cont%4==0 else max(range(len(TEMI_WEEKEND)),key=valore)
        q=f'{ZONE_WEEKEND[zona][0]} {TEMI_WEEKEND[indice]} (venerdì OR sabato OR domenica) when:21d'
        out.append({"nome":f"Radar adattivo {zona} {indice+1}","url":"https://news.google.com/rss/search?"+urlencode({"q":q,"hl":"it","gl":"IT","ceid":"IT:it"}),"solo_cerignola":zona=="Cerignola","prioritaria":zona=="Cerignola","focus_serate":True,"nightlife":True,"max_schede_rss":3})
    return out

def esplora_candidati(memoria, oggi):
    """Prova al massimo un dominio gia osservato via ricerca indicizzata.
    Non visita homepage arbitrarie, non promuove domini alla lista di fiducia."""
    registro=memoria.get("apprendimento",{}).get("dominiCandidati",{})
    cont=int(memoria.get("apprendimento",{}).get("cicli",0))
    candidati=sorted(h for h,d in registro.items() if isinstance(d,dict) and int(d.get("osservazioni",0))>=2
                     and re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,180}\.[a-z]{2,24}",h)
                     and not h.endswith((".local",".internal",".localhost")))
    if not candidati:
        return []
    host=candidati[cont%len(candidati)]
    q=f'site:{host} (Cerignola OR Foggia OR Barletta OR Trani OR Manfredonia OR Bisceglie) ("dj set" OR karaoke OR "dinner show" OR discoteca) when:21d'
    return [{"nome":"Esplorazione candidata "+host,"url":"https://news.google.com/rss/search?"+urlencode({"q":q,"hl":"it","gl":"IT","ceid":"IT:it"}),"focus_serate":True,"nightlife":True,"solo_scoperta":True,"max_schede_rss":2}]

def fonti(memoria,eventi,oggi):
    """Tre esplorazioni a ciclo: due movida e una per le altre aree a rotazione.
    Query nuove non equivalgono a eventi: valgono sempre le verifiche esistenti."""
    cont=memoria.get("apprendimento",{}).get("cicli",0)
    carenze=lacune(eventi,oggi)
    movida="Locali & Serate"
    altre=sorted((a for a in AREE if a!=movida),key=lambda a:(carenze[a],a))
    primo=variante(memoria,movida,cont)
    # Due famiglie di query distinte per la movida, a budget invariato.
    secondo=(primo+1+(cont%2))%len(AREE[movida])
    area=altre[cont%len(altre)]
    scelte=[(movida,primo),(movida,secondo),(area,variante(memoria,area,cont))]
    out=[]
    for area,indice in scelte:
        q=f'Cerignola {AREE[area][indice]} when:30d'
        out.append({"nome":f"Apprendimento Cerignola - {area} {indice+1}","url":"https://news.google.com/rss/search?"+urlencode({"q":q,"hl":"it","gl":"IT","ceid":"IT:it"}),"solo_cerignola":True,"prioritaria":True,"focus_serate":area==movida,"max_schede_rss":3})
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
        serate_territorio=set()
        for e in eventi:
            for i,f in enumerate(pubblicati):
                if not duplicati(e,f) or e.get("dataInizio")!=f.get("dataInizio") or e.get("dataFine")!=f.get("dataFine"):
                    continue
                validi.add(i)
                if not any(duplicati(f,p) for p in precedenti):
                    nuovi.add(i)
                    if f.get("categoria")=="Locali & Serate":
                        serate_territorio.add(i)
                    if f.get("citta")=="Cerignola":
                        locali.add(i)
                        if f.get("categoria")=="Locali & Serate":
                            serate.add(i)
                break
        out[nome]={"eventiUtili":len(validi),"novitaUtili":len(nuovi),"novitaCerignola":len(locali),"nuoveSerateCerignola":len(serate),"nuoveSerate":len(serate_territorio)}
    return out

def autodiagnosi(eventi, diagnostica, concordanze, oggi):
    """Segnali operativi osservabili. Non elimina eventi e non stima la verita'."""
    attivi=[e for e in eventi if e.get("dataFine",e.get("dataInizio",""))>=oggi.isoformat()]
    serate=[e for e in attivi if e.get("categoria")=="Locali & Serate"]
    mancanti=lacune_weekend(attivi,oggi)
    tentate={n:d for n,d in diagnostica.items() if d.get("stato")!="pausa"}
    errori={n:d.get("stato","n/d") for n,d in tentate.items() if d.get("stato")!="ok"}
    problemi=[]
    if any(d["mancanti"] for d in mancanti.values()):
        problemi.append("copertura_weekend_insufficiente")
    if serate and sum(bool(e.get("locandinaUrl")) for e in serate)/len(serate)<0.5:
        problemi.append("poche_immagini_serate")
    if tentate and len(errori)/len(tentate)>=0.25:
        problemi.append("molte_fonti_in_errore")
    if not tentate:
        problemi.append("nessuna_fonte_tentata")
    return {"segnali":problemi,"coperturaWeekend":mancanti,
            "fontiTentate":len(tentate),"fontiInErrore":errori,
            "serateConImmagine":sum(bool(e.get("locandinaUrl")) for e in serate),
            "serateAttive":len(serate),"eventiConConcordanza":len(concordanze),
            "criterio":"indicatori operativi; concordanza e immagine non certificano un evento"}

def aggiorna(memoria,eventi,oggi,now):
    a=memoria.setdefault("apprendimento",{})
    a["cicli"]=int(a.get("cicli",0))+1
    a["lacune14Giorni"]=lacune(eventi,oggi)
    a["lacuneWeekend"]=lacune_weekend(eventi,oggi)
    storico=a.get("storico",[])
    if not isinstance(storico,list):
        storico=[]
    storico.append({"timestamp":now,"lacune":a["lacune14Giorni"],"totaleCerignola":sum(e.get("citta")=="Cerignola" and e.get("dataFine","")>=oggi.isoformat() for e in eventi)})
    a["storico"]=storico[-336:]  # circa sette giorni a cadenza semioraria
    return a


def qualita_ciclo(memoria, diagnostica, eventi, oggi, now, *, nuovi, duplicati, concordanti):
    """Persiste misure osservate e confronta le ultime 24 ore disponibili."""
    attivi = [e for e in eventi if e.get("dataFine", "") >= oggi.isoformat()]
    esiti = Counter(d.get("stato", "n/d") for d in diagnostica.values())
    scarti = Counter()
    ritardi = {}
    for dati in diagnostica.values():
        scarti.update(dati.get("scartiSchede", {}))
        for chiave, ritardo in dati.get("ritardoSchedeMinuti", {}).items():
            ritardi[chiave] = min(ritardo, ritardi.get(chiave, ritardo))
    by_city = Counter(e.get("citta") for e in attivi)
    by_cat = Counter(e.get("categoria") for e in attivi)
    valori_ritardo = sorted(ritardi.values())
    n = len(valori_ritardo)
    mediana_ritardo = round((valori_ritardo[n // 2] + valori_ritardo[(n - 1) // 2]) / 2, 1) if n else None
    misure = {
        "timestamp": now, "fontiAttive": esiti["ok"], "fontiInPausa": esiti["pausa"],
        "eventiNuovi": nuovi, "duplicatiEvitati": duplicati,
        "eventiCerignola": by_city["Cerignola"], "eventiMovida": by_cat["Locali & Serate"],
        "concordanti": concordanti, "campioniRitardo": n, "ritardoMedianoMinuti": mediana_ritardo,
    }
    stato = memoria.setdefault("apprendimento", {})
    precedente = stato.get("qualita", [])
    ultimo_giorno = [c for c in precedente if now - c["timestamp"] <= 86400]
    confronto = {}
    for chiave in ("fontiAttive", "eventiNuovi", "eventiCerignola", "eventiMovida"):
        if ultimo_giorno:
            confronto[chiave] = round(sum(v[chiave] for v in ultimo_giorno) / len(ultimo_giorno), 2)
    anomalie = [
        chiave for chiave in ("fontiAttive", "eventiCerignola", "eventiMovida")
        if len(ultimo_giorno) >= 6 and confronto[chiave] >= 4 and misure[chiave] < confronto[chiave] * 0.5
    ]
    stato["qualita"] = (precedente + [misure])[-336:]
    return {
        **misure, "scartiSchede": dict(scarti), "perComune": dict(by_city),
        "perCategoria": dict(by_cat), "media24Ore": confronto, "anomalie": anomalie,
    }
