#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CHE SI FA CERIGNOLA - motore di raccolta v2

Output:
  - eventi.json                 Eventi datati, mantenendo lo schema compatibile
                                 con la versione precedente e aggiungendo metadati.
  - luoghi_da_verificare.json   Luoghi permanenti individuati dal motore; NON pubblicati
                                 automaticamente sul sito.
  - attivita_da_verificare.json Attività/esperienze individuate; NON pubblicate
                                 automaticamente sul sito.
  - report_copertura.json      Report della raccolta e dei relativi errori.

Variabili d'ambiente richieste:
  GEMINI_API_KEY

Variabili opzionali:
  MAX_FUTURE_DAYS=120
  SEARCH_DELAY_SECONDS=3
  ENABLE_SCRAPING=1
  ENABLE_PLACES_ACTIVITIES=1
  MAX_ARTICLES_PER_SOURCE=12
  GEMINI_MODELS=gemini-3.8-flash,gemini-3.7-flash,gemini-3.5-flash

Dipendenze:
  pip install requests beautifulsoup4

NOTA:
  Il motore usa l'API Interactions di Gemini con Google Search. Se Google Search
  fallisce, la ricerca viene dichiarata fallita: non viene chiesto al modello di
  inventare una risposta senza web.
"""

import os
import re
import json
import time
import math
import logging
import tempfile
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

# -----------------------------------------------------------------------------
# CONFIGURAZIONE
# -----------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTI_FILE = os.path.join(BASE_DIR, "eventi.json")
LUOGHI_FILE = os.path.join(BASE_DIR, "luoghi_da_verificare.json")
ATTIVITA_FILE = os.path.join(BASE_DIR, "attivita_da_verificare.json")
REPORT_FILE = os.path.join(BASE_DIR, "report_copertura.json")

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MAX_FUTURE_DAYS = int(os.environ.get("MAX_FUTURE_DAYS", "120"))
SEARCH_DELAY_SECONDS = float(os.environ.get("SEARCH_DELAY_SECONDS", "3"))
ENABLE_SCRAPING = os.environ.get("ENABLE_SCRAPING", "1").strip().lower() not in {"0", "false", "no"}
ENABLE_PLACES_ACTIVITIES = os.environ.get("ENABLE_PLACES_ACTIVITIES", "1").strip().lower() not in {"0", "false", "no"}
MAX_ARTICLES_PER_SOURCE = int(os.environ.get("MAX_ARTICLES_PER_SOURCE", "12"))

GEMINI_MODELS = [
    x.strip() for x in os.environ.get(
        "GEMINI_MODELS",
        "gemini-3.8-flash,gemini-3.7-flash,gemini-3.5-flash"
    ).split(",") if x.strip()
]

INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CheSiFaCerignolaBot/2.0; +https://francescocompierchio.github.io/che-si-fa-cerignola/)",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.7",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("che-si-fa")

FONTI_EVENTI = [
    {"url": "https://www.cerignolaviva.it/eventi/", "citta": "Cerignola", "gruppo": "Capitanata"},
    {"url": "https://www.foggiatoday.it/eventi/", "citta": "Foggia", "gruppo": "Capitanata"},
    {"url": "https://www.foggiatoday.it/eventi/weekend/", "citta": "Foggia", "gruppo": "Capitanata"},
    {"url": "https://www.barlettaviva.it/eventi/", "citta": "Barletta", "gruppo": "BAT e costa"},
    {"url": "https://www.traniviva.it/eventi/", "citta": "Trani", "gruppo": "BAT e costa"},
    {"url": "https://www.bisceglieviva.it/eventi/", "citta": "Bisceglie", "gruppo": "BAT e costa"},
    {"url": "https://www.andriaviva.it/eventi/", "citta": "Andria", "gruppo": "BAT e costa"},
    {"url": "https://www.manfredonianews.it/category/eventi/", "citta": "Manfredonia", "gruppo": "Gargano"},
]

FALLBACK_URL_PER_CITTA = {
    "Cerignola": "https://www.cerignolaviva.it/eventi/",
    "Foggia": "https://www.foggiatoday.it/eventi/",
    "Barletta": "https://www.barlettaviva.it/eventi/",
    "Trani": "https://www.traniviva.it/eventi/",
    "Bisceglie": "https://www.bisceglieviva.it/eventi/",
    "Andria": "https://www.andriaviva.it/eventi/",
    "Manfredonia": "https://www.manfredonianews.it/category/eventi/",
}

# I cerchi sono fasce orientative per ordinare i risultati, non distanze stradali certificate.
CINTURA_25_KM = {
    "stornara", "stornarella", "san ferdinando", "orta nova", "trinitapoli",
    "canosa", "ordona", "carapelle", "margherita di savoia", "lavello", "ascoli satriano"
}
CINTURA_50_KM = {
    "zapponeta", "castelluccio dei sauri", "barletta", "candela", "minervino murge",
    "foggia", "melfi", "venosa", "deliceto", "rapolla", "andria", "barile",
    "palazzo san gervasio", "rocchetta sant'antonio", "sant'agata di puglia",
    "manfredonia", "rionero in vulture", "trani", "bovino", "lacedonia",
    "monticchio", "spinazzola", "monteverde", "montemilone", "atella",
    "troia", "accadia", "aquilonia", "lucera", "bisceglie"
}

COMUNI_TARGET = [
    "Cerignola", "Stornara", "Stornarella", "San Ferdinando di Puglia", "Orta Nova",
    "Trinitapoli", "Canosa di Puglia", "Ordona", "Carapelle", "Margherita di Savoia",
    "Lavello", "Ascoli Satriano", "Zapponeta", "Castelluccio dei Sauri", "Barletta",
    "Candela", "Minervino Murge", "Foggia", "Melfi", "Venosa", "Deliceto", "Rapolla",
    "Andria", "Barile", "Palazzo San Gervasio", "Rocchetta Sant'Antonio",
    "Sant'Agata di Puglia", "Manfredonia", "Rionero in Vulture", "Trani", "Bovino",
    "Lacedonia", "Monticchio", "Spinazzola", "Monteverde", "Montemilone", "Atella",
    "Troia", "Accadia", "Aquilonia", "Lucera", "Bisceglie", "Molfetta", "San Severo",
    "Vieste", "Mattinata", "Monte Sant'Angelo"
]

CITTA_ALIASES = {
    "san ferdinando": "San Ferdinando di Puglia",
    "san ferdinando di puglia": "San Ferdinando di Puglia",
    "canosa": "Canosa di Puglia",
    "canosa di puglia": "Canosa di Puglia",
    "minervino": "Minervino Murge",
    "minervino murge": "Minervino Murge",
    "rionero": "Rionero in Vulture",
    "rionero in vulture": "Rionero in Vulture",
    "laghi di monticchio": "Monticchio",
    "monte sant'angelo": "Monte Sant'Angelo",
    "sant'agata di puglia": "Sant'Agata di Puglia",
    "rocchetta sant'antonio": "Rocchetta Sant'Antonio",
    "castelluccio dei sauri": "Castelluccio dei Sauri",
    "margherita di savoia": "Margherita di Savoia",
    "palazzo san gervasio": "Palazzo San Gervasio",
}

CATEGORIE_EVENTI = [
    "Locali & Serate", "Attività serali", "Musica & Concerti", "Sagre & Food",
    "Famiglie & Bambini", "Natura & Escursioni", "Attività diurne", "Altro"
]

MAPPA_CATEGORIE = {
    "serate": "Locali & Serate", "locali": "Locali & Serate", "club": "Locali & Serate",
    "aperitivo": "Locali & Serate", "dj set": "Locali & Serate", "discoteca": "Locali & Serate",
    "attività serali": "Attività serali", "attivita serali": "Attività serali",
    "apericena": "Attività serali", "karaoke": "Attività serali", "quiz night": "Attività serali",
    "musica": "Musica & Concerti", "concerti": "Musica & Concerti", "teatro": "Musica & Concerti",
    "spettacolo": "Musica & Concerti", "cabaret": "Musica & Concerti",
    "fiera": "Sagre & Food", "sagra": "Sagre & Food", "food": "Sagre & Food",
    "mercatino": "Sagre & Food", "degustazione": "Sagre & Food",
    "famiglie": "Famiglie & Bambini", "bambini": "Famiglie & Bambini", "laboratorio bambini": "Famiglie & Bambini",
    "natura": "Natura & Escursioni", "escursioni": "Natura & Escursioni", "trekking": "Natura & Escursioni",
    "passeggiata": "Natura & Escursioni", "attività diurne": "Attività diurne",
    "attivita diurne": "Attività diurne", "visita guidata": "Attività diurne",
}

# Blacklist volutamente circoscritta: evitare parole generiche come "sindaco" o "estate"
# che potrebbero far scartare un evento valido solo perché presenti nel testo.
PAROLE_ESCLUDI_TITOLO = [
    "incidente", "omicidio", "rapina", "arresto", "arresti", "cronaca", "morto", "ferito",
    "meteo", "allerta", "elezioni", "sciopero", "consiglio comunale", "indagine di mercato",
    "presentazione del libro", "presentazione libro", "convegno", "seminario", "tavola rotonda",
    "messa", "processione", "funerale", "raccolta fondi", "beneficenza"
]

STOPWORDS_IT = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "a", "da", "in",
    "con", "su", "per", "tra", "fra", "del", "dello", "della", "dei", "degli", "delle",
    "al", "allo", "alla", "ai", "agli", "alle", "dal", "dallo", "dalla", "nel", "nello",
    "nella", "sul", "sulla", "e", "ed", "o", "che", "si", "fa", "evento", "serata", "grande"
}

# Sei ricerche tematiche separate. Ogni missione chiede a Gemini di interrogare le singole
# località, non di limitarsi a una ricerca generica per tutta la provincia.
AGENTI_EVENTI = [
    {
        "id": "eventi_serate",
        "nome": "Eventi, teatro, concerti e serate",
        "categoria": "Musica & Concerti",
        "missione": "concerti, teatro, spettacoli, cabaret, musica dal vivo, DJ set, serate nei locali, aperitivi musicali, feste e appuntamenti serali"
    },
    {
        "id": "sagre_food",
        "nome": "Sagre, mercatini, feste e gastronomia",
        "categoria": "Sagre & Food",
        "missione": "sagre, mercatini, mercatini natalizi, fiere ricreative, degustazioni, feste di paese, eventi gastronomici e manifestazioni per il pubblico"
    },
    {
        "id": "famiglie",
        "nome": "Famiglie e bambini",
        "categoria": "Famiglie & Bambini",
        "missione": "laboratori per bambini, animazione, villaggi tematici, spettacoli per ragazzi, attività genitori-figli, fattorie didattiche con appuntamenti datati e iniziative per famiglie"
    },
    {
        "id": "natura",
        "nome": "Natura ed escursioni organizzate",
        "categoria": "Natura & Escursioni",
        "missione": "escursioni guidate, trekking non agonistico, passeggiate naturalistiche organizzate, visite a parchi, uscite in bicicletta ricreative e attività all'aperto con data prenotabile; escludi gare e competizioni"
    },
    {
        "id": "attivita_diurne",
        "nome": "Attività diurne ed esperienze",
        "categoria": "Attività diurne",
        "missione": "visite guidate, laboratori, esperienze artigianali, degustazioni, visite in azienda, attività per adulti, mercati tematici, aperture speciali e iniziative diurne con date o disponibilità verificabili"
    },
]

AGENTE_LUOGHI = {
    "id": "luoghi_permanenti",
    "nome": "Luoghi permanenti da visitare",
    "missione": (
        "luoghi visitabili o fruibili nel tempo libero: parchi, laghi, riserve, aree naturalistiche, "
        "percorsi, borghi, castelli, siti archeologici, musei, fattorie didattiche, masserie e punti "
        "panoramici. Cerca luoghi reali, non eventi temporanei."
    )
}

AGENTE_ATTIVITA = {
    "id": "attivita_permanenti",
    "nome": "Attività ed esperienze disponibili su prenotazione",
    "missione": (
        "esperienze prenotabili o ricorrenti: agriturismi con attività, fattorie didattiche, laboratori, "
        "degustazioni, visite guidate disponibili regolarmente, tour, attività per famiglie e noleggi "
        "ricreativi. Non inventare disponibilità, prezzi o orari."
    )
}

# -----------------------------------------------------------------------------
# FUNZIONI GENERALI
# -----------------------------------------------------------------------------


def now_local():
    # GitHub Actions usa normalmente UTC: si imposta il fuso Europe/Rome quando disponibile.
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Rome")).replace(tzinfo=None)
    except Exception:
        return datetime.now()


def oggi_iso():
    return now_local().strftime("%Y-%m-%d")


def limite_futuro_iso(giorni=None):
    giorni = MAX_FUTURE_DAYS if giorni is None else giorni
    return (now_local() + timedelta(days=giorni)).strftime("%Y-%m-%d")


def leggi_json(percorso, default=None):
    if default is None:
        default = []
    try:
        with open(percorso, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception as exc:
        log.warning("Impossibile leggere %s: %s", percorso, exc)
        return default


def scrivi_json_atomico(percorso, dati):
    os.makedirs(os.path.dirname(percorso) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="tmp_", suffix=".json", dir=os.path.dirname(percorso) or ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dati, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, percorso)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def normalizza_testo(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalizza_url(url):
    url = normalizza_testo(url)
    if not url.startswith(("http://", "https://")):
        return ""
    try:
        p = urlparse(url)
        if not p.netloc:
            return ""
        # Rimuove parametri di tracciamento ma conserva gli altri parametri funzionali.
        query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
        return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path or "/", p.params, urlencode(query), ""))
    except Exception:
        return ""


def dominio_stesso(url_a, url_b):
    try:
        a = (urlparse(url_a).hostname or "").lower().removeprefix("www.")
        b = (urlparse(url_b).hostname or "").lower().removeprefix("www.")
        return bool(a and b and (a == b or a.endswith("." + b) or b.endswith("." + a)))
    except Exception:
        return False


def priorita_comune(citta):
    c = normalizza_testo(citta).lower()
    if c == "cerignola":
        return 0
    # Varianti canoniche che la normalizzazione città usa nei JSON.
    fascia_25 = CINTURA_25_KM | {"san ferdinando di puglia", "canosa di puglia"}
    fascia_50 = CINTURA_50_KM | {"minervino murge", "rionero in vulture"}
    if c in fascia_25:
        return 1
    if c in fascia_50:
        return 2
    return 3


def etichetta_fascia(citta):
    p = priorita_comune(citta)
    return ["Cerignola", "Prima cintura (fascia orientativa)", "Seconda cintura (fascia orientativa)", "Altra area / distanza da verificare"][p]


def normalizza_citta(ev, default="Cerignola"):
    raw = normalizza_testo(ev.get("citta"))
    low = raw.lower()
    if low:
        if low in CITTA_ALIASES:
            return CITTA_ALIASES[low]
        return raw.title()
    # Se il campo città manca, tenta solo una corrispondenza esplicita nei campi testuali.
    testo = " ".join(normalizza_testo(ev.get(k)) for k in ("luogo", "titolo", "descrizione")).lower()
    for alias in sorted(CITTA_ALIASES, key=len, reverse=True):
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", testo):
            return CITTA_ALIASES[alias]
    for nome in sorted(COMUNI_TARGET, key=len, reverse=True):
        if re.search(rf"(?<!\w){re.escape(nome.lower())}(?!\w)", testo):
            return nome
    return default


def normalizza_categoria(raw):
    k = normalizza_testo(raw).lower()
    if k in MAPPA_CATEGORIE:
        return MAPPA_CATEGORIE[k]
    for c in CATEGORIE_EVENTI:
        if c.lower() == k:
            return c
    return "Altro"


def parse_data(data):
    s = normalizza_testo(data)[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def estrai_ore(testo):
    s = normalizza_testo(testo)
    match = re.search(r"(?:ore\s*)?(\d{1,2})[:.](\d{2})", s, re.IGNORECASE)
    if not match:
        return ""
    h, m = int(match.group(1)), int(match.group(2))
    return f"{h:02d}:{m:02d}" if 0 <= h <= 23 and 0 <= m <= 59 else ""


def evento_valido(ev):
    oggi = now_local().date()
    max_data = (now_local() + timedelta(days=MAX_FUTURE_DAYS)).date()
    titolo = normalizza_testo(ev.get("titolo"))
    descrizione = normalizza_testo(ev.get("descrizione"))
    luogo = normalizza_testo(ev.get("luogo"))
    inizio = parse_data(ev.get("dataInizio"))
    fine = parse_data(ev.get("dataFine") or ev.get("dataInizio"))
    if len(titolo) < 5 or not luogo or not inizio or not fine:
        return False
    if fine < oggi or inizio > max_data or fine < inizio:
        return False
    if not descrizione:
        ev["descrizione"] = f"Appuntamento segnalato a {ev.get('citta', 'località da verificare')}."
        ev["descrizione"] = normalizza_testo(ev["descrizione"])
    # Filtra sport competitivo/cronaca sulla base soprattutto del titolo, non di ogni parola del testo.
    titolo_low = titolo.lower()
    if any(p in titolo_low for p in PAROLE_ESCLUDI_TITOLO):
        return False
    return True


def normalizza_fonte_url(url_raw, url_ammesse):
    candidato = normalizza_url(url_raw)
    if not candidato:
        return ""
    ammesse = {normalizza_url(u) for u in url_ammesse if normalizza_url(u)}
    # Non accettare un URL semplicemente perché scritto dal modello: deve provenire dalle
    # citazioni Google Search o da una pagina effettivamente scaricata dallo scraper.
    if candidato in ammesse:
        return candidato
    return ""


def pulisci_evento(raw, default_city, url_ammesse):
    ev = dict(raw or {})
    ev["tipoContenuto"] = "evento"
    ev["citta"] = normalizza_citta(ev, default_city)
    ev["categoria"] = normalizza_categoria(ev.get("categoria"))
    ev["titolo"] = normalizza_testo(ev.get("titolo"))[:120]
    ev["luogo"] = normalizza_testo(ev.get("luogo"))[:180]
    ev["descrizione"] = normalizza_testo(ev.get("descrizione"))[:500]
    ev["dataInizio"] = normalizza_testo(ev.get("dataInizio"))[:10]
    ev["dataFine"] = normalizza_testo(ev.get("dataFine") or ev.get("dataInizio"))[:10]
    ev["dataTesto"] = normalizza_testo(ev.get("dataTesto"))[:120]
    ev["oraInizio"] = normalizza_testo(ev.get("oraInizio"))[:5] or estrai_ore(ev.get("dataTesto"))
    ev["oraFine"] = normalizza_testo(ev.get("oraFine"))[:5]
    ev["costo"] = normalizza_testo(ev.get("costo")) or "Da verificare"
    ev["indirizzoMappa"] = normalizza_testo(ev.get("indirizzoMappa")) or f"{ev['luogo']}, {ev['citta']}"
    ev["fonteUrl"] = normalizza_fonte_url(ev.get("fonteUrl"), url_ammesse)
    ev["statoVerifica"] = "fonte_trovata" if ev["fonteUrl"] else "da_verificare"
    ev["ultimaVerifica"] = now_local().strftime("%Y-%m-%d %H:%M:%S")
    ev["fasciaTerritoriale"] = etichetta_fascia(ev["citta"])
    return ev


def token_significativi(testo, citta=""):
    pulito = re.sub(r"[^a-z0-9àèéìòù\s]", " ", (testo or "").lower())
    city_tokens = set(re.sub(r"[^a-z0-9àèéìòù\s]", " ", (citta or "").lower()).split())
    return {w for w in pulito.split() if len(w) >= 3 and w not in STOPWORDS_IT and w not in city_tokens}


def date_compatibili(a, b):
    ai, af = parse_data(a.get("dataInizio")), parse_data(a.get("dataFine"))
    bi, bf = parse_data(b.get("dataInizio")), parse_data(b.get("dataFine"))
    if not all((ai, af, bi, bf)):
        return a.get("dataInizio") == b.get("dataInizio")
    return abs((ai - bi).days) <= 1 and abs((af - bf).days) <= 1 or max(ai, bi) <= min(af, bf)


def sono_duplicati(a, b):
    if normalizza_testo(a.get("citta")).lower() != normalizza_testo(b.get("citta")).lower():
        return False
    if not date_compatibili(a, b):
        return False
    t1 = re.sub(r"[^a-z0-9\s]", "", normalizza_testo(a.get("titolo")).lower()).strip()
    t2 = re.sub(r"[^a-z0-9\s]", "", normalizza_testo(b.get("titolo")).lower()).strip()
    if not t1 or not t2:
        return False
    if min(len(t1), len(t2)) >= 10 and (t1 in t2 or t2 in t1):
        return True
    sim = SequenceMatcher(None, t1, t2).ratio()
    if sim >= 0.78:
        return True
    tok1, tok2 = token_significativi(t1, a.get("citta")), token_significativi(t2, b.get("citta"))
    if tok1 and tok2:
        inter = len(tok1 & tok2)
        jac = inter / len(tok1 | tok2)
        contain = inter / min(len(tok1), len(tok2))
        if jac >= 0.58 or (inter >= 2 and contain >= 0.85):
            return True
    return False


def specifica_url(url):
    if not url:
        return False
    path = urlparse(url).path.rstrip("/").lower()
    return path not in ("", "/eventi", "/eventi/weekend", "/category/eventi")


def unisci_eventi(esistente, nuovo):
    out = dict(esistente)
    # Preferisce titolo/descrizione più completi, senza sovrascrivere dati buoni con stringhe vuote.
    for campo, limite in (("titolo", 120), ("descrizione", 500), ("luogo", 180)):
        nv = normalizza_testo(nuovo.get(campo))
        ov = normalizza_testo(out.get(campo))
        if len(nv) > len(ov) and len(nv) <= limite:
            out[campo] = nv
    if out.get("costo") in ("", "Da verificare") and nuovo.get("costo") not in ("", "Da verificare"):
        out["costo"] = nuovo["costo"]
    if not specifica_url(out.get("fonteUrl")) and specifica_url(nuovo.get("fonteUrl")):
        out["fonteUrl"] = nuovo["fonteUrl"]
        out["statoVerifica"] = nuovo.get("statoVerifica", "fonte_trovata")
    if not out.get("oraInizio") and nuovo.get("oraInizio"):
        out["oraInizio"] = nuovo["oraInizio"]
    if not out.get("oraFine") and nuovo.get("oraFine"):
        out["oraFine"] = nuovo["oraFine"]
    if not out.get("indirizzoMappa") and nuovo.get("indirizzoMappa"):
        out["indirizzoMappa"] = nuovo["indirizzoMappa"]
    out["ultimaVerifica"] = nuovo.get("ultimaVerifica", out.get("ultimaVerifica", ""))
    return out

# -----------------------------------------------------------------------------
# GEMINI INTERACTIONS API + GOOGLE SEARCH
# -----------------------------------------------------------------------------


def estrai_output_interaction(data):
    testi = []
    urls = set()
    steps = data.get("steps", []) if isinstance(data, dict) else []
    for step in steps:
        if not isinstance(step, dict):
            continue
        content = step.get("content", [])
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and block.get("text"):
                    testi.append(block["text"])
                for ann in block.get("annotations", []) or []:
                    if isinstance(ann, dict):
                        url = ann.get("url") or ann.get("uri")
                        if url and str(url).startswith(("https://", "http://")):
                            urls.add(normalizza_url(url))
        # Alcune versioni di risposta possono esporre output testuale direttamente nello step.
        if step.get("type") == "model_output" and isinstance(step.get("text"), str):
            testi.append(step["text"])
    output_text = data.get("output_text") if isinstance(data, dict) else None
    if output_text:
        testi.append(str(output_text))
    return "\n".join(dict.fromkeys(testi)).strip(), {u for u in urls if u}


def chiamata_gemini(prompt, label, usa_search=False, max_tentativi=3):
    if not API_KEY:
        log.error("GEMINI_API_KEY non è impostata: salto %s", label)
        return "", set(), False

    headers = {"Content-Type": "application/json", "x-goog-api-key": API_KEY, "Api-Revision": "2026-05-20"}
    ultimo_errore = "nessuna risposta"

    for modello in GEMINI_MODELS:
        for tentativo in range(1, max_tentativi + 1):
            payload = {"model": modello, "input": prompt}
            if usa_search:
                payload["tools"] = [{"type": "google_search"}]
            try:
                resp = SESSION.post(INTERACTIONS_URL, headers=headers, json=payload, timeout=120)
                if resp.status_code == 429:
                    ultimo_errore = f"429 quota/rate limit su {modello}"
                    attesa = min(60, 8 * tentativo)
                    log.warning("%s: %s, attendo %ss", label, ultimo_errore, attesa)
                    time.sleep(attesa)
                    continue
                if resp.status_code in (500, 502, 503, 504):
                    ultimo_errore = f"HTTP {resp.status_code} su {modello}"
                    time.sleep(5 * tentativo)
                    continue
                if resp.status_code != 200:
                    ultimo_errore = f"HTTP {resp.status_code}: {resp.text[:500]}"
                    log.error("%s: %s", label, ultimo_errore)
                    # Errori auth/modello/strumento non devono provocare un fallback senza ricerca.
                    if resp.status_code in (400, 401, 403, 404):
                        break
                    continue
                data = resp.json()
                testo, urls = estrai_output_interaction(data)
                if not testo:
                    ultimo_errore = f"risposta senza output testuale: {json.dumps(data, ensure_ascii=False)[:400]}"
                    log.warning("%s: %s", label, ultimo_errore)
                    break
                if usa_search and not urls:
                    # Search tool could have been invoked but annotations may be absent. Do not
                    # accept model-generated URLs as citations; return text with no source list,
                    # so the downstream validator keeps records pending rather than trusting them.
                    log.warning("%s: Google Search non ha restituito citazioni URL estraibili.", label)
                log.info("%s completato con %s (%s caratteri, %s URL citati)", label, modello, len(testo), len(urls))
                return testo, urls, True
            except requests.RequestException as exc:
                ultimo_errore = str(exc)
                log.warning("%s: errore di rete (%s/%s): %s", label, tentativo, max_tentativi, exc)
                time.sleep(4 * tentativo)
            except Exception as exc:
                ultimo_errore = str(exc)
                log.exception("%s: errore imprevisto: %s", label, exc)
                break
        # prova il modello successivo soltanto se il problema non è una chiave errata.
        if "HTTP 401" in ultimo_errore or "HTTP 403" in ultimo_errore:
            break
    log.error("Ricerca %s fallita: %s", label, ultimo_errore)
    return "", set(), False


def estrai_array_json(testo):
    if not testo:
        return []
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", testo.strip(), flags=re.IGNORECASE)
    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, list) else []
    except json.JSONDecodeError:
        pass
    # Trova il primo array JSON bilanciato, evitando regex greedy su più blocchi.
    start = cleaned.find("[")
    if start < 0:
        return []
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(cleaned[start:i + 1])
                        return obj if isinstance(obj, list) else []
                    except json.JSONDecodeError:
                        return []
    return []

# -----------------------------------------------------------------------------
# SCRAPING FONTI LOCALI + JSON-LD
# -----------------------------------------------------------------------------


def espandi_jsonld(data):
    out = []
    if isinstance(data, list):
        for item in data:
            out.extend(espandi_jsonld(item))
    elif isinstance(data, dict):
        if isinstance(data.get("@graph"), list):
            for item in data["@graph"]:
                out.extend(espandi_jsonld(item))
        else:
            out.append(data)
    return out


def tipo_jsonld_evento(obj):
    raw = obj.get("@type", [])
    values = raw if isinstance(raw, list) else [raw]
    return any("event" in str(x).lower() for x in values)


def categoria_da_testo(testo, default="Altro"):
    t = normalizza_testo(testo).lower()
    regole = [
        ("Famiglie & Bambini", ["bambin", "famigl", "laboratorio", "villaggio", "babbo natale"]),
        ("Natura & Escursioni", ["trekking", "escursion", "passeggiat", "natura", "camminata"]),
        ("Sagre & Food", ["sagra", "degust", "mercatino", "enogastronom", "street food"]),
        ("Locali & Serate", ["dj set", "discoteca", "club", "aperitivo", "serata", "night"]),
        ("Musica & Concerti", ["concerto", "musica", "teatro", "spettacolo", "cabaret"]),
        ("Attività diurne", ["visita guidata", "laboratorio", "mostra", "visita", "esperienza"]),
    ]
    for categoria, parole in regole:
        if any(p in t for p in parole):
            return categoria
    return default


def estrai_eventi_jsonld(soup, citta_fonte, url_pagina):
    risultati = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw = script.string or script.get_text()
            if not raw:
                continue
            data = json.loads(raw)
            for obj in espandi_jsonld(data):
                if not tipo_jsonld_evento(obj):
                    continue
                title = normalizza_testo(obj.get("name"))
                start = normalizza_testo(obj.get("startDate"))[:10]
                end = normalizza_testo(obj.get("endDate"))[:10] or start
                loc = obj.get("location") or {}
                if isinstance(loc, list):
                    loc = loc[0] if loc else {}
                if isinstance(loc, dict):
                    venue = normalizza_testo(loc.get("name"))
                    address = loc.get("address") or {}
                    city = normalizza_testo(address.get("addressLocality")) if isinstance(address, dict) else ""
                    street = normalizza_testo(address.get("streetAddress")) if isinstance(address, dict) else ""
                    map_address = ", ".join(x for x in (street, venue, city or citta_fonte) if x)
                else:
                    venue = normalizza_testo(loc)
                    city = ""
                    map_address = f"{venue}, {citta_fonte}"
                city = city or citta_fonte
                event_url = normalizza_url(obj.get("url") or url_pagina)
                if title and start and venue:
                    start_dt = normalizza_testo(obj.get("startDate"))
                    end_dt = normalizza_testo(obj.get("endDate"))
                    results_text = f"{title} {normalizza_testo(obj.get('description'))}"
                    risultati.append({
                        "tipoContenuto": "evento",
                        "citta": city,
                        "categoria": categoria_da_testo(results_text),
                        "titolo": title,
                        "dataTesto": f"Dal {start}" if start == end else f"Dal {start} al {end}",
                        "dataInizio": start,
                        "dataFine": end,
                        "oraInizio": estrai_ore(start_dt),
                        "oraFine": estrai_ore(end_dt),
                        "luogo": venue,
                        "indirizzoMappa": map_address,
                        "costo": "Da verificare",
                        "descrizione": normalizza_testo(obj.get("description"))[:450] or f"Evento in programma presso {venue}.",
                        "fonteUrl": event_url,
                    })
        except Exception as exc:
            log.debug("JSON-LD non leggibile su %s: %s", url_pagina, exc)
    return risultati


def raccogli_testo_fonte(url_indice, citta_fonte):
    """Raccoglie link/articoli dalla pagina di eventi e legge un numero limitato di schede."""
    try:
        response = SESSION.get(url_indice, timeout=18)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as exc:
        log.warning("Scraping non riuscito %s: %s", url_indice, exc)
        return "", [], set()

    testi = []
    eventi_jsonld = estrai_eventi_jsonld(soup, citta_fonte, url_indice)
    url_ammesse = {normalizza_url(url_indice)}
    index_host = (urlparse(url_indice).hostname or "").lower()
    link_candidates = []

    for tag in soup(["script", "style", "nav", "footer", "aside", "form", "header"]):
        tag.decompose()

    for a in soup.find_all("a", href=True):
        href = normalizza_url(urljoin(url_indice, a.get("href", "")))
        host = (urlparse(href).hostname or "").lower()
        if not href or not host or not dominio_stesso(href, url_indice):
            continue
        if href == normalizza_url(url_indice):
            continue
        path = urlparse(href).path.lower()
        if any(x in path for x in ("/tag/", "/author/", "/page/", "privacy", "cookie", "login", "contatti")):
            continue
        title = normalizza_testo(a.get_text(" ", strip=True))
        if len(title) < 12:
            continue
        # Non richiede che l'URL contenga /event: usa anche il testo del link e la sezione padre.
        parent_text = normalizza_testo(a.parent.get_text(" ", strip=True))[:350] if a.parent else ""
        candidate_text = (title + " " + parent_text + " " + path).lower()
        keywords = ("event", "serat", "concert", "sagra", "mercatin", "teatro", "spettacol",
                    "bambin", "famigl", "escursion", "festival", "festa", "weekend", "natale")
        if not any(k in candidate_text for k in keywords):
            continue
        if any(k in title.lower() for k in ("cookie", "privacy", "newsletter", "abbonati", "cronaca")):
            continue
        if href not in link_candidates:
            link_candidates.append(href)
            testi.append(f"- {title} [URL: {href}]")

    article_texts = []
    for article_url in link_candidates[:MAX_ARTICLES_PER_SOURCE]:
        try:
            art = SESSION.get(article_url, timeout=12)
            art.raise_for_status()
            art.encoding = art.apparent_encoding or "utf-8"
            sp = BeautifulSoup(art.text, "html.parser")
            ev_ld = estrai_eventi_jsonld(sp, citta_fonte, article_url)
            eventi_jsonld.extend(ev_ld)
            for tag in sp(["script", "style", "nav", "footer", "aside", "form", "header"]):
                tag.decompose()
            h = sp.find(["h1", "h2"])
            heading = normalizza_testo(h.get_text(" ", strip=True)) if h else ""
            paragraphs = []
            for p in sp.find_all(["p", "time", "li"]):
                text = normalizza_testo(p.get_text(" ", strip=True))
                if 30 <= len(text) <= 500 and text not in paragraphs:
                    paragraphs.append(text)
            if heading or paragraphs:
                article_texts.append(
                    f"[ARTICOLO {article_url}] {heading}\n" + " | ".join(paragraphs[:7])
                )
            url_ammesse.add(normalizza_url(article_url))
        except Exception as exc:
            log.debug("Articolo non letto %s: %s", article_url, exc)
        time.sleep(0.4)

    # Aggiunge metadati JSON-LD al testo passato all'estrattore.
    for ev in eventi_jsonld:
        testi.append("JSON_LD_EVENTO: " + json.dumps(ev, ensure_ascii=False))
        url_ammesse.add(normalizza_url(ev.get("fonteUrl")))

    corpus = f"FONTE INDICE {url_indice} ({citta_fonte})\n" + "\n".join(testi) + "\n\n" + "\n\n".join(article_texts)
    return corpus[:18000], eventi_jsonld, {u for u in url_ammesse if u}

# -----------------------------------------------------------------------------
# PROMPT E AGENTI
# -----------------------------------------------------------------------------


def prompt_ricerca_eventi(agente):
    today = oggi_iso()
    end = limite_futuro_iso()
    towns = ", ".join(COMUNI_TARGET)
    return f"""Sei un ricercatore web professionale per il portale locale indipendente 'Che Si Fa Cerignola'.
Data di riferimento: {today}. Cerca appuntamenti tra {today} e {end}.

MISSIONE TEMATICA: {agente['missione']}.

TERRITORIO: Cerignola e comuni raggiungibili nell'area circostante, con priorità a Cerignola e alla prima/seconda cintura. Verifica singolarmente, senza limitarti ai capoluoghi, queste località: {towns}.

ISTRUZIONI DI RICERCA:
- Usa Google Search. Effettua ricerche mirate per categoria + singolo comune + periodo; non fare una sola query generica.
- Cerca anche siti ufficiali dei Comuni, Pro Loco, associazioni, teatri, musei, organizzatori e pagine ufficiali dei locali.
- Cerca sia pagine di eventi sia post/pagine ufficiali pubbliche che riportino una data verificabile.
- Non inventare risultati, date, orari, prezzi, luoghi o link.
- Inserisci solo appuntamenti realmente programmati, con data certa e non già conclusi.
- Se trovi solo una pagina generica o non trovi data certa, NON trasformarla in un evento.
- Escludi politica, cronaca, celebrazioni religiose, beneficenza, convegni professionali e sport agonistico.

Restituisci un elenco testuale conciso con ogni candidato e il link esatto della pagina che conferma l'appuntamento. Se non trovi risultati, scrivi chiaramente 'NESSUN RISULTATO VERIFICATO'."""


def prompt_ricerca_permanenti(agente):
    today = oggi_iso()
    towns = ", ".join(COMUNI_TARGET)
    return f"""Sei un ricercatore territoriale per 'Che Si Fa Cerignola'. Oggi è {today}.
MISSIONE: trova {agente['missione']}
TERRITORIO: Cerignola e dintorni. Cerca località per località, dando priorità a Cerignola, prima e seconda cintura. Comuni da esaminare: {towns}.

REGOLE:
- Cerca luoghi/attività reali e identificabili.
- Non presentare un luogo come aperto, visitabile o prenotabile se non trovi una fonte che lo confermi.
- Distingui luogo permanente da attività/esperienza prenotabile.
- Non inventare telefono, indirizzo preciso, orari, prezzi o disponibilità.
- Cerca fonti ufficiali, siti di gestori, Comuni, Pro Loco e organizzatori.
- Restituisci candidati e URL esatti delle fonti. Non produrre eventi datati in questo agente.
Se la ricerca non produce risultati, scrivi 'NESSUN RISULTATO VERIFICATO'."""


def prompt_estrazione_eventi(corpus, url_ammesse):
    today = oggi_iso()
    allowed = "\n".join(sorted(url_ammesse))[:12000]
    return f"""Sei l'estrattore dati di 'Che Si Fa Cerignola'. Data odierna {today}.
Estrai dal materiale sottostante SOLO eventi futuri o attualmente in corso con data verificabile.

VINCOLI OBBLIGATORI:
1. Non inventare eventi, date, orari, indirizzi, costi o descrizioni.
2. 'fonteUrl' deve essere COPIATO IDENTICO da uno degli URL AMMESSI qui sotto. Se non trovi una fonte specifica, non includere quell'evento.
3. Non usare URL generici di categoria come fonte di un singolo evento.
4. Se il dato non è presente, usa stringa vuota per ora/costo; non indovinare.
5. La data finale deve essere uguale o successiva a oggi. Sono ammessi eventi già iniziati ma ancora in corso.
6. Le date devono essere YYYY-MM-DD; gli orari HH:MM.
7. La città deve essere quella dell'evento, non quella della redazione.
8. Non duplicare lo stesso evento.

Categorie consentite: {json.dumps(CATEGORIE_EVENTI, ensure_ascii=False)}.

URL AMMESSI:
{allowed}

Restituisci SOLO un array JSON valido. Ogni elemento deve avere queste chiavi:
{{"tipoContenuto":"evento","citta":"","categoria":"","titolo":"","dataTesto":"","dataInizio":"YYYY-MM-DD","dataFine":"YYYY-MM-DD","oraInizio":"HH:MM oppure vuoto","oraFine":"HH:MM oppure vuoto","luogo":"","indirizzoMappa":"","costo":"Da verificare se ignoto","descrizione":"","fonteUrl":"URL ammesso identico"}}

MATERIALE:
{corpus[:28000]}
"""


def prompt_estrazione_permanenti(corpus, url_ammesse, tipo):
    allowed = "\n".join(sorted(url_ammesse))[:12000]
    if tipo == "luogo":
        definizione = "luoghi permanenti: parchi, laghi, riserve, borghi, castelli, musei, siti, percorsi e attrazioni visitabili."
        fields = '"tipoContenuto":"luogo","nome":"","citta":"","indirizzo":"","descrizione":"","categoria":"","urlUfficiale":"","fonteUrl":""'
    else:
        definizione = "attività o esperienze: visite guidate, laboratori, fattorie didattiche, degustazioni, tour e attività prenotabili/ricorrenti."
        fields = '"tipoContenuto":"attivita","nome":"","citta":"","luogo":"","descrizione":"","categoria":"","disponibilita":"Da verificare se ignota","prezzo":"Da verificare se ignoto","urlUfficiale":"","fonteUrl":""'
    return f"""Sei un estrattore per 'Che Si Fa Cerignola'. Estrai solo {definizione}
Non inventare disponibilità, orari, prezzi, indirizzi o stato di apertura.
Ogni elemento deve avere una fonte esplicita. 'fonteUrl' e 'urlUfficiale' devono essere identici a uno degli URL ammessi; non generare URL nuovi.
Non includere eventi temporanei con una singola data, che appartengono a eventi.json.
Restituisci SOLO un array JSON di oggetti con queste chiavi: {{{fields}}}.
Tutti i campi devono essere stringhe. Se un'informazione è assente, usa stringa vuota o 'Da verificare'.

URL AMMESSI:
{allowed}

MATERIALE:
{corpus[:20000]}"""


def esegui_agente_eventi(agente):
    testo, urls, ok = chiamata_gemini(prompt_ricerca_eventi(agente), agente["nome"], usa_search=True)
    if not ok or not testo:
        return [], set(), {"stato": "errore_ricerca", "candidati": 0, "validi": 0}
    estratto, _, estrazione_ok = chiamata_gemini(
        prompt_estrazione_eventi(testo, urls),
        f"Estrazione {agente['nome']}",
        usa_search=False
    )
    if not estrazione_ok:
        return [], urls, {"stato": "errore_estrazione", "candidati": 0, "validi": 0}
    items = estrai_array_json(estratto)
    return items, urls, {"stato": "ok", "candidati": len(items), "validi": 0}


def esegui_agente_permanente(agente, tipo):
    testo, urls, ok = chiamata_gemini(prompt_ricerca_permanenti(agente), agente["nome"], usa_search=True)
    if not ok or not testo:
        return [], set(), {"stato": "errore_ricerca", "candidati": 0}
    extracted, _, ok2 = chiamata_gemini(
        prompt_estrazione_permanenti(testo, urls, tipo),
        f"Estrazione {agente['nome']}",
        usa_search=False
    )
    if not ok2:
        return [], urls, {"stato": "errore_estrazione", "candidati": 0}
    return estrai_array_json(extracted), urls, {"stato": "ok", "candidati": len(estrai_array_json(extracted))}

# -----------------------------------------------------------------------------
# VALIDAZIONE / CONSOLIDAMENTO
# -----------------------------------------------------------------------------


def normalizza_permanente(raw, tipo, urls_ammesse):
    item = dict(raw or {})
    item["tipoContenuto"] = tipo
    item["nome"] = normalizza_testo(item.get("nome"))[:150]
    item["citta"] = normalizza_citta({"citta": item.get("citta"), "luogo": item.get("luogo"), "titolo": item.get("nome"), "descrizione": item.get("descrizione")}, "Cerignola")
    item["descrizione"] = normalizza_testo(item.get("descrizione"))[:500]
    item["categoria"] = normalizza_testo(item.get("categoria"))[:100]
    item["fonteUrl"] = normalizza_fonte_url(item.get("fonteUrl"), urls_ammesse)
    item["urlUfficiale"] = normalizza_fonte_url(item.get("urlUfficiale"), urls_ammesse)
    item["statoVerifica"] = "da_verificare"  # La revisione umana è obbligatoria prima della pubblicazione.
    item["ultimaVerifica"] = now_local().strftime("%Y-%m-%d %H:%M:%S")
    item["fasciaTerritoriale"] = etichetta_fascia(item["citta"])
    return item


def dedup_permanenti(items):
    out = []
    seen = set()
    for item in items:
        key = (item.get("tipoContenuto", ""), item.get("nome", "").lower(), item.get("citta", "").lower())
        if not key[1] or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def genera_report(eventi, aggiunti, aggiornati, agent_stats, scraping_stats, luoghi_count, attivita_count, errori):
    by_city = Counter(e.get("citta", "Sconosciuta") for e in eventi)
    by_cat = Counter(e.get("categoria", "Altro") for e in eventi)
    by_band = Counter(e.get("fasciaTerritoriale", etichetta_fascia(e.get("citta"))) for e in eventi)
    specific_urls = sum(1 for e in eventi if specifica_url(e.get("fonteUrl")))
    report = {
        "aggiornatoAl": now_local().strftime("%Y-%m-%d %H:%M:%S"),
        "dataRiferimento": oggi_iso(),
        "totaleEventiAttivi": len(eventi),
        "nuoviAggiunti": aggiunti,
        "aggiornati": aggiornati,
        "coperturaTerritorialeOrientativa": dict(by_band),
        "ripartizioneCategorie": dict(by_cat.most_common()),
        "topComuni": dict(by_city.most_common(25)),
        "urlSpecifici": specific_urls,
        "percentualeUrlSpecifici": round(specific_urls / len(eventi) * 100, 1) if eventi else 0,
        "ricercheAgenti": agent_stats,
        "fontiScraping": scraping_stats,
        "candidatiLuoghiDaVerificare": luoghi_count,
        "candidatiAttivitaDaVerificare": attivita_count,
        "errori": errori,
        "nota": "Le fasce territoriali sono indicative, non distanze stradali o misure GPS. Luoghi e attività restano in revisione manuale."
    }
    scrivi_json_atomico(REPORT_FILE, report)
    return report

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------


def main():
    log.info("Avvio Che Si Fa Cerignola v2 | data locale=%s | modello primario=%s", oggi_iso(), GEMINI_MODELS[0] if GEMINI_MODELS else "nessuno")
    errori = []
    agent_stats = {}
    scraping_stats = {}
    url_ammesse_globali = set()

    existing_raw = leggi_json(EVENTI_FILE, [])
    if not isinstance(existing_raw, list):
        log.error("eventi.json non contiene un array JSON: interrompo senza sovrascriverlo.")
        return

    # Conserva gli eventi esistenti ancora validi; non svuota il file in caso di errore API.
    consolidati = []
    for raw in existing_raw:
        if not isinstance(raw, dict):
            continue
        ev = pulisci_evento(raw, raw.get("citta") or "Cerignola", {raw.get("fonteUrl", "")})
        if evento_valido(ev):
            idx = next((i for i, old in enumerate(consolidati) if sono_duplicati(old, ev)), None)
            if idx is None:
                consolidati.append(ev)
            else:
                consolidati[idx] = unisci_eventi(consolidati[idx], ev)

    nuovi_eventi = []

    # 1) Scraping delle fonti locali.
    if ENABLE_SCRAPING:
        for fonte in FONTI_EVENTI:
            log.info("Scraping: %s (%s)", fonte["url"], fonte["citta"])
            corpus, jsonld_events, urls = raccogli_testo_fonte(fonte["url"], fonte["citta"])
            url_ammesse_globali.update(urls)
            scraping_stats[fonte["citta"] + " | " + fonte["url"]] = {
                "caratteri": len(corpus), "jsonld": len(jsonld_events), "url": len(urls)
            }
            for raw in jsonld_events:
                ev = pulisci_evento(raw, fonte["citta"], urls | {raw.get("fonteUrl", "")})
                if evento_valido(ev) and ev.get("fonteUrl") and specifica_url(ev.get("fonteUrl")):
                    nuovi_eventi.append(ev)
            if corpus.strip() and API_KEY:
                # L'estrattore lavora sui testi scaricati; URL ammessi solo se raccolti dallo scraper.
                extracted_text, _, ok = chiamata_gemini(
                    prompt_estrazione_eventi(corpus, urls),
                    f"Estrazione scraping {fonte['citta']}",
                    usa_search=False
                )
                if ok:
                    for raw in estrai_array_json(extracted_text):
                        ev = pulisci_evento(raw, fonte["citta"], urls)
                        if evento_valido(ev) and ev.get("fonteUrl") and specifica_url(ev.get("fonteUrl")):
                            nuovi_eventi.append(ev)
                else:
                    errori.append(f"Estrazione scraping fallita: {fonte['url']}")
            time.sleep(0.5)

    # 2) Ricerche Google Search tematiche per appuntamenti.
    if API_KEY:
        for agente in AGENTI_EVENTI:
            if SEARCH_DELAY_SECONDS:
                time.sleep(SEARCH_DELAY_SECONDS)
            raw_items, urls, stats = esegui_agente_eventi(agente)
            url_ammesse_globali.update(urls)
            valid_count = 0
            for raw in raw_items:
                ev = pulisci_evento(raw, "Cerignola", urls)
                if evento_valido(ev) and ev.get("fonteUrl") and specifica_url(ev.get("fonteUrl")):
                    nuovi_eventi.append(ev)
                    valid_count += 1
            stats["validi"] = valid_count
            agent_stats[agente["id"]] = stats
            log.info("Agente %s: %s candidati, %s eventi ammessi con fonte", agente["id"], len(raw_items), valid_count)
    else:
        errori.append("GEMINI_API_KEY assente: non eseguite le ricerche Gemini.")

    # 3) Deduplicazione eventi e consolidamento.
    aggiunti = 0
    aggiornati = 0
    scartati_senza_fonte = 0
    for ev in nuovi_eventi:
        if not ev.get("fonteUrl"):
            scartati_senza_fonte += 1
            continue
        idx = next((i for i, old in enumerate(consolidati) if sono_duplicati(old, ev)), None)
        if idx is None:
            consolidati.append(ev)
            aggiunti += 1
        else:
            prima = consolidati[idx]
            dopo = unisci_eventi(prima, ev)
            if dopo != prima:
                consolidati[idx] = dopo
                aggiornati += 1

    # Se un errore totale ha impedito ogni nuova raccolta, i dati esistenti validi restano intatti.
    final_events = sorted(
        consolidati,
        key=lambda x: (x.get("dataInizio", "9999-12-31"), priorita_comune(x.get("citta")), x.get("titolo", "").lower())
    )
    scrivi_json_atomico(EVENTI_FILE, final_events)

    # 4) Luoghi e attività: raccolta in coda di revisione, mai pubblicazione automatica.
    luoghi_out = []
    attivita_out = []
    if API_KEY and ENABLE_PLACES_ACTIVITIES:
        if SEARCH_DELAY_SECONDS:
            time.sleep(SEARCH_DELAY_SECONDS)
        raw_places, place_urls, place_stats = esegui_agente_permanente(AGENTE_LUOGHI, "luogo")
        url_ammesse_globali.update(place_urls)
        for raw in raw_places:
            item = normalizza_permanente(raw, "luogo", place_urls)
            if item.get("nome") and item.get("fonteUrl"):
                luoghi_out.append(item)
        agent_stats[AGENTE_LUOGHI["id"]] = place_stats

        if SEARCH_DELAY_SECONDS:
            time.sleep(SEARCH_DELAY_SECONDS)
        raw_activities, activity_urls, activity_stats = esegui_agente_permanente(AGENTE_ATTIVITA, "attivita")
        url_ammesse_globali.update(activity_urls)
        for raw in raw_activities:
            item = normalizza_permanente(raw, "attivita", activity_urls)
            if item.get("nome") and item.get("fonteUrl"):
                attivita_out.append(item)
        agent_stats[AGENTE_ATTIVITA["id"]] = activity_stats

        # Mantiene i candidati precedenti ancora presenti, evitando di cancellarli in caso di
        # un ciclo temporaneamente povero. Questi file sono bozze da verificare dall'amministratore.
        old_places = leggi_json(LUOGHI_FILE, [])
        old_activities = leggi_json(ATTIVITA_FILE, [])
        luoghi_out = dedup_permanenti((old_places if isinstance(old_places, list) else []) + luoghi_out)
        attivita_out = dedup_permanenti((old_activities if isinstance(old_activities, list) else []) + attivita_out)
        scrivi_json_atomico(LUOGHI_FILE, luoghi_out)
        scrivi_json_atomico(ATTIVITA_FILE, attivita_out)
    else:
        # Non sovrascrivere archivi permanenti esistenti se la funzione è disabilitata.
        luoghi_out = leggi_json(LUOGHI_FILE, [])
        attivita_out = leggi_json(ATTIVITA_FILE, [])

    report = genera_report(
        final_events, aggiunti, aggiornati, agent_stats, scraping_stats,
        len(luoghi_out) if isinstance(luoghi_out, list) else 0,
        len(attivita_out) if isinstance(attivita_out, list) else 0,
        errori
    )
    report["candidatiScartatiSenzaFonte"] = scartati_senza_fonte
    scrivi_json_atomico(REPORT_FILE, report)

    log.info("=" * 64)
    log.info("COMPLETATO | eventi attivi=%s | aggiunti=%s | aggiornati=%s", len(final_events), aggiunti, aggiornati)
    log.info("URL specifici=%s%% | luoghi in revisione=%s | attività in revisione=%s", report["percentualeUrlSpecifici"], len(luoghi_out), len(attivita_out))
    log.info("Candidati scartati perché privi di fonte ammessa: %s", scartati_senza_fonte)
    log.info("File generati: %s, %s, %s, %s", EVENTI_FILE, LUOGHI_FILE, ATTIVITA_FILE, REPORT_FILE)


if __name__ == "__main__":
    main()
