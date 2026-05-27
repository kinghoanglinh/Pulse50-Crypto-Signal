import unittest

from pulse50.cache.store import TTLCache


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TTLCacheTests(unittest.TestCase):
    def test_get_returns_value_and_age_before_expiry(self):
        clock = FakeClock()
        cache = TTLCache(clock=clock)

        cache.set("key", {"value": 1}, ttl_seconds=10)
        clock.advance(3)
        value, age = cache.get("key")

        self.assertEqual(value, {"value": 1})
        self.assertEqual(age, 3.0)

    def test_get_evicts_after_expiry(self):
        clock = FakeClock()
        cache = TTLCache(clock=clock)

        cache.set("key", "value", ttl_seconds=5)
        clock.advance(6)
        value, age = cache.get("key")

        self.assertIsNone(value)
        self.assertEqual(age, 6.0)
        stale_value, stale_age = cache.get_stale("key")
        self.assertEqual(stale_value, "value")
        self.assertEqual(stale_age, 6.0)


if __name__ == "__main__":
    unittest.main()
