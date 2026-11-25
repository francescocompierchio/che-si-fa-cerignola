import unittest
import radar_movida as r
class RadarMovidaTest(unittest.TestCase):
    def test_formati(self):
        for s in ("Quiz game al pub","Jam session","DJ set","Karaoke","Cena spettacolo","Serata a tema"):
            self.assertTrue(r.pertinente(s))
        self.assertFalse(r.pertinente("Convegno sul DJ set"))
        self.assertFalse(r.live_in_locale("Concerto jazz","","Teatro Curci"))
        self.assertTrue(r.live_in_locale("Impromptu Jazz Quartet live","","Santo Graal"))
    def test_fonti(self):
        direct,rss=r.fonti({"Cerignola":[{"nome":"Safarà","alias":["Safarà"],"calendario":"https://iltaccodibacco.it/cerignola/safara"}],"Trani":[{"nome":"Santo Graal","alias":["santo graal"],"calendario":"https://iltaccodibacco.it/trani/santo-graal/"}]},[])
        self.assertEqual(len(direct),2)
        self.assertTrue(all(x["nightlife"] for x in direct+rss))
        self.assertTrue(any(x["alias_movida"] and x["solo_cerignola"] for x in rss))
        self.assertTrue(r.alias_corrispondente("NONZAI DJ set",["NONZAI"]))
        self.assertFalse(r.alias_corrispondente("altro locale",["NONZAI"]))
