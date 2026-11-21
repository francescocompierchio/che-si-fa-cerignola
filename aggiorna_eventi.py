import os
import re
import json
import time
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9"
}

FONTI_EVENTI = [
    {"url": "https://www.viverecerignola.it/", "citta": "Cerignola", "gruppo": "Nord / Capitanata"},
    {"url": "https://www.cerignolaviva.it/eventi/", "citta": "Cerignola", "gruppo": "Nord / Capitanata"},
    {"url": "https://www.foggiatoday.it/eventi/", "citta": "Foggia", "gruppo": "Nord / Capitanata"},
    {"url": "https://www.barlettaviva.it/eventi/", "citta": "Barletta", "gruppo": "Costa BAT e Gargano"},
    {"url": "https://www.traniviva.it/eventi/", "citta": "Trani", "gruppo": "Costa BAT e Gargano"},
    {"url": "https://www.manfredonianews.it/category/eventi/", "citta": "Manfredonia", "gruppo": "Costa BAT e Gargano"},
]

MESI_PASSATI_2026 = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre"
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
    "aperitiv", "famigl", "bambin", "natale", "arte", "cultur"
]

CITTA_TARGET_MAP = {
    "cerignola": "Cerignola",
    "foggia": "Foggia",
    "barletta": "Barletta",
    "trani": "Trani",
    "manfredonia": "Manfredonia",
    "canosa": "Canosa",
    "san ferdinando": "San Ferdinando",
    "san severo": "San Severo",
    "margherita di savoia": "Margherita di Savoia",
    "trinitapoli": "Trinitapoli",
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
    data_inizio = (ev.get("dataInizio") or "").strip()
    data_fine = (ev.get("dataFine") or "").strip()
    data_testo = (ev.get("dataTesto") or "").lower()
    titolo = (ev.get("titolo") or "").strip()
    descrizione = (ev.get("descrizione") or "").strip()

    if not titolo or not descrizione:
        return False

    if "agg." in data_testo or "segnalato il" in data_testo:
        return False

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", data_fine) or data_fine < oggi:
        return False

    if data_inizio and re.match(r"^\d{4}-\d{2}-\d{2}$", data_inizio) and data_inizio > data_fine:
        return False

    testo = f"{titolo} {descrizione} {data_testo}".lower()

    if any(p in testo for p in PAROLE_VIETATE):
        return False

    if any(m in testo for m in MESI_PASSATI_2026) and not any(f in testo for f in ["novembre", "dicembre", "2027"]):
        return False

    return True


def raccogli_testo_con_dettagli(url_indice, citta_fonte):
    testi = []
    try:
        r = requests.get(url_indice, headers=HEADERS, timeout=20)
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

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

        for a in soup.find_all("a", href=True):
            href = urljoin(url_indice, a["href"]).split("#")[0]
            if not href.startswith(dominio_base):
                continue
            if href.rstrip("/") == url_indice.rstrip("/"):
                continue
            low_href = href.lower()
            if any(x in low_href for x in [
                "/tag/", "/author/", "/page/", "login", "privacy", "cookie",
                "/2024/", "/2025/", "/2026/01/", "/2026/02/", "/2026/03/",
                "/2026/04/", "/2026/05/", "/2026/06/", "/2026/07/",
                "/2026/08/", "/2026/09/", "/2026/10/"
            ]):
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

        link_candidati = (link_prioritari + link_secondari)[:8]

        for link in link_candidati:
            try:
                rp = requests.get(link, headers=HEADERS, timeout=15)
                rp.encoding = rp.apparent_encoding or "utf-8"
                sp = BeautifulSoup(rp.text, "html.parser")
                for tag in sp(["script", "style", "nav", "footer", "aside", "form"]):
                    tag.decompose()
                titolo_p = sp.find(["h1", "h2"])
                titolo_str = re.sub(r"\s+", " ", titolo_p.get_text(" ", strip=True)) if titolo_p else ""
                corpo_p = []
                for p in sp.find_all(["p", "time", "li"]):
                    txt = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
                    if 15 <= len(txt) <= 320 and txt not in corpo_p:
                        corpo_p.append(txt)
                if corpo_p:
                    testi.append(f"[{citta_fonte}] SCHEDA ({link}): {titolo_str} | {' | '.join(corpo_p[:6])}")
            except Exception:
                continue

    except Exception as e:
        print("Errore lettura:", url_indice, e)

    return "\n\n".join(testi)[:8500]


def analizza_blocco_con_gemini(testo_grezzo, nome_blocco, citta_fallback):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or not testo_grezzo.strip():
        print(f"API key mancante o testo vuoto per blocco {nome_blocco}")
        return []

    oggi = oggi_iso()
    prompt = f"""Sei il curatore dell'app 'Che Si Fa Cerignola'. Oggi è {oggi}.
Analizza questi estratti e schede per il blocco '{nome_blocco}' e includi SOLO veri eventi PRESENTI o FUTURI (in corso oggi {oggi} o in programma nei giorni/mesi successivi) che siano belli, piacevoli e coinvolgenti:
- serate nei locali, aperitivi, DJ set, concerti, musica live e divertimento per giovani
- eventi per famiglie e bambini, feste, mercatini, fiere, sagre, mostre, spettacoli teatrali e iniziative culturali piacevoli.

REGOLE RIGIDE DI ESCLUSIONE:
1. SCARTA categoricamente eventi già passati o conclusi prima di {oggi} (o riferiti solo a mesi passati).
2. SCARTA categoricamente cronaca nera, cronaca giudiziaria, politica, amministrazione/bandi/comunicati istituzionali, meteo, incidenti, disservizi o notizie generiche.
3. Includi SOLO appuntamenti reali con data presente/future e luogo identificabile.

Restituisci SOLO un array JSON valido (senza ```json) con oggetti aventi queste chiavi esatte:
- "citta": città specifica dell'evento (es. "Cerignola", "Foggia", "Barletta", "Trani", "Manfredonia", "Canosa") oppure "{citta_fallback}"
- "categoria": scegli SOLO tra "Serate & Locali", "Musica", "Spettacolo", "Fiera", "Famiglie", "Incontro"
- "titolo": titolo pulito dell'evento o della serata
- "dataTesto": data e ora dell'evento (es. "22 Nov 2026 - 21:30" oppure "6 Dic 2026")
- "dataInizio": formato YYYY-MM-DD
- "dataFine": formato YYYY-MM-DD (deve essere >= "{oggi}")
- "luogo": nome del locale, teatro, piazza o indirizzo
- "indirizzoMappa": luogo + città per Google Maps
- "costo": es. "Ingresso libero", "A pagamento", oppure "Da verificare"
- "descrizione": 1 frase chiara e invitante su cosa si fa all'evento/serata

TESTO DA ANALIZZARE:
{testo_grezzo}
"""

    host = "generativelanguage.googleapis.com"
    modello = "gemini-3.8-flash"
    endpoint = f"https://{host}/v1beta/models/{modello}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1}
    }

    try:
        resp = requests.post(endpoint, json=payload, timeout=45)
        data = resp.json()
        if "candidates" not in data:
            print(f"Risposta non valida da Gemini per {nome_blocco}:", data)
            return []
        risposta = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        risposta = re.sub(r"^```json\s*|\s*```$", "", risposta, flags=re.IGNORECASE).strip()
        eventi = json.loads(risposta)
        return eventi if isinstance(eventi, list) else []
    except Exception as e:
        print(f"Errore Gemini ({nome_blocco}):", e)
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
    testo_unito = "\n\n---\n\n".join(testi_gruppo)[:16000]

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
    k = re.sub(r"[^a-z0-9]", "", ev.get("titolo", "").lower())[:45]
    if k:
        mappa[k] = ev

aggiunti = 0
for ev in nuovi_validi:
    k = re.sub(r"[^a-z0-9]", "", ev.get("titolo", "").lower())[:45]
    if k and k not in mappa:
        mappa[k] = ev
        aggiunti += 1

lista_finale = sorted(mappa.values(), key=lambda x: x.get("dataInizio", "9999-12-31"))

with open("eventi.json", "w", encoding="utf-8") as f:
    json.dump(lista_finale, f, ensure_ascii=False, indent=2)

print(f"Aggiornamento completato. Aggiunti {aggiunti} eventi reali. Totale in app: {len(lista_finale)}")
