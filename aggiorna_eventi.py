import os
import re
import json
import time
import requests
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urljoin, urlparse, quote_plus
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

GIORNI_ANTICIPO_MAX = 21

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9"
}

# 4 Feed RSS mirati sugli ultimi 10 giorni (zero teatro, zero convegni, zero cronaca)
FEED_RSS_MIRATI = [
    {
        "nome": "RSS Natale & Luminarie 50km",
        "query": '(luminarie OR "mercatini di natale" OR "villaggio di babbo natale" OR "pista di ghiaccio" OR "accensione albero" OR "eventi natalizi") (Cerignola OR Barletta OR Trani OR Andria OR Bisceglie OR Canosa OR "Margherita di Savoia" OR Foggia OR Manfredonia OR Melfi OR Venosa) when:10d',
        "blocco": "Natale_Feste"
    },
    {
        "nome": "RSS Sagre & Feste 50km",
        "query": '(sagra OR "festa in piazza" OR "street food" OR degustazione OR "festa patronale") (Cerignola OR Barletta OR Trani OR Andria OR Bisceglie OR Canosa OR "Orta Nova" OR Stornara OR Foggia OR Lucera OR Lavello OR Melfi OR Venosa) when:10d',
        "blocco": "Natale_Feste"
    },
    {
        "nome": "RSS Musica Live & Serate 50km",
        "query": '("musica live" OR "dj set" OR concerto OR "serata live" OR cabaret) (Cerignola OR Barletta OR Trani OR Andria OR Bisceglie OR "Margherita di Savoia" OR Foggia) -teatro -sinfonica -pianistico when:10d',
        "blocco": "Serate_Outdoor"
    },
    {
        "nome": "RSS Escursioni & Passeggiate 50km",
        "query": '(escursione OR trekking OR passeggiata OR "visita guidata") ("Margherita di Savoia" OR Monticchio OR "Castel del Monte" OR "Alta Murgia" OR Incoronata OR Cerignola OR Trani OR Barletta OR Canosa) when:10d',
        "blocco": "Serate_Outdoor"
    }
]

FONTI_WEB_POPOLARI = [
    {
        "nome": "Il Tacco di Bacco BAT",
        "url": "https://iltaccodibacco.it/barletta/",
        "tipo": "tacco_indice",
        "citta_fissa": "",
        "blocco": "Portali_Locali"
    },
    {
        "nome": "Il Tacco di Bacco Foggia",
        "url": "https://iltaccodibacco.it/foggia/",
        "tipo": "tacco_indice",
        "citta_fissa": "",
        "blocco": "Portali_Locali"
    },
    {
        "nome": "Eventbrite Cerignola",
        "url": "https://www.eventbrite.it/d/italy--cerignola/events/",
        "tipo": "eventbrite",
        "citta_fissa": "Cerignola",
        "blocco": "Portali_Locali"
    },
    {
        "nome": "Eventbrite BAT",
        "url": "https://www.eventbrite.it/d/italy--barletta-andria-trani/events/",
        "tipo": "eventbrite",
        "citta_fissa": "",
        "blocco": "Portali_Locali"
    },
    {
        "nome": "Eventbrite Foggia",
        "url": "https://www.eventbrite.it/d/italy--foggia/events/",
        "tipo": "eventbrite",
        "citta_fissa": "Foggia",
        "blocco": "Portali_Locali"
    }
]

# Poli movida e mete weekend sempre attive entro 50 km (mostrate sotto agli eventi datati)
METE_E_LOCALI = [
    {
        "tipoContenuto": "luogo",
        "citta": "Cerignola",
        "categoria": "Locali & Serate",
        "titolo": "Movida Corso Aldo Moro & Piazza Duomo",
        "dataTesto": "Ogni sera e weekend · Controlla storie IG",
        "dataInizio": "2026-01-01",
        "dataFine": "2099-12-31",
        "luogo": "Corso Aldo Moro / Piazza Duomo, Cerignola",
        "indirizzoMappa": "Corso Aldo Moro, Cerignola FG",
        "costo": "Ingresso libero / Consumazione",
        "descrizione": "Il cuore delle uscite serali a Cerignola tra cocktail bar, bistrot, pub e locali per aperitivo e dopocena.",
        "fonteUrl": "https://www.instagram.com/explore/tags/cerignola/"
    },
    {
        "tipoContenuto": "luogo",
        "citta": "Cerignola",
        "categoria": "Attività diurne",
        "titolo": "Piano delle Fosse Granarie — Passeggiata Storica",
        "dataTesto": "Sempre accessibile · Ideale tardo pomeriggio",
        "dataInizio": "2026-01-01",
        "dataFine": "2099-12-31",
        "luogo": "Piano San Rocco, Cerignola",
        "indirizzoMappa": "Piano delle Fosse Granarie, Cerignola FG",
        "costo": "Gratuito",
        "descrizione": "Area monumentale unica in Europa con oltre 600 fosse granarie, punto di ritrovo per passeggiate ed eventi all'aperto.",
        "fonteUrl": "https://www.instagram.com/explore/tags/pianodellefosse/"
    },
    {
        "tipoContenuto": "luogo",
        "citta": "Margherita di Savoia",
        "categoria": "Natura & Escursioni",
        "titolo": "Riserva delle Saline, Fenicotteri & Lungomare",
        "dataTesto": "Weekend e festivi (18 km da Cerignola)",
        "dataInizio": "2026-01-01",
        "dataFine": "2099-12-31",
        "luogo": "Lungomare Cristoforo Colombo / Zona Saline",
        "indirizzoMappa": "Riserva Naturale Salina di Margherita di Savoia",
        "costo": "Passeggiata gratuita / Visite su prenotazione",
        "descrizione": "Passeggiata sul lungomare e birdwatching dei fenicotteri rosa nella salina più grande d'Europa, con locali sul mare.",
        "fonteUrl": "https://www.instagram.com/explore/tags/margheritadisavoia/"
    },
    {
        "tipoContenuto": "luogo",
        "citta": "Canosa di Puglia",
        "categoria": "Locali & Serate",
        "titolo": "Centro Storico & Aperitivi a Canosa",
        "dataTesto": "Venerdì e Sabato sera (16 km da Cerignola)",
        "dataInizio": "2026-01-01",
        "dataFine": "2099-12-31",
        "luogo": "Corso San Sabino / Centro Storico, Canosa",
        "indirizzoMappa": "Corso San Sabino, Canosa di Puglia BT",
        "costo": "Ingresso libero / Consumazione",
        "descrizione": "Uscita rapida a 15 minuti da Cerignola tra lounge bar, birrerie e locali del centro storico.",
        "fonteUrl": "https://www.instagram.com/explore/tags/canosadipuglia/"
    },
    {
        "tipoContenuto": "luogo",
        "citta": "Barletta",
        "categoria": "Locali & Serate",
        "titolo": "Vicoli del Centro Storico & Castello Svevo",
        "dataTesto": "Giovedì, Venerdì e Sabato sera (28 km)",
        "dataInizio": "2026-01-01",
        "dataFine": "2099-12-31",
        "luogo": "Via Duomo / Corso Vittorio Emanuele, Barletta",
        "indirizzoMappa": "Via Duomo, Barletta BT",
        "costo": "Ingresso libero / Consumazione",
        "descrizione": "Concentrazione di pub, cocktail bar, vinoteche e musica dal vivo tra i vicoli intorno alla Cattedrale e al Castello.",
        "fonteUrl": "https://www.instagram.com/explore/tags/barletta/"
    },
    {
        "tipoContenuto": "luogo",
        "citta": "Trani",
        "categoria": "Locali & Serate",
        "titolo": "Porto Turistico di Trani & Cattedrale sul Mare",
        "dataTesto": "Ogni weekend · Polo movida BAT (36 km)",
        "dataInizio": "2026-01-01",
        "dataFine": "2099-12-31",
        "luogo": "Via Statuti Marittimi / Darsena, Trani",
        "indirizzoMappa": "Porto Turistico, Trani BT",
        "costo": "Ingresso libero / Consumazione",
        "descrizione": "Decine di lounge bar, cocktail bar, pub con musica live e ristoranti affacciati sul porto fino a tarda notte.",
        "fonteUrl": "https://www.instagram.com/explore/tags/portoditrani/"
    },
    {
        "tipoContenuto": "luogo",
        "citta": "Bisceglie",
        "categoria": "Locali & Serate",
        "titolo": "Porto Turistico & Waterfront Bisceglie",
        "dataTesto": "Venerdì e Sabato sera (43 km da Cerignola)",
        "dataInizio": "2026-01-01",
        "dataFine": "2099-12-31",
        "luogo": "Via Nazario Sauro / Porto, Bisceglie",
        "indirizzoMappa": "Via Nazario Sauro, Bisceglie BT",
        "costo": "Ingresso libero / Consumazione",
        "descrizione": "Passeggiata sul waterfront e locali per aperitivi, birre artigianali e serate con DJ set sul porto.",
        "fonteUrl": "https://www.instagram.com/explore/tags/bisceglie/"
    },
    {
        "tipoContenuto": "luogo",
        "citta": "Foggia",
        "categoria": "Locali & Serate",
        "titolo": "Isola Pedonale Corso Vittorio Emanuele & Piazza Giordano",
        "dataTesto": "Giovedì–Sabato sera (35 km da Cerignola)",
        "dataInizio": "2026-01-01",
        "dataFine": "2099-12-31",
        "luogo": "Corso Vittorio Emanuele II, Foggia",
        "indirizzoMappa": "Piazza Umberto Giordano, Foggia FG",
        "costo": "Ingresso libero / Consumazione",
        "descrizione": "Zona pedonale centrale con cocktail bar, birrerie, paninoteche e locali per il dopocena.",
        "fonteUrl": "https://www.instagram.com/explore/tags/foggia/"
    },
    {
        "tipoContenuto": "luogo",
        "citta": "Foggia",
        "categoria": "Natura & Escursioni",
        "titolo": "Parco Naturale Regionale Bosco dell'Incoronata",
        "dataTesto": "Sabato e Domenica mattina (28 km)",
        "dataInizio": "2026-01-01",
        "dataFine": "2099-12-31",
        "luogo": "Borgo Incoronata, Foggia",
        "indirizzoMappa": "Bosco dell'Incoronata, Foggia FG",
        "costo": "Gratuito",
        "descrizione": "Sentieri pianeggianti immersi nel bosco planiziale per camminate, corsa o domenica all'aria aperta.",
        "fonteUrl": "https://www.instagram.com/explore/tags/boscoincoronata/"
    },
    {
        "tipoContenuto": "luogo",
        "citta": "Monticchio",
        "categoria": "Natura & Escursioni",
        "titolo": "Laghi di Monticchio & Abbazia di San Michele",
        "dataTesto": "Gita domenica / weekend (48 km da Cerignola)",
        "dataInizio": "2026-01-01",
        "dataFine": "2099-12-31",
        "luogo": "Monticchio Laghi, Rionero in Vulture PZ",
        "indirizzoMappa": "Laghi di Monticchio, Rionero in Vulture PZ",
        "costo": "Gratuito",
        "descrizione": "Due laghi vulcanici nel verde del Vulture con sentieri trekking, passeggiata lungolago e ristoranti tipici.",
        "fonteUrl": "https://www.instagram.com/explore/tags/laghidimonticchio/"
    },
    {
        "tipoContenuto": "luogo",
        "citta": "Andria",
        "categoria": "Natura & Escursioni",
        "titolo": "Castel del Monte & Sentieri Alta Murgia",
        "dataTesto": "Weekend e festivi (45 km da Cerignola)",
        "dataInizio": "2026-01-01",
        "dataFine": "2099-12-31",
        "luogo": "Strada Statale 170, Castel del Monte, Andria",
        "indirizzoMappa": "Castel del Monte, Andria BT",
        "costo": "Esterno gratuito / Castello 10€",
        "descrizione": "Escursioni panoramici nei boschi dell'Alta Murgia e visita al maniero ottagonale patrimonio UNESCO.",
        "fonteUrl": "https://www.instagram.com/explore/tags/casteldelmonte/"
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

# Blocco totale di teatro di prosa, musica classica, convegni, parrocchie e cronaca
PAROLE_SCARTO = [
    "adblocker", "ci stai leggendo", "archivio", "evento si è già concluso",
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


def pulisci_evento(ev, urls_ok):
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
    limite_21gg = (datetime.now() + timedelta(days=GIORNI_ANTICIPO_MAX)).strftime("%Y-%m-%d")
    d1, d2 = ev.get("dataInizio", ""), ev.get("dataFine", "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d1) or not re.match(r"^\d{4}-\d{2}-\d{2}$", d2):
        return False, "formato_data"
    if d2 < oggi:
        return False, f"passato({d2})"
    if d1 > d2:
        return False, f"intervallo({d1}->{d2})"
    if d1 > limite_21gg:
        return False, f"oltre_{GIORNI_ANTICIPO_MAX}gg({d1})"

    titolo = ev.get("titolo", "")
    if len(titolo) < 5:
        return False, "titolo_corto"

    testo = f"{titolo} {ev.get('descrizione', '')} {ev.get('luogo', '')}"
    m = REGEX_SCARTO.search(testo)
    if m:
        return False, f"scarto({m.group(0)})"

    return True, "ok"


def pulisci_html_testo(sp, max_chars=7000):
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


def raccogli_rss_google_news(session, feed_cfg):
    schede = []
    urls_ok = set()
    nome = feed_cfg["nome"]
    rss_url = f"https://news.google.com/rss/search?q={quote_plus(feed_cfg['query'])}&hl=it&gl=IT&ceid=IT:it"
    soglia_pub = datetime.now(timezone.utc) - timedelta(days=12)

    try:
        r = session.get(rss_url, timeout=(5, 10))
        if r.status_code != 200:
            print(f"{nome}: HTTP {r.status_code}")
            return [], set()

        root = ET.fromstring(r.content)
        for item in root.findall(".//item")[:14]:
            titolo_raw = (item.findtext("title") or "").strip()
            titolo = re.sub(r"\s+-\s+[^-]+$", "", titolo_raw).strip()
            link = (item.findtext("link") or "").strip()
            pub_raw = (item.findtext("pubDate") or "").strip()
            desc_html = item.findtext("description") or ""
            desc = re.sub(r"\s+", " ", BeautifulSoup(desc_html, "html.parser").get_text(" ", strip=True)).strip()

            if len(titolo) < 8 or REGEX_SCARTO.search(f"{titolo} {desc}"):
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

            if link:
                urls_ok.add(link)
            schede.append(
                f"[{nome}] PUBBLICATO IL: {pub_str} | URL: {link}\n"
                f"TITOLO NOTIZIA: {titolo}\n"
                f"ESTRATTO: {desc[:300]}"
            )
        print(f"{nome}: {len(schede)} notizie recenti raccolte")
    except Exception as e:
        print(f"Errore {nome}: {str(e)[:80]}")

    return schede, urls_ok


def raccogli_fonte_web(session, fonte):
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

        if tipo == "eventbrite":
            eventi_ld = []
            for sc in soup.find_all("script", type="application/ld+json"):
                try:
                    dati = json.loads(sc.string or "")
                    estrai_eventi_jsonld(dati, eventi_ld)
                except Exception:
                    continue

            visti_url = set()
            for ev in eventi_ld[:12]:
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
                desc = re.sub(r"\s+", " ", str(ev.get("description", ""))).strip()[:240]

                prefisso = f"CITTÀ FISSA: {c_fissa} | " if c_fissa else ""
                schede.append(
                    f"[{nome}] {prefisso}URL: {ev_url}\n"
                    f"TITOLO: {titolo}\n"
                    f"DATA INIZIO: {d_ini} | DATA FINE: {d_fin}\n"
                    f"LUOGO: {luogo_nome} ({localita})\n"
                    f"DESCRIZIONE: {desc}"
                )
            print(f"{nome}: {len(schede)} schede")
            return schede, urls_ok

        # Il Tacco di Bacco (solo musica live, sagre, serate; scarta teatro)
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
                corpo = pulisci_html_testo(sp, max_chars=1000)
                if len(corpo) < 50 or REGEX_SCARTO.search(corpo[:350]):
                    continue
                urls_ok.add(link)
                schede.append(f"[{nome}] URL: {link}\nTITOLO: {titolo}\nDETTAGLI: {corpo}")
            except Exception:
                continue

        print(f"{nome}: {len(schede)} schede popolari")
    except Exception as e:
        print(f"Errore {nome}: {str(e)[:80]}")

    return schede, urls_ok


def estrai_con_gemini(api_key, testo_blocco, nome_blocco):
    if not api_key or not testo_blocco.strip():
        return []
    oggi = oggi_iso()
    limite_21gg = (datetime.now() + timedelta(days=GIORNI_ANTICIPO_MAX)).strftime("%Y-%m-%d")
    giorno_sett = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"][datetime.now().weekday()]

    modelli = ["gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.5-flash-lite"]

    prompt = (
        f"Curatore di 'Che Si Fa Cerignola', app per uscire e divertirsi a Cerignola e dintorni entro 50 km.\n"
        f"Oggi è {giorno_sett} {oggi}. Estrai SOLO veri eventi popolari di svago in corso o in arrivo tra '{oggi}' e '{limite_21gg}'.\n"
        "REGOLE TASSATIVE:\n"
        "- Includi SOLO: luminarie e accensioni natalizie, mercatini/villaggi di Natale, piste di ghiaccio, sagre, feste in piazza, street food, concerti live nei pub/piazze, DJ set, serate nei locali, escursioni/trekking/passeggiate.\n"
        "- ESCLUDI ASSOLUTAMENTE: spettacoli teatrali, prosa, recital pianistici, concerti sinfonici, convegni, seminari universitari, incontri parrocchiali, fiere sposi, anniversari di centri commerciali, mostre fotografiche e cronaca.\n"
        "- Se una notizia parla di luminarie o villaggi natalizi già accesi/aperti senza una data singola, usa '{oggi}' come dataInizio e la data di chiusura (o '{limite_21gg}') come dataFine.\n"
        "- Comuni ammessi (entro 50 km): Cerignola, Stornara, Stornarella, Orta Nova, San Ferdinando di Puglia, Trinitapoli, Canosa di Puglia, Ordona, Carapelle, Margherita di Savoia, Lavello, Ascoli Satriano, Zapponeta, Castelluccio dei Sauri, Barletta, Candela, Minervino Murge, Foggia, Melfi, Venosa, Deliceto, Rapolla, Andria, Barile, Palazzo San Gervasio, Rocchetta Sant'Antonio, Manfredonia, Rionero in Vulture, Trani, Bovino, Spinazzola, Troia, Lucera, Bisceglie, Monticchio.\n"
        "- Usa solo categorie tra: 'Musica & Concerti', 'Locali & Serate', 'Sagre & Food', 'Famiglie & Bambini', 'Natura & Escursioni', 'Attività diurne'.\n"
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
    t1 = re.sub(r"[^a-z0-9\s]", "", a.get("titolo", "").lower())
    t2 = re.sub(r"[^a-z0-9\s]", "", b.get("titolo", "").lower())
    return SequenceMatcher(None, t1, t2).ratio() >= 0.68


# ==============================================================================
# ESECUZIONE PRINCIPALE (EVENTI POPOLARI ENTRO 21GG + METE/LOCALI MOVIDA 50KM)
# ==============================================================================
t_start = time.time()
api_key = os.environ.get("GEMINI_API_KEY", "").strip()
urls_validi = set()

session = requests.Session()
session.headers.update(HEADERS)

blocchi = {"Natale_Feste": [], "Serate_Outdoor": [], "Portali_Locali": []}

for feed in FEED_RSS_MIRATI:
    sc, u_ok = raccogli_rss_google_news(session, feed)
    urls_validi.update(u_ok)
    blocchi[feed["blocco"]].extend(sc)

for fonte in FONTI_WEB_POPOLARI:
    sc, u_ok = raccogli_fonte_web(session, fonte)
    urls_validi.update(u_ok)
    blocchi[fonte["blocco"]].extend(sc)

consolidati = []

# 1) Eventi manuali da eventi_manuali.json (priorità massima)
try:
    with open("eventi_manuali.json", "r", encoding="utf-8") as f:
        manuali = json.load(f)
    if isinstance(manuali, list):
        for raw_m in manuali:
            ev_m = pulisci_evento(raw_m, urls_validi)
            ok, _ = verifica_evento(ev_m)
            if ok and not any(sono_duplicati(x, ev_m) for x in consolidati):
                consolidati.append(ev_m)
except Exception:
    pass

# 2) Eventi estratti dai feed RSS e portali (zero teatro/classica)
for idx, (nome_b, lista_sc) in enumerate(blocchi.items()):
    if not lista_sc:
        continue
    if idx > 0:
        time.sleep(1)
    testo_unito = "\n\n===\n\n".join(lista_sc)[:18000]
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
    print(f"[{nome_b}] Validati popolari: {validati_b}")

# Prima tutti gli eventi datati in ordine cronologico, poi le mete/locali movida
tutti_eventi = sorted(
    consolidati,
    key=lambda x: (x.get("dataInizio", "9999-12-31"), priorita_km(x.get("citta")), x.get("titolo", "").lower())
)

lista_finale = tutti_eventi + METE_E_LOCALI

with open("eventi.json", "w", encoding="utf-8") as f:
    json.dump(lista_finale, f, ensure_ascii=False, indent=2)

report = {
    "aggiornatoAl": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "eventiDatati21gg": len(tutti_eventi),
    "meteELocali": len(METE_E_LOCALI),
    "totaleContenuti": len(lista_finale),
    "topComuni": dict(Counter(e["citta"] for e in lista_finale).most_common(15))
}
with open("report_copertura.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"Fine: {len(tutti_eventi)} eventi + {len(METE_E_LOCALI)} mete (in {int(time.time() - t_start)}s)")
