import importlib
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType("gpt_researcher")
package.__path__ = [str(ROOT / "gpt_researcher")]
sys.modules.setdefault("gpt_researcher", package)

validator = importlib.import_module("gpt_researcher.sources.validator")
admit_scraped_source = validator.admit_scraped_source
normalize_url = validator.normalize_url


class ProductionSourceValidatorTests(unittest.TestCase):
    def test_admits_content_at_configured_character_and_sentence_boundaries(self):
        content = ("甲" * 198) + "。乙。"

        result = admit_scraped_source(
            {
                "url": "https://Example.com/article/?utm_source=test#section",
                "title": "边界来源",
                "raw_content": content,
            },
            min_content_chars=200,
            min_sentences=2,
        )

        self.assertTrue(result.is_usable)
        self.assertEqual(result.canonical_url, "https://example.com/article")
        self.assertEqual(result.title, "边界来源")
        self.assertGreaterEqual(result.content_chars, 200)
        self.assertEqual(result.sentence_count, 2)
        self.assertEqual(result.failure_reason, "ok")

    def test_rejects_sources_that_do_not_meet_content_requirements(self):
        cases = [
            ("短内容。仍然很短。", "content_too_short"),
            (("请登录后查看" * 35) + "。请先登录。", "login_page"),
            (("请输入验证码" * 35) + "。验证码错误。", "captcha_page"),
            (("页面不存在 404" * 35) + "。页面不存在。", "error_page"),
        ]

        for content, expected_reason in cases:
            with self.subTest(reason=expected_reason):
                result = admit_scraped_source(
                    {
                        "url": "https://example.com/article",
                        "raw_content": content,
                    },
                    min_content_chars=200,
                    min_sentences=2,
                )

                self.assertFalse(result.is_usable)
                self.assertEqual(result.failure_reason, expected_reason)

    def test_rejects_long_content_with_too_few_complete_sentences(self):
        result = admit_scraped_source(
            {
                "url": "https://example.com/article",
                "raw_content": ("这是一段没有结束符的正文" * 30) + "。",
            },
            min_content_chars=200,
            min_sentences=2,
        )

        self.assertFalse(result.is_usable)
        self.assertEqual(result.failure_reason, "too_few_sentences")

    def test_normalize_url_rejects_non_http_urls(self):
        for value in ("", "not-a-url", "ftp://example.com/a"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_url(value)


if __name__ == "__main__":
    unittest.main()
