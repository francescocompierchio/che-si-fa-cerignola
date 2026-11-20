import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
EVENTI_FILE = "eventi.json"

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=eventi+Cerignola+when:7d&hl=it&gl=IT&ceid=IT:it",
    "https://news.google.com/rss/search?q=(spettacolo+OR+concerto+OR+fiera+OR+mercatino+OR+teatro)+Cerignola+when:7d&hl=it&gl=IT&ceid=IT:it",
    "https://news.google.com/rss/search?q=eventi+(Canosa+OR+%22San+Ferdinando+di+Puglia%22+OR+Stornara+OR+Stornarella+OR+Orta+Nova+OR+%22Margherita+di+Savoia%22+OR+Trinitapoli)+when:7d&hl=it&gl=IT&ceid=IT:it",
]


def oggi_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def carica_eventi_esistenti():
    if not os.path.exists(EVENTI_FILE):
        return []
    with open(EVENTI_FILE, "r", encoding="utf-8") as f:
        try:
            dati = json.load(f)
        except json.JSONDecodeError:
            return []
    oggi = oggi_iso()
    return [ev for ev in dati if ev.get("dataFine", "9999-12-31") >= oggi]


def scarica_notizie_rss():
    notizie = []
    titoli_visti = set()
    headers = {"User-Agent": "Mozilla/5.0 (compatible; CheSiFaBot/1.0)"}

    for url in RSS_FEEDS:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                xml_data = resp.read()
            root = ET.fromstring(xml_data)
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                pub_date = (item.findtext("pubDate") or "").strip()
                desc = re.sub(r"<[^>]+>", " ", item.findtext("description") or "").strip()
                desc = re.sub(r"\s+", " ", desc)

                if title and title not in titoli_visti:
                    titoli_visti.add(title)
                    notizie.append(f"- TITOLO: {title} | DATA ARTICOLO: {pub_date} | DETTAGLI: {desc[:300]}")
        except Exception as e:
            print(f"Avviso feed {url}: {e}")

    return notizie[:45]


def estrai_nuovi_eventi_con_ai(notizie, eventi_esistenti):
    if not GEMINI_API_KEY or not notizie:
        return []

    oggi = oggi_iso()
    titoli_esistenti = [f"{e.get('titolo')} ({e.get('dataInizio')})" for e in eventi_esistenti]

    prompt = f"""
Oggi è {oggi}. Sei l'editor automatico del sito "Che Si Fa Cerignola".
Analizza questo elenco di notizie locali e estrai SOLO veri eventi pubblici futuri o in corso (spettacoli, teatro, concerti, sagre, fiere, mercatini, incontri culturali, eventi per famiglie, feste di piazza) a Cerignola e nei comuni vicini (Canosa di Puglia, San Ferdinando di Puglia, Margherita di Savoia, Trinitapoli, Stornara, Stornarella, Orta Nova, Ascoli Satriano).

REGOLE RIGIDE:
1. Ignora cronaca nera, politica senza evento pubblico aperto, risultati sportivi passati, annunci generici senza data precisa.
2. Includi SOLO eventi con dataFine maggiore o uguale a {oggi}.
3. NON duplicare eventi già presenti in questa lista: {json.dumps(titoli_esistenti, ensure_ascii=False)}
4. Se non ci sono nuovi eventi validi, restituisci una lista vuota [].

Restituisci ESCLUSIVAMENTE un array JSON valido con oggetti aventi queste chiavi esatte:
- "citta": nome breve del comune (es. "Cerignola", "Canosa", "San Ferdinando")
- "categoria": una tra "Spettacolo", "Famiglie", "Fiera", "Mercatino", "Incontro", "Musica", "Natale", "Sport"
- "titolo": titolo pulito e sintetico dell'evento
- "dataTesto": data leggibile in italiano con eventuale orario (es. "25 Nov 2026 - 18:30")
- "dataInizio": formato "YYYY-MM-DD"
- "dataFine": formato "YYYY-MM-DD" (uguale a dataInizio se dura un solo giorno)
- "luogo": nome della sede e città (es. "Teatro Mercadante, Cerignola")
- "indirizzoMappa": indirizzo preciso per Google Maps
- "costo": es. "Ingresso libero", "Su prenotazione", "A pagamento" oppure "Da verificare"
- "descrizione": descrizione oggettiva di 1-2 frasi senza opinioni

NOTIZIE DA ANALIZZARE:
{chr(10).join(notizie)}
"""

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1
        }
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            risposta = json.loads(resp.read().decode("utf-8"))
        testo_json = risposta["candidates"][0]["content"]["parts"][0]["text"]
        nuovi = json.loads(testo_json)
        return nuovi if isinstance(nuovi, list) else []
    except Exception as e:
        print(f"Errore chiamata AI: {e}")
        return []


def normalizza(testo):
    return re.sub(r"[^a-z0-9]", "", testo.lower())


def main():
    esistenti = carica_eventi_esistenti()
    chiavi_esistenti = {
        (normalizza(ev.get("titolo", "")), ev.get("dataInizio", ""))
        for ev in esistenti
    }

    notizie = scarica_notizie_rss()
    print(f"Notizie locali scaricate: {len(notizie)}")

    nuovi_eventi = estrai_nuovi_eventi_con_ai(notizie, esistenti)
    aggiunti = 0

    for ev in nuovi_eventi:
        if not ev.get("titolo") or not ev.get("dataInizio") or not ev.get("dataFine"):
            continue
        if ev["dataFine"] < oggi_iso():
            continue

        chiave = (normalizza(ev["titolo"]), ev["dataInizio"])
        if chiave not in chiavi_esistenti:
            esistenti.append(ev)
            chiavi_esistenti.add(chiave)
            aggiunti += 1

    esistenti.sort(key=lambda x: x.get("dataInizio", "9999-12-31"))

    with open(EVENTI_FILE, "w", encoding="utf-8") as f:
        json.dump(esistenti, f, ensure_ascii=False, indent=2)

    print(f"Aggiornamento completato. Nuovi eventi aggiunti: {aggiunti}. Totale attivi: {len(esistenti)}.")


if __name__ == "__main__":
    main()
