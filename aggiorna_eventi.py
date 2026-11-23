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
    {"url": "https://www.cerignolaviva.it/eventi/", "citta": "Cerignola", "area": "Area_Cerignola_25km"},
    {"url": "https://www.foggiatoday.it/eventi/", "citta": "Foggia", "area": "Area_BAT_Foggia_Vulture_50km"},
    {"url": "https://www.foggiatoday.it/eventi/weekend/", "citta": "Foggia", "area": "Area_BAT_Foggia_Vulture_50km"},
    {"url": "https://www.barlettaviva.it/eventi/", "citta": "Barletta", "area": "Area_BAT_Foggia_Vulture_50km"},
    {"url": "https://www.traniviva.it/eventi/", "citta": "Trani", "area": "Area_BAT_Foggia_Vulture_50km"},
    {"url": "https://www.bisceglieviva.it/eventi/", "citta": "Bisceglie", "area": "Area_BAT_Foggia_Vulture_50km"},
    {"url": "https://www.andriaviva.it/eventi/", "citta": "Andria", "area": "Area_BAT_Foggia_Vulture_50km"},
]

FALLBACK_URL = {
    "Cerignola": "https://www.cerignolaviva.it/eventi/",
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

# Blocca popup, pagine archivio, notizie istituzionali/politiche, cronaca, religione e resoconti al passato
LISTA_VIETATE = [
    "adblocker", "ci stai leggendo", "disattiva", "cookie", "abbonati", "newsletter",
    "archivio", "agenda di", "eventi in agenda", "tutti gli eventi", "sede nell'articolo",
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

REGEX_VIETATE = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in LISTA_VIETATE) + r")\b", re.I)

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
    "accadia": "Accadia", "lucera": "Lucera", "bisceglie": "Bisceglie", "molfetta": "Molfetta",
    "roseto valfortore": "Roseto Valfortore", "san giovanni rotondo": "San Giovanni Rotondo"
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


def pulisci_evento(ev, citta_def, urls_ok):
    citta = normalizza_citta(ev, citta_def)
    url = (ev.get("fonteUrl") or "").strip()
    parsed = urlparse(url)
    dom = parsed.netloc.lower()
    if url not in urls_ok and (not dom or "google.com" in dom or "example.com" in dom):
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
    max_d = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
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
    return True


def raccogli_portale(url_indice, citta_def):
    estratti = []
    urls_ok = set()
    try:
        r = requests.get(url_indice, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return "", set()
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

        for link in links[:12]:
            try:
                rp = requests.get(link, headers=HEADERS, timeout=10)
                if rp.status_code != 200:
                    continue
                rp.encoding = rp.apparent_encoding or "utf-8"
                sp = BeautifulSoup(rp.text, "html.parser")
                for tag in sp(["script", "style", "nav", "footer", "aside", "form"]):
                    tag.decompose()

                box = sp.find("article") or sp.find("main") or sp
                # Prende esclusivamente H1 per evitare popup H2 (es. adblocker)
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

                corpo = " | ".join(righe[:10])[:850]
                if len(corpo) < 40 or REGEX_VIETATE.search(f"{titolo} {corpo}"):
                    continue

                urls_ok.add(link)
                estratti.append(f"[{citta_def}] URL: {link}\nTITOLO: {titolo}\nTESTO: {corpo}")
            except Exception:
                continue

        print(f"Fonte {citta_def}: {len(estratti)} schede pulite")
    except Exception as e:
        print(f"Errore fonte {citta_def}:", e)

    return "\n\n---\n\n".join(estratti)[:10000], urls_ok


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
                if "3-flash" in l or "3.1-flash" in l:
                    p -= 30
                elif "flash-lite" in l:
                    p -= 20
                elif "pro" in l:
                    p -= 10
                return (p, l)

            ordinati = sorted(tutti, key=priorita)
            if ordinati:
                print("Modelli Gemini attivi:", ", ".join(ordinati[:5]))
                return ordinati[:4]
    except Exception as e:
        print("Errore verifica modelli:", e)
    return ["gemini-3-flash-preview", "gemini-3.1-flash-lite-preview", "gemini-2.5-pro"]


def cerca_ed_estrai_gemini(api_key, modelli, testo_locale, area_nome, comuni_target):
    if not api_key:
        return []
    oggi = oggi_iso()
    giorno_sett = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"][datetime.now().weekday()]

    prompt = (
        f"Sei il curatore di 'Che Si Fa Cerignola', app per uscire nel tempo libero. Oggi è {giorno_sett} {oggi}.\n"
        f"OBIETTIVO: Trova e seleziona 8-15 VERI eventi ricreativi di svago in programma tra oggi {oggi} e i prossimi 35 giorni nei comuni: {comuni_target}.\n"
        "COSA INCLUDERE (solo eventi divertenti/ricreativi per chi vuole uscire):\n"
        "- Concerti, musica live in pub/club, DJ set, serate nei locali.\n"
        "- Sagre, degustazioni, street food, mercatini di Natale, villaggi natalizi, luminarie.\n"
        "- Spettacoli teatrali, cabaret, commedie, cinema/rassegne.\n"
        "- Laboratori/spettacoli per bambini e famiglie, escursioni/trekking guidati futuri.\n"
        "COSA SCARTARE ASSOLUTAMENTE:\n"
        "- Cronaca, politica, progetti comunali, convegni/dibattiti/seminari, presentazioni di libri, cerimonie religiose/messe, beneficenza.\n"
        "- Articoli al passato su eventi già conclusi.\n"
        "- NON confondere la data di pubblicazione dell'articolo con la data dell'evento! Inserisci SOLO eventi di cui conosci data reale (dataFine >= oggi) e nome preciso del locale/piazza/teatro in 'luogo'.\n"
        "Usa sia la ricerca Google sia gli estratti locali validi qui sotto.\n"
        "Restituisci SOLO un array JSON valido (senza markdown) con oggetti aventi chiavi: "
        "tipoContenuto ('evento'), citta, categoria (tra 'Locali & Serate', 'Attività serali', 'Musica & Concerti', 'Sagre & Food', 'Famiglie & Bambini', 'Natura & Escursioni', 'Attività diurne', 'Altro'), "
        "titolo, dataTesto, dataInizio (YYYY-MM-DD), dataFine (YYYY-MM-DD), luogo, indirizzoMappa, costo, descrizione, fonteUrl.\n\n"
        f"ESTRATTI LOCALI:\n{testo_locale[:9000]}"
    )

    for mod in modelli:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
        # Prima prova con Google Search attivo (senza responseMimeType JSON che va in conflitto con tools)
        tentativi_payload = [
            {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "tools": [{"google_search": {}}],
                "generationConfig": {"temperature": 0.15}
            },
            {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
            }
        ]
        for idx_p, payload in enumerate(tentativi_payload):
            try:
                r = requests.post(url, json=payload, timeout=65)
                if r.status_code == 429:
                    print(f"[{area_nome}] Quota 429 su {mod}, salto.")
                    break
                if r.status_code != 200:
                    if idx_p == 0:
                        continue
                    print(f"[{area_nome}] HTTP {r.status_code} su {mod}: {r.text[:130]}")
                    break

                data_resp = r.json()
                cands = data_resp.get("candidates", [])
                if not cands:
                    continue

                # Estrae eventuali URL reali verificati dal grounding di Google Search
                urls_grounding = set()
                meta = cands[0].get("groundingMetadata", {})
                for ch in meta.get("groundingChunks", []):
                    u = ch.get("web", {}).get("uri", "")
                    if u.startswith("http") and "vertexaisearch" not in u:
                        urls_grounding.add(u)

                parts = cands[0].get("content", {}).get("parts", [])
                raw = "\n".join(p.get("text", "") for p in parts).strip()
                raw = re.sub(r"^`{3}json\s*|`{3}$", "", raw, flags=re.I).strip()
                m = re.search(r"\[.*\]", raw, flags=re.DOTALL)
                dati = json.loads(m.group(0) if m else raw)
                if isinstance(dati, list) and dati:
                    modo = "con Google Search" if idx_p == 0 else "da fonti locali"
                    print(f"[{area_nome}] Trovati {len(dati)} eventi ({modo}) con {mod}.")
                    return dati, urls_grounding
            except Exception as e:
                print(f"[{area_nome}] Errore {mod}:", e)
                continue
    return [], set()


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
modelli_attivi = scopri_modelli_gemini(api_key) if api_key else []
urls_validi = set()

# Ripulisce eventi.json esistente eliminando tutta la spazzatura passata
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

blocchi_testo = {"Area_Cerignola_25km": [], "Area_BAT_Foggia_Vulture_50km": []}
for fonte in FONTI_LOCALI:
    txt, u_ok = raccogli_portale(fonte["url"], fonte["citta"])
    urls_validi.update(u_ok)
    if txt:
        blocchi_testo[fonte["area"]].append(txt)

aree_config = [
    (
        "Area_Cerignola_25km",
        "Cerignola, Canosa di Puglia, San Ferdinando di Puglia, Trinitapoli, Margherita di Savoia, Orta Nova, Stornara, Stornarella, Lavello, Ascoli Satriano"
    ),
    (
        "Area_BAT_Foggia_Vulture_50km",
        "Barletta, Trani, Andria, Bisceglie, Foggia, Melfi, Venosa, Rionero in Vulture, Candela, Bovino, Monticchio, Manfredonia"
    )
]

nuovi = []
for idx, (area_id, comuni_str) in enumerate(aree_config):
    if idx > 0:
        time.sleep(4)
    unito = "\n\n===\n\n".join(blocchi_testo.get(area_id, []))
    estratti, u_g = cerca_ed_estrai_gemini(api_key, modelli_attivi, unito, area_id, comuni_str)
    urls_validi.update(u_g)
    for raw_ev in estratti:
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
