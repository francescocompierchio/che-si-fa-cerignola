"""Guardiano leggero: osserva il sito e recupera soltanto raccolte mancate.
Non corregge il codice, non pubblica dati e non annulla esecuzioni."""
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

def data(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z","+00:00"))
    except (TypeError,ValueError):
        return None

def decisione(runs,now):
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
    if now-timestamp < SOGLIA:
        return "raccolta_recente"
    if latest.get("conclusion") not in {"success","cancelled"}:
        return "errore_da_diagnosticare"
    return "recupera"

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

def main():
    now=datetime.now(timezone.utc)
    note=[]
    try:
        stats=verifica_archivio()
        note.append("Archivio pubblico raggiungibile e JSON valido: "+json.dumps(stats,ensure_ascii=False))
    except (URLError,ValueError,TimeoutError,OSError) as exc:
        note.append("Attenzione: archivio pubblico non verificabile ("+type(exc).__name__+"). Nessuna cancellazione.")
    try:
        stato=api(WORKFLOW)
        if stato.get("state")!="active":
            note.append("Raccolta non attiva: non riattivo un workflow disabilitato.")
        else:
            runs=api(WORKFLOW+"/runs?branch=main&per_page=30").get("workflow_runs",[])
            action=decisione(runs,now)
            note.append("Stato raccolta: "+action)
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
    message="## Guardiano tecnico Che Si Fa\n\n"+"\n".join("- "+x for x in note)+"\n\nLe metriche non includono Firebase o eventi editoriali. Nessuna modifica al sito."
    print(message)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f:
            f.write(message+"\n")

if __name__=="__main__":
    main()
