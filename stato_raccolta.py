"""Memoria operativa locale, ripristinabile fra i cicli senza scrivere nel sito."""
import json
from pathlib import Path
from datetime import datetime, timezone

def carica(path):
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and isinstance(d.get("fonti"), dict) else {"fonti": {}}
    except (OSError, ValueError, TypeError):
        return {"fonti": {}}

def pianifica(compiti, memoria, now, forza=False):
    attivi, pause = [], []
    for task in compiti:
        nome = task[1]["nome"]
        dati = memoria.get("fonti", {}).get(nome, {})
        prioritaria = task[1].get("prioritaria") or task[1].get("solo_cerignola") or task[1].get("citta_default")=="Cerignola"
        blocco_attivo = dati.get("blocchiConsecutivi",0)>=2
        if not forza and dati.get("prossimoTentativo", 0) > now and (blocco_attivo or not prioritaria):
            pause.append(nome)
        else:
            attivi.append(task)
    # Priorità alle fonti produttive e stagionali; ordine stabile a parità.
    attivi.sort(key=lambda t: (not bool(t[1].get("prioritaria") or t[1].get("solo_cerignola") or t[1].get("citta_default")=="Cerignola"), -memoria.get("fonti",{}).get(t[1]["nome"],{}).get("produttivita",0)))
    return attivi, pause

def aggiorna(memoria, diagnostica, now):
    fonti = memoria.setdefault("fonti", {})
    for nome, dati in diagnostica.items():
        if dati.get("stato") == "pausa":
            continue
        prima = fonti.get(nome, {})
        blocco = dati.get("stato") in {"HTTP 403", "HTTP 429"}
        serie = prima.get("blocchiConsecutivi", 0) + 1 if blocco else 0
        # Non confondere un sito senza eventi con un sito irraggiungibile.
        vuoti = prima.get("cicliVuoti", 0) + 1 if dati.get("stato") == "ok" and not dati.get("eventiEstratti", 0) else 0
        # Primo blocco: nuova prova al ciclo successivo. Poi 1, 2, 4, max 6 ore.
        pausa = min(21600, 3600 * 2 ** min(serie - 2, 3)) if serie >= 2 else 0
        # Dopo 8 cicli senza eventi: 1h, poi 2h, massimo 4h; mai per Cerignola prioritaria.
        if not pausa and not dati.get("prioritaria") and vuoti >= 8:
            pausa = min(14400, 3600 * 2 ** min((vuoti-8)//4,2))
        utili = int(dati.get("eventiEstratti", 0))
        media = round(0.7 * prima.get("produttivita", utili) + 0.3 * utili, 2)
        fonti[nome] = {"ultimoTentativo": now, "ultimoEsito": dati.get("stato", "n/d"),
                       "blocchiConsecutivi": serie, "cicliVuoti": vuoti,
                       "produttivita": media, "prossimoTentativo": now + pausa if pausa else 0,
                       "tentativi": prima.get("tentativi", 0) + 1}
    memoria["aggiornatoAl"] = datetime.fromtimestamp(now, timezone.utc).isoformat()
    return memoria

def riepilogo(memoria, pause):
    fonti = memoria.get("fonti", {})
    return {"fontiInPausa": pause, "fontiMonitorate": len(fonti),
            "fontiBloccate": [n for n,d in fonti.items() if d.get("blocchiConsecutivi", 0) >= 2],
            "fontiDaRivedere": [n for n,d in fonti.items() if d.get("cicliVuoti", 0) >= 6],
            "produttivita": {n:d.get("produttivita", 0) for n,d in fonti.items()}}
