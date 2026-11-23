import os
import re
import sys
import json
import time
import requests
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

GIORNI_ANTICIPO_MAX = 45
ABILITA_GEMINI_OPZIONALE = os.environ.get("ABILITA_GEMINI", "0").strip() == "1"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9"
}

DOMINI_AUTO = (
    "news.google.com", "iltaccodibacco.it", "viaggiareinpuglia.it",
    "pugliaevents.it", "eventiesagre.it", "eventbrite.it",
    "lanotiziaweb.it", "marchiodoc.it", "cerignolaviva.it",
    "canosaviva.it", "barlettaviva.it", "traniviva.it",
    "bisceglieviva.it", "andriaviva.it", "statoquotidiano.it",
    "immediato.net", "vulturenews.net",
    "teatromercadantecerignola.it", "teatrogiordano.it",
    "palazzodelleartibeltrani.it", "politeamaitalia.com",
    "happyticket.com", "pugliaculture.it", "ciaotickets.com", "virgilio.it"
)

FONTI_VIVA = [
    {"nome": "CerignolaViva - Eventi", "url": "https://www.cerignolaviva.it/eventi/", "dominio": "cerignolaviva.it", "citta_default": "Cerignola", "solo_eventi": True},
    {"nome": "CerignolaViva - Eventi e Cultura", "url": "https://www.cerignolaviva.it/cultura/", "dominio": "cerignolaviva.it", "citta_default": "Cerignola", "solo_eventi": False},
    {"nome": "CerignolaViva - Notizie", "url": "https://www.cerignolaviva.it/notizie/", "dominio": "cerignolaviva.it", "citta_default": "Cerignola", "solo_eventi": False},
    {"nome": "CerignolaViva - Vita di città", "url": "https://www.cerignolaviva.it/vita-di-citta/", "dominio": "cerignolaviva.it", "citta_default": "Cerignola", "solo_eventi": False},
    {"nome": "CanosaViva - Eventi", "url": "https://www.canosaviva.it/eventi/", "dominio": "canosaviva.it", "citta_default": "Canosa di Puglia", "solo_eventi": True},
    {"nome": "CanosaViva - Eventi e Cultura", "url": "https://www.canosaviva.it/cultura/", "dominio": "canosaviva.it", "citta_default": "Canosa di Puglia", "solo_eventi": False},
    {"nome": "CanosaViva - Notizie", "url": "https://www.canosaviva.it/notizie/", "dominio": "canosaviva.it", "citta_default": "Canosa di Puglia", "solo_eventi": False},
    {"nome": "CanosaViva - Vita di città", "url": "https://www.canosaviva.it/vita-di-citta/", "dominio": "canosaviva.it", "citta_default": "Canosa di Puglia", "solo_eventi": False},
    {"nome": "BarlettaViva - Eventi", "url": "https://www.barlettaviva.it/eventi/", "dominio": "barlettaviva.it", "citta_default": "Barletta", "solo_eventi": True},
    {"nome": "BarlettaViva - Cultura", "url": "https://www.barlettaviva.it/cultura/", "dominio": "barlettaviva.it", "citta_default": "Barletta", "solo_eventi": False},
    {"nome": "BarlettaViva - Notizie", "url": "https://www.barlettaviva.it/notizie/", "dominio": "barlettaviva.it", "citta_default": "Barletta", "solo_eventi": False},
    {"nome": "TraniViva - Eventi", "url": "https://www.traniviva.it/eventi/", "dominio": "traniviva.it", "citta_default": "Trani", "solo_eventi": True},
    {"nome": "TraniViva - Cultura", "url": "https://www.traniviva.it/cultura/", "dominio": "traniviva.it", "citta_default": "Trani", "solo_eventi": False},
    {"nome": "BisceglieViva - Eventi", "url": "https://www.bisceglieviva.it/eventi/", "dominio": "bisceglieviva.it", "citta_default": "Bisceglie", "solo_eventi": True},
    {"nome": "BisceglieViva - Cultura", "url": "https://www.bisceglieviva.it/cultura/", "dominio": "bisceglieviva.it", "citta_default": "Bisceglie", "solo_eventi": False},
    {"nome": "AndriaViva - Eventi", "url": "https://www.andriaviva.it/eventi/", "dominio": "andriaviva.it", "citta_default": "Andria", "solo_eventi": True},
    {"nome": "AndriaViva - Cultura", "url": "https://www.andriaviva.it/cultura/", "dominio": "andriaviva.it", "citta_default": "Andria", "solo_eventi": False}
]

FONTI_TACCO = [
    {"nome": "Il Tacco di Bacco BAT", "url": "https://iltaccodibacco.it/barletta/", "dominio": "iltaccodibacco.it"},
    {"nome": "Il Tacco di Bacco Foggia", "url": "https://iltaccodibacco.it/foggia/", "dominio": "iltaccodibacco.it"}
]

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

MESI_IT = {
    "gennaio": 1, "gen": 1,
    "febbraio": 2, "feb": 2,
    "marzo": 3, "mar": 3,
    "aprile": 4, "apr": 4,
    "maggio": 5, "mag": 5,
    "giugno": 6, "giu": 6,
    "luglio": 7, "lug": 7,
    "agosto": 8, "ago": 8,
    "settembre": 9, "set": 9, "sett": 9,
    "ottobre": 10, "ott": 10,
    "novembre": 11, "nov": 11,
    "dicembre": 12, "dic": 12
}

NOMI_MESI_BREVI = {
    1: "Gen", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mag", 6: "Giu",
    7: "Lug", 8: "Ago", 9: "Set", 10: "Ott", 11: "Nov", 12: "Dic"
}

NOMI_GIORNI_BREVI = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]

# Filtro tematico positivo rigoroso: NON ammette parole generiche come "evento", "festa", "musica", "natale", "weekend"
REGEX_TEMA_COERENTE = re.compile(
    r"\b(?:"
    # Natale e iniziative tematiche aperte al pubblico
    r"mercatin[oi]\s+di\s+natale|mercatin[oi]\s+nataliz\w*|mercatin[oi]\s+enogastronomic\w*|mercatin[oi]\s+artigianal\w*|"
    r"luminari[ae]|accensione\s+(?:delle\s+)?luminari[ae]|accensione\s+(?:dell['’]\s*)?albero|"
    r"villaggi[o]?\s+di\s+natale|villaggi[o]?\s+natalizi[o]?|villaggi[o]?\s+di\s+babbo\s+natale|"
    r"casa\s+di\s+babbo\s+natale|pist[ae]\s+di\s+pattinaggio|pist[ae]\s+di\s+ghiaccio|presepe\s+vivente|"
    # Musica e divertimento
    r"musica\s+dal\s+vivo|musica\s+live|live\s+music|tribute\s+band|cover\s+band|"
    r"concerto\s+(?:pop|rock|live|tribute|di\s+natale|in\s+piazza)|concerti\s+(?:pop|rock|live)|"
    r"dj\s*set|discotec[ah]|club\s+night|aperitiv[oi]\s+musical\w*|karaoke|"
    r"serat[ae]\s+(?:live|musical\w*|in\s+piazza|al\s+pub|nel\s+locale|danza|latina|disco)|"
    r"festa\s+in\s+piazza|festa\s+di\s+piazza|festa\s+patronale|festa\s+di\s+paese|"
    # Sagre e gastronomia
    r"sagr[ae]|street\s+food|degustazion[ei]|festa\s+gastronomic[ah]|percorso\s+enogastronomic[o]|caldarroste|prodotti\s+tipici|"
    # Famiglie e bambini
    r"laboratori[o]?\s+per\s+bambini|laboratori[o]?\s+creativ[oi]|animazione\s+per\s+bambini|"
    r"spettacol[oi]\s+per\s+famiglie|spettacol[oi]\s+di\s+intrattenimento|festa\s+per\s+bambini|"
    r"fattori[ae]\s+didattic[ah]|parco\s+tematico|"
    # Natura ed escursioni
    r"trekking|escursion[ei]|passeggiat[ae]\s+naturalistic[ah]|passeggiat[ae]\s+guidat[ah]|"
    r"uscit[ae]\s+organizzat[ah]|visita\s+guidata\s+(?:alle\s+saline|al\s+parco|alla\s+riserva|ai\s+laghi|al\s+castello|al\s+borgo)|"
    r"visita\s+alle\s+saline|riserva\s+naturale|attivit[aà]\s+all['’]aperto|"
    # Attività diurne ricreative
    r"fiera\s+ricreativa|fiera\s+artigianale|esperienz[ae]\s+artigianal\w*"
    r")\b",
    re.I
)

# Classi di scarto distinte per il report di qualità
CLASSI_SCARTO = {
    "cronaca": [
        "cronaca", "incidente", "incidenti", "arresto", "arresti", "indagine", "indagini",
        "omicidio", "furto", "rapina", "sequestro", "carabinieri", "polizia", "guardia di finanza",
        "tribunale", "politica", "consiglio comunale", "giunta", "elezioni", "sindaco", "assessore",
        "comunicato stampa", "comunicazione istituzionale", "inaugurazione istituzionale",
        "taglio del nastro", "conferenza stampa", "bando", "gara d'appalto", "affidamento",
        "delibera", "determina"
    ],
    "passati": [
        "evento si è già concluso", "si è concluso", "si è conclusa",
        "si è svolto", "si è svolta", "si sono svolti", "si sono svolte",
        "si è tenuto", "si è tenuta", "è andata in scena", "è andato in scena",
        "grande successo per", "bilancio positivo", "bilancio più che positivo",
        "ha riscosso", "archivio", "evento concluso"
    ],
    "non_pertinenti": [
        "convegno", "convegni", "conferenza", "conferenze", "seminario", "seminari",
        "tavola rotonda", "dibattito", "aula magna", "dipartimento", "università",
        "presentazione libro", "presentazione del libro", "presentazione del volume",
        "mostra fotografica", "vernissage", "esposizione fotografica", "galleria d'arte",
        "teatro di prosa", "stagione teatrale", "prosa", "opera lirica", "drammaturgia", "monologo",
        "concerto sinfonico", "orchestra sinfonica", "sinfonica", "musica classica",
        "recital pianistico", "pianoforte", "musica da camera", "conservatorio",
        "santa messa", "messa solenne", "processione", "parrocchia", "parrocchie",
        "diocesi", "vescovo", "liturgia",
        "sport agonistico", "torneo", "tornei", "campionato", "campionati",
        "gara podistica", "maratona", "mezza maratona", "partita",
        "calcio", "volley", "basket", "audace cerignola",
        "webinar", "evento online", "corso online", "b2b",
        "wedding", "fiera sposi", "adblocker", "ci stai leggendo"
    ]
}

PAROLE_SCARTO = [w for grp in CLASSI_SCARTO.values() for w in grp]
REGEX_SCARTO = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in PAROLE_SCARTO) + r")\b", re.I)

REGEX_SCARTO_CRONACA = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in CLASSI_SCARTO["cronaca"]) + r")\b", re.I)
REGEX_SCARTO_PASSATI = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in CLASSI_SCARTO["passati"]) + r")\b", re.I)
REGEX_SCARTO_NON_PERT = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in CLASSI_SCARTO["non_pertinenti"]) + r")\b", re.I)

ESCLUSIONI_PATH_VIVA = (
    "/cronaca/", "/politica/", "/sport/", "/necrologi/", "/meteo/",
    "/farmacie/", "/oroscopo/", "/redazione/", "/contatti/", "/pubblicita/",
    "/privacy/", "/cookie/", "/chi-siamo/", "/tag/", "/autore/",
    "/page/", "/pagina/", "/archivio/", "/cerca/", "/feed/", "/rss/",
    "/wp-admin/", "/wp-content/", "/login/", "/registrati/", "/oggi/", "/domani/", "/weekend/"
)

CHIAVI_OBBLIGATORIE = (
    "tipoContenuto", "citta", "categoria", "titolo",
    "dataTesto", "dataInizio", "dataFine", "luogo",
    "indirizzoMappa", "costo", "descrizione", "fonteUrl"
)


def nuovo_report_qualita():
    return {
        "eventiPertinenti": 0,
        "candidatiNonPertinentiScartati": 0,
        "articoliCronacaScartati": 0,
        "eventiPassatiScartati": 0,
        "dateNonVerificabili": 0,
        "comuniFuoriRaggio": 0,
        "fontiNonRaggiungibili": 0,
        "eventiSenzaLuogoODataCerta": 0
    }


def classifica_motivo_scarto(testo):
    t = testo or ""
    m_cr = REGEX_SCARTO_CRONACA.search(t)
    if m_cr:
        return "cronaca", f"cronaca({m_cr.group(0)})"
    m_pa = REGEX_SCARTO_PASSATI.search(t)
    if m_pa:
        return "passati", f"passato({m_pa.group(0)})"
    m_np = REGEX_SCARTO_NON_PERT.search(t)
    if m_np:
        return "non_pertinenti", f"non_pertinente({m_np.group(0)})"
    return "", ""


def registra_scarto_nel_report(rq, categoria_scarto):
    if not rq:
        return
    if categoria_scarto == "cronaca":
        rq["articoliCronacaScartati"] += 1
        rq["candidatiNonPertinentiScartati"] += 1
    elif categoria_scarto == "passati":
        rq["eventiPassatiScartati"] += 1
    elif categoria_scarto == "non_pertinenti":
        rq["candidatiNonPertinentiScartati"] += 1
    elif categoria_scarto == "date_non_verificabili":
        rq["dateNonVerificabili"] += 1
        rq["eventiSenzaLuogoODataCerta"] += 1
    elif categoria_scarto == "luogo_non_documentato":
        rq["eventiSenzaLuogoODataCerta"] += 1
    elif categoria_scarto == "fuori_raggio":
        rq["comuniFuoriRaggio"] += 1


def oggi_dt():
    return datetime.now()


def oggi_iso(ref_dt=None):
    return (ref_dt or oggi_dt()).strftime("%Y-%m-%d")


def priorita_km(citta):
    if citta == "Cerignola":
        return 0
    if citta in CINTURA_25:
        return 1
    return 2


def risolvi_comune_50km(testo_o_ev):
    if isinstance(testo_o_ev, dict):
        c_raw = (testo_o_ev.get("citta") or "").strip().lower()
        if c_raw in COMUNI_50KM:
            return COMUNI_50KM[c_raw]
        for k in sorted(COMUNI_50KM.keys(), key=len, reverse=True):
            if re.search(rf"\b{re.escape(k)}\b", c_raw):
                return COMUNI_50KM[k]
        testo = f"{testo_o_ev.get('luogo', '')} {testo_o_ev.get('titolo', '')} {testo_o_ev.get('descrizione', '')}".lower()
    else:
        testo = str(testo_o_ev or "").lower()

    for k in sorted(COMUNI_50KM.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(k)}\b", testo):
            return COMUNI_50KM[k]
    return ""


def classifica_categoria(testo):
    t = (testo or "").lower()
    if any(k in t for k in ("escursion", "trekking", "passeggiat", "camminat", "visita guidata", "visita alle saline", "riserva naturale", "saline", "monticchio", "murgia", "incoronata")):
        return "Natura & Escursioni"
    if any(k in t for k in ("sagra", "sagre", "street food", "degustazion", "enogastronom", "festa gastronomica", "caldarroste", "prodotti tipici")):
        return "Sagre & Food"
    if any(k in t for k in ("dj set", "dj-set", "club night", "discotec", "serata al pub", "serata nel locale", "serata disco", "serata latina", "aperitivo musicale", "aperitivi musicali", "karaoke")):
        return "Locali & Serate"
    if any(k in t for k in ("concerto", "concerti", "musica dal vivo", "musica live", "live music", "tribute band", "cover band", "festa in piazza", "festa di piazza", "festa patronale", "festa di paese")):
        return "Musica & Concerti"
    if any(k in t for k in ("luminari", "mercatini di natale", "mercatino di natale", "mercatini nataliz", "villaggio di natale", "villaggio nataliz", "villaggio di babbo natale", "casa di babbo natale", "pista di pattinaggio", "pista di ghiaccio", "presepe vivente", "laboratori per bambini", "laboratorio per bambini", "laboratori creativi", "animazione per bambini", "spettacolo per famiglie", "festa per bambini", "fattoria didattica", "fattorie didattiche", "parco tematico")):
        return "Famiglie & Bambini"
    return "Attività diurne"


def formatta_data_italiano(d_ini_iso, d_fin_iso):
    try:
        dt1 = datetime.strptime(d_ini_iso, "%Y-%m-%d")
        dt2 = datetime.strptime(d_fin_iso, "%Y-%m-%d")
        g1 = f"{NOMI_GIORNI_BREVI[dt1.weekday()]} {dt1.day:02d} {NOMI_MESI_BREVI[dt1.month]} {dt1.year}"
        if dt1.date() == dt2.date():
            return g1
        g2 = f"{dt2.day:02d} {NOMI_MESI_BREVI[dt2.month]} {dt2.year}"
        return f"Dal {dt1.day:02d} {NOMI_MESI_BREVI[dt1.month]} al {g2}"
    except Exception:
        return d_ini_iso


def _costruisci_data_sicura(giorno, mese, anno):
    try:
        return datetime(int(anno), int(mese), int(giorno))
    except ValueError:
        return None


def _inferisci_anno(giorno, mese, anno_str, ref_dt):
    if anno_str:
        return _costruisci_data_sicura(giorno, mese, int(anno_str))
    anno = ref_dt.year
    if mese < ref_dt.month - 2:
        anno += 1
    return _costruisci_data_sicura(giorno, mese, anno)


def rimuovi_riferimenti_pubblicazione(testo):
    """Rimuove date di pubblicazione, aggiornamento e dateline giornalistiche per non confonderle con la data dell'evento."""
    t = re.sub(r"\s+", " ", (testo or "")).strip()
    mesi_pat = "|".join(MESI_IT.keys())
    # Dateline iniziale articolo: "CERIGNOLA, 23 novembre 2026 - ..." o "23 novembre 2026 - ..."
    t = re.sub(
        rf"^(?:[A-ZÀ-Ü\s']+,\s*)?\d{{1,2}}(?:\s+(?:{mesi_pat})|[/.-]\d{{1,2}})(?:\s+|[/.-])20\d{{2}}\s*[-–—:]\s*",
        " ",
        t,
        flags=re.I
    )
    # "Pubblicato il 23 novembre 2026", "Aggiornato il 23/11/2026", "Ultimo aggiornamento: ..."
    t = re.sub(
        rf"\b(?:pubblicato|aggiornato|ultimo\s+aggiornamento|inserito|redazione|scritto)\s*(?:il|in\s+data|:)?\s*\d{{1,2}}(?:\s+(?:{mesi_pat})|[/.-]\d{{1,2}})(?:\s+|[/.-])20\d{{2}}(?:\s*(?:alle|ore|-)?\s*\d{{1,2}}[:.]\d{{2}})?",
        " ",
        t,
        flags=re.I
    )
    # "23 novembre 2026 - Redazione" o "23/11/2026 - di Mario Rossi"
    t = re.sub(
        rf"\b\d{{1,2}}(?:\s+(?:{mesi_pat})|[/.-]\d{{1,2}})(?:\s+|[/.-])20\d{{2}}\s*[-–|]\s*(?:redazione|di\s+[a-z]+)",
        " ",
        t,
        flags=re.I
    )
    return re.sub(r"\s+", " ", t).strip()


def estrai_date_italiano(testo, ref_dt=None, ignora_pubblicazione=True):
    """Estrae esclusivamente date o intervalli espliciti documentati dalla fonte. Mai date inventate."""
    ref = ref_dt or oggi_dt()
    sorgente = rimuovi_riferimenti_pubblicazione(testo) if ignora_pubblicazione else (testo or "")
    t = re.sub(r"\s+", " ", sorgente).strip().lower()
    mesi_pat = "|".join(MESI_IT.keys())
    prep_al = r"(?:al|all['’]|allo|alla|ai|agli|alle|-|–|—)"

    # 1. Intervallo tra due mesi diversi: "dal 29 nov al 2 dic 2026" o "dal 6 dicembre 2026 al 6 gennaio 2027"
    m = re.search(
        rf"\b(?:dal(?:l['’]|lo|la)?\s+)?(\d{{1,2}})\s+({mesi_pat})(?:\s+(20\d{{2}}))?\s*{prep_al}\s*(\d{{1,2}})\s+({mesi_pat})(?:\s+(20\d{{2}}))?\b",
        t
    )
    if m:
        g1, m1_s, a1_s, g2, m2_s, a2_s = m.groups()
        m1, m2 = MESI_IT[m1_s], MESI_IT[m2_s]
        dt2 = _inferisci_anno(int(g2), m2, a2_s, ref)
        if dt2:
            anno1 = int(a1_s) if a1_s else (dt2.year - 1 if m1 > m2 else dt2.year)
            dt1 = _costruisci_data_sicura(int(g1), m1, anno1)
            if dt1 and dt1 <= dt2:
                d1, d2 = dt1.strftime("%Y-%m-%d"), dt2.strftime("%Y-%m-%d")
                return d1, d2, formatta_data_italiano(d1, d2)

    # 2. Intervallo nello stesso mese: "dal 28 al 30 novembre 2026" o "dal 6 all'8 dicembre 2026"
    m = re.search(
        rf"\b(?:dal(?:l['’]|lo|la)?\s+)?(\d{{1,2}})\s*(?:{prep_al}|e)\s*(\d{{1,2}})\s+({mesi_pat})(?:\s+(20\d{{2}}))?\b",
        t
    )
    if m:
        g1, g2, m_s, a_s = m.groups()
        mese = MESI_IT[m_s]
        dt1 = _inferisci_anno(int(g1), mese, a_s, ref)
        dt2 = _inferisci_anno(int(g2), mese, a_s, ref)
        if dt1 and dt2 and dt1 <= dt2:
            d1, d2 = dt1.strftime("%Y-%m-%d"), dt2.strftime("%Y-%m-%d")
            return d1, d2, formatta_data_italiano(d1, d2)

    # 3. Data singola in italiano: "28 novembre 2026" o "sabato 28 novembre"
    m = re.search(
        rf"\b(\d{{1,2}})\s+({mesi_pat})(?:\s+(20\d{{2}}))?\b",
        t
    )
    if m:
        g1, m_s, a_s = m.groups()
        dt1 = _inferisci_anno(int(g1), MESI_IT[m_s], a_s, ref)
        if dt1:
            d1 = dt1.strftime("%Y-%m-%d")
            return d1, d1, formatta_data_italiano(d1, d1)

    # 4. Intervallo numerico: "28/11/2026 - 30/11/2026" o "dal 28/11 al 30/11/2026"
    m = re.search(
        rf"\b(?:dal(?:l['’])?\s+)?(\d{{1,2}})[/.-](\d{{1,2}})(?:[/.-](20\d{{2}}))?\s*{prep_al}\s*(\d{{1,2}})[/.-](\d{{1,2}})(?:[/.-](20\d{{2}}))?\b",
        t
    )
    if m:
        g1, m1_s, a1_s, g2, m2_s, a2_s = m.groups()
        dt2 = _inferisci_anno(int(g2), int(m2_s), a2_s, ref)
        if dt2:
            anno1 = int(a1_s) if a1_s else (dt2.year - 1 if int(m1_s) > int(m2_s) else dt2.year)
            dt1 = _costruisci_data_sicura(int(g1), int(m1_s), anno1)
            if dt1 and dt1 <= dt2:
                d1, d2 = dt1.strftime("%Y-%m-%d"), dt2.strftime("%Y-%m-%d")
                return d1, d2, formatta_data_italiano(d1, d2)

    # 5. Data numerica singola con anno: "06/12/2026" o "06-12-2026"
    m = re.search(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b", t)
    if m:
        g1, m1_s, a1_s = m.groups()
        dt1 = _costruisci_data_sicura(int(g1), int(m1_s), int(a1_s))
        if dt1:
            d1 = dt1.strftime("%Y-%m-%d")
            return d1, d1, formatta_data_italiano(d1, d1)

    return "", "", ""


def estrai_eventi_jsonld(obj, trovati):
    if isinstance(obj, list):
        for item in obj:
            estrai_eventi_jsonld(item, trovati)
    elif isinstance(obj, dict):
        t = obj.get("@type", "")
        tipi = t if isinstance(t, list) else [t]
        if any("Event" in str(x) for x in tipi) and obj.get("name"):
            trovati.append(obj)
        for v in obj.values():
            if isinstance(v, (dict, list)):
                estrai_eventi_jsonld(v, trovati)


def estrai_luogo_documentato(testo_o_soup, citta=""):
    """Estrae un luogo fisico reale solo se documentato nel testo. Non inventa mai 'Centro / Piazze'."""
    if hasattr(testo_o_soup, "get_text"):
        testo_pag = testo_o_soup.get_text("\n", strip=True)
    else:
        testo_pag = str(testo_o_soup or "")

    # 1. Etichette esplicite su riga dedicata (es. "Dove: Piazza Duomo", "Presso: ...")
    for raw_line in testo_pag.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if len(line) < 5 or len(line) > 130:
            continue
        m_dove = re.match(r"^(?:dove|luogo|presso|location|sede|indirizzo)\s*:\s*(.+)$", line, re.I)
        if m_dove:
            cand = re.split(r"\s+(?:a|ad|in)\s+[A-ZÀ-Ü]", m_dove.group(1).strip())[0].strip(" ,.;:-")
            if len(cand) >= 4 and cand.lower() not in ("da definire", "da verificare", "n/d", citta.lower()):
                return cand[:80]

    # 2. Espressioni di luogo fisico nel corpo del testo
    testo_flat = re.sub(r"\s+", " ", testo_pag)
    pat_luoghi = (
        r"\b(?:in|presso|al|allo|alla|ai|agli|alle|nel|nello|nella|sul|sulla|lungo)\s+"
        r"((?:Piazza|Piazzale|Largo|Corso|Via|Viale|Villa\s+Comunale|Parco|Giardini|Castello|Palazzo|"
        r"Saline|Riserva\s+Naturale|Bosco|Laghi\s+di|Lago\s+di|Lungomare|Arena|Anfiteatro|Chiostro|"
        r"Borgo\s+Antico|Centro\s+Storico|Masseria|Fattoria\s+Didattica|Pub|Club|Discoteca|Lounge|"
        r"Cantina|Pala\w*|Auditorium)\s+[A-Za-zÀ-ü0-9'’.\-\s]{2,55})"
    )
    m = re.search(pat_luoghi, testo_flat, re.I)
    if m:
        grezzo = m.group(1)
        pulito = re.split(
            r"(?:[,.;!?]|\s+(?:a|ad|in|nel|nella|il|lo|la|dal|dalle|con|per|dove|che|in\s+programma)\b)",
            grezzo,
            flags=re.I
        )[0].strip(" ,.;:-")
        if len(pulito) >= 4 and pulito.lower() not in ("da definire", "da verificare", "n/d", citta.lower()):
            return pulito[:80]

    return ""


def estrai_costo_documentato(testo_o_soup):
    if hasattr(testo_o_soup, "get_text"):
        testo_pag = testo_o_soup.get_text("\n", strip=True)
    else:
        testo_pag = str(testo_o_soup or "")

    for raw_line in testo_pag.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if len(line) < 5 or len(line) > 130:
            continue
        m_costo = re.match(r"^(?:ingresso|costo|prezzo|biglietti|quota)\s*:\s*(.+)$", line, re.I)
        if m_costo:
            return m_costo.group(1).strip()[:70]

    m_inline = re.search(r"\b(ingresso\s+(?:libero|gratuito)|gratuito|a\s+pagamento|€\s*\d+(?:[.,]\d{2})?)\b", testo_pag, re.I)
    if m_inline:
        return m_inline.group(1).strip().capitalize()

    return "Non specificato nella fonte"


def normalizza_e_valida_evento(raw, ref_dt=None, ignora_pubblicazione=True, rq=None):
    ref = ref_dt or oggi_dt()
    oggi = oggi_iso(ref)
    limite_max = (ref + timedelta(days=GIORNI_ANTICIPO_MAX)).strftime("%Y-%m-%d")

    titolo = re.sub(r"\s+", " ", str(raw.get("titolo") or "")).strip()[:85]
    descrizione = re.sub(r"\s+", " ", str(raw.get("descrizione") or "")).strip()[:220]
    luogo = re.sub(r"\s+", " ", str(raw.get("luogo") or "")).strip()
    url = str(raw.get("fonteUrl") or "").strip()

    if len(titolo) < 5:
        return None, "titolo_corto"
    if not url.startswith("http"):
        return None, "url_non_valido"

    testo_check = f"{titolo} {descrizione} {luogo}"

    # 1. Controllo scarti categorizzati (cronaca, passati, non pertinenti)
    cat_scarto, motivo_scarto = classifica_motivo_scarto(testo_check)
    if cat_scarto:
        registra_scarto_nel_report(rq, cat_scarto)
        return None, motivo_scarto

    # 2. Controllo pertinenza tematica per il tempo libero
    if not REGEX_TEMA_COERENTE.search(testo_check):
        registra_scarto_nel_report(rq, "non_pertinenti")
        return None, "tema_non_ricreativo"

    # 3. Controllo comune entro 50 km
    citta = risolvi_comune_50km(raw)
    if not citta:
        registra_scarto_nel_report(rq, "fuori_raggio")
        return None, "fuori_raggio_50km"

    # 4. Controllo data reale documentata (mai inventata)
    d1 = str(raw.get("dataInizio") or "").strip()[:10]
    d2 = str(raw.get("dataFine") or d1).strip()[:10]
    d_txt = str(raw.get("dataTesto") or "").strip()

    if not (re.match(r"^\d{4}-\d{2}-\d{2}$", d1) and re.match(r"^\d{4}-\d{2}-\d{2}$", d2)):
        d1, d2, d_txt = estrai_date_italiano(f"{titolo} {descrizione} {d_txt}", ref, ignora_pubblicazione=ignora_pubblicazione)

    if not (re.match(r"^\d{4}-\d{2}-\d{2}$", d1) and re.match(r"^\d{4}-\d{2}-\d{2}$", d2)):
        registra_scarto_nel_report(rq, "date_non_verificabili")
        return None, "data_non_verificabile"
    if d2 < oggi:
        registra_scarto_nel_report(rq, "passati")
        return None, f"passato({d2})"
    if d1 > d2:
        registra_scarto_nel_report(rq, "date_non_verificabili")
        return None, f"intervallo_invalido({d1}>{d2})"
    if d1 > limite_max:
        registra_scarto_nel_report(rq, "date_non_verificabili")
        return None, f"oltre_{GIORNI_ANTICIPO_MAX}gg({d1})"

    # 5. Controllo luogo fisico realmente documentato (mai 'Centro / Piazze' inventato)
    if not luogo or luogo.lower() in ("da definire", "da verificare", "n/d", "centro / piazze", citta.lower()):
        luogo = estrai_luogo_documentato(f"{titolo}\n{descrizione}", citta)
    if not luogo:
        registra_scarto_nel_report(rq, "luogo_non_documentato")
        return None, "luogo_non_documentato"

    cat = str(raw.get("categoria") or "").strip()
    if cat not in CATEGORIE_AMMESSE:
        cat = classifica_categoria(f"{titolo} {descrizione}")

    if not d_txt:
        d_txt = formatta_data_italiano(d1, d2)

    costo = str(raw.get("costo") or "").strip() or "Non specificato nella fonte"
    desc_finale = rimuovi_riferimenti_pubblicazione(descrizione) if descrizione else ""
    if len(desc_finale) < 15:
        desc_finale = f"{titolo} presso {luogo} ({citta})."

    ev_pulito = {
        "tipoContenuto": "evento",
        "citta": citta,
        "categoria": cat,
        "titolo": titolo,
        "dataTesto": d_txt,
        "dataInizio": d1,
        "dataFine": d2,
        "luogo": luogo,
        "indirizzoMappa": (str(raw.get("indirizzoMappa") or "").strip() or f"{luogo}, {citta}"),
        "costo": costo,
        "descrizione": desc_finale[:220],
        "fonteUrl": url
    }
    if rq:
        rq["eventiPertinenti"] += 1
    return ev_pulito, "ok"


# ==============================================================================
# PARSER DEDICATO IL TACCO DI BACCO
# ==============================================================================
def analizza_pagina_tacco(html_text, page_url, citta_default="", ref_dt=None, rq=None):
    ref = ref_dt or oggi_dt()
    soup = BeautifulSoup(html_text, "html.parser")
    risultati = []

    eventi_ld = []
    for sc in soup.find_all("script", type="application/ld+json"):
        try:
            dati = json.loads(sc.string or "")
            estrai_eventi_jsonld(dati, eventi_ld)
        except Exception:
            continue

    for ev_ld in eventi_ld[:3]:
        titolo = re.sub(r"\s+", " ", str(ev_ld.get("name") or "")).strip()
        d1 = str(ev_ld.get("startDate") or "").strip()[:10]
        d2 = str(ev_ld.get("endDate") or d1).strip()[:10]
        loc = ev_ld.get("location") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        luogo_nome = loc.get("name", "") if isinstance(loc, dict) else ""
        addr = loc.get("address", {}) if isinstance(loc, dict) else {}
        localita = addr.get("addressLocality", citta_default) if isinstance(addr, dict) else citta_default
        via = addr.get("streetAddress", "") if isinstance(addr, dict) else ""
        desc = re.sub(r"\s+", " ", str(ev_ld.get("description") or "")).strip()
        offers = ev_ld.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        prezzo = offers.get("price", "") if isinstance(offers, dict) else ""
        costo = f"€ {prezzo}" if str(prezzo).strip() not in ("", "0", "0.00") else ("Ingresso gratuito" if str(prezzo).strip() in ("0", "0.00") else "Non specificato nella fonte")

        candidato = {
            "citta": localita or citta_default,
            "titolo": titolo,
            "dataInizio": d1,
            "dataFine": d2,
            "dataTesto": formatta_data_italiano(d1, d2) if re.match(r"^\d{4}-\d{2}-\d{2}$", d1) else "",
            "luogo": luogo_nome,
            "indirizzoMappa": f"{luogo_nome} {via}, {localita or citta_default}".strip(" ,"),
            "costo": costo,
            "descrizione": desc,
            "fonteUrl": page_url
        }
        ev_ok, _ = normalizza_e_valida_evento(candidato, ref, ignora_pubblicazione=True, rq=rq)
        if ev_ok:
            risultati.append(ev_ok)

    if risultati:
        return risultati

    h1 = soup.find("h1")
    titolo = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else ""
    if not titolo:
        og_t = soup.find("meta", property="og:title")
        titolo = re.sub(r"\s+", " ", og_t.get("content", "")).strip() if og_t else ""

    if len(titolo) < 5:
        return []

    for tag in soup(["script", "style", "nav", "footer", "aside", "form", "noscript", "iframe"]):
        tag.decompose()

    cont = soup.find("article") or soup.find("main") or soup.body or soup
    paragrafi = []
    for p in cont.find_all(["p", "li", "div", "span"]):
        txt = re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
        if 20 <= len(txt) <= 450 and txt not in paragrafi:
            paragrafi.append(txt)
        if len(paragrafi) >= 12:
            break

    corpo = " ".join(paragrafi)[:1600]
    testo_completo = f"{titolo} | {corpo}"

    cat_scarto, _ = classifica_motivo_scarto(f"{titolo} {corpo[:450]}")
    if cat_scarto:
        registra_scarto_nel_report(rq, cat_scarto)
        return []
    if not REGEX_TEMA_COERENTE.search(testo_completo):
        registra_scarto_nel_report(rq, "non_pertinenti")
        return []

    d1, d2, d_txt = estrai_date_italiano(testo_completo, ref, ignora_pubblicazione=True)
    if not d1:
        registra_scarto_nel_report(rq, "date_non_verificabili")
        return []

    citta = risolvi_comune_50km({"citta": citta_default, "titolo": titolo, "descrizione": corpo[:600]})
    if not citta:
        registra_scarto_nel_report(rq, "fuori_raggio")
        return []

    luogo = estrai_luogo_documentato(cont, citta)
    if not luogo:
        registra_scarto_nel_report(rq, "luogo_non_documentato")
        return []

    costo = estrai_costo_documentato(cont)
    descrizione = ""
    for p in paragrafi:
        if len(p) >= 45 and p.lower() != titolo.lower() and not REGEX_SCARTO.search(p):
            descrizione = rimuovi_riferimenti_pubblicazione(p)[:220]
            break

    candidato = {
        "citta": citta,
        "categoria": classifica_categoria(testo_completo),
        "titolo": titolo,
        "dataTesto": d_txt,
        "dataInizio": d1,
        "dataFine": d2,
        "luogo": luogo,
        "indirizzoMappa": f"{luogo}, {citta}",
        "costo": costo,
        "descrizione": descrizione or f"{titolo} presso {luogo} ({citta}).",
        "fonteUrl": page_url
    }
    ev_ok, _ = normalizza_e_valida_evento(candidato, ref, ignora_pubblicazione=True, rq=rq)
    return [ev_ok] if ev_ok else []


def raccogli_da_tacco(session, fonte, rq=None):
    eventi = []
    nome = fonte["nome"]
    url = fonte["url"]
    stat = {"fonte": nome, "url": url, "httpStatus": 0, "schedeLette": 0, "eventiEstratti": 0, "motivoZero": ""}

    try:
        r = session.get(url, timeout=(5, 9))
        stat["httpStatus"] = r.status_code
        if r.status_code != 200:
            stat["motivoZero"] = f"HTTP {r.status_code}"
            if rq:
                rq["fontiNonRaggiungibili"] += 1
            print(f"{nome}: HTTP {r.status_code}")
            return [], stat
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        links = []
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"]).split("#")[0].split("?")[0]
            if re.search(r"iltaccodibacco\.it/puglia/eventi/\d+\.html$", href):
                if href not in links:
                    links.append(href)

        for link in links[:10]:
            try:
                rp = session.get(link, timeout=(4, 7))
                if rp.status_code != 200:
                    continue
                stat["schedeLette"] += 1
                rp.encoding = rp.apparent_encoding or "utf-8"
                if "evento si è già concluso" in rp.text.lower() or "fa parte del nostro archivio" in rp.text.lower():
                    registra_scarto_nel_report(rq, "passati")
                    continue
                trovati = analizza_pagina_tacco(rp.text, link, citta_default="", rq=rq)
                eventi.extend(trovati)
            except Exception:
                continue

        stat["eventiEstratti"] = len(eventi)
        if not eventi:
            stat["motivoZero"] = "Nessun evento futuro pertinente con data e luogo verificabili"
        print(f"{nome}: {len(eventi)} eventi estratti (da {stat['schedeLette']} schede)")
    except Exception as e:
        stat["motivoZero"] = f"Errore rete: {str(e)[:60]}"
        if rq:
            rq["fontiNonRaggiungibili"] += 1
        print(f"Errore {nome}: {str(e)[:75]}")

    return eventi, stat


# ==============================================================================
# PARSER E DISCOVERY DEDICATI AL NETWORK VIVA
# ==============================================================================
def _is_url_articolo_viva(path):
    p = (path or "").strip()
    if not p or p == "/":
        return False
    p_low = p.lower()
    if any(excl in p_low for excl in ESCLUSIONI_PATH_VIVA):
        return False
    if re.match(r"^/(?:eventi|notizie|cultura|eventi-e-cultura|vita-di-citta|spettacoli|tempo-libero)/?$", p_low):
        return False
    if re.match(r"^/(?:eventi|notizie|cultura|eventi-e-cultura|vita-di-citta|spettacoli|tempo-libero)(?:/[a-z0-9_-]{3,})+/?(?:\.html)?$", p_low):
        return True
    return False


def _is_url_articolo_viva_fallback(path):
    p = (path or "").strip()
    if not p or p == "/":
        return False
    p_low = p.lower()
    if any(excl in p_low for excl in ESCLUSIONI_PATH_VIVA):
        return False
    return bool(re.match(r"^/[a-z0-9_-]{3,}/[a-z0-9_-]{5,}(?:/[a-z0-9_-]{2,})*/?(?:\.html)?$", p_low))


def estrai_candidati_viva_da_html(html_text, base_url, dominio, solo_eventi):
    soup = BeautifulSoup(html_text, "html.parser")
    tutti_a = soup.find_all("a", href=True)
    totale_html = len(tutti_a)

    interni_visti = set()
    for a in tutti_a:
        full = urljoin(base_url, a["href"]).split("#")[0].strip()
        pr = urlparse(full)
        if pr.scheme in ("http", "https") and dominio in pr.netloc.lower():
            interni_visti.add(full)

    candidati = []
    chiavi_viste = set()
    strategia_usata = "Strategia 1 (card/articoli/heading/breadcrumb)"

    selettori_s1 = (
        "article a[href], .card a[href], [class*='card'] a[href], "
        "[class*='news'] a[href], [class*='post'] a[href], [class*='item'] a[href], "
        "[class*='articolo'] a[href], [class*='evento'] a[href], [class*='box'] a[href], "
        "h1 a[href], h2 a[href], h3 a[href], h4 a[href]"
    )
    ancore_s1 = soup.select(selettori_s1)

    for a in ancore_s1:
        full = urljoin(base_url, a["href"]).split("#")[0].strip()
        pr = urlparse(full)
        if pr.scheme not in ("http", "https") or dominio not in pr.netloc.lower():
            continue
        if not _is_url_articolo_viva(pr.path):
            continue

        chiave_norm = f"{pr.netloc.lower()}{pr.path.rstrip('/').lower()}"
        if chiave_norm in chiavi_viste:
            continue

        card = a.find_parent(["article", "li", "div", "section"])
        testo_anchor = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
        testo_card = re.sub(r"\s+", " ", card.get_text(" ", strip=True)).strip()[:400] if card else testo_anchor
        testo_valutazione = f"{testo_anchor} {testo_card}".strip()

        if len(testo_valutazione) < 8:
            continue
        if REGEX_SCARTO.search(testo_anchor or testo_valutazione[:180]):
            continue

        is_sez_eventi = "/eventi/" in pr.path.lower() or solo_eventi
        if is_sez_eventi or REGEX_TEMA_COERENTE.search(testo_valutazione):
            chiavi_viste.add(chiave_norm)
            candidati.append(full)

    if not candidati:
        strategia_usata = "Strategia 2 (fallback scansione completa anchor interni multi-segmento)"
        for a in tutti_a:
            full = urljoin(base_url, a["href"]).split("#")[0].strip()
            pr = urlparse(full)
            if pr.scheme not in ("http", "https") or dominio not in pr.netloc.lower():
                continue
            if not _is_url_articolo_viva_fallback(pr.path):
                continue

            chiave_norm = f"{pr.netloc.lower()}{pr.path.rstrip('/').lower()}"
            if chiave_norm in chiavi_viste:
                continue

            testo_anchor = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
            if len(testo_anchor) < 10 or REGEX_SCARTO.search(testo_anchor):
                continue

            is_sez_eventi = "/eventi/" in pr.path.lower() or solo_eventi
            if is_sez_eventi or REGEX_TEMA_COERENTE.search(f"{testo_anchor} {pr.path.replace('-', ' ')}"):
                chiavi_viste.add(chiave_norm)
                candidati.append(full)

    return {
        "totale_html": totale_html,
        "interni": len(interni_visti),
        "candidati": candidati,
        "strategia": strategia_usata
    }


def analizza_pagina_viva(html_text, page_url, citta_default="", ref_dt=None, rq=None):
    """Estrae evento da pagina Viva separando date pubblicazione da date appuntamento e richiedendo luogo reale."""
    ref = ref_dt or oggi_dt()
    soup = BeautifulSoup(html_text, "html.parser")
    risultati = []

    eventi_ld = []
    for sc in soup.find_all("script", type="application/ld+json"):
        try:
            dati = json.loads(sc.string or "")
            estrai_eventi_jsonld(dati, eventi_ld)
        except Exception:
            continue

    for ev_ld in eventi_ld[:3]:
        titolo = re.sub(r"\s+", " ", str(ev_ld.get("name") or "")).strip()
        d1 = str(ev_ld.get("startDate") or "").strip()[:10]
        d2 = str(ev_ld.get("endDate") or d1).strip()[:10]
        loc = ev_ld.get("location") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        luogo_nome = loc.get("name", "") if isinstance(loc, dict) else ""
        addr = loc.get("address", {}) if isinstance(loc, dict) else {}
        localita = addr.get("addressLocality", citta_default) if isinstance(addr, dict) else citta_default
        desc = re.sub(r"\s+", " ", str(ev_ld.get("description") or "")).strip()

        candidato = {
            "citta": localita or citta_default,
            "titolo": titolo,
            "dataInizio": d1,
            "dataFine": d2,
            "dataTesto": formatta_data_italiano(d1, d2) if re.match(r"^\d{4}-\d{2}-\d{2}$", d1) else "",
            "luogo": luogo_nome,
            "indirizzoMappa": f"{luogo_nome}, {localita or citta_default}".strip(" ,"),
            "costo": "Non specificato nella fonte",
            "descrizione": desc,
            "fonteUrl": page_url
        }
        ev_ok, _ = normalizza_e_valida_evento(candidato, ref, ignora_pubblicazione=True, rq=rq)
        if ev_ok:
            risultati.append(ev_ok)

    if risultati:
        return risultati

    h1 = soup.find("h1")
    titolo = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else ""
    if not titolo:
        og_t = soup.find("meta", property="og:title")
        titolo = re.sub(r"\s+", " ", og_t.get("content", "")).strip() if og_t else ""

    if len(titolo) < 5:
        return []

    for tag in soup(["script", "style", "nav", "footer", "aside", "form", "noscript", "iframe", "time"]):
        tag.decompose()

    for meta_el in soup.select(
        ".byline, .author, .meta, .post-meta, .entry-meta, .article-meta, "
        "[class*='publish'], [class*='update'], [class*='autore'], [class*='redazione'], [class*='breadcrumb']"
    ):
        meta_el.decompose()

    cont = soup.find("article") or soup.find("main") or soup.body or soup
    paragrafi = []
    for p in cont.find_all(["p", "li", "h2", "h3"]):
        txt = re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
        if 18 <= len(txt) <= 500 and txt not in paragrafi:
            paragrafi.append(txt)
        if len(paragrafi) >= 14:
            break

    corpo = " ".join(paragrafi)[:1800]
    testo_completo = f"{titolo} | {corpo}"

    cat_scarto, _ = classifica_motivo_scarto(f"{titolo} {corpo[:450]}")
    if cat_scarto:
        registra_scarto_nel_report(rq, cat_scarto)
        return []
    if not REGEX_TEMA_COERENTE.search(testo_completo):
        registra_scarto_nel_report(rq, "non_pertinenti")
        return []

    d1, d2, d_txt = estrai_date_italiano(testo_completo, ref, ignora_pubblicazione=True)
    if not d1:
        registra_scarto_nel_report(rq, "date_non_verificabili")
        return []

    citta = risolvi_comune_50km({"citta": citta_default, "titolo": titolo, "descrizione": corpo[:650]})
    if not citta:
        registra_scarto_nel_report(rq, "fuori_raggio")
        return []

    luogo = estrai_luogo_documentato(cont, citta)
    if not luogo:
        registra_scarto_nel_report(rq, "luogo_non_documentato")
        return []

    costo = estrai_costo_documentato(cont)
    descrizione = ""
    for p in paragrafi:
        if len(p) >= 40 and p.lower() != titolo.lower() and not REGEX_SCARTO.search(p):
            descrizione = rimuovi_riferimenti_pubblicazione(p)[:220]
            break

    candidato = {
        "citta": citta,
        "categoria": classifica_categoria(testo_completo),
        "titolo": titolo,
        "dataTesto": d_txt,
        "dataInizio": d1,
        "dataFine": d2,
        "luogo": luogo,
        "indirizzoMappa": f"{luogo}, {citta}",
        "costo": costo,
        "descrizione": descrizione or f"{titolo} presso {luogo} ({citta}).",
        "fonteUrl": page_url
    }
    ev_ok, _ = normalizza_e_valida_evento(candidato, ref, ignora_pubblicazione=True, rq=rq)
    return [ev_ok] if ev_ok else []


def raccogli_da_portale_viva(session, fonte, rq=None):
    eventi = []
    nome = fonte["nome"]
    url = fonte["url"]
    dominio = fonte["dominio"]
    c_def = fonte["citta_default"]
    solo_ev = fonte["solo_eventi"]

    stat = {
        "fonte": nome,
        "url": url,
        "httpStatus": 0,
        "totaleLinkHtml": 0,
        "linkInterni": 0,
        "linkCandidati": 0,
        "pagineScaricate": 0,
        "eventiEstratti": 0,
        "strategiaUsata": "",
        "motivoZero": ""
    }

    try:
        r = session.get(url, timeout=(5, 9))
        stat["httpStatus"] = r.status_code
        if r.status_code != 200:
            stat["motivoZero"] = f"HTTP {r.status_code}"
            if rq:
                rq["fontiNonRaggiungibili"] += 1
            print(
                f"[{nome}] HTTP status: {r.status_code} | Totale link HTML: 0 | Link interni: 0 | "
                f"Link candidati: 0 | Primi 10 URL: [] | Pagine scaricate: 0"
            )
            return [], stat

        r.encoding = r.apparent_encoding or "utf-8"
        diag = estrai_candidati_viva_da_html(r.text, url, dominio, solo_ev)
        candidati = diag["candidati"]

        stat["totaleLinkHtml"] = diag["totale_html"]
        stat["linkInterni"] = diag["interni"]
        stat["linkCandidati"] = len(candidati)
        stat["strategiaUsata"] = diag["strategia"]

        primi_10 = candidati[:10]
        pagine_scaricate = 0

        for link in primi_10:
            try:
                rp = session.get(link, timeout=(4, 7))
                if rp.status_code != 200:
                    continue
                pagine_scaricate += 1
                rp.encoding = rp.apparent_encoding or "utf-8"
                trovati = analizza_pagina_viva(rp.text, link, citta_default=c_def, rq=rq)
                eventi.extend(trovati)
            except Exception:
                continue

        stat["pagineScaricate"] = pagine_scaricate
        stat["eventiEstratti"] = len(eventi)

        print(
            f"[{nome}] HTTP status: {r.status_code} | Totale link HTML: {diag['totale_html']} | "
            f"Link interni: {diag['interni']} | Link candidati: {len(candidati)} ({diag['strategia']}) | "
            f"Primi 10 URL candidati: {primi_10} | Pagine scaricate: {pagine_scaricate} | "
            f"Eventi validi: {len(eventi)}"
        )

        if not eventi:
            if not candidati:
                stat["motivoZero"] = "0 link candidati trovati anche dopo Strategia 2"
            elif pagine_scaricate == 0:
                stat["motivoZero"] = "Impossibile scaricare le pagine candidate"
            else:
                stat["motivoZero"] = "Pagine lette prive di appuntamento futuro con luogo e data certi"

    except Exception as e:
        stat["motivoZero"] = f"Errore connessione: {str(e)[:60]}"
        if rq:
            rq["fontiNonRaggiungibili"] += 1
        print(
            f"[{nome}] HTTP status: ERRORE ({str(e)[:50]}) | Totale link HTML: 0 | Link interni: 0 | "
            f"Link candidati: 0 | Primi 10 URL: [] | Pagine scaricate: 0"
        )

    return eventi, stat


# ==============================================================================
# SECONDO LIVELLO FACOLTATIVO: GEMINI (SOLO SU EVENTI GIÀ VALIDATI DA PYTHON)
# ==============================================================================
def arricchisci_con_gemini_opzionale(api_key, eventi):
    """Disattivato di default (ABILITA_GEMINI=0). Non può creare eventi né inventare date/luoghi."""
    if not ABILITA_GEMINI_OPZIONALE or not api_key or not eventi:
        return eventi

    candidati = eventi[:10]
    ridotti = [
        {"idx": i, "citta": e["citta"], "luogo": e["luogo"], "titolo": e["titolo"], "descrizione": e["descrizione"]}
        for i, e in enumerate(candidati)
    ]

    modelli = ["gemini-flash-lite-latest"]
    prompt = (
        "Migliora esclusivamente la chiarezza di 'titolo' (max 80 char) e 'descrizione' (max 200 char) "
        "degli eventi locali pugliesi seguenti. NON inventare date o luoghi e mantieni lo stesso 'idx'. "
        "Rispondi SOLO con un array JSON: [{\"idx\":0,\"titolo\":\"...\",\"descrizione\":\"...\"}]\n\n"
        f"{json.dumps(ridotti, ensure_ascii=False)}"
    )

    for mod in modelli:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
        }
        try:
            r = requests.post(url, json=payload, timeout=(5, 15))
            if r.status_code != 200:
                print(f"[Gemini opzionale] HTTP {r.status_code} su {mod}: mantengo testi estratti da Python.")
                continue
            parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
            raw = "\n".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            raw_clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()
            aggiornamenti = json.loads(raw_clean)
            if isinstance(aggiornamenti, list):
                mappa = {item["idx"]: item for item in aggiornamenti if isinstance(item, dict) and "idx" in item}
                for i, ev in enumerate(candidati):
                    if i in mappa:
                        nuovo_t = re.sub(r"\s+", " ", str(mappa[i].get("titolo") or "")).strip()
                        nuova_d = re.sub(r"\s+", " ", str(mappa[i].get("descrizione") or "")).strip()
                        if len(nuovo_t) >= 5 and not REGEX_SCARTO.search(nuovo_t):
                            ev["titolo"] = nuovo_t[:85]
                        if len(nuova_d) >= 15 and not REGEX_SCARTO.search(nuova_d):
                            ev["descrizione"] = nuova_d[:220]
                print(f"[Gemini opzionale] Testi rifiniti con {mod}.")
                return eventi
        except Exception as e:
            print(f"[Gemini opzionale] Errore {mod} ({str(e)[:50]}): mantengo testi estratti da Python.")

    return eventi


def sono_duplicati(a, b):
    if a.get("citta", "").lower() != b.get("citta", "").lower():
        return False
    if a.get("fonteUrl") and a.get("fonteUrl") == b.get("fonteUrl"):
        return True
    t1 = re.sub(r"[^a-z0-9\s]", "", a.get("titolo", "").lower())
    t2 = re.sub(r"[^a-z0-9\s]", "", b.get("titolo", "").lower())
    return SequenceMatcher(None, t1, t2).ratio() >= 0.68


def carica_esistenti_protetti(percorso_json="eventi.json", ref_dt=None):
    oggi = oggi_iso(ref_dt)
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
    ref = oggi_dt()
    rq = nuovo_report_qualita()

    manuali_admin, precedenti_auto = carica_esistenti_protetti("eventi.json", ref)
    print(f"Eventi protetti caricati: {len(manuali_admin)} manuali admin, {len(precedenti_auto)} automatici ancora validi.")

    session = requests.Session()
    session.headers.update(HEADERS)

    statistiche_fonti = []
    nuovi_raccolti = []

    print("\n--- RACCOLTA PORTALI NETWORK VIVA ---")
    for fonte in FONTI_VIVA:
        ev_viva, st_viva = raccogli_da_portale_viva(session, fonte, rq=rq)
        nuovi_raccolti.extend(ev_viva)
        statistiche_fonti.append(st_viva)

    print("\n--- RACCOLTA IL TACCO DI BACCO ---")
    eventi_tacco_log = []
    for fonte in FONTI_TACCO:
        ev_tacco, st_tacco = raccogli_da_tacco(session, fonte, rq=rq)
        nuovi_raccolti.extend(ev_tacco)
        eventi_tacco_log.extend(ev_tacco)
        statistiche_fonti.append(st_tacco)

    print("\n--- RIEPILOGO EVENTI ESTRATTI DA IL TACCO DI BACCO ---")
    for idx, ev in enumerate(eventi_tacco_log, start=1):
        print(f"{idx}. [{ev['citta']}] {ev['dataTesto']} | {ev['luogo']} | {ev['titolo']} -> {ev['fonteUrl']}")

    nuovi_unici = []
    for ev in nuovi_raccolti:
        if not any(sono_duplicati(x, ev) for x in nuovi_unici):
            nuovi_unici.append(ev)

    if ABILITA_GEMINI_OPZIONALE:
        nuovi_unici = arricchisci_con_gemini_opzionale(api_key, nuovi_unici)
    else:
        print("\n[Gemini opzionale] Disattivato per impostazione predefinita (zero consumo quota).")

    consolidati = list(manuali_admin)
    aggiunti_nuovi = 0
    for ev in nuovi_unici:
        if not any(sono_duplicati(x, ev) for x in consolidati):
            consolidati.append(ev)
            aggiunti_nuovi += 1

    for ev_old in precedenti_auto:
        if not any(sono_duplicati(x, ev_old) for x in consolidati):
            consolidati.append(ev_old)

    lista_finale = sorted(
        consolidati,
        key=lambda x: (x.get("dataInizio", "9999-12-31"), priorita_km(x.get("citta", "")), x.get("titolo", "").lower())
    )

    with open("eventi.json", "w", encoding="utf-8") as f:
        json.dump(lista_finale, f, ensure_ascii=False, indent=2)

    report = {
        "aggiornatoAl": ref.strftime("%Y-%m-%d %H:%M:%S"),
        "totaleContenuti": len(lista_finale),
        "nuoviAggiunti": aggiunti_nuovi,
        "manualiConservati": len(manuali_admin),
        "qualitaSelezione": rq,
        "topComuni": dict(Counter(e.get("citta", "") for e in lista_finale).most_common(15)),
        "statisticheFonti": statistiche_fonti
    }
    with open("report_copertura.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n--- REPORT QUALITÀ SELEZIONE ---")
    for k_rq, v_rq in rq.items():
        print(f"- {k_rq}: {v_rq}")

    print("\n--- REPORT STATISTICHE FONTI ---")
    for st in statistiche_fonti:
        motivo = f" | Motivo zero: {st['motivoZero']}" if st.get("motivoZero") else ""
        print(f"- {st['fonte']}: {st['eventiEstratti']} eventi{motivo}")

    print(f"\nFine: {len(lista_finale)} eventi totali salvati ({aggiunti_nuovi} nuovi da portali, {len(manuali_admin)} manuali) in {int(time.time() - t_start)}s")


def esegui_self_test():
    """Suite di 22 test simulati di qualità (pertinenti vs cronaca, passati, teatro, sinfonica, convegni, date/luoghi non certi)."""
    ref = datetime(2026, 11, 23, 17, 30, 0)
    rq = nuovo_report_qualita()

    casi_test = [
        # --- 8 EVENTI PERTINENTI (DEVONO ESSERE ACCETTATI) ---
        ("1. Sagra futura con luogo", True, "Cerignola", "Sagra del Caciocavallo e Street Food", "Appuntamento sabato 5 dicembre 2026 in Piazza Duomo a Cerignola con degustazioni."),
        ("2. DJ set in locale", True, "Barletta", "Saturday Night DJ Set e Aperitivo Musicale", "Serata live sabato 28 novembre 2026 presso Clorophilla Club a Barletta."),
        ("3. Mercatini natalizi con periodo", True, "Canosa di Puglia", "Mercatini di Natale e Prodotti Tipici", "Dal 6 dicembre 2026 all'8 dicembre 2026 in Piazza Vittorio Veneto a Canosa di Puglia."),
        ("4. Accensione luminarie con data", True, "Cerignola", "Accensione delle Luminarie e Villaggio di Babbo Natale", "Domenica 29 novembre 2026 in Piazza Duomo a Cerignola apertura villaggio natalizio."),
        ("5. Escursione guidata naturalistica", True, "Margherita di Savoia", "Escursione guidata alle Saline di Margherita di Savoia", "Domenica 6 dicembre 2026 presso Riserva Naturale Saline di Margherita di Savoia."),
        ("6. Laboratori per bambini", True, "Trani", "Laboratori creativi e animazione per bambini", "Sabato 12 dicembre 2026 presso Villa Comunale di Trani attività genitori-figli."),
        ("7. Concerto tribute band", True, "Bisceglie", "Tribute Band Vasco Rossi - Musica dal vivo", "Venerdì 4 dicembre 2026 presso Arena del Mare a Bisceglie concerto live."),
        ("8. Fattoria didattica", True, "Andria", "Fattoria didattica aperta ed esperienza artigianale", "Domenica 13 dicembre 2026 presso Masseria San Vittore ad Andria."),
        # --- 14 CASI NON PERTINENTI / NON VERIFICABILI (DEVONO ESSERE SCARTATI) ---
        ("9. Cronaca incidente", False, "Cerignola", "Incidente stradale sulla statale 16", "Scontro tra due auto il 28 novembre 2026 in Via Manfredonia a Cerignola."),
        ("10. Politica consiglio comunale", False, "Cerignola", "Consiglio comunale straordinario", "Convocazione il 30 novembre 2026 presso Palazzo di Città a Cerignola."),
        ("11. Comunicato istituzionale", False, "Cerignola", "Comunicato stampa: taglio del nastro", "Inaugurazione istituzionale il 2 dicembre 2026 in Corso Gramsci a Cerignola."),
        ("12. Convegno medico", False, "Foggia", "Convegno sulla prevenzione cardiovascolare", "Seminario il 4 dicembre 2026 presso Auditorium Comunale a Foggia."),
        ("13. Presentazione libro", False, "Cerignola", "Presentazione del libro di storia locale", "Incontro con l'autore il 5 dicembre 2026 presso Palazzo Ducale a Cerignola."),
        ("14. Mostra fotografica", False, "Trani", "Mostra fotografica e vernissage sul paesaggio", "Esposizione dal 1 al 10 dicembre 2026 in Piazza Duomo a Trani."),
        ("15. Teatro di prosa", False, "Cerignola", "Stagione teatrale di prosa: commedia", "Spettacolo il 6 dicembre 2026 presso Teatro Mercadante a Cerignola."),
        ("16. Concerto sinfonico", False, "Foggia", "Concerto sinfonico dell'Orchestra Filarmonica", "Musica classica il 7 dicembre 2026 presso Auditorium a Foggia."),
        ("17. Iniziativa parrocchiale", False, "Cerignola", "Santa Messa solenne e processione", "Celebrazione religiosa l'8 dicembre 2026 in Piazza Duomo a Cerignola."),
        ("18. Sport agonistico", False, "Cerignola", "Torneo di calcio e gara podistica", "Competizione il 29 novembre 2026 presso Stadio Monterisi a Cerignola."),
        ("19. Festa già conclusa", False, "Cerignola", "Grande successo per la sagra autunnale", "La sagra si è svolta in Piazza Duomo a Cerignola con ampia partecipazione."),
        ("20. Evento con data passata", False, "Cerignola", "Concerto live band e street food", "Appuntamento il 15 ottobre 2025 in Piazza Duomo a Cerignola."),
        ("21. Articolo generico senza data/luogo", False, "Cerignola", "Natale a Cerignola: luminarie e festa nel weekend", "Pubblicato il 23 novembre 2026. L'amministrazione prepara le feste in città."),
        ("22. Comune fuori raggio 50 km", False, "Bari", "Mercatini di Natale e musica dal vivo", "Sabato 6 dicembre 2026 in Piazza Mercantile a Bari.")
    ]

    print("--- ESECUZIONE TEST DI QUALITÀ (22 CASI SIMULATI) ---")
    for nome_caso, atteso_valido, citta, titolo, testo in casi_test:
        html_sim = f"""
        <html><body><article>
          <div class="byline"><time datetime="2026-11-23">23 novembre 2026</time> - Redazione</div>
          <h1>{titolo}</h1>
          <p>{testo}</p>
        </article></body></html>
        """
        estratti = analizza_pagina_viva(html_sim, "https://www.cerignolaviva.it/notizie/test-simulato/", citta, ref, rq=rq)
        esito_valido = len(estratti) == 1
        assert esito_valido == atteso_valido, f"Errore su '{nome_caso}': atteso {atteso_valido}, ottenuto {esito_valido}"
        stato_str = f"ACCETTATO ({estratti[0]['categoria']} | {estratti[0]['dataInizio']} | {estratti[0]['luogo']})" if esito_valido else "SCARTATO"
        print(f"- {nome_caso}: {stato_str}")

    print("\n--- RIEPILOGO CONTATORI REPORT QUALITÀ ---")
    for k, v in rq.items():
        print(f"- {k}: {v}")
    print("\nTUTTI I 22 TEST DI QUALITÀ SUPERATI.")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        esegui_self_test()
    else:
        esegui_aggiornamento()
