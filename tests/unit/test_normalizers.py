import pytest
from app.utils.normalizers import strip, digits_only, date_iso, currency_brl, apply


class TestStrip:
    def test_removes_whitespace(self):
        assert strip("  hello  ") == "hello"

    def test_empty_string(self):
        assert strip("") == ""

    def test_no_whitespace(self):
        assert strip("abc") == "abc"


class TestDigitsOnly:
    def test_cnpj_with_punctuation(self):
        assert digits_only("12.345.678/0001-99") == "12345678000199"

    def test_cpf_with_punctuation(self):
        assert digits_only("123.456.789-00") == "12345678900"

    def test_phone_with_spaces(self):
        assert digits_only("(11) 99999-1234") == "11999991234"

    def test_already_digits(self):
        assert digits_only("12345") == "12345"

    def test_empty(self):
        assert digits_only("") == ""


class TestDateIso:
    def test_slash_format(self):
        assert date_iso("15/03/2026") == "2026-03-15"

    def test_dash_format(self):
        assert date_iso("15-03-2026") == "2026-03-15"

    def test_already_iso(self):
        assert date_iso("2026-03-15") == "2026-03-15"

    def test_short_year(self):
        assert date_iso("15/03/26") == "2026-03-15"

    def test_with_whitespace(self):
        assert date_iso("  15/03/2026  ") == "2026-03-15"

    def test_unparseable_returns_original(self):
        assert date_iso("not-a-date") == "not-a-date"


class TestCurrencyBrl:
    def test_standard_format(self):
        assert currency_brl("1.250,50") == "1250.5"

    def test_with_rs_prefix(self):
        assert currency_brl("R$ 1.250,50") == "1250.5"

    def test_no_thousands(self):
        assert currency_brl("250,50") == "250.5"

    def test_whole_number(self):
        assert currency_brl("1.000,00") == "1000.0"

    def test_with_whitespace(self):
        assert currency_brl("  R$ 500,00  ") == "500.0"


class TestApply:
    def test_dispatches_strip(self):
        assert apply("strip", "  abc  ") == "abc"

    def test_dispatches_digits_only(self):
        assert apply("digits_only", "abc-123") == "123"

    def test_dispatches_date_iso(self):
        assert apply("date_iso", "15/03/2026") == "2026-03-15"

    def test_dispatches_currency_brl(self):
        assert apply("currency_brl", "1.000,00") == "1000.0"

    def test_none_normalizer(self):
        assert apply("none", "  unchanged  ") == "  unchanged  "

    def test_unknown_falls_back_to_strip(self):
        assert apply("unknown_normalizer", "  abc  ") == "abc"
