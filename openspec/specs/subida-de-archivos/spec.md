# subida-de-archivos Specification

## Purpose

Recibe el lote de teselas y la imagen objetivo desde el navegador como recursos separados, los valida y los guarda en directorios temporales propios de los que el worker los lee por ruta, y los conserva para que se puedan reutilizar al volver a empezar.

## Requirements
### Requirement: Subida del lote y del objetivo por separado
El sistema MUST aceptar el lote de teselas como varios archivos sueltos o como un único `.zip`, y la imagen objetivo como un archivo, en subidas independientes. Cada subida MUST guardarse en un directorio temporal propio identificado por un id (`tiles_id` o `target_id`), que se devuelve junto con la cantidad de archivos aceptados (lote) o las dimensiones (objetivo). Un trabajo MUST referenciar un `tiles_id` y un `target_id`.

#### Scenario: Lote como archivos sueltos
- **WHEN** se suben 200 JPEG como lote
- **THEN** la respuesta incluye un `tiles_id` y "200 teselas recibidas"

#### Scenario: Lote como zip con carpetas
- **WHEN** se sube un zip que contiene imágenes dentro de subcarpetas
- **THEN** se aceptan todas las imágenes de todas las carpetas, conservando sus rutas relativas

#### Scenario: Reemplazar solo el objetivo
- **WHEN** existe un lote subido y se sube una imagen objetivo nueva
- **THEN** el lote no se vuelve a subir y un trabajo puede combinar el `tiles_id` anterior con el `target_id` nuevo

### Requirement: Filtro por formato
Solo MUST aceptarse archivos con extensión JPEG (`.jpg`, `.jpeg`), PNG o WebP, sin distinguir mayúsculas. Los demás MUST ignorarse e informarse en la respuesta. La imagen objetivo con otro formato MUST rechazarse.

#### Scenario: Zip con archivos ajenos
- **WHEN** el zip contiene imágenes, un `.txt` y archivos `__MACOSX/._*`
- **THEN** se aceptan solo las imágenes y la respuesta informa cuántos archivos se ignoraron

#### Scenario: Objetivo en formato no admitido
- **WHEN** la imagen objetivo es un `.gif`
- **THEN** la subida se rechaza con 400 indicando los formatos admitidos

### Requirement: Extracción segura de zip
La extracción MUST rechazar entradas con rutas absolutas o que salgan del directorio de destino, MUST NOT seguir enlaces simbólicos y MUST respetar un límite configurado de tamaño total descomprimido y de cantidad de entradas.

#### Scenario: Zip con ruta maliciosa
- **WHEN** el zip contiene una entrada `../../etc/passwd`
- **THEN** la entrada no se extrae fuera del directorio de la subida y se informa como rechazada

#### Scenario: Zip que excede el límite
- **WHEN** el contenido descomprimido supera el límite configurado
- **THEN** la subida se rechaza con 413 y se borra lo extraído

### Requirement: Consulta de las últimas subidas
El sistema MUST informar en el estado de la aplicación el último lote y el último objetivo subidos, con su resumen, y MUST servir el archivo original del objetivo y de una muestra acotada de teselas del lote, sin decodificarlos en el proceso web, para que la interfaz pueda mostrarlos al volver a empezar.

#### Scenario: Interfaz recargada
- **WHEN** la página se recarga después de un trabajo
- **THEN** `/api/state` incluye el `tiles_id` con N y el `target_id` con sus dimensiones, y sus miniaturas se pueden pedir por sus endpoints

### Requirement: Limpieza de temporales
El sistema MUST borrar los directorios de subidas y trabajos al apagarse, y al arrancar MUST borrar los que hayan quedado de ejecuciones anteriores. Al recibir una subida nueva MUST borrar las subidas anteriores del mismo tipo, salvo la que esté usando un trabajo en curso, y al empezar un trabajo MUST borrar los resultados de trabajos anteriores.

#### Scenario: Arranque tras un corte
- **WHEN** la aplicación se cerró abruptamente y se vuelve a iniciar
- **THEN** los directorios temporales de la ejecución anterior se eliminan al arrancar

#### Scenario: Lote nuevo
- **WHEN** no hay trabajos en curso y se sube un lote nuevo
- **THEN** solo queda en disco el lote nuevo, y el último objetivo se conserva
