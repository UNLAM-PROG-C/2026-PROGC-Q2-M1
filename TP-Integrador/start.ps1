<#
.SYNOPSIS
  Script de arranque de la aplicación (Windows). Equivalente a start.sh.

.DESCRIPTION
  Pasos (cada uno idempotente, ver design D11 del cambio agregar-worker-e-interfaz-web):
    1. Verifica la versión de Python y crea TP-Integrador\.venv si no existe.
    2. Instala backend\requirements.txt si cambió desde la última instalación.
    3. Instala la biblioteca de GPU: PyCUDA si hay placa NVIDIA, PyOpenCL si no
       (o si PyCUDA falla). Una falla es solo una advertencia y no se reintenta
       hasta que cambien los requirements de GPU o se pase -Reinstall.
    4. Usa el node del PATH si cumple la versión mínima; si no, instala Node LTS
       dentro del venv con nodeenv. Corre npm ci si cambió package-lock.json.
    5. Crea backend\.env y frontend\.env a partir de env.example si no existen.
    6. Levanta backend y frontend; Ctrl+C detiene ambos (try/finally) sin dejar
       huérfanos: se mata el árbol de procesos completo de cada uno.

  Las huellas de lo instalado se guardan en .venv\.mosaic-stamp (formato clave=valor,
  compartido con start.sh).

.PARAMETER CpuOnly
  No instala la biblioteca de GPU (también se acepta --cpu-only).

.PARAMETER Reinstall
  Ignora las huellas guardadas: reinstala dependencias de Python, reintenta la
  biblioteca de GPU y vuelve a correr npm ci (también se acepta --reinstall).

.PARAMETER Help
  Muestra esta ayuda (también se acepta --help).

.EXAMPLE
  .\start.ps1
  .\start.ps1 -CpuOnly
  .\start.ps1 --reinstall
#>
param(
  [switch]$CpuOnly,
  [switch]$Reinstall,
  [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Las opciones estilo start.sh (--cpu-only, --reinstall, --help) llegan en $args.
foreach ($arg in @($args | Where-Object { $_ }))
{
  switch ($arg)
  {
    '--cpu-only' { $CpuOnly = [switch]$true }
    '--reinstall' { $Reinstall = [switch]$true }
    { $_ -in '--help', '-h' } { $Help = [switch]$true }
    default
    {
      Write-Host "[start] ERROR: opción desconocida: $arg (ver: .\start.ps1 -Help)" -ForegroundColor Red
      exit 1
    }
  }
}

$MinPythonMajor = 3
$MinPythonMinor = 11
$MinNodeMajor = 20
$MinNodeMinor = 19
$DefaultBackendHost = '127.0.0.1'
$DefaultBackendPort = 8000
$DefaultFrontendHost = '127.0.0.1'
$DefaultFrontendPort = 5173
$BackendReadyTimeoutS = 180
$FrontendReadyTimeoutS = 60
$HttpProbeTimeoutS = 2
$PollIntervalS = 1
$ShutdownGraceS = 10
$ProcessRefreshIntervalS = 5
$BackendStatePath = '/api/state'

$GpuResultCuda = 'cuda'
$GpuResultOpenCl = 'opencl'
$GpuResultNone = 'none'

$RootDir = $PSScriptRoot
$BackendDir = Join-Path $RootDir 'backend'
$FrontendDir = Join-Path $RootDir 'frontend'
$VenvDir = Join-Path $RootDir '.venv'
$VenvBin = Join-Path $VenvDir 'Scripts'
$VenvPython = Join-Path $VenvBin 'python.exe'
$StampFile = Join-Path $VenvDir '.mosaic-stamp'

# Python sin comillas en el código: PowerShell 5.1 las rompe al pasarlas a un ejecutable.
$PythonHashCode = 'import hashlib,sys,pathlib; h=hashlib.sha256(); [h.update(pathlib.Path(p).read_bytes()) for p in sys.argv[1:]]; print(h.hexdigest())'
$PythonVersionCode = 'import platform; print(platform.python_version())'
$PythonMinimumCode = "import sys; sys.exit(0 if sys.version_info[:2] >= ($MinPythonMajor, $MinPythonMinor) else 1)"

function Write-Step([string]$Message)
{
  Write-Host "[start] $Message"
}

function Write-StartWarning([string]$Message)
{
  Write-Host "[start] ADVERTENCIA: $Message" -ForegroundColor Yellow
}

function Stop-WithError([string]$Message)
{
  throw "[start] ERROR: $Message"
}

# --- Huella de instalación (.venv\.mosaic-stamp) ------------------------------------

function Read-Stamp
{
  $stamp = @{}
  if (Test-Path $StampFile)
  {
    foreach ($line in [IO.File]::ReadAllLines($StampFile))
    {
      $key, $value = $line -split '=', 2
      if ($null -ne $value)
      {
        $stamp[$key.Trim()] = $value.Trim()
      }
    }
  }
  return $stamp
}

function Set-StampValue([string]$Key, [string]$Value)
{
  $stamp = Read-Stamp
  $stamp[$Key] = $Value
  $lines = $stamp.Keys | Sort-Object | ForEach-Object { "$_=$($stamp[$_])" }
  [IO.File]::WriteAllText($StampFile, (($lines -join "`n") + "`n"))
}

function Test-StampMatches([string]$Key, [string]$Hash)
{
  return (-not $Reinstall) -and ((Read-Stamp)[$Key] -eq $Hash)
}

# Huella SHA-256 del contenido de los archivos (misma fórmula que start.sh).
function Get-FilesHash([string[]]$Paths)
{
  $hash = & $VenvPython -c $PythonHashCode @Paths
  if ($LASTEXITCODE -ne 0)
  {
    Stop-WithError "no se pudo calcular la huella de $($Paths -join ', ')."
  }
  return $hash.Trim()
}

# --- Paso 1: Python y entorno virtual ------------------------------------------------

function Test-PythonMinimum([string[]]$Command)
{
  $exe = $Command[0]
  $prefix = @($Command | Select-Object -Skip 1)
  try
  {
    & $exe @prefix -c $PythonMinimumCode 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
  }
  catch
  {
    return $false
  }
}

function Get-PythonVersion([string[]]$Command)
{
  $exe = $Command[0]
  $prefix = @($Command | Select-Object -Skip 1)
  try
  {
    $version = & $exe @prefix -c $PythonVersionCode 2>$null
    if ($version)
    {
      return $version
    }
    return 'desconocida'
  }
  catch
  {
    return 'desconocida'
  }
}

# Prueba el lanzador py y después python/python3 (el alias de la Microsoft Store falla solo).
function Find-SystemPython
{
  $found = @()
  foreach ($candidate in @(@('py', '-3'), @('python'), @('python3')))
  {
    if (-not (Get-Command $candidate[0] -ErrorAction SilentlyContinue))
    {
      continue
    }
    if (Test-PythonMinimum $candidate)
    {
      return , $candidate
    }
    $found += "$($candidate -join ' ')=$(Get-PythonVersion $candidate)"
  }
  $foundText = if ($found) { $found -join ', ' } else { 'ninguno' }
  Stop-WithError "se necesita Python >= $MinPythonMajor.$MinPythonMinor (encontrado: $foundText). Instalalo y volvé a correr el script."
}

function Initialize-Venv
{
  if (Test-Path $VenvPython)
  {
    if (-not (Test-PythonMinimum @($VenvPython)))
    {
      Stop-WithError "el venv usa Python $(Get-PythonVersion @($VenvPython)) y se necesita >= $MinPythonMajor.$MinPythonMinor. Borrá .venv y volvé a correr el script."
    }
    return
  }
  $python = Find-SystemPython
  $exe = $python[0]
  $prefix = @($python | Select-Object -Skip 1)
  Write-Step "Creando el entorno virtual en .venv con $($python -join ' ') $(Get-PythonVersion $python)..."
  & $exe @prefix -m venv $VenvDir | Out-Host
  if ($LASTEXITCODE -ne 0)
  {
    Stop-WithError 'no se pudo crear el entorno virtual.'
  }
}

function Invoke-Pip([string[]]$PipArgs)
{
  & $VenvPython -m pip install --disable-pip-version-check @PipArgs | Out-Host
  return $LASTEXITCODE -eq 0
}

# --- Paso 2: dependencias de Python ---------------------------------------------------

function Install-PythonRequirements
{
  $requirements = Join-Path $BackendDir 'requirements.txt'
  $hash = Get-FilesHash @($requirements)
  if (Test-StampMatches 'python' $hash)
  {
    Write-Step 'Dependencias de Python al día.'
    return
  }
  Write-Step 'Instalando backend\requirements.txt...'
  if (-not (Invoke-Pip @('-r', $requirements)))
  {
    Stop-WithError 'falló la instalación de backend\requirements.txt.'
  }
  Set-StampValue 'python' $hash
}

# --- Paso 3: biblioteca de GPU ---------------------------------------------------------

function Test-NvidiaGpu
{
  if (-not (Get-Command 'nvidia-smi' -ErrorAction SilentlyContinue))
  {
    return $false
  }
  try
  {
    & nvidia-smi -L 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
  }
  catch
  {
    return $false
  }
}

# Intenta PyCUDA (solo con NVIDIA) y cae a PyOpenCL; devuelve el resultado.
function Install-GpuLibrary
{
  if (Test-NvidiaGpu)
  {
    Write-Step 'Placa NVIDIA detectada: instalando PyCUDA (requirements-cuda.txt)...'
    if (Invoke-Pip @('-r', (Join-Path $BackendDir 'requirements-cuda.txt')))
    {
      return $GpuResultCuda
    }
    Write-StartWarning 'no se pudo instalar PyCUDA (¿falta el CUDA Toolkit o Visual Studio?). Se intenta PyOpenCL sobre la misma placa.'
  }
  else
  {
    Write-Step 'Sin placa NVIDIA: instalando PyOpenCL (requirements-opencl.txt)...'
  }
  if (Invoke-Pip @('-r', (Join-Path $BackendDir 'requirements-opencl.txt')))
  {
    return $GpuResultOpenCl
  }
  return $GpuResultNone
}

function Install-GpuRequirements
{
  if ($CpuOnly)
  {
    Write-Step '-CpuOnly: se saltea la instalación de la biblioteca de GPU.'
    return
  }
  $hash = Get-FilesHash @((Join-Path $BackendDir 'requirements-cuda.txt'), (Join-Path $BackendDir 'requirements-opencl.txt'))
  if (Test-StampMatches 'gpu' $hash)
  {
    Write-Step "Biblioteca de GPU ya decidida: $((Read-Stamp)['gpu_result']) (usar -Reinstall para reintentar)."
    return
  }
  $result = Install-GpuLibrary | Select-Object -Last 1
  if ($result -eq $GpuResultNone)
  {
    Write-StartWarning 'no se pudo instalar ninguna biblioteca de GPU: la aplicación arranca solo con CPU. Reintentar con -Reinstall.'
  }
  Set-StampValue 'gpu' $hash
  Set-StampValue 'gpu_result' $result
}

# --- Paso 4: Node y dependencias del frontend ----------------------------------------

function Test-NodeMinimum
{
  if (-not (Get-Command 'node' -ErrorAction SilentlyContinue))
  {
    return $false
  }
  $version = (& node --version) -replace '^v', ''
  $major, $minor = ($version -split '\.')[0..1] | ForEach-Object { [int]$_ }
  return ($major -gt $MinNodeMajor) -or (($major -eq $MinNodeMajor) -and ($minor -ge $MinNodeMinor))
}

function Install-Node
{
  # Con el venv primero en el PATH, un Node instalado por nodeenv tiene prioridad.
  $env:PATH = "$VenvBin;$env:PATH"
  if (Test-NodeMinimum)
  {
    Write-Step "Node $(& node --version) disponible."
    return
  }
  Write-Step "No hay Node >= $MinNodeMajor.$MinNodeMinor en el PATH: instalando Node LTS dentro del venv con nodeenv..."
  if (-not (Invoke-Pip @('nodeenv')))
  {
    Stop-WithError 'no se pudo instalar nodeenv.'
  }
  $env:VIRTUAL_ENV = $VenvDir
  & $VenvPython -m nodeenv --python-virtualenv --node=lts | Out-Host
  if (($LASTEXITCODE -ne 0) -or -not (Test-NodeMinimum))
  {
    Stop-WithError 'nodeenv no pudo instalar un Node que cumpla la versión mínima.'
  }
  Write-Step "Node $(& node --version) instalado en el venv."
}

function Install-FrontendDependencies
{
  $hash = Get-FilesHash @((Join-Path $FrontendDir 'package-lock.json'))
  if ((Test-Path (Join-Path $FrontendDir 'node_modules')) -and (Test-StampMatches 'npm' $hash))
  {
    Write-Step 'Dependencias del frontend al día.'
    return
  }
  Write-Step 'Instalando dependencias del frontend (npm ci)...'
  Push-Location $FrontendDir
  try
  {
    & npm.cmd ci | Out-Host
    $ok = $LASTEXITCODE -eq 0
  }
  finally
  {
    Pop-Location
  }
  if (-not $ok)
  {
    Stop-WithError 'falló npm ci en frontend\.'
  }
  Set-StampValue 'npm' $hash
}

# --- Paso 5: archivos .env -------------------------------------------------------------

function Initialize-EnvFile([string]$Dir)
{
  $target = Join-Path $Dir '.env'
  if (-not (Test-Path $target))
  {
    Copy-Item (Join-Path $Dir 'env.example') $target
    Write-Step "Creado $(Split-Path $Dir -Leaf)\.env a partir de env.example."
  }
}

function Read-EnvFile([string]$Path)
{
  $values = [ordered]@{}
  if (Test-Path $Path)
  {
    foreach ($line in [IO.File]::ReadAllLines($Path))
    {
      if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$')
      {
        $values[$Matches[1]] = $Matches[2].Trim().Trim('"', "'")
      }
    }
  }
  return $values
}

# Valor de una variable: entorno, si no el .env indicado, si no el valor por defecto.
function Get-EnvValue([string]$Path, [string]$Key, [string]$Default)
{
  $fromEnv = [Environment]::GetEnvironmentVariable($Key)
  if ($fromEnv)
  {
    return $fromEnv
  }
  $fromFile = (Read-EnvFile $Path)[$Key]
  if ($fromFile)
  {
    return $fromFile
  }
  return $Default
}

# --- Paso 6: procesos de backend y frontend --------------------------------------------

function Test-UrlResponds([string]$Url)
{
  try
  {
    Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $HttpProbeTimeoutS | Out-Null
    return $true
  }
  catch
  {
    return $false
  }
}

function Wait-ForUrl([string]$Url, [Diagnostics.Process]$Process, [int]$TimeoutS)
{
  $deadline = (Get-Date).AddSeconds($TimeoutS)
  while (-not (Test-UrlResponds $Url))
  {
    if ($Process.HasExited)
    {
      Stop-WithError "el proceso terminó antes de responder en $Url."
    }
    if ((Get-Date) -gt $deadline)
    {
      Stop-WithError "$Url no respondió en $TimeoutS s."
    }
    Start-Sleep -Seconds $PollIntervalS
  }
}

# Registro de los procesos lanzados y sus descendientes (PID -> fecha de creación).
# Se actualiza durante la ejecución: si un intermedio muere (por ejemplo, el lanzador
# python.exe del venv), sus hijos (el worker) siguen registrados y no quedan huérfanos.
# La fecha de creación evita matar un proceso ajeno que reutilizó un PID.
$TrackedProcesses = @{}

function Get-ProcessSnapshot
{
  return @(Get-CimInstance Win32_Process -Property ProcessId, ParentProcessId, CreationDate)
}

function Add-TrackedDescendants([object[]]$Snapshot)
{
  $added = $true
  while ($added)
  {
    $added = $false
    foreach ($process in $Snapshot)
    {
      $parentDate = $TrackedProcesses[[int]$process.ParentProcessId]
      if ($parentDate -and -not $TrackedProcesses.ContainsKey([int]$process.ProcessId) -and ($process.CreationDate -ge $parentDate))
      {
        $TrackedProcesses[[int]$process.ProcessId] = $process.CreationDate
        $added = $true
      }
    }
  }
}

function Update-TrackedProcesses([Diagnostics.Process[]]$Roots)
{
  $snapshot = Get-ProcessSnapshot
  foreach ($process in $snapshot | Where-Object { $_.ProcessId -in @($Roots | Where-Object { $_ } | ForEach-Object { $_.Id }) })
  {
    if (-not $TrackedProcesses.ContainsKey([int]$process.ProcessId))
    {
      $TrackedProcesses[[int]$process.ProcessId] = $process.CreationDate
    }
  }
  Add-TrackedDescendants $snapshot
}

function Get-AliveTrackedIds
{
  $snapshot = Get-ProcessSnapshot
  return @($snapshot | Where-Object { $TrackedProcesses[[int]$_.ProcessId] -eq $_.CreationDate } | ForEach-Object { [int]$_.ProcessId })
}

# El Ctrl+C de la consola ya les llegó a los hijos (comparten consola) y arrancan su
# apagado ordenado; se espera un plazo y se fuerza la terminación de lo que quede.
function Stop-ProcessTrees([Diagnostics.Process[]]$Processes)
{
  Update-TrackedProcesses $Processes
  if ($TrackedProcesses.Count -eq 0)
  {
    return
  }
  Write-Step 'Deteniendo backend y frontend...'
  $deadline = (Get-Date).AddSeconds($ShutdownGraceS)
  while ((Get-AliveTrackedIds) -and ((Get-Date) -lt $deadline))
  {
    Start-Sleep -Seconds $PollIntervalS
  }
  foreach ($id in Get-AliveTrackedIds)
  {
    Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
  }
  Write-Step 'Listo.'
}

# Exporta al proceso actual (y así a los hijos) las variables de un .env que no estén
# definidas; devuelve sus nombres para quitarlas al terminar.
function Import-EnvFile([string]$Path)
{
  $added = @()
  $values = Read-EnvFile $Path
  foreach ($key in $values.Keys)
  {
    if ($null -eq [Environment]::GetEnvironmentVariable($key))
    {
      [Environment]::SetEnvironmentVariable($key, $values[$key])
      $added += $key
    }
  }
  return $added
}

function Start-Backend
{
  return Start-Process -FilePath $VenvPython -ArgumentList '-m', 'app.main' -WorkingDirectory $BackendDir -NoNewWindow -PassThru
}

# Vite se lanza con node directamente (equivale a npm run dev): npm.cmd pasa por
# cmd.exe, que ante Ctrl+C pregunta "¿Desea terminar el trabajo por lotes?".
function Start-Frontend
{
  $vite = Join-Path $FrontendDir 'node_modules\vite\bin\vite.js'
  $node = (Get-Command 'node').Source
  return Start-Process -FilePath $node -ArgumentList "`"$vite`"" -WorkingDirectory $FrontendDir -NoNewWindow -PassThru
}

# Espera mientras ambos sigan vivos, refrescando cada tanto el registro de procesos.
function Wait-WhileRunning([Diagnostics.Process]$Backend, [Diagnostics.Process]$Frontend)
{
  $nextRefresh = Get-Date
  while (-not $Backend.HasExited -and -not $Frontend.HasExited)
  {
    if ((Get-Date) -ge $nextRefresh)
    {
      Update-TrackedProcesses @($Backend, $Frontend)
      $nextRefresh = (Get-Date).AddSeconds($ProcessRefreshIntervalS)
    }
    Start-Sleep -Seconds $PollIntervalS
  }
}

function Invoke-Application
{
  $backendUrl = "http://$(Get-EnvValue (Join-Path $BackendDir '.env') 'MOSAIC_HOST' $DefaultBackendHost):$(Get-EnvValue (Join-Path $BackendDir '.env') 'MOSAIC_PORT' $DefaultBackendPort)"
  $frontendUrl = "http://${DefaultFrontendHost}:$(Get-EnvValue (Join-Path $FrontendDir '.env') 'FRONTEND_PORT' $DefaultFrontendPort)"
  $backend = $null
  $frontend = $null
  try
  {
    Write-Step "Levantando el backend en $backendUrl..."
    $backend = Start-Backend
    Wait-ForUrl "$backendUrl$BackendStatePath" $backend $BackendReadyTimeoutS
    Write-Step 'Levantando el frontend...'
    $frontend = Start-Frontend
    Wait-ForUrl $frontendUrl $frontend $FrontendReadyTimeoutS
    Write-Step "Aplicación lista: abrí $frontendUrl (Ctrl+C para detener)."
    Wait-WhileRunning $backend $frontend
    Write-StartWarning 'uno de los procesos terminó; se detiene el resto.'
  }
  finally
  {
    Stop-ProcessTrees @($backend, $frontend)
  }
}

function Invoke-Main
{
  Initialize-Venv
  Install-PythonRequirements
  Install-GpuRequirements
  Install-Node
  Install-FrontendDependencies
  Initialize-EnvFile $BackendDir
  Initialize-EnvFile $FrontendDir
  $addedVariables = Import-EnvFile (Join-Path $BackendDir '.env')
  try
  {
    Invoke-Application
  }
  finally
  {
    foreach ($key in $addedVariables)
    {
      [Environment]::SetEnvironmentVariable($key, $null)
    }
  }
}

if ($Help)
{
  Get-Help $PSCommandPath -Detailed
  exit 0
}

$originalPath = $env:PATH
$originalVirtualEnv = $env:VIRTUAL_ENV
try
{
  Invoke-Main
}
catch
{
  Write-Host $_.Exception.Message -ForegroundColor Red
  exit 1
}
finally
{
  # Si se corrió con .\start.ps1, no dejar cambios en el entorno de la sesión.
  $env:PATH = $originalPath
  $env:VIRTUAL_ENV = $originalVirtualEnv
}
