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
    {"url": "https://www.cerignolaviva.it/eventi/", "citta": "Cerignola", "blocco": "Capitanata"},
    {"url": "https://www.immediato.net/category/eventi/", "citta": "Foggia", "blocco": "Capitanata"},
    {"url": "https://www.foggiatoday.it/eventi/", "citta": "Foggia", "blocco": "Capitanata"},
    {"url": "https://www.barlettaviva.it/eventi/", "citta": "Barletta", "blocco": "BAT"},
    {"url": "https://www.traniviva.it/eventi/", "citta": "Trani", "blocco": "BAT"},
    {"url": "https://www.bisceglieviva.it/eventi/", "citta": "Bisceglie", "blocco": "BAT"},
    {"url": "https://www.andriaviva.it/eventi/", "citta": "Andria", "blocco": "BAT"},
]

DOMINI_OK = {urlparse(f["url"]).netloc.lower() for f in FONTI_LOCALI}

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
    if not luogo or luogo.lower() in ("da definire", "da verificare", "n/d", "sede nell'articolo", citta.lower()):
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


def verifica_evento(ev):
    oggi = oggi_iso()
    max_d = (datetime.now() + timedelta(days=120)).strftime("%Y-%m-%d")
    d1, d2 = ev.get("dataInizio", ""), ev.get("dataFine", "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d1) or not re.match(r"^\d{4}-\d{2}-\d{2}$", d2):
        return False, "formato_data"
    if d2 < oggi:
        return False, f"passato({d2})"
    if d1 > d2 or d1 > max_d:
        return False, f"intervallo({d1}->{d2})"
    titolo = ev.get("titolo", "")
    if len(titolo) < 5:
        return False, "titolo_corto"
    testo = f"{titolo} {ev.get('descrizione', '')} {ev.get('dataTesto', '')}"
    m = REGEX_VIETATE.search(testo)
    if m:
        return False, f"vietata({m.group(0)})"
    return True, "ok"


def estrai_pub_date(soup):
    meta = soup.find("meta", property="article:published_time")
    if meta and meta.get("content"):
        return str(meta["content"])[:10]
    t_tag = soup.find("time", attrs={"datetime": True})
    if t_tag:
        return str(t_tag["datetime"])[:10]
    return ""


def estrai_testo_articolo(sp):
    for tag in sp(["script", "style", "nav", "footer", "aside", "form", "noscript", "iframe"]):
        tag.decompose()
    for bad in sp.select('[class*="related"], [class*="correlat"], [class*="sidebar"], [class*="cookie"], [class*="adblock"], [class*="banner"], [id*="cookie"]'):
        bad.decompose()

    # Cerca prima i contenitori tipici del corpo articolo, altrimenti usa main o body
    cont = (
        sp.select_one('[class*="article-body"], [class*="entry-content"], [class*="article-content"], [class*="post-content"]')
        or sp.find("main")
        or sp.find("article")
        or sp.body
        or sp
    )

    righe = []
    for raw_line in cont.get_text("\n", strip=True).splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        low = line.lower()
        if len(line) < 12:
            continue
        if any(b in low for b in ("adblocker", "ci stai leggendo", "cookie", "abbonati", "newsletter", "leggi anche", "© riproduzione", "condividi su", "whatsapp", "telegram")):
            continue
        if line not in righe:
            righe.append(line)

    return " | ".join(righe)[:1450]


def raccogli_portale(session, url_indice, citta_def):
    schede = []
    urls_ok = set()
    try:
        r = session.get(url_indice, timeout=(4, 7))
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

        for link in links[:10]:
            try:
                rp = session.get(link, timeout=(4, 6))
                if rp.status_code != 200:
                    continue
                rp.encoding = rp.apparent_encoding or "utf-8"
                sp = BeautifulSoup(rp.text, "html.parser")
                pub_d = estrai_pub_date(sp)

                h1 = sp.find("h1")
                titolo = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else ""
                if len(titolo) < 8 or REGEX_VIETATE.search(titolo):
                    continue

                corpo = estrai_testo_articolo(sp)
                if len(corpo) < 60:
                    continue

                urls_ok.add(link)
                pub_info = f" | PUBBLICATO: {pub_d}" if pub_d else ""
                schede.append(f"[{citta_def}{pub_info}] URL: {link}\nTITOLO: {titolo}\nTESTO: {corpo}")
            except Exception:
                continue

        media_c = int(sum(len(s) for s in schede) / len(schede)) if schede else 0
        print(f"Fonte {citta_def}: {len(schede)} schede (media {media_c} char/scheda)")
    except Exception as e:
        print(f"Errore fonte {citta_def}: {str(e)[:80]}")

    return schede, urls_ok


def estrai_con_gemini(api_key, testo_blocco, nome_blocco):
    if not api_key or not testo_blocco.strip():
        return []
    oggi = oggi_iso()
    giorno_sett = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"][datetime.now().weekday()]

    # Usa prima gemini-3.5-flash (più accurato su blocchi lunghi) poi fallback su lite
    modelli = ["gemini-3.5-flash", "gemini-3-flash-preview", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]

    prompt = (
        f"Curatore di 'Che Si Fa Cerignola', guida agli eventi e al tempo libero. Oggi è {giorno_sett} {oggi}.\n"
        f"Leggi gli articoli di '{nome_blocco}' ed estrai TUTTI gli eventi aperti al pubblico "
        f"(concerti, musica live, DJ set, serate nei locali, sagre, degustazioni, mercatini/villaggi/luminarie/eventi di Natale, "
        f"spettacoli teatrali, cabaret, attività per bambini/famiglie, escursioni, rassegne culturali) "
        f"che si svolgono da oggi {oggi} in poi (dataFine >= '{oggi}').\n"
        "REGOLE:\n"
        "- Usa 'PUBBLICATO: YYYY-MM-DD' solo per calcolare date relative nel testo ('questo sabato', 'domenica', 'nel weekend'). Non usare la data di pubblicazione come data dell'evento se l'articolo indica una data diversa.\n"
        "- Indica dataInizio e dataFine nel formato YYYY-MM-DD (anno corrente 2026 o 2027 per gennaio).\n"
        "- Indica in 'luogo' il teatro, piazza, locale o sede dell'evento.\n"
        "- Escludi solo cronaca nera, politica/comune, messe/processioni, sport e resoconti di eventi già terminati prima di oggi.\n"
        "- Copia in 'fonteUrl' esattamente l'URL indicato accanto all'articolo.\n\n"
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
                print(f"[{nome_blocco}] HTTP {r.status_code} su {mod}, passo al successivo...")
                continue
            if r.status_code != 200:
                print(f"[{nome_blocco}] HTTP {r.status_code} su {mod}: {r.text[:110]}")
                continue
            parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            raw = "\n".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            dati = json.loads(raw)
            if isinstance(dati, list):
                print(f"[{nome_blocco}] Risposta OK da {mod}: {len(dati)} eventi.")
                if len(dati) > 0:
                    return dati
                print(f"[{nome_blocco}] 0 eventi su {mod}, provo modello successivo...")
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
    return SequenceMatcher(None, t1, t2).ratio() >= 0.72


# ==============================================================================
# ESECUZIONE PRINCIPALE
# ==============================================================================
t_start = time.time()
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
    ok, _ = verifica_evento(ev)
    if ok and not any(sono_duplicati(x, ev) for x in consolidati):
        consolidati.append(ev)

session = requests.Session()
session.headers.update(HEADERS)

blocchi = {"Capitanata": [], "BAT": []}
for fonte in FONTI_LOCALI:
    if time.time() - t_start > 55:
        break
    sc, u_ok = raccogli_portale(session, fonte["url"], fonte["citta"])
    urls_validi.update(u_ok)
    blocchi[fonte["blocco"]].extend(sc)

nuovi = []
for idx, (nome_b, lista_sc) in enumerate(blocchi.items()):
    if not lista_sc:
        continue
    if idx > 0:
        time.sleep(1)
    testo_unito = "\n\n---\n\n".join(lista_sc)[:24000]
    print(f"[{nome_b}] Invio {len(lista_sc)} schede ({len(testo_unito)} char)...")
    estratti = estrai_con_gemini(api_key, testo_unito, nome_b)
    validati_b = 0
    for raw_ev in estratti:
        ev = pulisci_evento(raw_ev, "Cerignola", urls_validi)
        ok, motivo = verifica_evento(ev)
        if ok:
            nuovi.append(ev)
            validati_b += 1
        else:
            print(f"[{nome_b}] Scartato ({motivo}): {ev.get('titolo')} | {ev.get('dataInizio')}->{ev.get('dataFine')}")
    print(f"[{nome_b}] Validati pronti per l'app: {validati_b}")

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

print(f"Fine: {len(lista_finale)} eventi (in {int(time.time() - t_start)}s)")
