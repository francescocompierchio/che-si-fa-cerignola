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
    {"url": "https://www.cerignolaviva.it/eventi/", "citta": "Cerignola"},
    {"url": "https://www.foggiatoday.it/eventi/", "citta": "Foggia"},
    {"url": "https://www.foggiatoday.it/eventi/weekend/", "citta": "Foggia"},
    {"url": "https://www.barlettaviva.it/eventi/", "citta": "Barletta"},
    {"url": "https://www.traniviva.it/eventi/", "citta": "Trani"},
    {"url": "https://www.bisceglieviva.it/eventi/", "citta": "Bisceglie"},
    {"url": "https://www.andriaviva.it/eventi/", "citta": "Andria"},
    {"url": "https://www.manfredonianews.it/category/eventi/", "citta": "Manfredonia"},
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
    "applausi per", "meteo", "libeccio", "venti forti", "pioggia", "allerta",
    "neve", "freddo", "cielo sereno", "°c", "min ", "max ", "archivio", "svolta ue",
    "cop31", "frode fiscale", "riciclaggio", "indagati", "sequestri",
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
    "calcio", "basket", "maratona", "campionato", "coppa"
]

PAROLE_SEGNALE_EVENTO = [
    "concerto", "concerti", "spettacolo", "spettacoli", "teatro", "stagione teatrale",
    "cabaret", "musical", "commedia", "rassegna", "festival", "live", "musica",
    "dj set", "serata", "serate", "aperitivo", "apericena", "party", "festa",
    "sagra", "sagre", "degustazione", "degustazioni", "street food",
    "mercatino", "mercatini", "villaggio di natale", "casa di babbo natale", "natale",
    "presepe", "accensione", "luminarie", "bambini", "famiglie", "laboratorio",
    "escursione", "escursioni", "trekking", "passeggiata", "visita guidata",
    "mostra", "vernissage", "appuntamento", "programma", "ingresso"
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

MESI_IT = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12
}

MESI_NOMI = {
    1: "Gen", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mag", 6: "Giu",
    7: "Lug", 8: "Ago", 9: "Set", 10: "Ott", 11: "Nov", 12: "Dic"
}

ABBR_MESI = {
    "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6,
    "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12
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


def formatta_data_leggibile(d_ini, d_fin, ora=""):
    try:
        dt1 = datetime.strptime(d_ini, "%Y-%m-%d")
        dt2 = datetime.strptime(d_fin, "%Y-%m-%d")
        giorni_sett = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
        if d_ini == d_fin:
            base = f"{giorni_sett[dt1.weekday()]} {dt1.day} {MESI_NOMI[dt1.month]} {dt1.year}"
        elif dt1.month == dt2.month and dt1.year == dt2.year:
            base = f"Dal {dt1.day} al {dt2.day} {MESI_NOMI[dt2.month]} {dt2.year}"
        else:
            base = f"Dal {dt1.day} {MESI_NOMI[dt1.month]} al {dt2.day} {MESI_NOMI[dt2.month]} {dt2.year}"
        return f"{base} · Ore {ora}" if ora else base
    except Exception:
        return d_ini


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
    mesi_pattern = "|".join(list(MESI_IT.keys()) + list(ABBR_MESI.keys()))
    for m in re.finditer(rf"\b(\d{{1,2}})\s+({mesi_pattern})(?:\s+(202[6-9]))?\b", t):
        giorno = int(m.group(1))
        mese_str = m.group(2)
        mese = MESI_IT.get(mese_str) or ABBR_MESI.get(mese_str[:3])
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


def classifica_categoria_euristica(testo):
    t = (testo or "").lower()
    if any(k in t for k in ("sagra", "degustazion", "vino", "olio", "street food", "mercatin", "fiera")):
        return "Sagre & Food"
    if any(k in t for k in ("concerto", "musica", "live", "band", "cantante", "teatro", "spettacolo", "cabaret", "musical", "rassegna")):
        return "Musica & Concerti"
    if any(k in t for k in ("bambin", "famigl", "laboratori", "animazion", "natale", "babbo natale", "presepe")):
        return "Famiglie & Bambini"
    if any(k in t for k in ("escursion", "trekking", "passeggiat", "natura", "parco", "riserva", "bosco", "saline")):
        return "Natura & Escursioni"
    if any(k in t for k in ("dj", "serata", "discotec", "club", "pub", "aperitivo", "apericena", "locale")):
        return "Locali & Serate"
    return "Attività diurne"


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
                            "categoria": classifica_categoria_euristica(f"{nome} {desc}"),
                            "titolo": nome[:85],
                            "dataTesto": formatta_data_leggibile(inizio, fine),
                            "dataInizio": inizio,
                            "dataFine": fine,
                            "luogo": luogo,
                            "indirizzoMappa": ind or f"{luogo}, {citta_loc}",
                            "costo": "Da verificare",
                            "descrizione": desc or f"Appuntamento in programma presso {luogo}.",
                            "fonteUrl": url_ev
                        })
        except Exception:
            continue

    return testi_meta, eventi_diretti


def estrai_date_reali_da_testo(testo_articolo):
    oggi = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    max_dt = oggi + timedelta(days=90)

    pulito = re.sub(
        r"(?:pubblicato|aggiornato|redazione)\s+(?:il\s+)?\d{1,2}\s+[a-zà]+\s+202\d",
        " ",
        testo_articolo.lower()
    )
    if re.search(r"\b(19\d{2}|20[01]\d|202[0-5])\b", pulito):
        return None, None, ""

    ora_match = re.search(r"\bore\s+(\d{1,2}[:.]\d{2})\b", pulito)
    ora_str = ora_match.group(1).replace(".", ":") if ora_match else ""

    mesi_pattern = "|".join(list(MESI_IT.keys()) + list(ABBR_MESI.keys()))

    for m in re.finditer(rf"\bdal\s+(\d{{1,2}})\s+({mesi_pattern})\s+al\s+(\d{{1,2}})\s+({mesi_pattern})(?:\s+(202[6-9]))?\b", pulito):
        g1, m1_s, g2, m2_s = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)
        m1 = MESI_IT.get(m1_s) or ABBR_MESI.get(m1_s[:3])
        m2 = MESI_IT.get(m2_s) or ABBR_MESI.get(m2_s[:3])
        anno2 = int(m.group(5)) if m.group(5) else oggi.year
        anno1 = anno2 - 1 if (m1 and m2 and m1 > m2) else anno2
        try:
            dt1 = datetime(anno1, m1, g1)
            dt2 = datetime(anno2, m2, g2)
            if dt2 >= oggi and dt1 <= max_dt and dt1 <= dt2:
                d_ini = max(dt1, oggi).strftime("%Y-%m-%d")
                d_fin = dt2.strftime("%Y-%m-%d")
                return d_ini, d_fin, formatta_data_leggibile(dt1.strftime("%Y-%m-%d"), d_fin, ora_str)
        except ValueError:
            continue

    for m in re.finditer(rf"\bdal\s+(\d{{1,2}})\s+al\s+(\d{{1,2}})\s+({mesi_pattern})(?:\s+(202[6-9]))?\b", pulito):
        g1, g2, m_s = int(m.group(1)), int(m.group(2)), m.group(3)
        mese = MESI_IT.get(m_s) or ABBR_MESI.get(m_s[:3])
        anno = int(m.group(4)) if m.group(4) else oggi.year
        try:
            dt1 = datetime(anno, mese, g1)
            dt2 = datetime(anno, mese, g2)
            if dt2 >= oggi and dt1 <= max_dt and dt1 <= dt2:
                d_ini = max(dt1, oggi).strftime("%Y-%m-%d")
                d_fin = dt2.strftime("%Y-%m-%d")
                return d_ini, d_fin, formatta_data_leggibile(dt1.strftime("%Y-%m-%d"), d_fin, ora_str)
        except ValueError:
            continue

    for m in re.finditer(rf"\b(\d{{1,2}})\s+e\s+(\d{{1,2}})\s+({mesi_pattern})(?:\s+(202[6-9]))?\b", pulito):
        g1, g2, m_s = int(m.group(1)), int(m.group(2)), m.group(3)
        mese = MESI_IT.get(m_s) or ABBR_MESI.get(m_s[:3])
        anno = int(m.group(4)) if m.group(4) else oggi.year
        try:
            dt1 = datetime(anno, mese, g1)
            dt2 = datetime(anno, mese, g2)
            if dt2 >= oggi and dt1 <= max_dt and dt1 <= dt2:
                d_ini = max(dt1, oggi).strftime("%Y-%m-%d")
                d_fin = dt2.strftime("%Y-%m-%d")
                return d_ini, d_fin, formatta_data_leggibile(dt1.strftime("%Y-%m-%d"), d_fin, ora_str)
        except ValueError:
            continue

    candidati = []
    for m in re.finditer(rf"\b(\d{{1,2}})\s+({mesi_pattern})(?:\s+(202[6-9]))?\b", pulito):
        giorno = int(m.group(1))
        m_s = m.group(2)
        mese = MESI_IT.get(m_s) or ABBR_MESI.get(m_s[:3])
        anno = int(m.group(3)) if m.group(3) else oggi.year
        if mese and 1 <= giorno <= 31:
            try:
                dt = datetime(anno, mese, giorno)
                if oggi <= dt <= max_dt:
                    candidati.append(dt)
            except ValueError:
                continue

    for m in re.finditer(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](202[6-9])\b", pulito):
        g, mese, anno = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            dt = datetime(anno, mese, g)
            if oggi <= dt <= max_dt:
                candidati.append(dt)
        except ValueError:
            continue

    if candidati:
        dt_min = min(candidati)
        dt_max = max(candidati)
        if (dt_max - dt_min).days > 14:
            dt_max = dt_min
        d_ini = dt_min.strftime("%Y-%m-%d")
        d_fin = dt_max.strftime("%Y-%m-%d")
        return d_ini, d_fin, formatta_data_leggibile(d_ini, d_fin, ora_str)

    return None, None, ""


def estrai_luogo_da_testo(testo_originale, citta):
    patterns = [
        r"(?:Dove|Luogo|Location)\s*:\s*([^\n|.;]{4,65})",
        r"\bpresso\s+(?:il|la|lo|l'|i|gli|le)?\s*([A-ZÀ-Ú0-9][^\n|,.;]{3,60})",
        r"\b(?:al|allo|alla|all'|ai|agli|alle)\s+((?:Teatro|Castello|Palazzo|Piazza|Villa\s+Comunale|Auditorium|Parco|Biblioteca|Museo|Cinema|Chiostro|Sala|Lungomare|Corso|Via)\s+[A-ZÀ-Ú0-9][^\n|,.;]{2,55})",
        r"\b(?:in|nel|nella|nello|nell')\s+((?:Piazza|Corso|Via|Villa\s+Comunale|Centro\s+Storico|Pineta|Bosco)\s+[A-ZÀ-Ú0-9][^\n|,.;]{2,55})"
    ]
    for pat in patterns:
        m = re.search(pat, testo_originale)
        if m:
            luogo = re.sub(r"\s+", " ", m.group(1)).strip(" -–—:,.")
            luogo = re.split(r"\s+(?:a|di|per|con|che|il|la|lo|in)\s+(?:Cerignola|Foggia|Barletta|Trani|Andria|Bisceglie|Canosa|Manfredonia)\b", luogo, flags=re.IGNORECASE)[0].strip()
            if 4 <= len(luogo) <= 65:
                return luogo
    return f"{citta} (vedi locandina)"


def estrai_costo_da_testo(testo):
    t = testo.lower()
    if any(k in t for k in ("ingresso libero", "ingresso gratuito", "entrata libera", "evento gratuito")):
        return "Ingresso libero"
    m = re.search(r"\b(\d{1,3}(?:[.,]\d{2})?\s*€|euro\s*\d{1,3})\b", t)
    if m:
        return m.group(1).replace("euro", "€").strip()
    return "Da verificare"


def raccogli_eventi_da_portale(url_indice, citta_fonte):
    testi = []
    eventi_strutturati = []
    try:
        r = requests.get(url_indice, headers=HEADERS, timeout=15)
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        meta_indice, ev_indice = estrai_eventi_strutturati_json_ld(soup, citta_fonte, url_indice)
        eventi_strutturati.extend(ev_indice)
        if meta_indice:
            testi.append(f"[{citta_fonte}] METADATI:\n" + "\n".join(meta_indice[:10]))

        for tag in soup(["script", "style", "nav", "footer", "aside", "form"]):
            tag.decompose()

        link_articoli = []
        dominio_base = "/".join(url_indice.split("/")[:3])
        anno_corrente = datetime.now().year
        anni_vecchi = [f"/{y}/" for y in range(2010, anno_corrente)]
        esclusi_path = ["/tag/", "/author/", "/page/", "/video/", "/foto/", "/meteo/", "/necrologi/", "/sport/", "/cronaca/", "/politica/", "login", "privacy", "cookie"] + anni_vecchi

        # Raccoglie i link degli articoli presenti direttamente nella sezione /eventi/
        contenitore = soup.find(["main", "section"]) or soup
        for a in contenitore.find_all("a", href=True):
            href = urljoin(url_indice, a["href"]).split("#")[0]
            if not href.startswith(dominio_base) or href.rstrip("/") == url_indice.rstrip("/"):
                continue
            low_href = href.lower()
            if any(x in low_href for x in esclusi_path):
                continue
            # Scarta link di navigazione brevi o sezioni indice
            path_clean = urlparse(href).path.strip("/")
            if path_clean.count("/") < 1 and not path_clean.endswith(".html"):
                continue

            titolo_link = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            if len(titolo_link) < 16 or any(p in titolo_link.lower() for p in PAROLE_VIETATE):
                continue

            if href not in link_articoli:
                link_articoli.append(href)

        for link in link_articoli[:16]:
            try:
                rp = requests.get(link, headers=HEADERS, timeout=10)
                rp.encoding = rp.apparent_encoding or "utf-8"
                sp = BeautifulSoup(rp.text, "html.parser")
                meta_scheda, ev_scheda = estrai_eventi_strutturati_json_ld(sp, citta_fonte, link)
                eventi_strutturati.extend(ev_scheda)

                time_tag = sp.find("time", attrs={"datetime": True})
                if time_tag:
                    dt_pub_str = str(time_tag.get("datetime", ""))[:10]
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", dt_pub_str):
                        try:
                            dt_pub = datetime.strptime(dt_pub_str, "%Y-%m-%d")
                            if (datetime.now() - dt_pub).days > 45:
                                continue
                        except ValueError:
                            pass

                for tag in sp(["script", "style", "nav", "footer", "aside", "form"]):
                    tag.decompose()

                titolo_p = sp.find(["h1", "h2"])
                titolo_str = re.sub(r"\s+", " ", titolo_p.get_text(" ", strip=True)) if titolo_p else ""
                if not titolo_str or len(titolo_str) < 8 or any(p in titolo_str.lower() for p in PAROLE_VIETATE):
                    continue

                corpo_p = []
                for p in sp.find_all(["p", "li", "span", "div"]):
                    if p.name in ("span", "div") and len(p.find_all()) > 2:
                        continue
                    txt = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
                    if any(w in txt.lower() for w in ("adblocker", "ci stai leggendo", "cookie", "abbonati", "newsletter", "pubblicato il", "aggiornato il")):
                        continue
                    if 18 <= len(txt) <= 340 and txt not in corpo_p:
                        corpo_p.append(txt)

                testo_articolo = f"{titolo_str} | " + " | ".join(corpo_p[:8])
                full_low = testo_articolo.lower()
                if any(p in full_low for p in PAROLE_VIETATE):
                    continue
                if not any(s in full_low for s in PAROLE_SEGNALE_EVENTO):
                    continue

                d_ini, d_fin, d_testo = estrai_date_reali_da_testo(testo_articolo)
                if d_ini and d_fin:
                    citta_ev = normalizza_citta({"citta": citta_fonte, "titolo": titolo_str, "descrizione": testo_articolo[:350]}, citta_fonte)
                    luogo_ev = estrai_luogo_da_testo(testo_articolo, citta_ev)
                    desc_pulita = next((c for c in corpo_p if len(c) >= 45 and not c.lower().startswith(("dove", "quando", "info"))), "")
                    if not desc_pulita:
                        desc_pulita = f"Evento in programma a {citta_ev} ({d_testo})."
                    eventi_strutturati.append({
                        "tipoContenuto": "evento",
                        "citta": citta_ev,
                        "categoria": classifica_categoria_euristica(testo_articolo),
                        "titolo": titolo_str[:85],
                        "dataTesto": d_testo,
                        "dataInizio": d_ini,
                        "dataFine": d_fin,
                        "luogo": luogo_ev,
                        "indirizzoMappa": f"{luogo_ev}, {citta_ev}" if citta_ev.lower() not in luogo_ev.lower() else luogo_ev,
                        "costo": estrai_costo_da_testo(testo_articolo),
                        "descrizione": desc_pulita[:220],
                        "fonteUrl": link
                    })
                    testi.append(f"[{citta_ev}] ({link}) {titolo_str} | {d_testo} | Luogo: {luogo_ev} | {desc_pulita[:160]}")
            except Exception:
                continue
    except Exception as e:
        print("Errore lettura:", url_indice, e)

    return "\n".join(testi)[:5500], eventi_strutturati


def chiamata_gemini_singola_economica(api_key, testo_locale):
    if not api_key:
        return []

    oggi = oggi_iso()
    # Priorità ai modelli con 100 RPD gratuiti (flash-lite) prima di quelli da 20 RPD
    modelli = ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash"]

    prompt = f"""Sei il curatore di 'Che Si Fa Cerignola'. Oggi è {oggi}.
Compito:
1) Rifinisci e normalizza gli eventi già raccolti dai portali locali qui sotto (correggendo città, luogo esatto, categoria e descrizione).
2) Aggiungi eventuali altri eventi reali e datati (concerti, spettacoli teatrali, mercatini di Natale, sagre, serate, escursioni) in programma da oggi {oggi} ai prossimi 30 giorni entro 50 km da Cerignola (Cerignola, Foggia, Barletta, Trani, Andria, Bisceglie, Canosa, Margherita di Savoia, Candela, Melfi, Venosa, Bovino).

REGOLE RIGIDE:
- Solo eventi datati reali con dataFine >= "{oggi}".
- Escludi sport, politica, attualità, religione/devozione, beneficenza, convegni su alimentazione/salute e cronaca.
- Restituisci SOLO un array JSON valido con chiavi: "tipoContenuto" ("evento"), "citta", "categoria" (tra "Locali & Serate", "Attività serali", "Musica & Concerti", "Sagre & Food", "Famiglie & Bambini", "Natura & Escursioni", "Attività diurne", "Altro"), "titolo", "dataTesto", "dataInizio" (YYYY-MM-DD), "dataFine" (YYYY-MM-DD), "luogo", "indirizzoMappa", "costo", "descrizione", "fonteUrl".

ESTRATTI LOCALI:
{testo_locale[:14000]}
"""

    for modello in modelli:
        if api_key.startswith("AQ."):
            endpoints = [
                f"https://generativelanguage.googleapis.com/v1beta/models/{modello}:generateContent?key={api_key}",
                f"https://aiplatform.googleapis.com/v1/publishers/google/models/{modello}:generateContent?key={api_key}"
            ]
        else:
            endpoints = [
                f"https://generativelanguage.googleapis.com/v1beta/models/{modello}:generateContent?key={api_key}"
            ]

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }

        for endpoint in endpoints:
            try:
                resp = requests.post(endpoint, json=payload, timeout=50)
                if resp.status_code == 429:
                    # Non brucia tempo/tentativi se è esaurita la quota giornaliera RPD
                    print(f"[Gemini] Quota 429 su {modello} (salto subito al modello successivo).")
                    break
                if resp.status_code != 200:
                    print(f"[Gemini] HTTP {resp.status_code} su {modello}: {resp.text[:160]}")
                    break

                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    break
                parts = candidates[0].get("content", {}).get("parts", [])
                testo = "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()
                testo = re.sub(r"^`{3}json\s*|`{3}$", "", testo, flags=re.IGNORECASE).strip()
                match_arr = re.search(r"\[.*\]", testo, flags=re.DOTALL)
                if match_arr:
                    testo = match_arr.group(0)
                eventi = json.loads(testo)
                if isinstance(eventi, list):
                    print(f"[Gemini] OK con {modello}: {len(eventi)} eventi restituiti in 1 sola chiamata.")
                    return eventi
            except Exception as e:
                print(f"[Gemini] Eccezione su {modello}:", e)
                break

    print("[Gemini] Nessuna risposta AI disponibile (quota giornaliera esaurita): uso i dati estratti dai portali locali.")
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
# PIPELINE ANTI-429: SCRAPER DETERMINISTICO + MAX 1 CHIAMATA AI ECONOMICA
# ==============================================================================
api_key = os.environ.get("GEMINI_API_KEY", "").strip()
print(f"Avvio pipeline | Chiave API presente: {bool(api_key)}")
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
testi_portali = []

for fonte in FONTI_EVENTI:
    t, ev_strutturati = raccogli_eventi_da_portale(fonte["url"], fonte["citta"])
    if t:
        testi_portali.append(t)
    validi_fonte = 0
    for ev_s in ev_strutturati:
        ev = pulisci_evento(ev_s, fonte["citta"], urls_grounding_totali)
        if evento_valido(ev):
            nuovi_trovati.append(ev)
            validi_fonte += 1
    print(f"Fonte {fonte['citta']} ({fonte['url']}): {validi_fonte} eventi datati estratti")

# Una sola chiamata API leggera per rifinire ed arricchire (zero spreco di RPD)
estratti_ai = chiamata_gemini_singola_economica(api_key, "\n\n".join(testi_portali))
for ev_raw in estratti_ai:
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
