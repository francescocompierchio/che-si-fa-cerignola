import unittest
from datetime import date
import discovery_locale as d

class DiscoveryLocaleTest(unittest.TestCase):
    def test_fonti(self):
        self.assertEqual(len(d.fonti()),3)
        self.assertEqual(len(d.settimanali()),3)
        self.assertTrue(all(x["solo_cerignola"] and x["prioritaria"] for x in d.fonti()+d.settimanali()))
    def test_alias(self):
        r=[{"alias":["Villa Torre Quarto","Il Titolo"]}]
        self.assertTrue(d.alias_locale("Cenone Villa Torre Quarto",r))
        self.assertFalse(d.alias_locale("Il titolo del libro",r))
    def test_data(self):
        self.assertTrue(d.data_evento_documentata("Karaoke 28 novembre 2026","2026-11-28"))
        self.assertTrue(d.data_evento_documentata("Dj set 28/11/26","2026-11-28"))
        self.assertFalse(d.data_evento_documentata("Ogni sabato karaoke","2026-11-28"))
        self.assertFalse(d.data_evento_documentata("Dj set 28 novembre 2025","2026-11-28"))
    def test_pubblicazione(self):
        self.assertEqual(d.data_pubblicazione("Wed, 25 Nov 2026 08:00:00 +0100"),date(2026,11,25))
        self.assertFalse(d.data_coerente_pubblicazione({"dataInizio":"2027-02-07"},date(2025,2,1)))
        self.assertTrue(d.data_coerente_pubblicazione({"dataInizio":"2026-12-31"},date(2026,11,25)))

    def test_associazione_locandina(self):
        self.assertTrue(d.titolo_locandina_compatibile("Karaoke Villa Bautier","Villa Bautier karaoke Cerignola 28 novembre 2026"))
        self.assertFalse(d.titolo_locandina_compatibile("Concerto Cerignola sabato 28 novembre","Festa Cerignola sabato 28 novembre"))
