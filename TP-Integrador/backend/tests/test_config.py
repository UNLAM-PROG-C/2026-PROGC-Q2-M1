from pathlib import Path

from app.config import DEFAULT_FRONTEND_ORIGIN, load_settings

# Valores por defecto de frontend/env.example (FRONTEND_PORT) y de vite.config.ts.
FRONTEND_DEFAULT_ORIGIN = "http://127.0.0.1:5173"


def test_without_environment_listens_only_locally():
  settings = load_settings({})
  assert settings.host == "127.0.0.1"
  assert settings.port == 8000


def test_default_origin_matches_default_frontend():
  assert load_settings({}).frontend_origin == FRONTEND_DEFAULT_ORIGIN == DEFAULT_FRONTEND_ORIGIN


def test_environment_variable_overrides_default(tmp_path):
  environ = {"MOSAIC_PORT": "9001", "MOSAIC_TEMP_DIR": str(tmp_path), "MOSAIC_CPU_CONFIRM_SECONDS": "12.5"}
  settings = load_settings(environ)
  assert settings.port == 9001
  assert settings.temp_dir == Path(tmp_path)
  assert settings.cpu_confirm_seconds == 12.5


def test_empty_variable_keeps_default_and_origin_drops_trailing_slash():
  settings = load_settings({"MOSAIC_HOST": "  ", "MOSAIC_FRONTEND_ORIGIN": "http://localhost:3000/"})
  assert settings.host == "127.0.0.1"
  assert settings.frontend_origin == "http://localhost:3000"


def test_every_setting_is_documented_in_env_example():
  example = (Path(__file__).resolve().parents[1] / "env.example").read_text(encoding="utf-8")
  from app.config import _FIELDS

  for name in _FIELDS:
    assert f"{name}=" in example
