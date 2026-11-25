import unittest
from datetime import date
import apprendimento as a

class ApprendimentoTests(unittest.TestCase):
    def test_lacune(self):
        e={"citta":"Cerignola","categoria":"Locali & Serate","dataInizio":"2026-11-28","dataFine":"2026-11-28"}
        self.assertEqual(a.lacune([e],date(2026,11,25))["Locali & Serate"],1)
        self.assertEqual(a.lacune([dict(e,citta="Barletta")],date(2026,11,25))["Locali & Serate"],0)
    def test_esplorazione(self):
        fs=a.fonti({},[],date(2026,11,25))
        self.assertLessEqual(len(fs),3)
        self.assertTrue(any("Locali & Serate" in x["nome"] for x in fs))
        self.assertTrue(all(x["solo_cerignola"] and x["prioritaria"] for x in fs))
    def test_feedback(self):
        e={"citta":"Cerignola","categoria":"Locali & Serate","dataInizio":"2026-11-28","dataFine":"2026-11-28","titolo":"Karaoke"}
        dup=lambda a,b:a==b
        self.assertEqual(a.misura({"f":[e,e]},[],[e],dup)["f"]["nuoveSerateCerignola"],1)
        self.assertEqual(a.misura({"f":[e]},[e],[e],dup)["f"]["novitaUtili"],0)
        self.assertEqual(a.misura({"f":[e]},[],[],dup)["f"]["eventiUtili"],0)
    def test_memoria(self):
        m={}
        a.aggiorna(m,[],date(2026,11,25),1)
        a.aggiorna(m,[],date(2026,11,25),2)
        self.assertEqual(m["apprendimento"]["cicli"],2)
        self.assertEqual(len(m["apprendimento"]["storico"]),2)
