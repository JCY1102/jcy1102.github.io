"""CV PDF printing must finish even when Chrome does not exit after writing the file.

Run: .venv/bin/python -m unittest discover -s projects/personal-homepage/tests
"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build import print_pdf  # noqa: E402

# Behaves like headless Chrome 154 on macOS: writes the PDF, reports it on stderr, then never exits.
FAKE_CHROME = f"""#!{sys.executable}
import sys, time
pdf = next(a.split("=", 1)[1] for a in sys.argv if a.startswith("--print-to-pdf="))
open(pdf, "wb").write(b"%PDF-1.4 fake")
{{report}}
{{body}}
"""
REPORT = 'print(f"13 bytes written to file {pdf}", file=sys.stderr, flush=True)'


def fake_chrome(folder, body, report=True):
    path = Path(folder) / "chrome"
    path.write_text(FAKE_CHROME.replace("{report}", REPORT if report else "").replace("{body}", body), encoding="utf-8")
    path.chmod(0o755)
    return str(path)


@unittest.skipIf(os.name == "nt", "fake Chrome is a shebang script")
class PrintPdf(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "cv.html").write_text("<h1>CV</h1>", encoding="utf-8")
        self.pdf = self.dir / "cv.pdf"
        self.saved = os.environ.get("CHROME_BIN")

    def tearDown(self):
        if self.saved is None:
            os.environ.pop("CHROME_BIN", None)
        else:
            os.environ["CHROME_BIN"] = self.saved
        self.tmp.cleanup()

    def test_returns_once_pdf_is_written_even_if_chrome_hangs(self):
        os.environ["CHROME_BIN"] = fake_chrome(self.dir, "time.sleep(600)")
        start = time.monotonic()
        print_pdf(self.dir / "cv.html", self.pdf, timeout=20)
        self.assertLess(time.monotonic() - start, 10)
        self.assertEqual(self.pdf.read_bytes(), b"%PDF-1.4 fake")

    def test_returns_when_message_goes_to_stdout_and_chrome_hangs(self):
        body = 'print("13 bytes written to file", flush=True)\ntime.sleep(600)'
        os.environ["CHROME_BIN"] = fake_chrome(self.dir, body, report=False)
        start = time.monotonic()
        print_pdf(self.dir / "cv.html", self.pdf, timeout=20)
        self.assertLess(time.monotonic() - start, 10)

    def test_returns_when_pdf_is_written_silently_and_chrome_hangs(self):
        os.environ["CHROME_BIN"] = fake_chrome(self.dir, "time.sleep(600)", report=False)
        start = time.monotonic()
        print_pdf(self.dir / "cv.html", self.pdf, timeout=20)
        self.assertLess(time.monotonic() - start, 10)
        self.assertEqual(self.pdf.read_bytes(), b"%PDF-1.4 fake")

    def test_helper_still_writing_to_the_profile_does_not_fail_the_build(self):
        # Like the Linux CI runner: a Chrome helper keeps writing into --user-data-dir
        # after the main process is stopped, so the temporary profile cannot be removed.
        helper = self.dir / "helper.py"
        helper.write_text(
            "import os, sys, time\n"
            "end = time.monotonic() + 4\n"
            "i = 0\n"
            "while time.monotonic() < end:\n"
            "    folder = os.path.join(sys.argv[1], 'Default')\n"
            "    try:\n"
            "        os.makedirs(folder, exist_ok=True)\n"
            "        open(os.path.join(folder, f'f{i}'), 'w').close()\n"
            "    except OSError:\n"
            "        pass\n"
            "    i += 1\n",
            encoding="utf-8",
        )
        body = "\n".join([
            "import subprocess",
            "profile = next(a.split('=', 1)[1] for a in sys.argv if a.startswith('--user-data-dir='))",
            f"subprocess.Popen([sys.executable, {str(helper)!r}, profile])",
            "time.sleep(0.5)",
            'print(f"13 bytes written to file {pdf}", file=sys.stderr, flush=True)',
            "time.sleep(600)",
        ])
        os.environ["CHROME_BIN"] = fake_chrome(self.dir, body, report=False)
        print_pdf(self.dir / "cv.html", self.pdf, timeout=20)
        self.assertEqual(self.pdf.read_bytes(), b"%PDF-1.4 fake")

    def test_chrome_that_exits_normally_still_works(self):
        os.environ["CHROME_BIN"] = fake_chrome(self.dir, "")
        print_pdf(self.dir / "cv.html", self.pdf, timeout=20)
        self.assertTrue(self.pdf.exists())

    def test_chrome_failure_raises(self):
        path = self.dir / "chrome"
        path.write_text(f"#!{sys.executable}\nimport sys\nsys.exit(3)\n", encoding="utf-8")
        path.chmod(0o755)
        os.environ["CHROME_BIN"] = str(path)
        with self.assertRaises(RuntimeError):
            print_pdf(self.dir / "cv.html", self.pdf, timeout=20)


if __name__ == "__main__":
    unittest.main()
