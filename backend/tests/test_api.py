from fastapi.testclient import TestClient

from app import main
from app.ratelimit import RateLimiter

# Punkt som ligg for langt frå kvarandre blir avviste før nokon data blir henta frå nettet
TOO_FAR = {"start": {"lat": 62.0, "lon": 7.0}, "end": {"lat": 63.0, "lon": 8.0}}


def test_route_returns_429_when_rate_limit_is_exceeded(monkeypatch):
    monkeypatch.setattr(main, "rate_limiter", RateLimiter([(2, 60)]))
    client = TestClient(main.app)

    assert client.post("/api/route", json=TOO_FAR).status_code == 422
    assert client.post("/api/route", json=TOO_FAR).status_code == 422
    resp = client.post("/api/route", json=TOO_FAR)
    assert resp.status_code == 429
    assert "Prøv igjen om 1 min" in resp.json()["detail"]
    assert int(resp.headers["Retry-After"]) <= 60


def test_health_is_not_rate_limited(monkeypatch):
    monkeypatch.setattr(main, "rate_limiter", RateLimiter([(1, 60)]))
    client = TestClient(main.app)
    assert all(client.get("/api/health").status_code == 200 for _ in range(5))
