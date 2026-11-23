import os
import re
import sys
import json
import time
import requests
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

GIORNI_ANTICIPO_MAX = 45

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9"
}

DOMINI_AUTO = (
    "news.google.com", "iltaccodibacco.it", "viaggiareinpuglia.it",
    "pugliaevents.it", "eventiesagre.it", "eventbrite.it",
    "lanotiziaweb.it", "marchiodoc.it", "cerignolaviva.it",
    "canosaviva.it", "barlettaviva.it", "traniviva.it",
    "bisceglieviva.it", "andriaviva.it", "statoquotidiano.it",
    "immediato.net", "vulturenews.net",
    "teatromercadantecerignola.it", "teatrogiordano.it",
    "palazzodelleartibeltrani.it", "politeamaitalia.com",
    "happyticket.com", "pugliaculture.it", "ciaotickets.com", "virgilio.it"
)

FONTI_VIVA = [
    {"nome": "CerignolaViva Eventi", "url": "https://www.cerignolaviva.it/eventi/", "dominio": "cerignolaviva.it", "citta_default": "Cerignola", "solo_eventi": True},
    {"nome": "CerignolaViva Notizie", "url": "https://www.cerignolaviva.it/notizie/", "dominio": "cerignolaviva.it", "citta_default": "Cerignola", "solo_eventi": False},
    {"nome": "CanosaViva Eventi", "url": "https://www.canosaviva.it/eventi/", "dominio": "canosaviva.it", "citta_default": "Canosa di Puglia", "solo_eventi": True},
    {"nome": "CanosaViva Notizie", "url": "https://www.canosaviva.it/notizie/", "dominio": "canosaviva.it", "citta_default": "Canosa di Puglia", "solo_eventi": False},
    {"nome": "BarlettaViva Eventi", "url": "https://www.barlettaviva.it/eventi/", "dominio": "barlettaviva.it", "citta_default": "Barletta", "solo_eventi": True},
    {"nome": "TraniViva Eventi", "url": "https://www.traniviva.it/eventi/", "dominio": "traniviva.it", "citta_default": "Trani", "solo_eventi": True},
    {"nome": "BisceglieViva Eventi", "url": "https://www.bisceglieviva.it/eventi/", "dominio": "bisceglieviva.it", "citta_default": "Bisceglie", "solo_eventi": True},
    {"nome": "AndriaViva Eventi", "url": "https://www.andriaviva.it/eventi/", "dominio": "andriaviva.it", "citta_default": "Andria", "solo_eventi": True}
]

FONTI_TACCO = [
    {"nome": "Il Tacco di Bacco BAT", "url": "https://iltaccodibacco.it/barletta/", "dominio": "iltaccodibacco.it"},
    {"nome": "Il Tacco di Bacco Foggia", "url": "https://iltaccodibacco.it/foggia/", "dominio": "iltaccodibacco.it"}
]

COMUNI_50KM = {
    "cerignola": "Cerignola",
    "stornara": "Stornara",
    "stornarella": "Stornarella",
    "orta nova": "Orta Nova",
    "san ferdinando di puglia": "San Ferdinando di Puglia",
    "san ferdinando": "San Ferdinando di Puglia",
    "trinitapoli": "Trinitapoli",
    "canosa di puglia": "Canosa di Puglia",
    "canosa": "Canosa di Puglia",
    "ordona": "Ordona",
    "carapelle": "Carapelle",
    "margherita di savoia": "Margherita di Savoia",
    "lavello": "Lavello",
    "ascoli satriano": "Ascoli Satriano",
    "zapponeta": "Zapponeta",
    "castelluccio dei sauri": "Castelluccio dei Sauri",
    "barletta": "Barletta",
    "candela": "Candela",
    "minervino murge": "Minervino Murge",
    "minervino": "Minervino Murge",
    "foggia": "Foggia",
    "melfi": "Melfi",
    "venosa": "Venosa",
    "deliceto": "Deliceto",
    "rapolla": "Rapolla",
    "andria": "Andria",
    "barile": "Barile",
    "palazzo san gervasio": "Palazzo San Gervasio",
    "rocchetta sant'antonio": "Rocchetta Sant'Antonio",
    "manfredonia": "Manfredonia",
    "rionero in vulture": "Rionero in Vulture",
    "rionero": "Rionero in Vulture",
    "trani": "Trani",
    "bovino": "Bovino",
    "spinazzola": "Spinazzola",
    "troia": "Troia",
    "lucera": "Lucera",
    "bisceglie": "Bisceglie",
    "monticchio": "Monticchio"
}

CINTURA_25 = {
    "Stornara", "Stornarella", "Orta Nova", "San Ferdinando di Puglia",
    "Trinitapoli", "Canosa di Puglia", "Ordona", "Carapelle",
    "Margherita di Savoia", "Lavello", "Ascoli Satriano"
}

CATEGORIE_AMMESSE = [
    "Musica & Concerti",
    "Locali & Serate",
    "Sagre & Food",
    "Famiglie & Bambini",
    "Natura & Escursioni",
    "Attività diurne"
]

MESI_IT = {
    "gennaio": 1, "gen": 1,
    "febbraio": 2, "feb": 2,
    "marzo": 3, "mar": 3,
    "aprile": 4, "apr": 4,
    "maggio": 5, "mag": 5,
    "giugno": 6, "giu": 6,
    "luglio": 7, "lug": 7,
    "agosto": 8, "ago": 8,
    "settembre": 9, "set": 9, "sett": 9,
    "ottobre": 10, "ott": 10,
    "novembre": 11, "nov": 11,
    "dicembre": 12, "dic": 12
}

NOMI_MESI_BREVI = {
    1: "Gen", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mag", 6: "Giu",
    7: "Lug", 8: "Ago", 9: "Set", 10: "Ott", 11: "Nov", 12: "Dic"
}

NOMI_GIORNI_BREVI = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]

REGEX_TEMA_COERENTE = re.compile(
    r"\b(?:natale|nataliz\w*|luminarie|mercatin\w*|babbo natale|ghiaccio|presep\w*|"
    r"sagra|sagre|street food|degustazion\w*|festa in piazza|festa patronale|enogastronom\w*|"
    r"musica live|concerto|concerti|dj set|serata|serate|cabaret|live music|tribute|club|disco|"
    r"escursion\w*|trekking|passeggiat\w*|camminat\w*|visita guidata|saline|monticchio|murgia|"
    r"weekend|fine settimana|cartellone natalizio|accensione|evento|eventi|festival|fiera)\b",
    re.I
)

PAROLE_SCARTO = [
    "adblocker", "ci stai leggendo", "archivio", "evento si è già concluso",
    "grande successo per", "si è concluso", "si è svolta", "si è svolto",
    "bilancio positivo", "bilancio più che positivo",
    "teatro", "teatrale", "prosa", "recital", "pianistico", "pianoforte",
    "sinfonica", "orchestra", "opera lirica", "drammaturgia", "monologo",
    "webinar", "online event", "evento online", "corso online", "formazione professionale",
    "networking aziendale", "b2b", "masterclass business", "zoom",
    "aula magna", "dipartimento", "università", "seminario", "convegno", "conferenza",
    "tavola rotonda", "dibattito", "diritto alla verità",
    "parrocchia", "parrocchie", "diocesi", "vescovo", "santa messa", "processione",
    "madre di san", "beato", "santo",
    "wedding", "sposi", "fiera sposi", "centro commerciale", "anniversario",
    "piantumazione", "alberi per il futuro", "giornata internazionale", "disabilità",
    "mostra fotografica", "scatti di", "vernissage", "esposizione fotografica",
    "presentazione libro", "presentazione del libro",
    "bando", "gara d'appalto", "affidamento", "delibera", "determina",
    "cronaca", "politica", "consiglio comunale", "giunta", "elezioni", "arresto", "incidente",
    "omicidio", "furto", "rapina", "sequestro", "carabinieri", "polizia", "guardia di finanza",
    "calcio", "volley", "basket", "torneo", "podistica", "maratona", "campionato", "audace cerignola"
]

REGEX_SCARTO = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in PAROLE_SCARTO) + r")\b", re.I)

CHIAVI_OBBLIGATORIE = (
    "tipoContenuto", "citta", "categoria", "titolo",
    "dataTesto", "dataInizio", "dataFine", "luogo",
    "indirizzoMappa", "costo", "descrizione", "fonteUrl"
)


def oggi_dt():
    return datetime.now()


def oggi_iso(ref_dt=None):
    return (ref_dt or oggi_dt()).strftime("%Y-%m-%d")


def priorita_km(citta):
    if citta == "Cerignola":
        return 0
    if citta in CINTURA_25:
        return 1
    return 2


def risolvi_comune_50km(testo_o_ev):
    if isinstance(testo_o_ev, dict):
        c_raw = (testo_o_ev.get("citta") or "").strip().lower()
        if c_raw in COMUNI_50KM:
            return COMUNI_50KM[c_raw]
        for k in sorted(COMUNI_50KM.keys(), key=len, reverse=True):
            if re.search(rf"\b{re.escape(k)}\b", c_raw):
                return COMUNI_50KM[k]
        testo = f"{testo_o_ev.get('luogo', '')} {testo_o_ev.get('titolo', '')} {testo_o_ev.get('descrizione', '')}".lower()
    else:
        testo = str(testo_o_ev or "").lower()

    for k in sorted(COMUNI_50KM.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(k)}\b", testo):
            return COMUNI_50KM[k]
    return ""


def classifica_categoria(testo):
    t = (testo or "").lower()
    if any(k in t for k in ("escursion", "trekking", "passeggiat", "camminat", "visita guidata", "saline", "monticchio", "murgia", "incoronata", "natura")):
        return "Natura & Escursioni"
    if any(k in t for k in ("sagra", "sagre", "street food", "degustazion", "enogastronom", "caldarroste", "prodotti tipici", "food")):
        return "Sagre & Food"
    if any(k in t for k in ("dj set", "dj-set", "club", "disco", "serata", "serate", "pub", "lounge", "aperitivo")):
        return "Locali & Serate"
    if any(k in t for k in ("concerto", "concerti", "musica live", "live music", "tribute", "band", "cantautore", "cabaret")):
        return "Musica & Concerti"
    if any(k in t for k in ("natale", "nataliz", "luminarie", "mercatin", "babbo natale", "ghiaccio", "presep", "bambin", "famigli", "villaggio")):
        return "Famiglie & Bambini"
    return "Attività diurne"


def formatta_data_italiano(d_ini_iso, d_fin_iso):
    try:
        dt1 = datetime.strptime(d_ini_iso, "%Y-%m-%d")
        dt2 = datetime.strptime(d_fin_iso, "%Y-%m-%d")
        g1 = f"{NOMI_GIORNI_BREVI[dt1.weekday()]} {dt1.day:02d} {NOMI_MESI_BREVI[dt1.month]} {dt1.year}"
        if dt1.date() == dt2.date():
            return g1
        g2 = f"{dt2.day:02d} {NOMI_MESI_BREVI[dt2.month]} {dt2.year}"
        return f"Dal {dt1.day:02d} {NOMI_MESI_BREVI[dt1.month]} al {g2}"
    except Exception:
        return d_ini_iso


def _costruisci_data_sicura(giorno, mese, anno):
    try:
        return datetime(int(anno), int(mese), int(giorno))
    except ValueError:
        return None


def _inferisci_anno(giorno, mese, anno_str, ref_dt):
    if anno_str:
        return _costruisci_data_sicura(giorno, mese, int(anno_str))
    anno = ref_dt.year
    if mese < ref_dt.month - 2:
        anno += 1
    return _costruisci_data_sicura(giorno, mese, anno)


def estrai_date_italiano(testo, ref_dt=None):
    ref = ref_dt or oggi_dt()
    t = re.sub(r"\s+", " ", (testo or "")).strip().lower()

    # 1. Intervallo tra due mesi diversi: "dal 29 nov al 2 dic 2026" o "28 novembre - 6 gennaio"
    m = re.search(
        r"\b(?:dal\s+)?(\d{1,2})\s+(" + "|".join(MESI_IT.keys()) + r")(?:\s+(20\d{2}))?\s*(?:al|-|–|—)\s*(\d{1,2})\s+(" + "|".join(MESI_IT.keys()) + r")(?:\s+(20\d{2}))?\b",
        t
    )
    if m:
        g1, m1_s, a1_s, g2, m2_s, a2_s = m.groups()
        m1, m2 = MESI_IT[m1_s], MESI_IT[m2_s]
        dt2 = _inferisci_anno(int(g2), m2, a2_s, ref)
        if dt2:
            anno1 = int(a1_s) if a1_s else (dt2.year - 1 if m1 > m2 else dt2.year)
            dt1 = _costruisci_data_sicura(int(g1), m1, anno1)
            if dt1 and dt1 <= dt2:
                d1, d2 = dt1.strftime("%Y-%m-%d"), dt2.strftime("%Y-%m-%d")
                return d1, d2, formatta_data_italiano(d1, d2)

    # 2. Intervallo nello stesso mese: "dal 28 al 30 novembre 2026" o "28-30 nov"
    m = re.search(
        r"\b(?:dal\s+)?(\d{1,2})\s*(?:al|-|–|—|e)\s*(\d{1,2})\s+(" + "|".join(MESI_IT.keys()) + r")(?:\s+(20\d{2}))?\b",
        t
    )
    if m:
        g1, g2, m_s, a_s = m.groups()
        mese = MESI_IT[m_s]
        dt1 = _inferisci_anno(int(g1), mese, a_s, ref)
        dt2 = _inferisci_anno(int(g2), mese, a_s, ref)
        if dt1 and dt2 and dt1 <= dt2:
            d1, d2 = dt1.strftime("%Y-%m-%d"), dt2.strftime("%Y-%m-%d")
            return d1, d2, formatta_data_italiano(d1, d2)

    # 3. Data singola in italiano: "28 novembre 2026" o "sabato 28 novembre"
    m = re.search(
        r"\b(\d{1,2})\s+(" + "|".join(MESI_IT.keys()) + r")(?:\s+(20\d{2}))?\b",
        t
    )
    if m:
        g1, m_s, a_s = m.groups()
        dt1 = _inferisci_anno(int(g1), MESI_IT[m_s], a_s, ref)
        if dt1:
            d1 = dt1.strftime("%Y-%m-%d")
            return d1, d1, formatta_data_italiano(d1, d1)

    # 4. Intervallo numerico: "28/11/2026 - 30/11/2026" o "dal 28/11 al 30/11"
    m = re.search(
        r"\b(?:dal\s+)?(\d{1,2})[/.-](\d{1,2})(?:[/.-](20\d{2}))?\s*(?:al|-|–|—)\s*(\d{1,2})[/.-](\d{1,2})(?:[/.-](20\d{2}))?\b",
        t
    )
    if m:
        g1, m1_s, a1_s, g2, m2_s, a2_s = m.groups()
        dt2 = _inferisci_anno(int(g2), int(m2_s), a2_s, ref)
        if dt2:
            anno1 = int(a1_s) if a1_s else (dt2.year - 1 if int(m1_s) > int(m2_s) else dt2.year)
            dt1 = _costruisci_data_sicura(int(g1), int(m1_s), anno1)
            if dt1 and dt1 <= dt2:
                d1, d2 = dt1.strftime("%Y-%m-%d"), dt2.strftime("%Y-%m-%d")
                return d1, d2, formatta_data_italiano(d1, d2)

    # 5. Data numerica singola con anno: "06/12/2026" o "06-12-2026"
    m = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b", t)
    if m:
        g1, m1_s, a1_s = m.groups()
        dt1 = _costruisci_data_sicura(int(g1), int(m1_s), int(a1_s))
        if dt1:
            d1 = dt1.strftime("%Y-%m-%d")
            return d1, d1, formatta_data_italiano(d1, d1)

    # 6. Riferimenti relativi prossimi (weekend / sabato / domenica / periodo natalizio attivo)
    if any(k in t for k in ("questo weekend", "fine settimana", "sabato e domenica")):
        days_to_sat = (5 - ref.weekday()) % 7
        sat = ref + timedelta(days=days_to_sat)
        sun = sat + timedelta(days=1)
        d1, d2 = sat.strftime("%Y-%m-%d"), sun.strftime("%Y-%m-%d")
        return d1, d2, formatta_data_italiano(d1, d2)

    if any(k in t for k in ("luminarie", "villaggio di babbo natale", "pista di ghiaccio", "mercatini di natale", "cartellone natalizio")):
        d1 = ref.strftime("%Y-%m-%d")
        fine_nat = datetime(ref.year + 1, 1, 6) if ref.month >= 11 else (ref + timedelta(days=25))
        if fine_nat > ref + timedelta(days=GIORNI_ANTICIPO_MAX):
            fine_nat = ref + timedelta(days=GIORNI_ANTICIPO_MAX)
        d2 = fine_nat.strftime("%Y-%m-%d")
        return d1, d2, f"Periodo natalizio · Fino al {fine_nat.day:02d} {NOMI_MESI_BREVI[fine_nat.month]}"

    return "", "", ""


def estrai_eventi_jsonld(obj, trovati):
    if isinstance(obj, list):
        for item in obj:
            estrai_eventi_jsonld(item, trovati)
    elif isinstance(obj, dict):
        t = obj.get("@type", "")
        tipi = t if isinstance(t, list) else [t]
        if any("Event" in str(x) for x in tipi) and obj.get("name"):
            trovati.append(obj)
        for v in obj.values():
            if isinstance(v, (dict, list)):
                estrai_eventi_jsonld(v, trovati)


def estrai_luogo_e_costo(soup, citta):
    luogo = ""
    costo = "Ingresso libero / Da verificare"
    testo_pag = soup.get_text("\n", strip=True)

    for raw_line in testo_pag.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if len(line) < 5 or len(line) > 130:
            continue
        m_dove = re.match(r"^(?:dove|luogo|presso|location)\s*:\s*(.+)$", line, re.I)
        if m_dove and not luogo:
            luogo = m_dove.group(1).strip()
        m_costo = re.match(r"^(?:ingresso|costo|prezzo|biglietti)\s*:\s*(.+)$", line, re.I)
        if m_costo:
            costo = m_costo.group(1).strip()[:70]

    if not luogo or luogo.lower() in ("da definire", "n/d", citta.lower()):
        luogo = f"Centro / Piazze, {citta}"
    return luogo, costo


def normalizza_e_valida_evento(raw, ref_dt=None):
    ref = ref_dt or oggi_dt()
    oggi = oggi_iso(ref)
    limite_max = (ref + timedelta(days=GIORNI_ANTICIPO_MAX)).strftime("%Y-%m-%d")

    titolo = re.sub(r"\s+", " ", str(raw.get("titolo") or "")).strip()[:85]
    descrizione = re.sub(r"\s+", " ", str(raw.get("descrizione") or "")).strip()[:220]
    luogo = re.sub(r"\s+", " ", str(raw.get("luogo") or "")).strip()
    url = str(raw.get("fonteUrl") or "").strip()

    if len(titolo) < 5:
        return None, "titolo_corto"
    if not url.startswith("http"):
        return None, "url_non_valido"

    testo_check = f"{titolo} {descrizione} {luogo}"
    m_scarto = REGEX_SCARTO.search(testo_check)
    if m_scarto:
        return None, f"scarto({m_scarto.group(0)})"

    citta = risolvi_comune_50km(raw)
    if not citta:
        return None, "fuori_raggio_50km"

    d1 = str(raw.get("dataInizio") or "").strip()[:10]
    d2 = str(raw.get("dataFine") or d1).strip()[:10]
    d_txt = str(raw.get("dataTesto") or "").strip()

    if not (re.match(r"^\d{4}-\d{2}-\d{2}$", d1) and re.match(r"^\d{4}-\d{2}-\d{2}$", d2)):
        d1, d2, d_txt = estrai_date_italiano(f"{titolo} {descrizione} {d_txt}", ref)

    if not (re.match(r"^\d{4}-\d{2}-\d{2}$", d1) and re.match(r"^\d{4}-\d{2}-\d{2}$", d2)):
        return None, "data_assente"
    if d2 < oggi:
        return None, f"passato({d2})"
    if d1 > d2:
        return None, f"intervallo_invalido({d1}>{d2})"
    if d1 > limite_max:
        return None, f"oltre_{GIORNI_ANTICIPO_MAX}gg({d1})"

    cat = str(raw.get("categoria") or "").strip()
    if cat not in CATEGORIE_AMMESSE:
        cat = classifica_categoria(f"{titolo} {descrizione}")

    if not luogo or luogo.lower() in ("da definire", "da verificare", "n/d", citta.lower()):
        luogo = f"Centro / Piazze, {citta}"

    if not d_txt:
        d_txt = formatta_data_italiano(d1, d2)

    ev_pulito = {
        "tipoContenuto": "evento",
        "citta": citta,
        "categoria": cat,
        "titolo": titolo,
        "dataTesto": d_txt,
        "dataInizio": d1,
        "dataFine": d2,
        "luogo": luogo,
        "indirizzoMappa": (str(raw.get("indirizzoMappa") or "").strip() or f"{luogo}, {citta}"),
        "costo": (str(raw.get("costo") or "").strip() or "Ingresso libero / Da verificare"),
        "descrizione": descrizione or f"{titolo} a {citta}.",
        "fonteUrl": url
    }
    return ev_pulito, "ok"


def analizza_pagina_evento(html_text, page_url, citta_default="", ref_dt=None):
    ref = ref_dt or oggi_dt()
    soup = BeautifulSoup(html_text, "html.parser")
    risultati = []

    # 1. Prova prima con JSON-LD strutturato (schema.org/Event)
    eventi_ld = []
    for sc in soup.find_all("script", type="application/ld+json"):
        try:
            dati = json.loads(sc.string or "")
            estrai_eventi_jsonld(dati, eventi_ld)
        except Exception:
            continue

    for ev_ld in eventi_ld[:3]:
        titolo = re.sub(r"\s+", " ", str(ev_ld.get("name") or "")).strip()
        d1 = str(ev_ld.get("startDate") or "").strip()[:10]
        d2 = str(ev_ld.get("endDate") or d1).strip()[:10]
        loc = ev_ld.get("location") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        luogo_nome = loc.get("name", "") if isinstance(loc, dict) else ""
        addr = loc.get("address", {}) if isinstance(loc, dict) else {}
        localita = addr.get("addressLocality", citta_default) if isinstance(addr, dict) else citta_default
        via = addr.get("streetAddress", "") if isinstance(addr, dict) else ""
        desc = re.sub(r"\s+", " ", str(ev_ld.get("description") or "")).strip()
        offers = ev_ld.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        prezzo = offers.get("price", "") if isinstance(offers, dict) else ""
        costo = f"€ {prezzo}" if str(prezzo).strip() not in ("", "0", "0.00") else ("Ingresso gratuito" if str(prezzo).strip() in ("0", "0.00") else "Ingresso libero / Da verificare")

        candidato = {
            "citta": localita or citta_default,
            "titolo": titolo,
            "dataInizio": d1,
            "dataFine": d2,
            "dataTesto": formatta_data_italiano(d1, d2) if re.match(r"^\d{4}-\d{2}-\d{2}$", d1) else "",
            "luogo": luogo_nome,
            "indirizzoMappa": f"{luogo_nome} {via}, {localita or citta_default}".strip(" ,"),
            "costo": costo,
            "descrizione": desc,
            "fonteUrl": page_url
        }
        ev_ok, _ = normalizza_e_valida_evento(candidato, ref)
        if ev_ok:
            risultati.append(ev_ok)

    if risultati:
        return risultati

    # 2. Estrazione deterministica HTML + regex date italiane
    h1 = soup.find("h1")
    titolo = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else ""
    if not titolo:
        og_t = soup.find("meta", property="og:title")
        titolo = re.sub(r"\s+", " ", og_t.get("content", "")).strip() if og_t else ""

    if len(titolo) < 5 or REGEX_SCARTO.search(titolo):
        return []

    for tag in soup(["script", "style", "nav", "footer", "aside", "form", "noscript", "iframe"]):
        tag.decompose()

    cont = soup.find("article") or soup.find("main") or soup.body or soup
    paragrafi = []
    for p in cont.find_all(["p", "li", "div", "span"]):
        txt = re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
        if 20 <= len(txt) <= 450 and txt not in paragrafi:
            paragrafi.append(txt)
        if len(paragrafi) >= 12:
            break

    corpo = " ".join(paragrafi)[:1600]
    testo_completo = f"{titolo} | {corpo}"

    if REGEX_SCARTO.search(f"{titolo} {corpo[:450]}"):
        return []
    if "/eventi/" not in page_url.lower() and not REGEX_TEMA_COERENTE.search(testo_completo):
        return []

    # Cerca prima tag <time datetime="YYYY-MM-DD...">
    d1, d2, d_txt = "", "", ""
    for tm in cont.find_all("time", datetime=True):
        dt_attr = tm.get("datetime", "").strip()[:10]
        if re.match(r"^\d{4}-\d{2}-\d{2}$", dt_attr) and dt_attr >= oggi_iso(ref):
            d1 = dt_attr
            d2 = dt_attr
            d_txt = formatta_data_italiano(d1, d2)
            break

    if not d1:
        d1, d2, d_txt = estrai_date_italiano(testo_completo, ref)

    if not d1:
        return []

    citta = risolvi_comune_50km({"citta": citta_default, "titolo": titolo, "descrizione": corpo[:600]})
    if not citta:
        return []

    luogo, costo = estrai_luogo_e_costo(cont, citta)
    descrizione = ""
    for p in paragrafi:
        if len(p) >= 45 and p.lower() != titolo.lower() and not REGEX_SCARTO.search(p):
            descrizione = p[:220]
            break

    candidato = {
        "citta": citta,
        "categoria": classifica_categoria(testo_completo),
        "titolo": titolo,
        "dataTesto": d_txt,
        "dataInizio": d1,
        "dataFine": d2,
        "luogo": luogo,
        "indirizzoMappa": f"{luogo}, {citta}",
        "costo": costo,
        "descrizione": descrizione or f"{titolo} a {citta}.",
        "fonteUrl": page_url
    }
    ev_ok, _ = normalizza_e_valida_evento(candidato, ref)
    return [ev_ok] if ev_ok else []


def raccogli_da_portale_viva(session, fonte):
    eventi = []
    nome = fonte["nome"]
    url = fonte["url"]
    dominio = fonte["dominio"]
    c_def = fonte["citta_default"]
    solo_ev = fonte["solo_eventi"]

    try:
        r = session.get(url, timeout=(5, 9))
        if r.status_code != 200:
            print(f"{nome}: HTTP {r.status_code}")
            return []
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        links = []
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"]).split("#")[0].split("?")[0]
            parsed = urlparse(href)
            if dominio not in parsed.netloc.lower():
                continue
            path = parsed.path.lower()

            # Filtra link reali di dettaglio evento/articolo ed esclude archivi/paginazione
            if any(x in path for x in ("/pagina-", "/archivio", "/oggi", "/domani", "/weekend", "/tag/", "/categoria/")):
                continue

            is_dettaglio_evento = bool(re.match(r"^/eventi/[a-z0-9_-]{5,}(?:\.html)?$", path))
            is_dettaglio_notizia = bool(re.match(r"^/notizie/[a-z0-9_-]{8,}(?:\.html)?$", path))

            if solo_ev and is_dettaglio_evento:
                if href not in links:
                    links.append(href)
            elif not solo_ev and (is_dettaglio_evento or is_dettaglio_notizia):
                t_link = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
                if (is_dettaglio_evento or REGEX_TEMA_COERENTE.search(t_link)) and not REGEX_SCARTO.search(t_link):
                    if href not in links:
                        links.append(href)

        for link in links[:8]:
            try:
                rp = session.get(link, timeout=(4, 7))
                if rp.status_code != 200:
                    continue
                rp.encoding = rp.apparent_encoding or "utf-8"
                trovati = analizza_pagina_evento(rp.text, link, citta_default=c_def)
                eventi.extend(trovati)
            except Exception:
                continue

        print(f"{nome}: {len(eventi)} eventi estratti (da {len(links[:8])} pagine)")
    except Exception as e:
        print(f"Errore {nome}: {str(e)[:75]}")

    return eventi


def raccogli_da_tacco(session, fonte):
    eventi = []
    nome = fonte["nome"]
    url = fonte["url"]

    try:
        r = session.get(url, timeout=(5, 9))
        if r.status_code != 200:
            print(f"{nome}: HTTP {r.status_code}")
            return []
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        links = []
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"]).split("#")[0].split("?")[0]
            if re.search(r"iltaccodibacco\.it/puglia/eventi/\d+\.html$", href):
                if href not in links:
                    links.append(href)

        for link in links[:10]:
            try:
                rp = session.get(link, timeout=(4, 7))
                if rp.status_code != 200:
                    continue
                rp.encoding = rp.apparent_encoding or "utf-8"
                if "evento si è già concluso" in rp.text.lower() or "fa parte del nostro archivio" in rp.text.lower():
                    continue
                trovati = analizza_pagina_evento(rp.text, link, citta_default="")
                eventi.extend(trovati)
            except Exception:
                continue

        print(f"{nome}: {len(eventi)} eventi estratti (da {len(links[:10])} schede)")
    except Exception as e:
        print(f"Errore {nome}: {str(e)[:75]}")

    return eventi


def arricchisci_con_gemini_opzionale(api_key, eventi):
    """
    Miglioramento facoltativo: rifinisce solo titolo e descrizione degli eventi già estratti da Python.
    In caso di HTTP 429, 503, 404 o timeout restituisce immediatamente gli eventi originali intatti.
    """
    if not api_key or not eventi:
        return eventi

    candidati = eventi[:12]
    ridotti = [
        {"idx": i, "citta": e["citta"], "titolo": e["titolo"], "descrizione": e["descrizione"]}
        for i, e in enumerate(candidati)
    ]

    modelli = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-3.5-flash-lite"]
    prompt = (
        "Migliora esclusivamente la chiarezza di 'titolo' (max 80 char, concreto, senza clickbait) e 'descrizione' (max 200 char, informativa) "
        "degli eventi locali pugliesi seguenti. NON inventare date o luoghi e mantieni lo stesso 'idx'. "
        "Rispondi SOLO con un array JSON: [{\"idx\":0,\"titolo\":\"...\",\"descrizione\":\"...\"}]\n\n"
        f"{json.dumps(ridotti, ensure_ascii=False)}"
    )

    for mod in modelli:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
        }
        try:
            r = requests.post(url, json=payload, timeout=(5, 15))
            if r.status_code != 200:
                print(f"[Gemini opzionale] HTTP {r.status_code} su {mod}: mantengo testi estratti da Python.")
                continue
            parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            raw = "\n".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            raw_clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()
            aggiornamenti = json.loads(raw_clean)
            if isinstance(aggiornamenti, list):
                mappa = {item["idx"]: item for item in aggiornamenti if isinstance(item, dict) and "idx" in item}
                for i, ev in enumerate(candidati):
                    if i in mappa:
                        nuovo_t = re.sub(r"\s+", " ", str(mappa[i].get("titolo") or "")).strip()
                        nuova_d = re.sub(r"\s+", " ", str(mappa[i].get("descrizione") or "")).strip()
                        if len(nuovo_t) >= 5 and not REGEX_SCARTO.search(nuovo_t):
                            ev["titolo"] = nuovo_t[:85]
                        if len(nuova_d) >= 15 and not REGEX_SCARTO.search(nuova_d):
                            ev["descrizione"] = nuova_d[:220]
                print(f"[Gemini opzionale] Testi rifiniti con {mod}.")
                return eventi
        except Exception as e:
            print(f"[Gemini opzionale] Errore {mod} ({str(e)[:50]}): mantengo testi estratti da Python.")
            continue

    return eventi


def sono_duplicati(a, b):
    if a.get("citta", "").lower() != b.get("citta", "").lower():
        return False
    if a.get("fonteUrl") and a.get("fonteUrl") == b.get("fonteUrl"):
        return True
    t1 = re.sub(r"[^a-z0-9\s]", "", a.get("titolo", "").lower())
    t2 = re.sub(r"[^a-z0-9\s]", "", b.get("titolo", "").lower())
    return SequenceMatcher(None, t1, t2).ratio() >= 0.68


def carica_esistenti_protetti(percorso_json="eventi.json", ref_dt=None):
    oggi = oggi_iso(ref_dt)
    manuali = []
    auto_validi = []

    if not os.path.exists(percorso_json):
        return manuali, auto_validi

    try:
        with open(percorso_json, "r", encoding="utf-8") as f:
            dati = json.load(f)
        if not isinstance(dati, list):
            return manuali, auto_validi

        for item in dati:
            if not isinstance(item, dict) or item.get("tipoContenuto") != "evento":
                continue
            titolo = str(item.get("titolo") or "").strip()
            if len(titolo) < 3:
                continue

            url = str(item.get("fonteUrl") or "").strip().lower()
            is_manuale = bool(item.get("manuale")) or not any(dom in url for dom in DOMINI_AUTO)
            d_fin = str(item.get("dataFine") or item.get("dataInizio") or "").strip()[:10]

            if is_manuale:
                if not d_fin or not re.match(r"^\d{4}-\d{2}-\d{2}$", d_fin) or d_fin >= oggi:
                    manuali.append(item)
            else:
                if re.match(r"^\d{4}-\d{2}-\d{2}$", d_fin) and d_fin >= oggi:
                    auto_validi.append(item)
    except Exception as e:
        print(f"Avviso lettura {percorso_json}: {str(e)[:70]}")

    return manuali, auto_validi


def esegui_aggiornamento():
    t_start = time.time()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    ref = oggi_dt()

    manuali_admin, precedenti_auto = carica_esistenti_protetti("eventi.json", ref)
    print(f"Eventi protetti caricati: {len(manuali_admin)} manuali admin, {len(precedenti_auto)} automatici ancora validi.")

    session = requests.Session()
    session.headers.update(HEADERS)

    nuovi_raccolti = []
    for fonte in FONTI_VIVA:
        nuovi_raccolti.extend(raccogli_da_portale_viva(session, fonte))

    for fonte in FONTI_TACCO:
        nuovi_raccolti.extend(raccogli_da_tacco(session, fonte))

    # Deduplica i nuovi eventi estratti da Python
    nuovi_unici = []
    for ev in nuovi_raccolti:
        if not any(sono_duplicati(x, ev) for x in nuovi_unici):
            nuovi_unici.append(ev)

    # Arricchimento Gemini strettamente opzionale
    nuovi_unici = arricchisci_con_gemini_opzionale(api_key, nuovi_unici)

    consolidati = list(manuali_admin)
    aggiunti_nuovi = 0
    for ev in nuovi_unici:
        if not any(sono_duplicati(x, ev) for x in consolidati):
            consolidati.append(ev)
            aggiunti_nuovi += 1

    # Conserva anche eventuali eventi automatici precedenti non ancora scaduti (protegge da blocchi parziali o totali dei portali)
    for ev_old in precedenti_auto:
        if not any(sono_duplicati(x, ev_old) for x in consolidati):
            consolidati.append(ev_old)

    lista_finale = sorted(
        consolidati,
        key=lambda x: (x.get("dataInizio", "9999-12-31"), priorita_km(x.get("citta", "")), x.get("titolo", "").lower())
    )

    with open("eventi.json", "w", encoding="utf-8") as f:
        json.dump(lista_finale, f, ensure_ascii=False, indent=2)

    report = {
        "aggiornatoAl": ref.strftime("%Y-%m-%d %H:%M:%S"),
        "totaleContenuti": len(lista_finale),
        "nuoviAggiunti": aggiunti_nuovi,
        "manualiConservati": len(manuali_admin),
        "topComuni": dict(Counter(e.get("citta", "") for e in lista_finale).most_common(15))
    }
    with open("report_copertura.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Fine: {len(lista_finale)} eventi totali salvati ({aggiunti_nuovi} nuovi da portali, {len(manuali_admin)} manuali) in {int(time.time() - t_start)}s")


def esegui_self_test():
    """Verifica locale deterministica dei 6 requisiti senza modificare eventi.json di produzione."""
    ref = datetime(2026, 11, 23, 17, 0, 0)

    # Test 1: Date italiane e scarto eventi passati
    d1, d2, txt = estrai_date_italiano("Accensione luminarie sabato 28 novembre 2026 in Piazza Duomo", ref)
    assert d1 == "2026-11-28" and d2 == "2026-11-28" and "28 Nov 2026" in txt, f"Fallito test data singola: {d1}, {d2}, {txt}"

    d1_r, d2_r, txt_r = estrai_date_italiano("Mercatini di Natale dal 29 nov al 2 dic 2026", ref)
    assert d1_r == "2026-11-29" and d2_r == "2026-12-02", f"Fallito test intervallo date: {d1_r} -> {d2_r}"

    ev_scaduto, motivo = normalizza_e_valida_evento({
        "citta": "Cerignola",
        "titolo": "Festa d'autunno",
        "descrizione": "Degustazione prodotti tipici il 10 ottobre 2025",
        "fonteUrl": "https://www.cerignolaviva.it/eventi/festa-autunno.html"
    }, ref)
    assert ev_scaduto is None and "passato" in motivo, f"Fallito scarto evento passato: {motivo}"

    # Test 2: Estrazione HTML + URL completi
    html_mock = """
    <html><head><title>Notte Live</title></head><body>
    <article>
      <h1>Concerto Live Band in Piazza Duomo</h1>
      <p>Dove: Piazza Duomo, Cerignola</p>
      <p>Ingresso: Gratuito</p>
      <p>Appuntamento sabato 28 novembre 2026 con musica live e street food nel centro di Cerignola.</p>
    </article></body></html>
    """
    estratti = analizza_pagina_evento(html_mock, "https://www.cerignolaviva.it/eventi/concerto-live.html", "Cerignola", ref)
    assert len(estratti) == 1, "Fallita estrazione HTML autonoma"
    ev_test = estratti[0]
    for k in CHIAVI_OBBLIGATORIE:
        assert k in ev_test and ev_test[k], f"Chiave mancante nel JSON: {k}"
    assert ev_test["fonteUrl"].startswith("https://"), "URL non assoluto"

    # Test 3: Simulazione errore 429/503 su Gemini (chiave fittizia / endpoint non disponibile)
    post_orig = requests.post

    class FakeResp:
        status_code = 503
        text = "Service Unavailable"

    try:
        requests.post = lambda *a, **kw: FakeResp()
        dopo_gemini = arricchisci_con_gemini_opzionale("FAKE_KEY", [ev_test])
        assert len(dopo_gemini) == 1 and dopo_gemini[0]["titolo"] == ev_test["titolo"], "Fallita resilienza 503"
    finally:
        requests.post = post_orig

    # Test 4: Conservazione eventi manuali e non svuotamento se tutte le fonti falliscono
    tmp_file = "_test_eventi_tmp.json"
    try:
        dati_iniziali = [
            {
                "tipoContenuto": "evento",
                "citta": "Cerignola",
                "categoria": "Locali & Serate",
                "titolo": "Serata Privata Admin",
                "dataTesto": "Sab 05 Dic 2026",
                "dataInizio": "2026-12-05",
                "dataFine": "2026-12-05",
                "luogo": "Corso Gramsci, Cerignola",
                "indirizzoMappa": "Corso Gramsci, Cerignola",
                "costo": "€ 10",
                "descrizione": "Evento inserito manualmente da admin.",
                "fonteUrl": ""
            },
            ev_test
        ]
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(dati_iniziali, f)
        man, auto_v = carica_esistenti_protetti(tmp_file, ref)
        assert len(man) == 1 and man[0]["titolo"] == "Serata Privata Admin", "Fallita protezione evento manuale"
        assert len(auto_v) == 1 and auto_v[0]["titolo"] == ev_test["titolo"], "Fallito mantenimento automatico valido"
    finally:
        if os.path.exists(tmp_file):
            os.remove(tmp_file)

    print("SELF-TEST COMPLETATO CON SUCCESSO: tutti i controlli superati.")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        esegui_self_test()
    else:
        esegui_aggiornamento()
