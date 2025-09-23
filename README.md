# Crittr

Crittr is a lightweight media review tool intended for animators and artists. It focuses on responsive playback, precise timecode display, efficient scrubbing, and note-taking.

This repository contains the application sources, optional Cython modules, packaging scripts, and installer creation utilities.

## Project Structure

- **Platform:** Windows first (PyInstaller executable)
- **Formats:** Video (FFmpeg via ffpyplayer/PyAV) + image sequences (PNG/JPG/TIFF/EXR)
- **Scope:** Local projects, reviewer-controlled data; SaaS-style features are out-of-scope for v1

---

## Goals
- **Speed up feedback loops** with on-frame drawing and notes.
- **Make feedback actionable**: bookmarks, tags, and status per note.
- **Track change across versions** of the same playblast.
- **Stay format-flexible**: video or image sets, now and later.
- **Keep data local**: simple, secure, studio-friendly.

---

## Core Features (MVP)
- Open & scrub **videos / image sequences**
- **Draw** (single pen) + **per-frame notes**
- **Bookmarks** on frames (visible markers on the timeline)
- **Session autosave** and reopen
- **Versioned imports** (copy media into project structure)

**V1 adds:** layered drawings (visibility/opacity/lock), brush size/opacity, holds (frame ranges), ghosting, link comments to drawings, cut/copy/move/paste drawings, **compare versions** (synced), **multi-camera** (synced), **exports** (HTML/PDF/CSV), hotkeys.

---

## Tech Stack
- **UI:** PySide6 (Qt for Python)
- **Decode:** ffpyplayer (FFmpeg), optional PyAV backend
- **Numerics:** NumPy
- **Data:** SQLite + project folders
- **Packaging:** PyInstaller
- **Config & Logs:** QSettings + rotating file logs

> Bootstrapped from:
> - `app_to_exe_template` (Digi Monsters): packaging, config, logging
> - `cvplayer`: OpenCV/FFmpeg-based playback widget patterns

---

## Key Features

- Time-based timeline slider (milliseconds) with accurate duration from metadata or robust fallback probing
- Fast, responsive scrubbing using OpenCV for preview frames during slider drag
- Playback via ffpyplayer backend for proper PTS pacing
- Minimal, extensible UI built with Qt (widgets + layouts)
- Notes, playlist, and inspector panes designed for animation review workflows

## How Playback Works

- Backend: ffpyplayer decodes frames and emits PTS-based updates for smooth playback.
- Duration: we first attempt to read duration from ffpyplayer metadata; if unavailable, we probe using OpenCV (frame_count / fps). This value drives the slider maximum (in milliseconds).
- Slider:
  - The slider value represents time in milliseconds (not frame indices).
  - During playback, it advances based on PTS — stable and free of FPS-estimate drift.
  - If a media’s duration cannot be determined, the slider grows dynamically as playback progresses.
- Scrubbing:
  - While dragging the slider, preview frames are fetched via OpenCV for instant feedback without disrupting ffpyplayer.
  - When the slider is released, a single robust seek aligns the playback backend to the chosen position.

## Controls Overview

- Play/Pause: toggles playback.
- Go to Start/End: jumps to the beginning or end of the clip.
- Step ±1 Frame: computes a single-frame step from the current time using the effective FPS and seeks precisely.
- Rate: UI placeholder for future backend rate control.

This launches the Qt application with the main window containing the player, playlist, notes, and inspector panels.

## Development Workflow

1. Develop in-place in `crittr/` and run `main.py` for quick iterations.
2. Optimize critical paths incrementally:
   - Add high-level logic in `crittr/logic/`
   - Improve UI/UX in `crittr/ui/`
   - For hotspots, consider migrating sections to `cython_logic/` (optional)
3. Packaging/Installer (Windows):
   - Use the scripts in `installer/` (NSIS-based) and `build.py` as needed.

## Notes on Media Handling

- Duration metadata can be missing in some containers. We fall back to OpenCV probing for reliable total length.
- Timeline is always time-based (ms). This avoids confusion from evolving FPS estimates during playback.
- Scrubbing uses OpenCV for preview frames only during drag to keep it responsive, then commits a precise backend seek on release.

## Contributing

- Keep UI updates on the Qt main thread.
- When adding new widgets, prefer clear signal/slot contracts to keep composition simple.
- For performance-sensitive code, measure first; then optimize and consider Cython only where justified.

## License

Copyright © Digi Monsters.

- Python 3.11+
- Windows (recommended; installer pipeline targets Windows)
- Dependencies in `requirements.txt` (notably Qt, numpy, opencv-python, requests, etc.)

## Running

From the repository root:
