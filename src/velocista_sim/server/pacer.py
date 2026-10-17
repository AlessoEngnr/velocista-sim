"""Ritmo en tiempo real de una sesión y cola de salida con descarte (research R11).

Es el único código, junto con `app`, que lee el reloj: decide *cuándo* ejecutar cada paso,
nunca *qué* pasa en él.
"""

from __future__ import annotations

import asyncio
import math
from collections import deque
from typing import Callable, Protocol

STEP_S = 0.002
MAX_BATCH = 50
SLICE = 10  # pasos entre cesiones del loop: el envío y las otras sesiones no esperan una tanda entera
MAX_LAG_S = 0.100
MAX_SLEEP_S = 0.005
MAX_PENDING_TELEMETRY = 25
MAX_BACKLOG = 1000


class SteppableSession(Protocol):
    def step(self) -> list[dict]: ...

    def next_telemetry_step(self) -> int: ...


class OutboundQueue:
    """Cola de mensajes hacia el cliente.

    Descarta `telemetry` si ya hay 25 pendientes; nunca descarta `hello`, `config`, `event`,
    `error` ni `catalog`. Si estos superan 1.000 pendientes, marca `overflow` (cerrar con 1008).
    """

    def __init__(self, max_telemetry: int = MAX_PENDING_TELEMETRY, max_backlog: int = MAX_BACKLOG) -> None:
        self.max_telemetry = max_telemetry
        self.max_backlog = max_backlog
        self._items: deque[dict] = deque()
        self.telemetry_pending = 0
        self.overflow = False
        self._ready = asyncio.Event()

    def __len__(self) -> int:
        return len(self._items)

    def put(self, message: dict) -> bool:
        """Encola `message`; devuelve `False` si la conexión debe cerrarse por backlog."""
        if message.get("type") == "telemetry":
            if self.telemetry_pending >= self.max_telemetry:
                return not self.overflow
            self.telemetry_pending += 1
        elif len(self._items) - self.telemetry_pending >= self.max_backlog:
            self.overflow = True
            return False
        self._items.append(message)
        self._ready.set()
        return not self.overflow

    def get_nowait(self) -> dict:
        message = self._items.popleft()
        if message.get("type") == "telemetry":
            self.telemetry_pending -= 1
        if not self._items:
            self._ready.clear()
        return message

    async def get(self) -> dict:
        while not self._items:
            await self._ready.wait()
        return self.get_nowait()


class Pacer:
    """Ejecuta los pasos de `session` al ritmo de `clock` (segundos, monótono)."""

    def __init__(self, session: SteppableSession, clock: Callable[[], float], queue: OutboundQueue) -> None:
        self.session = session
        self.clock = clock
        self.queue = queue
        self.t_base = clock()
        self.steps_done = 0
        self.should_close = False

    def tick(self, limit: int = MAX_BATCH) -> int:
        """Ejecuta los pasos debidos (como máximo `limit` ≤ 50) y encola sus mensajes; devuelve cuántos."""
        target = math.floor((self.clock() - self.t_base) / STEP_S + 1e-9)
        count = min(max(target - self.steps_done, 0), limit)
        for _ in range(count):
            for message in self.session.step():
                if not self.queue.put(message):
                    self.should_close = True
            self.steps_done += 1
        behind = target - self.steps_done
        if behind * STEP_S > MAX_LAG_S:
            # Atraso grande: la simulación se enlentece en vez de recuperar a ráfagas.
            self.t_base += behind * STEP_S
        if self.queue.overflow:
            self.should_close = True
        return count

    def sleep_time(self) -> float:
        """Segundos de reloj hasta el próximo paso con telemetría, como máximo 5 ms."""
        next_step = self.session.next_telemetry_step()
        wait = self.t_base + next_step * STEP_S - self.clock()
        return min(max(wait, 0.0), MAX_SLEEP_S)

    async def run(self) -> None:
        """Bucle de la sesión hasta que haya que cerrar la conexión."""
        while not self.should_close:
            if self.tick(SLICE) == SLICE:
                await asyncio.sleep(0)  # sigue atrasado: cede el loop y continúa
            else:
                await asyncio.sleep(self.sleep_time())
