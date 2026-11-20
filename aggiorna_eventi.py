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

def oggi_iso():
    return datetime.now().strftime("%Y-%m-%d")

def carica_json(percorso):
    try:
        with open(percorso, "r", encoding="utf-8") as f:
            dati = json.load(f)
            return dati if isinstance(dati, list) else []
    except Exception:
        return []

def pulisci_sporchi(eventi):
    oggi = oggi_iso()
    parole_vietate = [
        "meteo", "libeccio", "venti forti", "pioggia", "allerta",
        "questore", "sospende la licenza", "amianto", "pomodori",
        "annullato", "annullamento", "cancellazione", "indagine di mercato",
        "arresto", "rapina", "incidente", "incendio", "sequestro",
        "30 agosto", "28 agosto", "8 settembre"
    ]
    puliti = []
    for ev in eventi:
        if (ev.get("dataFine") or "9999-12-31") < oggi:
            continue
        testo = f"{ev.get('titolo', '')} {ev.get('descrizione', '')}".lower()
        if any(p in testo for p in parole_vietate):
            continue
        puliti.append(ev)
    return puliti

def estrai_testo_pagina(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "aside", "form"]):
            tag.decompose()
        blocchi = []
        for el in soup.find_all(["article", "h2", "h3", "h4", "time"]):
            t = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
            if 15 <= len(t) <= 320 and t not in blocchi:
                blocchi.append(t)
        return "\n".join(blocchi[:60])
    except Exception as e:
        print("Errore lettura:", url, e)
        return ""

def analizza_con_gemini(testo_grezzo, citta_default):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or not testo_grezzo.strip():
        return []

    oggi = oggi_iso()
    prompt = f"""Sei il redattore dell'app 'Che Si Fa Cerignola'. Oggi è {oggi}.
Analizza questi estratti presi da una pagina locale di {citta_default} ed estrai SOLO veri eventi ricreativi, serate nei locali, concerti, DJ set, spettacoli teatrali, sagre, mercatini o feste popolari in programma da oggi ({oggi}) in poi.

REGOLE RIGIDE DI ESCLUSIONE:
- SCARTA categoricamente articoli di cronaca, politica, bandi/avvisi comunali, meteo, proteste, incidenti, sospensioni di licenze o eventi annullati.
- SCARTA eventi passati (es. mesi estivi già trascorsi o date precedenti a {oggi}).
- SCARTA notizie senza un reale appuntamento/evento a cui il pubblico può partecipare.

Restituisci SOLO un array JSON valido (senza markdown ```json) con oggetti aventi esattamente queste chiavi:
- "citta": "{citta_default}" (oppure la città specifica della provincia di Foggia/BAT se indicata nell'evento, es. "San Severo", "Canosa di Puglia", "Manfredonia", "Barletta", "Trani", "Foggia", "Cerignola")
- "categoria": scegli SOLO tra "Serate & Locali", "Musica", "Spettacolo", "Fiera", "Famiglie", "Incontro"
- "titolo": titolo breve e pulito dell'evento o della serata
- "dataTesto": data e ora leggibili (es. "23 Nov 2026 - 21:00" oppure "6 Dic 2026")
- "dataInizio": formato YYYY-MM-DD (se non esplicita ma è un evento imminente della settimana, usa "{oggi}")
- "dataFine": formato YYYY-MM-DD (uguale a dataInizio se dura un solo giorno)
- "luogo": nome del locale, teatro, piazza o indirizzo preciso (es. "Teatro del Fuoco, Foggia")
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
        resp = requests.post(url, json=payload, timeout=35)
        data = resp.json()
        risposta = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        risposta = re.sub(r"^```json\s*|\s*```$", "", risposta, flags=re.IGNORECASE).strip()
        eventi = json.loads(risposta)
        return eventi if isinstance(eventi, list) else []
    except Exception as e:
        print("Errore Gemini:", e)
        return []

vecchi_eventi = pulisci_sporchi(carica_json("eventi.json"))
nuovi_trovati = []

for fonte in FONTI_EVENTI:
    testo = estrai_testo_pagina(fonte["url"])
    estratti = analizza_con_gemini(testo, fonte["citta"])
    print(f"{fonte['citta']} ({fonte['url']}): {len(estratti)} eventi reali estratti")
    nuovi_trovati.extend(estratti)

nuovi_puliti = pulisci_sporchi(nuovi_trovati)

mappa = {}
for ev in vecchi_eventi:
    k = re.sub(r"[^a-z0-9]", "", ev.get("titolo", "").lower())[:50]
    if k:
        mappa[k] = ev

aggiunti = 0
for ev in nuovi_puliti:
    k = re.sub(r"[^a-z0-9]", "", ev.get("titolo", "").lower())[:50]
    if k and k not in mappa:
        mappa[k] = ev
        aggiunti += 1

lista_finale = sorted(mappa.values(), key=lambda x: x.get("dataInizio", "9999-12-31"))

with open("eventi.json", "w", encoding="utf-8") as f:
    json.dump(lista_finale, f, ensure_ascii=False, indent=2)

print(f"Pulizia completata. Aggiunti {aggiunti} eventi reali. Totale attivi: {len(lista_finale)}")
