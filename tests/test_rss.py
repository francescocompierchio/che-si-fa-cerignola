import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

import aggiorna_eventi as motore

class ParserRSSTests(unittest.TestCase):
    def test_link_rss_e_immagine_namespace(self):
        rss = b'<rss xmlns:media="http://search.yahoo.com/mrss/"><channel><item><title>Serata DJ a Cerignola</title><link>https://example.org/evento</link><description><![CDATA[<p>Serata DJ a Cerignola</p>]]></description><media:content url="https://example.org/locandina.jpg"/></item></channel></rss>'
        feed = motore.BeautifulSoup(rss, "xml")
        self.assertEqual(feed.item.link.get_text(), "https://example.org/evento")
        self.assertEqual(feed.item.find("media:content").get("url"), "https://example.org/locandina.jpg")
        session = Mock()
        session.get.side_effect = [
            SimpleNamespace(status_code=200, content=rss),
            SimpleNamespace(status_code=200, headers={"Content-Type":"text/html"}, url="https://example.org/evento", apparent_encoding="utf-8", text="<h1>Serata</h1>")
        ]
        evento = {"titolo":"Serata DJ"}
        with patch.object(motore, "analizza_pagina_evento", return_value=[evento]) as parser:
            risultato = motore.raccogli_da_feed_social(session, {"nome":"test RSS","url":"https://example.org/rss","citta_default":"Cerignola"})
        self.assertEqual(risultato, [evento])
        self.assertEqual(session.get.call_args_list[1].args[0], "https://example.org/evento")
        parser.assert_called_once()

    def test_link_non_http_non_interrogato(self):
        rss = b'<rss><channel><item><title>Serata DJ a Cerignola</title><link>file:///etc/passwd</link><description>Serata</description></item></channel></rss>'
        session = Mock()
        session.get.return_value = SimpleNamespace(status_code=200, content=rss)
        risultato = motore.raccogli_da_feed_social(session, {"nome":"test RSS","url":"https://example.org/rss"})
        self.assertEqual(risultato, [])
        self.assertEqual(session.get.call_count, 1)
