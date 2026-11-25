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
