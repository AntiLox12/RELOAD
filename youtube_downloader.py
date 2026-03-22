from __future__ import annotations

import asyncio
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import yt_dlp


YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}

PROJECT_ROOT = Path(__file__).resolve().parent
LOCAL_FFMPEG_DIR_CANDIDATES = (
    PROJECT_ROOT / "ffmpeg-2026-03-18-git-106616f13d-essentials_build" / "bin",
    PROJECT_ROOT / "ffmpeg" / "bin",
)


class YoutubeDownloaderError(Exception):
    """Base error for YouTube audio downloads."""


class UnsupportedYoutubeUrlError(YoutubeDownloaderError):
    """Raised when URL does not point to YouTube or YouTube Music."""


class FfmpegNotFoundError(YoutubeDownloaderError):
    """Raised when ffmpeg is not installed or not available in PATH."""


class YoutubeAudioDownloadError(YoutubeDownloaderError):
    """Raised when yt-dlp fails to download or convert audio."""


@dataclass
class DownloadedAudio:
    audio_path: Path
    thumbnail_path: Optional[Path]
    title: str
    uploader: str
    duration: Optional[int]
    source_url: str
    working_dir: Path


def is_supported_youtube_url(url: str) -> bool:
    try:
        parsed = urlparse((url or "").strip())
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host
    return host in YOUTUBE_HOSTS


def extract_first_youtube_url(text: str) -> Optional[str]:
    for chunk in (text or "").split():
        candidate = chunk.strip().strip("<>[](){}.,!?:;\"'")
        if is_supported_youtube_url(candidate):
            return candidate
    return None


def _find_file(directory: Path, suffixes: tuple[str, ...], preferred_stem: Optional[str] = None) -> Optional[Path]:
    candidates = [
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in suffixes
    ]
    if not candidates:
        return None
    if preferred_stem:
        for candidate in candidates:
            if candidate.stem == preferred_stem:
                return candidate
    candidates.sort(key=lambda item: item.stat().st_size, reverse=True)
    return candidates[0]


def _resolve_ffmpeg_dir() -> Optional[Path]:
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return Path(ffmpeg_path).resolve().parent
    for candidate in LOCAL_FFMPEG_DIR_CANDIDATES:
        ffmpeg_exe = candidate / "ffmpeg.exe"
        ffprobe_exe = candidate / "ffprobe.exe"
        if ffmpeg_exe.exists() and ffprobe_exe.exists():
            return candidate
    return None


def download_youtube_audio(url: str) -> DownloadedAudio:
    if not is_supported_youtube_url(url):
        raise UnsupportedYoutubeUrlError("Only YouTube and YouTube Music links are supported.")
    ffmpeg_dir = _resolve_ffmpeg_dir()
    if ffmpeg_dir is None:
        raise FfmpegNotFoundError("ffmpeg is required to convert audio to mp3.")

    working_dir = Path(tempfile.mkdtemp(prefix="yt_audio_"))
    output_template = str(working_dir / "%(title).180B [%(id)s].%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "writethumbnail": True,
        "ffmpeg_location": str(ffmpeg_dir),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            },
            {
                "key": "FFmpegThumbnailsConvertor",
                "format": "jpg",
            },
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as exc:
        cleanup_downloaded_audio(working_dir)
        raise YoutubeAudioDownloadError(str(exc)) from exc

    title = str((info or {}).get("title") or "YouTube Audio")
    uploader = str((info or {}).get("uploader") or (info or {}).get("channel") or "YouTube")
    duration = (info or {}).get("duration")

    audio_path = _find_file(working_dir, (".mp3",))
    if audio_path is None:
        cleanup_downloaded_audio(working_dir)
        raise YoutubeAudioDownloadError("mp3 file was not produced.")

    thumbnail_path = _find_file(
        working_dir,
        (".jpg", ".jpeg", ".png", ".webp"),
        preferred_stem=audio_path.stem,
    )

    return DownloadedAudio(
        audio_path=audio_path,
        thumbnail_path=thumbnail_path,
        title=title,
        uploader=uploader,
        duration=int(duration) if isinstance(duration, (int, float)) else None,
        source_url=url,
        working_dir=working_dir,
    )


async def download_youtube_audio_async(url: str) -> DownloadedAudio:
    return await asyncio.to_thread(download_youtube_audio, url)


def cleanup_downloaded_audio(target: Path | DownloadedAudio | None) -> None:
    if target is None:
        return
    if isinstance(target, DownloadedAudio):
        target = target.working_dir
    try:
        shutil.rmtree(target, ignore_errors=True)
    except Exception:
        pass
