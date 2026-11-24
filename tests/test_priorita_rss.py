import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
import aggiorna_eventi as motore

class PrioritaRSS(unittest.TestCase):
    def test_serata_con_data_precede_risultato_generico(self):
        self.assertGreater(motore.priorita_candidato_rss("Cerignola DJ set 28 novembre", ""), motore.priorita_candidato_rss("Cerignola evento", ""))
        self.assertEqual(motore.priorita_candidato_rss("Cerignola cronaca", ""), -1)
        self.assertEqual(motore.priorita_candidato_rss("Party a Milano", ""), -1)

    def test_candidato_utile_oltre_i_primi_diciotto(self):
        rss = "<rss><channel>" + "".join(f"<item><title>Cerignola evento {i}</title><link>https://example.org/{i}</link></item>" for i in range(25)) + "<item><title>Cerignola DJ set 28 novembre</title><link>https://example.org/serata</link></item></channel></rss>"
        session = Mock()
        session.get.side_effect = [SimpleNamespace(status_code=200, content=rss.encode())] + [SimpleNamespace(status_code=200, headers={"Content-Type":"text/html"}, url="https://example.org/evento", apparent_encoding="utf-8", text="<h1>Test</h1>") for _ in range(6)]
        with patch.object(motore, "analizza_pagina_evento", return_value=[{"titolo":"test"}]):
            motore.raccogli_da_feed_social(session, {"nome":"RSS test", "url":"https://example.org/rss"})
        self.assertEqual(session.get.call_args_list[1].args[0], "https://example.org/serata")
        self.assertEqual(session.get.call_count, 7)
