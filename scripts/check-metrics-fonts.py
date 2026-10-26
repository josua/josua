"""Validate embedded Metrics fonts before Docker reads its URL-encoded env file."""
import argparse
import base64
from pathlib import Path
import re
import sys
from urllib.parse import quote

SAFE_ENV_LINE_BYTES = 60_000


def validate(workflow: Path) -> tuple[int, int]:
    lines = workflow.read_text(encoding="utf-8-sig").splitlines()
    marker = "          extras_css: |"
    try:
        start = lines.index(marker) + 1
    except ValueError as error:
        raise ValueError("Expected an extras_css block under the Metrics inputs") from error
    body = []
    for line in lines[start:]:
        if line.strip() and not line.startswith("            "):
            break
        body.append(line[12:] if line else "")
    css = "\n".join(body).rstrip() + "\n"
    # lowlighter/metrics uses jq @uri before writing INPUT_EXTRAS_CSS to .env.
    env_line = ("INPUT_EXTRAS_CSS=" + quote(css, safe="") + "\n").encode("utf-8")
    if len(env_line) >= SAFE_ENV_LINE_BYTES:
        raise ValueError(
            f"URL-encoded Docker env line: {len(env_line)} bytes; "
            f"must stay below {SAFE_ENV_LINE_BYTES}. Reduce the embedded font subsets."
        )
    faces = re.findall(r"data:font/woff2;base64,([A-Za-z0-9+/=]+)", css)
    if len(faces) != 2:
        raise ValueError("Expected exactly two embedded WOFF2 faces")
    for face in faces:
        if not base64.b64decode(face, validate=True).startswith(b"wOF2"):
            raise ValueError("Invalid embedded WOFF2 signature")
    for family in ("Ubuntu derivative Metrics Latin", "Plus Jakarta Sans"):
        if family not in css:
            raise ValueError(f"Missing font family: {family}")
    return len(css.encode("utf-8")), len(env_line)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow", nargs="?", type=Path,
                        default=Path(".github/workflows/profile-metrics.yml"))
    args = parser.parse_args()
    try:
        css_bytes, env_bytes = validate(args.workflow)
    except (ValueError, OSError) as error:
        print(f"Embedded font validation failed: {error}", file=sys.stderr)
        sys.exit(1)
    print(f"Two embedded WOFF2 fonts validated: CSS {css_bytes} bytes, "
          f"Docker env line {env_bytes} bytes (< {SAFE_ENV_LINE_BYTES}).")
