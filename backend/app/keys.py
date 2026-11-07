"""API key rotation with cooldowns.

A `KeyPool` hands out keys round-robin. A key that hit a rate limit or was
rejected is put on cooldown and tried last, so one exhausted free-tier key
never blocks a request while another key still has quota.
"""
from __future__ import annotations

import time


class KeyPool:
    def __init__(self, name: str, keys: list[str]) -> None:
        self.name = name
        self._keys = list(keys)
        self._cooldown_until: dict[tuple[int, str], float] = {}
        self._cursor = 0

    def __len__(self) -> int:
        return len(self._keys)

    def candidates(self, scope: str = "") -> list[tuple[str, str]]:
        """Return [(label, key)] in the order to try: healthy keys first (rotated), cooling last.

        `scope` (e.g. a model name) lets a key be exhausted for one model but still usable for another.
        """
        if not self._keys:
            return []
        now = time.monotonic()
        order = [(self._cursor + i) % len(self._keys) for i in range(len(self._keys))]
        self._cursor = (self._cursor + 1) % len(self._keys)
        healthy = [i for i in order if self._cooldown_until.get((i, scope), 0) <= now]
        cooling = [i for i in order if i not in healthy]
        return [(f"{self.name}#{i + 1}", self._keys[i]) for i in healthy + cooling]

    def penalize(self, label: str, seconds: float, scope: str = "") -> None:
        index = int(label.rsplit("#", 1)[1]) - 1
        self._cooldown_until[(index, scope)] = time.monotonic() + seconds
