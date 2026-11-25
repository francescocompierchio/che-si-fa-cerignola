import unittest
from datetime import date
import ricorrenze as r

class RicorrenzeTest(unittest.TestCase):
    def test_pasqua(self):
        self.assertEqual(r.pasqua(2027),date(2027,3,28))
        self.assertEqual(r.pasqua(2028),date(2028,4,16))
    def test_calendario(self):
        self.assertEqual(len(r.calendario(2027)),8)
        self.assertIn("Madonna di Ripalta",[x["nome"] for x in r.attive(date(2027,6,1))])
        self.assertNotIn("Madonna di Ripalta",[x["nome"] for x in r.attive(date(2027,12,1))])
    def test_date(self):
        xs=r.attive(date(2027,2,1))
        self.assertEqual(r.date_documentate("San Valentino cena 14 febbraio 2027",xs),[("2027-02-14","San Valentino")])
        self.assertEqual(r.date_documentate("San Valentino cena 14 febbraio 2026",xs),[])
        self.assertEqual(r.date_documentate("San Valentino cena 14 febbraio",xs),[])
        self.assertEqual(r.date_documentate("San Valentino cena 14 e 15 febbraio 2027",xs),[])
        self.assertEqual(r.date_documentate("San Valentino cena 14 febbraio 2027 e 15 febbraio",xs),[])
    def test_fonte(self):
        d,rss=r.fonti(date(2027,6,1),[])
        self.assertEqual(d,[])
        self.assertTrue(all(x["solo_cerignola"] and x["prioritaria"] for x in rss))
        self.assertTrue(any("Ripalta" in x["nome"] for x in rss))
