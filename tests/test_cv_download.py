"""A revised CV must use a new download URL even on the same date."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build


class CvDownload(unittest.TestCase):
    def test_same_day_pdf_revision_changes_download_url(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config").mkdir()
            (root / "data").mkdir()
            (root / "templates").mkdir()
            (root / "static" / "assets").mkdir(parents=True)
            (root / "config" / "profile.yaml").write_text('email: test@example.org\n', encoding="utf-8")
            (root / "config" / "journals.yaml").write_text('{}', encoding="utf-8")
            data = dict(orcid="test", fetched_at="2026-11-26", educations=[], employments=[], qualifications=[], works=[])
            (root / "data" / "orcid_cache.json").write_text(json.dumps(data), encoding="utf-8")
            (root / "templates" / "index.html.j2").write_text('<a download href="{{ cv_file }}">CV</a>', encoding="utf-8")
            (root / "templates" / "cv.html.j2").write_text('CV', encoding="utf-8")
            out = root / "_site"
            urls = []
            for content in (b"%PDF-1.4 preprint", b"%PDF-1.4 published"):
                def render_pdf(html_path, pdf_path):
                    pdf_path.write_bytes(content)
                with patch.object(build, "ROOT", root), patch.object(build, "OUT", out), patch.object(build, "print_pdf", render_pdf):
                    build.main()
                url = re.search(r'href="([^"]+)"', (out / "index.html").read_text(encoding="utf-8")).group(1)
                urls.append(url)
                self.assertEqual((out / url.split("?")[0]).read_bytes(), content)
            self.assertNotEqual(urls[0], urls[1], "Same-day CV updates must bypass the old cached PDF")
