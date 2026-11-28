"""Memoria operativa locale, ripristinabile fra i cicli senza scrivere nel sito."""
import json
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timezone
import apprendimento

def carica(path):
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and isinstance(d.get("fonti"), dict) else {"fonti": {}}
    except (OSError, ValueError, TypeError):
        return {"fonti": {}}

def fonte_locale(f):
    return bool(f.get("prioritaria") or f.get("solo_cerignola") or f.get("citta_default")=="Cerignola")

def fonte_serale(f):
    return bool(f.get("focus_serate") or f.get("nightlife") or f.get("cene_show"))

def dominio(fonte):
    return (fonte.get("dominio") or urlparse(fonte.get("url", "")).hostname or "").lower().removeprefix("www.")


def pianifica(compiti, memoria, now, forza=False, priorita_km=None):
    attivi, pause = [], []
    for task in compiti:
        fonte = task[1]
        nome = fonte["nome"]
        dati = memoria.get("fonti", {}).get(nome, {})
        limite_dominio = memoria.get("limitiDomini", {}).get(dominio(fonte), 0)
        pausa_tecnica = dati.get("blocchiConsecutivi", 0) >= 2 or dati.get("erroriConsecutivi", 0) >= 2
        scadenza = dati.get("prossimoTentativo", 0)
        if limite_dominio > now or (scadenza > now and (pausa_tecnica or (not forza and not fonte_locale(fonte)))):
            pause.append(nome)
        else:
            attivi.append(task)

    def priorita(task):
        f = task[1]
        dati = memoria.get("fonti", {}).get(f["nome"], {})
        comune = f.get("citta_default") or f.get("comune_radar") or f.get("comune_capodanno")
        distanza = 0 if fonte_locale(f) else priorita_km(comune) if comune and priorita_km else 2
        gruppo = (0 if fonte_locale(f) else 1) if fonte_serale(f) else (2 if fonte_locale(f) else 3)
        valore = dati.get("valoreAppreso", dati.get("produttivita", 0)) + apprendimento.bonus_temporale(dati, now)
        return (gruppo, distanza, -valore)

    attivi.sort(key=priorita)
    return attivi, pause

def aggiorna(memoria, diagnostica, now):
    fonti = memoria.setdefault("fonti", {})
    limiti = {host: fino for host, fino in memoria.get("limitiDomini", {}).items() if fino > now}
    for nome, dati in diagnostica.items():
        if dati.get("stato") == "pausa":
            continue
        prima = fonti.get(nome, {})
        stato = dati.get("stato")
        blocco = stato in {"HTTP 401", "HTTP 403", "HTTP 429"}
        errore = stato in {"errore", "HTTP 404", "HTTP 410", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504"}
        serie = prima.get("blocchiConsecutivi", 0) + 1 if blocco else 0
        errori = prima.get("erroriConsecutivi", 0) + 1 if errore else 0
        host = dati.get("dominio")
        if stato == "HTTP 429" and host:
            limiti[host] = max(limiti.get(host, 0), now + max(3600, dati.get("riprovaDopoSecondi", 0)))
        # Non confondere un sito senza eventi con un sito irraggiungibile.
        vuoti = prima.get("cicliVuoti", 0) + 1 if dati.get("stato") == "ok" and not dati.get("eventiEstratti", 0) else 0
        # Primo blocco: nuova prova al ciclo successivo. Poi 1, 2, 4, max 6 ore.
        pausa = min(21600, 3600 * 2 ** min(serie - 2, 3)) if serie >= 2 else 0
        if errori >= 2:
            base = 21600 if stato in {"HTTP 404", "HTTP 410"} else 3600
            pausa = min(86400, base * 2 ** min(errori - 2, 4))
        # Dopo 8 cicli senza eventi: 1h, poi 2h, massimo 4h; mai per Cerignola prioritaria.
        if not pausa and not dati.get("prioritaria") and vuoti >= 8:
            pausa = min(3600 if dati.get("focus_serate") else 14400, 3600 * 2 ** min((vuoti-8)//4,2))
        utili = int(dati.get("eventiEstratti", 0))
        media = round(0.7 * prima.get("produttivita", utili) + 0.3 * utili, 2)
        # Il punteggio premia novità effettivamente pubblicate e copertura locale.
        valore = min(20, 0.15*dati.get("eventiUtili",0)+dati.get("novitaUtili",0)+2*dati.get("novitaCerignola",0)+2*dati.get("nuoveSerate",0)+4*dati.get("nuoveSerateCerignola",0))
        appreso=round(0.8*prima.get("valoreAppreso",valore)+0.2*valore,3)
        fonti[nome] = {"fasce":apprendimento.profilo_temporale(prima,dati,now),"valoreAppreso":appreso,"novitaUtili":dati.get("novitaUtili",0),"ultimoTentativo": now, "ultimoEsito": dati.get("stato", "n/d"),
                       "blocchiConsecutivi": serie, "erroriConsecutivi": errori, "cicliVuoti": vuoti,
                       "successi": prima.get("successi", 0) + (stato == "ok"),
                       "dominio": dati.get("dominio", ""), "tipologia": dati.get("tipologia", ""),
                       "comune": dati.get("comuneFonte", ""),
                       "totaleEventiUtili": prima.get("totaleEventiUtili", 0) + dati.get("eventiUtili", 0),
                       "totaleNovita": prima.get("totaleNovita", 0) + dati.get("novitaUtili", 0),
                       "produttivita": media, "prossimoTentativo": now + pausa if pausa else 0,
                       "tentativi": prima.get("tentativi", 0) + 1}
    # Le query generate hanno nomi temporanei. Scarta le voci inattive dopo tre mesi.
    memoria["fonti"] = {nome: dati for nome, dati in fonti.items() if now - dati.get("ultimoTentativo", now) <= 90 * 86400}
    memoria["limitiDomini"] = limiti
    memoria["aggiornatoAl"] = datetime.fromtimestamp(now, timezone.utc).isoformat()
    return memoria

def riepilogo(memoria, pause):
    fonti = memoria.get("fonti", {})
    return {"fontiInPausa": pause, "fontiMonitorate": len(fonti),
            "fontiBloccate": [n for n,d in fonti.items() if d.get("blocchiConsecutivi", 0) >= 2],
            "fontiDaRivedere": [n for n,d in fonti.items() if d.get("cicliVuoti", 0) >= 6],
            "produttivita": {n:d.get("produttivita", 0) for n,d in fonti.items()}}
