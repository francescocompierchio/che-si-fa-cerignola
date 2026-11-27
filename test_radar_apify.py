import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import radar_apify as radar


class TestRadar(unittest.TestCase):
    def test_budget(self):
        plan = {"tier": "FREE", "monthlyBasePriceUsd": 0, "monthlyUsageCreditsUsd": 5}
        limits = {"limits": {"maxMonthlyUsageUsd": 5}, "current": {"monthlyUsageUsd": 0}}
        radar.verifica_budget(plan, limits)
        radar.verifica_budget({"id":"Free", "monthlyBasePriceUsd":0, "monthlyUsageCreditsUsd":5}, limits)
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
        actor["pricingInfos"][0]["minimalMaxTotalChargeUsd"] = None
        self.assertEqual(radar.verifica_prezzi(actor, datetime.now(timezone.utc)), {"post": 0.002})
        with patch.dict(actor["pricingInfos"][0], {"isPPEPlatformUsagePaidByUser":True}), self.assertRaises(radar.Pausa):
            radar.verifica_prezzi(actor, datetime.now(timezone.utc))
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

    def test_calendario_avvia_solo_http_con_robots_e_tetto(self):
        import aggiorna_eventi as engine

        plan = {"id":"Free", "monthlyBasePriceUsd":0, "monthlyUsageCreditsUsd":5}
        limits = {"limits":{"maxMonthlyUsageUsd":5}, "current":{"monthlyUsageUsd":0}}
        pricing = {"actorPermissionLevel":"LIMITED_PERMISSIONS", "pricingInfos":[{
            "startedAt":"2020-01-01T00:00:00Z", "pricingModel":"PAY_PER_EVENT",
            "minimalMaxTotalChargeUsd":None,
            "pricingPerEvent":{"actorChargeEvents":{"page-crawled":{"eventPriceUsd":0.0012}}},
        }]}
        run = {"status":"SUCCEEDED", "defaultDatasetId":"test", "usageTotalUsd":0.0012}
        policy = Mock()
        policy.can_fetch.return_value = True
        with TemporaryDirectory() as folder, patch.dict("os.environ", {"APIFY_TOKEN":"fixture"}), patch.object(
            radar, "STATE", Path(folder)/"apify.json"
        ), patch.object(radar, "OUTPUT", Path(folder)/"eventi.json"), patch.object(
            engine.fonti_editori, "robots", return_value=policy
        ), patch.object(radar, "api", side_effect=[{"data":{"plan":plan}}, {"data":limits}, {"data":pricing}, {"data":run}, []]) as api:
            result = radar.raccogli_calendario()
            self.assertEqual(result["stato"], "SUCCEEDED")
            self.assertEqual(result["tettoUsd"], 0.01)
            self.assertEqual(radar.raccogli_calendario()["stato"], "pausa programmata")
            self.assertEqual(api.call_count, 5)
            _, path, payload = api.call_args_list[3].args
            self.assertEqual(path, radar.ATTORE_CALENDARI + "/runs")
            self.assertEqual(payload["startUrls"], [{"url":radar.AGENDA_CERIGNOLA}])
            self.assertEqual(payload["renderJavaScript"], "never")
            self.assertEqual(payload["proxyConfiguration"], {"useApifyProxy":False})
            self.assertEqual(payload["maxRequestRetries"], 0)
            self.assertTrue(payload["respectRobotsTxtFile"])
            self.assertEqual(api.call_args_list[3].kwargs["maxTotalChargeUsd"], 0.01)

    def test_calendario_scarta_pagine_non_pertinenti_e_reindirizzate(self):
        engine = Mock()
        engine.analizza_pagina_evento.return_value = [{"citta":"Cerignola", "descrizione":"Serata", "locandinaUrl":"https://altro.example/foto.jpg"}]
        engine.evento_non_attivo.return_value = False
        url = radar.AGENDA_CERIGNOLA + "serata-di-prova/"
        def pagina(url, loaded=None, status=200):
            return {"url":url, "rawHtml":"<main>Evento comunale con descrizione, data e luogo.</main>",
                    "crawl":{"httpStatusCode":status,"loadedUrl":loaded or url}}
        eventi, metrics = radar.leggi_righe_calendario([
            pagina(radar.AGENDA_CERIGNOLA), pagina(url), pagina(url, "https://altro.example/evento"),
            pagina(url, status=403), pagina("https://altro.example/vivere-il-comune/eventi/serata-di-prova/"),
        ], engine)
        self.assertEqual(metrics, {"pagineLette":2,"indiciLetti":1,"schedeLette":1})
        self.assertEqual(eventi, [{"citta":"Cerignola","descrizione":"Serata · Fonte: Comune di Cerignola"}])
        self.assertEqual(engine.analizza_pagina_evento.call_count, 1)
