#!/usr/bin/env python3
"""Frontend architecture checker for living-paper.

Validates:
  1. Script load order matches dependency chain
  2. CSS layering (base.css before page-specific)
  3. Referenced files exist
  4. defer attribute consistency
  5. App._ private property ownership
  6. No hardcoded localhost URLs in JS
  7. No direct innerHTML assignment (non-empty) in JS
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"

JS_DEP_CHAIN = {
    "store.js": [],
    "html-utils.js": ["store.js"],
    "api.js": ["store.js", "html-utils.js"],
    "ui.js": ["store.js", "html-utils.js", "api.js"],
    "map.js": ["store.js", "html-utils.js", "api.js", "ui.js"],
    "dialogue.js": ["store.js", "html-utils.js", "api.js", "ui.js"],
    "confirm.js": ["store.js", "html-utils.js"],
    "auth.js": ["store.js", "html-utils.js", "api.js", "confirm.js"],
    "main.js": ["store.js", "html-utils.js", "api.js", "ui.js", "map.js", "dialogue.js", "confirm.js", "auth.js"],
    "tests.js": ["store.js", "html-utils.js", "api.js"],
}

PRIVATE_PROP_OWNERS = {
    "_playerX": ["map.js"],
    "_playerY": ["map.js"],
    "_isMoving": ["map.js"],
    "_playerMarkerState": ["map.js"],
    "_lastDir": ["map.js"],
    "_mapLocations": ["ui.js"],
    "_streamAbortController": ["api.js", "dialogue.js"],
    "_actLoopAbortController": ["api.js", "dialogue.js", "main.js"],
    "_showOfflineScreen": ["main.js"],
}

errors = []


def err(msg: str) -> None:
    errors.append(msg)
    print(f"  ✗ {msg}")


def _strip_version(ref: str) -> str:
    return ref.split("?", 1)[0]


def check_script_order(html_path: Path) -> None:
    print(f"\n📋 Script load order: {html_path.name}")
    text = html_path.read_text(encoding="utf-8")
    scripts = re.findall(r'<script\s+src="js/([^"]+)"(\s+defer)?', text)
    if not scripts:
        err(f"No scripts found in {html_path.name}")
        return

    loaded = []
    for raw_name, defer_attr in scripts:
        name = _strip_version(raw_name)
        if not defer_attr and name != "tests.js":
            err(f"{html_path.name}: <script src='js/{name}'> missing defer attribute")

        deps = JS_DEP_CHAIN.get(name)
        if deps is None:
            err(f"{html_path.name}: Unknown script '{name}' (not in JS_DEP_CHAIN)")
            continue

        for dep in deps:
            if dep not in loaded:
                err(f"{html_path.name}: '{name}' loaded before its dependency '{dep}'")

        loaded.append(name)

    print(f"  ✓ {len(loaded)} scripts in correct order")


def check_css_order(html_path: Path) -> None:
    print(f"\n🎨 CSS load order: {html_path.name}")
    text = html_path.read_text(encoding="utf-8")
    stylesheets = [_strip_version(s) for s in re.findall(r'<link\s+rel="stylesheet"\s+href="css/([^"]+)"', text)]
    if not stylesheets:
        err(f"No stylesheets found in {html_path.name}")
        return

    if stylesheets[0] != "base.css":
        err(f"{html_path.name}: First stylesheet should be base.css, got '{stylesheets[0]}'")
    else:
        print("  ✓ base.css loaded first")

    for css_name in stylesheets:
        css_path = STATIC / "css" / css_name
        if not css_path.exists():
            err(f"{html_path.name}: Referenced CSS file does not exist: css/{css_name}")


def check_file_references(html_path: Path) -> None:
    print(f"\n📁 File references: {html_path.name}")
    text = html_path.read_text(encoding="utf-8")

    js_refs = re.findall(r'<script\s+src="([^"]+)"', text)
    css_refs = re.findall(r'<link\s+[^>]*href="([^"]+)"', text)

    for ref in js_refs + css_refs:
        file_path = STATIC / _strip_version(ref)
        if not file_path.exists():
            err(f"{html_path.name}: Referenced file does not exist: {ref}")

    total = len(js_refs) + len(css_refs)
    print(f"  ✓ All {total} referenced files exist")


def check_private_props() -> None:
    print("\n🔒 App._ private property ownership")
    js_dir = STATIC / "js"
    for js_file in sorted(js_dir.glob("*.js")):
        text = js_file.read_text(encoding="utf-8")
        for match in re.finditer(r'App\.(_\w+)\s*=', text):
            prop = match.group(1)
            owner = PRIVATE_PROP_OWNERS.get(prop)
            if owner is None:
                err(f"{js_file.name}: App.{prop} is not registered in PRIVATE_PROP_OWNERS")
                continue
            if js_file.name not in owner:
                err(f"{js_file.name}: App.{prop} should only be written by {owner}")

    print("  ✓ Private property ownership validated")


def check_no_hardcoded_urls() -> None:
    print("\n🌐 Hardcoded URL check")
    js_dir = STATIC / "js"
    for js_file in sorted(js_dir.glob("*.js")):
        text = js_file.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
                continue
            if re.search(r'https?://localhost', line):
                err(f"{js_file.name}:{i}: Hardcoded localhost URL found")
            if re.search(r'127\.0\.0\.1', line):
                err(f"{js_file.name}:{i}: Hardcoded 127.0.0.1 found")

    print("  ✓ No hardcoded URLs")


def check_no_direct_innerhtml() -> None:
    print("\n🛡️ Direct innerHTML check")
    js_dir = STATIC / "js"
    for js_file in sorted(js_dir.glob("*.js")):
        if js_file.name == "html-utils.js":
            continue
        text = js_file.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
                continue
            if re.search(r'\.innerHTML\s*=\s*[\'"]<', line):
                err(f"{js_file.name}:{i}: Direct innerHTML with HTML content (use HtmlUtils or DOM API)")

    print("  ✓ No direct innerHTML with HTML content")


def main() -> int:
    print("═══════════════════════════════════════════")
    print("  Frontend Architecture Checker")
    print("═══════════════════════════════════════════")

    html_files = [f for f in STATIC.glob("*.html") if f.name != "admin.html"]
    for html_path in sorted(html_files):
        check_script_order(html_path)
        check_css_order(html_path)
        check_file_references(html_path)

    check_private_props()
    check_no_hardcoded_urls()
    check_no_direct_innerhtml()

    print("\n═══════════════════════════════════════════")
    if errors:
        print(f"  ❌ {len(errors)} error(s) found")
        return 1
    else:
        print("  ✅ All checks passed")
        return 0


if __name__ == "__main__":
    sys.exit(main())
