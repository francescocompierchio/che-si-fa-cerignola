import os
import re
import json
import time
import requests
from collections import Counter
from difflib import SequenceMatcher
from datetime import datetime, timedelta

GIORNI_ANTICIPO_MAX = 45

DOMINI_AUTO = (
    "news.google.com", "iltaccodibacco.it", "viaggiareinpuglia.it",
    "pugliaevents.it", "eventiesagre.it", "eventbrite.it",
    "lanotiziaweb.it", "marchiodoc.it", "cerignolaviva.it",
    "canosaviva.it", "barlettaviva.it", "traniviva.it",
    "bisceglieviva.it", "andriaviva.it", "statoquotidiano.it",
    "immediato.net", "vulturenews.net", "foggia.today", "lagazzettadelmezzogiorno.it",
    "teatromercadantecerignola.it", "teatrogiordano.it",
    "palazzodelleartibeltrani.it", "politeamaitalia.com",
    "happyticket.com", "pugliaculture.it", "ciaotickets.com", "virgilio.it",
    "instagram.com", "facebook.com"
)

COMUNI_50KM = {
    "cerignola": "Cerignola",
    "stornara": "Stornara",
    "stornarella": "Stornarella",
    "orta nova": "Orta Nova",
    "san ferdinando di puglia": "San Ferdinando di Puglia",
    "san ferdinando": "San Ferdinando di Puglia",
    "trinitapoli": "Trinitapoli",
    "canosa di puglia": "Canosa di Puglia",
    "canosa": "Canosa di Puglia",
    "ordona": "Ordona",
    "carapelle": "Carapelle",
    "margherita di savoia": "Margherita di Savoia",
    "lavello": "Lavello",
    "ascoli satriano": "Ascoli Satriano",
    "zapponeta": "Zapponeta",
    "castelluccio dei sauri": "Castelluccio dei Sauri",
    "barletta": "Barletta",
    "candela": "Candela",
    "minervino murge": "Minervino Murge",
    "minervino": "Minervino Murge",
    "foggia": "Foggia",
    "melfi": "Melfi",
    "venosa": "Venosa",
    "deliceto": "Deliceto",
    "rapolla": "Rapolla",
    "andria": "Andria",
    "barile": "Barile",
    "palazzo san gervasio": "Palazzo San Gervasio",
    "rocchetta sant'antonio": "Rocchetta Sant'Antonio",
    "manfredonia": "Manfredonia",
    "rionero in vulture": "Rionero in Vulture",
    "rionero": "Rionero in Vulture",
    "trani": "Trani",
    "bovino": "Bovino",
    "spinazzola": "Spinazzola",
    "troia": "Troia",
    "lucera": "Lucera",
    "bisceglie": "Bisceglie",
    "monticchio": "Monticchio"
}

CINTURA_25 = {
    "Stornara", "Stornarella", "Orta Nova", "San Ferdinando di Puglia",
    "Trinitapoli", "Canosa di Puglia", "Ordona", "Carapelle",
    "Margherita di Savoia", "Lavello", "Ascoli Satriano"
}

CATEGORIE_AMMESSE = [
    "Musica & Concerti",
    "Locali & Serate",
    "Sagre & Food",
    "Famiglie & Bambini",
    "Natura & Escursioni",
    "Attività diurne"
]

PAROLE_SCARTO = [
    "adblocker", "ci stai leggendo", "archivio", "evento si è già concluso",
    "grande successo per", "si è concluso", "si è svolta", "si è svolto",
    "teatro", "teatrale", "prosa", "recital", "pianistico", "pianoforte",
    "sinfonica", "orchestra", "opera lirica", "drammaturgia", "monologo",
    "webinar", "online event", "evento online", "corso online", "formazione professionale",
    "networking aziendale", "b2b", "masterclass business", "zoom",
    "aula magna", "dipartimento", "università", "seminario", "convegno", "conferenza",
    "tavola rotonda", "dibattito", "diritto alla verità",
    "parrocchia", "parrocchie", "diocesi", "vescovo", "santa messa", "processione",
    "madre di san", "beato", "santo",
    "wedding", "sposi", "fiera sposi", "centro commerciale", "anniversario",
    "piantumazione", "alberi per il futuro", "giornata internazionale", "disabilità",
    "mostra fotografica", "scatti di", "vernissage", "esposizione fotografica",
    "presentazione libro", "presentazione del libro",
    "bando", "gara d'appalto", "affidamento", "delibera", "determina",
    "cronaca", "politica", "consiglio comunale", "giunta", "elezioni", "arresto", "incidente",
    "omicidio", "furto", "rapina", "sequestro", "carabinieri", "polizia", "guardia di finanza",
    "calcio", "volley", "basket", "torneo", "podistica", "maratona", "campionato", "audace cerignola"
]

REGEX_SCARTO = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in PAROLE_SCARTO) + r")\b", re.I)


def oggi_iso():
    return datetime.now().strftime("%Y-%m-%d")


def calendario_prossimi_giorni(giorni=21):
    nomi = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
    oggi = datetime.now()
    righe = []
    for i in range(giorni):
        d = oggi + timedelta(days=i)
        tag = " (OGGI)" if i == 0 else (" (DOMANI)" if i == 1 else "")
        righe.append(f"{nomi[d.weekday()]} {d.strftime('%Y-%m-%d')}{tag}")
    return ", ".join(righe)


def priorita_km(citta):
    if citta == "Cerignola":
        return 0
    if citta in CINTURA_25:
        return 1
    return 2


def risolvi_comune_50km(ev):
    c_raw = (ev.get("citta") or "").strip().lower()
    if c_raw in COMUNI_50KM:
        return COMUNI_50KM[c_raw]
    for k in sorted(COMUNI_50KM.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(k)}\b", c_raw):
            return COMUNI_50KM[k]
    altri = f"{ev.get('luogo', '')} {ev.get('titolo', '')} {ev.get('descrizione', '')}".lower()
    for k in sorted(COMUNI_50KM.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(k)}\b", altri):
            return COMUNI_50KM[k]
    return ""


def normalizza_cat(cat):
    c = (cat or "").strip().lower()
    for valid in CATEGORIE_AMMESSE:
        if c == valid.lower():
            return valid
    if any(k in c for k in ("musica", "concert", "live", "tribute", "band")):
        return "Musica & Concerti"
    if any(k in c for k in ("local", "serat", "dj", "club", "disco", "pub", "aperitiv", "karaoke")):
        return "Locali & Serate"
    if any(k in c for k in ("sagr", "food", "street", "degust", "gastronom", "enogastronom")):
        return "Sagre & Food"
    if any(k in c for k in ("famigl", "bambin", "natal", "luminar", "mercatin", "babbo", "ghiaccio", "pattinagg", "presep")):
        return "Famiglie & Bambini"
    if any(k in c for k in ("natur", "escursion", "trekking", "passeggiat", "salin", "riserva", "parco")):
        return "Natura & Escursioni"
    if any(k in c for k in ("diurn", "fiera", "artigian", "visita")):
        return "Attività diurne"
    return "Attività diurne"


def pulisci_evento(ev):
    citta = risolvi_comune_50km(ev)
    cat = normalizza_cat(ev.get("categoria"))
    url = (ev.get("fonteUrl") or "").strip()
    if not url.startswith("http"):
        url = ""

    d_ini = (ev.get("dataInizio") or "").strip()[:10]
    d_fin = (ev.get("dataFine") or d_ini).strip()[:10]
    luogo = re.sub(r"\s+", " ", (ev.get("luogo") or "")).strip()

    return {
        "tipoContenuto": "evento",
        "citta": citta,
        "categoria": cat,
        "titolo": re.sub(r"\s+", " ", (ev.get("titolo") or "")).strip()[:85],
        "dataTesto": re.sub(r"\s+", " ", (ev.get("dataTesto") or "")).strip(),
        "dataInizio": d_ini,
        "dataFine": d_fin,
        "luogo": luogo,
        "indirizzoMappa": (ev.get("indirizzoMappa") or (f"{luogo}, {citta}" if luogo else "")).strip(),
        "costo": (ev.get("costo") or "Da verificare").strip(),
        "descrizione": re.sub(r"\s+", " ", (ev.get("descrizione") or "")).strip()[:220],
        "fonteUrl": url
    }


def verifica_evento(ev):
    if not ev.get("citta"):
        return False, "fuori_raggio_50km"
    if not ev.get("fonteUrl") or not ev["fonteUrl"].startswith("http"):
        return False, "manca_fonte_url"
    if not ev.get("luogo"):
        return False, "manca_luogo"

    oggi = oggi_iso()
    limite_max = (datetime.now() + timedelta(days=GIORNI_ANTICIPO_MAX)).strftime("%Y-%m-%d")
    d1, d2 = ev.get("dataInizio", ""), ev.get("dataFine", "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d1) or not re.match(r"^\d{4}-\d{2}-\d{2}$", d2):
        return False, "formato_data"
    if d2 < oggi:
        return False, f"passato({d2})"
    if d1 > d2:
        return False, f"intervallo({d1}->{d2})"
    if d1 > limite_max:
        return False, f"oltre_{GIORNI_ANTICIPO_MAX}gg({d1})"

    titolo = ev.get("titolo", "")
    if len(titolo) < 5:
        return False, "titolo_corto"

    testo = f"{titolo} {ev.get('descrizione', '')} {ev.get('luogo', '')}"
    m = REGEX_SCARTO.search(testo)
    if m:
        return False, f"scarto({m.group(0)})"

    return True, "ok"


def ottieni_modelli_gemini(api_key):
    preferiti = [
        "gemini-2.5-flash",
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash"
    ]
    try:
        r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}", timeout=(5, 10))
        if r.status_code == 200:
            disponibili = [
                m.get("name", "").replace("models/", "")
                for m in r.json().get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", [])
            ]
            ordinati = [p for p in preferiti if p in disponibili]
            for d in disponibili:
                if "flash" in d and not any(x in d for x in ("image", "audio", "tts", "thinking")) and d not in ordinati:
                    ordinati.append(d)
            if ordinati:
                return ordinati[:5]
    except Exception:
        pass
    return preferiti[:4]


def cerca_eventi_web_con_gemini(api_key, area_query, cal_ref, oggi, limite_max):
    """Usa Gemini con Ricerca Google (google_search) su tutto il web per trovare eventi di tempo libero."""
    if not api_key:
        return [], False

    prompt = (
        f"Cerca su tutto il web (siti locali, pagine di eventi, locali, pagine social pubbliche, portali turistici) "
        f"eventi e attività reali per il tempo libero a {area_query} con date tra {oggi} e {limite_max}.\n"
        f"CALENDARIO DI RIFERIMENTO: {cal_ref}.\n"
        "COSA CERCARE:\n"
        "- Mercatini di Natale, luminarie con accensione/date, villaggi natalizi, piste di pattinaggio, Casa di Babbo Natale.\n"
        "- Musica dal vivo, concerti pop/rock/tribute, DJ set, serate nei pub/locali/club, aperitivi musicali, karaoke.\n"
        "- Sagre, street food, degustazioni, feste gastronomiche.\n"
        "- Escursioni, trekking non agonistico, passeggiate guidate, visite a saline/parchi/riserve, laboratori/attività per bambini.\n"
        "COSA ESCLUDERE:\n"
        "- Cronaca, incidenti, politica, consigli comunali, comunicati stampa, convegni, presentazioni libri, mostre fotografiche, "
        "teatro di prosa, musica classica/sinfonica, messe/processioni, sport agonistico/tornei ed eventi già passati.\n"
        "REGOLE TASSATIVE:\n"
        "- Usa SOLO eventi reali trovati tramite ricerca web, con data documentata e luogo reale.\n"
        "- Non inventare date né luoghi.\n"
        "- Rispondi SOLO con un JSON array puro (niente markdown ```json) dove ogni oggetto ha queste esatte chiavi:\n"
        '[{"tipoContenuto":"evento","citta":"...","categoria":"Musica & Concerti|Locali & Serate|Sagre & Food|Famiglie & Bambini|Natura & Escursioni|Attività diurne","titolo":"...","dataTesto":"...","dataInizio":"YYYY-MM-DD","dataFine":"YYYY-MM-DD","luogo":"...","indirizzoMappa":"...","costo":"...","descrizione":"...","fonteUrl":"https://..."}]'
    )

    modelli = ottieni_modelli_gemini(api_key)

    for mod in modelli:
        url = f"[https://generativelanguage.googleapis.com/v1beta/models/](https://generativelanguage.googleapis.com/v1beta/models/){mod}:generateContent?key={api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"temperature": 0.2}
        }
        try:
            r = requests.post(url, json=payload, timeout=(10, 45))
            if r.status_code in (429, 503):
                print(f"[Gemini Search] HTTP {r.status_code} su {mod} ({area_query}), attendo 8s...")
                time.sleep(8)
                continue
            if r.status_code != 200:
                print(f"[Gemini Search] HTTP {r.status_code} su {mod}: {r.text[:100]}")
                continue

            parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            raw = "\n".join(p.get("text", "") for p in parts if not p.get("thought") and p.get("text")).strip()
            raw_clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()
            m_arr = re.search(r"\[.*\]", raw_clean, flags=re.S)
            if not m_arr:
                continue
            dati = json.loads(m_arr.group(0))
            if isinstance(dati, list):
                print(f"[Gemini Search] {area_query} -> {len(dati)} candidati da {mod}.")
                return dati, True
        except Exception as e:
            print(f"[Gemini Search] Errore su {mod} ({area_query}): {str(e)[:75]}")
            continue

    return [], False


def sono_duplicati(a, b):
    if a.get("citta", "").lower() != b.get("citta", "").lower():
        return False
    if a.get("fonteUrl") and a.get("fonteUrl") == b.get("fonteUrl"):
        return True
    t1 = re.sub(r"[^a-z0-9\s]", "", a.get("titolo", "").lower())
    t2 = re.sub(r"[^a-z0-9\s]", "", b.get("titolo", "").lower())
    return SequenceMatcher(None, t1, t2).ratio() >= 0.68


def carica_esistenti_protetti(percorso_json="eventi.json"):
    oggi = oggi_iso()
    manuali = []
    auto_validi = []

    if not os.path.exists(percorso_json):
        return manuali, auto_validi

    try:
        with open(percorso_json, "r", encoding="utf-8") as f:
            dati = json.load(f)
        if not isinstance(dati, list):
            return manuali, auto_validi

        for item in dati:
            if not isinstance(item, dict) or item.get("tipoContenuto") != "evento":
                continue
            titolo = str(item.get("titolo") or "").strip()
            if len(titolo) < 3:
                continue

            url = str(item.get("fonteUrl") or "").strip().lower()
            is_manuale = bool(item.get("manuale")) or not any(dom in url for dom in DOMINI_AUTO)
            d_fin = str(item.get("dataFine") or item.get("dataInizio") or "").strip()[:10]

            if is_manuale:
                if not d_fin or not re.match(r"^\d{4}-\d{2}-\d{2}$", d_fin) or d_fin >= oggi:
                    manuali.append(item)
            else:
                if re.match(r"^\d{4}-\d{2}-\d{2}$", d_fin) and d_fin >= oggi:
                    auto_validi.append(item)
    except Exception as e:
        print(f"Avviso lettura {percorso_json}: {str(e)[:70]}")

    return manuali, auto_validi


def esegui_aggiornamento():
    t_start = time.time()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    oggi = oggi_iso()
    limite_max = (datetime.now() + timedelta(days=GIORNI_ANTICIPO_MAX)).strftime("%Y-%m-%d")
    cal_ref = calendario_prossimi_giorni(21)

    manuali_admin, precedenti_auto = carica_esistenti_protetti("eventi.json")
    print(f"Eventi protetti caricati: {len(manuali_admin)} manuali admin, {len(precedenti_auto)} automatici ancora validi.")

    aree_ricerca = [
        "Cerignola e comuni vicini (Stornara, Stornarella, Orta Nova, San Ferdinando di Puglia, Trinitapoli, Canosa di Puglia, Margherita di Savoia)",
        "dintorni entro 50 km da Cerignola (Barletta, Trani, Bisceglie, Andria, Foggia, Lavello, Venosa, Melfi, Ascoli Satriano)"
    ]

    nuovi_validi = []
    almeno_una_risposta_ok = False

    for area in aree_ricerca:
        candidati, ok = cerca_eventi_web_con_gemini(api_key, area, cal_ref, oggi, limite_max)
        if ok:
            almeno_una_risposta_ok = True
        for raw_ev in candidati:
            ev = pulisci_evento(raw_ev)
            valido, motivo = verifica_evento(ev)
            if valido:
                if not any(sono_duplicati(x, ev) for x in nuovi_validi):
                    nuovi_validi.append(ev)
            else:
                print(f"[Scarto] ({motivo}): {ev.get('citta') or '?'} - {ev.get('titolo')}")

    consolidati = list(manuali_admin)
    aggiunti_nuovi = 0
    for ev in nuovi_validi:
        if not any(sono_duplicati(x, ev) for x in consolidati):
            consolidati.append(ev)
            aggiunti_nuovi += 1

    # Mantiene sempre gli eventi automatici ancora validi precedenti (e in caso di errore API li preserva integralmente)
    for ev_old in precedenti_auto:
        if not any(sono_duplicati(x, ev_old) for x in consolidati):
            consolidati.append(ev_old)

    if not almeno_una_risposta_ok:
        print("[Avviso] Gemini non ha restituito risposta in questo run: preservati eventi manuali e precedenti validi.")

    lista_finale = sorted(
        consolidati,
        key=lambda x: (x.get("dataInizio", "9999-12-31"), priorita_km(x.get("citta", "")), x.get("titolo", "").lower())
    )

    with open("eventi.json", "w", encoding="utf-8") as f:
        json.dump(lista_finale, f, ensure_ascii=False, indent=2)

    report = {
        "aggiornatoAl": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "totaleContenuti": len(lista_finale),
        "nuoviAggiunti": aggiunti_nuovi,
        "manualiConservati": len(manuali_admin),
        "topComuni": dict(Counter(e.get("citta", "") for e in lista_finale).most_common(15))
    }
    with open("report_copertura.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Fine: {len(lista_finale)} eventi totali salvati ({aggiunti_nuovi} nuovi, {len(manuali_admin)} manuali) in {int(time.time() - t_start)}s")


if __name__ == "__main__":
    esegui_aggiornamento()
