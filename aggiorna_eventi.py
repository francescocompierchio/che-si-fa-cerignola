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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/129.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9"
}

FONTI_LOCALI = [
    {"url": "https://www.cerignolaviva.it/eventi/", "citta": "Cerignola"},
    {"url": "https://www.canosaweb.it/category/eventi/", "citta": "Canosa"},
    {"url": "https://www.foggiatoday.it/eventi/", "citta": "Foggia"},
    {"url": "https://www.foggiatoday.it/eventi/weekend/", "citta": "Foggia"},
    {"url": "https://www.immediato.net/category/eventi/", "citta": "Foggia"},
    {"url": "https://www.barlettaviva.it/eventi/", "citta": "Barletta"},
    {"url": "https://www.traniviva.it/eventi/", "citta": "Trani"},
    {"url": "https://www.bisceglieviva.it/eventi/", "citta": "Bisceglie"},
    {"url": "https://www.andriaviva.it/eventi/", "citta": "Andria"},
]

DOMINI_OK = {urlparse(f["url"]).netloc.lower() for f in FONTI_LOCALI}

FALLBACK_URL = {
    "Cerignola": "https://www.cerignolaviva.it/eventi/",
    "Canosa": "https://www.canosaweb.it/category/eventi/",
    "Foggia": "https://www.foggiatoday.it/eventi/",
    "Barletta": "https://www.barlettaviva.it/eventi/",
    "Trani": "https://www.traniviva.it/eventi/",
    "Bisceglie": "https://www.bisceglieviva.it/eventi/",
    "Andria": "https://www.andriaviva.it/eventi/",
}

CATEGORIE_OK = [
    "Locali & Serate", "Attività serali", "Musica & Concerti", "Sagre & Food",
    "Famiglie & Bambini", "Natura & Escursioni", "Attività diurne", "Altro"
]

MAPPA_CAT = {
    "serate": "Locali & Serate", "locali": "Locali & Serate", "dj": "Locali & Serate",
    "attività serali": "Attività serali", "apericena": "Attività serali",
    "musica": "Musica & Concerti", "concerti": "Musica & Concerti", "teatro": "Musica & Concerti",
    "sagra": "Sagre & Food", "sagre": "Sagre & Food", "food": "Sagre & Food",
    "famiglie": "Famiglie & Bambini", "bambini": "Famiglie & Bambini",
    "natura": "Natura & Escursioni", "escursioni": "Natura & Escursioni",
    "attività diurne": "Attività diurne", "cultura": "Attività diurne"
}

LISTA_VIETATE = [
    "adblocker", "ci stai leggendo", "disattiva", "cookie", "abbonati", "newsletter",
    "archivio", "agenda di", "eventi in agenda", "tutti gli eventi", "sede nell'articolo",
    "mostra fotografica", "scatti di", "vernissage", "pinacoteca", "esposizione fotografica",
    "cronaca", "politica", "alimentazione", "nutrizione", "dieta", "screening",
    "vescovo", "diocesi", "parrocchia", "santa messa", "processione", "devozione", "cattedrale",
    "beneficenza", "raccolta fondi", "raccolta alimentare", "volontariato",
    "bilancio", "si è svolta", "si è svolto", "si è tenuto", "si è conclusa", "si è concluso",
    "conquista", "escursionisti", "partecipanti", "presenze", "grande affluenza", "applausi per",
    "annullato", "rinviato", "indagine di mercato", "progetto", "confronto", "fuga dei giovani",
    "diritti", "meteo", "libeccio", "allerta meteo",
    "frode", "riciclaggio", "indagati", "indagato", "sequestri", "sequestro",
    "scontro tra auto", "morti e feriti", "questore", "sospende la licenza",
    "arresto", "arresti", "rapina", "incidente", "incendio", "denuncia",
    "tribunale", "carabinieri", "polizia", "guardia di finanza",
    "consiglio comunale", "giunta", "elezioni", "partito", "sciopero", "ospedale", "asl",
    "furto", "truffa", "omicidio", "ferito", "morto", "lutto", "cordoglio",
    "convegno", "conferenza", "tavola rotonda", "dibattito", "seminario", "incontro pubblico",
    "presentazione del libro", "presentazione libro", "nuovo libro",
    "sport", "torneo", "podistica", "partita", "stadio", "palazzetto",
    "volley", "calcio", "basket", "maratona", "campionato", "serie c", "serie d"
]

LISTA_SVAGO_OK = [
    "concerto", "concerti", "musica", "musicale", "live", "band", "tribute",
    "spettacolo", "spettacoli", "teatro", "teatrale", "cabaret", "commedia", "musical",
    "rassegna", "festival", "dj set", "serata", "serate", "discoteca", "club", "party",
    "apericena", "aperitivo", "festa", "sagra", "sagre", "degustazione", "degustazioni",
    "street food", "castagne", "novello", "mercatino", "mercatini", "natale", "natalizio",
    "natalizi", "babbo natale", "presepe", "luminarie", "albero di natale",
    "bambini", "famiglie", "laboratorio", "laboratori", "animazione", "circo", "burattini",
    "escursione", "escursioni", "trekking", "passeggiata", "camminata", "visita guidata",
    "visite guidate", "cinema", "proiezione"
]

REGEX_VIETATE = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in LISTA_VIETATE) + r")\b", re.I)
REGEX_SVAGO_OK = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in LISTA_SVAGO_OK) + r")\b", re.I)

PATH_ESCLUSI = [
    "/archivio", "/tag/", "/author/", "/page/", "/video/", "/foto/", "/meteo/", "/necrologi/",
    "/sport/", "/cronaca/", "/politica/", "/attualita/", "/economia/", "/scuola/",
    "/salute/", "login", "privacy", "cookie", "/contatti", "/redazione"
]

CITTA_MAP = {
    "cerignola": "Cerignola", "stornara": "Stornara", "stornarella": "Stornarella",
    "san ferdinando": "San Ferdinando", "orta nova": "Orta Nova", "trinitapoli": "Trinitapoli",
    "canosa": "Canosa", "ordona": "Ordona", "carapelle": "Carapelle",
    "margherita di savoia": "Margherita di Savoia", "lavello": "Lavello",
    "ascoli satriano": "Ascoli Satriano", "zapponeta": "Zapponeta",
    "castelluccio dei sauri": "Castelluccio dei Sauri", "barletta": "Barletta",
    "candela": "Candela", "minervino": "Minervino Murge", "foggia": "Foggia",
    "melfi": "Melfi", "venosa": "Venosa", "deliceto": "Deliceto", "rapolla": "Rapolla",
    "andria": "Andria", "barile": "Barile", "palazzo san gervasio": "Palazzo San Gervasio",
    "rocchetta sant'antonio": "Rocchetta Sant'Antonio", "manfredonia": "Manfredonia",
    "rionero": "Rionero in Vulture", "trani": "Trani", "bovino": "Bovino",
    "monticchio": "Monticchio", "spinazzola": "Spinazzola", "troia": "Troia",
    "accadia": "Accadia", "lucera": "Lucera", "bisceglie": "Bisceglie", "molfetta": "Molfetta"
}

CINTURA_25 = {
    "stornara", "stornarella", "san ferdinando", "orta nova", "trinitapoli",
    "canosa", "ordona", "carapelle", "margherita di savoia", "lavello", "ascoli satriano"
}

CINTURA_50 = {
    "zapponeta", "castelluccio dei sauri", "barletta", "candela", "minervino murge",
    "foggia", "melfi", "venosa", "deliceto", "rapolla", "andria", "barile",
    "palazzo san gervasio", "rocchetta sant'antonio", "manfredonia", "rionero in vulture",
    "trani", "bovino", "monticchio", "spinazzola", "troia", "accadia", "lucera", "bisceglie"
}

MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
    "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6,
    "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12
}
MESI_BREVE = {1: "Gen", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mag", 6: "Giu",
              7: "Lug", 8: "Ago", 9: "Set", 10: "Ott", 11: "Nov", 12: "Dic"}
GIORNI_SETT = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]


def priorita_km(citta):
    c = (citta or "").strip().lower()
    if c == "cerignola":
        return 0
    if c in CINTURA_25:
        return 1
    if c in CINTURA_50:
        return 2
    return 3


def oggi_iso():
    return datetime.now().strftime("%Y-%m-%d")


def risolvi_anno(mese, anno_str, oggi):
    if anno_str:
        return int(anno_str)
    if oggi.month >= 11 and mese <= 2:
        return oggi.year + 1
    return oggi.year


def formatta_data(d1, d2, ora=""):
    try:
        dt1 = datetime.strptime(d1, "%Y-%m-%d")
        dt2 = datetime.strptime(d2, "%Y-%m-%d")
        if d1 == d2:
            txt = f"{GIORNI_SETT[dt1.weekday()]} {dt1.day} {MESI_BREVE[dt1.month]} {dt1.year}"
        elif dt1.month == dt2.month:
            txt = f"Dal {dt1.day} al {dt2.day} {MESI_BREVE[dt2.month]} {dt2.year}"
        else:
            txt = f"Dal {dt1.day} {MESI_BREVE[dt1.month]} al {dt2.day} {MESI_BREVE[dt2.month]} {dt2.year}"
        return f"{txt} · Ore {ora}" if ora else txt
    except Exception:
        return d1


def normalizza_citta(ev, default):
    campi = [ev.get("citta", ""), ev.get("luogo", ""), ev.get("titolo", ""), ev.get("descrizione", "")]
    for campo in campi:
        low = campo.lower()
        for k, v in CITTA_MAP.items():
            if re.search(rf"\b{re.escape(k)}\b", low):
                return v
    return (ev.get("citta") or default).strip().title()


def normalizza_cat(cat):
    c = (cat or "").strip().lower()
    for valid in CATEGORIE_OK:
        if c == valid.lower():
            return valid
    for k, v in MAPPA_CAT.items():
        if k in c:
            return v
    return "Altro"


def classifica_cat(testo):
    t = testo.lower()
    if any(k in t for k in ("dj set", "discoteca", "club", "party", "notte")):
        return "Locali & Serate"
    if any(k in t for k in ("apericena", "aperitivo", "serata")):
        return "Attività serali"
    if any(k in t for k in ("sagra", "degustazion", "street food", "castagne", "novello", "mercatin")):
        return "Sagre & Food"
    if any(k in t for k in ("concerto", "musica", "live", "band", "teatro", "spettacolo", "cabaret", "musical", "commedia")):
        return "Musica & Concerti"
    if any(k in t for k in ("bambin", "famigl", "laboratori", "animazion", "natale", "babbo natale", "presepe", "luminarie")):
        return "Famiglie & Bambini"
    if any(k in t for k in ("escursion", "trekking", "passeggiat", "camminat", "saline", "bosco", "parco")):
        return "Natura & Escursioni"
    return "Attività diurne"


def pulisci_evento(ev, citta_def, urls_ok):
    citta = normalizza_citta(ev, citta_def)
    url = (ev.get("fonteUrl") or "").strip()
    dom = urlparse(url).netloc.lower()
    if url not in urls_ok and dom not in DOMINI_OK:
        url = FALLBACK_URL.get(citta, "https://www.cerignolaviva.it/eventi/")
    d_ini = (ev.get("dataInizio") or "").strip()[:10]
    d_fin = (ev.get("dataFine") or d_ini).strip()[:10]
    luogo = re.sub(r"\s+", " ", (ev.get("luogo") or "")).strip()
    return {
        "tipoContenuto": "evento",
        "citta": citta,
        "categoria": normalizza_cat(ev.get("categoria")),
        "titolo": re.sub(r"\s+", " ", (ev.get("titolo") or "")).strip()[:85],
        "dataTesto": re.sub(r"\s+", " ", (ev.get("dataTesto") or "")).strip(),
        "dataInizio": d_ini,
        "dataFine": d_fin,
        "luogo": luogo,
        "indirizzoMappa": (ev.get("indirizzoMappa") or f"{luogo}, {citta}").strip(),
        "costo": (ev.get("costo") or "Da verificare").strip(),
        "descrizione": re.sub(r"\s+", " ", (ev.get("descrizione") or "")).strip()[:220],
        "fonteUrl": url
    }


def evento_valido(ev):
    oggi = oggi_iso()
    max_d = (datetime.now() + timedelta(days=100)).strftime("%Y-%m-%d")
    d1, d2 = ev.get("dataInizio", ""), ev.get("dataFine", "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d1) or not re.match(r"^\d{4}-\d{2}-\d{2}$", d2):
        return False
    if d2 < oggi or d1 > d2 or d1 > max_d:
        return False
    titolo = ev.get("titolo", "")
    luogo = ev.get("luogo", "")
    if len(titolo) < 6 or len(luogo) < 4:
        return False
    if luogo.lower() in (ev.get("citta", "").lower(), "da definire", "da verificare"):
        return False
    testo = f"{titolo} {ev.get('descrizione', '')} {ev.get('dataTesto', '')} {luogo}"
    if REGEX_VIETATE.search(testo):
        return False
    if not REGEX_SVAGO_OK.search(testo):
        return False
    return True


def estrai_data_pubblicazione(soup):
    meta = soup.find("meta", property="article:published_time")
    if meta and meta.get("content"):
        s = str(meta["content"])[:10]
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            try:
                return datetime.strptime(s, "%Y-%m-%d")
            except ValueError:
                pass
    t_tag = soup.find("time", attrs={"datetime": True})
    if t_tag:
        s = str(t_tag["datetime"])[:10]
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            try:
                return datetime.strptime(s, "%Y-%m-%d")
            except ValueError:
                pass
    return None


def estrai_date_deterministiche(testo, pub_dt=None):
    oggi = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    max_dt = oggi + timedelta(days=100)
    pulito = re.sub(r"(?:pubblicato|aggiornato)\s+(?:il\s+)?\d{1,2}\s+[a-zà]+\s+202\d", " ", testo.lower())
    ora_m = re.search(r"\bore\s+(\d{1,2}[:.]\d{2})\b", pulito)
    ora = ora_m.group(1).replace(".", ":") if ora_m else ""
    m_pat = "|".join(MESI.keys())

    # 1. Dal G1 M1 al G2 M2
    for m in re.finditer(rf"\bdal\s+(\d{{1,2}})\s+({m_pat})\s+al\s+(\d{{1,2}})\s+({m_pat})(?:\s+(202[6-9]))?\b", pulito):
        g1, m1, g2, m2 = int(m.group(1)), MESI[m.group(2)], int(m.group(3)), MESI[m.group(4)]
        y2 = risolvi_anno(m2, m.group(5), oggi)
        y1 = y2 - 1 if m1 > m2 else y2
        try:
            dt1, dt2 = datetime(y1, m1, g1), datetime(y2, m2, g2)
            if dt2 >= oggi and dt1 <= max_dt and dt1 <= dt2:
                d1, d2 = dt1.strftime("%Y-%m-%d"), dt2.strftime("%Y-%m-%d")
                return d1, d2, formatta_data(d1, d2, ora)
        except ValueError:
            pass

    # 2. Dal G1 al G2 Mese
    for m in re.finditer(rf"\bdal\s+(\d{{1,2}})\s+al\s+(\d{{1,2}})\s+({m_pat})(?:\s+(202[6-9]))?\b", pulito):
        g1, g2, mese = int(m.group(1)), int(m.group(2)), MESI[m.group(3)]
        y = risolvi_anno(mese, m.group(4), oggi)
        try:
            dt1, dt2 = datetime(y, mese, g1), datetime(y, mese, g2)
            if dt2 >= oggi and dt1 <= max_dt and dt1 <= dt2:
                d1, d2 = dt1.strftime("%Y-%m-%d"), dt2.strftime("%Y-%m-%d")
                return d1, d2, formatta_data(d1, d2, ora)
        except ValueError:
            pass

    # 3. Date testuali singole (es. 28 novembre, 6 dicembre, 6 gennaio)
    trovate = []
    for m in re.finditer(rf"\b(\d{{1,2}})\s+({m_pat})(?:\s+(202[6-9]))?\b", pulito):
        g, mese = int(m.group(1)), MESI[m.group(2)]
        y = risolvi_anno(mese, m.group(3), oggi)
        try:
            dt = datetime(y, mese, g)
            if oggi <= dt <= max_dt:
                trovate.append(dt)
        except ValueError:
            pass

    # 4. Date numeriche (es. 28/11/2026 o 28/11)
    for m in re.finditer(r"\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](202[6-9]))?\b", pulito):
        g, mese = int(m.group(1)), int(m.group(2))
        if 1 <= mese <= 12 and 1 <= g <= 31:
            y = risolvi_anno(mese, m.group(3), oggi)
            try:
                dt = datetime(y, mese, g)
                if oggi <= dt <= max_dt:
                    trovate.append(dt)
            except ValueError:
                pass

    if trovate:
        dt_min = min(trovate)
        dt_max = max(trovate) if (max(trovate) - dt_min).days <= 14 else dt_min
        d1, d2 = dt_min.strftime("%Y-%m-%d"), dt_max.strftime("%Y-%m-%d")
        return d1, d2, formatta_data(d1, d2, ora)

    # 5. Date relative rispetto alla data di pubblicazione recente (es. "questo sabato", "nel weekend")
    ref = pub_dt if (pub_dt and 0 <= (oggi - pub_dt).days <= 7) else None
    if ref:
        wd = ref.weekday()
        if any(k in pulito for k in ("nel weekend", "fine settimana", "sabato e domenica")):
            sat = ref + timedelta(days=(5 - wd) % 7)
            sun = sat + timedelta(days=1)
            if sun >= oggi:
                d1, d2 = max(sat, oggi).strftime("%Y-%m-%d"), sun.strftime("%Y-%m-%d")
                return d1, d2, formatta_data(d1, d2, ora)
        for nome_g, target_wd in (("venerdì", 4), ("venerdi", 4), ("sabato", 5), ("domenica", 6)):
            if re.search(rf"\b{nome_g}\b", pulito):
                dt_g = ref + timedelta(days=(target_wd - wd) % 7)
                if dt_g >= oggi:
                    d1 = dt_g.strftime("%Y-%m-%d")
                    return d1, d1, formatta_data(d1, d1, ora)

    return None, None, ""


def estrai_luogo_reale(testo, citta):
    pats = [
        r"(?:Dove|Luogo|Location)\s*:\s*([^\n|.;]{4,60})",
        r"\bpresso\s+(?:il|la|lo|l'|i|gli|le)?\s*([A-ZÀ-Ú0-9][^\n|,.;]{3,55})",
        r"\b(?:al|allo|alla|all'|in|nel|nella|sul|sulla)\s+((?:Teatro|Castello|Palazzo|Piazza|Villa\s+Comunale|Auditorium|Parco|Biblioteca|Cinema|Chiostro|Sala|Corso|Via|Lungomare|Arena|Ex\s+Opera|Laboratorio\s+Urbano|Pub|Club|Borgo)\s+[A-ZÀ-Ú0-9][^\n|,.;]{2,50})"
    ]
    for pat in pats:
        m = re.search(pat, testo)
        if m:
            luogo = re.sub(r"\s+", " ", m.group(1)).strip(" -–—:,.")
            if 4 <= len(luogo) <= 60 and "articolo" not in luogo.lower():
                return luogo
    low = testo.lower()
    if any(k in low for k in ("mercatin", "luminarie", "villaggio di natale", "centro storico", "lungomare", "corso")):
        return f"Centro storico, {citta}"
    return ""


def raccogli_portale(url_indice, citta_def):
    eventi_py = []
    schede_ai = []
    urls_ok = set()
    try:
        r = requests.get(url_indice, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return [], "", set()
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "aside", "form"]):
            tag.decompose()

        dom = "/".join(url_indice.split("/")[:3])
        anni_old = [f"/{y}/" for y in range(2010, datetime.now().year)]
        links = []
        for a in soup.find_all("a", href=True):
            href = urljoin(url_indice, a["href"]).split("#")[0]
            low = href.lower()
            if not href.startswith(dom) or href.rstrip("/") == url_indice.rstrip("/"):
                continue
            if any(x in low for x in PATH_ESCLUSI + anni_old):
                continue
            path_clean = urlparse(href).path.strip("/")
            if len(path_clean) < 12 or "/" not in path_clean:
                continue
            txt = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            if len(txt) < 15 or REGEX_VIETATE.search(txt):
                continue
            if href not in links:
                links.append(href)

        for link in links[:15]:
            try:
                rp = requests.get(link, headers=HEADERS, timeout=10)
                if rp.status_code != 200:
                    continue
                rp.encoding = rp.apparent_encoding or "utf-8"
                sp = BeautifulSoup(rp.text, "html.parser")
                pub_dt = estrai_data_pubblicazione(sp)
                if pub_dt and (datetime.now() - pub_dt).days > 35:
                    continue

                for tag in sp(["script", "style", "nav", "footer", "aside", "form"]):
                    tag.decompose()

                box = sp.find("article") or sp.find("main") or sp
                h1 = box.find("h1") or sp.find("h1")
                titolo = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else ""
                if len(titolo) < 8 or REGEX_VIETATE.search(titolo):
                    continue

                righe = []
                for el in box.find_all(["p", "li", "dd", "h3", "div", "span"]):
                    if el.name in ("div", "span") and el.find(["p", "div", "section", "article", "ul"]):
                        continue
                    t = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
                    low_t = t.lower()
                    if any(b in low_t for b in ("adblocker", "ci stai leggendo", "cookie", "abbonati", "newsletter", "leggi anche", "pubblicato il", "aggiornato il")):
                        continue
                    if 14 <= len(t) <= 550 and t not in righe:
                        righe.append(t)

                corpo = " | ".join(righe[:12])[:1100]
                full = f"{titolo} | {corpo}"
                if len(corpo) < 40 or REGEX_VIETATE.search(full):
                    continue
                if not REGEX_SVAGO_OK.search(full):
                    continue

                urls_ok.add(link)
                citta = normalizza_citta({"citta": citta_def, "titolo": titolo, "descrizione": corpo[:400]}, citta_def)
                d1, d2, d_txt = estrai_date_deterministiche(full, pub_dt)
                luogo = estrai_luogo_reale(full, citta)

                if d1 and d2 and luogo:
                    desc = next((x for x in righe if len(x) >= 45 and x != titolo and REGEX_SVAGO_OK.search(x)), "")
                    if not desc:
                        desc = next((x for x in righe if len(x) >= 45 and x != titolo), f"Appuntamento in programma a {citta} ({d_txt}).")
                    low_f = full.lower()
                    costo = "Ingresso libero" if "ingresso libero" in low_f or "gratuit" in low_f else "Da verificare"
                    eventi_py.append({
                        "tipoContenuto": "evento",
                        "citta": citta,
                        "categoria": classifica_cat(full),
                        "titolo": titolo[:85],
                        "dataTesto": d_txt,
                        "dataInizio": d1,
                        "dataFine": d2,
                        "luogo": luogo,
                        "indirizzoMappa": f"{luogo}, {citta}",
                        "costo": costo,
                        "descrizione": desc[:220],
                        "fonteUrl": link
                    })
                else:
                    schede_ai.append(f"[{citta}] URL: {link}\nTITOLO: {titolo}\nTESTO: {corpo[:650]}")
            except Exception:
                continue

        print(f"Fonte {citta_def}: estratti_diretti={len(eventi_py)} | extra_ai={len(schede_ai)}")
    except Exception as e:
        print(f"Errore fonte {citta_def}:", e)

    return eventi_py, "\n\n---\n\n".join(schede_ai)[:5500], urls_ok


def scopri_modelli_gemini(api_key):
    try:
        r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}", timeout=20)
        if r.status_code == 200:
            tutti = []
            for m in r.json().get("models", []):
                if "generateContent" not in m.get("supportedGenerationMethods", []):
                    continue
                nome = m.get("name", "").replace("models/", "")
                low = nome.lower()
                if not low.startswith("gemini-"):
                    continue
                if any(x in low for x in ("embedding", "imagen", "veo", "tts", "audio", "robotics", "computer", "research", "image")):
                    continue
                tutti.append(nome)

            def priorita(n):
                l = n.lower()
                p = 0
                if "3.5-flash-lite" in l:
                    p -= 40
                elif "flash-lite" in l:
                    p -= 30
                elif "flash" in l:
                    p -= 20
                elif "pro" in l:
                    p -= 10
                return (p, l)

            ordinati = sorted(tutti, key=priorita)
            if ordinati:
                print("Modelli Gemini attivi:", ", ".join(ordinati))
                return ordinati
    except Exception as e:
        print("Errore verifica modelli:", e)
    return ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite-preview", "gemini-2.5-pro"]


def estrai_extra_con_gemini(api_key, modelli, testo_schede):
    if not api_key or not testo_schede.strip():
        return []
    oggi = oggi_iso()
    giorno_sett = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"][datetime.now().weekday()]
    prompt = (
        f"Curatore 'Che Si Fa Cerignola'. Oggi è {giorno_sett} {oggi}. "
        f"Estrai SOLO gli eventi di svago (concerti, serate, sagre, mercatini natalizi, teatro, bambini, escursioni) "
        f"presenti nei testi qui sotto con dataFine >= '{oggi}' e luogo reale.\n"
        "Scarta cronaca, mostre fotografiche, convegni, politica, sport, religione. Non inventare nulla.\n"
        "Restituisci SOLO JSON array con chiavi: tipoContenuto, citta, categoria, titolo, dataTesto, dataInizio, dataFine, luogo, indirizzoMappa, costo, descrizione, fonteUrl.\n\n"
        f"{testo_schede[:5500]}"
    )

    for mod in modelli:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
        }
        try:
            r = requests.post(url, json=payload, timeout=40)
            if r.status_code in (404, 429):
                continue
            if r.status_code != 200:
                continue
            parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            raw = "\n".join(p.get("text", "") for p in parts).strip()
            raw = re.sub(r"^`{3}json\s*|`{3}$", "", raw, flags=re.I).strip()
            m = re.search(r"\[.*\]", raw, flags=re.DOTALL)
            dati = json.loads(m.group(0) if m else raw)
            if isinstance(dati, list):
                print(f"[Gemini] Estratti {len(dati)} eventi extra con {mod}.")
                return dati
        except Exception:
            continue
    print("[Gemini] Nessun modello disponibile (quota/404), uso gli eventi estratti direttamente da Python.")
    return []


def sono_duplicati(a, b):
    if a.get("citta", "").lower() != b.get("citta", "").lower():
        return False
    if a.get("dataInizio") != b.get("dataInizio"):
        return False
    t1 = re.sub(r"[^a-z0-9\s]", "", a.get("titolo", "").lower())
    t2 = re.sub(r"[^a-z0-9\s]", "", b.get("titolo", "").lower())
    return SequenceMatcher(None, t1, t2).ratio() >= 0.72


# ==============================================================================
# ESECUZIONE PRINCIPALE (MOTORE DETERMINISTICO + AI OPZIONALE)
# ==============================================================================
api_key = os.environ.get("GEMINI_API_KEY", "").strip()
urls_validi = set()

try:
    with open("eventi.json", "r", encoding="utf-8") as f:
        esistenti = json.load(f)
except Exception:
    esistenti = []

consolidati = []
for raw in (esistenti if isinstance(esistenti, list) else []):
    ev = pulisci_evento(raw, raw.get("citta") or "Cerignola", urls_validi)
    if evento_valido(ev) and not any(sono_duplicati(x, ev) for x in consolidati):
        consolidati.append(ev)

nuovi = []
testi_extra = []
for fonte in FONTI_LOCALI:
    evs_py, txt_ai, u_ok = raccogli_portale(fonte["url"], fonte["citta"])
    urls_validi.update(u_ok)
    if txt_ai:
        testi_extra.append(txt_ai)
    for raw_ev in evs_py:
        ev = pulisci_evento(raw_ev, fonte["citta"], urls_validi)
        if evento_valido(ev):
            nuovi.append(ev)

if testi_extra and api_key:
    modelli_attivi = scopri_modelli_gemini(api_key)
    for raw_ev in estrai_extra_con_gemini(api_key, modelli_attivi, "\n\n===\n\n".join(testi_extra)):
        ev = pulisci_evento(raw_ev, "Cerignola", urls_validi)
        if evento_valido(ev):
            nuovi.append(ev)

aggiunti = 0
for ev in nuovi:
    if not any(sono_duplicati(x, ev) for x in consolidati):
        consolidati.append(ev)
        aggiunti += 1

lista_finale = sorted(
    consolidati,
    key=lambda x: (x.get("dataInizio", "9999-12-31"), priorita_km(x.get("citta")), x.get("titolo", "").lower())
)

with open("eventi.json", "w", encoding="utf-8") as f:
    json.dump(lista_finale, f, ensure_ascii=False, indent=2)

report = {
    "aggiornatoAl": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "totaleContenuti": len(lista_finale),
    "nuoviAggiunti": aggiunti,
    "topComuni": dict(Counter(e["citta"] for e in lista_finale).most_common(15))
}
with open("report_copertura.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("Fine:", len(lista_finale), "eventi")
