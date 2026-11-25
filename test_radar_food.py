import unittest
import radar_food as r

class RadarFoodTest(unittest.TestCase):
    def test_fonti(self):
        dirette,rss=r.fonti()
        self.assertEqual(len(dirette),10)
        self.assertEqual(len(rss),10)
        self.assertEqual(sum(bool(f.get("solo_cerignola")) for f in rss),4)
    def test_tema(self):
        for testo in ("Sagra della Sfogliatella","Street food","Cena a tema","Degustazione di olio","Cantine aperte"):
            self.assertTrue(r.pertinente(testo))
        for testo in ("Convegno sulla sagra","Sagra annullata","Ristorante aperto tutti i giorni","Concerto di Natale"):
            self.assertFalse(r.pertinente(testo))
        self.assertFalse(r.evento_documentato({"titolo":"Degustazione","fonteUrl":"https://example.org"}))
        self.assertTrue(r.evento_documentato({"titolo":"Sagra del Carciofo","dataInizio":"2026-12-18","dataFine":"2026-12-20","fonteUrl":"https://example.org"}))
