"""Guardiano leggero: osserva il sito e recupera soltanto raccolte mancate.
Non corregge il codice, non pubblica dati e non annulla esecuzioni.
Rende visibili gli errori ripetuti e recupera timeout programmati dopo la soglia."""
import json
import os
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError
from pathlib import Path

ATTIVI={"queued","in_progress","pending","waiting","requested"}
SOGLIA=timedelta(minutes=90)
REPO="francescocompierchio/che-si-fa-cerignola"
BASE="https://api.github.com/repos/"+REPO
SITE="https://francescocompierchio.github.io/che-si-fa-cerignola/"
WORKFLOW="/actions/workflows/aggiorna-eventi.yml"
COMMUNITY="/actions/workflows/community-moderazione.yml"
SOGLIA_COMMUNITY=timedelta(minutes=25)

def data(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z","+00:00"))
    except (TypeError,ValueError):
        return None

def decisione(runs,now,soglia=SOGLIA):
    """Niente recupero se esiste attività, errore non diagnosticato o storico incerto."""
    if not runs or not isinstance(runs,list):
        return "storico_insufficiente"
    if any(r.get("status") in ATTIVI for r in runs):
        return "raccolta_attiva"
    if any(r.get("status")!="completed" for r in runs):
        return "stato_incerto"
    latest=max(runs,key=lambda r:r.get("created_at",""))
    timestamp=data(latest.get("updated_at") or latest.get("created_at"))
    if not timestamp or timestamp.tzinfo is None:
        return "stato_incerto"
    esito=latest.get("conclusion")
    if esito not in {"success","cancelled","timed_out"}:
        return "errore_da_diagnosticare"
    if now-timestamp < soglia:
        return "raccolta_recente"
    if esito=="timed_out":
        # Un solo recupero di un timeout programmato; mai ripetere un dispatch
        # fallito o mascherare errori di test e validazione.
        if latest.get("event")!="schedule":
            return "errore_da_diagnosticare"
        return "recupera"
    return "recupera"

def allarmi_raccolta(runs,now):
    completati=sorted((r for r in runs if r.get("status")=="completed"),
                     key=lambda r:r.get("created_at",""),reverse=True)
    rilevanti=[r for r in completati if r.get("conclusion")!="cancelled"]
    if len(rilevanti)>=2 and all(r.get("conclusion")!="success" for r in rilevanti[:2]):
        return "Due raccolte consecutive non riuscite: controllare i log."
    successi=[data(r.get("updated_at") or r.get("created_at")) for r in completati if r.get("conclusion")=="success"]
    successi=[t for t in successi if t is not None and t.tzinfo is not None]
    if successi and now-max(successi)>timedelta(hours=3):
        return "Nessuna raccolta riuscita nelle ultime tre ore."
    return ""

def api(path,body=None):
    headers={"Accept":"application/vnd.github+json","Authorization":"Bearer "+os.environ["GH_TOKEN"],"User-Agent":"CheSiFa-Guardiano"}
    request=Request(BASE+path,headers=headers,data=json.dumps(body).encode() if body is not None else None,method="POST" if body is not None else "GET")
    if body is not None:
        request.add_header("Content-Type","application/json")
    with urlopen(request,timeout=15) as r:
        raw=r.read(2_000_000)
        return json.loads(raw) if raw else {}

def verifica_archivio():
    request=Request(SITE+"eventi.json",headers={"User-Agent":"CheSiFa-Guardiano","Cache-Control":"no-cache"})
    with urlopen(request,timeout=15) as r:
        if r.status!=200:
            raise ValueError("HTTP non riuscito")
        rows=json.loads(r.read(5_000_000))
    if not isinstance(rows,list) or any(not isinstance(x,dict) for x in rows):
        raise ValueError("Archivio non valido")
    oggi=datetime.now(timezone.utc).date().isoformat()
    eventi=[x for x in rows if x.get("tipoContenuto")=="evento" and x.get("dataFine",x.get("dataInizio",""))>=oggi]
    return {"eventi":len(eventi),"cerignola":sum(x.get("citta")=="Cerignola" for x in eventi),"serateCerignola":sum(x.get("citta")=="Cerignola" and x.get("categoria")=="Locali & Serate" for x in eventi)}

def verifica_community(now,note,allarmi):
    stato=api(COMMUNITY)
    if stato.get("state")!="active":
        allarmi.append("Moderazione Community non attiva: nessuna riattivazione automatica.")
        return
    def storico():
        return [r for r in api(COMMUNITY+"/runs?branch=main&per_page=30").get("workflow_runs",[]) if r.get("event") in ("schedule","push","workflow_dispatch")]
    azione=decisione(storico(),now,SOGLIA_COMMUNITY)
    note.append("Stato moderazione Community: "+azione)
    if azione in {"errore_da_diagnosticare","storico_insufficiente","stato_incerto"}:
        allarmi.append("Moderazione Community da verificare: nessun bypass.")
    if azione=="recupera" and os.environ.get("GITHUB_EVENT_NAME")=="schedule":
        if decisione(storico(),datetime.now(timezone.utc),SOGLIA_COMMUNITY)=="recupera":
            api(COMMUNITY+"/dispatches",{"ref":"main"})
            note.append("Moderazione di recupero richiesta, filtri invariati.")

def main():
    now=datetime.now(timezone.utc)
    note=[]
    allarmi=[]
    try:
        stats=verifica_archivio()
        note.append("Archivio pubblico raggiungibile e JSON valido: "+json.dumps(stats,ensure_ascii=False))
    except (URLError,ValueError,TimeoutError,OSError) as exc:
        note.append("Attenzione: archivio pubblico non verificabile ("+type(exc).__name__+"). Nessuna cancellazione.")
        allarmi.append("Archivio pubblico non verificabile.")
    try:
        stato=api(WORKFLOW)
        if stato.get("state")!="active":
            note.append("Raccolta non attiva: non riattivo un workflow disabilitato.")
            allarmi.append("Workflow di raccolta non attivo.")
        else:
            runs=api(WORKFLOW+"/runs?branch=main&per_page=30").get("workflow_runs",[])
            action=decisione(runs,now)
            note.append("Stato raccolta: "+action)
            avviso=allarmi_raccolta(runs,now)
            if avviso:
                allarmi.append(avviso)
            if action=="recupera" and os.environ.get("GITHUB_EVENT_NAME")=="schedule":
                # Ricontrolla immediatamente prima del dispatch; niente replay di vecchi commit.
                runs=api(WORKFLOW+"/runs?branch=main&per_page=30").get("workflow_runs",[])
                if decisione(runs,datetime.now(timezone.utc))=="recupera":
                    api(WORKFLOW+"/dispatches",{"ref":"main","inputs":{"forza_fonti":"false"}})
                    note.append("Raccolta di recupero richiesta sul main corrente; le pause delle fonti restano rispettate.")
            elif action=="recupera":
                note.append("Modalità verifica: nessuna raccolta avviata.")
    except (URLError,ValueError,TimeoutError,OSError,KeyError) as exc:
        note.append("Stato GitHub non verificabile ("+type(exc).__name__+"): nessun recupero forzato.")
        allarmi.append("Stato della raccolta non verificabile.")
    try:
        verifica_community(now,note,allarmi)
    except (URLError,ValueError,TimeoutError,OSError,KeyError) as exc:
        allarmi.append("Stato Community non verificabile ("+type(exc).__name__+").")
    note.extend("ALLARME: "+x for x in allarmi)
    message="## Guardiano tecnico Che Si Fa\n\n"+"\n".join("- "+x for x in note)+"\n\nLe metriche non includono Firebase o eventi editoriali. Nessuna modifica al sito."
    print(message)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f:
            f.write(message+"\n")
    if allarmi:
        for avviso in allarmi:
            print("::error::"+avviso)
        raise SystemExit(1)

if __name__=="__main__":
    main()
