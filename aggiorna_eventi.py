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

FONTI_LOCALI = [
    {"url": "https://www.cerignolaviva.it/eventi/", "citta": "Cerignola"},
    {"url": "https://www.foggiatoday.it/eventi/", "citta": "Foggia"},
    {"url": "https://www.foggiatoday.it/eventi/weekend/", "citta": "Foggia"},
    {"url": "https://www.immediato.net/category/eventi/", "citta": "Foggia"},
    {"url": "https://www.statoquotidiano.it/category/eventi/", "citta": "Manfredonia"},
    {"url": "https://www.barlettaviva.it/eventi/", "citta": "Barletta"},
    {"url": "https://www.traniviva.it/eventi/", "citta": "Trani"},
    {"url": "https://www.bisceglieviva.it/eventi/", "citta": "Bisceglie"},
    {"url": "https://www.andriaviva.it/eventi/", "citta": "Andria"},
]

DOMINI_OK = {urlparse(f["url"]).netloc.lower() for f in FONTI_LOCALI}

FALLBACK_URL = {
    "Cerignola": "https://www.cerignolaviva.it/eventi/",
    "Foggia": "https://www.foggiatoday.it/eventi/",
    "Manfredonia": "https://www.statoquotidiano.it/category/eventi/",
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
    "adblocker", "ci stai leggendo", "archivio", "agenda di", "eventi in agenda",
    "cronaca", "politica", "alimentazione", "nutrizione", "dieta", "screening",
    "vescovo", "diocesi", "parrocchia", "santa messa", "processione", "devozione",
    "beneficenza", "raccolta fondi", "raccolta alimentare",
    "si è svolta", "si è svolto", "si è tenuto", "si è conclusa", "si è concluso",
    "grande affluenza", "applausi per", "annullato", "rinviato", "indagine di mercato",
    "meteo", "libeccio", "allerta meteo",
    "frode", "riciclaggio", "indagati", "indagato", "sequestri", "sequestro",
    "scontro tra auto", "morti e feriti", "questore", "sospende la licenza",
    "arresto", "arresti", "rapina", "incidente", "incendio", "denuncia",
    "tribunale", "carabinieri", "polizia", "guardia di finanza",
    "consiglio comunale", "giunta", "elezioni", "partito", "sciopero", "ospedale", "asl",
    "furto", "truffa", "omicidio", "ferito", "morto", "lutto", "cordoglio",
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
    dom = urlparse(url).netloc.lower()
    if url not in urls_ok and dom not in DOMINI_OK:
        url = FALLBACK_URL.get(citta, "https://www.cerignolaviva.it/eventi/")
    d_ini = (ev.get("dataInizio") or "").strip()[:10]
    d_fin = (ev.get("dataFine") or d_ini).strip()[:10]
    luogo = re.sub(r"\s+", " ", (ev.get("luogo") or "")).strip()
    if not luogo or luogo.lower() in ("da definire", "da verificare", "n/d", "sede nell'articolo"):
        luogo = f"Centro / Varie sedi, {citta}"
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
    max_d = (datetime.now() + timedelta(days=120)).strftime("%Y-%m-%d")
    d1, d2 = ev.get("dataInizio", ""), ev.get("dataFine", "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d1) or not re.match(r"^\d{4}-\d{2}-\d{2}$", d2):
        return False
    if d2 < oggi or d1 > d2 or d1 > max_d:
        return False
    titolo = ev.get("titolo", "")
    if len(titolo) < 5:
        return False
    testo = f"{titolo} {ev.get('descrizione', '')} {ev.get('dataTesto', '')}"
    if REGEX_VIETATE.search(testo):
        return False
    return True


def estrai_pub_date(soup):
    meta = soup.find("meta", property="article:published_time")
    if meta and meta.get("content"):
        return str(meta["content"])[:10]
    t_tag = soup.find("time", attrs={"datetime": True})
    if t_tag:
        return str(t_tag["datetime"])[:10]
    return ""


def raccogli_portale(url_indice, citta_def):
    schede = []
    urls_ok = set()
    titoli_log = []
    try:
        r = requests.get(url_indice, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"Fonte {citta_def}: HTTP {r.status_code}")
            return [], set()
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
            if len(path_clean) < 10:
                continue
            if "/eventi/" not in low and "/" not in path_clean:
                continue
            txt = re.sub(r"\s+", " ", a.get_text(" ", strip=True) or a.get("title", ""))
            if len(txt) < 12 or REGEX_VIETATE.search(txt):
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
                pub_d = estrai_pub_date(sp)

                for tag in sp(["script", "style", "nav", "footer", "aside", "form"]):
                    tag.decompose()

                box = sp.find("article") or sp.find("main") or sp
                h1 = box.find("h1") or sp.find("h1")
                titolo = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else ""
                if len(titolo) < 8 or REGEX_VIETATE.search(titolo):
                    continue

                # Estrae sia metadati (div/span foglia con date/luoghi) sia tutti i paragrafi reali
                righe = []
                for el in box.find_all(["p", "li", "dd", "h2", "h3", "time", "address", "div", "span"]):
                    if el.name in ("div", "span") and el.find(["p", "div", "section", "article", "ul"]):
                        continue
                    t = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
                    low_t = t.lower()
                    if any(b in low_t for b in ("adblocker", "ci stai leggendo", "cookie", "abbonati", "newsletter", "leggi anche", "© riproduzione", "condividi su")):
                        continue
                    if 10 <= len(t) <= 800 and t not in righe:
                        righe.append(t)

                corpo = " | ".join(righe[:24])[:1800]
                if len(corpo) < 35:
                    continue

                urls_ok.add(link)
                if len(titoli_log) < 2:
                    titoli_log.append(titolo[:45])
                pub_info = f" | PUBBLICATO: {pub_d}" if pub_d else ""
                schede.append(f"[{citta_def}{pub_info}] URL: {link}\nTITOLO: {titolo}\nTESTO: {corpo}")
            except Exception:
                continue

        anteprima = f" ({'; '.join(titoli_log)})" if titoli_log else ""
        print(f"Fonte {citta_def}: {len(schede)} schede{anteprima}")
    except Exception as e:
        print(f"Errore fonte {citta_def}:", e)

    return schede, urls_ok


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
                # Esclude modelli dismessi (2.0/2.5-flash), sperimentali lenti (3.6/3.7/3.8) e non testuali
                if any(bad in low for bad in ("2.0-", "2.5-flash", "3.6-", "3.7-", "3.8-", "omni", "4-")):
                    continue
                if any(x in low for x in ("embedding", "imagen", "veo", "tts", "audio", "robotics", "computer", "research", "image", "transcribe")):
                    continue
                tutti.append(nome)

            def priorita(n):
                l = n.lower()
                p = 0
                if l == "gemini-flash-latest":
                    p -= 60
                elif l == "gemini-3-flash-preview":
                    p -= 50
                elif l == "gemini-3.5-flash":
                    p -= 40
                elif "3.1-flash-lite" in l:
                    p -= 30
                elif "3.5-flash-lite" in l:
                    p -= 20
                elif "pro" in l:
                    p -= 10
                return (p, l)

            ordinati = sorted(tutti, key=priorita)
            if ordinati:
                print("Modelli selezionati:", ", ".join(ordinati[:5]))
                return ordinati[:5]
    except Exception as e:
        print("Errore verifica modelli:", e)
    return ["gemini-flash-latest", "gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-pro"]


def estrai_con_gemini(api_key, modelli, testo_blocco, nome_blocco):
    if not api_key or not testo_blocco.strip():
        return []
    oggi = oggi_iso()
    giorno_sett = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"][datetime.now().weekday()]

    prompt = (
        f"Curatore di 'Che Si Fa Cerignola', app per il tempo libero. Oggi è {giorno_sett} {oggi}.\n"
        f"Leggi gli articoli del '{nome_blocco}' ed estrai TUTTI gli eventi aperti al pubblico "
        f"(concerti, musica live, DJ set, serate nei locali, sagre, degustazioni, mercatini/villaggi/luminarie di Natale, "
        f"spettacoli teatrali, cabaret, attività per bambini/famiglie, escursioni, rassegne culturali/festival) "
        f"che si svolgono da oggi {oggi} in poi (dataFine >= '{oggi}').\n"
        "REGOLE:\n"
        "- Usa 'PUBBLICATO: YYYY-MM-DD' solo per capire espressioni relative ('questo sabato', 'domenica', 'nel weekend'). Non usare la data di pubblicazione come data dell'evento se l'articolo indica un'altra data.\n"
        "- Indica dataInizio e dataFine nel formato YYYY-MM-DD.\n"
        "- Indica in 'luogo' il teatro, piazza, locale o sede reale dell'evento.\n"
        "- Escludi cronaca nera, politica/comune, messe/processioni, sport e resoconti di eventi già terminati prima di oggi.\n"
        "- Copia in 'fonteUrl' l'URL esatto dell'articolo.\n"
        "- Restituisci SOLO un array JSON valido con chiavi: "
        "tipoContenuto ('evento'), citta, categoria (tra 'Locali & Serate', 'Attività serali', 'Musica & Concerti', 'Sagre & Food', 'Famiglie & Bambini', 'Natura & Escursioni', 'Attività diurne', 'Altro'), "
        "titolo, dataTesto, dataInizio, dataFine, luogo, indirizzoMappa, costo, descrizione, fonteUrl.\n\n"
        f"{testo_blocco}"
    )

    for mod in modelli:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
        }
        try:
            r = requests.post(url, json=payload, timeout=90)
            if r.status_code in (404, 429, 503):
                print(f"[{nome_blocco}] HTTP {r.status_code} su {mod}, passo al successivo...")
                continue
            if r.status_code != 200:
                print(f"[{nome_blocco}] HTTP {r.status_code} su {mod}: {r.text[:110]}")
                continue
            parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            # Ignora eventuali parti di pensiero interno (thought=True)
            testi_risposta = [p.get("text", "") for p in parts if not p.get("thought")]
            raw = "\n".join(testi_risposta or [p.get("text", "") for p in parts]).strip()
            raw = re.sub(r"^`{3}json\s*|`{3}$", "", raw, flags=re.I).strip()
            m = re.search(r"\[.*\]", raw, flags=re.DOTALL)
            dati = json.loads(m.group(0) if m else raw)
            if isinstance(dati, list) and len(dati) > 0:
                print(f"[{nome_blocco}] Estratti {len(dati)} eventi con {mod}.")
                return dati
            print(f"[{nome_blocco}] 0 eventi con {mod}, provo modello successivo...")
        except Exception as e:
            print(f"[{nome_blocco}] Errore {mod}: {str(e)[:90]}")
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
modelli_attivi = scopri_modelli_gemini(api_key) if api_key else []
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

tutte_schede = []
for fonte in FONTI_LOCALI:
    sc, u_ok = raccogli_portale(fonte["url"], fonte["citta"])
    urls_validi.update(u_ok)
    tutte_schede.extend(sc)

# Divide le schede in piccoli batch da ~9.500 caratteri per evitare timeout
batches = []
corrente = []
lung = 0
for s in tutte_schede:
    if corrente and lung + len(s) > 9500:
        batches.append("\n\n---\n\n".join(corrente))
        corrente = [s]
        lung = len(s)
    else:
        corrente.append(s)
        lung += len(s)
if corrente:
    batches.append("\n\n---\n\n".join(corrente))

nuovi = []
for idx, blocco in enumerate(batches, 1):
    if idx > 1:
        time.sleep(2)
    nome_b = f"Batch {idx}/{len(batches)}"
    estratti = estrai_con_gemini(api_key, modelli_attivi, blocco, nome_b)
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
