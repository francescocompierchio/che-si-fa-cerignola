import unittest
from datetime import date
import festivita as f
import capodanno

class FestivitaTest(unittest.TestCase):
    def test_stagione(self):
        self.assertEqual(f.stagione(date(2026,11,25)),2026)
        self.assertEqual(f.stagione(date(2027,1,6)),2026)
        self.assertIsNone(f.stagione(date(2027,1,7)))
    def test_date(self):
        self.assertEqual(f.date_documentate("Pranzo di Natale 25 dicembre 2026",2026),["2026-12-25"])
        self.assertEqual(f.date_documentate("Santo Stefano 2026 menu pranzo",2026),["2026-12-26"])
        self.assertEqual(f.date_documentate("Festa della Befana 6 gennaio 2027",2026),["2027-01-06"])
        self.assertEqual(f.date_documentate("Mercatini 13 dicembre 2026",2026),["2026-12-13"])
        self.assertEqual(f.date_documentate("Natale pranzo 25 dicembre 2025",2026),[])
        self.assertEqual(f.date_documentate("Pranzo di Natale 25 dicembre",2026),[])
        self.assertEqual(f.date_documentate("Mercatini dal 13 dicembre al 20 dicembre 2026",2026),[])
        self.assertEqual(f.date_documentate("Mercatini 13 e 20 dicembre 2026",2026),[])
        self.assertEqual(f.date_documentate("Natale 2026 25 dicembre 2025",2026),[])
    def test_fonti(self):
        fs=f.fonti(date(2026,11,25),capodanno.registro())
        self.assertEqual(len(fs),10)
        self.assertTrue(all(x["prioritaria"] and x["solo_cerignola"] for x in fs))
        self.assertEqual(f.fonti(date(2027,1,7),[]),[])
    def test_titoli(self):
        self.assertEqual(f.titolo_pasto("menu pranzo", "2026-12-26"),"Pranzo di Santo Stefano")
        self.assertEqual(f.titolo_pasto("festa bambini", "2027-01-06"),"")
