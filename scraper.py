import requests, json, re
from datetime import datetime

HEADERS = {"User-Agent": "Mozilla/5.0 CheSiFaCerignola/1.0"}

FONTI = [
    "https://www.viverecerignola.it/",
    "https://www.iltaccodibacco.it/cerignola/",
    "https://www.comune.cerignola.fg.it/",
]

def pulisci(t):
    return re.sub(r"\s+", " ", t).strip()

def cerca_eventi():
    trovati = []
    for url in FONTI:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            html = r.text
            # prende titoli che contengono Cerignola / evento / festival / mercatino / concerto
            titoli = re.findall(r"<h[2-3][^>]*>(.*?)</h[2-3]>", html, re.DOTALL)
            for t in titoli[:20]:
                t = pulisci(re.sub(r"<[^>]+>", "", t))
                if len(t) < 10 or len(t) > 120:
                    continue
                low = t.lower()
                if any(k in low for k in ["cerignola", "festival", "mercatino", "concerto", "natale", "bambinella", "danza", "fiera", "sagra"]):
                    trovati.append({
                        "titolo": t,
                        "data": datetime.now().strftime("%Y-%m-%d 18:00"),
                        "luogo": "Cerignola",
                        "descrizione": "Evento trovato in automatico da " + url + " - controlla dettagli sul sito fonte.",
                        "citta": "Cerignola",
                        "categoria": "Evento",
                        "fonte": url
                    })
        except Exception as e:
            print("Errore fonte", url, e)
    # togli duplicati per titolo
    visti = set()
    unici = []
    for e in trovati:
        k = e["titolo"].lower()
        if k not in visti:
            visti.add(k)
            unici.append(e)
    return unici

try:
    with open("events.json", "r", encoding="utf-8") as f:
        vecchi = json.load(f)
except:
    vecchi = []

nuovi = cerca_eventi()
print(f"Trovati {len(nuovi)} nuovi")

# unisci vecchi + nuovi senza duplicati e senza cancellare quelli pubblicati dai locali
tutti = {e["titolo"].lower(): e for e in vecchi}
for e in nuovi:
    if e["titolo"].lower() not in tutti:
        tutti[e["titolo"].lower()] = e

with open("events.json", "w", encoding="utf-8") as f:
    json.dump(list(tutti.values()), f, ensure_ascii=False, indent=2)

print(f"Totale eventi: {len(tutti)}")
