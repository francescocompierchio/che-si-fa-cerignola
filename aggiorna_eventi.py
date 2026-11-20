import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
EVENTI_FILE = "eventi.json"

RSS_FEEDS = [
    # Cerignola
    ("Cerignola", "https://news.google.com/rss/search?q=(eventi+OR+serata+OR+concerto+OR+spettacolo+OR+fiera+OR+mercatino+OR+teatro)+Cerignola+when:7d&hl=it&gl=IT&ceid=IT:it"),
    # Foggia
    ("Foggia", "https://news.google.com/rss/search?q=(eventi+OR+concerto+OR+spettacolo+OR+teatro+OR+serata+OR+mostra+OR+fiera)+Foggia+when:7d&hl=it&gl=IT&ceid=IT:it"),
    # Barletta
    ("Barletta", "https://news.google.com/rss/search?q=(eventi+OR+concerto+OR+spettacolo+OR+teatro+OR+serata+OR+mostra)+Barletta+when:7d&hl=it&gl=IT&ceid=IT:it"),
    # Trani
    ("Trani", "https://news.google.com/rss/search?q=(eventi+OR+concerto+OR+spettacolo+OR+teatro+OR+serata+OR+mostra)+Trani+when:7d&hl=it&gl=IT&ceid=IT:it"),
    # Manfredonia
    ("Manfredonia", "https://news.google.com/rss/search?q=(eventi+OR+concerto+OR+spettacolo+OR+teatro+OR+serata+OR+mostra)+Manfredonia+when:7d&hl=it&gl=IT&ceid=IT:it"),
    # Altri comuni vicini
    ("Dintorni", "https://news.google.com/rss/search?q=eventi+(Canosa+OR+%22San+Ferdinando+di+Puglia%22+OR+Stornara+OR+Stornarella+OR+Orta+Nova+OR+%22Margherita+di+Savoia%22+OR+Trinitapoli)+when:7d&hl=it&gl=IT&ceid=IT:it"),
]

PAGINE_EVENTI_DIRETTE = [
    ("Cerignola", "https://www.iltaccodibacco.it/cerignola/"),
    ("Foggia", "https://www.iltaccodibacco.it/foggia/"),
    ("Foggia", "https://www.foggiatoday.it/eventi/"),
    ("Barletta", "https://www.iltaccodibacco.it/barletta/"),
    ("Barletta", "https://www.barlettaviva.it/eventi/"),
    ("Trani", "https://www.iltaccodibacco.it/trani/"),
    ("Trani", "https://www.traniviva.it/eventi/"),
    ("Manfredonia", "https://www.iltaccodibacco.it/manfredonia/"),
    ("Manfredonia", "https://www.manfredonianews.it/category/eventi/"),
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
    headers = {"User-Agent": "Mozilla/5.0 (compatible; CheSiFaBot/3.0)"}

    for area, url in RSS_FEEDS:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                xml_data = resp.read()
            root = ET.fromstring(xml_data)
            count_feed = 0
            for item in root.findall(".//item"):
                if count_feed >= 15:
                    break
                title = (item.findtext("title") or "").strip()
                pub_date = (item.findtext("pubDate") or "").strip()
                desc = re.sub(r"<[^>]+>", " ", item.findtext("description") or "").strip()
                desc = re.sub(r"\s+", " ", desc)

                if title and title not in titoli_visti:
                    titoli_visti.add(title)
                    notizie.append(f"[RSS {area}] TITOLO: {title} | DATA ARTICOLO: {pub_date} | DETTAGLI: {desc[:250]}")
                    count_feed += 1
        except Exception as e:
            print(f"Avviso feed {area}: {e}")

    return notizie


def scarica_pagine_eventi():
    estratti = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    }

    for citta, url in PAGINE_EVENTI_DIRETTE:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            html = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
            blocchi = re.findall(r"<(?:article|div|li)[^>]*>(.*?)</(?:article|div|li)>", html, flags=re.DOTALL | re.IGNORECASE)

            righe_pagina = []
            visti = set()
            for b in blocchi:
                testo = re.sub(r"<[^>]+>", " ", b)
                testo = re.sub(r"\s+", " ", testo).strip()
                if 35 <= len(testo) <= 320:
                    chiave = testo[:80].lower()
                    if chiave not in visti:
                        visti.add(chiave)
                        righe_pagina.append(testo)
                if len(righe_pagina) >= 18:
                    break

            for r in righe_pagina:
                estratti.append(f"[PORTALE {citta} - {url}] {r}")
        except Exception as e:
            print(f"Avviso pagina {url}: {e}")

    return estratti


def normalizza_citta(citta_raw):
    c = (citta_raw or "").strip()
    low = c.lower()
    if "cerignola" in low:
        return "Cerignola"
    if "foggia" in low:
        return "Foggia"
    if "barletta" in low:
        return "Barletta"
    if "trani" in low:
        return "Trani"
    if "manfredonia" in low:
        return "Manfredonia"
    if "canosa" in low:
        return "Canosa di Puglia"
    if "san ferdinando" in low:
        return "San Ferdinando di Puglia"
    if "margherita" in low:
        return "Margherita di Savoia"
    return c if c else "Cerignola"


def estrai_nuovi_eventi_con_ai(fonti_testo, eventi_esistenti):
    if not GEMINI_API_KEY or not fonti_testo:
        return []

    oggi = oggi_iso()
    titoli_esistenti = [f"{e.get('titolo')} ({e.get('dataInizio')})" for e in eventi_esistenti]

    prompt = f"""
Oggi è {oggi}. Sei l'editor automatico del sito "Che Si Fa Cerignola".
Analizza queste notizie RSS e questi estratti dai portali eventi locali, ed estrai TUTTI i veri eventi pubblici futuri o in corso (dal {oggi} in poi):
- Serate nei locali (DJ set, live music, concerti in pub/club/lounge bar, aperitivi musicali, tribute band, karaoke, serate dance)
- Spettacoli, teatro, cabaret, concerti, sagre, fiere, mercatini, mostre, incontri culturali, eventi per famiglie, feste di piazza

Comuni ammessi: Cerignola, Foggia, Barletta, Trani, Manfredonia, Canosa di Puglia, San Ferdinando di Puglia, Margherita di Savoia, Trinitapoli, Stornara, Stornarella, Orta Nova, Ascoli Satriano.

REGOLE RIGIDE:
1. Estrai eventi reali per TUTTE le città presenti nei dati (specialmente Cerignola, Foggia, Barletta, Trani, Manfredonia).
2. Ignora cronaca nera, politica senza evento pubblico, notizie senza evento reale o eventi già terminati prima di {oggi}.
3. Se la data esatta del giorno/mese è scritta nel testo (es. "22 novembre", "sabato 21"), convertila correttamente in formato "YYYY-MM-DD" considerando che oggi è {oggi}. Se un evento indica solo "questo weekend" o "stasera" rispetto alla data articolo recente, stima la data coerente.
4. NON duplicare eventi già presenti in questa lista: {json.dumps(titoli_esistenti, ensure_ascii=False)}
5. Se non ci sono nuovi eventi validi, restituisci [].

Restituisci ESCLUSIVAMENTE un array JSON valido con oggetti aventi queste chiavi esatte:
- "citta": nome esatto del comune ("Cerignola", "Foggia", "Barletta", "Trani", "Manfredonia", "Canosa di Puglia", ecc.)
- "categoria": una tra "Serate & Locali", "Spettacolo", "Musica", "Famiglie", "Fiera", "Mercatino", "Incontro", "Natale", "Sport"
- "titolo": titolo pulito e sintetico dell'evento o della serata
- "dataTesto": data leggibile in italiano con eventuale orario (es. "22 Nov 2026 - 22:00")
- "dataInizio": formato "YYYY-MM-DD"
- "dataFine": formato "YYYY-MM-DD" (uguale a dataInizio se dura un solo giorno)
- "luogo": nome del locale o della sede e città (es. "Teatro Giordano, Foggia" oppure "Nome Locale, Barletta")
- "indirizzoMappa": indirizzo preciso o luogo + città per Google Maps
- "costo": es. "Ingresso libero", "Su prenotazione", "A pagamento" oppure "Da verificare"
- "descrizione": descrizione oggettiva di 1-2 frasi senza opinioni

FONTI DA ANALIZZARE:
{chr(10).join(fonti_testo[:160])}
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
        with urllib.request.urlopen(req, timeout=60) as resp:
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

    rss_items = scarica_notizie_rss()
    pagine_items = scarica_pagine_eventi()
    tutto_materiale = pagine_items + rss_items
    print(f"Fonti raccolte -> Portali eventi: {len(pagine_items)}, RSS: {len(rss_items)}")

    nuovi_eventi = estrai_nuovi_eventi_con_ai(tutto_materiale, esistenti)
    aggiunti = 0

    for ev in nuovi_eventi:
        if not ev.get("titolo") or not ev.get("dataInizio") or not ev.get("dataFine"):
            continue
        if ev["dataFine"] < oggi_iso():
            continue

        ev["citta"] = normalizza_citta(ev.get("citta"))
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
