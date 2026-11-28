"""Registro territoriale costruito da eventi verificati e fonti pubbliche."""
from collections import Counter
from datetime import date, timedelta
from hashlib import sha256
from urllib.parse import urlencode, urlsplit
import json
import re

import requests

import apprendimento

ENDPOINT_APPROVATI = "https://chesifa-cerignola-default-rtdb.europe-west1.firebasedatabase.app/eventiManuali.json"
CAMPIONI_FIREBASE = 40
MAX_FIREBASE_BYTES = 96 * 1024
MOVIDA = "Locali & Serate"
FASCE = ("Cerignola", "Entro 25 km", "Tra 25 e 50 km")


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


def eventi_nella_finestra(eventi, oggi, comuni):
    inizio = oggi.isoformat()
    fine = (oggi + timedelta(days=14)).isoformat()
    return [
        e for e in eventi if e.get("citta") in comuni and e.get("categoria") in apprendimento.AREE
        and inizio <= (e.get("dataFine") or e.get("dataInizio") or "")
        and "" < (e.get("dataInizio") or "") <= fine
    ]


def ricerche(memoria, eventi, oggi, priorita_km, comuni, registro_locali=None):
    """Uguali categorie e regole di ricerca, con un massimo di 3, 2, 1 query."""
    territorio = memoria.get("territorio", {})
    ultimo = territorio.get("ultimeRicerche", {})
    verifica = territorio.get("ultimaVerificaCopertura", {})
    fasce_precedenti = verifica.get("fasce", {})
    ciclo = int(memoria.get("apprendimento", {}).get("cicli", 0))
    copertura = Counter((e["citta"], e["categoria"]) for e in eventi_nella_finestra(eventi, oggi, comuni))
    altre = [categoria for categoria in apprendimento.AREE if categoria != MOVIDA]
    comuni_per_fascia = {i: sorted(c for c in comuni if priorita_km(c) == i) for i in range(len(FASCE))}
    slot = [(0, MOVIDA), (0, MOVIDA), (0, None), (1, MOVIDA), (1, None),
            (2, None if ciclo % 3 == 2 else MOVIDA)]
    fonti = []
    for fascia, categoria in slot:
        localita = comuni_per_fascia[fascia]
        if not localita:
            continue
        if categoria is None:
            riscontri = fasce_precedenti.get(FASCE[fascia], {}).get("categorie", {})
            def priorita_categoria(area):
                ultima = max(ultimo.get(c, {}).get(area, 0) for c in localita)
                mancanti = riscontri.get(area, {}).get("senzaRiscontroAutomatico", 0)
                return (ultima, -mancanti, sum(copertura[c, area] for c in localita),
                        (altre.index(area) - ciclo) % len(altre))
            categoria = min(altre, key=priorita_categoria)
        comune = min(localita, key=lambda c: (ultimo.get(c, {}).get(categoria, 0),
                                             copertura[c, categoria], (localita.index(c) - ciclo) % len(localita)))
        prefisso = f"Apprendimento {comune} - "
        variante = apprendimento.variante(memoria, categoria, ciclo, prefisso)
        termini = apprendimento.AREE[categoria][variante]
        nome = f"{prefisso}{categoria} {variante + 1}"
        if any(f["nome"] == nome for f in fonti):
            # Il secondo slot di Cerignola cerca anche le sedi ricorrenti o approvate.
            # Anche i locali senza storico meritano un turno. L'anagrafica è solo
            # un indizio di ricerca, mai una prova che esista una serata.
            luoghi = {v["luogo"] for v in territorio.get("organizzatori", {}).values()
                      if v["citta"] == comune and (v["categorie"].get(MOVIDA, 0) >= 2
                      or any(d.get("presenteInEventoApprovato") for d in v["domini"].values()))}
            if comune == "Cerignola":
                luoghi.update(nome_locale(v.get("nome")) for v in (registro_locali or [])
                              if isinstance(v, dict) and v.get("gruppo") == "movida")
            luoghi = sorted({nome_locale(v) for v in luoghi} - {""})
            if luoghi:
                ultimi_locali = territorio.get("ultimeRicercheLocali", {})
                def ordine_locale(v):
                    k = f"{comune}/{v.casefold()}"
                    attivi = sum(1 for e in eventi_nella_finestra(eventi, oggi, comuni)
                                 if e["citta"] == comune and e["categoria"] == MOVIDA
                                 and nome_locale(e.get("luogo")).casefold() == v.casefold())
                    return (ultimi_locali.get(k, 0), attivi, (luoghi.index(v) - ciclo) % len(luoghi))
                luogo = min(luoghi, key=ordine_locale)
                nome = f"Ricerca locale {comune} / {luogo}"
                # Termini meno restrittivi: il validatore originale verifica data, sede e pertinenza.
                termini = f'"{luogo}" (serata OR evento OR party OR dj OR karaoke OR aperitivo OR live OR concerto)'
            else:
                variante = (variante + 1 + ciclo % 2) % len(apprendimento.AREE[categoria])
                nome = f"{prefisso}{categoria} {variante + 1}"
                termini = apprendimento.AREE[categoria][variante]
        fonte = query(nome, f'"{comune}" {termini}', comune, movida=categoria == MOVIDA)
        if nome.startswith("Ricerca locale "):
            fonte["locale_radar"] = luogo
        fonti.append(dict(fonte, fascia_copertura=fascia, categoria_cercata=categoria))
    return fonti


def registra_ricerche(memoria, fonti, diagnostica, ora):
    territorio = memoria.setdefault("territorio", {})
    ultimo = territorio.setdefault("ultimeRicerche", {})
    ultimi_locali = territorio.setdefault("ultimeRicercheLocali", {})
    risultati = []
    for fonte in fonti:
        comune, categoria = fonte["comune_radar"], fonte["categoria_cercata"]
        dati = diagnostica.get(fonte["nome"], {})
        esito = dati.get("stato", "non_eseguita")
        if esito not in ("pausa", "non_eseguita"):
            ultimo.setdefault(comune, {})[categoria] = ora
            if fonte.get("locale_radar"):
                ultimi_locali[f"{comune}/{fonte['locale_radar'].casefold()}"] = ora
        risultati.append({"fascia": FASCE[fonte["fascia_copertura"]], "comune": comune,
                          "categoria": categoria, "fonte": fonte["nome"], "esito": esito,
                          "eventiEstratti": dati.get("eventiEstratti", 0)})
    territorio["ultimeRicercheLocali"] = dict(sorted(ultimi_locali.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)[:300])
    return risultati


def misura_fasce(visibili, automatici, riferimenti, oggi, comuni, priorita_km, duplicati):
    """Confronta il campione di riferimento con le schede automatiche dei prossimi 14 giorni."""
    out = {
        nome: {
            "comuni": sum(priorita_km(c) == i for c in comuni),
            "categorie": {
                area: {"visibili": 0, "automatici": 0, "riferimenti": 0,
                       "conRiscontroAutomatico": 0, "senzaRiscontroAutomatico": 0}
                for area in apprendimento.AREE
            },
        }
        for i, nome in enumerate(FASCE)
    }

    def cella(ev):
        return out[FASCE[priorita_km(ev["citta"])]]["categorie"][ev["categoria"]]

    def intervallo(ev):
        inizio = ev["dataInizio"]
        return ev["citta"], inizio, ev.get("dataFine") or inizio

    for ev in eventi_nella_finestra(visibili, oggi, comuni):
        cella(ev)["visibili"] += 1
    indice = {}
    for ev in eventi_nella_finestra(automatici, oggi, comuni):
        schede = indice.setdefault(intervallo(ev), [])
        if not any(duplicati(ev, e) for e in schede):
            schede.append(ev)
            cella(ev)["automatici"] += 1
    for ev in eventi_nella_finestra(riferimenti, oggi, comuni):
        info = cella(ev)
        info["riferimenti"] += 1
        schede = indice.get(intervallo(ev), ())
        campo = "conRiscontroAutomatico" if any(duplicati(ev, e) for e in schede) else "senzaRiscontroAutomatico"
        info[campo] += 1
    return out


def scegli_schede_imminenti(candidati, massimo, slot):
    """Candidati come (fascia, data, URL), con rotazione fra schede dello stesso giorno."""
    per_fascia = {i: [] for i in range(len(FASCE))}
    for fascia, giorno, url in sorted(set(candidati)):
        per_fascia[fascia].append((giorno, url))
    ordinati = {}
    for fascia, schede in per_fascia.items():
        per_giorno = {}
        for giorno, url in schede:
            per_giorno.setdefault(giorno, []).append(url)
        ordinati[fascia] = []
        for giorno, urls in per_giorno.items():
            inizio = slot % len(urls)
            ordinati[fascia].extend((giorno, url) for url in urls[inizio:] + urls[:inizio])
    quote = Counter((0, 1, 0, 2, 0, 1, 0, 2, 0, 1)[i % 10] for i in range(massimo))
    scelti = [(fascia, url) for fascia, schede in ordinati.items() for _, url in schede[:quote[fascia]]]
    eccedenza = [(giorno, fascia, url) for fascia, schede in ordinati.items() for giorno, url in schede[quote[fascia]:]]
    scelti.extend((fascia, url) for _, fascia, url in sorted(eccedenza, key=lambda x: x[:2])[:massimo - len(scelti)])
    return scelti


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
