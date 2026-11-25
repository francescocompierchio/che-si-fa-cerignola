"""Test di regressione offline. Eseguire: python -m unittest test_radar_adattivo."""
import unittest
from datetime import date
from urllib.parse import urlparse, parse_qs
import apprendimento as a

class RadarAdattivoTest(unittest.TestCase):
    def test_finestra_weekend(self):
        self.assertEqual(a.finestra_weekend(date(2026,11,25)),(date(2026,11,27),date(2026,11,29)))
        self.assertEqual(a.finestra_weekend(date(2026,11,28)),(date(2026,11,28),date(2026,11,29)))
        self.assertEqual(a.finestra_weekend(date(2026,11,29)),(date(2026,11,29),date(2026,11,29)))

    def test_lacune_solo_serate_date_future(self):
        oggi=date(2026,11,28)
        eventi=[dict(citta="Cerignola",categoria="Locali & Serate",dataInizio="2026-11-28"),
                dict(citta="Cerignola",categoria="Locali & Serate",dataInizio="2026-11-27"),
                dict(citta="Cerignola",categoria="Attività diurne",dataInizio="2026-11-29")]
        self.assertEqual(a.lacune_weekend(eventi,oggi)["Cerignola"],{"eventi":1,"obiettivo":3,"mancanti":2})

    def test_budget_e_priorita(self):
        for giorno,budget in [(date(2026,11,23),1),(date(2026,11,27),3)]:
            fonti=a.fonti_adattive_weekend({},[],giorno)
            self.assertEqual(len(fonti),budget)
            self.assertTrue(fonti[0]["solo_cerignola"])
            self.assertTrue(all(f["nightlife"] for f in fonti))
        eventi=[]
        for zona,(_,obiettivo) in a.ZONE_WEEKEND.items():
            citta=sorted(a.COMUNI_ZONE[zona])[0]
            eventi.extend(dict(citta=citta,categoria="Locali & Serate",dataInizio="2026-11-28") for _ in range(obiettivo))
        self.assertEqual(a.fonti_adattive_weekend({},eventi,date(2026,11,27)),[])

    def test_esplorazione_solo_scoperta(self):
        m={"apprendimento":{"dominiCandidati":{"example.com":{"osservazioni":2},"unconfirmed.com":{"osservazioni":1},"host.local":{"osservazioni":9}}}}
        fonti=a.esplora_candidati(m,date(2026,11,27))
        self.assertEqual(len(fonti),1)
        self.assertTrue(fonti[0]["solo_scoperta"])
        self.assertEqual(urlparse(fonti[0]["url"]).hostname,"news.google.com")
        self.assertIn("site:example.com",parse_qs(urlparse(fonti[0]["url"]).query)["q"][0])

    def test_autodiagnosi_non_modifica_eventi(self):
        eventi=[dict(citta="Cerignola",categoria="Locali & Serate",dataInizio="2026-11-28",dataFine="2026-11-28")]
        prima=[dict(e) for e in eventi]
        r=a.autodiagnosi(eventi,{"a":{"stato":"HTTP 403"},"b":{"stato":"pausa"}},[],date(2026,11,27))
        self.assertIn("poche_immagini_serate",r["segnali"])
        self.assertIn("molte_fonti_in_errore",r["segnali"])
        self.assertEqual(r["fontiTentate"],1)
        self.assertEqual(eventi,prima)

if __name__=="__main__":
    unittest.main()
