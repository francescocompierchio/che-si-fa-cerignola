import os
import re
import json
import time
import requests
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urljoin, quote_plus
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

GIORNI_ANTICIPO_MAX = 40

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9"
}

DOMINI_AUTO = (
    "news.google.com", "iltaccodibacco.it", "viaggiareinpuglia.it",
    "pugliaevents.it", "eventiesagre.it", "eventbrite.it",
    "teatromercadantecerignola.it", "teatrogiordano.it",
    "palazzodelleartibeltrani.it", "politeamaitalia.com",
    "happyticket.com", "pugliaculture.it", "ciaotickets.com",
    "virgilio.it", "cerignolaviva.it", "barlettaviva.it", "traniviva.it"
)

# Query RSS semplici e dirette (evitano il taglio di Google News sulle query troppo nidificate)
FEED_RSS_COERENTI = [
    {
        "nome": "RSS Luminarie & Natale BAT-Foggia",
        "query": 'natale luminarie OR mercatini OR "babbo natale" OR "pista di ghiaccio" Cerignola OR Barletta OR Trani OR Andria OR Bisceglie OR Foggia when:14d',
        "blocco": "Natale_Luminarie"
    },
    {
        "nome": "RSS Eventi Natalizi Puglia Nord",
        "query": '"eventi natalizi" OR "programma di natale" OR "accensione" Cerignola OR Canosa OR "Margherita di Savoia" OR Manfredonia OR Lucera OR Melfi OR Venosa when:14d',
        "blocco": "Natale_Luminarie"
    },
    {
        "nome": "RSS Sagre & Feste 50km",
        "query": 'sagra OR "festa in piazza" OR "street food" OR degustazione Cerignola OR Barletta OR Trani OR Andria OR Foggia OR Lucera OR Troia OR Melfi when:14d',
        "blocco": "Sagre_Feste"
    },
    {
        "nome": "RSS Musica Live & Serate 50km",
        "query": '"musica live" OR "dj set" OR concerto OR cabaret Cerignola OR Barletta OR Trani OR Andria OR Bisceglie OR Foggia -teatro -sinfonica -pianistico when:14d',
        "blocco": "Musica_Serate"
    },
    {
        "nome": "RSS Escursioni & Trekking 50km",
        "query": 'escursione OR trekking OR passeggiata OR "visita guidata" "Margherita di Savoia" OR Monticchio OR "Castel del Monte" OR "Alta Murgia" OR Incoronata OR Canosa when:14d',
        "blocco": "Outdoor_Gite"
    }
]

FONTI_PORTALI = [
    {
        "nome": "Il Tacco di Bacco BAT",
        "url": "https://iltaccodibacco.it/barletta/",
        "tipo": "tacco_indice",
        "blocco": "Musica_Serate"
    },
    {
        "nome": "Il Tacco di Bacco Foggia",
        "url": "https://iltaccodibacco.it/foggia/",
        "tipo": "tacco_indice",
        "blocco": "Musica_Serate"
    },
    {
        "nome": "Viaggiare in Puglia Eventi",
        "url": "https://www.viaggiareinpuglia.it/it/eventi",
        "tipo": "portale_regionale",
        "blocco": "Outdoor_Gite"
    },
    {
        "nome": "Eventi e Sagre Puglia",
        "url": "https://www.eventiesagre.it/Eventi_Sagre/Puglia.html",
        "tipo": "portale_regionale",
        "blocco": "Sagre_Feste"
    }
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

REGEX_COMUNI_50KM = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in sorted(COMUNI_50KM.keys(), key=len, reverse=True)) + r")\b",
    re.I
)

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

MAPPA_CAT = {
    "musica": "Musica & Concerti",
    "concert": "Musica & Concerti",
    "live": "Musica & Concerti",
    "tribute": "Musica & Concerti",
    "locali": "Locali & Serate",
    "serat": "Locali & Serate",
    "dj": "Locali & Serate",
    "club": "Locali & Serate",
    "disco": "Locali & Serate",
    "cabaret": "Locali & Serate",
    "sagr": "Sagre & Food",
    "food": "Sagre & Food",
    "degustazion": "Sagre & Food",
    "enogastronom": "Sagre & Food",
    "famigli": "Famiglie & Bambini",
    "bambin": "Famiglie & Bambini",
    "natal": "Famiglie & Bambini",
    "luminar": "Famiglie & Bambini",
    "mercatin": "Famiglie & Bambini",
    "presep": "Famiglie & Bambini",
    "ghiacci": "Famiglie & Bambini",
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
    "grande successo per", "si è concluso", "si è svolta", "si è svolto",
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


def pulisci_evento(ev):
    citta = risolvi_comune_50km(ev)
    cat = normalizza_cat(ev.get("categoria"))
    url = (ev.get("fonteUrl") or "").strip()
    if not url.startswith("http"):
        url = "https://iltaccodibacco.it/barletta/"

    d_ini = (ev.get("dataInizio") or "").strip()[:10]
    d_fin = (ev.get("dataFine") or d_ini).strip()[:10]
    luogo = re.sub(r"\s+", " ", (ev.get("luogo") or "")).strip()
    if not luogo or luogo.lower() in ("da definire", "da verificare", "n/d", citta.lower()):
        luogo = f"Centro / Piazze, {citta}"

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
        "costo": (ev.get("costo") or "Ingresso libero / Da verificare").strip(),
        "descrizione": re.sub(r"\s+", " ", (ev.get("descrizione") or "")).strip()[:220],
        "fonteUrl": url
    }


def verifica_evento(ev):
    if not ev.get("citta"):
        return False, "fuori_raggio_50km"
    if not ev.get("categoria") or ev.get("categoria") not in CATEGORIE_AMMESSE:
        return False, "categoria_non_svago"

    oggi = oggi_iso()
    limite_max = (datetime.now() + timedelta(days=GIORNI_ANTICIPO_MAX)).strftime("%Y-%m-%d")
    d1, d2 = ev.get("dataInizio", ""), ev.get("dataFine", "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d1) or not re.match(r"^\d{4}-\d{2}-\d{2}$", d2):
        return False, "formato_data"
    if d2 < oggi:
        return False, f"passato({d2})"
    if d1 > d2:
        return False, f"intervallo({d1}->{d2})"
    if d1 > limite_max:
        return False, f"oltre_{GIORNI_ANTICIPO_MAX}gg({d1})"

    titolo = ev.get("titolo", "")
    if len(titolo) < 5:
        return False, "titolo_corto"

    testo = f"{titolo} {ev.get('descrizione', '')} {ev.get('luogo', '')}"
    m = REGEX_SCARTO.search(testo)
    if m:
        return False, f"scarto({m.group(0)})"

    return True, "ok"


def pulisci_html_testo(sp, max_chars=5500):
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


def raccogli_rss(session, feed_cfg):
    schede = []
    nome = feed_cfg["nome"]
    rss_url = f"https://news.google.com/rss/search?q={quote_plus(feed_cfg['query'])}&hl=it&gl=IT&ceid=IT:it"
    soglia_pub = datetime.now(timezone.utc) - timedelta(days=15)

    try:
        r = session.get(rss_url, timeout=(5, 10))
        if r.status_code != 200:
            print(f"{nome}: HTTP {r.status_code}")
            return []

        root = ET.fromstring(r.content)
        for item in root.findall(".//item")[:14]:
            titolo_raw = (item.findtext("title") or "").strip()
            titolo = re.sub(r"\s+-\s+[^-]+$", "", titolo_raw).strip()
            link = (item.findtext("link") or "").strip()
            pub_raw = (item.findtext("pubDate") or "").strip()
            desc_html = item.findtext("description") or ""
            desc = re.sub(r"\s+", " ", BeautifulSoup(desc_html, "html.parser").get_text(" ", strip=True)).strip()

            testo_check = f"{titolo} {desc}"
            if len(titolo) < 8 or REGEX_SCARTO.search(testo_check):
                continue
            if not REGEX_COMUNI_50KM.search(testo_check):
                continue

            pub_str = ""
            if pub_raw:
                try:
                    dt_pub = parsedate_to_datetime(pub_raw)
                    if dt_pub < soglia_pub:
                        continue
                    pub_str = dt_pub.strftime("%Y-%m-%d")
                except Exception:
                    pass

            schede.append(
                f"[{nome}] PUBBLICATO IL: {pub_str} | URL: {link}\n"
                f"TITOLO: {titolo}\n"
                f"ESTRATTO: {desc[:280]}"
            )
        print(f"{nome}: {len(schede)} notizie coerenti raccolte")
    except Exception as e:
        print(f"Errore {nome}: {str(e)[:80]}")

    return schede


def raccogli_portale(session, fonte):
    schede = []
    url = fonte["url"]
    nome = fonte["nome"]
    tipo = fonte["tipo"]

    try:
        r = session.get(url, timeout=(4, 8))
        if r.status_code != 200:
            print(f"{nome}: HTTP {r.status_code}")
            return []
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        if tipo == "portale_regionale":
            testo = pulisci_html_testo(soup, max_chars=7500)
            righe_50km = [
                seg.strip() for seg in testo.split(" | ")
                if REGEX_COMUNI_50KM.search(seg) and not REGEX_SCARTO.search(seg)
            ]
            if righe_50km:
                blocco_txt = " | ".join(righe_50km)[:4000]
                schede.append(f"[{nome}] URL: {url}\nELENCO FILTRATO 50KM:\n{blocco_txt}")
            print(f"{nome}: {len(righe_50km)} righe entro 50km")
            return schede

        links = []
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"]).split("#")[0]
            if re.search(r"iltaccodibacco\.it/puglia/eventi/\d+\.html$", href):
                if href not in links:
                    links.append(href)

        for link in links[:8]:
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
                corpo = pulisci_html_testo(sp, max_chars=750)
                if len(corpo) < 50 or REGEX_SCARTO.search(corpo[:300]):
                    continue
                schede.append(f"[{nome}] URL: {link}\nTITOLO: {titolo}\nDETTAGLI: {corpo}")
            except Exception:
                continue

        print(f"{nome}: {len(schede)} schede live/serate")
    except Exception as e:
        print(f"Errore {nome}: {str(e)[:80]}")

    return schede


def estrai_con_gemini(api_key, testo_blocco, nome_blocco):
    if not api_key or not testo_blocco.strip():
        return []
    oggi = oggi_iso()
    limite_max = (datetime.now() + timedelta(days=GIORNI_ANTICIPO_MAX)).strftime("%Y-%m-%d")
    giorno_sett = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"][datetime.now().weekday()]

    # Ordine ottimizzato: gemini-3.5-flash risponde in pochi secondi senza timeout
    modelli = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]

    prompt = (
        f"Curatore di 'Che Si Fa Cerignola', guida alle iniziative reali di tempo libero, Natale ed escursioni a Cerignola e nei comuni entro 50 km.\n"
        f"Oggi è {giorno_sett} {oggi}. Estrai TUTTI gli eventi coerenti presenti nei testi qui sotto con dataFine >= '{oggi}' e dataInizio <= '{limite_max}'.\n"
        "COSA INCLUDERE:\n"
        "1. Natale & Luminarie: accensione luminarie/alberi, mercatini di Natale, villaggi di Babbo Natale, piste di ghiaccio, presepi viventi.\n"
        "2. Musica Live & Serate: concerti, band dal vivo nei pub/piazze, DJ set, serate club, cabaret/comicità.\n"
        "3. Sagre & Food: sagre gastronomiche, street food, feste in piazza, degustazioni.\n"
        "4. Escursioni & Passeggiate: trekking, passeggiate guidate, visite naturalistiche (Saline Margherita di Savoia, Monticchio, Alta Murgia/Castel del Monte, Bosco Incoronata, borghi).\n"
        "COSA SCARTARE:\n"
        "- Spettacoli teatrali di prosa, recital pianistici, concerti sinfonici/classici, convegni, seminari universitari, incontri parrocchiali/processioni, fiere sposi, anniversari commerciali, mostre fotografiche, presentazione libri, sport, bandi/delibere senza evento e resoconti di eventi già terminati ('si è concluso', 'grande successo per').\n"
        "REGOLE SU DATE E COMUNI:\n"
        "- Comuni ammessi (entro 50 km): Cerignola, Stornara, Stornarella, Orta Nova, San Ferdinando di Puglia, Trinitapoli, Canosa di Puglia, Ordona, Carapelle, Margherita di Savoia, Lavello, Ascoli Satriano, Zapponeta, Castelluccio dei Sauri, Barletta, Candela, Minervino Murge, Foggia, Melfi, Venosa, Deliceto, Rapolla, Andria, Barile, Palazzo San Gervasio, Rocchetta Sant'Antonio, Manfredonia, Rionero in Vulture, Trani, Bovino, Spinazzola, Troia, Lucera, Bisceglie, Monticchio.\n"
        "- Se una notizia annuncia un programma natalizio, luminarie, pista di ghiaccio o iniziativa del weekend senza indicare la data numerica esatta nel titolo, usa '{oggi}' (o la data di PUBBLICATO IL se >= '{oggi}') come dataInizio e il weekend/fine periodo natalizio (entro '{limite_max}') come dataFine, scrivendo in dataTesto il periodo (es. 'Periodo natalizio · Vedi programma').\n"
        "- Usa SOLO categorie tra: 'Musica & Concerti', 'Locali & Serate', 'Sagre & Food', 'Famiglie & Bambini', 'Natura & Escursioni', 'Attività diurne'.\n"
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
            r = requests.post(url, json=payload, timeout=(6, 55))
            if r.status_code in (404, 429, 503):
                print(f"[{nome_blocco}] HTTP {r.status_code} su {mod}, attendo e provo successivo...")
                time.sleep(4)
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
    t1 = re.sub(r"[^a-z0-9\s]", "", a.get("titolo", "").lower())
    t2 = re.sub(r"[^a-z0-9\s]", "", b.get("titolo", "").lower())
    return SequenceMatcher(None, t1, t2).ratio() >= 0.65


# ==============================================================================
# ESECUZIONE PRINCIPALE
# ==============================================================================
t_start = time.time()
api_key = os.environ.get("GEMINI_API_KEY", "").strip()
oggi = oggi_iso()

session = requests.Session()
session.headers.update(HEADERS)

consolidati = []

# Mantiene eventuali inserimenti manuali già presenti in eventi.json (non provenienti dai feed automatici)
try:
    with open("eventi.json", "r", encoding="utf-8") as f:
        esistenti = json.load(f)
    if isinstance(esistenti, list):
        for raw_old in esistenti:
            if raw_old.get("tipoContenuto") != "evento":
                continue
            url_old = (raw_old.get("fonteUrl") or "").lower()
            if any(d in url_old for d in DOMINI_AUTO):
                continue
            d_fin = (raw_old.get("dataFine") or raw_old.get("dataInizio") or "").strip()[:10]
            if re.match(r"^\d{4}-\d{2}-\d{2}$", d_fin) and d_fin >= oggi and len((raw_old.get("titolo") or "").strip()) >= 3:
                consolidati.append(raw_old)
except Exception:
    pass

blocchi = {"Natale_Luminarie": [], "Sagre_Feste": [], "Musica_Serate": [], "Outdoor_Gite": []}

for feed in FEED_RSS_COERENTI:
    sc = raccogli_rss(session, feed)
    blocchi[feed["blocco"]].extend(sc)

for fonte in FONTI_PORTALI:
    sc = raccogli_portale(session, fonte)
    blocchi[fonte["blocco"]].extend(sc)

for idx, (nome_b, lista_sc) in enumerate(blocchi.items()):
    if not lista_sc:
        continue
    if idx > 0:
        time.sleep(3)
    testo_unito = "\n\n===\n\n".join(lista_sc)[:7000]
    print(f"[{nome_b}] Analisi {len(testo_unito)} char con Gemini...")
    estratti = estrai_con_gemini(api_key, testo_unito, nome_b)
    validati_b = 0
    for raw_ev in estratti:
        ev = pulisci_evento(raw_ev)
        ok, motivo = verifica_evento(ev)
        if ok:
            if not any(sono_duplicati(x, ev) for x in consolidati):
                consolidati.append(ev)
                validati_b += 1
        else:
            print(f"[{nome_b}] Scartato ({motivo}): {ev.get('citta') or '?'} - {ev.get('titolo')}")
    print(f"[{nome_b}] Validati coerenti: {validati_b}")

lista_finale = sorted(
    consolidati,
    key=lambda x: (x.get("dataInizio", "9999-12-31"), priorita_km(x.get("citta")), x.get("titolo", "").lower())
)

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

print(f"Fine: {len(lista_finale)} eventi reali trovati (in {int(time.time() - t_start)}s)")
