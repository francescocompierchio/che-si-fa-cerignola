import unittest
from datetime import date
from urllib.parse import parse_qs,urlparse
import capodanno as c
import aggiorna_eventi as a

class TestCapodanno(unittest.TestCase):
    def test_stagione(self):
        self.assertEqual(c.stagione(date(2026,11,25)),2026)
        self.assertEqual(c.stagione(date(2027,1,1)),2026)
        self.assertIsNone(c.stagione(date(2027,1,2)))
    def test_date(self):
        self.assertEqual(c.date_documentate("Cenone 31 dicembre 2026",2026),["2026-12-31"])
        self.assertEqual(c.date_documentate("Capodanno 2027, veglione 31 dicembre",2026),["2026-12-31"])
        self.assertEqual(c.date_documentate("Capodanno 2027 pranzo 1 gennaio",2026),["2027-01-01"])
        self.assertEqual(c.date_documentate("Cenone 31 dicembre 2025",2026),[])
        self.assertEqual(c.date_documentate("Capodanno 2026 cenone 31 dicembre",2026),[])
        self.assertEqual(c.date_documentate("Capodanno 2027",2026),[])
        self.assertEqual(c.date_documentate("Cenone 31 dicembre",2026),[])
    def test_fonti(self):
        dirette,rss=c.fonti(date(2026,11,25))
        self.assertEqual(len(dirette),8)
        self.assertEqual(len(c.registro()),20)
        self.assertTrue(all(f["prioritaria"] for f in dirette+rss))
        q=" ".join(parse_qs(urlparse(f["url"]).query)["q"][0] for f in rss)
        for r in c.registro():
            self.assertTrue(all(alias in q for alias in r["alias"]))
    def test_dup(self):
        ev={"citta":"Cerignola","dataInizio":"2026-12-31","dataFine":"2026-12-31","titolo":"Cenone di Capodanno","luogo":"Villa Bautier"}
        self.assertFalse(a.sono_duplicati(ev,dict(ev,luogo="Villa Demetra")))
        self.assertTrue(a.sono_duplicati(ev,ev))
