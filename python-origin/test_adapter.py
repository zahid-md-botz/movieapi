"""Contract tests use explicit fixtures; none are production catalog data."""
import base64
import hashlib
import hmac
import os
import unittest
from unittest.mock import patch

import content
import engine
import manga


class AdapterTests(unittest.TestCase):
    def test_canonical_matches_supplied_javascript_protocol(self):
        body = '{"keyword":"日本語"}'
        expected = "\n".join(["POST", "application/json", "application/json",
                              str(len(body.encode())), "12345", hashlib.md5(body.encode()).hexdigest(),
                              "/path?a=2&a=3&z=1"])
        self.assertEqual(engine.canonical("POST", "https://api3.aoneroom.com/path?z=1&a=2&a=3", body, 12345), expected)
        with patch.dict(os.environ, {"MOVIEBOX_SIGNING_KEY_B64": base64.b64encode(b"test-fixture-key").decode()}):
            headers = engine.MovieBoxEngine().headers("POST", "https://api3.aoneroom.com/path?z=1&a=2&a=3", body, timestamp=12345)
        signature = base64.b64encode(hmac.new(b"test-fixture-key", expected.encode(), hashlib.md5).digest()).decode()
        self.assertEqual(headers["x-tr-signature"], "12345|2|" + signature)
        self.assertNotIn("x-forwarded-for", headers)

    def test_nested_details_and_ids_are_not_lost(self):
        result = engine.MovieBoxEngine.normalize({"subject": {"subjectId": "1234567890123456789", "title": "Fixture",
                                                "cover": {"url": "https://example.test/poster.jpg"}},
                                                "dubs": [{"language": "en"}]})
        self.assertEqual(result["subject_id"], "1234567890123456789")
        self.assertEqual(result["cover"], "https://example.test/poster.jpg")
        self.assertEqual(result["dubs"], [{"language": "en"}])
        self.assertEqual(engine.stream_id({"resourceId": "98765"}), "98765")

    def test_anime_catalog_filters_and_paginates_on_backend(self):
        class Service:
            normalize = staticmethod(lambda row: row)
            def call(self, action, params):
                self.action = action
                return {"operatingList": [{"subjects": [
                    {"subjectId": "12345", "title": "Anime fixture", "genre": "Animation"},
                    {"subjectId": "23456", "title": "Drama fixture", "genre": "Drama"}]}]}
        result = content.dispatch(Service(), "/api/v3/anime", {"perPage": "1"})
        self.assertEqual(result["data"]["total"], 1)
        self.assertEqual(result["data"]["items"][0]["subjectId"], "12345")

    def test_seasons_keep_existing_response_contract(self):
        class Service:
            def call(self, action, params):
                return {"title": "Fixture", "seasons": [{"se": 2, "maxEp": 3}]}
        result = content.dispatch(Service(), "/api/v3/season/12345/2", {})
        self.assertEqual(result["kind"], "direct")
        self.assertEqual(result["data"]["seasonTitle"], "Season 2")
        self.assertIsNone(result["data"]["episodes"][0]["title"])

    def test_invalid_catalog_parameters(self):
        for query in ({"page": "0"}, {"page": "nan"}, {"perPage": "101"}):
            with self.assertRaises(content.ContentError):
                content.dispatch(None, "/api/v3/anime", query)

    def test_manga_host_and_slug_validation(self):
        for url in ["http://rosyscans.id/a", "https://127.0.0.1/a", "https://rosyscans.id.evil.test/a",
                    "https://user:pass@rosyscans.id/a"]:
            with self.assertRaises(manga.MangaError):
                manga.safe_url(url)
        for value in ["../admin", "%2e%2e%2fadmin", "abc?x=y"]:
            with self.assertRaises(manga.MangaError):
                manga.slug(value)

    def test_manga_listing_preserves_shape(self):
        html = '<div class="bsx"><a href="/manga/demo/"><img src="/cover.jpg"><div class="tt">Demo</div></a><div class="epxs">Chapter 1</div></div><a class="next page-numbers"></a>'
        with patch.object(manga, "page", return_value=manga.BeautifulSoup(html, "html.parser")):
            result = manga.dispatch("/api/v3/manga/popular", {"page": ["2"]})
        self.assertEqual(result["page"], 2)
        self.assertTrue(result["hasNextPage"])
        self.assertEqual(result["results"][0]["title"], "Demo")


if __name__ == "__main__":
    unittest.main()
