"""Generación de ``choice``: qué candidato del top-k recibe cada celda.

Se genera una sola vez por trabajo, en el host y fuera de la medición, y se
pasa igual a todos los backends.
"""

import numpy as np


def generate_choice(seed: int, k: int, n_cells: int) -> np.ndarray:
  """Devuelve ``choice [M]`` int32 con enteros uniformes en ``[0, k)``."""
  return np.random.default_rng(seed).integers(0, k, n_cells, dtype=np.int32)
