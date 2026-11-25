import unittest
import radar_natura as r

class RadarNaturaTest(unittest.TestCase):
    def test_fonti(self):
        dirette,rss=r.fonti()
        self.assertEqual(len(dirette),9)
        self.assertEqual(len(rss),8)
        self.assertTrue(all(f["natura"] for f in dirette+rss))
        self.assertTrue(any("Cerignola" in f["nome"] and f["prioritaria"] for f in rss))
    def test_selezione(self):
        self.assertTrue(r.pertinente("Escursione guidata nella Valle dell'Ofanto"))
        self.assertTrue(r.pertinente("Birdwatching alle saline"))
        self.assertFalse(r.pertinente("Convegno sul parco naturale e il trekking"))
        self.assertFalse(r.pertinente("Concerto nel bosco"))
        self.assertFalse(r.pertinente("Gara podistica trail running nel bosco"))
        self.assertFalse(r.evento_documentato({"titolo":"Trekking nel bosco","fonteUrl":"https://example.org"}))
        self.assertTrue(r.evento_documentato({"titolo":"Trekking nel bosco","dataInizio":"2026-12-06","dataFine":"2026-12-06","fonteUrl":"https://example.org"}))
