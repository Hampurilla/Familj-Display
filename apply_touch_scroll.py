#!/usr/bin/env python3
from pathlib import Path
import shutil
import re
import sys
from datetime import datetime

PROJECT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()

STYLE = PROJECT / "static" / "style.css"
APPJS = PROJECT / "static" / "app.js"

PATCH_DIR = Path(__file__).resolve().parent / "patch"
PATCH_CSS = PATCH_DIR / "touch-scroll-v5.1.css"
PATCH_JS = PATCH_DIR / "touch-scroll-v5.1.js"

CSS_START = "/* === FAMILJ_TOUCH_SCROLL_V5_1_START === */"
CSS_END = "/* === FAMILJ_TOUCH_SCROLL_V5_1_END === */"

JS_START = "/* === FAMILJ_TOUCH_SCROLL_V5_1_START === */"
JS_END = "/* === FAMILJ_TOUCH_SCROLL_V5_1_END === */"

def replace_or_append(path: Path, start: str, end: str, payload: str):
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    block = f"\n{start}\n{payload.rstrip()}\n{end}\n"

    pattern = re.compile(
        re.escape(start) + r".*?" + re.escape(end),
        flags=re.S
    )

    if pattern.search(current):
        new = pattern.sub(
            f"{start}\n{payload.rstrip()}\n{end}",
            current
        )
    else:
        new = current.rstrip() + block

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new, encoding="utf-8", newline="\n")

def main():
    if not (PROJECT / "static").exists():
        raise SystemExit(f"Hittar ingen static/-mapp i {PROJECT}")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = PROJECT / f"touch-scroll-backup-{stamp}"
    backup.mkdir(parents=True, exist_ok=True)

    for f in (STYLE, APPJS):
        if f.exists():
            shutil.copy2(f, backup / f.name)

    replace_or_append(
        STYLE,
        CSS_START,
        CSS_END,
        PATCH_CSS.read_text(encoding="utf-8")
    )

    replace_or_append(
        APPJS,
        JS_START,
        JS_END,
        PATCH_JS.read_text(encoding="utf-8")
    )

    print("Touch Scroll v5.1 installerad.")
    print(f"Projekt: {PROJECT}")
    print(f"Backup: {backup}")
    print("")
    print("Starta om appen med:")
    print("  sudo systemctl restart home-display")
    print("")
    print("Om Chromium cachear gamla filer:")
    print("  sudo reboot")

if __name__ == "__main__":
    main()
