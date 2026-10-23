"""Retransmisión de eventos a todas las pestañas conectadas (Observer, design D6).

``ProgressHub`` guarda los WebSocket abiertos y les reenvía cada evento. Todo
pasa por una única cola y una única tarea (``_pump``), así:

- los eventos llegan a cada pestaña en el orden en que ocurrieron;
- una pestaña nueva recibe primero el snapshot del estado tomado en el momento
  en que se conectó, y después solo los eventos posteriores (ni repetidos ni
  perdidos), porque la suscripción se encola en el mismo orden que los eventos.
"""

import asyncio
import contextlib
import logging

from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)


class ProgressHub:
  """Conexiones WebSocket abiertas y cola de eventos a retransmitir."""

  def __init__(self) -> None:
    """Sin conexiones; ``start()`` crea la cola dentro del event loop."""
    self._clients: set[WebSocket] = set()
    self._queue: asyncio.Queue | None = None
    self._task: asyncio.Task | None = None

  def start(self) -> None:
    """Arranca la tarea que vacía la cola (dentro del event loop)."""
    self._queue = asyncio.Queue()
    self._task = asyncio.create_task(self._pump(), name="progress-hub")

  async def stop(self) -> None:
    """Detiene la tarea y olvida las conexiones."""
    if self._task is not None:
      self._task.cancel()
      with contextlib.suppress(asyncio.CancelledError):
        await self._task
    self._clients.clear()

  def publish(self, event: dict) -> None:
    """Encola un evento para todas las pestañas."""
    self._queue.put_nowait((None, event))

  def subscribe(self, websocket: WebSocket, snapshot: dict) -> None:
    """Encola la suscripción con el snapshot de este momento."""
    self._queue.put_nowait((websocket, snapshot))

  def unsubscribe(self, websocket: WebSocket) -> None:
    """La pestaña se desconectó."""
    self._clients.discard(websocket)

  async def _pump(self) -> None:
    """Única tarea que escribe en los WebSocket."""
    while True:
      websocket, event = await self._queue.get()
      if websocket is not None:
        if await self._send(websocket, event):
          self._clients.add(websocket)
        continue
      for client in list(self._clients):
        if not await self._send(client, event):
          self._clients.discard(client)

  @staticmethod
  async def _send(websocket: WebSocket, event: dict) -> bool:
    """Envía un evento; devuelve ``False`` si la conexión ya no sirve."""
    try:
      await websocket.send_json(event)
    except Exception:  # Conexión cerrada o rota: se la descarta.
      logger.debug("se descarta un WebSocket cerrado")
      return False
    return True
