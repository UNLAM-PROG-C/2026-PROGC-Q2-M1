"""Backend CPU secuencial.

"Secuencial" también significa sin SIMD (design D4): LLVM, debajo de Numba,
auto-vectoriza los bucles simples. Por eso se desactiva la vectorización antes
de importar Numba. Se usa ``setdefault`` para que se pueda experimentar con la
variable de entorno (ver ``env.example``). Si Numba ya estaba importado, se
relee su configuración para que el cambio tenga efecto igual.
"""

import os

_NUMBA_VECTORIZE_FLAGS = ("NUMBA_LOOP_VECTORIZE", "NUMBA_SLP_VECTORIZE")
_DISABLED = "0"

for _flag in _NUMBA_VECTORIZE_FLAGS:
  os.environ.setdefault(_flag, _DISABLED)

from numba.core import config as _numba_config  # noqa: E402  (después de fijar el entorno)

_numba_config.reload_config()
