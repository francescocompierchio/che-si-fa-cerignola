import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import aggiorna_eventi
import radar_meta as meta


class RadarMetaTests(unittest.TestCase):
    config = {
        "META_GRAPH_VERSION": "v24.0",
        "META_IG_ACCOUNT_ID": "12345678910",
        "META_IG_ACCESS_TOKEN": "valore-di-prova",
        "META_IG_PROFILES": "locale_aderente altro_locale ignorato()",
    }

    def test_senza_accesso_non_interroga_la_rete(self):
        session = MagicMock()
        events, report = meta.raccogli(aggiorna_eventi, {}, session=session)
        self.assertEqual(events, [])
        self.assertEqual(report["stato"], "non_configurato")
        self.assertIn("META_IG_ACCESS_TOKEN", report["instagram"]["impostazioniMancanti"])
        self.assertIn("META_FB_PAGE_IDS", report["facebook"]["impostazioniMancanti"])
        session.get.assert_not_called()
        _, profiles, validation = meta.selezione(dict(self.config, META_GRAPH_VERSION="../"))
        self.assertEqual(profiles, [])
        self.assertEqual(validation["instagram"]["impostazioniNonValide"], ["META_GRAPH_VERSION"])

    def test_connettore_legge_solo_endpoint_ufficiale_e_senza_redirect(self):
        version, profiles, _ = meta.selezione(dict(self.config, META_IG_PROFILES="@Locale_Aderente, altro_locale ignorato()"))
        self.assertEqual([row[1] for row in profiles], ["locale_aderente", "altro_locale"])
        session = MagicMock()
        response = session.get.return_value.__enter__.return_value
        response.status_code = 200
        row = {"caption": "Annuncio di prova"}
        response.iter_content.return_value = [json.dumps({"business_discovery":{"media":{"data":[row]}}}).encode()]
        self.assertEqual(meta.leggi(session, version, profiles[0]), ([row], 200))
        args, kwargs = session.get.call_args
        self.assertEqual(args, ("https://graph.facebook.com/v24.0/12345678910",))
        self.assertFalse(kwargs["allow_redirects"])
        self.assertIn("username(locale_aderente)", kwargs["params"]["fields"])
        self.assertNotIn("access_token", kwargs["params"])

    def test_limita_richieste_e_rispetta_pausa_dopo_429(self):
        session = MagicMock()
        session.get.return_value.__enter__.return_value.status_code = 429
        now = datetime(2026, 11, 26, 18, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory, patch.object(meta, "STATE", Path(directory)/"meta.json"):
            result, report = meta.raccogli(aggiorna_eventi, self.config, now, session)
            self.assertEqual(result, [])
            self.assertEqual(report["esiti"], {"instagram/429": 1})
            self.assertEqual(meta.raccogli(aggiorna_eventi, self.config, now, session)[1]["stato"], "pausa")
        self.assertEqual(session.get.call_count, 1)

    def test_notizia_fuori_dominio_o_con_data_vecchia_viene_scartata(self):
        now = datetime(2026, 11, 26, 18, tzinfo=timezone.utc)
        row = {"caption":"DJ set a Cerignola", "permalink":"https://instagram.com/p/example", "timestamp":"2026-11-20T17:10:00Z"}
        fake = MagicMock()
        fake.eventi_da_locandina.return_value = [{"titolo":"Test"}]
        reads = [row, dict(row, permalink="https://instagram.com.example/p/example"),
                 dict(row, timestamp="2025-11-20T17:10:00Z"),dict(row,permalink="https://instagram.com/stories/profilo/123456")]
        self.assertEqual(meta.eventi_da_post(fake, reads, "instagram", now), [{"titolo":"Test"}])
        self.assertEqual(fake.eventi_da_locandina.call_count,1)

    def test_meta_segnala_token_o_limite_in_http_400_senza_esporre_la_risposta(self):
        session = MagicMock()
        response = session.get.return_value.__enter__.return_value
        response.status_code = 400
        now = datetime(2026, 11, 26, 18, tzinfo=timezone.utc)
        for code, status in ((190, 401), (10, 403), (17, 429)):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory, patch.object(meta, "STATE", Path(directory)/"meta.json"):
                response.iter_content.return_value = [json.dumps({"error":{"code":code,"message":"dato da non pubblicare"}}).encode()]
                _, report = meta.raccogli(aggiorna_eventi, self.config, now, session)
                self.assertEqual(report["stato"], "errore")
                self.assertEqual(report["esiti"], {f"instagram/{status}":1})
                self.assertNotIn("dato da non pubblicare", str(report))
                self.assertNotIn(self.config["META_IG_ACCESS_TOKEN"], str(report))
