import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree

from scripts import profile_cards as cards


def repo(name, *, fork=False, private=False, owner=cards.USERNAME):
    return {"name": name, "private": private, "owner": {"login": owner},
            "fork": fork, "stargazers_count": 2, "forks_count": 1}


class ProfileCardsTests(unittest.TestCase):
    def test_public_owned_data_and_nonfork_languages(self):
        replies = [{"followers": 3},
                   [repo("original"), repo("fork", fork=True),
                    repo("private", private=True), repo("elsewhere", owner="other")],
                   {"Python": 300, "HTML": 100}]
        with patch.object(cards, "api", side_effect=replies) as api:
            data = cards.collect()
        self.assertEqual([data[k] for k in ("repos", "stars", "forks", "followers")],
                         [2, 4, 2, 3])
        self.assertEqual(data["languages"], {"Python": 300, "HTML": 100})
        self.assertEqual(api.call_count, 3)
        self.assertEqual(api.call_args.args[0],
                         f"/repos/{cards.USERNAME}/original/languages")

    def test_repository_pagination(self):
        replies = [{"followers": 0}, [repo(str(i), fork=True) for i in range(100)],
                   [repo("last", fork=True)]]
        with patch.object(cards, "api", side_effect=replies) as api:
            data = cards.collect()
        self.assertEqual(data["repos"], 101)
        self.assertIn("page=2", api.call_args.args[0])

    def test_svg_escapes_and_groups_language_bytes(self):
        data = {"repos": 9, "stars": 8, "forks": 2, "followers": 3,
                "updated": "2026-10-29 10:00 UTC",
                "languages": {"A&B<test>": 50, **{f"Lang{i}": 10 for i in range(7)}}}
        rendered = cards.render(data)
        self.assertEqual(len(rendered), 16)
        for content in rendered.values():
            ElementTree.fromstring(content)
            self.assertNotIn("<script", content)
            self.assertNotIn("<foreignObject", content)
        language_svg = rendered["languages-dark.svg"]
        self.assertIn("A&amp;B&lt;test&gt;", language_svg)
        self.assertIn("Other", language_svg)
        self.assertIn("41.7%", language_svg)
        self.assertIn("25.0%", language_svg)

    def test_empty_languages(self):
        content = cards.languages({"languages": {}, "updated": "today"}, "dark")
        ElementTree.fromstring(content)
        self.assertIn("No language data yet", content)
        self.assertNotIn("nan", content.lower())

    def test_api_failure_preserves_existing_cards(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            target = Path(directory) / "stats-dark.svg"
            target.write_text("last successful card", encoding="utf-8")
            with patch.object(cards, "OUTPUT", Path(directory)), \
                    patch.object(cards, "collect", side_effect=URLError("offline")):
                with self.assertRaises(URLError):
                    cards.main()
            self.assertEqual(target.read_text(encoding="utf-8"), "last successful card")
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_blocked_repository_is_disclosed(self):
        replies = [{"followers": 3}, [repo("available"), repo("blocked")],
                   {"Python": 100}, HTTPError("url", 451, "blocked", {}, None)]
        with patch.object(cards, "api", side_effect=replies):
            data = cards.collect()
        self.assertEqual(data["repos"], 2)
        self.assertEqual(data["unavailable"], 1)
        self.assertIn("1 repos unavailable", cards.languages(data, "dark"))


if __name__ == "__main__":
    unittest.main()
