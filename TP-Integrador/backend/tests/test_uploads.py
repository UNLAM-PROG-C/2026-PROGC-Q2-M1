import io
import stat
import zipfile

import pytest
from PIL import Image

from app.web.uploads import TILES_DIR, UploadError, UploadStore, UploadTooLargeError

MAX_BYTES = 200_000
MAX_ENTRIES = 50
SAMPLE_COUNT = 3


def png_bytes(size=(8, 6), color=(10, 20, 30)) -> bytes:
  buffer = io.BytesIO()
  Image.new("RGB", size, color).save(buffer, format="PNG")
  return buffer.getvalue()


def zip_bytes(entries: dict[str, bytes], symlinks: tuple[str, ...] = ()) -> io.BytesIO:
  buffer = io.BytesIO()
  with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
    for name, data in entries.items():
      archive.writestr(name, data)
    for name in symlinks:
      info = zipfile.ZipInfo(name)
      info.external_attr = (stat.S_IFLNK | 0o777) << 16
      archive.writestr(info, "/etc/passwd")
  buffer.seek(0)
  return buffer


@pytest.fixture
def store(tmp_path):
  upload_store = UploadStore(tmp_path / "base", MAX_BYTES, MAX_ENTRIES, SAMPLE_COUNT)
  upload_store.reset()
  return upload_store


def stored_files(store, tiles_id):
  folder = store.tiles_dir(tiles_id)
  return sorted(path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file())


def test_loose_files(store):
  files = [("a.jpg", io.BytesIO(png_bytes())), ("B.PNG", io.BytesIO(png_bytes())), ("notas.txt", io.BytesIO(b"x"))]
  summary = store.save_tiles_files(files, set())
  assert (summary.accepted, summary.ignored, summary.rejected) == (2, 1, 0)
  assert stored_files(store, summary.tiles_id) == ["B.PNG", "a.jpg"]
  assert store.last_tiles == summary


def test_zip_with_folders_keeps_relative_paths(store):
  entries = {"viaje/dia1/a.jpg": png_bytes(), "viaje/dia2/b.webp": png_bytes(), "c.jpeg": png_bytes()}
  summary = store.save_tiles_zip(zip_bytes(entries), set())
  assert summary.accepted == 3
  assert stored_files(store, summary.tiles_id) == ["c.jpeg", "viaje/dia1/a.jpg", "viaje/dia2/b.webp"]
  assert summary.samples == ("c.jpeg", "viaje/dia1/a.jpg", "viaje/dia2/b.webp")
  assert store.sample_path(summary, 1).read_bytes() == png_bytes()
  assert store.sample_path(summary, SAMPLE_COUNT) is None


def test_zip_ignores_macos_metadata_and_text(store):
  entries = {"a.jpg": png_bytes(), "leeme.txt": b"x", "__MACOSX/._a.jpg": b"x", "carpeta/._b.jpg": b"x"}
  summary = store.save_tiles_zip(zip_bytes(entries), set())
  assert (summary.accepted, summary.ignored, summary.rejected) == (1, 3, 0)
  assert stored_files(store, summary.tiles_id) == ["a.jpg"]


def test_zip_rejects_path_traversal_absolute_paths_and_symlinks(store, tmp_path):
  entries = {"a.jpg": png_bytes(), "../../etc/passwd": b"root", "../fuera.jpg": png_bytes(), "/abs.jpg": png_bytes()}
  summary = store.save_tiles_zip(zip_bytes(entries, symlinks=("enlace.jpg",)), set())
  assert (summary.accepted, summary.rejected) == (1, 4)
  assert not (tmp_path / "fuera.jpg").exists() and not (store.root / TILES_DIR / "fuera.jpg").exists()
  assert stored_files(store, summary.tiles_id) == ["a.jpg"]


def test_zip_over_uncompressed_limit_is_413_and_deleted(store):
  big = bytes(MAX_BYTES + 1)  # Se comprime muy bien: el zip es chico, lo descomprimido no.
  with pytest.raises(UploadTooLargeError) as error:
    store.save_tiles_zip(zip_bytes({"a.png": png_bytes(), "grande.png": big}), set())
  assert error.value.status_code == 413
  assert list((store.root / TILES_DIR).iterdir()) == []


def test_zip_file_over_upload_limit_is_413_and_deleted(store, tmp_path):
  with pytest.raises(UploadTooLargeError):
    store.save_tiles_zip(io.BytesIO(bytes(MAX_BYTES + 1)), set())
  assert list((store.root / TILES_DIR).iterdir()) == []


def test_too_many_entries_is_413(store):
  entries = {f"{index}.png": b"x" for index in range(MAX_ENTRIES + 1)}
  with pytest.raises(UploadTooLargeError):
    store.save_tiles_zip(zip_bytes(entries), set())


def test_batch_without_images_is_rejected(store):
  with pytest.raises(UploadError) as error:
    store.save_tiles_files([("a.txt", io.BytesIO(b"x"))], set())
  assert error.value.status_code == 400


def test_target_dimensions_and_gif_rejected(store):
  target = store.save_target("foto.png", io.BytesIO(png_bytes((40, 30))), set())
  assert (target.width, target.height, target.filename) == (40, 30, "foto.png")
  assert store.target_path(target).is_file()
  with pytest.raises(UploadError) as error:
    store.save_target("anim.gif", io.BytesIO(b"GIF89a"), set())
  assert error.value.status_code == 400
  assert "JPEG, PNG o WebP" in str(error.value)


def test_target_with_image_extension_but_invalid_content_is_400(store):
  with pytest.raises(UploadError, match="no se pudo leer"):
    store.save_target("roto.jpg", io.BytesIO(b"no es una imagen"), set())


def test_new_batch_keeps_last_target_and_only_new_batch(store):
  target = store.save_target("t.png", io.BytesIO(png_bytes()), set())
  first = store.save_tiles_files([("a.png", io.BytesIO(png_bytes()))], set())
  second = store.save_tiles_files([("b.png", io.BytesIO(png_bytes()))], set())
  assert [path.name for path in (store.root / TILES_DIR).iterdir()] == [second.tiles_id]
  assert store.tiles(first.tiles_id) is None and store.tiles(second.tiles_id) == second
  assert store.last_target == target and store.target_path(target).is_file()


def test_batch_used_by_running_job_is_kept(store):
  first = store.save_tiles_files([("a.png", io.BytesIO(png_bytes()))], set())
  store.save_tiles_files([("b.png", io.BytesIO(png_bytes()))], {first.tiles_id})
  assert store.tiles_dir(first.tiles_id).is_dir()


def test_new_job_removes_previous_results_and_reset_cleans_everything(store):
  first = store.create_job_dir("job1", set())
  (first / "cpu").mkdir()
  second = store.create_job_dir("job2", set())
  assert not first.exists() and second.is_dir()
  store.save_tiles_files([("a.png", io.BytesIO(png_bytes()))], set())
  store.reset()
  assert all(not any(folder.iterdir()) for folder in store.root.iterdir())
  assert store.last_tiles is None
