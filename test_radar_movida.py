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
        self.assertTrue(all(x["nightlife"] for x in direct+rss if not x.get("anno_capodanno")))
        self.assertTrue(any(x["alias_movida"] and x["solo_cerignola"] for x in rss))
        self.assertTrue(r.alias_corrispondente("NONZAI DJ set",["NONZAI"]))
        self.assertFalse(r.alias_corrispondente("altro locale",["NONZAI"]))

    def test_profili_pubblici_senza_apify(self):
        from datetime import date
        from urllib.parse import parse_qs,urlparse
        reg={"Cerignola":[{"nome":"Locale Test","alias":["Locale Test"],"social":"https://www.instagram.com/localetest/","facebook":"https://www.facebook.com/localetest/"}],
             "Trani":[{"nome":"Club Test","alias":["Club Test"],"calendario":"https://www.instagram.com/clubtest/"},
                      {"nome":"Post","alias":["Post non profilo"],"calendario":"https://www.instagram.com/reel/abcdef/"}]}
        _,rss=r.fonti(reg,[],date(2026,11,26),[{"nome":"Promoter Test","social":"https://www.instagram.com/promotertest/"}])
        feeds=[(f,parse_qs(urlparse(f["url"]).query)["q"][0]) for f in rss]
        self.assertTrue(any("site:facebook.com" in q and '"localetest"' in q and f["solo_cerignola"] for f,q in feeds))
        self.assertTrue(any("site:instagram.com" in q and '"clubtest"' in q and f["comune_radar"]=="Trani" for f,q in feeds))
        self.assertTrue(any('"Club Test"' in q and f["comune_radar"]=="Trani" for f,q in feeds))
        p=next(f for f,q in feeds if "Promoter pubblico" in f["nome"])
        self.assertEqual(p["comune_radar"],"")
        self.assertIn("promotertest",p["alias_movida"])
        self.assertFalse(any("abcdef" in q for f,q in feeds))
        self.assertIsNone(r.profilo_social("https://www.instagram.com/stories/"))
        self.assertIsNone(r.profilo_social("https://instagram.com.evil.test/clubtest/"))

    def test_ricerca_cenoni_territoriale(self):
        from urllib.parse import parse_qs, urlparse
        from datetime import date
        _, rss = r.fonti({}, [], date(2026,11,26))
        self.assertFalse(any(f.get("anno_capodanno") for f in r.fonti({},[],date(2027,5,1))[1]))
        stagionali = [f for f in rss if f["nome"].endswith(" feste e cenoni")]
        self.assertEqual(len(stagionali), 12)
        self.assertEqual(len({f["url"] for f in stagionali}), 12)
        for f in stagionali:
            q = parse_qs(urlparse(f["url"]).query)["q"][0]
            self.assertIn('"'+f["comune_radar"]+'"', q)
            self.assertIn('"cenone"', q)
            self.assertEqual(f["solo_cerignola"], f["comune_radar"]=="Cerignola")
            self.assertEqual(f["max_schede_rss"], 4)
            self.assertEqual(f["anno_capodanno"],2026)
            self.assertEqual(f["comune_capodanno"],f["comune_radar"])
            self.assertFalse(f["nightlife"])

    def test_ricerca_fonti_ufficiali(self):
        from urllib.parse import parse_qs, urlparse
        _,rss=r.fonti({"Cerignola":[{"nome":"Alchimia","alias":["Alchimia Cucina"],"sito":"https://alchimiacucinaevino.eatbu.com/","social":"https://www.instagram.com/alchimia.cucinaevino/"}]},[])
        q=[parse_qs(urlparse(x["url"]).query)["q"][0] for x in rss if x["solo_cerignola"]]
        self.assertTrue(any("site:alchimiacucinaevino.eatbu.com" in x for x in q))
        self.assertTrue(any('site:instagram.com "alchimia.cucinaevino"' in x for x in q))
        self.assertTrue(any("disc jockey" in x for x in q))
