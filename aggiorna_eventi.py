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
    "teatro": "Musica & Concerti",
    "spettacolo": "Musica & Concerti",
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
    "cultura & spettacoli": "Attività diurne",
    "cultura": "Attività diurne"
}

PAROLE_VIETATE = [
    "adblocker", "ci stai leggendo", "disattiva", "cookie", "abbonati",
    "registrati", "newsletter", "pubblicità", "pubblicita", "scrivi alla redazione",
    "attualità", "attualita", "alimentazione", "nutrizione", "dieta",
    "saperi di frontiera", "carnevale", "notte bianca", "s. antonio", "san antonio",
    "festeggiamenti in onore", "inaugurata", "inaugurato", "inaugurazione monumento",
    "monumento", "vescovo", "club per l", "ballerino", "mostra di pittura",
    "mostra fotografica", "città mariana", "citta mariana", "devozione",
    "anniversario", "solidarietà", "solidarieta", "maglia", "beneficenza",
    "raccolta fondi", "parrocchia", "diocesi", "messa", "processione", "storia della",
    "bilancio", "successo per", "si è svolta", "si è tenuto", "conclusa", "concluso",
    "meteo", "libeccio", "venti forti", "pioggia", "allerta", "neve", "freddo",
    "cielo sereno", "°c", "min ", "max ", "archivio", "svolta ue", "cop31",
    "frode fiscale", "riciclaggio", "indagati", "sequestri",
    "scontro tra auto", "morti e feriti", "colpisce il padre", "martello", "leccese",
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
    "stadio", "palazzetto", "sbanca", "vittoria esterna", "volley",
    "piano delle fosse granarie", "ipogei lagrasta", "castel del monte e parco nazionale"
]

PAROLE_PRIORITA_LINK = [
    "event", "serat", "seral", "notturn", "dopocena", "apericena", "concert",
    "dj", "live", "sagra", "mercatin", "festival", "festa", "musica", "club",
    "pub", "aperitiv", "lounge", "discotec", "night", "drink", "karaoke",
    "quiz", "famigl", "bambin", "natale", "escursion", "passeggiat", "trekking",
    "teatro", "spettacol", "weekend"
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
        "nome": "Agente 1 - Eventi, Teatro & Serate (Cerignola, Foggia, BAT)",
        "categoria_default": "Locali & Serate",
        "missione": (
            "Cerca su Google gli eventi reali, spettacoli teatrali (es. Teatro Mercadante Cerignola, "
            "Teatro Giordano Foggia, Teatro Curci Barletta), concerti, serate nei locali e DJ set "
            "in programma tra fine novembre e dicembre 2026 a Cerignola, Foggia, Barletta, Trani, "
            "Andria, Bisceglie e Canosa di Puglia. Escludi sport, politica, attualità, religione e convegni."
        )
    },
    {
        "nome": "Agente 2 - Mercatini di Natale, Sagre & Feste (50 km)",
        "categoria_default": "Sagre & Food",
        "missione": (
            "Cerca su Google mercatini di Natale, sagre, degustazioni e feste di paese con date "
            "confermate tra novembre e dicembre 2026 entro 50 km da Cerignola: Cerignola, Foggia, "
            "Candela (Casa di Babbo Natale), Bovino, Deliceto, Ascoli Satriano, Melfi, Venosa, "
            "Rionero in Vulture, Barletta, Trani, Andria, Margherita di Savoia."
        )
    },
    {
        "nome": "Agente 3 - Famiglie, Bambini & Spettacoli",
        "categoria_default": "Famiglie & Bambini",
        "missione": (
            "Cerca su Google eventi per famiglie e bambini, villaggi di Natale, spettacoli per "
            "ragazzi e laboratori datati tra novembre e dicembre 2026 a Cerignola, Foggia, Candela, "
            "Barletta, Andria, Trani, Canosa di Puglia e Melfi."
        )
    },
    {
        "nome": "Agente 4 - Natura & Escursioni Guidate (50 km)",
        "categoria_default": "Natura & Escursioni",
        "missione": (
            "Cerca su Google escursioni guidate, trekking e passeggiate naturalistiche con data "
            "confermata nei prossimi weekend entro 50 km da Cerignola: Laghi di Monticchio, Monte "
            "Vulture, Bosco dell'Incoronata (Foggia), Parco dell'Ofanto, Saline di Margherita di "
            "Savoia, Monti Dauni (Bovino, Deliceto, Accadia). Escludi gare podistiche o sport."
        )
    }
]

MESI_IT = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12
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


def limite_futuro_iso(giorni=120):
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


def pulisci_evento(ev, citta_fallback, urls_grounding_validi):
    citta = normalizza_citta(ev, citta_fallback)
    ev["tipoContenuto"] = "evento"
    ev["citta"] = citta
    ev["categoria"] = normalizza_categoria(ev.get("categoria"))
    ev["titolo"] = re.sub(r"\s+", " ", (ev.get("titolo") or "")).strip()
    ev["luogo"] = re.sub(r"\s+", " ", (ev.get("luogo") or "")).strip()
    ev["descrizione"] = re.sub(r"\s+", " ", (ev.get("descrizione") or "")).strip()
    ev["dataTesto"] = re.sub(r"\s+", " ", (ev.get("dataTesto") or "")).strip()
    ev["dataInizio"] = (ev.get("dataInizio") or "").strip()[:10]
    ev["dataFine"] = (ev.get("dataFine") or ev["dataInizio"]).strip()[:10]
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
    max_data = limite_futuro_iso(120)
    data_inizio = (ev.get("dataInizio") or "").strip()
    data_fine = (ev.get("dataFine") or "").strip()
    data_testo = (ev.get("dataTesto") or "").lower()
    titolo = (ev.get("titolo") or "").strip()
    descrizione = (ev.get("descrizione") or "").strip()
    desc_low = descrizione.lower()
    luogo = (ev.get("luogo") or "").strip().lower()
    categoria = (ev.get("categoria") or "").strip().lower()

    if categoria in ("sport", "luoghi da visitare"):
        return False
    if not titolo or not descrizione or len(titolo) < 5:
        return False
    # Scarta schede statiche o generate dai vecchi fallback
    if any(k in data_testo for k in ("ideale nel weekend", "visitabile nel weekend", "aperto tutto l'anno", "agg.", "segnalato il")):
        return False
    if desc_low.startswith("iniziativa segnalata su") or desc_low.startswith("appuntamento segnalato su"):
        return False
    if any(luogo.startswith(pref) for pref in ("centro città", "centro citta", "location evento", "centro / location di")):
        return False
    if len(luogo) < 3 or "da confermare" in luogo or "da definire" in luogo:
        return False
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", data_fine) or data_fine < oggi or data_fine > max_data:
        return False
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", data_inizio) or data_inizio < oggi or data_inizio > data_fine or data_inizio > max_data:
        return False

    testo = f"{titolo} {descrizione} {data_testo} {luogo}".lower()
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


def esplodi_oggetti_json_ld(dati):
    oggetti = []
    if isinstance(dati, list):
        for item in dati:
            oggetti.extend(esplodi_oggetti_json_ld(item))
    elif isinstance(dati, dict):
        if "@graph" in dati and isinstance(dati["@graph"], list):
            for item in dati["@graph"]:
                oggetti.extend(esplodi_oggetti_json_ld(item))
        else:
            oggetti.append(dati)
    return oggetti


def estrai_eventi_strutturati_json_ld(soup, citta_fonte, url_pagina):
    testi_meta = []
    eventi_diretti = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw = script.string or script.get_text()
            if not raw:
                continue
            dati = json.loads(raw)
            for obj in esplodi_oggetti_json_ld(dati):
                tipo = str(obj.get("@type", ""))
                if not any(k in tipo for k in ["Event", "MusicEvent", "SocialEvent", "Festival", "TheaterEvent", "ExhibitionEvent"]):
                    continue
                nome = re.sub(r"\s+", " ", str(obj.get("name", ""))).strip()
                inizio = str(obj.get("startDate", "")).strip()[:10]
                fine = str(obj.get("endDate", "")).strip()[:10] or inizio
                url_ev = str(obj.get("url", "")).strip() or url_pagina
                desc = re.sub(r"\s+", " ", str(obj.get("description", ""))).strip()[:220]
                loc = obj.get("location", {})
                luogo = loc.get("name", "") if isinstance(loc, dict) else str(loc)
                luogo = re.sub(r"\s+", " ", luogo).strip()
                citta_loc = citta_fonte
                ind = ""
                if isinstance(loc, dict) and isinstance(loc.get("address"), dict):
                    addr = loc["address"]
                    citta_loc = addr.get("addressLocality") or citta_fonte
                    ind = f"{addr.get('streetAddress', '')} {citta_loc}".strip()

                if nome:
                    testi_meta.append(f"META_EVENTO: {nome} | Dal: {inizio} | Al: {fine} | Luogo: {luogo} ({ind}) | URL: {url_ev}")
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", inizio) and luogo:
                        eventi_diretti.append({
                            "tipoContenuto": "evento",
                            "citta": citta_loc,
                            "categoria": "Attività diurne",
                            "titolo": nome[:85],
                            "dataTesto": f"Dal {inizio}" if inizio == fine else f"Dal {inizio} al {fine}",
                            "dataInizio": inizio,
                            "dataFine": fine,
                            "luogo": luogo,
                            "indirizzoMappa": ind or f"{luogo}, {citta_loc}",
                            "costo": "Da verificare",
                            "descrizione": desc or f"Evento in programma presso {luogo}.",
                            "fonteUrl": url_ev
                        })
        except Exception:
            continue

    return testi_meta, eventi_diretti


def raccogli_testo_con_dettagli(url_indice, citta_fonte):
    testi = []
    eventi_strutturati = []
    try:
        r = requests.get(url_indice, headers=HEADERS, timeout=15)
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        meta_indice, ev_indice = estrai_eventi_strutturati_json_ld(soup, citta_fonte, url_indice)
        eventi_strutturati.extend(ev_indice)
        if meta_indice:
            testi.append(f"[{citta_fonte}] FONTE_INDICE ({url_indice}) METADATI:\n" + "\n".join(meta_indice[:15]))

        for tag in soup(["script", "style", "nav", "footer", "aside", "form"]):
            tag.decompose()

        link_prioritari = []
        righe_con_link = []
        dominio_base = "/".join(url_indice.split("/")[:3])
        anno_corrente = datetime.now().year
        anni_vecchi = [f"/{y}/" for y in range(2010, anno_corrente)]

        for a in soup.find_all("a", href=True):
            href = urljoin(url_indice, a["href"]).split("#")[0]
            if not href.startswith(dominio_base) or href.rstrip("/") == url_indice.rstrip("/"):
                continue
            low_href = href.lower()
            # Accetta SOLO link di sezione eventi ed esclude archivi anni passati
            if "/event" not in low_href:
                continue
            if any(x in low_href for x in ["/tag/", "/author/", "/page/", "login", "privacy", "cookie"] + anni_vecchi):
                continue

            titolo_link = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            if len(titolo_link) < 15 or any(p in titolo_link.lower() for p in PAROLE_VIETATE):
                continue

            voce = f"- {titolo_link} [ARTICOLO: {href}]"
            if voce not in righe_con_link:
                righe_con_link.append(voce)

            if href not in link_prioritari:
                link_prioritari.append(href)

        if righe_con_link:
            testi.append(f"[{citta_fonte}] ELENCO_EVENTI:\n" + "\n".join(righe_con_link[:25]))

        for link in link_prioritari[:10]:
            try:
                rp = requests.get(link, headers=HEADERS, timeout=10)
                rp.encoding = rp.apparent_encoding or "utf-8"
                sp = BeautifulSoup(rp.text, "html.parser")
                meta_scheda, ev_scheda = estrai_eventi_strutturati_json_ld(sp, citta_fonte, link)
                eventi_strutturati.extend(ev_scheda)
                for tag in sp(["script", "style", "nav", "footer", "aside", "form"]):
                    tag.decompose()
                titolo_p = sp.find(["h1", "h2"])
                titolo_str = re.sub(r"\s+", " ", titolo_p.get_text(" ", strip=True)) if titolo_p else ""
                if any(p in titolo_str.lower() for p in PAROLE_VIETATE):
                    continue
                corpo_p = []
                for p in sp.find_all(["p", "time", "li"]):
                    txt = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
                    if any(w in txt.lower() for w in ("adblocker", "ci stai leggendo", "cookie", "abbonati", "newsletter")):
                        continue
                    if 15 <= len(txt) <= 320 and txt not in corpo_p:
                        corpo_p.append(txt)
                extra = f" [{' ; '.join(meta_scheda[:2])}]" if meta_scheda else ""
                if corpo_p or meta_scheda:
                    testi.append(f"[{citta_fonte}] SCHEDA ({link}): {titolo_str}{extra} | {' | '.join(corpo_p[:5])}")
            except Exception:
                continue
    except Exception as e:
        print("Errore lettura:", url_indice, e)

    return "\n\n".join(testi)[:9000], eventi_strutturati


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
    missione = agente["missione"]

    prompt = f"""Sei '{nome}' di 'Che Si Fa Cerignola'. Oggi è {oggi}.
{missione}

Raccogli TUTTI gli eventi reali e datati in programma oggi {oggi} o nei prossimi giorni e weekend (entro 45 giorni).
REGOLE:
- Escludi eventi già conclusi prima di {oggi}, sport, attualità, religione/devozione, beneficenza, convegni su alimentazione/salute/politica e cronaca.
- Riporta ogni evento trovato indicando: Titolo, Città esatta, Categoria ({cat_def}), Data e ora leggibile, Data inizio (YYYY-MM-DD), Data fine (YYYY-MM-DD), Luogo esatto (nome teatro, locale, piazza o struttura), Costo, Descrizione breve (1 frase) e URL della fonte web.
"""

    testo, urls, fonti_chunks, modello_usato = chiamata_gemini_universale(
        api_key, prompt, nome, usa_search=True, json_mode=False
    )
    if not testo:
        return "", set()

    blocco = f"=== {nome} ===\n{testo}"
    if fonti_chunks:
        blocco += "\nFONTI_VERIFICATE_GOOGLE:\n" + "\n".join(fonti_chunks[:12])
    print(f"[{nome}] OK ({modello_usato}): {len(testo)} caratteri, {len(urls)} fonti Google.")
    return blocco, urls


def analizza_blocco_con_gemini(api_key, testo_grezzo, nome_blocco, citta_fallback):
    if not testo_grezzo.strip() or not api_key:
        return []

    oggi = oggi_iso()
    prompt = f"""Sei il curatore di 'Che Si Fa Cerignola'. Oggi è {oggi}.
Analizza questi estratti per il blocco '{nome_blocco}' ed estrai TUTTI i veri eventi datati nel raggio di 50 km da Cerignola:
- "Locali & Serate": DJ set, club, lounge bar, pub, live music, aperitivi musicali;
- "Attività serali": cene spettacolo, apericena, quiz night, karaoke, mercatini serali, iniziative dopo cena;
- "Musica & Concerti": concerti, spettacoli teatrali, musical, cabaret, rassegne;
- "Sagre & Food": sagre, mercatini natalizi, degustazioni;
- "Famiglie & Bambini": laboratori, animazione, spettacoli per bambini, villaggi di Natale;
- "Natura & Escursioni": trekking, passeggiate guidate, uscite nella natura;
- "Attività diurne": visite guidate, mostre d'arte ed esperienze diurne.

REGOLE RIGIDE:
1. Estrai SOLO veri eventi ricreativi/culturali con data certa >= "{oggi}".
2. SCARTA sport, attualità, religione/devozione, anniversari storici, beneficenza, convegni/seminari su alimentazione o salute, politica/istituzioni, presentazioni di libri, banner anti-adblock, cronaca e meteo.
3. Per ogni voce riporta in "fonteUrl" l'URL specifico dell'articolo o della fonte web presente nel testo.

Restituisci SOLO un array JSON valido con oggetti aventi queste chiavi esatte:
- "tipoContenuto": "evento"
- "citta": città specifica dell'evento oppure "{citta_fallback}"
- "categoria": scegli SOLO tra "Locali & Serate", "Attività serali", "Musica & Concerti", "Sagre & Food", "Famiglie & Bambini", "Natura & Escursioni", "Attività diurne", "Altro"
- "titolo": titolo pulito dell'evento
- "dataTesto": data e ora leggibile (es. "Sab 28 Nov 2026 · Ore 21:00")
- "dataInizio": formato YYYY-MM-DD
- "dataFine": formato YYYY-MM-DD (deve essere >= "{oggi}")
- "luogo": nome esatto del teatro, locale, club, parco, piazza o indirizzo
- "indirizzoMappa": luogo + via/piazza + città per Google Maps
- "costo": es. "Ingresso libero", "15€", oppure "Da verificare"
- "descrizione": 1 frase chiara e invitante sull'evento
- "fonteUrl": URL esatto della fonte

TESTO DA ANALIZZARE:
{testo_grezzo}
"""

    risposta, _, _, _ = chiamata_gemini_universale(
        api_key, prompt, nome_blocco, usa_search=False, json_mode=True
    )
    if not risposta:
        return []

    try:
        risposta = re.sub(r"^`{3}json\s*|`{3}$", "", risposta, flags=re.IGNORECASE).strip()
        match_arr = re.search(r"\[.*\]", risposta, flags=re.DOTALL)
        if match_arr:
            risposta = match_arr.group(0)
        eventi = json.loads(risposta)
        return eventi if isinstance(eventi, list) else []
    except Exception as e:
        print(f"[{nome_blocco}] Errore parsing JSON:", e)
        return []


def genera_report_copertura(lista_finale, aggiunti, aggiornati):
    totale = len(lista_finale)
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
    print(f"Totale eventi attivi: {totale} | Novità: +{aggiunti} aggiunti, {aggiornati} aggiornati | URL specifici: {report['percentualeUrlSpecifici']}%")
    print("=" * 60 + "\n")


# ==============================================================================
# PIPELINE SOLO EVENTI REALI: BONIFICA TOTALE + JSON-LD + RICERCATORI WEB
# ==============================================================================
api_key = os.environ.get("GEMINI_API_KEY", "").strip()
modalita_api = "Vertex AI Express (AQ.)" if api_key.startswith("AQ.") else "Gemini AI Studio (AIza)"
print(f"Avvio pipeline | Modalità: {modalita_api} | Chiave presente: {bool(api_key)}")
urls_grounding_totali = set()

eventi_esistenti_raw = carica_json("eventi.json")
lista_consolidata = []
for ev_raw in eventi_esistenti_raw:
    ev = pulisci_evento(dict(ev_raw), ev_raw.get("citta") or "Cerignola", urls_grounding_totali)
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
        t, ev_strutturati = raccogli_testo_con_dettagli(fonte["url"], fonte["citta"])
        if t:
            testi_gruppo.append(t)
        for ev_s in ev_strutturati:
            ev = pulisci_evento(ev_s, fonte["citta"], urls_grounding_totali)
            if evento_valido(ev):
                nuovi_trovati.append(ev)
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
    print(f"Raccolta totale dai 4 ricercatori: {len(testo_agenti)} caratteri")
    if testo_agenti.strip():
        time.sleep(8)
        estratti_web = analizza_blocco_con_gemini(api_key, testo_agenti, "Ricercatori Web 50 km", "Cerignola")
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
        x.get("dataInizio", "9999-12-31"),
        priorita_cerchio_cerignola(x.get("citta")),
        x.get("titolo", "").lower()
    )
)

with open("eventi.json", "w", encoding="utf-8") as f:
    json.dump(lista_finale, f, ensure_ascii=False, indent=2)

genera_report_copertura(lista_finale, aggiunti, aggiornati)
