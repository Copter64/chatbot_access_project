"""Tests for utils/token_generator.py."""

import string

from utils.token_generator import (
    generate_access_token,
    generate_token,
    is_valid_token_format,
)

ALLOWED_CHARS = set(string.ascii_letters + string.digits + "-_")


class TestGenerateToken:
    """Tests for generate_token()."""

    def test_default_length_is_32(self):
        assert len(generate_token()) == 32

    def test_custom_length(self):
        for length in (16, 32, 64, 128):
            assert len(generate_token(length)) == length

    def test_only_allowed_characters(self):
        for _ in range(20):
            token = generate_token(64)
            assert all(c in ALLOWED_CHARS for c in token), f"Bad char in: {token}"

    def test_tokens_are_unique(self):
        tokens = {generate_token() for _ in range(100)}
        assert len(tokens) == 100


class TestGenerateAccessToken:
    """Tests for generate_access_token()."""

    def test_returns_32_char_string(self):
        token = generate_access_token()
        assert isinstance(token, str)
        assert len(token) == 32

    def test_only_allowed_characters(self):
        token = generate_access_token()
        assert all(c in ALLOWED_CHARS for c in token)

    def test_tokens_differ_across_calls(self):
        tokens = {generate_access_token() for _ in range(50)}
        assert len(tokens) == 50


class TestIsValidTokenFormat:
    """Tests for is_valid_token_format()."""

    def test_valid_token_returns_true(self):
        assert is_valid_token_format(generate_access_token()) is True

    def test_none_returns_false(self):
        assert is_valid_token_format(None) is False

    def test_empty_string_returns_false(self):
        assert is_valid_token_format("") is False

    def test_too_short_returns_false(self):
        assert is_valid_token_format("abc123") is False

    def test_exactly_16_chars_returns_true(self):
        assert is_valid_token_format("a" * 16) is True

    def test_too_long_returns_false(self):
        assert is_valid_token_format("a" * 129) is False

    def test_exactly_128_chars_returns_true(self):
        assert is_valid_token_format("a" * 128) is True

    def test_invalid_characters_return_false(self):
        assert is_valid_token_format("valid-token!@#$" + "a" * 10) is False

    def test_spaces_return_false(self):
        assert is_valid_token_format("valid token " + "a" * 10) is False

    def test_hyphens_and_underscores_allowed(self):
        assert is_valid_token_format("abcd-efgh_ijkl-mnop") is True
