import unittest
import indexnow_submit as x

class IndexNowTests(unittest.TestCase):
    def test_scope(self):
        self.assertTrue(x.permitted(x.BASE+"eventi/weekend.html"))
        for url in [x.BASE+"admin.html",x.BASE+"privacy.html",x.BASE+"?admin=1",x.BASE+"eventi/../admin.html","https://francescocompierchio.github.io/altro/","https://example.org/eventi/"]:
            self.assertFalse(x.permitted(url))
    def test_changes(self):
        a=x.BASE+"eventi/weekend.html"
        b=x.BASE+"eventi/cerignola.html"
        c=x.BASE+"eventi/hub-serate.html"
        self.assertEqual(x.plan({a:"2026-11-25",c:"2026-11-25"},{a:"2026-11-24",b:"2026-11-24"}),[a,c,b])
        self.assertEqual(x.plan({a:"2026-11-25"},{a:"2026-11-25"}),[])
    def test_initial(self):
        self.assertEqual(x.plan({x.BASE:"",x.BASE+"eventi/":"",x.BASE+"eventi/test-evento.html":"2026-11-25"},None),[x.BASE,x.BASE+"eventi/"])
    def test_sitemap(self):
        xml='<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>'+x.BASE+'</loc></url><url><loc>'+x.BASE+'eventi/</loc></url><url><loc>'+x.BASE+'admin.html</loc></url></urlset>'
        self.assertEqual(set(x.parse_sitemap(xml)),{x.BASE,x.BASE+"eventi/"})
        with self.assertRaises(ValueError):
            x.parse_sitemap('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"/>')
