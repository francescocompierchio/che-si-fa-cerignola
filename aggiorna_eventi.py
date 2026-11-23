import os
import re
import json
import time
import requests
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9"
}

FONTI_EVENTI = [
    {"url": "https://www.viverecerignola.it/", "citta": "Cerignola", "gruppo": "Nord / Capitanata"},
    {"url": "https://www.cerignolaviva.it/eventi/", "citta": "Cerignola", "gruppo": "Nord / Capitanata"},
    {"url": "https://www.foggiatoday.it/eventi/", "citta": "Foggia", "gruppo": "Nord / Capitanata"},
    {"url": "https://www.foggiatoday.it/eventi/weekend/", "citta": "Foggia", "gruppo": "Nord / Capitanata"},
    {"url": "https://www.barlettaviva.it/eventi/", "citta": "Barletta", "gruppo": "Costa BAT e Gargano"},
    {"url": "https://www.traniviva.it/eventi/", "citta": "Trani", "gruppo": "Costa BAT e Gargano"},
    {"url": "https://www.bisceglieviva.it/eventi/", "citta": "Bisceglie", "gruppo": "Costa BAT e Gargano"},
    {"url": "https://www.andriaviva.it/eventi/", "citta": "Andria", "gruppo": "Costa BAT e Gargano"},
    {"url": "https://www.manfredonianews.it/category/eventi/", "citta": "Manfredonia", "gruppo": "Costa BAT e Gargano"},
]

DOMINI_FONTI_CONSENTITI = {
    urlparse(f["url"]).netloc.lower() for f in FONTI_EVENTI
}

FALLBACK_URL_PER_CITTA = {
    "Cerignola": "https://www.cerignolaviva.it/eventi/",
    "Foggia": "https://www.foggiatoday.it/eventi/",
    "Barletta": "https://www.barlettaviva.it/eventi/",
    "Trani": "https://www.traniviva.it/eventi/",
    "Bisceglie": "https://www.bisceglieviva.it/eventi/",
    "Andria": "https://www.andriaviva.it/eventi/",
    "Manfredonia": "https://www.manfredonianews.it/category/eventi/",
}

CATEGORIE_VALIDE = [
    "Locali & Serate",
    "Attività serali",
    "Musica & Concerti",
    "Sagre & Food",
    "Famiglie & Bambini",
    "Natura & Escursioni",
    "Attività diurne",
    "Luoghi da visitare",
    "Altro"
]

MAPPA_CATEGORIE = {
    "serate & locali": "Locali & Serate",
    "locali & serate": "Locali & Serate",
    "serate": "Locali & Serate",
    "locali": "Locali & Serate",
    "club": "Locali & Serate",
    "aperitivo": "Locali & Serate",
    "dj set": "Locali & Serate",
    "attività serali": "Attività serali",
    "attivita serali": "Attività serali",
    "attività serale": "Attività serali",
    "attivita serale": "Attività serali",
    "serale": "Attività serali",
    "notturna": "Attività serali",
    "notturno": "Attività serali",
    "dopocena": "Attività serali",
    "apericena": "Attività serali",
    "musica": "Musica & Concerti",
    "musica & concerti": "Musica & Concerti",
    "concerti": "Musica & Concerti",
    "fiera": "Sagre & Food",
    "sagra": "Sagre & Food",
    "sagre & food": "Sagre & Food",
    "food": "Sagre & Food",
    "famiglie": "Famiglie & Bambini",
    "famiglie & bambini": "Famiglie & Bambini",
    "bambini": "Famiglie & Bambini",
    "natura": "Natura & Escursioni",
    "escursioni": "Natura & Escursioni",
    "escursione": "Natura & Escursioni",
    "natura & escursioni": "Natura & Escursioni",
    "trekking": "Natura & Escursioni",
    "passeggiata": "Natura & Escursioni",
    "attività diurne": "Attività diurne",
    "attivita diurne": "Attività diurne",
    "luoghi da visitare": "Luoghi da visitare",
    "luogo da visitare": "Luoghi da visitare",
    "cultura & spettacoli": "Attività diurne",
    "cultura": "Attività diurne"
}

PAROLE_VIETATE = [
    "meteo", "libeccio", "venti forti", "pioggia", "allerta", "neve", "freddo",
    "cielo sereno", "°c", "min ", "max ", "archivio", "svolta ue", "cop31",
    "frode fiscale", "riciclaggio", "indagati", "sequestri", "scontro tra auto",
    "morti e feriti", "colpisce il padre", "martello", "leccese",
    "questore", "sospende la licenza", "amianto", "pomodori", "agricoltura",
    "annullato", "annullamento", "cancellazione", "rinviato", "indagine di mercato",
    "arresto", "arresti", "rapina", "incidente", "incendio", "sequestro", "denuncia",
    "indagato", "tribunale", "carabinieri", "polizia", "guardia di finanza",
    "ha rischiato", "intervista", "commentato", "torna sulla", "consiglio comunale",
    "giunta", "sindaco", "elezioni", "partito", "sciopero", "ospedale", "asl",
    "furto", "truffa", "omicidio", "ferito", "morto", "lutto", "cordoglio",
    "convegno", "conferenza", "tavola rotonda", "dibattito", "seminario",
    "presentazione del libro", "presentazione libro", "nuovo libro", "sala consiliare",
    "incontro pubblico", "palazzo di città", "palazzo di citta",
    "salute e prevenzione", "prevenzione", "screening", "vaccin", "estate ",
    "sport", "torneo", "gara", "corsa", "podistica", "trail", "partita",
    "stadio", "palazzetto", "sbanca", "vittoria esterna", "volley"
]

PAROLE_EVENTO_VALIDO = [
    "evento", "eventi", "programma", "natale", "festa", "feste", "sagra", "sagri",
    "concerto", "concerti", "musica", "live", "serata", "serate", "dj", "aperitivo",
    "apericena", "mostra", "mostre", "spettacolo", "spettacoli", "teatro", "rassegna",
    "mercatino", "mercatini", "fiera", "degustazione", "degustazioni", "escursione",
    "escursioni", "trekking", "passeggiata", "laboratorio", "laboratori", "bambini",
    "famiglie", "festival", "apertura", "visita guidata", "visite guidate",
    "castello", "parco", "borgo", "riserva"
]

PAROLE_PRIORITA_LINK = [
    "event", "serat", "seral", "notturn", "dopocena", "apericena", "concert",
    "dj", "live", "sagra", "mercatin", "festival", "festa", "musica", "club",
    "pub", "aperitiv", "lounge", "discotec", "night", "drink", "karaoke",
    "quiz", "famigl", "bambin", "natale", "escursion", "passeggiat", "trekking",
    "natura", "parco", "weekend"
]

STOPWORDS_IT = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una",
    "di", "a", "da", "in", "con", "su", "per", "tra", "fra",
    "del", "dello", "della", "dei", "degli", "delle",
    "al", "allo", "alla", "ai", "agli", "alle",
    "dal", "dallo", "dalla", "nel", "nello", "nella", "sul", "sulla",
    "e", "ed", "o", "che", "si", "fa", "evento", "serata", "appuntamento", "grande", "nuovo"
}

CITTA_TARGET_MAP = {
    "cerignola": "Cerignola",
    "stornara": "Stornara",
    "stornarella": "Stornarella",
    "san ferdinando": "San Ferdinando",
    "san ferdinando di puglia": "San Ferdinando",
    "orta nova": "Orta Nova",
    "trinitapoli": "Trinitapoli",
    "canosa": "Canosa",
    "canosa di puglia": "Canosa",
    "ordona": "Ordona",
    "carapelle": "Carapelle",
    "margherita di savoia": "Margherita di Savoia",
    "lavello": "Lavello",
    "ascoli satriano": "Ascoli Satriano",
    "zapponeta": "Zapponeta",
    "castelluccio dei sauri": "Castelluccio dei Sauri",
    "barletta": "Barletta",
    "candela": "Candela",
    "minervino": "Minervino Murge",
    "minervino murge": "Minervino Murge",
    "foggia": "Foggia",
    "melfi": "Melfi",
    "venosa": "Venosa",
    "deliceto": "Deliceto",
    "rapolla": "Rapolla",
    "andria": "Andria",
    "barile": "Barile",
    "palazzo san gervasio": "Palazzo San Gervasio",
    "rocchetta sant'antonio": "Rocchetta Sant'Antonio",
    "sant'agata di puglia": "Sant'Agata di Puglia",
    "manfredonia": "Manfredonia",
    "rionero in vulture": "Rionero in Vulture",
    "rionero": "Rionero in Vulture",
    "trani": "Trani",
    "bovino": "Bovino",
    "lacedonia": "Lacedonia",
    "monticchio": "Monticchio",
    "laghi di monticchio": "Monticchio",
    "spinazzola": "Spinazzola",
    "monteverde": "Monteverde",
    "montemilone": "Montemilone",
    "atella": "Atella",
    "troia": "Troia",
    "accadia": "Accadia",
    "aquilonia": "Aquilonia",
    "lucera": "Lucera",
    "bisceglie": "Bisceglie",
    "molfetta": "Molfetta",
    "san severo": "San Severo",
    "vieste": "Vieste",
    "mattinata": "Mattinata",
    "monte sant'angelo": "Monte Sant'Angelo"
}

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

COMUNI_CHIAVE_MONITORAGGIO = [
    "Cerignola", "Canosa", "San Ferdinando", "Trinitapoli", "Margherita di Savoia",
    "Orta Nova", "Stornara", "Stornarella", "Lavello", "Ascoli Satriano",
    "Barletta", "Trani", "Andria", "Foggia", "Melfi", "Venosa",
    "Rionero in Vulture", "Monticchio", "Bovino", "Candela", "Minervino Murge"
]

AGENTI_RICERCA = [
    {
        "nome": "Agente 1 - Eventi & Serate (Cerignola, Foggia, BAT)",
        "tipo_contenuto": "evento",
        "categoria_default": "Locali & Serate",
        "missione": (
            "Cerca su Google gli eventi, concerti, spettacoli, serate nei locali, DJ set e feste "
            "in programma nei prossimi 30 giorni pubblicati su cerignolaviva.it, foggiatoday.it, "
            "barlettaviva.it, traniviva.it, andriaviva.it e portali eventi della Puglia "
            "settentrionale e BAT (Cerignola, Foggia, Barletta, Trani, Andria, Canosa di Puglia, "
            "Margherita di Savoia, San Ferdinando di Puglia). Escludi qualsiasi evento sportivo."
        )
    },
    {
        "nome": "Agente 2 - Vulture-Melfese, Subappennino & Sagre (50 km)",
        "tipo_contenuto": "evento",
        "categoria_default": "Sagre & Food",
        "missione": (
            "Cerca su Google sagre, feste di paese, mercatini, degustazioni e manifestazioni in "
            "programma nei prossimi 45 giorni nei comuni entro 50 km da Cerignola: Melfi, Venosa, "
            "Lavello, Rionero in Vulture, Laghi di Monticchio, Ascoli Satriano, Candela, Bovino, "
            "Deliceto, Sant'Agata di Puglia, Minervino Murge, Spinazzola, Orta Nova, Stornara."
        )
    },
    {
        "nome": "Agente 3 - Famiglie, Bambini & Attività Diurne",
        "tipo_contenuto": "evento",
        "categoria_default": "Famiglie & Bambini",
        "missione": (
            "Cerca su Google eventi per famiglie e bambini, laboratori creativi, animazione, "
            "spettacoli per ragazzi, fattorie didattiche e mercatini diurni nei prossimi 45 giorni "
            "tra Cerignola, Foggia, Barletta, Andria, Trani, Canosa di Puglia, Manfredonia e Melfi."
        )
    },
    {
        "nome": "Agente 4 - Natura & Escursioni (50 km)",
        "tipo_contenuto": "evento",
        "categoria_default": "Natura & Escursioni",
        "missione": (
            "Cerca su Google escursioni guidate, trekking, passeggiate nella natura e camminate "
            "nei prossimi weekend entro 50 km da Cerignola: Laghi di Monticchio, Monte Vulture, "
            "Bosco dell'Incoronata (Foggia), Parco dell'Ofanto, Saline di Margherita di Savoia, "
            "Subappennino Dauno (Bovino, Deliceto, Accadia). Escludi gare podistiche o sport."
        )
    },
    {
        "nome": "Agente 5 - Luoghi Permanenti & Attrazioni Weekend (50 km)",
        "tipo_contenuto": "luogo",
        "categoria_default": "Luoghi da visitare",
        "missione": (
            "Cerca su Google i principali luoghi permanenti, castelli, aree archeologiche, borghi "
            "storici e riserve naturali visitabili nel weekend entro 50 km da Cerignola: Castello "
            "Federiciano di Melfi, Laghi di Monticchio, Parco Archeologico e Ipogei di Canosa, "
            "Castel del Monte (Andria), Castello Svevo di Barletta, Cattedrale e Porto di Trani, "
            "Borgo di Bovino, Riserva Saline di Margherita di Savoia, Piano delle Fosse di Cerignola."
        )
    }
]

MESI_IT = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12
}

GIORNI_SETTIMANA_OFFSET = {
    "lunedì": 0, "lunedi": 0,
    "martedì": 1, "martedi": 1,
    "mercoledì": 2, "mercoledi": 2,
    "giovedì": 3, "giovedi": 3,
    "venerdì": 4, "venerdi": 4,
    "sabato": 5,
    "domenica": 6
}


def priorita_cerchio_cerignola(citta):
    c = (citta or "").strip().lower()
    if c == "cerignola":
        return 0
    if c in CINTURA_25_KM:
        return 1
    if c in CINTURA_50_KM:
        return 2
    return 3


def etichetta_fascia_km(citta):
    p = priorita_cerchio_cerignola(citta)
    if p == 0:
        return "Cerignola (0 km)"
    if p == 1:
        return "Prima cintura (entro 25 km)"
    if p == 2:
        return "Seconda cintura (entro 50 km)"
    return "Oltre 50 km / Altra area"


def oggi_iso():
    return datetime.now().strftime("%Y-%m-%d")


def limite_futuro_iso(giorni=180):
    return (datetime.now() + timedelta(days=giorni)).strftime("%Y-%m-%d")


def carica_json(percorso):
    try:
        with open(percorso, "r", encoding="utf-8") as f:
            dati = json.load(f)
            return dati if isinstance(dati, list) else []
    except Exception:
        return []


def normalizza_citta(ev, citta_default):
    citta_raw = (ev.get("citta") or "").strip().lower()
    luogo_raw = (ev.get("luogo") or "").strip().lower()
    titolo_raw = (ev.get("titolo") or "").strip().lower()
    desc_raw = (ev.get("descrizione") or "").strip().lower()

    for campo in (citta_raw, luogo_raw, titolo_raw, desc_raw):
        for chiave, nome_pulito in CITTA_TARGET_MAP.items():
            if re.search(rf"\b{re.escape(chiave)}\b", campo):
                return nome_pulito

    if citta_raw:
        return ev.get("citta").strip().title()
    return citta_default


def normalizza_categoria(cat_raw):
    chiave = (cat_raw or "").strip().lower()
    if chiave in MAPPA_CATEGORIE:
        return MAPPA_CATEGORIE[chiave]
    for valida in CATEGORIE_VALIDE:
        if chiave == valida.lower():
            return valida
    return "Altro"


def normalizza_fonte_url(url_raw, citta_pulita, urls_grounding_validi):
    candidato = (url_raw or "").strip()
    if candidato.startswith(("http://", "https://")):
        parsed = urlparse(candidato)
        dominio = parsed.netloc.lower()
        path = parsed.path.strip("/")
        if candidato in urls_grounding_validi:
            return candidato
        if dominio in DOMINI_FONTI_CONSENTITI:
            return candidato
        if dominio and path and "google.com" not in dominio and "example.com" not in dominio:
            return candidato
    return FALLBACK_URL_PER_CITTA.get(citta_pulita, "https://www.cerignolaviva.it/eventi/")


def determina_tipo_contenuto(ev):
    tipo_raw = (ev.get("tipoContenuto") or "").strip().lower()
    categoria = (ev.get("categoria") or "").strip()
    data_testo = (ev.get("dataTesto") or "").lower()

    if tipo_raw in ("luogo", "permanente", "ricorrente"):
        return "luogo"
    if categoria == "Luoghi da visitare":
        return "luogo"
    if any(k in data_testo for k in ("tutto l'anno", "sempre aperto", "sempre visitabile", "ogni weekend", "permanente")):
        return "luogo"
    return "evento"


def pulisci_evento(ev, citta_fallback, urls_grounding_validi):
    citta = normalizza_citta(ev, citta_fallback)
    ev["citta"] = citta
    ev["categoria"] = normalizza_categoria(ev.get("categoria"))
    ev["titolo"] = re.sub(r"\s+", " ", (ev.get("titolo") or "")).strip()
    ev["luogo"] = re.sub(r"\s+", " ", (ev.get("luogo") or "")).strip()
    ev["descrizione"] = re.sub(r"\s+", " ", (ev.get("descrizione") or "")).strip()
    ev["dataTesto"] = re.sub(r"\s+", " ", (ev.get("dataTesto") or "")).strip()

    tipo = determina_tipo_contenuto(ev)
    ev["tipoContenuto"] = tipo

    if tipo == "luogo":
        ev["dataInizio"] = oggi_iso()
        ev["dataFine"] = limite_futuro_iso(90)
        if not ev["dataTesto"] or re.match(r"^\d{4}-\d{2}-\d{2}$", ev["dataTesto"]):
            ev["dataTesto"] = "Aperto tutto l'anno · Ideale nel weekend"
    else:
        ev["dataInizio"] = (ev.get("dataInizio") or "").strip()
        ev["dataFine"] = (ev.get("dataFine") or ev["dataInizio"]).strip()

    ev["costo"] = (ev.get("costo") or "Da verificare").strip()
    ev["indirizzoMappa"] = (ev.get("indirizzoMappa") or f"{ev['luogo']}, {citta}").strip()
    ev["fonteUrl"] = normalizza_fonte_url(ev.get("fonteUrl"), citta, urls_grounding_validi)
    return ev


def contiene_riferimento_passato(testo):
    t = (testo or "").lower()
    if re.search(r"\b(19\d{2}|20[01]\d|202[0-5])\b", t):
        return True
    if any(k in t for k in ("ieri", "settimana scorsa", "mese scorso", "edizione passata")):
        return True
    oggi_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    mesi_pattern = "|".join(list(MESI_IT.keys()) + ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"])
    abbr_mesi = {
        "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6,
        "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12
    }
    for m in re.finditer(rf"\b(\d{{1,2}})\s+({mesi_pattern})(?:\s+(202[6-9]))?\b", t):
        giorno = int(m.group(1))
        mese_str = m.group(2)
        mese = MESI_IT.get(mese_str) or abbr_mesi.get(mese_str[:3])
        anno = int(m.group(3)) if m.group(3) else oggi_dt.year
        if mese and 1 <= giorno <= 31:
            try:
                dt = datetime(anno, mese, giorno)
                if dt < oggi_dt:
                    return True
            except ValueError:
                continue
    return False


def evento_valido(ev):
    oggi = oggi_iso()
    max_data = limite_futuro_iso(180)
    data_inizio = (ev.get("dataInizio") or "").strip()
    data_fine = (ev.get("dataFine") or "").strip()
    data_testo = (ev.get("dataTesto") or "").lower()
    titolo = (ev.get("titolo") or "").strip()
    descrizione = (ev.get("descrizione") or "").strip()
    luogo = (ev.get("luogo") or "").strip().lower()
    categoria = (ev.get("categoria") or "").strip().lower()

    if categoria == "sport":
        return False
    if not titolo or not descrizione or len(titolo) < 4:
        return False
    if "centro / location di" in luogo or "piazza o spazio eventi" in luogo or "centro città" in luogo:
        return False
    if len(luogo) < 3 or "da confermare" in luogo or "da definire" in luogo:
        return False
    if "agg." in data_testo or "segnalato il" in data_testo:
        return False
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", data_fine) or data_fine < oggi or data_fine > max_data:
        return False
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", data_inizio) or data_inizio < oggi or data_inizio > data_fine or data_inizio > max_data:
        return False

    testo = f"{titolo} {descrizione} {data_testo}".lower()
    if any(p in testo for p in PAROLE_VIETATE):
        return False
    if contiene_riferimento_passato(f"{titolo} {data_testo}"):
        return False

    return True


def token_significativi(testo, citta=""):
    pulito = re.sub(r"[^a-z0-9àèéìòù\s]", " ", (testo or "").lower())
    citta_tokens = set(re.sub(r"[^a-z0-9àèéìòù\s]", " ", (citta or "").lower()).split())
    return {
        w for w in pulito.split()
        if len(w) >= 3 and w not in STOPWORDS_IT and w not in citta_tokens
    }


def date_compatibili(ev1, ev2):
    if ev1.get("tipoContenuto") == "luogo" and ev2.get("tipoContenuto") == "luogo":
        return True
    i1, f1 = ev1.get("dataInizio", ""), ev1.get("dataFine", "")
    i2, f2 = ev2.get("dataInizio", ""), ev2.get("dataFine", "")
    if not (i1 and f1 and i2 and f2):
        return i1 == i2
    if i1 == i2:
        return True
    try:
        d_i1 = datetime.strptime(i1, "%Y-%m-%d")
        d_f1 = datetime.strptime(f1, "%Y-%m-%d")
        d_i2 = datetime.strptime(i2, "%Y-%m-%d")
        d_f2 = datetime.strptime(f2, "%Y-%m-%d")
        if abs((d_i1 - d_i2).days) <= 1 and abs((d_f1 - d_f2).days) <= 1:
            return True
        return max(d_i1, d_i2) <= min(d_f1, d_f2)
    except Exception:
        return i1 == i2


def sono_duplicati(ev1, ev2):
    if (ev1.get("citta") or "").lower() != (ev2.get("citta") or "").lower():
        return False
    if not date_compatibili(ev1, ev2):
        return False

    citta = ev1.get("citta", "")
    t1 = re.sub(r"[^a-z0-9\s]", "", ev1.get("titolo", "").lower()).strip()
    t2 = re.sub(r"[^a-z0-9\s]", "", ev2.get("titolo", "").lower()).strip()

    if len(t1) >= 10 and len(t2) >= 10 and (t1 in t2 or t2 in t1):
        return True

    sim_titolo = SequenceMatcher(None, t1, t2).ratio()
    if sim_titolo >= 0.72:
        return True

    tok1 = token_significativi(ev1.get("titolo", ""), citta)
    tok2 = token_significativi(ev2.get("titolo", ""), citta)
    jaccard_titolo = 0.0
    if tok1 and tok2:
        intersezione = len(tok1 & tok2)
        jaccard_titolo = intersezione / len(tok1 | tok2)
        containment_titolo = intersezione / min(len(tok1), len(tok2))
        if jaccard_titolo >= 0.55 or (intersezione >= 2 and containment_titolo >= 0.80):
            return True

    l1 = re.sub(r"[^a-z0-9\s]", "", ev1.get("luogo", "").lower()).strip()
    l2 = re.sub(r"[^a-z0-9\s]", "", ev2.get("luogo", "").lower()).strip()
    sim_luogo = SequenceMatcher(None, l1, l2).ratio() if (l1 and l2) else 0.0
    if ev1.get("tipoContenuto") == "luogo" and ev2.get("tipoContenuto") == "luogo" and sim_luogo >= 0.80:
        return True
    if sim_luogo >= 0.75 and jaccard_titolo >= 0.35:
        return True

    return False


def is_url_articolo_specifico(url):
    if not url:
        return False
    path = urlparse(url).path.rstrip("/")
    return path not in ("", "/eventi", "/eventi/weekend", "/category/eventi")


def unisci_eventi(esistente, nuovo):
    risultato = dict(esistente)
    if len(nuovo.get("titolo", "")) > len(risultato.get("titolo", "")) and len(nuovo.get("titolo", "")) <= 85:
        risultato["titolo"] = nuovo["titolo"]
    if len(nuovo.get("descrizione", "")) > len(risultato.get("descrizione", "")):
        risultato["descrizione"] = nuovo["descrizione"]
    if risultato.get("costo") in ("", "Da verificare") and nuovo.get("costo") not in ("", "Da verificare"):
        risultato["costo"] = nuovo["costo"]
    if not is_url_articolo_specifico(risultato.get("fonteUrl")) and is_url_articolo_specifico(nuovo.get("fonteUrl")):
        risultato["fonteUrl"] = nuovo["fonteUrl"]
    if len(nuovo.get("luogo", "")) > len(risultato.get("luogo", "")):
        risultato["luogo"] = nuovo["luogo"]
        risultato["indirizzoMappa"] = nuovo.get("indirizzoMappa", risultato.get("indirizzoMappa", ""))
    return risultato


def estrai_json_ld(soup):
    risultati = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw = script.string or script.get_text()
            if not raw:
                continue
            dati = json.loads(raw)
            oggetti = dati if isinstance(dati, list) else [dati]
            for obj in oggetti:
                if not isinstance(obj, dict):
                    continue
                tipo = str(obj.get("@type", ""))
                if any(k in tipo for k in ["Event", "MusicEvent", "SocialEvent", "Festival"]):
                    nome = re.sub(r"\s+", " ", str(obj.get("name", ""))).strip()
                    inizio = str(obj.get("startDate", "")).strip()
                    fine = str(obj.get("endDate", "")).strip()
                    loc = obj.get("location", {})
                    luogo = loc.get("name", "") if isinstance(loc, dict) else str(loc)
                    ind = ""
                    if isinstance(loc, dict) and isinstance(loc.get("address"), dict):
                        addr = loc["address"]
                        ind = f"{addr.get('streetAddress', '')} {addr.get('addressLocality', '')}".strip()
                    if nome:
                        risultati.append(f"META_EVENTO: {nome} | Dal: {inizio} | Al: {fine} | Luogo: {luogo} ({ind})")
        except Exception:
            continue
    return risultati


def raccogli_testo_con_dettagli(url_indice, citta_fonte):
    testi = []
    try:
        r = requests.get(url_indice, headers=HEADERS, timeout=15)
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        meta_indice = estrai_json_ld(soup)
        if meta_indice:
            testi.append(f"[{citta_fonte}] FONTE_INDICE ({url_indice}) METADATI:\n" + "\n".join(meta_indice[:12]))

        for tag in soup(["script", "style", "nav", "footer", "aside", "form"]):
            tag.decompose()

        link_prioritari = []
        link_secondari = []
        righe_con_link = []
        dominio_base = "/".join(url_indice.split("/")[:3])
        anno_corrente = datetime.now().year
        anni_vecchi = [f"/{y}/" for y in range(2010, anno_corrente)]

        for a in soup.find_all("a", href=True):
            href = urljoin(url_indice, a["href"]).split("#")[0]
            if not href.startswith(dominio_base) or href.rstrip("/") == url_indice.rstrip("/"):
                continue
            low_href = href.lower()
            if any(x in low_href for x in ["/tag/", "/author/", "/page/", "login", "privacy", "cookie"] + anni_vecchi):
                continue

            titolo_link = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            if len(titolo_link) < 15:
                continue

            voce = f"- {titolo_link} [ARTICOLO: {href}]"
            if voce not in righe_con_link:
                righe_con_link.append(voce)

            if any(k in f"{low_href} {titolo_link.lower()}" for k in PAROLE_PRIORITA_LINK):
                if href not in link_prioritari:
                    link_prioritari.append(href)
            else:
                if href not in link_secondari:
                    link_secondari.append(href)

        if righe_con_link:
            testi.append(f"[{citta_fonte}] ELENCO_ARTICOLI:\n" + "\n".join(righe_con_link[:25]))

        link_candidati = (link_prioritari + link_secondari)[:10]
        for link in link_candidati:
            try:
                rp = requests.get(link, headers=HEADERS, timeout=10)
                rp.encoding = rp.apparent_encoding or "utf-8"
                sp = BeautifulSoup(rp.text, "html.parser")
                meta_scheda = estrai_json_ld(sp)
                for tag in sp(["script", "style", "nav", "footer", "aside", "form"]):
                    tag.decompose()
                titolo_p = sp.find(["h1", "h2"])
                titolo_str = re.sub(r"\s+", " ", titolo_p.get_text(" ", strip=True)) if titolo_p else ""
                corpo_p = []
                for p in sp.find_all(["p", "time", "li"]):
                    txt = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
                    if 15 <= len(txt) <= 320 and txt not in corpo_p:
                        corpo_p.append(txt)
                extra = f" [{' ; '.join(meta_scheda[:2])}]" if meta_scheda else ""
                if corpo_p or meta_scheda:
                    testi.append(f"[{citta_fonte}] SCHEDA ({link}): {titolo_str}{extra} | {' | '.join(corpo_p[:5])}")
            except Exception:
                continue
    except Exception as e:
        print("Errore lettura:", url_indice, e)

    return "\n\n".join(testi)[:9000]


def get_endpoints_e_modelli(api_key):
    modelli = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
    if api_key.startswith("AQ."):
        def build_urls(modello):
            return [
                f"https://generativelanguage.googleapis.com/v1beta/models/{modello}:generateContent?key={api_key}",
                f"https://aiplatform.googleapis.com/v1/publishers/google/models/{modello}:generateContent?key={api_key}"
            ]
        return modelli, build_urls
    else:
        def build_urls(modello):
            return [
                f"https://generativelanguage.googleapis.com/v1beta/models/{modello}:generateContent?key={api_key}"
            ]
        return modelli, build_urls


def chiamata_gemini_universale(api_key, prompt, label_log, usa_search=False, json_mode=False):
    modelli, build_urls = get_endpoints_e_modelli(api_key)

    for modello in modelli:
        gen_config = {"temperature": 0.1}
        if json_mode:
            gen_config["responseMimeType"] = "application/json"
        if "2.5" in modello:
            gen_config["thinkingConfig"] = {"thinkingBudget": 0}

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": gen_config
        }
        if usa_search:
            payload["tools"] = [{"google_search": {}}]

        for endpoint in build_urls(modello):
            for tentativo in range(1, 3):
                try:
                    resp = requests.post(endpoint, json=payload, timeout=55)
                    if resp.status_code == 404:
                        print(f"[{label_log}] {modello} -> 404: {resp.text[:180]}")
                        break
                    if resp.status_code == 400 and usa_search and "tools" in payload:
                        print(f"[{label_log}] {modello} -> 400 con google_search, riprovo senza tool...")
                        payload.pop("tools", None)
                        continue
                    if resp.status_code == 429:
                        print(f"[{label_log}] Quota 429 su {modello}, attendo 62s...")
                        time.sleep(62)
                        continue
                    if resp.status_code in (500, 502, 503, 504):
                        print(f"[{label_log}] HTTP {resp.status_code} su {modello}, ritento...")
                        if tentativo < 2:
                            time.sleep(15)
                            continue
                        break
                    if resp.status_code != 200:
                        print(f"[{label_log}] HTTP {resp.status_code} su {modello}: {resp.text[:250]}")
                        break

                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        print(f"[{label_log}] Nessun candidate da {modello}: {json.dumps(data)[:220]}")
                        break

                    cand = candidates[0]
                    parts = cand.get("content", {}).get("parts", [])
                    testo = "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()
                    if not testo:
                        break

                    urls = set()
                    fonti_chunks = []
                    grounding = cand.get("groundingMetadata", {})
                    for ch in grounding.get("groundingChunks", []):
                        web = ch.get("web", {})
                        uri = (web.get("uri") or "").strip()
                        title = (web.get("title") or "").strip()
                        if uri.startswith(("http://", "https://")):
                            urls.add(uri)
                            fonti_chunks.append(f"- {title}: {uri}" if title else f"- {uri}")

                    return testo, urls, fonti_chunks, modello

                except Exception as e:
                    print(f"[{label_log}] Eccezione ({modello}, tentativo {tentativo}/2):", e)
                    if tentativo < 2:
                        time.sleep(12)

    return "", set(), [], ""


def esegui_agente_ricerca(api_key, agente):
    oggi = oggi_iso()
    nome = agente["nome"]
    cat_def = agente["categoria_default"]
    tipo_cont = agente.get("tipo_contenuto", "evento")
    missione = agente["missione"]

    if tipo_cont == "luogo":
        istruzione_temporale = (
            "Individua luoghi permanenti, castelli, borghi, parchi e riserve naturali realmente "
            "visitabili nel weekend entro 50 km da Cerignola. Indica tipoContenuto='luogo' e come "
            "disponibilità indica gli orari o 'Aperto tutto l'anno · Ideale nel weekend'."
        )
    else:
        istruzione_temporale = (
            f"Raccogli TUTTI gli eventi, feste, serate, spettacoli, escursioni, sagre e iniziative "
            f"reali in corso oggi {oggi} o in programma nei prossimi giorni e weekend (entro 45 giorni). "
            f"Indica tipoContenuto='evento'."
        )

    prompt = f"""Sei '{nome}' di 'Che Si Fa Cerignola'. Oggi è {oggi}.
{missione}

{istruzione_temporale}
REGOLE:
- Escludi eventi già conclusi prima di {oggi}, sport, convegni politici/istituzionali e cronaca.
- Riporta ogni risultato trovato indicando: Tipo ({tipo_cont}), Titolo, Città esatta, Categoria ({cat_def}), Data e ora leggibile, Data inizio (YYYY-MM-DD), Data fine (YYYY-MM-DD), Luogo esatto, Costo, Descrizione breve (1 frase) e URL della fonte web.
"""

    testo, urls, fonti_chunks, modello_usato = chiamata_gemini_universale(
        api_key, prompt, nome, usa_search=True, json_mode=False
    )
    if not testo:
        return "", set()

    blocco = f"=== {nome} (tipoContenuto={tipo_cont}) ===\n{testo}"
    if fonti_chunks:
        blocco += "\nFONTI_VERIFICATE_GOOGLE:\n" + "\n".join(fonti_chunks[:12])
    print(f"[{nome}] OK ({modello_usato}): {len(testo)} caratteri, {len(urls)} fonti Google.")
    return blocco, urls


def stima_data_da_testo(testo_grezzo):
    oggi = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    max_dt = oggi + timedelta(days=120)
    t_low = (testo_grezzo or "").lower()

    if contiene_riferimento_passato(t_low):
        return None, None, False

    for m in re.finditer(r"\b(202[6-9])-(\d{2})-(\d{2})\b", t_low):
        try:
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if oggi <= dt <= max_dt:
                return dt.strftime("%Y-%m-%d"), dt.strftime("%Y-%m-%d"), True
        except ValueError:
            continue

    mesi_pattern = "|".join(list(MESI_IT.keys()) + ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"])
    abbr_mesi = {
        "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6,
        "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12
    }
    for m in re.finditer(rf"\b(\d{{1,2}})\s+({mesi_pattern})(?:\s+(202[6-9]))?\b", t_low):
        giorno = int(m.group(1))
        mese_str = m.group(2)
        mese = MESI_IT.get(mese_str) or abbr_mesi.get(mese_str[:3])
        anno = int(m.group(3)) if m.group(3) else oggi.year
        if mese and 1 <= giorno <= 31:
            try:
                dt = datetime(anno, mese, giorno)
                if dt < oggi and not m.group(3):
                    dt = datetime(anno + 1, mese, giorno)
                if oggi <= dt <= max_dt:
                    d_str = dt.strftime("%Y-%m-%d")
                    return d_str, d_str, True
            except ValueError:
                continue

    if "weekend" in t_low or "fine settimana" in t_low:
        giorni_al_sabato = (5 - oggi.weekday()) % 7
        sab = oggi + timedelta(days=giorni_al_sabato)
        dom = sab + timedelta(days=1)
        return sab.strftime("%Y-%m-%d"), dom.strftime("%Y-%m-%d"), True

    for nome_g, target_wd in GIORNI_SETTIMANA_OFFSET.items():
        if re.search(rf"\b{re.escape(nome_g)}\b", t_low):
            delta = (target_wd - oggi.weekday()) % 7
            dt = oggi + timedelta(days=delta)
            d_str = dt.strftime("%Y-%m-%d")
            return d_str, d_str, True

    return None, None, False


def classifica_categoria_euristica(testo):
    t = (testo or "").lower()
    if any(k in t for k in ("sagra", "degustazion", "cibo", "vino", "olio", "street food", "mercatin", "fiera")):
        return "Sagre & Food"
    if any(k in t for k in ("concerto", "musica", "live", "band", "cantante", "teatro", "spettacolo", "rassegna")):
        return "Musica & Concerti"
    if any(k in t for k in ("bambin", "famigl", "laboratori", "animazion", "natale", "babbo natale")):
        return "Famiglie & Bambini"
    if any(k in t for k in ("escursion", "trekking", "passeggiat", "natura", "parco", "riserva", "bosco", "saline")):
        return "Natura & Escursioni"
    if any(k in t for k in ("dj", "serata", "discotec", "club", "pub", "aperitivo", "apericena", "locale")):
        return "Locali & Serate"
    return "Attività diurne"


def estrai_fallback_da_testo(testo_grezzo, nome_blocco, citta_fallback):
    estratti = []
    visti = set()

    for m in re.finditer(r"-\s+([^\[\n]{15,120}?)\s*\[ARTICOLO:\s*(https?://[^\s\]]+)\]", testo_grezzo):
        titolo = re.sub(r"\s+", " ", m.group(1)).strip(" -–—|")
        url = m.group(2).strip()
        low_t = titolo.lower()
        if len(titolo) < 12 or any(p in low_t for p in PAROLE_VIETATE):
            continue
        if contiene_riferimento_passato(f"{low_t} {url.lower()}"):
            continue

        ha_segnale_evento = any(k in f"{low_t} {url.lower()}" for k in PAROLE_EVENTO_VALIDO)
        d_ini, d_fin, ha_data_esplicita = stima_data_da_testo(f"{titolo} {url}")
        if not ha_segnale_evento or not ha_data_esplicita or not d_ini or not d_fin:
            continue

        chiave = low_t
        if chiave in visti:
            continue
        visti.add(chiave)

        citta = normalizza_citta({"titolo": titolo, "descrizione": testo_grezzo[:300]}, citta_fallback)
        cat = classifica_categoria_euristica(f"{titolo} {url}")

        estratti.append({
            "tipoContenuto": "evento",
            "citta": citta,
            "categoria": cat,
            "titolo": titolo[:85],
            "dataTesto": f"Dal {d_ini}" if d_ini == d_fin else f"Dal {d_ini} al {d_fin}",
            "dataInizio": d_ini,
            "dataFine": d_fin,
            "luogo": f"Centro città, {citta}",
            "indirizzoMappa": f"{citta}",
            "costo": "Da verificare",
            "descrizione": f"Iniziativa segnalata su {urlparse(url).netloc}: {titolo}.",
            "fonteUrl": url
        })
        if len(estratti) >= 10:
            break

    print(f"[{nome_blocco}] Fallback locale ha estratto {len(estratti)} schede.")
    return estratti


def analizza_blocco_con_gemini(api_key, testo_grezzo, nome_blocco, citta_fallback):
    if not testo_grezzo.strip():
        return []

    if not api_key:
        return estrai_fallback_da_testo(testo_grezzo, nome_blocco, citta_fallback)

    oggi = oggi_iso()
    futuro_90 = limite_futuro_iso(90)
    prompt = f"""Sei il curatore di 'Che Si Fa Cerignola'. Oggi è {oggi}.
Analizza questi estratti per il blocco '{nome_blocco}' ed estrai TUTTI i veri eventi datati E i luoghi permanenti / attività ricorrenti nel raggio di 50 km da Cerignola:
- "Locali & Serate": DJ set, club, lounge bar, pub, live music, aperitivi musicali;
- "Attività serali": cene spettacolo, apericena, quiz night, karaoke, mercatini serali, iniziative dopo cena;
- "Famiglie & Bambini": laboratori, animazione, spettacoli per bambini, fattorie didattiche;
- "Natura & Escursioni": trekking, passeggiate guidate, uscite nella natura;
- "Attività diurne": mercatini, degustazioni, visite ed esperienze diurne;
- "Luoghi da visitare": castelli, borghi, aree archeologiche, parchi e attrazioni permanenti visitabili nel weekend;
- "Musica & Concerti", "Sagre & Food".

REGOLE RIGIDE:
1. Estrai TUTTI gli elementi validi presenti nel testo senza tralasciarne nessuno.
2. Per gli eventi datati ("tipoContenuto": "evento"), SCARTA quelli già conclusi prima di {oggi} o con date/anni passati.
3. Per i luoghi permanenti o attività ricorrenti ("tipoContenuto": "luogo"), imposta "dataInizio": "{oggi}" e "dataFine": "{futuro_90}".
4. SCARTA qualsiasi evento sportivo, convegni politici/istituzionali, incontri pubblici, conferenze, dibattiti, seminari, presentazioni di libri, salute/prevenzione, cronaca nera/giudiziaria, meteo e disservizi.
5. Per ogni voce riporta in "fonteUrl" l'URL specifico dell'articolo o della fonte web presente nel testo.

Restituisci SOLO un array JSON valido con oggetti aventi queste chiavi esatte:
- "tipoContenuto": "evento" (per appuntamenti con data precisa) oppure "luogo" (per luoghi permanenti da visitare o attività ricorrenti)
- "citta": città specifica dell'evento o luogo oppure "{citta_fallback}"
- "categoria": scegli SOLO tra "Locali & Serate", "Attività serali", "Musica & Concerti", "Sagre & Food", "Famiglie & Bambini", "Natura & Escursioni", "Attività diurne", "Luoghi da visitare", "Altro"
- "titolo": titolo pulito dell'evento o del luogo
- "dataTesto": data e ora leggibile (es. "Sab 28 Nov 2026 · Ore 22:00" oppure "Aperto tutto l'anno · Ideale nel weekend")
- "dataInizio": formato YYYY-MM-DD
- "dataFine": formato YYYY-MM-DD (deve essere >= "{oggi}")
- "luogo": nome esatto del locale, club, castello, parco, piazza o indirizzo
- "indirizzoMappa": luogo + via/piazza + città per Google Maps
- "costo": es. "Ingresso libero", "15€ con drink", oppure "Da verificare"
- "descrizione": 1 frase chiara e invitante su cosa si fa o si visita
- "fonteUrl": URL esatto della fonte

TESTO DA ANALIZZARE:
{testo_grezzo}
"""

    risposta, _, _, _ = chiamata_gemini_universale(
        api_key, prompt, nome_blocco, usa_search=False, json_mode=True
    )
    if not risposta:
        return estrai_fallback_da_testo(testo_grezzo, nome_blocco, citta_fallback)

    try:
        risposta = re.sub(r"^`{3}json\s*|`{3}$", "", risposta, flags=re.IGNORECASE).strip()
        eventi = json.loads(risposta)
        if isinstance(eventi, list) and eventi:
            return eventi
        return estrai_fallback_da_testo(testo_grezzo, nome_blocco, citta_fallback)
    except Exception as e:
        print(f"[{nome_blocco}] Errore parsing JSON:", e)
        return estrai_fallback_da_testo(testo_grezzo, nome_blocco, citta_fallback)


def genera_report_copertura(lista_finale, aggiunti, aggiornati):
    totale = len(lista_finale)
    per_tipo = Counter(ev.get("tipoContenuto", "evento") for ev in lista_finale)
    per_fascia = Counter(etichetta_fascia_km(ev.get("citta")) for ev in lista_finale)
    per_categoria = Counter(ev.get("categoria", "Altro") for ev in lista_finale)
    per_citta = Counter(ev.get("citta", "Sconosciuta") for ev in lista_finale)

    url_specifici = sum(1 for ev in lista_finale if is_url_articolo_specifico(ev.get("fonteUrl")))
    comuni_scoperti = [c for c in COMUNI_CHIAVE_MONITORAGGIO if per_citta.get(c, 0) == 0]

    report = {
        "aggiornatoAl": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "totaleContenuti": totale,
        "nuoviAggiunti": aggiunti,
        "aggiornati": aggiornati,
        "ripartizioneTipo": dict(per_tipo),
        "coperturaCerchiKm": dict(per_fascia),
        "ripartizioneCategorie": dict(per_categoria.most_common()),
        "topComuni": dict(per_citta.most_common(15)),
        "comuniChiaveScoperti": comuni_scoperti,
        "percentualeUrlSpecifici": round((url_specifici / totale * 100), 1) if totale else 0.0
    }

    with open("report_copertura.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("REPORT COPERTURA TERRITORIALE - CHE SI FA CERIGNOLA")
    print("=" * 60)
    print(f"Totale schede attive: {totale} (Eventi datati: {per_tipo.get('evento', 0)} | Luoghi permanenti: {per_tipo.get('luogo', 0)})")
    print(f"Novità questo run: +{aggiunti} aggiunti, {aggiornati} aggiornati | URL specifici: {report['percentualeUrlSpecifici']}%")
    print("\n--- Copertura per Cerchio Concentrico ---")
    for fascia in ("Cerignola (0 km)", "Prima cintura (entro 25 km)", "Seconda cintura (entro 50 km)", "Oltre 50 km / Altra area"):
        print(f"  * {fascia}: {per_fascia.get(fascia, 0)}")
    print("\n--- Copertura per Categoria ---")
    for cat, count in per_categoria.most_common():
        print(f"  * {cat}: {count}")
    print("\n--- Top Comuni Coperti ---")
    for cit, count in per_citta.most_common(10):
        print(f"  * {cit}: {count}")
    if comuni_scoperti:
        print("\n--- Comuni chiave (entro 50 km) attualmente a 0 schede ---")
        print("  " + ", ".join(comuni_scoperti))
    print("=" * 60 + "\n")


# ==============================================================================
# PIPELINE IBRIDA POTENZIATA: SCRAPING + 5 RICERCATORI + TELEMETRIA
# ==============================================================================
api_key = os.environ.get("GEMINI_API_KEY", "").strip()
modalita_api = "Vertex AI Express (AQ.)" if api_key.startswith("AQ.") else "Gemini AI Studio (AIza)"
print(f"Avvio pipeline | Modalità: {modalita_api} | Chiave presente: {bool(api_key)}")
urls_grounding_totali = set()

lista_consolidata = []
for ev_raw in carica_json("eventi.json"):
    ev = pulisci_evento(ev_raw, ev_raw.get("citta") or "Cerignola", urls_grounding_totali)
    if not evento_valido(ev):
        continue
    idx_dup = next((i for i, esist in enumerate(lista_consolidata) if sono_duplicati(esist, ev)), None)
    if idx_dup is None:
        lista_consolidata.append(ev)
    else:
        lista_consolidata[idx_dup] = unisci_eventi(lista_consolidata[idx_dup], ev)

nuovi_trovati = []

blocchi_locali = [
    ("Nord / Capitanata", "Cerignola", [f for f in FONTI_EVENTI if f["gruppo"] == "Nord / Capitanata"]),
    ("Costa BAT e Gargano", "Barletta", [f for f in FONTI_EVENTI if f["gruppo"] == "Costa BAT e Gargano"]),
]

for idx, (nome_blocco, citta_fallback, fonti_gruppo) in enumerate(blocchi_locali):
    testi_gruppo = []
    for fonte in fonti_gruppo:
        t = raccogli_testo_con_dettagli(fonte["url"], fonte["citta"])
        if t:
            testi_gruppo.append(t)
    testo_unito = "\n\n---\n\n".join(testi_gruppo)[:26000]
    print(f"Blocco locale '{nome_blocco}': {len(testo_unito)} caratteri raccolti")
    if idx > 0 and testo_unito.strip():
        time.sleep(8)
    estratti = analizza_blocco_con_gemini(api_key, testo_unito, nome_blocco, citta_fallback)
    print(f"Blocco locale '{nome_blocco}': {len(estratti)} schede estratte")
    for ev_raw in estratti:
        ev = pulisci_evento(ev_raw, citta_fallback, urls_grounding_totali)
        if evento_valido(ev):
            nuovi_trovati.append(ev)

raccolta_agenti = []
if api_key:
    for idx, agente in enumerate(AGENTI_RICERCA):
        time.sleep(8)
        blocco_agente, urls_trovati = esegui_agente_ricerca(api_key, agente)
        urls_grounding_totali.update(urls_trovati)
        if blocco_agente:
            raccolta_agenti.append(blocco_agente)

    testo_agenti = "\n\n---\n\n".join(raccolta_agenti)[:30000]
    print(f"Raccolta totale dai 5 ricercatori: {len(testo_agenti)} caratteri")
    if testo_agenti.strip():
        time.sleep(8)
        estratti_web = analizza_blocco_con_gemini(api_key, testo_agenti, "Ricercatori Web 50 km (Eventi & Luoghi)", "Cerignola")
        print(f"Blocco Ricercatori Web: {len(estratti_web)} schede estratte")
        for ev_raw in estratti_web:
            ev = pulisci_evento(ev_raw, "Cerignola", urls_grounding_totali)
            if evento_valido(ev):
                nuovi_trovati.append(ev)

aggiunti = 0
aggiornati = 0
for ev in nuovi_trovati:
    idx_dup = next((i for i, esist in enumerate(lista_consolidata) if sono_duplicati(esist, ev)), None)
    if idx_dup is None:
        lista_consolidata.append(ev)
        aggiunti += 1
    else:
        prima = lista_consolidata[idx_dup]
        dopo = unisci_eventi(prima, ev)
        if dopo != prima:
            lista_consolidata[idx_dup] = dopo
            aggiornati += 1

lista_finale = sorted(
    lista_consolidata,
    key=lambda x: (
        1 if x.get("tipoContenuto") == "luogo" else 0,
        x.get("dataInizio", "9999-12-31"),
        priorita_cerchio_cerignola(x.get("citta")),
        x.get("titolo", "").lower()
    )
)

with open("eventi.json", "w", encoding="utf-8") as f:
    json.dump(lista_finale, f, ensure_ascii=False, indent=2)

genera_report_copertura(lista_finale, aggiunti, aggiornati)
