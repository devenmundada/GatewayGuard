"""Settings validation and client IP extraction."""
import pytest
from starlette.requests import Request

from app.config import Settings


class TestJwtSecretGuard:
    def test_production_refuses_default_secret(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET", raising=False)
        with pytest.raises(ValueError, match="JWT_SECRET"):
            Settings(ENVIRONMENT="production", _env_file=None)

    def test_production_refuses_short_secret(self):
        with pytest.raises(ValueError, match="JWT_SECRET"):
            Settings(ENVIRONMENT="production", JWT_SECRET="short", _env_file=None)

    def test_production_accepts_long_secret(self):
        s = Settings(ENVIRONMENT="production", JWT_SECRET="x" * 40, _env_file=None)
        assert s.is_production

    def test_development_allows_default(self):
        Settings(ENVIRONMENT="development", _env_file=None)


def _request(peer="10.0.0.9", forwarded=None):
    headers = []
    if forwarded:
        headers.append((b"x-forwarded-for", forwarded.encode()))
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


class TestClientIp:
    def test_forwarded_header_ignored_by_default(self, monkeypatch):
        from app.utils import client_ip

        monkeypatch.setattr(client_ip.settings, "TRUSTED_PROXY_COUNT", 0)
        assert client_ip.get_client_ip(_request(forwarded="6.6.6.6")) == "10.0.0.9"

    def test_one_trusted_proxy_uses_last_entry(self, monkeypatch):
        from app.utils import client_ip

        monkeypatch.setattr(client_ip.settings, "TRUSTED_PROXY_COUNT", 1)
        # client forged "1.1.1.1"; our proxy appended the real peer 203.0.113.7
        req = _request(forwarded="1.1.1.1, 203.0.113.7")
        assert client_ip.get_client_ip(req) == "203.0.113.7"

    def test_missing_header_falls_back_to_peer(self, monkeypatch):
        from app.utils import client_ip

        monkeypatch.setattr(client_ip.settings, "TRUSTED_PROXY_COUNT", 1)
        assert client_ip.get_client_ip(_request()) == "10.0.0.9"
