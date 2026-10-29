import json
import os
import stat
import sys
import tempfile
from pathlib import Path


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def main():
    if len(sys.argv) != 4:
        fail("expected config path, station id, and key path")
    config_path, station_id, key_path = map(Path, (sys.argv[1], sys.argv[2], sys.argv[3]))
    secret = sys.stdin.buffer.read()
    if not secret.strip():
        fail("station key input is empty")
    if not config_path.is_file() or config_path.is_symlink():
        fail("relay config is missing or not a regular file")
    if not station_id.name or not key_path.is_absolute():
        fail("invalid station id or key path")
    try:
        config_bytes = config_path.read_bytes()
        config = json.loads(config_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        fail("relay config cannot be read as JSON")
    key_map = config.get("station_key_files")
    if not isinstance(key_map, dict):
        fail("relay station_key_files map is missing")
    configured_path = key_map.get(station_id.name)
    if configured_path is not None and configured_path != str(key_path):
        fail("station id is already mapped to a different key path")
    try:
        for mapped_station, mapped_path in key_map.items():
            existing_key = Path(mapped_path).read_bytes()
            if existing_key == secret and not (mapped_station == station_id.name and mapped_path == str(key_path)):
                fail("station key uniqueness check failed")
    except Exception:
        fail("station key uniqueness check failed")
    if key_path.exists():
        if key_path.is_symlink() or not key_path.is_file():
            fail("station key path is not a regular file")
        if key_path.read_bytes() != secret:
            fail("existing station key differs from encrypted input")
    else:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            fail("station key appeared during enrollment")
        with os.fdopen(fd, "wb") as stream:
            stream.write(secret)
            stream.flush()
            os.fsync(stream.fileno())
        key_changed = True
    if configured_path is None:
        config["station_key_files"][station_id.name] = str(key_path)
        mode = stat.S_IMODE(config_path.stat().st_mode)
        owner = config_path.stat()
        fd, temporary = tempfile.mkstemp(prefix=".relay.json.", dir=config_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(config, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, mode)
            os.chown(temporary, owner.st_uid, owner.st_gid)
            if config_path.read_bytes() != config_bytes:
                fail("relay config changed during enrollment")
            os.replace(temporary, config_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        print("changed")
        return
    print("changed" if locals().get("key_changed", False) else "ok")


if __name__ == "__main__":
    main()
