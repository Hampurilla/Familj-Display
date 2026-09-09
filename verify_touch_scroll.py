#!/usr/bin/env python3
from pathlib import Path
import sys

PROJECT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()

style = PROJECT / "static" / "style.css"
appjs = PROJECT / "static" / "app.js"

checks = []

def check(name, ok):
    checks.append((name, bool(ok)))

style_text = style.read_text(encoding="utf-8") if style.exists() else ""
js_text = appjs.read_text(encoding="utf-8") if appjs.exists() else ""

check("style.css finns", style.exists())
check("app.js finns", appjs.exists())
check("touch-action pan-y finns", "touch-action: pan-y" in style_text)
check("scrollbar göms för Firefox", "scrollbar-width: none" in style_text)
check("WebKit scrollbar göms", "::-webkit-scrollbar" in style_text)
check("overflow-y auto", "overflow-y: auto" in style_text)
check("touch fallback laddad", "window.__familjTouchScrollV51Loaded" in js_text)
check("drag click suppression finns", 'document.addEventListener("click"' in js_text)
check("editable controls undantas", '[contenteditable="true"]' in js_text)
check("manual fallback finns", "window.scrollTo" in js_text)

failed = False
for name, ok in checks:
    print(("OK   " if ok else "FAIL ") + name)
    if not ok:
        failed = True

print()
if failed:
    print("Verifiering misslyckades.")
    raise SystemExit(1)

print("Alla statiska touch-scroll-kontroller godkända.")
print("Slutlig fysisk verifiering måste göras på Raspberry Pi Touch Display 2.")
