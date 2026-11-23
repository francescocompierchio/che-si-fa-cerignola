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

FEED_RSS_COERENTI = [
    {
        "nome": "RSS Luminarie & Natale BAT-Foggia",
        "query": 'natale luminarie OR mercatini OR "babbo natale" OR "pista di ghiaccio" Cerignola OR Barletta OR Trani OR Andria OR Bisceglie OR Foggia when:14d'
    },
    {
        "nome": "RSS Eventi Natalizi Puglia Nord",
        "query": '"eventi natalizi" OR "programma di natale" OR "accensione" Cerignola OR Canosa OR "Margherita di Savoia" OR Manfredonia OR Lucera OR Melfi OR Venosa when:14d'
    },
    {
        "nome": "RSS Sagre & Feste 50km",
        "query": 'sagra OR "festa in piazza" OR "street food" OR degustazione Cerignola OR Barletta OR Trani OR Andria OR Foggia OR Lucera OR Troia OR Melfi when:14d'
    },
    {
        "nome": "RSS Musica Live & Serate 50km",
        "query": '"musica live" OR "dj set" OR concerto OR cabaret Cerignola OR Barletta OR Trani OR Andria OR Bisceglie OR Foggia -teatro -sinfonica -pianistico when:14d'
    },
    {
        "nome": "RSS Escursioni & Trekking 50km",
        "query": 'escursione OR trekking OR passeggiata OR "visita guidata" "Margherita di Savoia" OR Monticchio OR "Castel del Monte" OR "Alta Murgia" OR Incoronata OR Canosa when:14d'
    }
]

FONTI_PORTALI = [
    {
        "nome": "Il Tacco di Bacco BAT",
        "url": "https://iltaccodibacco.it/barletta/"
    },
    {
        "nome": "Il Tacco di Bacco Foggia",
        "url": "https://iltaccodibacco.it/foggia/"
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


def calendario_prossimi_giorni(giorni=21):
    nomi = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
    oggi = datetime.now()
    righe = []
    for i in range(giorni):
        d = oggi + timedelta(days=i)
        tag = " (OGGI)" if i == 0 else (" (DOMANI)" if i == 1 else "")
        righe.append(f"{nomi[d.weekday()]} {d.strftime('%Y-%m-%d')}{tag}")
    return ", ".join(righe)


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


def pulisci_html_testo(sp, max_chars=700):
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
        for item in root.findall(".//item")[:12]:
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
                f"FONTE: {nome} | PUBBLICATO: {pub_str} | URL: {link}\n"
                f"TITOLO: {titolo}\n"
                f"TESTO: {desc[:220]}"
            )
        print(f"{nome}: {len(schede)} notizie coerenti raccolte")
    except Exception as e:
        print(f"Errore {nome}: {str(e)[:80]}")

    return schede


def raccogli_tacco(session, fonte):
    schede = []
    url = fonte["url"]
    nome = fonte["nome"]

    try:
        r = session.get(url, timeout=(4, 8))
        if r.status_code != 200:
            print(f"{nome}: HTTP {r.status_code}")
            return []
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

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
                corpo = pulisci_html_testo(sp, max_chars=650)
                if len(corpo) < 50 or REGEX_SCARTO.search(corpo[:300]):
                    continue
                schede.append(f"FONTE: {nome} | URL: {link}\nTITOLO: {titolo}\nDETTAGLI: {corpo}")
            except Exception:
                continue

        print(f"{nome}: {len(schede)} schede live/serate")
    except Exception as e:
        print(f"Errore {nome}: {str(e)[:80]}")

    return schede


def estrai_unico_blocco_gemini(api_key, testo_unico):
    if not api_key or not testo_unico.strip():
        return []
    oggi = oggi_iso()
    limite_max = (datetime.now() + timedelta(days=GIORNI_ANTICIPO_MAX)).strftime("%Y-%m-%d")
    cal_ref = calendario_prossimi_giorni(21)

    modelli = ["gemini-3.5-flash", "gemini-3.5-flash-lite"]

    prompt = (
        f"Selezionatore di 'Che Si Fa Cerignola', guida agli eventi di tempo libero, Natale, serate ed escursioni entro 50 km da Cerignola.\n"
        f"CALENDARIO DI RIFERIMENTO: {cal_ref}.\n"
        f"Estrai TUTTI gli eventi reali presenti nelle schede qui sotto con dataFine >= '{oggi}' e dataInizio <= '{limite_max}'.\n"
        "COSA INCLUDERE:\n"
        "1. Natale & Luminarie: luminarie, accensione alberi, mercatini di Natale, villaggi di Babbo Natale, piste di ghiaccio, presepi viventi.\n"
        "2. Musica Live & Serate: concerti, band dal vivo nei pub/piazze, DJ set, serate club, cabaret.\n"
        "3. Sagre & Food: sagre gastronomiche, street food, feste in piazza, degustazioni.\n"
        "4. Escursioni & Passeggiate: trekking, passeggiate guidate, visite naturalistiche (Saline Margherita di Savoia, Monticchio, Castel del Monte/Alta Murgia, Bosco Incoronata, borghi).\n"
        "COSA SCARTARE:\n"
        "- Teatro di prosa, recital pianistici, concerti sinfonici/classici, convegni, seminari, parrocchie, sport, mostre fotografiche, presentazione libri e articoli di eventi già conclusi.\n"
        "REGOLE DATE E COMUNI:\n"
        "- Comuni ammessi (entro 50 km): Cerignola, Stornara, Stornarella, Orta Nova, San Ferdinando di Puglia, Trinitapoli, Canosa di Puglia, Ordona, Carapelle, Margherita di Savoia, Lavello, Ascoli Satriano, Zapponeta, Castelluccio dei Sauri, Barletta, Candela, Minervino Murge, Foggia, Melfi, Venosa, Deliceto, Rapolla, Andria, Barile, Palazzo San Gervasio, Rocchetta Sant'Antonio, Manfredonia, Rionero in Vulture, Trani, Bovino, Spinazzola, Troia, Lucera, Bisceglie, Monticchio.\n"
        "- Se una notizia parla di 'questo sabato', 'domenica', 'questo weekend' o 'venerdì', usa la data esatta dal CALENDARIO DI RIFERIMENTO.\n"
        "- Se una notizia annuncia luminarie, pista di ghiaccio o programma natalizio senza una data numerica singola, imposta dataInizio='{oggi}' (o PUBBLICATO se >= '{oggi}') e dataFine='{(datetime.now() + timedelta(days=25)).strftime('%Y-%m-%d')}'.\n"
        "- Categorie ammesse: 'Musica & Concerti', 'Locali & Serate', 'Sagre & Food', 'Famiglie & Bambini', 'Natura & Escursioni', 'Attività diurne'.\n"
        "- Copia in 'fonteUrl' l'URL esatto della scheda.\n\n"
        f"{testo_unico}"
    )

    for tentativo in range(2):
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
                r = requests.post(url, json=payload, timeout=(8, 75))
                if r.status_code in (404, 429, 503):
                    print(f"[Gemini] HTTP {r.status_code} su {mod} (round {tentativo+1}), attendo 12s...")
                    time.sleep(12)
                    continue
                if r.status_code != 200:
                    print(f"[Gemini] HTTP {r.status_code} su {mod}: {r.text[:120]}")
                    continue
                parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
                raw = "\n".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
                dati = json.loads(raw)
                if isinstance(dati, list) and len(dati) > 0:
                    print(f"[Gemini] Estratti {len(dati)} eventi da {mod}.")
                    return dati
                print(f"[Gemini] 0 eventi da {mod}, provo alternativo...")
            except Exception as e:
                print(f"[Gemini] Errore {mod}: {str(e)[:80]}")
                time.sleep(8)
                continue
    return []


def sono_duplicati(a, b):
    if a.get("citta", "").lower() != b.get("citta", "").lower():
        return False
    t1 = re.sub(r"[^a-z0-9\s]", "", a.get("titolo", "").lower())
    t2 = re.sub(r"[^a-z0-9\s]", "", b.get("titolo", "").lower())
    return SequenceMatcher(None, t1, t2).ratio() >= 0.65


# ==============================================================================
# ESECUZIONE PRINCIPALE (CHIAMATA UNICA COMPATTO-VELOCE)
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

tutte_schede = []
for feed in FEED_RSS_COERENTI:
    tutte_schede.extend(raccogli_rss(session, feed))

for fonte in FONTI_PORTALI:
    tutte_schede.extend(raccogli_tacco(session, fonte))

testo_unico = "\n---\n".join(tutte_schede)[:11500]
print(f"[Batch Unico] Invio {len(tutte_schede)} schede ({len(testo_unico)} char) a Gemini...")

estratti = estrai_unico_blocco_gemini(api_key, testo_unico)
validati = 0
for raw_ev in estratti:
    ev = pulisci_evento(raw_ev)
    ok, motivo = verifica_evento(ev)
    if ok:
        if not any(sono_duplicati(x, ev) for x in consolidati):
            consolidati.append(ev)
            validati += 1
    else:
        print(f"[Scarto] ({motivo}): {ev.get('citta') or '?'} - {ev.get('titolo')}")

print(f"[Batch Unico] Validati coerenti: {validati}")

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
