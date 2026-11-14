"""Búsqueda de cl.exe para nvcc en Windows (sin GPU: todo con rutas falsas)."""

from pathlib import Path

import pytest

from app.backends.cuda import host_compiler

MSVC_BIN = "VC/Tools/MSVC/{version}/bin/Hostx64/x64"


def fake_install(root: Path, *versions: str) -> Path:
  for version in versions:
    folder = root / MSVC_BIN.format(version=version)
    folder.mkdir(parents=True)
    (folder / "cl.exe").touch()
  return root


def test_highest_msvc_version_wins(tmp_path, monkeypatch):
  install = fake_install(tmp_path / "VS", "14.44.35207", "14.50.35717", "14.9.1")
  monkeypatch.setattr(host_compiler, "_vswhere_installations", lambda: [install])
  monkeypatch.setattr(host_compiler, "_standard_installations", lambda: [])
  assert host_compiler.find_cl_dir() == install / MSVC_BIN.format(version="14.50.35717")


def test_no_options_outside_windows(monkeypatch):
  monkeypatch.setattr(host_compiler.sys, "platform", "linux")
  assert host_compiler.host_compiler_options() == []


def test_configured_folder_is_used_on_windows(monkeypatch, tmp_path):
  monkeypatch.setattr(host_compiler.sys, "platform", host_compiler.WINDOWS)
  monkeypatch.setattr(host_compiler.shutil, "which", lambda name: None)
  monkeypatch.setenv(host_compiler.HOST_COMPILER_DIR_VAR, str(tmp_path))
  assert host_compiler.host_compiler_options() == ["-ccbin", str(tmp_path)]


def test_missing_compiler_has_a_readable_error(monkeypatch):
  monkeypatch.setattr(host_compiler.sys, "platform", host_compiler.WINDOWS)
  monkeypatch.setattr(host_compiler.shutil, "which", lambda name: None)
  monkeypatch.delenv(host_compiler.HOST_COMPILER_DIR_VAR, raising=False)
  monkeypatch.setattr(host_compiler, "find_cl_dir", lambda: None)
  with pytest.raises(host_compiler.HostCompilerNotFoundError, match="cl.exe"):
    host_compiler.host_compiler_options()


def test_extra_nvcc_options_are_split(monkeypatch):
  monkeypatch.setenv(host_compiler.EXTRA_NVCC_OPTIONS_VAR, "-allow-unsupported-compiler -lineinfo")
  assert host_compiler.extra_nvcc_options() == ["-allow-unsupported-compiler", "-lineinfo"]
