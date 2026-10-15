# CLAUDE.md — TP Integrador

## Estándares de código

### 1. Coding Standard

Se sigue el [Google Style Guide](https://google.github.io/styleguide/) del lenguaje que corresponda:

- C++: https://google.github.io/styleguide/cppguide.html
- Python: https://google.github.io/styleguide/pyguide.html
- Java: https://google.github.io/styleguide/javaguide.html
- Otros lenguajes: la guía de Google equivalente, si existe.

Ante una duda que la guía no resuelva, mantener la consistencia con el código ya existente en el TP.

### 2. Ajustes específicos de la cátedra

Estos ajustes tienen prioridad sobre la guía de Google:

- **Llaves en la misma columna** (estilo Allman): la llave de apertura va en su propia línea, alineada con la de cierre.
- Configuración de referencia en [.clang-format](../.clang-format) (`BasedOnStyle: Google`, `BreakBeforeBraces: Allman`, `ColumnLimit: 180`, `PointerAlignment: Right`, sin funciones de una sola línea).

```cpp
int CountActiveWorkers(const std::vector<Worker> &workers)
{
  int active_count = 0;
  for (const Worker &worker : workers)
  {
    if (worker.IsActive())
    {
      ++active_count;
    }
  }
  return active_count;
}
```

### 3. Indentación

- Espacios, **nunca** tabulaciones.
- **2 espacios** por nivel de indentación.

### 4. Largo de métodos/funciones

- Objetivo: **menos de 15 líneas** por método/función.
- No es un límite estricto, es una guía. Si una función queda en 16–18 líneas y partirla la vuelve artificial o menos legible, se deja como una sola. No fragmentar código solo para cumplir el número.
- Si una función supera ampliamente el límite, es señal de que tiene más de una responsabilidad: extraer funciones con nombres descriptivos.

### 5. Patrones de diseño

- Aplicar patrones de diseño donde aporten (por ejemplo: Productor/Consumidor, Monitor, Singleton, Factory, Strategy, Observer, Template Method).
- Elegir el patrón por el problema, no por forzar su uso.
- Documentar en un comentario (o en el README del TP) qué patrón se usó y por qué.

### 6. Sin números mágicos

- Ningún literal numérico con significado de negocio en el código: usar **constantes con nombre descriptivo**.
- Se aceptan `0`, `1` o `-1` cuando su significado es obvio por contexto (inicializar un contador, incrementar, etc.).

```cpp
// Mal
std::this_thread::sleep_for(std::chrono::milliseconds(500));

// Bien
constexpr int kProducerDelayMs = 500;
std::this_thread::sleep_for(std::chrono::milliseconds(kProducerDelayMs));
```

### 7. Código en inglés

- **Todo** el código va en inglés, sin excepción: nombres de variables, funciones, clases, constantes, archivos, mensajes de log y de error.

## Flujo de trabajo

### 1. Commits

- Formato [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `style:`, etc.
- La descripción del commit va **en español**; el prefijo de tipo (`feat:`, `fix:`, etc.) se mantiene en inglés.
- Ejemplo: `feat: agregar buffer acotado para productor-consumidor`
- **Sin atribución de IA** en los mensajes de commit ni en las descripciones de PR (nada de `Co-Authored-By: Claude`, "Generated with Claude Code" ni similares).

### 2. OpenSpec para cambios grandes

- Todo cambio grande (nueva funcionalidad, cambio de arquitectura, refactor que toque varios módulos) pasa primero por **OpenSpec**: se redacta y aprueba la propuesta antes de escribir código.
- Cambios chicos (fixes puntuales, renombres, documentación) no lo requieren.

### 3. Variables de entorno

- Los archivos `.env` **no se versionan**.
- Usar `env.example` como plantilla, con las claves necesarias y valores de ejemplo (nunca secretos reales).
- Si se agrega una variable nueva, actualizar `env.example` en el mismo cambio.

### 4. Idioma

- **Documentación y comentarios**: español rioplatense.
- **Código**: inglés (ver regla 7 de estándares).

```cpp
// Esperamos a que el buffer tenga lugar antes de producir.
buffer_not_full_.wait(lock, [this] { return items_.size() < kBufferCapacity; });
```

### 5. Tests

- **Nunca** modificar código de producción solo para que un test pase sin implementar correctamente el comportamiento esperado (nada de casos especiales para el test, valores hardcodeados ni condiciones que detecten el entorno de testing).
- Si un test falla, se corrige la implementación o, si el test está mal, se corrige el test explicando el motivo.
