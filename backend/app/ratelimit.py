"""Enkel grense for kor mange førespurnader kvar klient kan gjere (i minnet, éin prosess)."""

from collections import deque
import time


class RateLimiter:
    """Glidande tidsvindauge: maks `count` førespurnader per `seconds`, for kvar grense."""

    def __init__(self, limits: list[tuple[int, float]], clock=time.monotonic):
        self.limits = limits
        self.window = max(seconds for _, seconds in limits)
        self.clock = clock
        self.hits: dict[str, deque[float]] = {}
        self.last_cleanup = clock()

    def check(self, key: str) -> float | None:
        """Registrerer ein førespurnad. Returnerer None om han er tillaten, elles sekund til neste forsøk."""
        now = self.clock()
        self._cleanup(now)
        hits = self.hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window:
            hits.popleft()

        retry_after = 0.0
        for count, seconds in self.limits:
            recent = [t for t in hits if t > now - seconds]
            if len(recent) >= count:
                # Ledig igjen når den eldste førespurnaden i vindauget har gått ut
                retry_after = max(retry_after, recent[-count] + seconds - now)
        if retry_after > 0:
            return retry_after

        hits.append(now)
        return None

    def _cleanup(self, now: float) -> None:
        """Fjernar klientar som ikkje har vore aktive, så minnebruken ikkje veks for alltid."""
        if now - self.last_cleanup < self.window:
            return
        self.last_cleanup = now
        for key in [k for k, hits in self.hits.items() if not hits or hits[-1] <= now - self.window]:
            del self.hits[key]
