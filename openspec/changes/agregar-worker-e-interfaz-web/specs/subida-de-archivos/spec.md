# Spec Delta

## Purpose

Recibe el lote de teselas y la imagen objetivo desde el navegador, los valida y los guarda en un directorio temporal propio de la subida, del que el worker los lee por ruta.

## ADDED Requirements

### Requirement: Subida del lote y del objetivo
El sistema MUST aceptar el lote de teselas como varios archivos sueltos o como un único `.zip`, y la imagen objetivo como un archivo. Cada subida MUST guardarse en un directorio temporal propio identificado por un id de subida, que se devuelve junto con la cantidad de archivos aceptados.

#### Scenario: Lote como archivos sueltos
- **WHEN** se suben 200 JPEG y una imagen objetivo
- **THEN** la respuesta incluye un id de subida y "200 teselas recibidas"

#### Scenario: Lote como zip con carpetas
- **WHEN** se sube un zip que contiene imágenes dentro de subcarpetas
- **THEN** se aceptan todas las imágenes de todas las carpetas, conservando sus rutas relativas

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

### Requirement: Limpieza de temporales
El sistema MUST borrar los directorios de subidas y trabajos al apagarse, y al arrancar MUST borrar los que hayan quedado de ejecuciones anteriores. Al recibir una subida nueva MUST borrar las anteriores, salvo la que esté usando un trabajo en curso.

#### Scenario: Arranque tras un corte
- **WHEN** la aplicación se cerró abruptamente y se vuelve a iniciar
- **THEN** los directorios temporales de la ejecución anterior se eliminan al arrancar

#### Scenario: Subida nueva
- **WHEN** no hay trabajos en curso y se hace una subida nueva
- **THEN** solo queda en disco el directorio de la subida nueva
