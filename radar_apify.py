"""Registra il budget zero del progetto senza collegarsi ad Apify."""
import json
from pathlib import Path

REPORT = Path("apify-rapporto.json")


def rapporto_budget_zero():
    return {"stato": "disattivato_budget_zero", "budgetUsd": 0, "actorAvviati": 0}


if __name__ == "__main__":
    rapporto = json.dumps(rapporto_budget_zero(), ensure_ascii=False)
    REPORT.write_text(rapporto + "\n", encoding="utf-8")
    print(rapporto)
