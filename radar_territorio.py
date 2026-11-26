"""Registro territoriale costruito da eventi verificati e fonti pubbliche."""
from collections import Counter
from datetime import date, timedelta
from hashlib import sha256
from urllib.parse import urlencode, urlsplit
import json
import re

import requests

ENDPOINT_APPROVATI = "https://chesifa-cerignola-default-rtdb.europe-west1.firebasedatabase.app/eventiManuali.json"
CAMPIONI_FIREBASE = 40
MAX_FIREBASE_BYTES = 96 * 1024
COMUNI_MOVIDA = (
    "Cerignola", "Stornara", "Stornarella", "Orta Nova", "San Ferdinando di Puglia",
    "Canosa di Puglia", "Trinitapoli", "Margherita di Savoia", "Foggia",
    "Barletta", "Trani", "Andria", "Manfredonia", "Bisceglie",
)
FORMATI = (
    '("dj set" OR discoteca OR "opening party")',
    '("cena spettacolo" OR "dinner show" OR apericena OR karaoke)',
    '("musica dal vivo" OR "serata latina" OR "live music")',
    '("festa con ingresso" OR "festa aperta al pubblico" OR "serata a tema")',
)
FORMATI_GIORNO = (
    '(mercatino OR sagra OR "street food" OR degustazione)',
    '(trekking OR "escursione guidata" OR passeggiata)',
    '("laboratorio per bambini" OR "fattoria didattica" OR "attività per famiglie")',
    '("visita guidata" OR "attività ricreative" OR "workshop creativo")',
    '(concerto OR spettacolo OR cabaret)',
)


def leggi_approvati(valida, oggi, session=requests):
    """Legge la stessa collezione pubblicata nel sito, con un limite di rete."""
    try:
        with session.get(
            ENDPOINT_APPROVATI, params={"orderBy": '"$key"', "limitToLast": CAMPIONI_FIREBASE},
            timeout=(3, 6), allow_redirects=False, stream=True,
        ) as risposta:
            if risposta.status_code != 200:
                return [], f"HTTP {risposta.status_code}"
            body = bytearray()
            for chunk in risposta.iter_content(8192):
                body.extend(chunk)
                if len(body) > MAX_FIREBASE_BYTES:
                    return [], "risposta oltre il limite"
        raw = json.loads(body)
        if raw is None:
            return [], "ok"
        if not isinstance(raw, dict):
            return [], "formato inatteso"
    except (requests.RequestException, ValueError):
        return [], "indisponibile"
    out = []
    for record in list(raw.values())[:CAMPIONI_FIREBASE]:
        if not isinstance(record, dict) or not isinstance(record.get("dataInizio"), str):
            continue
        campi = ("titolo", "citta", "categoria", "luogo", "dataInizio", "dataFine", "fonteUrl")
        if not all(isinstance(record.get(k, ""), str) and len(record.get(k, "")) <= 800 for k in campi):
            continue
        try:
            fine = date.fromisoformat(record.get("dataFine") or record["dataInizio"])
        except ValueError:
            continue
        if oggi <= fine <= oggi + timedelta(days=180):
            verificato = valida({k: record.get(k, "") for k in campi})
            if verificato:
                out.append(verificato)
    return out, "ok"


def nome_locale(value):
    value = " ".join(re.sub(r'[^\w\s&.\-’]', " ", str(value or "")).split()).strip(" .-")
    return value if 4 <= len(value) <= 80 and not re.search(r"\d{5}|https?|@",
        value, re.I) and sum(c.isalpha() for c in value) >= 4 else ""


def host_pubblico(url):
    try:
        pr = urlsplit(url or "")
        host = (pr.hostname or "").removeprefix("www.")
    except ValueError:
        return ""
    if pr.scheme != "https" or pr.username or pr.password or not re.fullmatch(r"[a-z0-9][a-z0-9.-]+\.[a-z]{2,24}", host):
        return ""
    return host


def aggiorna_registro(memoria, eventi, approvati, oggi, ora):
    """Ricorda sedi, argomenti e domini osservati. Conta ogni appuntamento una volta."""
    stato = memoria.setdefault("territorio", {})
    registro = stato.setdefault("organizzatori", {})
    soglia = (oggi - timedelta(days=90)).isoformat()
    for ev, approvato in [(e, False) for e in eventi] + [(e, True) for e in approvati]:
        citta, luogo = ev.get("citta", ""), nome_locale(ev.get("luogo"))
        inizio = ev.get("dataInizio", "")
        if not luogo or not citta or luogo.casefold() == citta.casefold() or inizio < soglia:
            continue
        chiave = f"{citta}/{luogo.casefold()}"
        voce = registro.setdefault(chiave, {"citta": citta, "luogo": luogo, "eventi": {}, "domini": {}})
        voce["ultimoRiscontro"] = ora
        titolo = str(ev.get("titolo") or "").casefold()
        id_evento = sha256(f"{inizio}|{titolo}".encode()).hexdigest()[:20]
        voce["eventi"][id_evento] = {"data": inizio, "categoria": ev.get("categoria", "")}
        host = host_pubblico(ev.get("fonteUrl"))
        if host:
            fonte = voce["domini"].setdefault(host, {})
            fonte["ultimoRiscontro"] = ora
            if approvato:
                fonte["presenteInEventoApprovato"] = True
    for voce in registro.values():
        voce["eventi"] = dict(sorted(
            ((k, v) for k, v in voce["eventi"].items() if v["data"] >= soglia),
            key=lambda kv: (kv[1]["data"], kv[0]),
        )[-24:])
        voce["categorie"] = dict(Counter(e["categoria"] for e in voce["eventi"].values()))
        voce["domini"] = dict(sorted(
            voce["domini"].items(), key=lambda kv: (kv[1].get("presenteInEventoApprovato", False), kv[1]["ultimoRiscontro"], kv[0]),
            reverse=True,
        )[:6])
    ordinati = sorted(
        ((k, v) for k, v in registro.items() if v["eventi"] and ora - v["ultimoRiscontro"] <= 90 * 86400),
        key=lambda kv: (kv[1]["citta"] != "Cerignola", -kv[1]["categorie"].get("Locali & Serate", 0), -kv[1]["ultimoRiscontro"], kv[0]),
    )
    stato["organizzatori"] = dict(ordinati[:200])
    return stato


def query(nome, termini, comune, *, movida=False):
    return {
        "nome": nome,
        "url": "https://news.google.com/rss/search?" + urlencode(
            {"q": termini + " when:30d", "hl": "it", "gl": "IT", "ceid": "IT:it"}
        ),
        "solo_cerignola": comune == "Cerignola", "comune_radar": comune,
        "prioritaria": comune == "Cerignola", "focus_serate": movida, "nightlife": movida,
        "max_schede_rss": 3, "origini_note": True,
    }


def ricerche(memoria, eventi, oggi, priorita_km, comuni):
    """Tre slot limitati guidati dalla copertura e dal rendimento storico."""
    stato = memoria.get("territorio", {})
    registro = stato.get("organizzatori", {})
    ciclo = memoria.get("apprendimento", {}).get("cicli", 0)
    fine = (oggi + timedelta(days=14)).isoformat()
    copertura = Counter(
        (ev.get("citta"), ev.get("categoria")) for ev in eventi
        if ev.get("dataInizio", "") <= fine and ev.get("dataFine", "") >= oggi.isoformat()
    )
    movida = "Locali & Serate"
    parole = FORMATI[ciclo % len(FORMATI)]
    # Alterna la prima cintura e i comuni principali, mantenendo la ricerca locale dedicata.
    distanza = 1 if ciclo % 3 != 2 else 2
    zona = [c for c in COMUNI_MOVIDA if c != "Cerignola" and priorita_km(c) == distanza]
    territori = zona or list(COMUNI_MOVIDA[1:])
    carente = min(territori, key=lambda c: (copertura[c, movida], (territori.index(c) - ciclo) % len(territori)))
    ricerche = [query(f"Movida territoriale {carente} {ciclo % len(FORMATI) + 1}", f'"{carente}" {parole}', carente, movida=True)]
    organizzatori = [v for v in registro.values() if v["categorie"].get(movida, 0) >= 2
                     or any(f.get("presenteInEventoApprovato") for f in v["domini"].values())]
    if organizzatori:
        vicini = [v for v in organizzatori if v["citta"] == "Cerignola"] or organizzatori
        scelto = vicini[ciclo % len(vicini)]
        luogo, citta = scelto["luogo"], scelto["citta"]
        ricerche.append(query(f"Ricerca locale {citta} / {luogo}", f'"{citta}" "{luogo}" {parole}', citta, movida=True))
    categorie = ("Sagre & Food", "Natura & Escursioni", "Famiglie & Bambini", "Attività diurne", "Teatro & Spettacoli")
    # Ruota anche i comuni minori del bacino e usa categorie con poca copertura.
    candidati = sorted(c for c in comuni if priorita_km(c) == distanza)
    if candidati:
        comune = candidati[(ciclo // 2) % len(candidati)]
        indice = min(range(len(categorie)), key=lambda i: (copertura[comune, categorie[i]], (i - ciclo) % len(categorie)))
        ricerche.append(query(f"Svago territoriale {comune} {categorie[indice]}", f'"{comune}" {FORMATI_GIORNO[indice]}', comune))
    return ricerche


def leggi_evento_editoriale(record, comuni, oggi):
    comune = record["citta"].strip()
    luogo = nome_locale(record["luogo"])
    titolo = record["titolo"].strip()[:120]
    if comune not in comuni or not luogo or len(titolo) < 5:
        return None
    try:
        inizio = date.fromisoformat(record["dataInizio"])
        fine = date.fromisoformat(record["dataFine"] or record["dataInizio"])
    except ValueError:
        return None
    if inizio > fine or fine < oggi or inizio < oggi - timedelta(days=90):
        return None
    return {
        "tipoContenuto": "evento", "citta": comune, "luogo": luogo, "titolo": titolo,
        "categoria": record["categoria"], "dataInizio": inizio.isoformat(),
        "dataFine": fine.isoformat(), "fonteUrl": record["fonteUrl"],
    }
