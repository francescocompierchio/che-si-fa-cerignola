import os
import re
import json
import time
import requests
from difflib import SequenceMatcher
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9"
}

FONTI_EVENTI = [
    {"url": "https://www.viverecerignola.it/", "citta": "Cerignola", "gruppo": "Nord / Capitanata"},
    {"url": "https://www.cerignolaviva.it/eventi/", "citta": "Cerignola", "gruppo": "Nord / Capitanata"},
    {"url": "https://www.foggiatoday.it/eventi/", "citta": "Foggia", "gruppo": "Nord / Capitanata"},
    {"url": "https://www.foggiatoday.it/eventi/weekend/", "citta": "Foggia", "gruppo": "Nord / Capitanata"},
    {"url": "https://www.barlettaviva.it/eventi/", "citta": "Barletta", "gruppo": "Costa BAT e Gargano"},
    {"url": "https://www.traniviva.it/eventi/", "citta": "Trani", "gruppo": "Costa BAT e Gargano"},
    {"url": "https://www.bisceglieviva.it/eventi/", "citta": "Bisceglie", "gruppo": "Costa BAT e Gargano"},
    {"url": "https://www.andriaviva.it/eventi/", "citta": "Andria", "gruppo": "Costa BAT e Gargano"},
    {"url": "https://www.manfredonianews.it/category/eventi/", "citta": "Manfredonia", "gruppo": "Costa BAT e Gargano"},
]

DOMINI_FONTI_CONSENTITI = {
    urlparse(f["url"]).netloc.lower() for f in FONTI_EVENTI
}

FALLBACK_URL_PER_CITTA = {
    "Cerignola": "https://www.cerignolaviva.it/eventi/",
    "Foggia": "https://www.foggiatoday.it/eventi/",
    "Barletta": "https://www.barlettaviva.it/eventi/",
    "Trani": "https://www.traniviva.it/eventi/",
    "Bisceglie": "https://www.bisceglieviva.it/eventi/",
    "Andria": "https://www.andriaviva.it/eventi/",
    "Manfredonia": "https://www.manfredonianews.it/category/eventi/",
}

CATEGORIE_VALIDE = [
    "Locali & Serate",
    "Attività serali",
    "Musica & Concerti",
    "Sagre & Food",
    "Famiglie & Bambini",
    "Natura & Escursioni",
    "Attività diurne",
    "Luoghi da visitare",
    "Sport",
    "Altro"
]

MAPPA_CATEGORIE = {
    "serate & locali": "Locali & Serate",
    "locali & serate": "Locali & Serate",
    "serate": "Locali & Serate",
    "locali": "Locali & Serate",
    "club": "Locali & Serate",
    "aperitivo": "Locali & Serate",
    "dj set": "Locali & Serate",
    "attività serali": "Attività serali",
    "attivita serali": "Attività serali",
    "attività serale": "Attività serali",
    "attivita serale": "Attività serali",
    "serale": "Attività serali",
    "notturna": "Attività serali",
    "notturno": "Attività serali",
    "dopocena": "Attività serali",
    "apericena": "Attività serali",
    "musica": "Musica & Concerti",
    "musica & concerti": "Musica & Concerti",
    "concerti": "Musica & Concerti",
    "fiera": "Sagre & Food",
    "sagra": "Sagre & Food",
    "sagre & food": "Sagre & Food",
    "food": "Sagre & Food",
    "sport": "Sport",
    "famiglie": "Famiglie & Bambini",
    "famiglie & bambini": "Famiglie & Bambini",
    "bambini": "Famiglie & Bambini",
    "natura": "Natura & Escursioni",
    "escursioni": "Natura & Escursioni",
    "escursione": "Natura & Escursioni",
    "natura & escursioni": "Natura & Escursioni",
    "trekking": "Natura & Escursioni",
    "passeggiata": "Natura & Escursioni",
    "attività diurne": "Attività diurne",
    "attivita diurne": "Attività diurne",
    "luoghi da visitare": "Luoghi da visitare",
    "luogo da visitare": "Luoghi da visitare",
    "cultura & spettacoli": "Attività diurne",
    "cultura": "Attività diurne"
}

PAROLE_VIETATE = [
    "meteo", "libeccio", "venti forti", "pioggia", "allerta", "neve", "freddo",
    "questore", "sospende la licenza", "amianto", "pomodori", "agricoltura",
    "annullato", "annullamento", "cancellazione", "rinviato", "indagine di mercato",
    "arresto", "arresti", "rapina", "incidente", "incendio", "sequestro", "denuncia",
    "indagato", "tribunale", "carabinieri", "polizia", "guardia di finanza",
    "ha rischiato", "intervista", "commentato", "torna sulla", "consiglio comunale",
    "giunta", "sindaco", "elezioni", "partito", "sciopero", "ospedale", "asl",
    "furto", "truffa", "omicidio", "ferito", "morto", "lutto", "cordoglio",
    "convegno", "conferenza", "tavola rotonda", "dibattito", "seminario",
    "presentazione del libro", "presentazione libro", "sala consiliare"
]

PAROLE_PRIORITA_LINK = [
    "event", "serat", "seral", "notturn", "dopocena", "apericena", "concert",
    "dj", "live", "sagra", "mercatin", "festival", "festa", "musica", "club",
    "pub", "aperitiv", "lounge", "discotec", "night", "drink", "karaoke",
    "quiz", "famigl", "bambin", "natale", "escursion", "passeggiat", "trekking",
    "natura", "parco", "sport", "weekend"
]

STOPWORDS_IT = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una",
    "di", "a", "da", "in", "con", "su", "per", "tra", "fra",
    "del", "dello", "della", "dei", "degli", "delle",
    "al", "allo", "alla", "ai", "agli", "alle",
    "dal", "dallo", "dalla", "nel", "nello", "nella", "sul", "sulla",
    "e", "ed", "o", "che", "si", "fa", "evento", "serata", "appuntamento", "grande", "nuovo"
}

CITTA_TARGET_MAP = {
    "cerignola": "Cerignola",
    "stornara": "Stornara",
    "stornarella": "Stornarella",
    "san ferdinando": "San Ferdinando",
    "san ferdinando di puglia": "San Ferdinando",
    "orta nova": "Orta Nova",
    "trinitapoli": "Trinitapoli",
    "canosa": "Canosa",
    "canosa di puglia": "Canosa",
    "ordona": "Ordona",
    "carapelle": "Carapelle",
    "margherita di savoia": "Margherita di Savoia",
    "lavello": "Lavello",
    "ascoli satriano": "Ascoli Satriano",
    "zapponeta": "Zapponeta",
    "castelluccio dei sauri": "Castelluccio dei Sauri",
    "barletta": "Barletta",
    "candela": "Candela",
    "minervino": "Minervino Murge",
    "minervino murge": "Minervino Murge",
    "foggia": "Foggia",
    "melfi": "Melfi",
    "venosa": "Venosa",
    "deliceto": "Deliceto",
    "rapolla": "Rapolla",
    "andria": "Andria",
    "barile": "Barile",
    "palazzo san gervasio": "Palazzo San Gervasio",
    "rocchetta sant'antonio": "Rocchetta Sant'Antonio",
    "sant'agata di puglia": "Sant'Agata di Puglia",
    "manfredonia": "Manfredonia",
    "rionero in vulture": "Rionero in Vulture",
    "rionero": "Rionero in Vulture",
    "trani": "Trani",
    "bovino": "Bovino",
    "lacedonia": "Lacedonia",
    "monticchio": "Monticchio",
    "laghi di monticchio": "Monticchio",
    "spinazzola": "Spinazzola",
    "monteverde": "Monteverde",
    "montemilone": "Montemilone",
    "atella": "Atella",
    "troia": "Troia",
    "accadia": "Accadia",
    "aquilonia": "Aquilonia",
    "lucera": "Lucera",
    "bisceglie": "Bisceglie",
    "molfetta": "Molfetta",
    "san severo": "San Severo",
    "vieste": "Vieste",
    "mattinata": "Mattinata",
    "monte sant'angelo": "Monte Sant'Angelo"
}

CINTURA_25_KM = {
    "stornara", "stornarella", "san ferdinando", "orta nova", "trinitapoli",
    "canosa", "ordona", "carapelle", "margherita di savoia", "lavello", "ascoli satriano"
}

CINTURA_50_KM = {
    "zapponeta", "castelluccio dei sauri", "barletta", "candela", "minervino murge",
    "foggia", "melfi", "venosa", "deliceto", "rapolla", "andria", "barile",
    "palazzo san gervasio", "rocchetta sant'antonio", "sant'agata di puglia",
    "manfredonia", "rionero in vulture", "trani", "bovino", "lacedonia",
    "monticchio", "spinazzola", "monteverde", "montemilone", "atella",
    "troia", "accadia", "aquilonia", "lucera", "bisceglie"
}

# 4 Ricercatori Web mirati sulle aree e categorie non coperte dai giornali locali
AGENTI_RICERCA = [
    {
        "nome": "Agente 1 - Serate, Musica & Vita Notturna",
        "categoria_default": "Locali & Serate",
        "missione": (
            "Cerca eventi serali, concerti, DJ set, live music, cene spettacolo, apericena e feste "
            "nei locali in programma nei prossimi 30 giorni a Cerignola, Barletta, Trani, Andria, "
            "Foggia, Canosa di Puglia, Margherita di Savoia, Melfi e Venosa."
        )
    },
    {
        "nome": "Agente 2 - Vulture-Melfese e Subappennino Dauno (50 km)",
        "categoria_default": "Sagre & Food",
        "missione": (
            "Cerca eventi, sagre, feste di paese, mercatini, degustazioni e iniziative weekend in "
            "programma nei prossimi 45 giorni nei comuni attorno a Cerignola entro 50 km: Melfi, "
            "Venosa, Lavello, Rionero in Vulture, Laghi di Monticchio, Ascoli Satriano, Candela, "
            "Bovino, Deliceto, Sant'Agata di Puglia, Orta Nova, Stornara, Stornarella."
        )
    },
    {
        "nome": "Agente 3 - Famiglie, Bambini & Attività Diurne",
        "categoria_default": "Famiglie & Bambini",
        "missione": (
            "Cerca attività per famiglie e bambini, laboratori, animazione, spettacoli, mercatini "
            "diurni e iniziative weekend nei prossimi 45 giorni tra Cerignola, Foggia, Barletta, "
            "Andria, Trani, Canosa di Puglia, Manfredonia e Melfi."
        )
    },
    {
        "nome": "Agente 4 - Natura, Escursioni & Luoghi nel Weekend",
        "categoria_default": "Natura & Escursioni",
        "missione": (
            "Cerca escursioni guidate, trekking, passeggiate nella natura e visite speciali nei "
            "prossimi weekend entro 50 km da Cerignola: Laghi di Monticchio, Bosco dell'Incoronata, "
            "Saline di Margherita di Savoia, Parco dell'Ofanto, Castel del Monte, Castello di Melfi, "
            "Parco Archeologico di Canosa."
        )
    }
]


def priorita_cerchio_cerignola(citta):
    c = (citta or "").strip().lower()
    if c == "cerignola":
        return 0
    if c in CINTURA_25_KM:
        return 1
    if c in CINTURA_50_KM:
        return 2
    return 3


def oggi_iso():
    return datetime.now().strftime("%Y-%m-%d")


def limite_futuro_iso(giorni=180):
    return (datetime.now() + timedelta(days=giorni)).strftime("%Y-%m-%d")


def carica_json(percorso):
    try:
        with open(percorso, "r", encoding="utf-8") as f:
            dati = json.load(f)
            return dati if isinstance(dati, list) else []
    except Exception:
        return []


def normalizza_citta(ev, citta_default):
    citta_raw = (ev.get("citta") or "").strip().lower()
    luogo_raw = (ev.get("luogo") or "").strip().lower()
    titolo_raw = (ev.get("titolo") or "").strip().lower()
    desc_raw = (ev.get("descrizione") or "").strip().lower()

    for campo in (citta_raw, luogo_raw, titolo_raw, desc_raw):
        for chiave, nome_pulito in CITTA_TARGET_MAP.items():
            if re.search(rf"\b{re.escape(chiave)}\b", campo):
                return nome_pulito

    if citta_raw:
        return ev.get("citta").strip().title()
    return citta_default


def normalizza_categoria(cat_raw):
    chiave = (cat_raw or "").strip().lower()
    if chiave in MAPPA_CATEGORIE:
        return MAPPA_CATEGORIE[chiave]
    for valida in CATEGORIE_VALIDE:
        if chiave == valida.lower():
            return valida
    return "Altro"


def normalizza_fonte_url(url_raw, citta_pulita, urls_grounding_validi):
    candidato = (url_raw or "").strip()
    if candidato.startswith(("http://", "https://")):
        parsed = urlparse(candidato)
        dominio = parsed.netloc.lower()
        path = parsed.path.strip("/")
        if candidato in urls_grounding_validi:
            return candidato
        if dominio in DOMINI_FONTI_CONSENTITI:
            return candidato
        if dominio and path and "google.com" not in dominio and "example.com" not in dominio:
            return candidato
    return FALLBACK_URL_PER_CITTA.get(citta_pulita, "https://www.cerignolaviva.it/eventi/")


def pulisci_evento(ev, citta_fallback, urls_grounding_validi):
    citta = normalizza_citta(ev, citta_fallback)
    ev["citta"] = citta
    ev["categoria"] = normalizza_categoria(ev.get("categoria"))
    ev["titolo"] = re.sub(r"\s+", " ", (ev.get("titolo") or "")).strip()
    ev["luogo"] = re.sub(r"\s+", " ", (ev.get("luogo") or "")).strip()
    ev["descrizione"] = re.sub(r"\s+", " ", (ev.get("descrizione") or "")).strip()
    ev["dataTesto"] = re.sub(r"\s+", " ", (ev.get("dataTesto") or "")).strip()
    ev["dataInizio"] = (ev.get("dataInizio") or "").strip()
    ev["dataFine"] = (ev.get("dataFine") or ev["dataInizio"]).strip()
    ev["costo"] = (ev.get("costo") or "Da verificare").strip()
    ev["indirizzoMappa"] = (ev.get("indirizzoMappa") or f"{ev['luogo']}, {citta}").strip()
    ev["fonteUrl"] = normalizza_fonte_url(ev.get("fonteUrl"), citta, urls_grounding_validi)
    return ev


def evento_valido(ev):
    oggi = oggi_iso()
    max_data = limite_futuro_iso(180)
    data_inizio = (ev.get("dataInizio") or "").strip()
    data_fine = (ev.get("dataFine") or "").strip()
    data_testo = (ev.get("dataTesto") or "").lower()
    titolo = (ev.get("titolo") or "").strip()
    descrizione = (ev.get("descrizione") or "").strip()
    luogo = (ev.get("luogo") or "").strip().lower()

    if not titolo or not descrizione or len(titolo) < 4:
        return False
    if len(luogo) < 3 or "da confermare" in luogo or "da definire" in luogo:
        return False
    if "agg." in data_testo or "segnalato il" in data_testo:
        return False
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", data_fine) or data_fine < oggi or data_fine > max_data:
        return False
    if data_inizio and re.match(r"^\d{4}-\d{2}-\d{2}$", data_inizio):
        if data_inizio > data_fine or data_inizio > max_data:
            return False

    testo = f"{titolo} {descrizione} {data_testo}".lower()
    if any(p in testo for p in PAROLE_VIETATE):
        return False

    return True


def token_significativi(testo, citta=""):
    pulito = re.sub(r"[^a-z0-9àèéìòù\s]", " ", (testo or "").lower())
    citta_tokens = set(re.sub(r"[^a-z0-9àèéìòù\s]", " ", (citta or "").lower()).split())
    return {
        w for w in pulito.split()
        if len(w) >= 3 and w not in STOPWORDS_IT and w not in citta_tokens
    }


def date_compatibili(ev1, ev2):
    i1, f1 = ev1.get("dataInizio", ""), ev1.get("dataFine", "")
    i2, f2 = ev2.get("dataInizio", ""), ev2.get("dataFine", "")
    if not (i1 and f1 and i2 and f2):
        return i1 == i2
    if i1 == i2:
        return True
    try:
        d_i1 = datetime.strptime(i1, "%Y-%m-%d")
        d_f1 = datetime.strptime(f1, "%Y-%m-%d")
        d_i2 = datetime.strptime(i2, "%Y-%m-%d")
        d_f2 = datetime.strptime(f2, "%Y-%m-%d")
        if abs((d_i1 - d_i2).days) <= 1 and abs((d_f1 - d_f2).days) <= 1:
            return True
        return max(d_i1, d_i2) <= min(d_f1, d_f2)
    except Exception:
        return i1 == i2


def sono_duplicati(ev1, ev2):
    if (ev1.get("citta") or "").lower() != (ev2.get("citta") or "").lower():
        return False
    if not date_compatibili(ev1, ev2):
        return False

    citta = ev1.get("citta", "")
    t1 = re.sub(r"[^a-z0-9\s]", "", ev1.get("titolo", "").lower()).strip()
    t2 = re.sub(r"[^a-z0-9\s]", "", ev2.get("titolo", "").lower()).strip()

    if len(t1) >= 10 and len(t2) >= 10 and (t1 in t2 or t2 in t1):
        return True

    sim_titolo = SequenceMatcher(None, t1, t2).ratio()
    if sim_titolo >= 0.72:
        return True

    tok1 = token_significativi(ev1.get("titolo", ""), citta)
    tok2 = token_significativi(ev2.get("titolo", ""), citta)
    jaccard_titolo = 0.0
    if tok1 and tok2:
        intersezione = len(tok1 & tok2)
        jaccard_titolo = intersezione / len(tok1 | tok2)
        containment_titolo = intersezione / min(len(tok1), len(tok2))
        if jaccard_titolo >= 0.55 or (intersezione >= 2 and containment_titolo >= 0.80):
            return True

    l1 = re.sub(r"[^a-z0-9\s]", "", ev1.get("luogo", "").lower()).strip()
    l2 = re.sub(r"[^a-z0-9\s]", "", ev2.get("luogo", "").lower()).strip()
    sim_luogo = SequenceMatcher(None, l1, l2).ratio() if (l1 and l2) else 0.0
    if sim_luogo >= 0.75 and jaccard_titolo >= 0.35:
        return True

    return False


def is_url_articolo_specifico(url):
    if not url:
        return False
    path = urlparse(url).path.rstrip("/")
    return path not in ("", "/eventi", "/eventi/weekend", "/category/eventi")


def unisci_eventi(esistente, nuovo):
    risultato = dict(esistente)
    if len(nuovo.get("titolo", "")) > len(risultato.get("titolo", "")) and len(nuovo.get("titolo", "")) <= 85:
        risultato["titolo"] = nuovo["titolo"]
    if len(nuovo.get("descrizione", "")) > len(risultato.get("descrizione", "")):
        risultato["descrizione"] = nuovo["descrizione"]
    if risultato.get("costo") in ("", "Da verificare") and nuovo.get("costo") not in ("", "Da verificare"):
        risultato["costo"] = nuovo["costo"]
    if not is_url_articolo_specifico(risultato.get("fonteUrl")) and is_url_articolo_specifico(nuovo.get("fonteUrl")):
        risultato["fonteUrl"] = nuovo["fonteUrl"]
    if len(nuovo.get("luogo", "")) > len(risultato.get("luogo", "")):
        risultato["luogo"] = nuovo["luogo"]
        risultato["indirizzoMappa"] = nuovo.get("indirizzoMappa", risultato.get("indirizzoMappa", ""))
    return risultato


def estrai_json_ld(soup):
    risultati = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw = script.string or script.get_text()
            if not raw:
                continue
            dati = json.loads(raw)
            oggetti = dati if isinstance(dati, list) else [dati]
            for obj in oggetti:
                if not isinstance(obj, dict):
                    continue
                tipo = str(obj.get("@type", ""))
                if any(k in tipo for k in ["Event", "MusicEvent", "SocialEvent", "Festival"]):
                    nome = re.sub(r"\s+", " ", str(obj.get("name", ""))).strip()
                    inizio = str(obj.get("startDate", "")).strip()
                    fine = str(obj.get("endDate", "")).strip()
                    loc = obj.get("location", {})
                    luogo = loc.get("name", "") if isinstance(loc, dict) else str(loc)
                    ind = ""
                    if isinstance(loc, dict) and isinstance(loc.get("address"), dict):
                        addr = loc["address"]
                        ind = f"{addr.get('streetAddress', '')} {addr.get('addressLocality', '')}".strip()
                    if nome:
                        risultati.append(f"META_EVENTO: {nome} | Dal: {inizio} | Al: {fine} | Luogo: {luogo} ({ind})")
        except Exception:
            continue
    return risultati


def raccogli_testo_con_dettagli(url_indice, citta_fonte):
    testi = []
    try:
        r = requests.get(url_indice, headers=HEADERS, timeout=15)
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        meta_indice = estrai_json_ld(soup)
        if meta_indice:
            testi.append(f"[{citta_fonte}] FONTE_INDICE ({url_indice}) METADATI:\n" + "\n".join(meta_indice[:12]))

        for tag in soup(["script", "style", "nav", "footer", "aside", "form"]):
            tag.decompose()

        link_prioritari = []
        link_secondari = []
        righe_con_link = []
        dominio_base = "/".join(url_indice.split("/")[:3])
        anno_corrente = datetime.now().year
        anni_vecchi = [f"/{y}/" for y in range(2020, anno_corrente)]

        for a in soup.find_all("a", href=True):
            href = urljoin(url_indice, a["href"]).split("#")[0]
            if not href.startswith(dominio_base) or href.rstrip("/") == url_indice.rstrip("/"):
                continue
            low_href = href.lower()
            if any(x in low_href for x in ["/tag/", "/author/", "/page/", "login", "privacy", "cookie"] + anni_vecchi):
                continue

            titolo_link = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            if len(titolo_link) < 15:
                continue

            voce = f"- {titolo_link} [ARTICOLO: {href}]"
            if voce not in righe_con_link:
                righe_con_link.append(voce)

            if any(k in f"{low_href} {titolo_link.lower()}" for k in PAROLE_PRIORITA_LINK):
                if href not in link_prioritari:
                    link_prioritari.append(href)
            else:
                if href not in link_secondari:
                    link_secondari.append(href)

        if righe_con_link:
            testi.append(f"[{citta_fonte}] ELENCO_ARTICOLI:\n" + "\n".join(righe_con_link[:25]))

        link_candidati = (link_prioritari + link_secondari)[:10]
        for link in link_candidati:
            try:
                rp = requests.get(link, headers=HEADERS, timeout=10)
                rp.encoding = rp.apparent_encoding or "utf-8"
                sp = BeautifulSoup(rp.text, "html.parser")
                meta_scheda = estrai_json_ld(sp)
                for tag in sp(["script", "style", "nav", "footer", "aside", "form"]):
                    tag.decompose()
                titolo_p = sp.find(["h1", "h2"])
                titolo_str = re.sub(r"\s+", " ", titolo_p.get_text(" ", strip=True)) if titolo_p else ""
                corpo_p = []
                for p in sp.find_all(["p", "time", "li"]):
                    txt = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
                    if 15 <= len(txt) <= 320 and txt not in corpo_p:
                        corpo_p.append(txt)
                extra = f" [{' ; '.join(meta_scheda[:2])}]" if meta_scheda else ""
                if corpo_p or meta_scheda:
                    testi.append(f"[{citta_fonte}] SCHEDA ({link}): {titolo_str}{extra} | {' | '.join(corpo_p[:5])}")
            except Exception:
                continue
    except Exception as e:
        print("Errore lettura:", url_indice, e)

    return "\n\n".join(testi)[:9000]


def esegui_agente_ricerca(api_key, agente):
    oggi = oggi_iso()
    nome = agente["nome"]
    cat_def = agente["categoria_default"]
    missione = agente["missione"]

    prompt = f"""Sei '{nome}' di 'Che Si Fa Cerignola'. Oggi è {oggi}.
{missione}

Usa Google Search per raccogliere TUTTI gli eventi, feste, serate, spettacoli, escursioni, sagre e iniziative reali in corso oggi {oggi} o in programma nei prossimi giorni e weekend (entro 45 giorni).
REGOLE:
- Escludi eventi già conclusi prima di {oggi}, convegni politici/istituzionali e cronaca.
- Riporta ogni risultato trovato indicando: Titolo, Città esatta, Categoria ({cat_def}), Data e ora leggibile, Data inizio (YYYY-MM-DD), Data fine (YYYY-MM-DD), Luogo esatto, Costo, Descrizione breve (1 frase) e URL della fonte web.
"""

    host = "generativelanguage.googleapis.com"
    modelli = ["gemini-2.5-flash", "gemini-2.0-flash"]
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {
            "temperature": 0.1
        }
    }

    urls_grounding = set()

    for modello in modelli:
        endpoint = f"https://{host}/v1beta/models/{modello}:generateContent?key={api_key}"
        for tentativo in range(1, 3):
            try:
                resp = requests.post(endpoint, json=payload, timeout=55)
                if resp.status_code == 404:
                    break
                if resp.status_code == 429:
                    print(f"[{nome}] Quota 429 su {modello}, attendo 62s per reset finestra...")
                    time.sleep(62)
                    continue
                if resp.status_code in (500, 502, 503, 504):
                    if tentativo < 2:
                        time.sleep(15)
                        continue
                    break
                if resp.status_code != 200:
                    print(f"[{nome}] HTTP {resp.status_code} su {modello}: {resp.text[:200]}")
                    break

                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    break

                cand = candidates[0]
                parts = cand.get("content", {}).get("parts", [])
                testo = "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()

                grounding = cand.get("groundingMetadata", {})
                fonti_chunks = []
                for ch in grounding.get("groundingChunks", []):
                    web = ch.get("web", {})
                    uri = (web.get("uri") or "").strip()
                    title = (web.get("title") or "").strip()
                    if uri.startswith(("http://", "https://")):
                        urls_grounding.add(uri)
                        fonti_chunks.append(f"- {title}: {uri}" if title else f"- {uri}")

                if not testo:
                    return "", urls_grounding

                blocco = f"=== {nome} ===\n{testo}"
                if fonti_chunks:
                    blocco += "\nFONTI_VERIFICATE_GOOGLE:\n" + "\n".join(fonti_chunks[:12])
                print(f"[{nome}] OK ({len(urls_grounding)} fonti Google).")
                return blocco, urls_grounding

            except Exception as e:
                print(f"[{nome}] Errore ({modello}, tentativo {tentativo}/2):", e)
                if tentativo < 2:
                    time.sleep(12)

    return "", urls_grounding


def analizza_blocco_con_gemini(api_key, testo_grezzo, nome_blocco, citta_fallback):
    if not api_key or not testo_grezzo.strip():
        return []

    oggi = oggi_iso()
    prompt = f"""Sei il curatore di 'Che Si Fa Cerignola'. Oggi è {oggi}.
Analizza questi estratti per il blocco '{nome_blocco}' ed estrai TUTTI i veri eventi, serate e attività PRESENTI o FUTURI (in corso oggi {oggi} o in programma nei prossimi giorni/mesi) di svago, serate, socialità e tempo libero nel raggio di 50 km da Cerignola:
- "Locali & Serate": DJ set, club, lounge bar, pub, live music, aperitivi musicali;
- "Attività serali": cene spettacolo, apericena, quiz night, karaoke, mercatini serali, iniziative dopo cena;
- "Famiglie & Bambini": laboratori, animazione, spettacoli per bambini, fattorie didattiche;
- "Natura & Escursioni": trekking, passeggiate guidate, uscite nella natura;
- "Attività diurne": mercatini, degustazioni, visite ed esperienze diurne;
- "Luoghi da visitare": castelli, borghi, parchi e attrazioni visitabili nel weekend;
- "Musica & Concerti", "Sagre & Food", "Sport".

REGOLE RIGIDE:
1. Estrai TUTTI gli eventi validi presenti nel testo senza tralasciarne nessuno.
2. SCARTA eventi già conclusi prima di {oggi}.
3. SCARTA convegni politici/istituzionali, conferenze, dibattiti, seminari, presentazioni di libri, cronaca nera/giudiziaria, meteo e disservizi.
4. Per ogni evento riporta in "fonteUrl" l'URL specifico dell'articolo o della fonte web presente nel testo.

Restituisci SOLO un array JSON valido con oggetti aventi queste chiavi esatte:
- "citta": città specifica dell'evento oppure "{citta_fallback}"
- "categoria": scegli SOLO tra "Locali & Serate", "Attività serali", "Musica & Concerti", "Sagre & Food", "Famiglie & Bambini", "Natura & Escursioni", "Attività diurne", "Luoghi da visitare", "Sport", "Altro"
- "titolo": titolo pulito dell'evento o dell'attività
- "dataTesto": data e ora leggibile dell'evento (es. "Sab 28 Nov 2026 · Ore 22:00")
- "dataInizio": formato YYYY-MM-DD
- "dataFine": formato YYYY-MM-DD (deve essere >= "{oggi}")
- "luogo": nome esatto del locale, club, parco, piazza o indirizzo
- "indirizzoMappa": luogo + via/piazza + città per Google Maps
- "costo": es. "Ingresso libero", "15€ con drink", oppure "Da verificare"
- "descrizione": 1 frase chiara e invitante su cosa si fa
- "fonteUrl": URL esatto dell'articolo sorgente

TESTO DA ANALIZZARE:
{testo_grezzo}
"""

    host = "generativelanguage.googleapis.com"
    modelli = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    for modello in modelli:
        endpoint = f"https://{host}/v1beta/models/{modello}:generateContent?key={api_key}"
        for tentativo in range(1, 3):
            try:
                resp = requests.post(endpoint, json=payload, timeout=55)
                if resp.status_code == 404:
                    break
                if resp.status_code == 429:
                    print(f"[{nome_blocco}] Quota 429 su {modello}, attendo 62s...")
                    time.sleep(62)
                    continue
                if resp.status_code in (500, 502, 503, 504):
                    if tentativo < 2:
                        time.sleep(15)
                        continue
                    break

                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    break

                risposta = candidates[0]["content"]["parts"][0]["text"].strip()
                risposta = re.sub(r"^`{3}json\s*|`{3}$", "", risposta, flags=re.IGNORECASE).strip()
                eventi = json.loads(risposta)
                return eventi if isinstance(eventi, list) else []
            except Exception as e:
                print(f"[{nome_blocco}] Errore ({modello}, tentativo {tentativo}/2):", e)
                if tentativo < 2:
                    time.sleep(12)

    return []


# ==============================================================================
# PIPELINE IBRIDA: SCRAPING COMPLETO + RICERCATORI GOOGLE SEARCH
# ==============================================================================
api_key = os.environ.get("GEMINI_API_KEY", "").strip()
urls_grounding_totali = set()

# 1. Carica e consolida eventi validi già presenti in eventi.json
lista_consolidata = []
for ev_raw in carica_json("eventi.json"):
    ev = pulisci_evento(ev_raw, ev_raw.get("citta") or "Cerignola", urls_grounding_totali)
    if not evento_valido(ev):
        continue
    idx_dup = next((i for i, esist in enumerate(lista_consolidata) if sono_duplicati(esist, ev)), None)
    if idx_dup is None:
        lista_consolidata.append(ev)
    else:
        lista_consolidata[idx_dup] = unisci_eventi(lista_consolidata[idx_dup], ev)

nuovi_trovati = []

# 2. Analisi completa delle testate locali divise per blocco geografico
blocchi_locali = [
    ("Nord / Capitanata", "Cerignola", [f for f in FONTI_EVENTI if f["gruppo"] == "Nord / Capitanata"]),
    ("Costa BAT e Gargano", "Barletta", [f for f in FONTI_EVENTI if f["gruppo"] == "Costa BAT e Gargano"]),
]

for idx, (nome_blocco, citta_fallback, fonti_gruppo) in enumerate(blocchi_locali):
    testi_gruppo = []
    for fonte in fonti_gruppo:
        t = raccogli_testo_con_dettagli(fonte["url"], fonte["citta"])
        if t:
            testi_gruppo.append(t)
    testo_unito = "\n\n---\n\n".join(testi_gruppo)[:26000]
    if idx > 0 and testo_unito.strip():
        time.sleep(11)
    estratti = analizza_blocco_con_gemini(api_key, testo_unito, nome_blocco, citta_fallback)
    print(f"Blocco locale '{nome_blocco}': {len(estratti)} eventi estratti")
    for ev_raw in estratti:
        ev = pulisci_evento(ev_raw, citta_fallback, urls_grounding_totali)
        if evento_valido(ev):
            nuovi_trovati.append(ev)

# 3. Esecuzione dei 4 Ricercatori Specializzati con Google Search Grounding
raccolta_agenti = []
if api_key:
    for idx, agente in enumerate(AGENTI_RICERCA):
        time.sleep(11)
        blocco_agente, urls_trovati = esegui_agente_ricerca(api_key, agente)
        urls_grounding_totali.update(urls_trovati)
        if blocco_agente:
            raccolta_agenti.append(blocco_agente)

    testo_agenti = "\n\n---\n\n".join(raccolta_agenti)[:28000]
    if testo_agenti.strip():
        time.sleep(11)
        estratti_web = analizza_blocco_con_gemini(api_key, testo_agenti, "Ricercatori Web 50 km", "Cerignola")
        print(f"Blocco Ricercatori Web: {len(estratti_web)} eventi estratti")
        for ev_raw in estratti_web:
            ev = pulisci_evento(ev_raw, "Cerignola", urls_grounding_totali)
            if evento_valido(ev):
                nuovi_trovati.append(ev)

# 4. Merge e deduplicazione intelligente
aggiunti = 0
aggiornati = 0
for ev in nuovi_trovati:
    idx_dup = next((i for i, esist in enumerate(lista_consolidata) if sono_duplicati(esist, ev)), None)
    if idx_dup is None:
        lista_consolidata.append(ev)
        aggiunti += 1
    else:
        prima = lista_consolidata[idx_dup]
        dopo = unisci_eventi(prima, ev)
        if dopo != prima:
            lista_consolidata[idx_dup] = dopo
            aggiornati += 1

# 5. Ordinamento cronologico + cerchio concentrico da Cerignola (0 km -> 25 km -> 50 km)
lista_finale = sorted(
    lista_consolidata,
    key=lambda x: (
        x.get("dataInizio", "9999-12-31"),
        priorita_cerchio_cerignola(x.get("citta")),
        x.get("titolo", "").lower()
    )
)

with open("eventi.json", "w", encoding="utf-8") as f:
    json.dump(lista_finale, f, ensure_ascii=False, indent=2)

print(f"Aggiornamento completato. Aggiunti: {aggiunti}, Aggiornati: {aggiornati}. Totale in app: {len(lista_finale)}")
