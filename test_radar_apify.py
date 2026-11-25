import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import radar_apify as radar


class TestRadar(unittest.TestCase):
    def test_budget(self):
        plan = {"tier": "FREE", "monthlyBasePriceUsd": 0, "monthlyUsageCreditsUsd": 5}
        limits = {"limits": {"maxMonthlyUsageUsd": 5}, "current": {"monthlyUsageUsd": 0}}
        radar.verifica_budget(plan, limits)
        for field, value in (("tier", "BRONZE"), ("monthlyBasePriceUsd", 1)):
            with patch.dict(plan, {field: value}), self.assertRaises(radar.Pausa):
                radar.verifica_budget(plan, limits)
        for field, key, value in (("current", "monthlyUsageUsd", 4.8),
                                  ("current", "monthlyUsageUsd", float("nan")),
                                  ("limits", "maxMonthlyUsageUsd", 10)):
            with patch.dict(limits[field], {key: value}), self.assertRaises(radar.Pausa):
                radar.verifica_budget(plan, limits)

    def test_actor_non_compatibile(self):
        actor = {"pricingInfos": [{"startedAt": "2020-01-01T00:00:00Z", "pricingModel": "FLAT_PRICE_PER_MONTH"}]}
        with self.assertRaises(radar.Pausa):
            radar.verifica_prezzi(actor, datetime.now(timezone.utc))

    def test_rotazione(self):
        now = 1800000000
        profiles = radar.profili()
        url, _ = radar.scegli(profiles, {}, now)
        self.assertEqual(profiles[url][0], "Cerignola")
        self.assertNotEqual(radar.scegli(profiles, {url: {"at": now}}, now)[0], url)

    def test_prezzo_senza_tariffa_free(self):
        actor = {"actorPermissionLevel": "LIMITED_PERMISSIONS", "pricingInfos": [{
            "startedAt": "2020-01-01T00:00:00Z", "pricingModel": "PAY_PER_EVENT",
            "pricingPerEvent": {"actorChargeEvents": {"post": {"eventPriceUsd": 0.002}}}}]}
        self.assertEqual(radar.verifica_prezzi(actor, datetime.now(timezone.utc)), {"post": 0.002})
        actor["pricingInfos"][0]["minimalMaxTotalChargeUsd"] = 0.5
        with self.assertRaises(radar.Pausa):
            radar.verifica_prezzi(actor, datetime.now(timezone.utc))

    def test_snippet_google_non_e_un_evento(self):
        import aggiorna_eventi as engine
        rows = [{"organicResults": [{"url": "https://example.com/festa",
                                     "snippet": "Karaoke a Cerignola il 31 dicembre 2026"}]}]
        with patch("radar_apify.requests.get") as get:
            events, stats = radar.pagine_google(rows, engine)
        get.assert_not_called()
        self.assertFalse(events)
        self.assertEqual(stats["pagineLette"], 0)

    def test_post_con_e_senza_data_documentata(self):
        import aggiorna_eventi as engine
        from datetime import timedelta
        day = (engine.oggi_dt() + timedelta(days=5)).date()
        month = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()[day.month-1]
        title = "Gold Fashion Karaoke Show"
        post = "https://www.instagram.com/p/test-fixture/"
        text = f"{title}. Il {day.day} {month} {day.year} alle 21:00 presso Gold Fashion Pub a Cerignola."
        valid = engine.eventi_da_locandina(text, "", title, post)
        self.assertEqual([e["dataInizio"] for e in valid], [day.isoformat()])
        self.assertFalse(engine.eventi_da_locandina(text.replace(str(day.year), ""), "", title, post))
