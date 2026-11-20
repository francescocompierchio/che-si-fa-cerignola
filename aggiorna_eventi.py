import os
import re
import json
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9"
}

FONTI_EVENTI = [
    {"url": "https://www.viverecerignola.it/", "citta": "Cerignola"},
    {"url": "https://www.cerignolaviva.it/eventi/", "citta": "Cerignola"},
    {"url": "https://www.foggiatoday.it/eventi/", "citta": "Foggia"},
    {"url": "https://www.barlettaviva.it/eventi/", "citta": "Barletta"},
    {"url": "https://www.traniviva.it/eventi/", "citta": "Trani"},
    {"url": "https://www.manfredonianews.it/category/eventi/", "citta": "Manfredonia"},
]

MESI_PASSATI_2026 = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre"
]

PAROLE_VIETATE = [
    "meteo", "libeccio", "venti forti", "pioggia", "allerta",
    "questore", "sospende la licenza", "amianto", "pomodori",
    "annullato", "annullamento", "cancellazione", "indagine di mercato",
    "arresto", "rapina", "incidente", "incendio", "sequestro",
    "festa patronale", "sal da vinci", "daniele de martino",
    "ha rischiato", "intervista", "commentato", "torna sulla"
]

def oggi_iso():
    return datetime.now().strftime("%Y-%m-%d")

def carica_json(percorso):
    try:
        with open(percorso, "r", encoding="utf-8") as f:
            dati = json.load(f)
            return dati if isinstance(dati, list) else []
    except Exception:
        return []

def evento_valido(ev):
    oggi = oggi_iso()
    data_inizio = ev.get("dataInizio") or ""
    data_fine = ev.get("dataFine") or ""
    data_testo = (ev.get("dataTesto") or "").lower()

    if "agg." in data_testo or "segnalato il" in data_testo:
        return False

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", data_fine) or data_fine < oggi:
        return False

    if re.match(r"^\d{4}-\d{2}-\d{2}$", data_inizio) and data_inizio < "2026-11-19":
        return False

    testo = f"{ev.get('titolo', '')} {ev.get('descrizione', '')} {data_testo}".lower()

    if any(p in testo for p in PAROLE_VIETATE):
        return False

    if any(m in testo for m in MESI_PASSATI_2026) and not any(f in testo for f in ["novembre", "dicembre", "2027"]):
        return False

    return True

def raccogli_testo_con_dettagli(url_indice):
    """Legge la pagina elenco e apre i primi 6 link eventi recenti per recuperare date e luoghi esatti."""
    testi = []
    try:
        r = requests.get(url_indice, headers=HEADERS, timeout=20)
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "aside", "form"]):
            tag.decompose()

        # Estratto sintetico della pagina indice
        righe_indice = []
        for el in soup.find_all(["h2", "h3", "h4", "time"]):
            t = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
            if 15 <= len(t) <= 220 and t not in righe_indice:
                righe_indice.append(t)
        if righe_indice:
            testi.append("ELENCO PAGINA PRINCIPALE:\n" + "\n".join(righe_indice[:25]))

        # Cerca link a singoli eventi/articoli evitando URL di mesi/anni passati
        link_candidati = []
        dominio_base = "/".join(url_indice.split("/")[:3])
        for a in soup.find_all("a", href=True):
            href = urljoin(url_indice, a["href"]).split("#")[0]
            if not href.startswith(dominio_base):
                continue
            if href.rstrip("/") == url_indice.rstrip("/"):
                continue
            if any(x in href.lower() for x in ["/tag/", "/author/", "/page/", "login", "privacy", "cookie", "/2024/", "/2025/", "/2026/01/", "/2026/02/", "/2026/03/", "/2026/04/", "/2026/05/", "/2026/06/", "/2026/07/", "/2026/08/", "/2026/09/", "/2026/10/"]):
                continue
            titolo_link = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            if len(titolo_link) >= 22 and href not in link_candidati:
                link_candidati.append(href)

        # Apre le prime 6 schede evento per leggere data, ora e luogo precisi
        for link in link_candidati[:6]:
            try:
                rp = requests.get(link, headers=HEADERS, timeout=15)
                rp.encoding = rp.apparent_encoding or "utf-8"
                sp = BeautifulSoup(rp.text, "html.parser")
                for tag in sp(["script", "style", "nav", "footer", "aside", "form"]):
                    tag.decompose()
                titolo_p = sp.find("h1")
                titolo_str = re.sub(r"\s+", " ", titolo_p.get_text(" ", strip=True)) if titolo_p else ""
                corpo_p = []
                for p in sp.find_all(["p", "time", "li"]):
                    txt = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
                    if 20 <= len(txt) <= 350 and txt not in corpo_p:
                        corpo_p.append(txt)
                if titolo_str and corpo_p:
                    testi.append(f"SCHEDA EVENTO ({link}):\nTITOLO: {titolo_str}\nDETTAGLI: {' | '.join(corpo_p[:6])}")
            except Exception:
                continue

    except Exception as e:
        print("Errore lettura:", url_indice, e)

    return "\n\n".join(testi)[:14000]

def analizza_con_gemini(testo_grezzo, citta_default):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or not testo_grezzo.strip():
        return []

    oggi = oggi_iso()
    prompt = f"""Sei il redattore dell'app 'Che Si Fa Cerignola'. Oggi è {oggi}.
Analizza questi estratti e schede prese dalla sezione eventi di {citta_default} ed estrai SOLO veri eventi ricreativi, serate nei locali, concerti, DJ set, spettacoli teatrali, sagre, mercatini o incontri culturali che si svolgono da oggi ({oggi}) in poi (novembre 2026, dicembre 2026 o inizio 2027).

REGOLE DI ESCLUSIONE:
1. SCARTA eventi già conclusi o relativi a mesi passati (gennaio–ottobre 2026).
2. SCARTA articoli di cronaca nera/giudiziaria, meteo, politica, bandi comunali o eventi annullati.
3. Estrai SOLO appuntamenti reali a cui le persone possono partecipare, riportando la data e il luogo esatti ricavati dalle schede.

Restituisci SOLO un array JSON valido (senza ```json) con oggetti aventi queste chiavi esatte:
- "citta": "{citta_default}" (oppure la città specifica della provincia di Foggia/BAT indicata nell'evento, es. "Cerignola", "Foggia", "Barletta", "Trani", "Manfredonia", "Canosa di Puglia", "San Severo")
- "categoria": scegli SOLO tra "Serate & Locali", "Musica", "Spettacolo", "Fiera", "Famiglie", "Incontro"
- "titolo": titolo pulito dell'evento o della serata
- "dataTesto": data e ora esatte dell'evento (es. "23 Nov 2026 - 21:00" oppure "6 Dic 2026")
- "dataInizio": formato YYYY-MM-DD (deve essere >= "{oggi}")
- "dataFine": formato YYYY-MM-DD (deve essere >= dataInizio)
- "luogo": nome del locale, teatro, piazza o indirizzo preciso
- "indirizzoMappa": luogo + città per Google Maps
- "costo": es. "Ingresso libero", "A pagamento", oppure "Da verificare"
- "descrizione": 1 frase chiara su cosa si fa all'evento/serata

TESTO DA ANALIZZARE:
{testo_grezzo}
"""

    url = f"[https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=](https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=){api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1}
    }

    try:
        resp = requests.post(url, json=payload, timeout=45)
        data = resp.json()
        risposta = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        risposta = re.sub(r"^```json\s*|\s*```$", "", risposta, flags=re.IGNORECASE).strip()
        eventi = json.loads(risposta)
        return eventi if isinstance(eventi, list) else []
    except Exception as e:
        print("Errore Gemini:", e)
        return []

vecchi_eventi = [ev for ev in carica_json("eventi.json") if evento_valido(ev)]
nuovi_trovati = []

for fonte in FONTI_EVENTI:
    testo = raccogli_testo_con_dettagli(fonte["url"])
    estratti = analizza_con_gemini(testo, fonte["citta"])
    print(f"{fonte['citta']}: {len(estratti)} eventi estratti")
    nuovi_trovati.extend(estratti)

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
