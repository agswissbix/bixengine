import os
import django
from django.conf import settings

if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bixengine.settings")
    django.setup()

from django.test import SimpleTestCase
from django.core.cache import cache
from unittest import mock

from commonapp.currency import (
    convert_amount,
    get_frankfurter_rates,
    normalize_currency,
    _cache_key,
)

MODULE_PATH = "commonapp.currency"

class CurrencyUtilsTest(SimpleTestCase):
    
    def setUp(self):
        cache.clear()

    # --- Test normalize_currency ---
    def test_normalize_currency(self):
        self.assertEqual(normalize_currency("eur"), "EUR")
        self.assertEqual(normalize_currency("  chf  "), "CHF")
        self.assertIsNone(normalize_currency(None))
        self.assertIsNone(normalize_currency(""))

    # --- Test _cache_key ---
    def test_cache_key_generation(self):
        key1 = _cache_key("EUR", ["USD", "CHF"], None)
        key2 = _cache_key("EUR", ["CHF", "USD"], None)
        self.assertEqual(key1, key2)
        self.assertIn("latest", key1)

        key_date = _cache_key("EUR", ["USD"], "2023-01-01")
        self.assertIn("2023-01-01", key_date)

    # --- Test get_frankfurter_rates ---

    @mock.patch(f"{MODULE_PATH}.requests.get")
    def test_get_rates_api_success_latest(self, mock_get):
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "amount": 1.0, 
            "base": "EUR", 
            "date": "2023-01-01", 
            "rates": {"USD": 1.1, "GBP": 0.85}
        }
        mock_get.return_value = mock_response

        rates = get_frankfurter_rates("EUR", ["USD", "GBP"])

        self.assertEqual(rates["USD"], 1.1)
        self.assertEqual(rates["GBP"], 0.85)
        
        args, kwargs = mock_get.call_args
        self.assertIn("/latest", args[0])
        self.assertEqual(kwargs['params']['from'], 'EUR')
        
        cached_data = cache.get(_cache_key("EUR", ["GBP", "USD"], None))
        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data["USD"], 1.1)

    @mock.patch(f"{MODULE_PATH}.requests.get")
    def test_get_rates_api_success_historical(self, mock_get):
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"rates": {"USD": 1.05}}
        mock_get.return_value = mock_response

        dt = "2022-12-25"
        rates = get_frankfurter_rates("EUR", ["USD"], date=dt)

        self.assertEqual(rates["USD"], 1.05)
        args, _ = mock_get.call_args
        self.assertIn("2022-12-25", args[0])

    @mock.patch(f"{MODULE_PATH}.requests.get")
    def test_get_rates_uses_cache(self, mock_get):
        base = "EUR"
        to_list = ["USD"]
        key = _cache_key(base, to_list, None)
        cache.set(key, {"USD": 2.0}, 3600)

        rates = get_frankfurter_rates(base, to_list)

        self.assertEqual(rates["USD"], 2.0)
        mock_get.assert_not_called()

    @mock.patch(f"{MODULE_PATH}.requests.get")
    def test_get_rates_api_failure(self, mock_get):
        mock_get.side_effect = Exception("Connection Error")

        with self.assertLogs(logger=MODULE_PATH, level='ERROR') as cm:
            rates = get_frankfurter_rates("EUR", ["USD"])
        
        self.assertEqual(rates, {})

    @mock.patch(f"{MODULE_PATH}.requests.get")
    def test_get_rates_include_base(self, mock_get):
        mock_response = mock.Mock()
        mock_response.json.return_value = {"rates": {"USD": 1.1}}
        mock_get.return_value = mock_response

        rates = get_frankfurter_rates("EUR", ["USD", "EUR"])

        self.assertEqual(rates["USD"], 1.1)
        self.assertEqual(rates["EUR"], 1.0)

    # --- Test convert_amount ---

    def test_convert_amount_success(self):
        rates = {"USD": 1.2, "CHF": 0.95}
        result = convert_amount(120, "USD", "EUR", rates)
        self.assertAlmostEqual(result, 100.0)

    def test_convert_amount_same_currency(self):
        result = convert_amount(50, "EUR", "EUR", {})
        self.assertEqual(result, 50.0)

    def test_convert_amount_missing_rate(self):
        rates = {"USD": 1.1}
        result = convert_amount(100, "JPY", "EUR", rates)
        self.assertIsNone(result)

    def test_convert_amount_invalid_inputs(self):
        rates = {"USD": 1.1}
        self.assertIsNone(convert_amount(None, "USD", "EUR", rates))
        rates_zero = {"USD": 0.0}
        self.assertIsNone(convert_amount(100, "USD", "EUR", rates_zero))