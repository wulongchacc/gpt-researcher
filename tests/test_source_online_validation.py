import asyncio
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


class SourceOnlineValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_2xx_and_uses_normalized_final_url(self):
        async def fetcher(url, timeout):
            self.assertEqual(timeout, 8.0)
            return validator.FetchResponse(
                status_code=200,
                final_url="https://Example.com/final/?utm_source=test#part",
            )

        checker = validator.SourceValidator(fetcher=fetcher)
        [result] = await checker.validate_many(["https://example.com/start"])

        self.assertTrue(result.is_valid)
        self.assertEqual(result.status, "valid")
        self.assertEqual(result.final_url, "https://example.com/final")
        self.assertEqual(result.attempts, 1)

    async def test_does_not_retry_permanent_http_failure(self):
        attempts = 0

        async def fetcher(url, timeout):
            nonlocal attempts
            attempts += 1
            return validator.FetchResponse(status_code=404, final_url=url)

        checker = validator.SourceValidator(fetcher=fetcher, max_retries=2)
        [result] = await checker.validate_many(["https://example.com/missing"])

        self.assertFalse(result.is_valid)
        self.assertEqual(result.status, "invalid")
        self.assertEqual(result.failure_reason, "http_404")
        self.assertEqual(result.attempts, 1)
        self.assertEqual(attempts, 1)

    async def test_classifies_access_restrictions_as_blocked(self):
        responses = {
            "https://example.com/forbidden": 403,
            "https://example.com/rate-limited": 429,
        }

        async def fetcher(url, timeout):
            return validator.FetchResponse(status_code=responses[url], final_url=url)

        checker = validator.SourceValidator(fetcher=fetcher)
        results = await checker.validate_many(list(responses))

        self.assertEqual([item.status for item in results], ["blocked", "blocked"])
        self.assertEqual(
            [item.failure_reason for item in results],
            ["http_403", "http_429"],
        )

    async def test_retries_timeout_and_returns_later_success(self):
        attempts = 0

        async def fetcher(url, timeout):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise asyncio.TimeoutError
            return validator.FetchResponse(status_code=204, final_url=url)

        checker = validator.SourceValidator(fetcher=fetcher, max_retries=2)
        [result] = await checker.validate_many(["https://example.com/flaky"])

        self.assertTrue(result.is_valid)
        self.assertEqual(result.attempts, 2)

    async def test_reports_timeout_after_retry_budget_is_exhausted(self):
        attempts = 0

        async def fetcher(url, timeout):
            nonlocal attempts
            attempts += 1
            raise asyncio.TimeoutError

        checker = validator.SourceValidator(fetcher=fetcher, max_retries=2)
        [result] = await checker.validate_many(["https://example.com/slow"])

        self.assertFalse(result.is_valid)
        self.assertEqual(result.status, "timeout")
        self.assertEqual(result.failure_reason, "timeout")
        self.assertEqual(result.attempts, 3)
        self.assertEqual(attempts, 3)

    async def test_limits_concurrent_fetches(self):
        active = 0
        peak = 0

        async def fetcher(url, timeout):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return validator.FetchResponse(status_code=200, final_url=url)

        checker = validator.SourceValidator(fetcher=fetcher, concurrency=2)
        results = await checker.validate_many(
            [f"https://example.com/{index}" for index in range(6)]
        )

        self.assertTrue(all(item.is_valid for item in results))
        self.assertEqual(peak, 2)


if __name__ == "__main__":
    unittest.main()
