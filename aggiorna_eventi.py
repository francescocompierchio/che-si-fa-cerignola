import os
import re
import json
import requests
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8"
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

DOMINI_OK = {urlparse(f["url"]).netloc.lower() for f in FONTI_EVENTI}

FALLBACK_URL = {
    "Cerignola": "https://www.cerignolaviva.it/eventi/",
    "Foggia": "https://www.foggiatoday.it/eventi/",
    "Barletta": "https://www.barlettaviva.it/eventi/",
    "Trani": "https://www.traniviva.it/eventi/",
    "Bisceglie": "https://www.bisceglieviva.it/eventi/",
    "Andria": "https://www.andriaviva.it/eventi/",
    "Manfredonia": "https://www.manfredonianews.it/category/eventi/",
}

CATEGORIE_OK = [
    "Locali & Serate", "Attività serali", "Musica & Concerti", "Sagre & Food",
    "Famiglie & Bambini", "Natura & Escursioni", "Attività diurne", "Altro"
]

MAPPA_CAT = {
    "serate": "Locali & Serate", "locali": "Locali & Serate", "dj set": "Locali & Serate",
    "attività serali": "Attività serali", "apericena": "Attività serali",
    "musica": "Musica & Concerti", "concerti": "Musica & Concerti", "teatro": "Musica & Concerti",
    "sagra": "Sagre & Food", "sagre": "Sagre & Food", "food": "Sagre & Food",
    "famiglie": "Famiglie & Bambini", "bambini": "Famiglie & Bambini",
    "natura": "Natura & Escursioni", "escursioni": "Natura & Escursioni",
    "attività diurne": "Attività diurne", "cultura": "Attività diurne"
}

LISTA_VIETATE = [
    "cronaca", "politica", "alimentazione", "nutrizione", "dieta", "screening",
    "vescovo", "diocesi", "parrocchia", "santa messa", "processione", "devozione",
    "beneficenza", "raccolta fondi", "raccolta alimentare",
    "bilancio", "si è svolta", "si è tenuto", "annullato", "rinviato", "indagine di mercato",
    "meteo", "libeccio", "allerta meteo",
    "frode", "riciclaggio", "indagati", "indagato", "sequestri", "sequestro",
    "scontro tra auto", "morti e feriti", "questore", "sospende la licenza",
    "arresto", "arresti", "rapina", "incidente", "incendio", "denuncia",
    "tribunale", "carabinieri", "polizia", "guardia di finanza",
    "consiglio comunale", "giunta", "elezioni", "partito", "sciopero", "ospedale", "asl",
    "furto", "truffa", "omicidio", "ferito", "morto", "lutto", "cordoglio",
    "convegno", "conferenza", "tavola rotonda", "dibattito", "seminario",
    "presentazione del libro", "presentazione libro",
    "sport", "torneo", "podistica", "partita", "stadio", "palazzetto",
    "volley", "calcio", "basket", "maratona", "campionato", "serie c", "serie d"
]

LISTA_EVENTO_OK = [
    "concerto", "concerti", "spettacolo", "spettacoli", "teatro", "teatrale",
    "cabaret", "musical", "commedia", "rassegna", "festival", "live", "musica", "musicale",
    "dj set", "serata", "serate", "aperitivo", "apericena", "party", "discoteca",
    "sagra", "sagre", "degustazione", "degustazioni", "street food",
    "mercatino", "mercatini", "natale", "natalizio", "natalizi", "babbo natale",
    "presepe", "luminarie", "bambini", "famiglie", "laboratorio", "laboratori",
    "animazione", "escursione", "escursioni", "trekking", "passeggiata",
    "visita guidata", "visite guidate", "mostra", "cinema", "proiezione", "festa"
]

REGEX_VIETATE = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in LISTA_VIETATE) + r")\b", re.I)
REGEX_EVENTO_OK = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in LISTA_EVENTO_OK) + r")\b", re.I)

PATH_ESCLUSI = [
    "/tag/", "/author/", "/page/", "/video/", "/foto/", "/meteo/", "/necrologi/",
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
    if any(k in t for k in ("sagra", "degustazion", "street food", "mercatin")):
        return "Sagre & Food"
    if any(k in t for k in ("concerto", "musica", "live", "teatro", "spettacolo", "cabaret", "musical")):
        return "Musica & Concerti"
    if any(k in t for k in ("bambin", "famigl", "laboratori", "animazion", "natale", "babbo natale", "presepe")):
        return "Famiglie & Bambini"
    if any(k in t for k in ("escursion", "trekking", "passeggiat", "natura", "parco", "saline", "bosco")):
        return "Natura & Escursioni"
    if any(k in t for k in ("dj set", "serata", "discotec", "party", "apericena", "aperitivo")):
        return "Locali & Serate"
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
        "fonteUrl": url,
        "_verificato": bool(ev.get("_verificato", False))
    }


def evento_valido(ev):
    oggi = oggi_iso()
    max_d = (datetime.now() + timedelta(days=120)).strftime("%Y-%m-%d")
    d1, d2 = ev.get("dataInizio", ""), ev.get("dataFine", "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d1) or not re.match(r"^\d{4}-\d{2}-\d{2}$", d2):
        return False
    if d2 < oggi or d1 < oggi or d1 > d2 or d1 > max_d:
        return False
    if len(ev.get("titolo", "")) < 5 or len(ev.get("luogo", "")) < 3:
        return False
    testo = f"{ev['titolo']} {ev['descrizione']} {ev['dataTesto']} {ev['luogo']}"
    if REGEX_VIETATE.search(testo):
        return False
    if not ev.get("_verificato") and not REGEX_EVENTO_OK.search(testo):
        return False
    return True


def estrai_date(testo):
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
                d1, d2 = max(dt1, oggi).strftime("%Y-%m-%d"), dt2.strftime("%Y-%m-%d")
                return d1, d2, formatta_data(dt1.strftime("%Y-%m-%d"), d2, ora)
        except ValueError:
            pass

    # 2. Dal G1 al G2 Mese
    for m in re.finditer(rf"\bdal\s+(\d{{1,2}})\s+al\s+(\d{{1,2}})\s+({m_pat})(?:\s+(202[6-9]))?\b", pulito):
        g1, g2, mese = int(m.group(1)), int(m.group(2)), MESI[m.group(3)]
        y = risolvi_anno(mese, m.group(4), oggi)
        try:
            dt1, dt2 = datetime(y, mese, g1), datetime(y, mese, g2)
            if dt2 >= oggi and dt1 <= max_dt and dt1 <= dt2:
                d1, d2 = max(dt1, oggi).strftime("%Y-%m-%d"), dt2.strftime("%Y-%m-%d")
                return d1, d2, formatta_data(dt1.strftime("%Y-%m-%d"), d2, ora)
        except ValueError:
            pass

    # 3. Date testuali singole (es. 28 novembre, 6 gennaio)
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

    return None, None, ""


def estrai_luogo(testo, citta):
    pats = [
        r"(?:Dove|Luogo|Location)\s*:\s*([^\n|.;]{4,60})",
        r"\bpresso\s+(?:il|la|lo|l'|i|gli|le)?\s*([A-ZÀ-Ú0-9][^\n|,.;]{3,55})",
        r"\b(?:al|allo|alla|all'|in|nel|nella)\s+((?:Teatro|Castello|Palazzo|Piazza|Villa\s+Comunale|Auditorium|Parco|Biblioteca|Museo|Cinema|Chiostro|Sala|Corso|Via)\s+[A-ZÀ-Ú0-9][^\n|,.;]{2,50})"
    ]
    for pat in pats:
        m = re.search(pat, testo)
        if m:
            luogo = re.sub(r"\s+", " ", m.group(1)).strip(" -–—:,.")
            if 4 <= len(luogo) <= 60:
                return luogo
    return f"{citta} (sede nell'articolo)"


def estrai_json_ld(soup, citta_def, url_pag):
    oggi = oggi_iso()
    risultati = []
    for sc in soup.find_all("script", type="application/ld+json"):
        try:
            dati = json.loads(sc.string or sc.get_text() or "{}")
            lista = dati.get("@graph", [dati]) if isinstance(dati, dict) else (dati if isinstance(dati, list) else [])
            for obj in lista:
                if not isinstance(obj, dict):
                    continue
                if "Event" not in str(obj.get("@type", "")):
                    continue
                nome = re.sub(r"\s+", " ", str(obj.get("name", ""))).strip()
                d1 = str(obj.get("startDate", ""))[:10]
                d2 = str(obj.get("endDate", ""))[:10] or d1
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", d1) or d2 < oggi:
                    continue
                loc = obj.get("location", {})
                luogo = loc.get("name", "") if isinstance(loc, dict) else str(loc)
                desc = re.sub(r"\s+", " ", str(obj.get("description", ""))).strip()[:220]
                full_ld = f"{nome} {desc} {luogo}"
                if REGEX_VIETATE.search(full_ld) or not REGEX_EVENTO_OK.search(full_ld):
                    continue
                if nome:
                    risultati.append({
                        "tipoContenuto": "evento",
                        "citta": citta_def,
                        "categoria": classifica_cat(full_ld),
                        "titolo": nome[:85],
                        "dataTesto": formatta_data(d1, d2),
                        "dataInizio": d1,
                        "dataFine": d2,
                        "luogo": luogo or f"{citta_def} (vedi fonte)",
                        "indirizzoMappa": f"{luogo or citta_def}, {citta_def}",
                        "costo": "Da verificare",
                        "descrizione": desc or f"Evento in programma a {citta_def}.",
                        "fonteUrl": str(obj.get("url") or url_pag),
                        "_verificato": True
                    })
        except Exception:
            continue
    return risultati


def raccogli_portale(url_indice, citta_def):
    testi = []
    eventi = []
    urls_ok = set()
    try:
        r = requests.get(url_indice, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"Fonte {citta_def}: HTTP {r.status_code}")
            return "", [], set()
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        eventi.extend(estrai_json_ld(soup, citta_def, url_indice))

        for tag in soup(["script", "style", "nav", "footer", "aside", "form", "header"]):
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

        for link in links[:20]:
            try:
                rp = requests.get(link, headers=HEADERS, timeout=10)
                if rp.status_code != 200:
                    continue
                rp.encoding = rp.apparent_encoding or "utf-8"
                sp = BeautifulSoup(rp.text, "html.parser")
                ev_ld = estrai_json_ld(sp, citta_def, link)
                if ev_ld:
                    eventi.extend(ev_ld)
                    urls_ok.add(link)

                for tag in sp(["script", "style", "nav", "footer", "aside", "form", "header"]):
                    tag.decompose()

                h1 = sp.find(["h1", "h2"])
                titolo = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else ""
                if len(titolo) < 8 or REGEX_VIETATE.search(titolo):
                    continue

                paragrafi = []
                for p in sp.find_all(["p", "li", "dd", "h2", "h3"]):
                    t = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
                    low_t = t.lower()
                    if any(b in low_t for b in ("adblocker", "ci stai leggendo", "cookie", "abbonati", "newsletter")):
                        continue
                    if 18 <= len(t) <= 900 and t not in paragrafi:
                        paragrafi.append(t)

                full = f"{titolo} | " + " | ".join(paragrafi[:10])
                if REGEX_VIETATE.search(full):
                    continue
                if not REGEX_EVENTO_OK.search(full):
                    continue

                d1, d2, d_txt = estrai_date(full)
                if d1 and d2:
                    citta = normalizza_citta({"citta": citta_def, "titolo": titolo, "descrizione": full[:350]}, citta_def)
                    luogo = estrai_luogo(full, citta)
                    desc = next((x for x in paragrafi if len(x) >= 45 and x != titolo and REGEX_EVENTO_OK.search(x)), "")
                    if not desc:
                        desc = next((x for x in paragrafi if len(x) >= 45 and x != titolo), f"Evento in programma a {citta} ({d_txt}).")
                    low_full = full.lower()
                    costo = "Ingresso libero" if "ingresso libero" in low_full or "gratuit" in low_full else "Da verificare"
                    eventi.append({
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
                        "fonteUrl": link,
                        "_verificato": True
                    })
                    urls_ok.add(link)
                    testi.append(f"[{citta}] ({link}) {titolo} | {d_txt} | {luogo} | {desc[:150]}")
            except Exception:
                continue
    except Exception as e:
        print(f"Errore fonte {citta_def}:", e)

    return "\n".join(testi)[:5000], eventi, urls_ok


def filtra_con_gemini(api_key, testo):
    if not api_key or not testo.strip():
        return []
    oggi = oggi_iso()
    modelli = ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-2.5-flash"]
    prompt = (
        f"Curatore 'Che Si Fa Cerignola'. Oggi è {oggi}. "
        f"Normalizza SOLO gli eventi ricreativi/culturali reali presenti qui sotto (dataFine >= '{oggi}'). "
        "DIVIETO ASSOLUTO di inventare eventi o includere cronaca, politica, sport, religione, beneficenza. "
        "Usa solo l'URL tra parentesi in fonteUrl. Restituisci SOLO JSON array con chiavi: "
        "tipoContenuto, citta, categoria, titolo, dataTesto, dataInizio, dataFine, luogo, indirizzoMappa, costo, descrizione, fonteUrl.\n\n"
        f"{testo[:12000]}"
    )
    for mod in modelli:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"}
        }
        try:
            r = requests.post(url, json=payload, timeout=45)
            if r.status_code == 429:
                print(f"[Gemini] Quota 429 su {mod}, salto.")
                continue
            if r.status_code != 200:
                continue
            parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            raw = "\n".join(p.get("text", "") for p in parts).strip()
            raw = re.sub(r"^`{3}json\s*|`{3}$", "", raw, flags=re.I).strip()
            m = re.search(r"\[.*\]", raw, flags=re.DOTALL)
            dati = json.loads(m.group(0) if m else raw)
            if isinstance(dati, list):
                print(f"[Gemini] Validati {len(dati)} eventi con {mod}.")
                return dati
        except Exception:
            continue
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
# ESECUZIONE PRINCIPALE
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
testi_ai = []
for fonte in FONTI_EVENTI:
    t, evs, u_ok = raccogli_portale(fonte["url"], fonte["citta"])
    urls_validi.update(u_ok)
    if t:
        testi_ai.append(t)
    ok_count = 0
    for e in evs:
        ev = pulisci_evento(e, fonte["citta"], urls_validi)
        if evento_valido(ev):
            nuovi.append(ev)
            ok_count += 1
    print(f"Fonte {fonte['citta']}: {ok_count} eventi validi")

for e in filtra_con_gemini(api_key, "\n\n".join(testi_ai)):
    ev = pulisci_evento(e, "Cerignola", urls_validi)
    if evento_valido(ev):
        nuovi.append(ev)

aggiunti = 0
for ev in nuovi:
    if not any(sono_duplicati(x, ev) for x in consolidati):
        consolidati.append(ev)
        aggiunti += 1

lista_finale = []
for item in sorted(
    consolidati,
    key=lambda x: (x.get("dataInizio", "9999-12-31"), priorita_km(x.get("citta")), x.get("titolo", "").lower())
):
    pulito = {k: v for k, v in item.items() if not k.startswith("_")}
    lista_finale.append(pulito)

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
