import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "gpt_researcher" / "scraper" / "encoding.py"
SPEC = importlib.util.spec_from_file_location("scraper_encoding", MODULE_PATH)
ENCODING_MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ENCODING_MODULE)
resolve_response_encoding = ENCODING_MODULE.resolve_response_encoding


class _FakeResponse:
    def __init__(self, html: str, encoding: str, apparent_encoding: str):
        self.content = html.encode("gb18030")
        self.encoding = encoding
        self.apparent_encoding = apparent_encoding


class BeautifulSoupEncodingTests(unittest.TestCase):
    def test_uses_detected_chinese_encoding_when_response_defaults_to_latin1(self):
        html = (
            "<html><head><title>青年文化群体营销方案</title></head>"
            "<body><main>这是可正常阅读的中文正文。</main></body></html>"
        )
        response = _FakeResponse(
            html,
            encoding="ISO-8859-1",
            apparent_encoding="GB2312",
        )
        encoding = resolve_response_encoding(response)
        decoded = response.content.decode(encoding)

        self.assertEqual(encoding, "gb18030")
        self.assertIn("青年文化群体营销方案", decoded)
        self.assertIn("这是可正常阅读的中文正文。", decoded)

    def test_keeps_explicit_utf8_encoding(self):
        response = _FakeResponse(
            "<html></html>",
            encoding="UTF-8",
            apparent_encoding="Windows-1252",
        )

        self.assertEqual(resolve_response_encoding(response), "utf-8")


if __name__ == "__main__":
    unittest.main()
