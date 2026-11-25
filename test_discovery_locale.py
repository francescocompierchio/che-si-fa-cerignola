import unittest
from datetime import date
import discovery_locale as d

class DiscoveryLocaleTest(unittest.TestCase):
    def test_fonti(self):
        self.assertEqual(len(d.fonti()),3)
        self.assertEqual(len(d.settimanali()),3)
        self.assertTrue(all(x["solo_cerignola"] and x["prioritaria"] for x in d.fonti()+d.settimanali()))
    def test_cene_show(self):
        from urllib.parse import urlparse,parse_qs
        fonti=d.fonti_cene_show({"Foggia":[{"alias":["acquolina","mirage village"],"organizzatori":["eventi_enjoy","DBA Events"]}]})
        self.assertTrue(any(f.get("solo_cerignola") and f["prioritaria"] for f in fonti))
        self.assertTrue(all(f["nightlife"] and f["cene_show"] and f["max_schede_rss"]<=4 for f in fonti))
        q=[parse_qs(urlparse(f["url"]).query)["q"][0] for f in fonti]
        self.assertTrue(any("eventi_enjoy" in x and "mirage village" in x for x in q))
        self.assertTrue(all('"cena spettacolo"' in x for x in q))
        for testo in ("Acquolina in cena spettacolo", "Cena con spettacolo", "Dinner-show", "Cena con DJ set", "Showman Antonio", "Percussioni live"):
            self.assertTrue(d.CENE_SHOW.search(testo),testo)
        for testo in ("Menu del ristorante", "Orari di apertura", "Convegno", "Cena di beneficenza"):
            self.assertFalse(d.CENE_SHOW.search(testo),testo)
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
