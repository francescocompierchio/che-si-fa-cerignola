import requests
import json
import re
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 CheSiFaCerignola/2.0"
}

FONTI = [
    {"url": "https://www.viverecerignola.it/", "citta_default": "Cerignola"},
    {"url": "https://www.iltaccodibacco.it/cerignola/", "citta_default": "Cerignola"},
    {"url": "https://www.comune.cerignola.fg.it/", "citta_default": "Cerignola"},
    {"url": "https://www.iltaccodibacco.it/foggia/", "citta_default": "Foggia"},
    {"url": "https://www.iltaccodibacco.it/barletta/", "citta_default": "Barletta"},
    {"url": "https://www.iltaccodibacco.it/trani/", "citta_default": "Trani"},
    {"url": "https://www.iltaccodibacco.it/manfredonia/", "citta_default": "Manfredonia"},
]

CITTA_NOTE = [
    "Cerignola",
    "Foggia",
    "Barletta",
    "Trani",
    "Manfredonia",
    "Stornara",
    "Stornarella",
    "Orta Nova",
    "Carapelle",
    "Ordona",
    "Canosa di Puglia",
    "Canosa",
    "Margherita di Savoia",
    "San Ferdinando di Puglia",
    "Trinitapoli",
    "Ascoli Satriano",
    "Candela",
]

KEYWORD_LOCALI = [
    "dj set", "djset", "live", "serata", "aperitivo", "apericena",
    "pub", "club", "disco", "party", "karaoke", "tribute", "band",
    "concerto", "musica", "drink", "notte", "weekend", "sabato", "venerdi", "venerdì"
]

KEYWORD_EVENTI = [
    "cerignola", "foggia", "barletta", "trani", "manfredonia",
    "festival", "mercatino", "natale", "bambinella", "danza",
    "fiera", "sagra", "spettacolo", "teatro", "mostra", "evento",
    "raduno", "torneo", "cabaret", "commedia"
] + KEYWORD_LOCALI

def pulisci(t):
    return re.sub(r"\s+", " ", t).strip()

def rileva_citta(testo, default):
    low = testo.lower()
    for c in CITTA_NOTE:
        if c.lower() in low:
            if c.lower() == "canosa":
                return "Canosa di Puglia"
            return c
    return default

def rileva_categoria(testo):
    low = testo.lower()
    if any(k in low for k in KEYWORD_LOCALI):
        return "Serate & Locali"
    if any(k in low for k in ["teatro", "commedia", "cabaret", "spettacolo", "danza"]):
        return "Teatro & Spettacoli"
    if any(k in low for k in ["sagra", "mercatino", "fiera", "natale", "bambinella"]):
        return "Feste & Mercatini"
    return "Eventi & Cultura"

def cerca_eventi():
    trovati = []
    oggi = datetime.now()
    data_inizio = oggi.strftime("%Y-%m-%d")
    data_fine = (oggi + timedelta(days=3)).strftime("%Y-%m-%d")
    data_testo = f"Segnalato il {oggi.strftime('%d/%m/%Y')}"

    for fonte in FONTI:
        url = fonte["url"]
        citta_default = fonte["citta_default"]
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.encoding = r.apparent_encoding or "utf-8"
            html = r.text
            titoli = re.findall(r"<h[2-4][^>]*>(.*?)</h[2-4]>", html, re.DOTALL | re.IGNORECASE)
            for t in titoli[:35]:
                t = pulisci(re.sub(r"<[^>]+>", "", t))
                if len(t) < 12 or len(t) > 130:
                    continue
                low = t.lower()
                if any(k in low for k in KEYWORD_EVENTI):
                    citta = rileva_citta(t, citta_default)
                    categoria = rileva_categoria(t)
                    trovati.append({
                        "titolo": t,
                        "dataInizio": data_inizio,
                        "dataFine": data_fine,
                        "dataTesto": data_testo,
                        "citta": citta,
                        "categoria": categoria,
                        "luogo": citta,
                        "indirizzoMappa": citta,
                        "costo": "Verifica su fonte / locale",
                        "descrizione": f"Evento rilevato in automatico da {url}. Verifica orari e dettagli sulla pagina della fonte o del locale.",
                        "fonte": url
                    })
        except Exception as e:
            print("Errore fonte", url, e)

    visti = set()
    unici = []
    for e in trovati:
        k = e["titolo"].lower()
        if k not in visti:
            visti.add(k)
            unici.append(e)
    return unici

def carica_json(percorso):
    try:
        with open(percorso, "r", encoding="utf-8") as f:
            dati = json.load(f)
            return dati if isinstance(dati, list) else []
    except Exception:
        return []

vecchi_eventi = carica_json("eventi.json")
nuovi_eventi = cerca_eventi()
print(f"Trovati {len(nuovi_eventi)} eventi dalle fonti web")

tutti = {}
for e in vecchi_eventi:
    chiave = e.get("titolo", "").strip().lower()
    if chiave:
        tutti[chiave] = e

aggiunti = 0
for e in nuovi_eventi:
    chiave = e["titolo"].strip().lower()
    if chiave and chiave not in tutti:
        tutti[chiave] = e
        aggiunti += 1

lista_finale = list(tutti.values())

with open("eventi.json", "w", encoding="utf-8") as f:
    json.dump(lista_finale, f, ensure_ascii=False, indent=2)

print(f"Aggiunti {aggiunti} nuovi eventi. Totale in eventi.json: {len(lista_finale)}")
