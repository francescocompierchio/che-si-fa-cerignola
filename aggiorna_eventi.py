import os
import re
import json
import time
import requests
from urllib.parse import urljoin
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

PAROLE_VIETATE = [
    "meteo", "libeccio", "venti forti", "pioggia", "allerta", "neve", "freddo",
    "questore", "sospende la licenza", "amianto", "pomodori", "agricoltura",
    "annullato", "annullamento", "cancellazione", "rinviato", "indagine di mercato",
    "arresto", "arresti", "rapina", "incidente", "incendio", "sequestro",
    "denuncia", "indagato", "tribunale", "carabinieri", "polizia", "guardia di finanza",
    "ha rischiato", "intervista", "commentato", "torna sulla", "consiglio comunale",
    "giunta", "sindaco", "elezioni", "partito", "sciopero", "ospedale", "asl",
    "furto", "truffa", "omicidio", "ferito", "morto", "lutto", "cordoglio"
]

PAROLE_PRIORITA_LINK = [
    "event", "serat", "concert", "dj", "live", "teatr", "spettacol",
    "mostr", "sagra", "mercatin", "festival", "festa", "musica", "club", "pub",
    "aperitiv", "lounge", "discotec", "night", "drink", "famigl", "bambin",
    "natale", "arte", "cultur", "weekend"
]

CITTA_TARGET_MAP = {
    "cerignola": "Cerignola",
    "canosa": "Canosa",
    "canosa di puglia": "Canosa",
    "san ferdinando": "San Ferdinando",
    "san ferdinando di puglia": "San Ferdinando",
    "trinitapoli": "Trinitapoli",
    "margherita di savoia": "Margherita di Savoia",
    "orta nova": "Orta Nova",
    "stornara": "Stornara",
    "stornarella": "Stornarella",
    "carapelle": "Carapelle",
    "ascoli satriano": "Ascoli Satriano",
    "candela": "Candela",
    "rocchetta sant'antonio": "Rocchetta Sant'Antonio",
    "lavello": "Lavello",
    "melfi": "Melfi",
    "foggia": "Foggia",
    "barletta": "Barletta",
    "trani": "Trani",
    "manfredonia": "Manfredonia",
    "san severo": "San Severo",
    "lucera": "Lucera",
    "vieste": "Vieste",
    "mattinata": "Mattinata",
    "monte sant'angelo": "Monte Sant'Angelo",
    "bisceglie": "Bisceglie",
    "molfetta": "Molfetta",
    "andria": "Andria"
}


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


def evento_valido(ev):
    oggi = oggi_iso()
    max_data = limite_futuro_iso(180)
    data_inizio = (ev.get("dataInizio") or "").strip()
    data_fine = (ev.get("dataFine") or "").strip()
    data_testo = (ev.get("dataTesto") or "").lower()
    titolo = (ev.get("titolo") or "").strip()
    descrizione = (ev.get("descrizione") or "").strip()

    if not titolo or not descrizione or len(titolo) < 4:
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
            testi.append(f"[{citta_fonte}] METADATI:\n" + "\n".join(meta_indice[:12]))

        for tag in soup(["script", "style", "nav", "footer", "aside", "form"]):
            tag.decompose()

        righe_indice = []
        for el in soup.find_all(["article", "h2", "h3", "h4", "time"]):
            t = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
            if 15 <= len(t) <= 300 and t not in righe_indice:
                righe_indice.append(t)
        if righe_indice:
            testi.append(f"[{citta_fonte}] ELENCO:\n" + "\n".join(righe_indice[:25]))

        link_prioritari = []
        link_secondari = []
        dominio_base = "/".join(url_indice.split("/")[:3])
        anno_corrente = datetime.now().year
        anni_vecchi = [f"/{y}/" for y in range(2020, anno_corrente)]

        for a in soup.find_all("a", href=True):
            href = urljoin(url_indice, a["href"]).split("#")[0]
            if not href.startswith(dominio_base):
                continue
            if href.rstrip("/") == url_indice.rstrip("/"):
                continue
            low_href = href.lower()
            if any(x in low_href for x in ["/tag/", "/author/", "/page/", "login", "privacy", "cookie"] + anni_vecchi):
                continue

            titolo_link = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            if len(titolo_link) < 15:
                continue

            testo_check = f"{low_href} {titolo_link.lower()}"
            if any(k in testo_check for k in PAROLE_PRIORITA_LINK):
                if href not in link_prioritari:
                    link_prioritari.append(href)
            else:
                if href not in link_secondari:
                    link_secondari.append(href)

        link_candidati = (link_prioritari + link_secondari)[:7]

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

                extra_meta = f" [{' ; '.join(meta_scheda[:2])}]" if meta_scheda else ""
                if corpo_p or meta_scheda:
                    testi.append(f"[{citta_fonte}] SCHEDA ({link}): {titolo_str}{extra_meta} | {' | '.join(corpo_p[:5])}")
            except Exception:
                continue

    except Exception as e:
        print("Errore lettura:", url_indice, e)

    return "\n\n".join(testi)[:7500]


def analizza_blocco_con_gemini(testo_grezzo, nome_blocco, citta_fallback):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or not testo_grezzo.strip():
        print(f"API key mancante o testo vuoto per blocco {nome_blocco}")
        return []

    oggi = oggi_iso()
    prompt = f"""Sei il curatore dell'app 'Che Si Fa Cerignola'. Oggi è {oggi}.
Analizza questi estratti, metadati e schede per il blocco '{nome_blocco}' ed estrai TUTTI i veri eventi PRESENTI o FUTURI (in corso oggi {oggi} o in programma nei prossimi giorni/mesi) che siano piacevoli, sociali o di intrattenimento, includendo Cerignola, tutti i paesi limitrofi (Canosa, San Ferdinando, Trinitapoli, Margherita di Savoia, Orta Nova, Stornara, Stornarella, Carapelle, Ascoli Satriano) e le città di riferimento (Foggia, Barletta, Trani, Bisceglie, Andria, Manfredonia):
- PRIORITÀ MASSIMA a serate nei locali, lounge bar, pub, club, aperitivi, DJ set, live music, cene spettacolo e appuntamenti per giovani
- eventi per famiglie e bambini, feste, mercatini, fiere, sagre, mostre, spettacoli teatrali e iniziative culturali piacevoli.

REGOLE RIGIDE DI ESCLUSIONE:
1. SCARTA categoricamente eventi già conclusi prima di {oggi}.
2. SCARTA categoricamente cronaca nera, giudiziaria, politica, bandi/comunicati istituzionali, meteo, incidenti, disservizi o notizie generiche.
3. Includi SOLO appuntamenti reali con data presente/futura e luogo identificabile.

Restituisci SOLO un array JSON valido con oggetti aventi queste chiavi esatte:
- "citta": città specifica dell'evento (es. "Cerignola", "Canosa", "San Ferdinando", "Trinitapoli", "Margherita di Savoia", "Orta Nova", "Stornara", "Stornarella", "Carapelle", "Ascoli Satriano", "Foggia", "Barletta", "Trani", "Bisceglie", "Andria", "Manfredonia") oppure "{citta_fallback}"
- "categoria": scegli SOLO tra "Serate & Locali", "Musica", "Spettacolo", "Fiera", "Famiglie", "Incontro"
- "titolo": titolo pulito dell'evento o della serata
- "dataTesto": data e ora leggibile dell'evento (es. "Sab 22 Nov 2026 - 22:00" oppure "6 Dic 2026")
- "dataInizio": formato YYYY-MM-DD
- "dataFine": formato YYYY-MM-DD (deve essere >= "{oggi}")
- "luogo": nome esatto del locale, club, teatro, piazza o indirizzo
- "indirizzoMappa": luogo + via/piazza + città per Google Maps
- "costo": es. "Ingresso libero", "A pagamento", oppure "Da verificare"
- "descrizione": 1 frase chiara e invitante su cosa si fa alla serata o all'evento

TESTO DA ANALIZZARE:
{testo_grezzo}
"""

    host = "generativelanguage.googleapis.com"
    modello = "gemini-3.8-flash"
    endpoint = f"https://{host}/v1beta/models/{modello}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    for tentativo in range(1, 4):
        try:
            resp = requests.post(endpoint, json=payload, timeout=50)
            if resp.status_code == 429:
                print(f"Quota giornaliera Gemini esaurita (429) per {nome_blocco}. Attesa reset.")
                return []
            if resp.status_code in (500, 502, 503, 504):
                print(f"Server Gemini occupato ({resp.status_code}) per {nome_blocco}, tentativo {tentativo}/3...")
                if tentativo < 3:
                    time.sleep(20 * tentativo)
                    continue
                return []

            data = resp.json()
            if "candidates" not in data:
                print(f"Risposta non valida da Gemini per {nome_blocco}:", data)
                return []

            risposta = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            risposta = re.sub(r"^`{3}json\s*|`{3}$", "", risposta, flags=re.IGNORECASE).strip()
            eventi = json.loads(risposta)
            return eventi if isinstance(eventi, list) else []
        except Exception as e:
            print(f"Errore Gemini ({nome_blocco}, tentativo {tentativo}/3):", e)
            if tentativo < 3:
                time.sleep(15)

    return []


vecchi_eventi = []
for ev in carica_json("eventi.json"):
    ev["citta"] = normalizza_citta(ev, ev.get("citta") or "Cerignola")
    if evento_valido(ev):
        vecchi_eventi.append(ev)

blocchi = [
    ("Nord / Capitanata", "Cerignola", [f for f in FONTI_EVENTI if f["gruppo"] == "Nord / Capitanata"]),
    ("Costa BAT e Gargano", "Barletta", [f for f in FONTI_EVENTI if f["gruppo"] == "Costa BAT e Gargano"]),
]

nuovi_trovati = []
for idx, (nome_blocco, citta_fallback, fonti_gruppo) in enumerate(blocchi):
    testi_gruppo = []
    for fonte in fonti_gruppo:
        t = raccogli_testo_con_dettagli(fonte["url"], fonte["citta"])
        if t:
            testi_gruppo.append(t)
    testo_unito = "\n\n---\n\n".join(testi_gruppo)[:24000]

    if idx > 0 and testo_unito.strip():
        time.sleep(15)

    estratti = analizza_blocco_con_gemini(testo_unito, nome_blocco, citta_fallback)
    print(f"Blocco '{nome_blocco}': {len(estratti)} eventi estratti")
    for ev in estratti:
        ev["citta"] = normalizza_citta(ev, citta_fallback)
        nuovi_trovati.append(ev)

nuovi_validi = [ev for ev in nuovi_trovati if evento_valido(ev)]

mappa = {}
for ev in vecchi_eventi:
    titolo_k = re.sub(r"[^a-z0-9]", "", ev.get("titolo", "").lower())[:35]
    data_k = (ev.get("dataInizio") or "").strip()
    k = f"{titolo_k}_{data_k}"
    if titolo_k:
        mappa[k] = ev

aggiunti = 0
aggiornati = 0
for ev in nuovi_validi:
    titolo_k = re.sub(r"[^a-z0-9]", "", ev.get("titolo", "").lower())[:35]
    data_k = (ev.get("dataInizio") or "").strip()
    k = f"{titolo_k}_{data_k}"
    if not titolo_k:
        continue
    if k not in mappa:
        mappa[k] = ev
        aggiunti += 1
    else:
        esistente = mappa[k]
        if esistente.get("costo") == "Da verificare" and ev.get("costo") and ev.get("costo") != "Da verificare":
            mappa[k] = ev
            aggiornati += 1

lista_finale = sorted(mappa.values(), key=lambda x: x.get("dataInizio", "9999-12-31"))

with open("eventi.json", "w", encoding="utf-8") as f:
    json.dump(lista_finale, f, ensure_ascii=False, indent=2)

print(f"Aggiornamento completato. Aggiunti: {aggiunti}, Aggiornati: {aggiornati}. Totale in app: {len(lista_finale)}")
