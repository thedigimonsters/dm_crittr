"""
Application configuration settings
Do not modify these values once your application has been distributed to users.
This file centralises brand, packaging, paths, formats, and runtime defaults.
"""

from __future__ import annotations
import os
import sys
import platform
from pathlib import Path

DEV_MODE = True
DEV_STARTUP_MOV = r"R:\Digi\faceware_roms\Female_Performance_ROM_02.mov"
DEV_LAYER = [
    {
        "id": "L1",
        "name": "Blocking",
        "color": "#8ab4f8",
        "notes": [
            {"id": "n1", "start_s": 10.0, "end_s": 12.0, "text": "Pose C timing"},
        ],
    },
    {
        "id": "L2",
        "name": "Polish",
        "color": "#80cbc4",
        "notes": [
            {"id": "n1a", "start_s": 12.0, "end_s": 14.0, "text": "Pose D timing"},
            {"id": "n2b", "start_s": 15.0, "end_s": 16.0, "text": "Pose E timing"},
        ],
    }
]

# ───────────────────────────────────────────────────────────────────────────────
# Core fields used by PyInstaller / MSI creator (keep names unchanged)
# ───────────────────────────────────────────────────────────────────────────────
# Application name (used for executable and installer)
APP_NAME = "Crittr"

# Application version in format x.y.z
APP_VERSION = "0.1.0"

# Company or developer name
COMPANY_NAME = "Digi Monsters"

# Product ID - must be a valid GUID for Windows MSI installers
# This GUID is used by Windows to identify the application for updates
# Once you've shipped a version to users, don't change this GUID
# TODO: Replace with a NEW GUID for Crittr before first public release.
APP_UUID = "{baf9a395-3698-40f2-82b1-d4b183c11232}"

# Icon file for the application (relative to project root)
# e.g., "resources/crittr.ico" — set when you add your icon
APP_ICON = None
APP_PNG = os.path.join(os.path.dirname(__file__), "crittr", "resources", "images", "crittr.png")

# ───────────────────────────────────────────────────────────────────────────────
# Crittr identity / branding
# ───────────────────────────────────────────────────────────────────────────────
# Reverse-DNS App ID (used in About/QSettings/diagnostics)
APP_ID = "uk.digimonsters.crittr"

# Organization identifiers (for QSettings, folders, About box)
ORG_NAME = "Digi Monsters"       # human readable
ORG_DIRNAME = "DigiMonsters"     # filesystem safe (no spaces)
ORG_DOMAIN = "digimonsters.uk"

# Code & distribution naming
REPO_NAME = "dm_crittr"
PACKAGE_NAME = "crittr"          # Python import package
DIST_NAME = "dm-crittr"          # pip/dist name if ever published

# Repo/URLs (About dialog, logs, diagnostics)
REPO_URL = "https://github.com/thedigimonsters/dm_crittr"
ISSUE_URL = f"{REPO_URL}/issues"
DOCS_URL = ""  # optional: link your Confluence page

# Marketing strings
TAGLINE = "Friendly feedback for frames & clips."
APP_DESCRIPTION = (
    "Crittr is Digi Monsters’ lightweight review tool for videos and images: "
    "draw on frames, add notes, track versions, and export clean reports."
)

# Build metadata (optional, stamped by CI or PyInstaller spec)
BUILD_COMMIT = os.getenv("CRITTR_BUILD_COMMIT", "")[:7]
BUILD_CHANNEL = os.getenv("CRITTR_BUILD_CHANNEL", "dev")  # dev/beta/stable


def version_string() -> str:
    """Human-friendly version string for About dialogs and logs."""
    meta = f"+{BUILD_COMMIT}" if BUILD_COMMIT else ""
    chan = f" ({BUILD_CHANNEL})" if BUILD_CHANNEL and BUILD_CHANNEL != "stable" else ""
    return f"{APP_VERSION}{meta}{chan}"


# ───────────────────────────────────────────────────────────────────────────────
# Supported formats / detection hints
# ───────────────────────────────────────────────────────────────────────────────
VIDEO_EXTS = {
    ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm", ".wmv", ".mpg", ".mpeg"
}
IMAGE_EXTS = {
    ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".exr"
}
# Treat numbered image sequences as clips (e.g., frame_0001.png → frame_####.png)
SEQUENCE_GLOB_CANDIDATES = [
    "*.png", "*.jpg", "*.jpeg", "*.tif", "*.tiff", "*.exr", "*.bmp"
]

# Preferred decoding backend (we keep a pluggable abstraction in code)
DEFAULT_VIDEO_BACKEND = "ffpyplayer"  # or "pyav"
FFMPEG_THREADS = "auto"               # passed to backend if supported

# Bundled resource folder names (used by PyInstaller data files)
FFMPEG_DIRNAME = "ffmpeg"      # e.g., ffmpeg/avcodec-*.dll
QT_PLUGINS_DIRNAME = "qt_plugins"
ICON_FILENAME = "crittr.ico"   # used when APP_ICON is set


# ───────────────────────────────────────────────────────────────────────────────
# Runtime / packaging helpers
# ───────────────────────────────────────────────────────────────────────────────
def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def resource_path(*parts: str) -> Path:
    """
    Path to bundled/static files. In PyInstaller mode, resolves under sys._MEIPASS;
    otherwise relative to this file’s directory.
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*parts)


# ───────────────────────────────────────────────────────────────────────────────
# User data locations (settings, logs, DB, default projects)
# ───────────────────────────────────────────────────────────────────────────────
def _appdata_base() -> Path:
    system = platform.system()
    if system == "Windows":
        base = os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming")
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return Path(base) / ORG_DIRNAME / APP_NAME


APPDATA_DIR = _appdata_base()
LOG_DIR = APPDATA_DIR / "logs"
CACHE_DIR = APPDATA_DIR / "cache"
SETTINGS_FILE = APPDATA_DIR / "settings.ini"  # QSettings (Native) is fine too
DATABASE_PATH = APPDATA_DIR / "crittr.db"
DEFAULT_PROJECTS_DIR = Path.home() / "CrittrProjects"


def ensure_app_dirs() -> None:
    """Create required folders if they don't exist."""
    for p in (APPDATA_DIR, LOG_DIR, CACHE_DIR, DEFAULT_PROJECTS_DIR):
        p.mkdir(parents=True, exist_ok=True)


# ───────────────────────────────────────────────────────────────────────────────
# QSettings bootstrap (call once during crittr init)
# ───────────────────────────────────────────────────────────────────────────────
def apply_qsettings_org() -> None:
    """
    Apply org/crittr metadata for QSettings. Call early in crittr startup,
    before constructing your first QSettings instance.
    """
    try:
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.setOrganizationName(ORG_NAME)
        QCoreApplication.setOrganizationDomain(ORG_DOMAIN)
        QCoreApplication.setApplicationName(APP_NAME)
    except Exception:
        # Safe to import this module in non-Qt contexts (e.g., CLI tools)
        pass


# ───────────────────────────────────────────────────────────────────────────────
# Exports / reports
# ───────────────────────────────────────────────────────────────────────────────
EXPORT_TITLE = "Crittr Review Report"
EXPORT_HTML_FILENAME = "crittr_report.html"
EXPORT_PDF_FILENAME = "crittr_report.pdf"
EXPORT_CSV_FILENAME = "crittr_notes.csv"
EXPORT_BUNDLE_BASENAME = "crittr_review_bundle"  # used for ZIP bundles


# ───────────────────────────────────────────────────────────────────────────────
# Session / data model identifiers
# ───────────────────────────────────────────────────────────────────────────────
SESSION_SCHEMA_KEY = "crittr_v1"  # namespace for saved JSON
NOTE_STATES = ("open", "in_progress", "done", "wont_fix")


# ───────────────────────────────────────────────────────────────────────────────
# CLI hints (for your argparse/typer setup)
# ───────────────────────────────────────────────────────────────────────────────
CLI_NAME = "crittr"
CLI_EXAMPLES = (
    'crittr --open "C:/shots/shot001_v0003.mov" --frame 123\n'
    'crittr --import "C:/shots/seq/shot_####.png" --project "TestProject"\n'
)

# ───────────────────────────────────────────────────────────────────────────────
# Defaults / UI hints (read by settings wrapper; safe to change before shipping)
# ───────────────────────────────────────────────────────────────────────────────
DEFAULTS = {
    "video": {
        "backend": DEFAULT_VIDEO_BACKEND,   # "ffpyplayer" or "pyav"
        "ffmpeg_threads": FFMPEG_THREADS,   # typically "auto"
        "max_frame_cache_mb": 512,
        "prefetch_on_scrub": True,
    },
    "overlay": {
        "default_color": "#ff5a36",
        "default_width_px": 3,
        "default_opacity": 1.0,
        # Ghosting is a Phase 8 feature; defaults here are harmless placeholders
        "ghosting_frames": 3,               # ±N frames
        "ghosting_opacity": 0.35,
        "layers": [
            {"name": "Notes", "visible": True, "opacity": 1.0, "locked": False},
        ],
    },
    "hotkeys": {
        "play_pause": "K",
        "step_prev": "J",
        "step_next": "L",
        "bookmark": "B",
        "note_focus": "N",
        "pen_tool": "P",
        "eraser_tool": "E",
        "increase_brush": "]",
        "decrease_brush": "[",
        "compare_toggle": "C",
    },
    "paths": {
        "projects_dir": str(DEFAULT_PROJECTS_DIR),
        "database": str(DATABASE_PATH),
        "logs_dir": str(LOG_DIR),
    },
}

# ───────────────────────────────────────────────────────────────────────────────
# Convenience banner for logs / about dialog
# ───────────────────────────────────────────────────────────────────────────────
def banner() -> str:
    return (
        f"{APP_NAME} {version_string()}  •  {APP_ID}\n"
        f"Vendor: {COMPANY_NAME}  •  Repo: {REPO_URL}\n"
        f"Data: {APPDATA_DIR}"
    )


if __name__ == "__main__":
    # Quick sanity check when run directly
    ensure_app_dirs()
    print(banner())
    print("Projects:", DEFAULT_PROJECTS_DIR)
    print("DB:      ", DATABASE_PATH)
