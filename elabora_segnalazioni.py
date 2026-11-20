import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

REPO = os.environ.get("GITHUB_REPOSITORY", "francescocompierchio/che-si-fa-cerignola")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
EVENTI_FILE = "eventi.json"
GEMINI_MODEL = "gemini-2.5-flash"

CATEGORIE_AMMESSE = [
    "Spettacolo",
    "Musica",
    "Cultura",
    "Famiglie",
    "Mercatino",
    "Fiera",
    "Incontro",
    "Sport",
    "Natale",
    "Altro",
]


def normalizza_chiave(titolo: str, data_inizio: str) -> str:
    t = re.sub(r"[^a-z0-9]+", "", (titolo or "").lower())
    return f"{t}|{data_inizio or ''}"


def get_oggi_roma() -> str:
    return datetime.now(ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d")


def carica_eventi() -> list[dict]:
    if not os.path.exists(EVENTI_FILE):
        return []
    with open(EVENTI_FILE, "r", encoding="utf-8") as f:
        dati = json.load(f)
    return dati if isinstance(dati, list) else []


def salva_eventi(eventi: list[dict]) -> None:
    eventi_ordinati = sorted(
        eventi,
        key=lambda x: (x.get("dataInizio", "9999-99-99"), x.get("titolo", "")),
    )
    with open(EVENTI_FILE, "w", encoding="utf-8") as f:
        json.dump(eventi_ordinati, f, ensure_ascii=False, indent=2)
        f.write("\n")


def github_api_request(method: str, path: str, payload: dict | None = None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "CheSiFaCerignola-Bot",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=25) as resp:
        corpo = resp.read().decode("utf-8")
        return json.loads(corpo) if corpo else None


def ottieni_issue_approvate() -> list[dict]:
    query = urllib.parse.urlencode({
        "state": "open",
        "labels": "approvato",
        "sort": "created",
        "direction": "asc",
        "per_page": "30",
    })
    issues = github_api_request("GET", f"/issues?{query}")
    if not isinstance(issues, list):
        return []
    return [item for item in issues if "pull_request" not in item]


def commenta_e_chiudi_issue(issue_number: int, commento: str, chiudi: bool = True) -> None:
    github_api_request("POST", f"/issues/{issue_number}/comments", {"body": commento})
    if chiudi:
        github_api_request("PATCH", f"/issues/{issue_number}", {"state": "closed"})


def estrai_evento_con_gemini(titolo_issue: str, corpo_issue: str, oggi: str) -> dict | None:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY non impostata nell'ambiente.")

    prompt = f"""Sei un assistente editoriale per l'app "Che Si Fa Cerignola" (eventi a Cerignola e comuni limitrofi come Canosa di Puglia, San Ferdinando di Puglia, Trinitapoli, Margherita di Savoia, Stornara, Stornarella, Orta Nova).
Data odierna (Europe/Rome): {oggi}

Analizza la seguente segnalazione inviata da un utente/locale e restituisci UN SOLO oggetto JSON valido (oppure null se mancano dati essenziali o non è un evento pubblico).

Segnalazione:
Titolo / Oggetto: {titolo_issue}
Testo / Campi:
{corpo_issue}

Campi richiesti nell'oggetto JSON:
- "citta": stringa, nome del comune (es. "Cerignola", "Canosa di Puglia", "Trinitapoli", ecc.).
- "categoria": una tra {", ".join(CATEGORIE_AMMESSE)}.
- "titolo": stringa chiara e pulita dell'evento.
- "dataTesto": stringa leggibile in italiano con data ed eventuale orario (es. "Venerdì 27 Novembre 2026 · ore 20:30").
- "dataInizio": data in formato "YYYY-MM-DD".
- "dataFine": data in formato "YYYY-MM-DD" (uguale a dataInizio se dura un solo giorno).
- "luogo": stringa con nome locale, piazza o struttura.
- "indirizzoMappa": stringa utile per Google Maps includendo via/piazza e città (es. "Piazza Duomo, Cerignola FG").
- "costo": stringa breve (es. "Ingresso libero", "Ingresso su consumazione", "Biglietto", oppure "Da confermare").
- "descrizione": stringa sintetica e chiara (max 240 caratteri) senza emoji eccessive o spam.

Rispondi ESCLUSIVAMENTE con JSON puro, senza markdown o testo aggiuntivo."""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={urllib.parse.quote(GEMINI_API_KEY)}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=35) as resp:
        risposta = json.loads(resp.read().decode("utf-8"))

    testo = ""
    for cand in risposta.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            if "text" in part:
                testo += part["text"]

    testo = testo.strip()
    if not testo or testo.lower() == "null":
        return None

    testo = re.sub(r"^```(?:json)?\s*|\s*```$", "", testo, flags=re.IGNORECASE).strip()
    parsed = json.loads(testo)
    if not isinstance(parsed, dict):
        return None

    campi_obbligatori = ["citta", "categoria", "titolo", "dataTesto", "dataInizio", "dataFine", "luogo", "descrizione"]
    for campo in campi_obbligatori:
        val = str(parsed.get(campo, "")).strip()
        if not val:
            return None
        parsed[campo] = val

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", parsed["dataInizio"]):
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", parsed["dataFine"]):
        parsed["dataFine"] = parsed["dataInizio"]
    if parsed["dataFine"] < parsed["dataInizio"]:
        parsed["dataFine"] = parsed["dataInizio"]

    if parsed["categoria"] not in CATEGORIE_AMMESSE:
        parsed["categoria"] = "Altro"

    parsed["indirizzoMappa"] = str(parsed.get("indirizzoMappa") or f"{parsed['luogo']}, {parsed['citta']}").strip()
    parsed["costo"] = str(parsed.get("costo") or "Da confermare").strip()
    return parsed


def main() -> None:
    oggi = get_oggi_roma()
    eventi = carica_eventi()
    eventi_attivi = [ev for ev in eventi if ev.get("dataFine", "0000-00-00") >= oggi]

    try:
        issues = ottieni_issue_approvate()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"Errore nel recupero delle issue approvate: {exc}", file=sys.stderr)
        sys.exit(1)

    if not issues:
        print("Nessuna segnalazione con etichetta 'approvato' da elaborare.")
        salva_eventi(eventi_attivi)
        return

    chiavi_esistenti = {
        normalizza_chiave(ev.get("titolo", ""), ev.get("dataInizio", ""))
        for ev in eventi_attivi
    }
    aggiunti = 0

    for issue in issues:
        num = issue.get("number")
        titolo_issue = issue.get("title", "")
        corpo_issue = issue.get("body", "")

        try:
            evento_estratti = estrai_evento_con_gemini(titolo_issue, corpo_issue, oggi)
        except Exception as exc:
            print(f"Errore Gemini sulla Issue #{num}: {exc}", file=sys.stderr)
            commenta_e_chiudi_issue(
                num,
                f"Errore durante l'analisi automatica con Gemini: `{exc}`",
                chiudi=False,
            )
            continue

        if not evento_estratti:
            commenta_e_chiudi_issue(
                num,
                "Segnalazione non pubblicata: dati incompleti o non riconosciuti come evento pubblico valido.",
                chiudi=False,
            )
            continue

        if evento_estratti["dataFine"] < oggi:
            commenta_e_chiudi_issue(
                num,
                f"Segnalazione non pubblicata: la data di fine (`{evento_estratti['dataFine']}`) risulta già passata rispetto a oggi (`{oggi}`).",
                chiudi=True,
            )
            continue

        chiave = normalizza_chiave(evento_estratti["titolo"], evento_estratti["dataInizio"])
        if chiave in chiavi_esistenti:
            commenta_e_chiudi_issue(
                num,
                f"Evento già presente in `eventi.json`: **{evento_estratti['titolo']}** ({evento_estratti['dataInizio']}). Issue chiusa senza duplicati.",
                chiudi=True,
            )
            continue

        eventi_attivi.append(evento_estratti)
        chiavi_esistenti.add(chiave)
        aggiunti += 1

        commenta_e_chiudi_issue(
            num,
            f"Evento aggiunto automaticamente a `eventi.json`:\n- **Titolo:** {evento_estratti['titolo']}\n- **Data:** {evento_estratti['dataTesto']}\n- **Luogo:** {evento_estratti['luogo']} ({evento_estratti['citta']})",
            chiudi=True,
        )

    salva_eventi(eventi_attivi)
    print(f"Elaborazione completata. Nuovi eventi aggiunti: {aggiunti}")


if __name__ == "__main__":
    main()
