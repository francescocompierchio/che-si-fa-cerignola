import requests
import json
import re
import html as html_lib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36 CheSiFaCerignola/3.0",
    "Accept-Language": "it-IT,it;q=0.9"
}

FONTI_HTML = [
    {"url": "https://www.viverecerignola.it/", "citta_default": "Cerignola"},
    {"url": "https://www.foggiatoday.it/eventi/", "citta_default": "Foggia"},
    {"url": "https://www.barlettaviva.it/eventi/", "citta_default": "Barletta"},
    {"url": "https://www.traniviva.it/eventi/", "citta_default": "Trani"},
    {"url": "https://www.manfredonianews.it/category/eventi/", "citta_default": "Manfredonia"},
    {"url": "https://www.cerignolaviva.it/eventi/", "citta_default": "Cerignola"},
]

FONTI_RSS = [
    {"url": "https://news.google.com/rss/search?q=eventi+OR+serata+OR+concerto+OR+spettacolo+Cerignola&hl=it&gl=IT&ceid=IT:it", "citta_default": "Cerignola"},
    {"url": "https://news.google.com/rss/search?q=eventi+OR+serata+OR+concerto+OR+spettacolo+Foggia&hl=it&gl=IT&ceid=IT:it", "citta_default": "Foggia"},
    {"url": "https://news.google.com/rss/search?q=eventi+OR+serata+OR+concerto+OR+spettacolo+Barletta&hl=it&gl=IT&ceid=IT:it", "citta_default": "Barletta"},
    {"url": "https://news.google.com/rss/search?q=eventi+OR+serata+OR+concerto+OR+spettacolo+Trani&hl=it&gl=IT&ceid=IT:it", "citta_default": "Trani"},
    {"url": "https://news.google.com/rss/search?q=eventi+OR+serata+OR+concerto+OR+spettacolo+Manfredonia&hl=it&gl=IT&ceid=IT:it", "citta_default": "Manfredonia"},
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
    "San Ferdinando",
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
    "festival", "mercatino", "natale", "bambinella", "danza",
    "fiera", "sagra", "spettacolo", "teatro", "mostra", "evento",
    "raduno", "torneo", "cabaret", "commedia", "rassegna", "stagione",
    "incontro", "presentazione", "visita guidata", "degustazione"
] + KEYWORD_LOCALI

PAROLE_ESCLUSE = [
    "incidente", "arresto", "arrestato", "rapina", "furto", "omicidio",
    "morto", "morte", "sequestro", "droga", "spaccio", "incendio",
    "condanna", "processo", "truffa", "denunciato", "aggressione"
]

def pulisci(t):
    t = html_lib.unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"\s+", " ", t).strip()

def titolo_valido(t):
    if len(t) < 15 or len(t) > 140:
        return False
    low = t.lower()
    if any(bad in low for bad in PAROLE_ESCLUSE):
        return False
    return any(k in low for k in KEYWORD_EVENTI)

def rileva_citta(testo, default):
    low = testo.lower()
    for c in CITTA_NOTE:
        if c.lower() in low:
            if c.lower() == "canosa":
                return "Canosa di Puglia"
            if c.lower() == "san ferdinando di puglia":
                return "San Ferdinando"
            return c
    return default

def rileva_categoria(testo):
    low = testo.lower()
    if any(k in low for k in KEYWORD_LOCALI):
        return "Serate & Locali"
    if any(k in low for k in ["teatro", "commedia", "cabaret", "spettacolo", "danza"]):
        return "Spettacolo"
    if any(k in low for k in ["sagra", "mercatino", "fiera", "natale", "bambinella"]):
        return "Fiera"
    if any(k in low for k in ["bambini", "famiglie"]):
        return "Famiglie"
    return "Incontro"

def cerca_eventi():
    trovati = []
    oggi = datetime.now()
    data_inizio = oggi.strftime("%Y-%m-%d")
    data_fine = (oggi + timedelta(days=4)).strftime("%Y-%m-%d")
    data_testo = f"In programma · agg. {oggi.strftime('%d/%m/%Y')}"

    for fonte in FONTI_HTML:
        url = fonte["url"]
        citta_default = fonte["citta_default"]
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.encoding = r.apparent_encoding or "utf-8"
            titoli = re.findall(r"<h[1-4][^>]*>(.*?)</h[1-4]>", r.text, re.DOTALL | re.IGNORECASE)
            for raw in titoli[:45]:
                t = pulisci(raw)
                if not titolo_valido(t):
                    continue
                citta = rileva_citta(t, citta_default)
                trovati.append({
                    "titolo": t,
                    "dataInizio": data_inizio,
                    "dataFine": data_fine,
                    "dataTesto": data_testo,
                    "citta": citta,
                    "categoria": rileva_categoria(t),
                    "luogo": citta,
                    "indirizzoMappa": citta,
                    "costo": "Verifica su fonte / locale",
                    "descrizione": f"Segnalato da {url}. Tocca 'Apri mappa' o consulta il portale locale per orari e ingresso.",
                    "fonte": url
                })
        except Exception as e:
            print("Errore fonte HTML:", url, e)

    for fonte in FONTI_RSS:
        url = fonte["url"]
        citta_default = fonte["citta_default"]
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:15]:
                raw_title = item.findtext("title") or ""
                # Rimuove il nome della testata dopo " - "
                titolo_pulito = pulisci(raw_title.rsplit(" - ", 1)[0])
                if not titolo_valido(titolo_pulito):
                    continue
                citta = rileva_citta(titolo_pulito, citta_default)
                trovati.append({
                    "titolo": titolo_pulito,
                    "dataInizio": data_inizio,
                    "dataFine": data_fine,
                    "dataTesto": data_testo,
                    "citta": citta,
                    "categoria": rileva_categoria(titolo_pulito),
                    "luogo": citta,
                    "indirizzoMappa": citta,
                    "costo": "Verifica su fonte / locale",
                    "descrizione": f"Notizia evento per {citta}. Verifica orari e dettagli presso gli organizzatori.",
                    "fonte": url
                })
        except Exception as e:
            print("Errore fonte RSS:", url, e)

    visti = set()
    unici = []
    for e in trovati:
        k = re.sub(r"[^a-z0-9]", "", e["titolo"].lower())[:55]
        if k and k not in visti:
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

oggi_str = datetime.now().strftime("%Y-%m-%d")
vecchi_eventi = [e for e in carica_json("eventi.json") if (e.get("dataFine") or "9999-12-31") >= oggi_str]
nuovi_eventi = cerca_eventi()
print(f"Trovati {len(nuovi_eventi)} eventi dalle fonti web")

tutti = {}
for e in vecchi_eventi:
    chiave = re.sub(r"[^a-z0-9]", "", e.get("titolo", "").lower())[:55]
    if chiave:
        tutti[chiave] = e

aggiunti = 0
for e in nuovi_eventi:
    chiave = re.sub(r"[^a-z0-9]", "", e["titolo"].lower())[:55]
    if chiave and chiave not in tutti:
        tutti[chiave] = e
        aggiunti += 1

lista_finale = list(tutti.values())

with open("eventi.json", "w", encoding="utf-8") as f:
    json.dump(lista_finale, f, ensure_ascii=False, indent=2)

print(f"Aggiunti {aggiunti} nuovi eventi. Totale in eventi.json: {len(lista_finale)}")
