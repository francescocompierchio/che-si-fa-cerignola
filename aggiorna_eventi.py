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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9"
}

# Parole obbligatorie per far passare un articolo dai portali cittadini (solo Natale, Luminarie ed Escursioni)
PAROLE_NATALE_OUTDOOR = [
    "natale", "natalizio", "natalizia", "natalizi", "natalizie",
    "luminarie", "accensione", "albero di natale", "villaggio di babbo natale",
    "babbo natale", "mercatini", "mercatino", "presepe", "pista di ghiaccio",
    "escursione", "escursioni", "trekking", "passeggiata", "camminata",
    "visita guidata", "visite guidate", "saline", "castel del monte", "monticchio"
]
REGEX_NATALE_OUTDOOR = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in PAROLE_NATALE_OUTDOOR) + r")\b", re.I)

FONTI_SPETTACOLO = [
    # --- 1. CERIGNOLA ---
    {
        "nome": "Teatro Mercadante Cerignola",
        "url": "https://www.teatromercadantecerignola.it/stagione-teatrale-2026-27/",
        "tipo": "pagina_singola",
        "citta_fissa": "Cerignola",
        "blocco": "Cerignola"
    },
    {
        "nome": "Virgilio Eventi Cerignola",
        "url": "https://www.virgilio.it/italia/cerignola/eventi",
        "tipo": "virgilio",
        "citta_fissa": "Cerignola",
        "blocco": "Cerignola"
    },
    {
        "nome": "Eventbrite Cerignola",
        "url": "https://www.eventbrite.it/d/italy--cerignola/events/",
        "tipo": "eventbrite",
        "citta_fissa": "Cerignola",
        "blocco": "Cerignola"
    },
    {
        "nome": "Natale & Luminarie Cerignola",
        "url": "https://www.cerignolaviva.it/eventi/",
        "tipo": "solo_natale_outdoor",
        "citta_fissa": "Cerignola",
        "blocco": "Cerignola"
    },

    # --- 2. CAPITANATA ENTRO 50 KM ---
    {
        "nome": "Teatro Giordano Foggia",
        "url": "https://www.teatrogiordano.it/stagione/2026-2027.html",
        "tipo": "pagina_singola",
        "citta_fissa": "Foggia",
        "blocco": "Capitanata_50km"
    },
    {
        "nome": "Il Tacco di Bacco Foggia",
        "url": "https://iltaccodibacco.it/foggia/",
        "tipo": "tacco_indice",
        "citta_fissa": "",
        "blocco": "Capitanata_50km"
    },
    {
        "nome": "Virgilio Eventi Foggia",
        "url": "https://www.virgilio.it/italia/foggia/eventi",
        "tipo": "virgilio",
        "citta_fissa": "Foggia",
        "blocco": "Capitanata_50km"
    },
    {
        "nome": "Eventbrite Foggia",
        "url": "https://www.eventbrite.it/d/italy--foggia/events/",
        "tipo": "eventbrite",
        "citta_fissa": "Foggia",
        "blocco": "Capitanata_50km"
    },

    # --- 3. BAT ENTRO 50 KM ---
    {
        "nome": "Il Tacco di Bacco BAT",
        "url": "https://iltaccodibacco.it/barletta/",
        "tipo": "tacco_indice",
        "citta_fissa": "",
        "blocco": "BAT_50km"
    },
    {
        "nome": "Palazzo delle Arti Beltrani Trani",
        "url": "https://www.palazzodelleartibeltrani.it/eventi/",
        "tipo": "pagina_singola",
        "citta_fissa": "Trani",
        "blocco": "BAT_50km"
    },
    {
        "nome": "Politeama Italia Bisceglie",
        "url": "https://www.politeamaitalia.com/",
        "tipo": "pagina_singola",
        "citta_fissa": "Bisceglie",
        "blocco": "BAT_50km"
    },
    {
        "nome": "Happyticket BAT",
        "url": "https://www.happyticket.com/it/barletta-andria-trani/biglietti-spettacoli-weekend.htm",
        "tipo": "pagina_singola",
        "citta_fissa": "",
        "blocco": "BAT_50km"
    },
    {
        "nome": "Natale & Luminarie Barletta",
        "url": "https://www.barlettaviva.it/eventi/",
        "tipo": "solo_natale_outdoor",
        "citta_fissa": "Barletta",
        "blocco": "BAT_50km"
    },
    {
        "nome": "Natale & Luminarie Trani",
        "url": "https://www.traniviva.it/eventi/",
        "tipo": "solo_natale_outdoor",
        "citta_fissa": "Trani",
        "blocco": "BAT_50km"
    },
    {
        "nome": "Virgilio Eventi Barletta",
        "url": "https://www.virgilio.it/italia/barletta/eventi",
        "tipo": "virgilio",
        "citta_fissa": "Barletta",
        "blocco": "BAT_50km"
    },
    {
        "nome": "Virgilio Eventi Trani",
        "url": "https://www.virgilio.it/italia/trani/eventi",
        "tipo": "virgilio",
        "citta_fissa": "Trani",
        "blocco": "BAT_50km"
    },
    {
        "nome": "Virgilio Eventi Andria",
        "url": "https://www.virgilio.it/italia/andria/eventi",
        "tipo": "virgilio",
        "citta_fissa": "Andria",
        "blocco": "BAT_50km"
    },
    {
        "nome": "Eventbrite BAT",
        "url": "https://www.eventbrite.it/d/italy--barletta-andria-trani/events/",
        "tipo": "eventbrite",
        "citta_fissa": "",
        "blocco": "BAT_50km"
    },

    # --- 4. PORTALI REGIONALI (TURISMO, ESCURSIONI, TEATRI, SAGRE) ---
    {
        "nome": "Viaggiare in Puglia Eventi",
        "url": "https://www.viaggiareinpuglia.it/it/eventi",
        "tipo": "pagina_singola",
        "citta_fissa": "",
        "blocco": "Regionali_50km"
    },
    {
        "nome": "Puglia Culture Teatri",
        "url": "https://www.pugliaculture.it/eventi/",
        "tipo": "pagina_singola",
        "citta_fissa": "",
        "blocco": "Regionali_50km"
    },
    {
        "nome": "Ciaotickets Puglia",
        "url": "https://www.ciaotickets.com/it/eventi/puglia",
        "tipo": "pagina_singola",
        "citta_fissa": "",
        "blocco": "Regionali_50km"
    },
    {
        "nome": "Ciaotickets Basilicata (Vulture)",
        "url": "https://www.ciaotickets.com/it/eventi/basilicata",
        "tipo": "pagina_singola",
        "citta_fissa": "",
        "blocco": "Regionali_50km"
    },
    {
        "nome": "Eventi e Sagre Puglia",
        "url": "https://www.eventiesagre.it/Eventi_Sagre/Puglia.html",
        "tipo": "pagina_singola",
        "citta_fissa": "",
        "blocco": "Regionali_50km"
    },
    {
        "nome": "PugliaEvents",
        "url": "https://www.pugliaevents.it/it/eventi",
        "tipo": "pagina_singola",
        "citta_fissa": "",
        "blocco": "Regionali_50km"
    }
]

DOMINI_OK = {urlparse(f["url"]).netloc.lower() for f in FONTI_SPETTACOLO} | {
    "eventbrite.it", "www.eventbrite.it", "virgilio.it", "www.virgilio.it",
    "ciaotickets.com", "www.ciaotickets.com", "pugliaculture.it", "www.pugliaculture.it",
    "pugliaevents.it", "www.pugliaevents.it", "eventiesagre.it", "www.eventiesagre.it",
    "viaggiareinpuglia.it", "www.viaggiareinpuglia.it"
}

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
    "Attività serali",
    "Sagre & Food",
    "Famiglie & Bambini",
    "Natura & Escursioni",
    "Attività diurne"
]

MAPPA_CAT = {
    "musica": "Musica & Concerti",
    "concert": "Musica & Concerti",
    "live": "Musica & Concerti",
    "jazz": "Musica & Concerti",
    "tribute": "Musica & Concerti",
    "locali": "Locali & Serate",
    "serat": "Locali & Serate",
    "dj": "Locali & Serate",
    "club": "Locali & Serate",
    "disco": "Locali & Serate",
    "teatr": "Attività serali",
    "cabaret": "Attività serali",
    "commedia": "Attività serali",
    "prosa": "Attività serali",
    "spettacol": "Attività serali",
    "cinema": "Attività serali",
    "sagr": "Sagre & Food",
    "food": "Sagre & Food",
    "degustazion": "Sagre & Food",
    "enogastronom": "Sagre & Food",
    "famigli": "Famiglie & Bambini",
    "bambin": "Famiglie & Bambini",
    "ragazzi": "Famiglie & Bambini",
    "natal": "Famiglie & Bambini",
    "luminar": "Famiglie & Bambini",
    "mercatin": "Famiglie & Bambini",
    "presep": "Famiglie & Bambini",
    "natur": "Natura & Escursioni",
    "escursion": "Natura & Escursioni",
    "trekking": "Natura & Escursioni",
    "passeggiat": "Natura & Escursioni",
    "camminat": "Natura & Escursioni",
    "saline": "Natura & Escursioni",
    "diurn": "Attività diurne",
    "festival": "Attività diurne"
}

PAROLE_SCARTO = [
    "adblocker", "ci stai leggendo", "archivio", "evento si è già concluso",
    "si è svolta", "si è svolto", "si è conclusa", "conquista", "escursionisti",
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
    "cronaca", "politica", "consiglio comunale", "giunta", "elezioni",
    "calcio", "volley", "basket", "torneo", "podistica", "maratona", "campionato"
]

REGEX_SCARTO = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in PAROLE_SCARTO) + r")\b", re.I)

SCHEMA_EVENTI = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "tipoContenuto": {"type": "STRING"},
            "citta": {"type": "STRING"},
            "categoria": {"type": "STRING"},
            "titolo": {"type": "STRING"},
            "dataTesto": {"type": "STRING"},
            "dataInizio": {"type": "STRING"},
            "dataFine": {"type": "STRING"},
            "luogo": {"type": "STRING"},
            "indirizzoMappa": {"type": "STRING"},
            "costo": {"type": "STRING"},
            "descrizione": {"type": "STRING"},
            "fonteUrl": {"type": "STRING"}
        },
        "required": [
            "tipoContenuto", "citta", "categoria", "titolo",
            "dataTesto", "dataInizio", "dataFine", "luogo",
            "indirizzoMappa", "costo", "descrizione", "fonteUrl"
        ]
    }
}


def oggi_iso():
    return datetime.now().strftime("%Y-%m-%d")


def priorita_km(citta):
    if citta == "Cerignola":
        return 0
    if citta in CINTURA_25:
        return 1
    return 2


def risolvi_comune_50km(ev):
    c_raw = (ev.get("citta") or "").strip().lower()
    if c_raw in COMUNI_50KM:
        return COMUNI_50KM[c_raw]
    for k, v in COMUNI_50KM.items():
        if re.search(rf"\b{re.escape(k)}\b", c_raw):
            return v

    altri_campi = f"{ev.get('luogo', '')} {ev.get('titolo', '')} {ev.get('descrizione', '')}".lower()
    for k, v in COMUNI_50KM.items():
        if re.search(rf"\b{re.escape(k)}\b", altri_campi):
            return v
    return ""


def normalizza_cat(cat):
    c = (cat or "").strip().lower()
    if c in ("altro", "other", "varie", ""):
        return ""
    for valid in CATEGORIE_AMMESSE:
        if c == valid.lower():
            return valid
    for k, v in MAPPA_CAT.items():
        if k in c:
            return v
    return ""


def pulisci_evento(ev, urls_ok):
    citta = risolvi_comune_50km(ev)
    cat = normalizza_cat(ev.get("categoria"))
    url = (ev.get("fonteUrl") or "").strip()
    dom = urlparse(url).netloc.lower()
    if url not in urls_ok and dom not in DOMINI_OK:
        url = "https://iltaccodibacco.it/barletta/"

    d_ini = (ev.get("dataInizio") or "").strip()[:10]
    d_fin = (ev.get("dataFine") or d_ini).strip()[:10]
    luogo = re.sub(r"\s+", " ", (ev.get("luogo") or "")).strip()
    if not luogo or luogo.lower() in ("da definire", "da verificare", "n/d", citta.lower()):
        luogo = f"Centro storico / Varie sedi, {citta}"

    return {
        "tipoContenuto": "evento",
        "citta": citta,
        "categoria": cat,
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


def verifica_evento(ev):
    if not ev.get("citta"):
        return False, "fuori_raggio_50km"
    if not ev.get("categoria") or ev.get("categoria") not in CATEGORIE_AMMESSE:
        return False, "categoria_non_svago"

    oggi = oggi_iso()
    max_d = (datetime.now() + timedelta(days=150)).strftime("%Y-%m-%d")
    d1, d2 = ev.get("dataInizio", ""), ev.get("dataFine", "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d1) or not re.match(r"^\d{4}-\d{2}-\d{2}$", d2):
        return False, "formato_data"
    if d2 < oggi:
        return False, f"passato({d2})"
    if d1 > d2 or d1 > max_d:
        return False, f"fuori_finestra({d1})"

    titolo = ev.get("titolo", "")
    if len(titolo) < 5:
        return False, "titolo_corto"

    testo = f"{titolo} {ev.get('descrizione', '')} {ev.get('luogo', '')}"
    m = REGEX_SCARTO.search(testo)
    if m:
        return False, f"scarto({m.group(0)})"

    return True, "ok"


def pulisci_html_testo(sp, max_chars=8500):
    for tag in sp(["script", "style", "nav", "footer", "aside", "form", "noscript", "iframe"]):
        tag.decompose()
    cont = sp.find("main") or sp.find("article") or sp.body or sp
    righe = []
    for raw_line in cont.get_text("\n", strip=True).splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if len(line) < 6:
            continue
        if any(b in line.lower() for b in ("cookie", "privacy", "newsletter", "accedi", "registrati", "cerca gli eventi", "adblocker")):
            continue
        if line not in righe:
            righe.append(line)
    return " | ".join(righe)[:max_chars]


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


def raccogli_fonte(session, fonte):
    schede = []
    urls_ok = set()
    url = fonte["url"]
    nome = fonte["nome"]
    c_fissa = fonte["citta_fissa"]
    tipo = fonte["tipo"]

    try:
        r = session.get(url, timeout=(4, 8))
        if r.status_code != 200:
            print(f"{nome}: HTTP {r.status_code}")
            return [], set()
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        # 1) Pagine cartellone / elenco unico
        if tipo == "pagina_singola":
            testo = pulisci_html_testo(soup, max_chars=8500)
            if len(testo) > 100:
                urls_ok.add(url)
                prefisso = f"CITTÀ FISSA: {c_fissa} | " if c_fissa else ""
                schede.append(f"[{nome}] {prefisso}URL: {url}\nPROGRAMMA COMPLETO:\n{testo}")
            print(f"{nome}: programma caricato ({len(testo)} char)")
            return schede, urls_ok

        # 2) Portali cittadini filtrati SOLO per Luminarie, Natale ed Escursioni/Passeggiate
        if tipo == "solo_natale_outdoor":
            dom = "/".join(url.split("/")[:3])
            links = []
            for a in soup.find_all("a", href=True):
                href = urljoin(url, a["href"]).split("#")[0]
                if not href.startswith(dom) or href.rstrip("/") == url.rstrip("/"):
                    continue
                if any(x in href.lower() for x in ("/archivio", "/tag/", "/author/", "/page/", "/video/", "/foto/")):
                    continue
                txt = re.sub(r"\s+", " ", a.get_text(" ", strip=True) or a.get("title", ""))
                if len(txt) >= 12 and REGEX_NATALE_OUTDOOR.search(txt) and not REGEX_SCARTO.search(txt):
                    if href not in links:
                        links.append(href)

            for link in links[:8]:
                try:
                    rp = session.get(link, timeout=(4, 6))
                    if rp.status_code != 200:
                        continue
                    rp.encoding = rp.apparent_encoding or "utf-8"
                    sp = BeautifulSoup(rp.text, "html.parser")
                    h1 = sp.find("h1")
                    titolo = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else ""
                    if len(titolo) < 6 or REGEX_SCARTO.search(titolo):
                        continue
                    corpo = pulisci_html_testo(sp, max_chars=1200)
                    if not REGEX_NATALE_OUTDOOR.search(f"{titolo} {corpo}") or REGEX_SCARTO.search(corpo[:350]):
                        continue
                    urls_ok.add(link)
                    schede.append(f"[{nome}] CITTÀ FISSA: {c_fissa} | URL: {link}\nTITOLO: {titolo}\nDETTAGLI: {corpo}")
                except Exception:
                    continue

            print(f"{nome}: {len(schede)} schede Natale/Escursioni raccolte")
            return schede, urls_ok

        # 3) Eventbrite -> JSON-LD (@type: Event)
        if tipo == "eventbrite":
            eventi_ld = []
            for sc in soup.find_all("script", type="application/ld+json"):
                try:
                    dati = json.loads(sc.string or "")
                    estrai_eventi_jsonld(dati, eventi_ld)
                except Exception:
                    continue

            visti_url = set()
            for ev in eventi_ld[:15]:
                titolo = re.sub(r"\s+", " ", str(ev.get("name", ""))).strip()
                ev_url = str(ev.get("url", url)).split("?")[0].strip()
                if not titolo or ev_url in visti_url or REGEX_SCARTO.search(titolo):
                    continue
                visti_url.add(ev_url)
                urls_ok.add(ev_url)

                d_ini = str(ev.get("startDate", ""))[:16]
                d_fin = str(ev.get("endDate", d_ini))[:16]
                loc = ev.get("location") or {}
                if isinstance(loc, list):
                    loc = loc[0] if loc else {}
                luogo_nome = loc.get("name", "") if isinstance(loc, dict) else ""
                addr = loc.get("address", {}) if isinstance(loc, dict) else {}
                localita = addr.get("addressLocality", c_fissa) if isinstance(addr, dict) else c_fissa
                via = addr.get("streetAddress", "") if isinstance(addr, dict) else ""
                desc = re.sub(r"\s+", " ", str(ev.get("description", ""))).strip()[:260]

                prefisso = f"CITTÀ FISSA: {c_fissa} | " if c_fissa else ""
                schede.append(
                    f"[{nome}] {prefisso}URL: {ev_url}\n"
                    f"TITOLO: {titolo}\n"
                    f"DATA INIZIO: {d_ini} | DATA FINE: {d_fin}\n"
                    f"LUOGO: {luogo_nome} ({via}, {localita})\n"
                    f"DESCRIZIONE: {desc}"
                )

            if not schede:
                testo = pulisci_html_testo(soup, max_chars=6500)
                if len(testo) > 150:
                    urls_ok.add(url)
                    prefisso = f"CITTÀ FISSA: {c_fissa} | " if c_fissa else ""
                    schede.append(f"[{nome}] {prefisso}URL: {url}\nELENCO EVENTI:\n{testo}")

            print(f"{nome}: {len(schede)} schede raccolte")
            return schede, urls_ok

        # 4) Virgilio Eventi
        if tipo == "virgilio":
            links = []
            for a in soup.find_all("a", href=True):
                href = urljoin(url, a["href"]).split("#")[0]
                if "/eventi/" in href and href.rstrip("/") != url.rstrip("/") and "virgilio.it" in href:
                    if href not in links:
                        links.append(href)

            for link in links[:7]:
                try:
                    rp = session.get(link, timeout=(4, 6))
                    if rp.status_code != 200:
                        continue
                    rp.encoding = rp.apparent_encoding or "utf-8"
                    sp = BeautifulSoup(rp.text, "html.parser")
                    h1 = sp.find("h1")
                    titolo = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else ""
                    if len(titolo) < 5 or REGEX_SCARTO.search(titolo):
                        continue
                    corpo = pulisci_html_testo(sp, max_chars=1000)
                    if len(corpo) < 40 or REGEX_SCARTO.search(corpo[:300]):
                        continue
                    urls_ok.add(link)
                    schede.append(f"[{nome}] CITTÀ FISSA: {c_fissa} | URL: {link}\nTITOLO: {titolo}\nDETTAGLI: {corpo}")
                except Exception:
                    continue

            if not schede:
                testo = pulisci_html_testo(soup, max_chars=6000)
                if len(testo) > 150:
                    urls_ok.add(url)
                    schede.append(f"[{nome}] CITTÀ FISSA: {c_fissa} | URL: {url}\nELENCO VIRGILIO:\n{testo}")

            print(f"{nome}: {len(schede)} schede raccolte")
            return schede, urls_ok

        # 5) Il Tacco di Bacco
        links = []
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"]).split("#")[0]
            if re.search(r"iltaccodibacco\.it/puglia/eventi/\d+\.html$", href):
                if href not in links:
                    links.append(href)

        for link in links[:10]:
            try:
                rp = session.get(link, timeout=(4, 6))
                if rp.status_code != 200:
                    continue
                rp.encoding = rp.apparent_encoding or "utf-8"
                if "evento si è già concluso" in rp.text.lower() or "fa parte del nostro archivio" in rp.text.lower():
                    continue
                sp = BeautifulSoup(rp.text, "html.parser")
                h1 = sp.find("h1")
                titolo = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else ""
                if len(titolo) < 5 or REGEX_SCARTO.search(titolo):
                    continue
                corpo = pulisci_html_testo(sp, max_chars=1100)
                if len(corpo) < 50:
                    continue
                urls_ok.add(link)
                schede.append(f"[{nome}] URL: {link}\nTITOLO: {titolo}\nDETTAGLI: {corpo}")
            except Exception:
                continue

        print(f"{nome}: {len(schede)} schede spettacolo attive raccolte")
    except Exception as e:
        print(f"Errore {nome}: {str(e)[:80]}")

    return schede, urls_ok


def estrai_con_gemini(api_key, testo_blocco, nome_blocco):
    if not api_key or not testo_blocco.strip():
        return []
    oggi = oggi_iso()
    giorno_sett = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"][datetime.now().weekday()]

    modelli = ["gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.5-flash-lite"]

    prompt = (
        f"Curatore di 'Che Si Fa Cerignola', guida alle uscite serali, concerti, luminarie/eventi natalizi, escursioni e tempo libero entro 50 km da Cerignola.\n"
        f"Oggi è {giorno_sett} {oggi}. Estrai SOLO veri eventi di intrattenimento, Natale ed escursioni con dataFine >= '{oggi}' dai testi qui sotto.\n"
        "REGOLE TASSATIVE:\n"
        "- Includi SOLO: concerti, musica live, DJ set, serate nei locali/pub, spettacoli teatrali, cabaret, commedie, luminarie e accensioni natalizie, mercatini/villaggi di Natale, piste di ghiaccio, sagre, degustazioni, escursioni/trekking/passeggiate guidate.\n"
        "- ESCLUDI ASSOLUTAMENTE: webinar/eventi online, corsi professionali/business, convegni, seminari universitari, incontri religiosi/parrocchiali, fiere sposi, anniversari commerciali, piantumazioni, giornate istituzionali e mostre fotografiche.\n"
        "- Estrai SOLO eventi che si svolgono a Cerignola o nei comuni vicini entro 50 km (Barletta, Trani, Andria, Bisceglie, Canosa, Margherita di Savoia, Trinitapoli, San Ferdinando, Orta Nova, Stornara, Stornarella, Foggia, Manfredonia, Lucera, Lavello, Melfi, Venosa, Rionero in Vulture). Scarta Bari, Lecce, Taranto, San Giovanni Rotondo, Monte Sant'Angelo, San Severo.\n"
        "- Se il blocco indica 'CITTÀ FISSA: <Comune>', assegna quel comune agli eventi di quel blocco.\n"
        "- Usa 'Famiglie & Bambini' per luminarie/mercatini/eventi di Natale e 'Natura & Escursioni' per trekking/passeggiate/visite guidate. Non usare mai 'Altro'.\n"
        "- Copia in 'fonteUrl' l'URL esatto del blocco.\n\n"
        f"{testo_blocco}"
    )

    for mod in modelli:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
                "responseSchema": SCHEMA_EVENTI
            }
        }
        try:
            r = requests.post(url, json=payload, timeout=(5, 35))
            if r.status_code in (404, 429, 503):
                print(f"[{nome_blocco}] HTTP {r.status_code} su {mod}, provo successivo...")
                continue
            if r.status_code != 200:
                print(f"[{nome_blocco}] HTTP {r.status_code} su {mod}: {r.text[:110]}")
                continue
            parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            raw = "\n".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            dati = json.loads(raw)
            if isinstance(dati, list):
                print(f"[{nome_blocco}] Estratti {len(dati)} eventi da {mod}.")
                return dati
        except Exception as e:
            print(f"[{nome_blocco}] Errore {mod}: {str(e)[:80]}")
            continue
    return []


def sono_duplicati(a, b):
    if a.get("citta", "").lower() != b.get("citta", "").lower():
        return False
    if a.get("dataInizio") != b.get("dataInizio"):
        return False
    t1 = re.sub(r"[^a-z0-9\s]", "", a.get("titolo", "").lower())
    t2 = re.sub(r"[^a-z0-9\s]", "", b.get("titolo", "").lower())
    return SequenceMatcher(None, t1, t2).ratio() >= 0.70


# ==============================================================================
# ESECUZIONE PRINCIPALE
# ==============================================================================
t_start = time.time()
api_key = os.environ.get("GEMINI_API_KEY", "").strip()
urls_validi = set()

session = requests.Session()
session.headers.update(HEADERS)

blocchi = {"Cerignola": [], "Capitanata_50km": [], "BAT_50km": [], "Regionali_50km": []}
for fonte in FONTI_SPETTACOLO:
    sc, u_ok = raccogli_fonte(session, fonte)
    urls_validi.update(u_ok)
    blocchi[fonte["blocco"]].extend(sc)

consolidati = []
for idx, (nome_b, lista_sc) in enumerate(blocchi.items()):
    if not lista_sc:
        continue
    if idx > 0:
        time.sleep(1)
    testo_unito = "\n\n===\n\n".join(lista_sc)[:19000]
    print(f"[{nome_b}] Analisi {len(testo_unito)} char con Gemini...")
    estratti = estrai_con_gemini(api_key, testo_unito, nome_b)
    validati_b = 0
    for raw_ev in estratti:
        ev = pulisci_evento(raw_ev, urls_validi)
        ok, motivo = verifica_evento(ev)
        if ok:
            if not any(sono_duplicati(x, ev) for x in consolidati):
                consolidati.append(ev)
                validati_b += 1
        else:
            print(f"[{nome_b}] Scartato ({motivo}): {ev.get('citta') or '?'} - {ev.get('titolo')}")
    print(f"[{nome_b}] Validati puliti: {validati_b}")

lista_finale = sorted(
    consolidati,
    key=lambda x: (priorita_km(x.get("citta")), x.get("dataInizio", "9999-12-31"), x.get("titolo", "").lower())
)

if len(lista_finale) > 0:
    with open("eventi.json", "w", encoding="utf-8") as f:
        json.dump(lista_finale, f, ensure_ascii=False, indent=2)

    report = {
        "aggiornatoAl": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "totaleContenuti": len(lista_finale),
        "nuoviAggiunti": len(lista_finale),
        "topComuni": dict(Counter(e["citta"] for e in lista_finale).most_common(15))
    }
    with open("report_copertura.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

print(f"Fine: {len(lista_finale)} eventi reali (in {int(time.time() - t_start)}s)")
