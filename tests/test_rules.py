"""Rules that decide how publications appear on the site and in the CV.

Run: .venv/Scripts/python.exe -m unittest discover -s projects/personal-homepage/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_orcid import abbreviate_author, normalize_doi  # noqa: E402
from build import classify, format_authors  # noqa: E402

JOURNALS = {
    "SCIE": ["Hydrobiologia", "Journal of Hydrology: Regional Studies"],
    "KCI": ["Journal of Korean Society on Water Environment"],
}


class AuthorRules(unittest.TestCase):
    def test_initials_keep_hyphens(self):
        self.assertEqual(abbreviate_author({"given": "Woo-Hyun", "family": "Jeon"}), "Jeon W-H")

    def test_initials_join_spaced_given_names(self):
        self.assertEqual(abbreviate_author({"given": "Soo Min", "family": "Song"}), "Song SM")

    def test_single_given_name(self):
        self.assertEqual(abbreviate_author({"given": "Chanyoung", "family": "Jeong"}), "Jeong C")

    def test_missing_given_name(self):
        self.assertEqual(abbreviate_author({"family": "Consortium"}), "Consortium")

    def test_owner_is_bold_and_list_uses_and(self):
        authors = [
            {"name": "Song J", "me": False},
            {"name": "Jeong C", "me": True},
            {"name": "Kong D", "me": False},
        ]
        self.assertEqual(format_authors(authors), "Song J, <b>Jeong C</b> and Kong D")

    def test_two_authors(self):
        authors = [{"name": "Jeong C", "me": True}, {"name": "Kong D", "me": False}]
        self.assertEqual(format_authors(authors), "<b>Jeong C</b> and Kong D")


class DoiRules(unittest.TestCase):
    def test_strips_resolver_prefix(self):
        self.assertEqual(normalize_doi("https://doi.org/10.15681/KSWE.2026.42.3.254"), "10.15681/KSWE.2026.42.3.254")

    def test_plain_doi_unchanged(self):
        self.assertEqual(normalize_doi("10.1007/s10750-026-06158-3"), "10.1007/s10750-026-06158-3")


class ClassifyRules(unittest.TestCase):
    def test_scie_match_ignores_case_and_spaces(self):
        self.assertEqual(classify({"type": "journal-article", "journal": " hydrobiologia "}, JOURNALS), "SCIE")

    def test_kci_match(self):
        work = {"type": "journal-article", "journal": "Journal of Korean Society on Water Environment"}
        self.assertEqual(classify(work, JOURNALS), "KCI")

    def test_preprint_goes_to_preprints(self):
        self.assertEqual(classify({"type": "preprint", "journal": "Hydrobiologia"}, JOURNALS), "Preprints")

    def test_unknown_journal_is_flagged(self):
        self.assertEqual(classify({"type": "journal-article", "journal": "New Journal"}, JOURNALS), "Unclassified")


class ConfigFiles(unittest.TestCase):
    def test_journal_names_are_plain_strings(self):
        import yaml
        cfg = yaml.safe_load((Path(__file__).resolve().parents[1] / "config" / "journals.yaml").read_text(encoding="utf-8"))
        for group, names in cfg.items():
            for n in names:
                self.assertIsInstance(n, str, f"{group}: quote journal names that contain ':'")


if __name__ == "__main__":
    unittest.main()
