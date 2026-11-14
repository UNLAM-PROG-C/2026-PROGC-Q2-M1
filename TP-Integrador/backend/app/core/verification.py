"""Verificación por celdas entre backends (design D2 del cambio 4).

La imagen final puede pesar cientos de MB, así que no se guardan dos en memoria
para compararlas. Apenas termina un backend se toma su *huella*: ``topk_idx``
completo (a lo sumo unos MB) y un digest ``blake2b`` de 8 bytes por celda de la
imagen. Después la imagen se libera. Al final, una celda difiere de la
referencia si su fila de ``topk_idx`` o su digest no coinciden.

Una colisión de 64 bits es despreciable frente al objetivo, que es detectar
diferencias de punto flotante en casi-empates. ``verify()`` acepta cualquier
cantidad de backends para que ``benchmark.py`` (cambio 5) la reutilice.
"""

import hashlib
from dataclasses import dataclass

import numpy as np

# Bytes del digest por celda: 64 bits alcanzan para detectar diferencias.
CELL_DIGEST_BYTES = 8
CELL_DIGEST_DTYPE = np.uint64


class FingerprintMismatchError(ValueError):
  """Las huellas no corresponden al mismo problema (otra grilla u otro ``k``)."""


@dataclass(frozen=True)
class ResultFingerprint:
  """Huella de un resultado: ``topk_idx [M, k]`` y un digest por celda ``[M]``."""

  topk_idx: np.ndarray
  cell_digests: np.ndarray


@dataclass(frozen=True)
class CellDifferences:
  """Celdas de un backend que no coinciden con la referencia."""

  topk_cells: int
  image_cells: int
  total_cells: int


@dataclass(frozen=True)
class VerificationSummary:
  """Resultado de comparar cada backend contra la referencia (siempre CPU en la interfaz)."""

  reference: str
  differences: dict[str, CellDifferences]

  @property
  def identical(self) -> bool:
    """Ningún backend difiere de la referencia en ninguna celda."""
    return all(diff.total_cells == 0 for diff in self.differences.values())


def _row_digests(row: np.ndarray, tile_px: int, cols: int) -> list[bytes]:
  """Digest de cada celda de una fila ``[tile_px, cols·tile_px, 3]`` de la imagen."""
  cells = np.ascontiguousarray(row.reshape(tile_px, cols, tile_px, -1).transpose(1, 0, 2, 3))
  return [hashlib.blake2b(cell.tobytes(), digest_size=CELL_DIGEST_BYTES).digest() for cell in cells]


def cell_digests(image: np.ndarray, tile_px: int) -> np.ndarray:
  """Digest de 64 bits por celda, en el mismo orden que ``topk_idx`` (por filas).

  Recorre la imagen de a una fila de celdas para no duplicar su memoria.
  """
  rows, cols = image.shape[0] // tile_px, image.shape[1] // tile_px
  digests = []
  for row in range(rows):
    digests.extend(_row_digests(image[row * tile_px : (row + 1) * tile_px], tile_px, cols))
  return np.frombuffer(b"".join(digests), dtype=CELL_DIGEST_DTYPE)


def fingerprint(image: np.ndarray, topk_idx: np.ndarray, tile_px: int) -> ResultFingerprint:
  """Huella de un resultado; después de tomarla se puede liberar la imagen."""
  return ResultFingerprint(np.array(topk_idx, copy=True), cell_digests(image, tile_px))


def compare(candidate: ResultFingerprint, reference: ResultFingerprint) -> CellDifferences:
  """Cuenta las celdas en las que ``candidate`` difiere de ``reference``."""
  same_topk = candidate.topk_idx.shape == reference.topk_idx.shape
  if not same_topk or candidate.cell_digests.shape != reference.cell_digests.shape:
    raise FingerprintMismatchError("los resultados no tienen la misma grilla ni el mismo k")
  topk_differs = np.any(candidate.topk_idx != reference.topk_idx, axis=1)
  image_differs = candidate.cell_digests != reference.cell_digests
  return CellDifferences(int(topk_differs.sum()), int(image_differs.sum()), int((topk_differs | image_differs).sum()))


def verify(fingerprints: dict[str, ResultFingerprint], reference: str) -> VerificationSummary:
  """Compara cada backend contra ``reference`` (que tiene que estar entre las huellas)."""
  base = fingerprints[reference]
  differences = {name: compare(print_, base) for name, print_ in fingerprints.items() if name != reference}
  return VerificationSummary(reference, differences)
