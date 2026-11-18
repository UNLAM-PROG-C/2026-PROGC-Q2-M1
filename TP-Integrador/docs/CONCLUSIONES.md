# Conclusiones — Fotomosaico CPU / CUDA / OpenCL

**Trabajo Práctico Integrador · Programación Concurrente · UNLaM**

En esta sección resumimos los principales aprendizajes y dificultades que encontramos al realizar el trabajo práctico.

---

## 1. Separar el cálculo de la interfaz

La primera decisión de arquitectura fue entender que el cómputo pesado no podía convivir con el proceso que atiende al navegador: en Python, varios hilos de un mismo proceso no ejecutan código en paralelo real. Por eso el cálculo corre en un proceso aparte (el worker), que además es el único que usa la GPU. Así la interfaz sigue respondiendo y mostrando el progreso mientras se genera el mosaico, y los recursos de la GPU quedan concentrados en un solo lugar.

## 2. Un mismo algoritmo, tres formas de ejecutarlo

Lograr que el mismo programa corriera en cualquier máquina, con o sin GPU, nos obligó a definir un contrato común para los tres backends (**Strategy**) y una secuencia de etapas fija que todos respetan (**Template Method**). Gracias a eso, sumar OpenCL no requirió tocar el resto del sistema, y la comparación entre backends es justa: todos miden exactamente las mismas etapas.

## 3. Tener GPU no garantiza velocidad

Descubrimos en la práctica que la GPU no siempre gana: el costo de mover los datos hasta la placa y lanzar el trabajo es fijo, y en problemas muy chicos pesa más que el cálculo en sí. Con problemas del tamaño de un mosaico real, en cambio, la GPU llegó a ser más de cien veces más rápida que la CPU. La lección es que el hardware paralelo rinde solo cuando hay suficiente trabajo para aprovecharlo.

## 4. Elegir el mecanismo de concurrencia adecuado

No hay una única herramienta de concurrencia que resuelva todo. Usamos procesos para el cálculo y para decodificar imágenes en paralelo, hilos para poder recibir órdenes mientras se trabaja, colas para comunicar procesos con el esquema **productor/consumidor** y memoria compartida para no copiar imágenes de un proceso a otro. Coordinar todo esto, y lograr que la aplicación se apague de forma ordenada sin dejar procesos colgados, fue una de las partes más laboriosas del trabajo.

## 5. Medir en vez de asumir

Para que la comparación entre CPU y GPU fuera válida no alcanzaba con correr el mismo algoritmo: había que asegurarse de que la versión "secuencial" de la CPU fuera realmente secuencial, sin paralelismo agregado por el compilador, y medir cada etapa con el mecanismo de tiempo más preciso de cada plataforma. Solo así los números del speedup reflejan la diferencia real entre ejecutar en serie y en paralelo.

## 6. Conclusión general

Tres ideas resumen el trabajo:

1. **Concurrencia bien modelada:** cada problema necesita su herramienta (procesos, hilos, colas, memoria compartida).
2. **GPU bien aprovechada:** el paralelismo masivo rinde cuando el problema es lo bastante grande como para compensar el costo de usarlo.
3. **Backends intercambiables:** un diseño con contratos claros permitió comparar tres implementaciones del mismo algoritmo en igualdad de condiciones.
