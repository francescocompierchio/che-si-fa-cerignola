import os
import re
import json
import time
import requests
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

GIORNI_ANTICIPO_MAX = 40

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

FONTI_LOCALI = [
    {"nome": "CerignolaViva Eventi", "url": "https://www.cerignolaviva.it/eventi/", "citta_default": "Cerignola", "solo_eventi": True},
    {"nome": "CerignolaViva Notizie", "url": "https://www.cerignolaviva.it/notizie/", "citta_default": "Cerignola", "solo_eventi": False},
    {"nome": "CanosaViva Eventi", "url": "https://www.canosaviva.it/eventi/", "citta_default": "Canosa di Puglia", "solo_eventi": True},
    {"nome": "CanosaViva Notizie", "url": "https://www.canosaviva.it/notizie/", "citta_default": "Canosa di Puglia", "solo_eventi": False},
    {"nome": "BarlettaViva Eventi", "url": "https://www.barlettaviva.it/eventi/", "citta_default": "Barletta", "solo_eventi": True},
    {"nome": "TraniViva Eventi", "url": "https://www.traniviva.it/eventi/", "citta_default": "Trani", "solo_eventi": True},
    {"nome": "BisceglieViva Eventi", "url": "https://www.bisceglieviva.it/eventi/", "citta_default": "Bisceglie", "solo_eventi": True},
    {"nome": "AndriaViva Eventi", "url": "https://www.andriaviva.it/eventi/", "citta_default": "Andria", "solo_eventi": True}
]

FONTI_PORTALI = [
    {"nome": "Il Tacco di Bacco BAT", "url": "https://iltaccodibacco.it/barletta/"},
    {"nome": "Il Tacco di Bacco Foggia", "url": "https://iltaccodibacco.it/foggia/"}
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

REGEX_TEMA_COERENTE = re.compile(
    r"\b(?:natale|nataliz\w*|luminarie|mercatin\w*|babbo natale|ghiaccio|presep\w*|"
    r"sagra|sagre|street food|degustazion\w*|festa in piazza|festa patronale|"
    r"musica live|concerto|concerti|dj set|serata|serate|cabaret|live music|tribute|"
    r"escursion\w*|trekking|passeggiat\w*|camminat\w*|visita guidata|saline|monticchio|"
    r"weekend|fine settimana|cartellone natalizio|accensione)\b",
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
    "omicidio", "furto", "rapina", "sequestro", "carabinieri", "polizia", "guardia di finanza",
    "calcio", "volley", "basket", "torneo", "podistica", "maratona", "campionato", "audace cerignola"
]

REGEX_SCARTO = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in PAROLE_SCARTO) + r")\b", re.I)


def oggi_iso():
    return datetime.now().strftime("%Y-%m-%d")


def calendario_prossimi_giorni(giorni=18):
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


def pulisci_html_testo(sp, max_chars=450):
    for tag in sp(["script", "style", "nav", "footer", "aside", "form", "noscript", "iframe"]):
        tag.decompose()
    cont = sp.find("main") or sp.find("article") or sp.body or sp
    righe = []
    for raw_line in cont.get_text("\n", strip=True).splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if len(line) < 6:
            continue
        if any(b in line.lower() for b in ("cookie", "privacy", "newsletter", "accedi", "registrati", "cerca gli eventi", "adblocker", "condividi")):
            continue
        if line not in righe:
            righe.append(line)
    return " | ".join(righe)[:max_chars]


def raccogli_portale_viva(session, fonte):
    schede = []
    nome = fonte["nome"]
    url = fonte["url"]
    c_def = fonte["citta_default"]
    solo_ev = fonte["solo_eventi"]

    try:
        r = session.get(url, timeout=(5, 9))
        if r.status_code != 200:
            print(f"{nome}: HTTP {r.status_code}")
            return []
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        links_candidati = []
        for a in soup.find_all("a", href=True):
            t_link = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
            href = urljoin(url, a["href"]).split("#")[0]
            if len(t_link) < 16 or not href.startswith("http") or href == url:
                continue
            if REGEX_SCARTO.search(t_link):
                continue
            if solo_ev or REGEX_TEMA_COERENTE.search(t_link):
                if href not in links_candidati:
                    links_candidati.append(href)

        for link in links_candidati[:4]:
            try:
                rp = session.get(link, timeout=(4, 7))
                if rp.status_code != 200:
                    continue
                rp.encoding = rp.apparent_encoding or "utf-8"
                sp = BeautifulSoup(rp.text, "html.parser")
                h1 = sp.find("h1")
                titolo = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else ""
                if len(titolo) < 8 or REGEX_SCARTO.search(titolo):
                    continue
                corpo = pulisci_html_testo(sp, max_chars=260)
                if REGEX_SCARTO.search(corpo[:220]):
                    continue
                schede.append(f"CITTÀ:{c_def} | URL:{link} | TITOLO:{titolo} | TESTO:{corpo}")
            except Exception:
                continue

        print(f"{nome}: {len(schede)} schede")
    except Exception as e:
        print(f"Errore {nome}: {str(e)[:75]}")

    return schede


def raccogli_tacco(session, fonte):
    schede = []
    url = fonte["url"]
    nome = fonte["nome"]

    try:
        r = session.get(url, timeout=(5, 9))
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
                rp = session.get(link, timeout=(4, 7))
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
                corpo = pulisci_html_testo(sp, max_chars=360)
                if len(corpo) < 50 or REGEX_SCARTO.search(corpo[:250]):
                    continue
                schede.append(f"URL:{link} | TITOLO:{titolo} | DETTAGLI:{corpo}")
            except Exception:
                continue

        print(f"{nome}: {len(schede)} schede")
    except Exception as e:
        print(f"Errore {nome}: {str(e)[:75]}")

    return schede


def ottieni_modelli_attivi(api_key):
    preferiti = [
        "gemini-flash-lite-latest",
        "gemini-flash-latest",
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemma-3-27b-it"
    ]
    try:
        r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}", timeout=(5, 10))
        if r.status_code == 200:
            disponibili = []
            for m in r.json().get("models", []):
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    nome = m.get("name", "").replace("models/", "")
                    if nome:
                        disponibili.append(nome)
            print(f"Modelli attivi su API key: {', '.join(disponibili[:12])}")
            ordinati = [p for p in preferiti if p in disponibili]
            for d in disponibili:
                if ("flash" in d or "gemma-3-27b" in d) and not any(x in d for x in ("image", "audio", "tts", "thinking")) and d not in ordinati:
                    ordinati.append(d)
            if ordinati:
                return ordinati[:6]
    except Exception as e:
        print(f"Avviso lista modelli: {str(e)[:70]}")
    return preferiti[:5]


def estrai_unico_blocco_gemini(api_key, testo_unico):
    if not api_key or not testo_unico.strip():
        return [], False
    oggi = oggi_iso()
    fine_natale = (datetime.now() + timedelta(days=28)).strftime("%Y-%m-%d")
    cal_ref = calendario_prossimi_giorni(18)

    modelli = ottieni_modelli_attivi(api_key)

    prompt = (
        f"Estrai gli eventi reali di tempo libero (Natale/luminarie, musica live/DJ set, sagre/food, escursioni/passeggiate) entro 50 km da Cerignola.\n"
        f"CALENDARIO: {cal_ref}.\n"
        f"Scarta teatro di prosa, concerti sinfonici/pianistici, convegni, sport, parrocchie ed eventi passati (dataFine < '{oggi}').\n"
        f"Comuni ammessi: Cerignola, Stornara, Stornarella, Orta Nova, San Ferdinando di Puglia, Trinitapoli, Canosa di Puglia, Ordona, Carapelle, Margherita di Savoia, Lavello, Ascoli Satriano, Zapponeta, Castelluccio dei Sauri, Barletta, Candela, Minervino Murge, Foggia, Melfi, Venosa, Deliceto, Rapolla, Andria, Barile, Palazzo San Gervasio, Rocchetta Sant'Antonio, Manfredonia, Rionero in Vulture, Trani, Bovino, Spinazzola, Troia, Lucera, Bisceglie, Monticchio.\n"
        f"Se manca una data singola per luminarie/mercatini/villaggi natalizi, usa dataInizio='{oggi}' e dataFine='{fine_natale}'.\n"
        "Rispondi SOLO con un array JSON valido di oggetti con queste esatte chiavi: "
        '[{"tipoContenuto":"evento","citta":"...","categoria":"Musica & Concerti|Locali & Serate|Sagre & Food|Famiglie & Bambini|Natura & Escursioni|Attività diurne","titolo":"...","dataTesto":"...","dataInizio":"YYYY-MM-DD","dataFine":"YYYY-MM-DD","luogo":"...","indirizzoMappa":"...","costo":"...","descrizione":"...","fonteUrl":"..."}]\n\n'
        f"DATI:\n{testo_unico}"
    )

    for mod in modelli:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
        gen_cfg = {"temperature": 0.1}
        if not mod.startswith("gemma"):
            gen_cfg["responseMimeType"] = "application/json"

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": gen_cfg
        }
        try:
            r = requests.post(url, json=payload, timeout=(8, 35))
            if r.status_code in (400, 404, 429, 503):
                print(f"[Gemini] HTTP {r.status_code} su {mod}, provo successivo...")
                time.sleep(3)
                continue
            if r.status_code != 200:
                print(f"[Gemini] HTTP {r.status_code} su {mod}: {r.text[:100]}")
                continue

            parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            raw = "\n".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            raw_clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()
            m_arr = re.search(r"\[.*\]", raw_clean, flags=re.S)
            if m_arr:
                raw_clean = m_arr.group(0)
            dati = json.loads(raw_clean)
            if isinstance(dati, list):
                print(f"[Gemini] Estratti {len(dati)} eventi da {mod}.")
                return dati, True
        except Exception as e:
            print(f"[Gemini] Errore {mod}: {str(e)[:80]}")
            time.sleep(2)
            continue

    return [], False


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

manuali_admin = []
precedenti_auto = []

try:
    with open("eventi.json", "r", encoding="utf-8") as f:
        esistenti = json.load(f)
    if isinstance(esistenti, list):
        for raw_old in esistenti:
            if raw_old.get("tipoContenuto") != "evento":
                continue
            d_fin = (raw_old.get("dataFine") or raw_old.get("dataInizio") or "").strip()[:10]
            if not (re.match(r"^\d{4}-\d{2}-\d{2}$", d_fin) and d_fin >= oggi and len((raw_old.get("titolo") or "").strip()) >= 3):
                continue
            url_old = (raw_old.get("fonteUrl") or "").lower()
            if any(d in url_old for d in DOMINI_AUTO):
                precedenti_auto.append(raw_old)
            else:
                manuali_admin.append(raw_old)
except Exception:
    pass

tutte_schede = []
visti_link = set()

for f_loc in FONTI_LOCALI:
    for sc in raccogli_portale_viva(session, f_loc):
        m_url = re.search(r"URL:(\S+)", sc)
        u = m_url.group(1) if m_url else sc[:80]
        if u not in visti_link:
            visti_link.add(u)
            tutte_schede.append(sc)

for fonte in FONTI_PORTALI:
    for sc in raccogli_tacco(session, fonte):
        m_url = re.search(r"URL:(\S+)", sc)
        u = m_url.group(1) if m_url else sc[:80]
        if u not in visti_link:
            visti_link.add(u)
            tutte_schede.append(sc)

testo_unico = "\n".join(tutte_schede)[:5600]
print(f"[Batch Unico] Invio {len(tutte_schede)} schede ({len(testo_unico)} char) a Gemini...")

estratti, api_ok = estrai_unico_blocco_gemini(api_key, testo_unico)
consolidati = list(manuali_admin)

if api_ok:
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
else:
    print("[Avviso] Tutti i modelli Gemini temporaneamente occupati: mantengo eventi validi esistenti.")
    for ev_old in precedenti_auto:
        if not any(sono_duplicati(x, ev_old) for x in consolidati):
            consolidati.append(ev_old)

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
