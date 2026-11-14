"""Punto de entrada del backend: ``python -m app.main`` (desde ``backend/``).

Arranca uvicorn programáticamente dentro de ``if __name__ == "__main__":``,
obligatorio con ``spawn``: el worker vuelve a importar este módulo como
``__mp_main__`` y no tiene que volver a levantar el servidor. Sin ``--reload``
y con un solo proceso de uvicorn, porque cada proceso extra duplicaría el
worker y sus contextos de GPU (design D1).

Ctrl+C lo recibe uvicorn, que cierra las conexiones y corre el *lifespan* de
apagado: ``Shutdown`` al worker, ``join`` con tiempo límite y ``terminate()``
si no alcanzó. El worker y su pool ignoran ``SIGINT``.
"""

import logging

import uvicorn

from app.config import load_env_file, load_settings
from app.web.api import create_app

LOG_FORMAT = "%(levelname)s %(name)s: %(message)s"
SINGLE_PROCESS = 1


def main() -> None:
  """Carga la configuración y sirve la API hasta Ctrl+C."""
  load_env_file()
  settings = load_settings()
  logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
  app = create_app(settings)
  uvicorn.run(app, host=settings.host, port=settings.port, workers=SINGLE_PROCESS, reload=False, log_level="info")


if __name__ == "__main__":
  main()
