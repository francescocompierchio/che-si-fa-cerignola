import os
import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
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

    # Scarta tutto ciò che proviene dal vecchio scraper senza data reale
    if "agg." in data_testo or "segnalato il" in data_testo:
        return False

    # Scarta date passate o non valide
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", data_fine) or data_fine < oggi:
        return False
    if re.match(r"^\d{4}-\d{2}-\d{2}$", data_inizio) and data_inizio < "2026-11-19":
        return False

    testo = f"{ev.get('titolo', '')} {ev.get('descrizione', '')} {data_testo}".lower()

    if any(p in testo for p in PAROLE_VIETATE):
        return False

    # Se nel titolo/testo c'è un mese già trascorso senza riferimento a novembre/dicembre/2027, scarta
    if any(m in testo for m in MESI_PASSATI_2026) and not any(f in testo for f in ["novembre", "dicembre", "2027"]):
        return False

    return True

def estrai_testo_pagina(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "aside", "form"]):
            tag.decompose()
        blocchi = []
        for el in soup.find_all(["article", "li", "div"]):
            if el.name == "div" and not any(c in (el.get("class") or []) for c in ["post", "article", "card", "item", "news", "event"]):
                continue
            t = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
            if 25 <= len(t) <= 380 and t not in blocchi:
                blocchi.append(t)
        return "\n".join(blocchi[:55])
    except Exception as e:
        print("Errore lettura:", url, e)
        return ""

def analizza_con_gemini(testo_grezzo, citta_default):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or not testo_grezzo.strip():
        return []

    oggi = oggi_iso()
    prompt = f"""Sei il redattore dell'app 'Che Si Fa Cerignola'. Oggi è venerdì {oggi}.
Analizza questi estratti presi dalla sezione eventi di un portale locale di {citta_default} ed estrai SOLO veri eventi ricreativi, serate nei locali, concerti, DJ set, spettacoli teatrali, sagre o mercatini che si svolgono da oggi ({oggi}) in poi (fine novembre 2026, dicembre 2026 o inizio 2027).

REGOLE ASSOLUTE DI ESCLUSIONE (SE HAI UN DUBBIO, SCARTA L'ARTICOLO):
1. SCARTA categoricamente qualsiasi articolo passato (es. luglio, agosto, settembre, ottobre o inizio novembre 2026, Festa Patronale estiva, articoli d'archivio).
2. SCARTA qualsiasi notizia di cronaca, interviste, retroscena, bandi comunali, meteo, proteste o annunci generici di intere stagioni teatrali senza una singola data precisa.
3. NON INVENTARE MAI LA DATA: se nell'estratto non è indicata una data reale e futura dell'evento (es. "21 novembre", "23 nov", "6 dicembre", "ogni sabato"), SCARTA l'evento.

Restituisci SOLO un array JSON valido (senza ```json) con oggetti aventi queste chiavi esatte:
- "citta": "{citta_default}" (oppure la città specifica della provincia di Foggia/BAT indicata nell'evento, es. "Cerignola", "Foggia", "Barletta", "Trani", "Manfredonia", "Canosa di Puglia", "San Severo")
- "categoria": scegli SOLO tra "Serate & Locali", "Musica", "Spettacolo", "Fiera", "Famiglie", "Incontro"
- "titolo": titolo pulito e diretto dell'evento o della serata
- "dataTesto": data e ora esatte dell'evento (es. "22 Nov 2026 - 21:00" oppure "6 Dic 2026")
- "dataInizio": formato YYYY-MM-DD (deve essere >= "{oggi}")
- "dataFine": formato YYYY-MM-DD (deve essere >= dataInizio)
- "luogo": locale, teatro, piazza o indirizzo preciso (es. "Teatro del Fuoco, Foggia")
- "indirizzoMappa": luogo + città per Google Maps
- "costo": es. "Ingresso libero", "A pagamento", oppure "Da verificare"
- "descrizione": 1 frase chiara su cosa si fa all'evento/serata

TESTO DA ANALIZZARE:
{testo_grezzo}
"""

    url = f"[https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=](https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=){api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0}
    }

    try:
        resp = requests.post(url, json=payload, timeout=35)
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
    testo = estrai_testo_pagina(fonte["url"])
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

print(f"Pulizia completata. Aggiunti {aggiunti} eventi futuri verificati. Totale in app: {len(lista_finale)}")
