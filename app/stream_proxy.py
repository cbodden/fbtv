"""Optional ffmpeg HLS → MPEG-TS remux for split-egress clients."""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Iterator
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class StreamProxyBusy(Exception):
    """Raised when STREAM_PROXY_MAX concurrent remuxes are already active."""


class StreamProxyError(Exception):
    """Raised when ffmpeg cannot start or produces no output."""


class StreamProxy:
    def __init__(self, *, ffmpeg_path: str, max_streams: int) -> None:
        self.ffmpeg_path = ffmpeg_path
        self.max_streams = max(1, max_streams)
        self._lock = Lock()
        self._active = 0

    def runtime_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": True,
                "max": self.max_streams,
                "active": self._active,
                "ffmpeg_path": self.ffmpeg_path,
            }

    def can_accept(self) -> bool:
        with self._lock:
            return self._active < self.max_streams

    def _begin(self) -> None:
        with self._lock:
            if self._active >= self.max_streams:
                raise StreamProxyBusy(
                    f"Stream proxy at capacity ({self.max_streams} concurrent)"
                )
            self._active += 1

    def _end(self) -> None:
        with self._lock:
            self._active = max(0, self._active - 1)

    def iter_mpegts(self, url: str) -> Iterator[bytes]:
        """Spawn ffmpeg and yield MPEG-TS chunks. Releases the slot on exit."""
        self._begin()
        proc: subprocess.Popen[bytes] | None = None
        try:
            binary = shutil.which(self.ffmpeg_path) or (
                self.ffmpeg_path if self.ffmpeg_path.startswith("/") else None
            )
            if not binary:
                raise StreamProxyError(
                    f"ffmpeg not found ({self.ffmpeg_path!r}); install ffmpeg or set FFMPEG_PATH"
                )

            cmd = [
                binary,
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                url,
                "-c",
                "copy",
                "-f",
                "mpegts",
                "-",
            ]
            logger.info(
                "Stream proxy starting ffmpeg remux (active=%s/%s)",
                self._active,
                self.max_streams,
            )
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            assert proc.stdout is not None
            first = proc.stdout.read(65536)
            if not first:
                err = b""
                if proc.stderr is not None:
                    err = proc.stderr.read(4096)
                code = proc.poll()
                detail = err.decode("utf-8", errors="replace").strip() or f"exit={code}"
                raise StreamProxyError(f"ffmpeg produced no MPEG-TS output ({detail})")
            yield first
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            if proc is not None:
                _terminate(proc)
            self._end()
            logger.info(
                "Stream proxy finished (active=%s/%s)",
                self._active,
                self.max_streams,
            )


def _terminate(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
    except Exception:
        logger.exception("Failed to stop ffmpeg process pid=%s", proc.pid)
