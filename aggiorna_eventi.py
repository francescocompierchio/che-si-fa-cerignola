import os
import re
import json
import time
import requests
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urljoin
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
    "lanotiziaweb.it", "marchiodoc.it", "cerignolaviva.it",
    "canosaviva.it", "barlettaviva.it", "traniviva.it",
    "bisceglieviva.it", "andriaviva.it", "statoquotidiano.it",
    "immediato.net", "vulturenews.net",
    "teatromercadantecerignola.it", "teatrogiordano.it",
    "palazzodelleartibeltrani.it", "politeamaitalia.com",
    "happyticket.com", "pugliaculture.it", "ciaotickets.com", "virgilio.it"
)

# Testate locali reali di Cerignola e raggio 50 km (funzionano senza blocchi da GitHub Actions)
TESTATE_LOCALI = [
    {"nome": "La Notizia Web (Cerignola)", "url": "https://www.lanotiziaweb.it/feed/", "citta_default": "Cerignola"},
    {"nome": "MarchioDoc (Cerignola)", "url": "https://www.marchiodoc.it/feed/", "citta_default": "Cerignola"},
    {"nome": "CerignolaViva", "url": "https://www.cerignolaviva.it/notizie/", "citta_default": "Cerignola"},
    {"nome": "CanosaViva", "url": "https://www.canosaviva.it/notizie/", "citta_default": "Canosa di Puglia"},
    {"nome": "BarlettaViva", "url": "https://www.barlettaviva.it/notizie/", "citta_default": "Barletta"},
    {"nome": "TraniViva", "url": "https://www.traniviva.it/notizie/", "citta_default": "Trani"},
    {"nome": "BisceglieViva", "url": "https://www.bisceglieviva.it/notizie/", "citta_default": "Bisceglie"},
    {"nome": "AndriaViva", "url": "https://www.andriaviva.it/notizie/", "citta_default": "Andria"},
    {"nome": "Stato Quotidiano (Capitanata)", "url": "https://www.statoquotidiano.it/feed/", "citta_default": ""},
    {"nome": "Immediato (Foggia & Capitanata)", "url": "https://www.immediato.net/feed/", "citta_default": ""},
    {"nome": "VultureNews (Melfi/Venosa/Monticchio)", "url": "https://www.vulturenews.net/feed/", "citta_default": ""}
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

REGEX_COMUNI_50KM = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in sorted(COMUNI_50KM.keys(), key=len, reverse=True)) + r")\b",
    re.I
)

# Filtro tematico positivo: lascia passare solo Natale, luminarie, sagre, musica live, serate ed escursioni
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


def pulisci_html_testo(sp, max_chars=1500):
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


def raccogli_testata_locale(session, fonte):
    schede = []
    nome = fonte["nome"]
    url = fonte["url"]
    c_def = fonte["citta_default"]
    soglia_pub = datetime.now(timezone.utc) - timedelta(days=14)

    try:
        r = session.get(url, timeout=(5, 9))
        if r.status_code != 200:
            print(f"{nome}: HTTP {r.status_code}")
            return []
        r.encoding = r.apparent_encoding or "utf-8"
        body_text = r.text.strip()

        # Caso 1: Feed RSS XML (WordPress / giornali locali)
        if body_text.startswith("<?xml") or "<rss" in body_text[:300] or "<feed" in body_text[:300]:
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:25]:
                titolo = re.sub(r"\s+", " ", (item.findtext("title") or "")).strip()
                link = (item.findtext("link") or "").strip()
                pub_raw = (item.findtext("pubDate") or "").strip()

                # Estrae testo completo da content:encoded o description
                contenuto_raw = ""
                for child in item:
                    if child.tag.endswith("encoded") or child.tag == "description":
                        if child.text and len(child.text) > len(contenuto_raw):
                            contenuto_raw = child.text
                testo_art = re.sub(r"\s+", " ", BeautifulSoup(contenuto_raw, "html.parser").get_text(" ", strip=True)).strip()

                combinato = f"{titolo} {testo_art[:450]}"
                if len(titolo) < 8 or REGEX_SCARTO.search(combinato):
                    continue
                if not REGEX_TEMA_COERENTE.search(combinato):
                    continue
                if not c_def and not REGEX_COMUNI_50KM.search(combinato):
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

                pref_citta = f"CITTÀ DI RIFERIMENTO: {c_def} | " if c_def else ""
                schede.append(
                    f"FONTE: {nome} | {pref_citta}PUBBLICATO: {pub_str} | URL: {link}\n"
                    f"TITOLO: {titolo}\n"
                    f"ARTICOLO: {testo_art[:550]}"
                )
            print(f"{nome}: {len(schede)} articoli coerenti")
            return schede

        # Caso 2: Pagina indice HTML (es. network Viva)
        soup = BeautifulSoup(body_text, "html.parser")
        links_candidati = []
        for a in soup.find_all("a", href=True):
            t_link = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
            href = urljoin(url, a["href"]).split("#")[0]
            if len(t_link) < 18 or not href.startswith("http"):
                continue
            if REGEX_TEMA_COERENTE.search(t_link) and not REGEX_SCARTO.search(t_link):
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
                corpo = pulisci_html_testo(sp, max_chars=750)
                if REGEX_SCARTO.search(corpo[:350]):
                    continue
                pref_citta = f"CITTÀ DI RIFERIMENTO: {c_def} | " if c_def else ""
                schede.append(
                    f"FONTE: {nome} | {pref_citta}URL: {link}\n"
                    f"TITOLO: {titolo}\n"
                    f"ARTICOLO: {corpo}"
                )
            except Exception:
                continue

        print(f"{nome}: {len(schede)} articoli coerenti")
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
                # 1500 caratteri per non tagliare mai data, indirizzo e comune dell'evento
                corpo = pulisci_html_testo(sp, max_chars=1500)
                if len(corpo) < 60 or REGEX_SCARTO.search(corpo[:400]):
                    continue
                schede.append(f"FONTE: {nome} | URL: {link}\nTITOLO: {titolo}\nDETTAGLI COMPLETI: {corpo}")
            except Exception:
                continue

        print(f"{nome}: {len(schede)} schede complete")
    except Exception as e:
        print(f"Errore {nome}: {str(e)[:75]}")

    return schede


def estrai_con_gemini(api_key, testo_blocco, idx_blocco):
    if not api_key or not testo_blocco.strip():
        return []
    oggi = oggi_iso()
    limite_max = (datetime.now() + timedelta(days=GIORNI_ANTICIPO_MAX)).strftime("%Y-%m-%d")
    cal_ref = calendario_prossimi_giorni(21)

    # gemini-2.5-flash come modello primario per velocità e stabilità
    modelli = ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-2.5-flash-lite"]

    prompt = (
        f"Selezionatore di 'Che Si Fa Cerignola', guida agli eventi di tempo libero, Natale, serate ed escursioni entro 50 km da Cerignola.\n"
        f"CALENDARIO DI RIFERIMENTO: {cal_ref}.\n"
        f"Estrai TUTTI gli eventi reali presenti nelle schede qui sotto con dataFine >= '{oggi}' e dataInizio <= '{limite_max}'.\n"
        "COSA INCLUDERE:\n"
        "1. Natale & Luminarie: luminarie, accensione alberi, mercatini di Natale, villaggi di Babbo Natale, piste di ghiaccio, presepi viventi, cartelloni natalizi.\n"
        "2. Musica Live & Serate: concerti, band dal vivo nei pub/piazze, DJ set, serate nei locali, cabaret.\n"
        "3. Sagre & Food: sagre gastronomiche, street food, feste in piazza, degustazioni.\n"
        "4. Escursioni & Passeggiate: trekking, passeggiate guidate, visite naturalistiche (Saline Margherita di Savoia, Monticchio, Castel del Monte/Alta Murgia, Bosco Incoronata, borghi).\n"
        "COSA SCARTARE:\n"
        "- Teatro di prosa, recital pianistici, concerti sinfonici/classici, convegni, seminari, parrocchie, sport, mostre fotografiche, presentazione libri e articoli di eventi già conclusi.\n"
        "REGOLE DATE E COMUNI:\n"
        "- Comuni ammessi (entro 50 km): Cerignola, Stornara, Stornarella, Orta Nova, San Ferdinando di Puglia, Trinitapoli, Canosa di Puglia, Ordona, Carapelle, Margherita di Savoia, Lavello, Ascoli Satriano, Zapponeta, Castelluccio dei Sauri, Barletta, Candela, Minervino Murge, Foggia, Melfi, Venosa, Deliceto, Rapolla, Andria, Barile, Palazzo San Gervasio, Rocchetta Sant'Antonio, Manfredonia, Rionero in Vulture, Trani, Bovino, Spinazzola, Troia, Lucera, Bisceglie, Monticchio.\n"
        "- Se una scheda ha 'CITTÀ DI RIFERIMENTO' e non cita un altro comune, usa quella città.\n"
        "- Se una notizia parla di 'questo sabato', 'domenica', 'questo weekend' o 'venerdì', usa la data esatta dal CALENDARIO DI RIFERIMENTO.\n"
        "- Se una notizia annuncia luminarie, pista di ghiaccio o programma natalizio senza una data numerica singola, imposta dataInizio='{oggi}' (o PUBBLICATO se >= '{oggi}') e dataFine='{(datetime.now() + timedelta(days=28)).strftime('%Y-%m-%d')}'.\n"
        "- Categorie ammesse: 'Musica & Concerti', 'Locali & Serate', 'Sagre & Food', 'Famiglie & Bambini', 'Natura & Escursioni', 'Attività diurne'.\n"
        "- Copia in 'fonteUrl' l'URL esatto della scheda.\n\n"
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
            r = requests.post(url, json=payload, timeout=(8, 50))
            if r.status_code in (404, 429, 503):
                print(f"[Blocco {idx_blocco}] HTTP {r.status_code} su {mod}, provo successivo...")
                time.sleep(6)
                continue
            if r.status_code != 200:
                print(f"[Blocco {idx_blocco}] HTTP {r.status_code} su {mod}: {r.text[:110]}")
                continue
            parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            raw = "\n".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            dati = json.loads(raw)
            if isinstance(dati, list):
                print(f"[Blocco {idx_blocco}] Estratti {len(dati)} eventi da {mod}.")
                return dati
        except Exception as e:
            print(f"[Blocco {idx_blocco}] Errore {mod}: {str(e)[:80]}")
            time.sleep(4)
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

# Conserva eventuali inserimenti manuali già presenti in eventi.json (non provenienti dai feed automatici)
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
for testata in TESTATE_LOCALI:
    tutte_schede.extend(raccogli_testata_locale(session, testata))

for fonte in FONTI_PORTALI:
    tutte_schede.extend(raccogli_tacco(session, fonte))

print(f"Totale schede coerenti raccolte: {len(tutte_schede)}")

# Divide in massimo 2 pacchetti compatti per evitare timeout o saturazione quota
pacchetti = []
corrente = []
char_correnti = 0
for sc in tutte_schede:
    if char_correnti + len(sc) > 7500 and corrente:
        pacchetti.append("\n---\n".join(corrente))
        corrente = [sc]
        char_correnti = len(sc)
    else:
        corrente.append(sc)
        char_correnti += len(sc)
if corrente:
    pacchetti.append("\n---\n".join(corrente))

for idx, pkg in enumerate(pacchetti[:2], start=1):
    if idx > 1:
        time.sleep(5)
    print(f"[Blocco {idx}] Invio {len(pkg)} char a Gemini...")
    estratti = estrai_con_gemini(api_key, pkg, idx)
    validati_b = 0
    for raw_ev in estratti:
        ev = pulisci_evento(raw_ev)
        ok, motivo = verifica_evento(ev)
        if ok:
            if not any(sono_duplicati(x, ev) for x in consolidati):
                consolidati.append(ev)
                validati_b += 1
        else:
            print(f"[Blocco {idx}] Scartato ({motivo}): {ev.get('citta') or '?'} - {ev.get('titolo')}")
    print(f"[Blocco {idx}] Validati coerenti: {validati_b}")

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
