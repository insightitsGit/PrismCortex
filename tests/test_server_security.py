"""Server security: API-key auth + input size limits (no Gemini key needed)."""
from fastapi.testclient import TestClient

from prismcortex import auth, server


def _client(monkeypatch, api_key):
    if api_key:
        monkeypatch.setenv("PRISMCORTEX_API_KEY", api_key)
    else:
        monkeypatch.delenv("PRISMCORTEX_API_KEY", raising=False)
    auth.reload_keys()
    monkeypatch.setattr(server, "_memory", None)
    monkeypatch.setattr(server, "_tenant_mgr", None)
    return TestClient(server.app)


def test_health_open_but_endpoints_require_key(monkeypatch):
    c = _client(monkeypatch, "secret123")
    assert c.get("/health").status_code == 200                 # health is open
    assert c.get("/metrics").status_code == 401                # protected, no key
    assert c.get("/metrics", headers={"x-api-key": "wrong"}).status_code == 401
    assert c.get("/metrics", headers={"x-api-key": "secret123"}).status_code == 200
    assert c.get("/metrics", headers={"authorization": "Bearer secret123"}).status_code == 200


def test_oversized_input_rejected(monkeypatch):
    c = _client(monkeypatch, None)  # auth off; testing input validation
    r = c.post("/recall", json={"query": "x" * 9000})          # > 8000 max
    assert r.status_code == 422
    r2 = c.post("/digest", json={"text": "y" * 200_000})       # > 100k max
    assert r2.status_code == 422
