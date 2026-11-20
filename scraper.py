import json
from datetime import date, timedelta

oggi = date.today()
eventi = [
    {
        "title": "Mercatino di Natale - Cerignola",
        "city": "Cerignola",
        "place": "Corso Garibaldi, Cerignola",
        "date": str(oggi + timedelta(days=1)),
        "time": "17:00",
        "description": "Bancarelle, artigianato, street food e musica per le vie del centro."
    },
    {
        "title": "Serata di musica live",
        "city": "Cerignola",
        "place": "Piazza Duomo, Cerignola",
        "date": str(oggi + timedelta(days=2)),
        "time": "20:30",
        "description": "Musica live e aperitivo in piazza."
    },
    {
        "title": "Audace Cerignola - Partita in casa",
        "city": "Cerignola",
        "place": "Stadio Monterisi, Cerignola",
        "date": str(oggi + timedelta(days=3)),
        "time": "15:00",
        "description": "Partita dell'Audace Cerignola allo stadio Monterisi."
    },
    {
        "title": "Eventi nei dintorni - Orta Nova e Stornarella",
        "city": "Orta Nova",
        "place": "Centro, Orta Nova",
        "date": str(oggi + timedelta(days=2)),
        "time": "18:00",
        "description": "Eventi, sagre e mercatini nei paesi vicini a Cerignola."
    }
]

with open("events.json", "w", encoding="utf-8") as f:
    json.dump({"events": eventi}, f, ensure_ascii=False, indent=2)

print("events.json aggiornato")
