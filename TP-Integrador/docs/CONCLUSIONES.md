# Conclusiones — Fotomosaico CPU / CUDA / OpenCL

**Trabajo Práctico Integrador · Programación Concurrente · UNLaM**

---

## 1. Introducción

Este proyecto arma un **fotomosaico**: una imagen grande reconstruida a partir de miles de fotos chiquitas (teselas), elegidas automáticamente para que, vistas de lejos, reproduzcan una imagen objetivo. El objetivo del TP no era solo armar el mosaico, sino **implementar y comparar tres formas de calcularlo** — secuencial en CPU, y en paralelo con CUDA y con OpenCL — sobre el mismo trabajo, para medir de forma empírica cuánto gana la concurrencia en un problema naturalmente paralelizable. Estas conclusiones recogen los aprendizajes más relevantes, con referencias concretas al código.

---

## 2. Por qué procesos y no solo hilos

Python tiene el **GIL** (Global Interpreter Lock): un solo proceso Python no puede ejecutar bytecode en paralelo real entre hilos, por más hilos que se abran. Por eso el trabajo pesado se delega a un **proceso worker separado**, lanzado con `multiprocessing.get_context("spawn")`. Elegimos `spawn` en vez de `fork` a propósito: `fork` copiaría el proceso tal cual está, con contextos de GPU y threads ya abiertos, lo que puede romper CUDA/OpenCL en el hijo; `spawn` arranca un intérprete limpio. El proceso web y el worker se comunican por colas de `multiprocessing` — patrón **Productor/Consumidor** — nunca con llamadas directas.

La lección: elegir el mecanismo de concurrencia correcto empieza por entender las limitaciones del lenguaje, no por asumir que "más hilos" es más rápido.

---

## 3. Backends intercambiables, mismo contrato

Los tres backends (CPU, CUDA, OpenCL) implementan la misma interfaz `MosaicBackend` (`core/backend.py`) — patrón **Strategy**. Por encima, `BaseBackend.run()`/`_execute()` fija el orden de los pasos (cargar teselas, preparar candidatas, calcular distancias, armar el mosaico) — patrón **Template Method**, con un segundo nivel en `GpuBackend` (`backends/gpu_base.py`) que fija los pasos comunes a CUDA y OpenCL antes de que cada uno redefina su kernel específico.

El valor concreto de este diseño: agregar o modificar un backend no toca el resto del sistema. El worker y el proceso web nunca saben qué backend está corriendo — solo hablan con la interfaz.

---

## 4. Rendimiento real medido, no teórico

El número que mejor resume el trabajo es el **speedup medido en nuestra propia corrida**: en la etapa de "preparación de teselas" (el cálculo del color promedio de cada tesela candidata), pasamos de 16,0 ms en CPU a 0,7 ms en GPU — **×23**. Es importante no sobrevender este número: es el speedup de la etapa más paralelizable, no de todo el programa. Otra etapa, la "carga común" de las teselas desde disco, mide igual en los dos backends (281,9 ms) porque no se paraleliza — es trabajo de CPU que pagan ambos por igual. El speedup total del pipeline completo está acotado por esa parte no paralelizable (la intuición detrás de la Ley de Amdahl).

También medimos, no asumimos, la corrección: un chequeo de verificación (`core/verification.py`) compara celda por celda qué tesela eligió cada backend. De 7.500 celdas generadas en nuestra corrida, solo 3 (0,04%) difirieron entre CPU y GPU — diferencias de redondeo en sumas de punto flotante hechas en distinto orden, no errores del algoritmo. El sistema lo detecta y lo reporta solo.

---

## 5. Progreso en vivo sin acoplar el backend a la interfaz

El worker reporta su avance mediante `ProgressReporter` (`core/backend.py`), que un `ProgressHub` (`web/hub.py`) reenvía por WebSocket al frontend (`socket.ts`, `zoomController.ts`) — patrón **Observer**. El backend emite progreso sin saber quién escucha ni cuántos interesados hay; agregar una nueva forma de mostrar el progreso (por ejemplo, otro cliente) no requiere tocar el backend.

Los mensajes entre el proceso web y el worker (`RunJob`, `Shutdown`) son objetos tipados (`worker/messages.py`) — patrón **Command** — en vez de llamadas directas, lo que permite encolarlos y pasarlos entre procesos de forma segura.

---

## 6. Reproducibilidad: la semilla como contrato de comparación justa

Para que CPU, CUDA y OpenCL sean comparables, el experimento tiene que ser **determinístico**: dado el mismo lote de teselas, la misma imagen objetivo y la misma semilla, los tres backends deben producir el mismo mosaico. La semilla (`core/choice.py`, `generate_choice`) decide cuál de las *k* teselas candidatas más parecidas se usa en cada celda, de forma idéntica en los tres backends. Sin este control, cualquier diferencia entre corridas sería indistinguible entre "backend distinto" y "azar distinto" — la semilla es lo que hace que la comparación tenga sentido.

---

## 7. Validación y pruebas

Antes de sacar conclusiones de rendimiento corrimos la suite completa: **363 tests en total** (246 de backend con pytest, 117 de frontend con vitest), todos en verde; 32 se saltean automáticamente en máquinas sin GPU NVIDIA/AMD — no es una falla, es la propia suite reportando correctamente que no hay hardware disponible para esos casos. Medir sin antes validar la corrección habría invalidado cualquier número de speedup.

---

## 8. Conclusión general

Tres ideas resumen el trabajo:

1. **La concurrencia en Python empieza por conocer el GIL** — de ahí la elección de procesos (`spawn`) sobre hilos para el cómputo pesado.
2. **Un buen diseño (Strategy + Template Method) permite comparar backends de forma justa** sin acoplar el resto del sistema a ninguno en particular.
3. **El rendimiento se mide, no se asume** — el ×23 y el 0,04% de discrepancia son números de una corrida real, con su propia verificación automática, no cifras de un paper o de la documentación de CUDA/OpenCL.

El aprendizaje central: la ganancia de usar GPU no es automática ni pareja entre etapas — hay que medir cada una por separado para saber dónde realmente vale la pena paralelizar.
