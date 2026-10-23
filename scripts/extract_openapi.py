"""Extract the Personal API OpenAPI document from Garmin's Swagger docs page.

Garmin does not publish the spec as a file. The docs page at
https://developer.garmin.com/gc-developer-program/personal/swagger-docs/ is a Gatsby site
whose page bundle embeds the spec as a `JSON.parse('...')` string literal.

Usage:
    curl -sL https://developer.garmin.com/gc-developer-program/personal/swagger-docs/ \
        | grep -oE 'component---[a-z-]+-personal-swagger-docs-js-[0-9a-f]+\\.js' | head -1
    curl -sL https://developer.garmin.com/<that file> -o bundle.js
    python3 -I scripts/extract_openapi.py bundle.js openapi.json

The spec is Garmin's documentation. Keep the output out of this repository.
"""

import json
from pathlib import Path
import re
import sys


def extract(bundle: str) -> dict[str, object]:
    for match in re.finditer(r"JSON\.parse\('", bundle):
        start = end = match.end()
        while True:
            end = bundle.index("'", end)
            if bundle[end - 1] != "\\":
                break
            end += 1
        literal = bundle[start:end]
        if '"openapi"' not in literal[:200]:
            continue
        text = literal.replace("\\'", "'").replace("\\\\", "\\")
        spec: dict[str, object] = json.loads(text)
        return spec
    raise SystemExit("No embedded OpenAPI document found")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    spec = extract(Path(sys.argv[1]).read_text(encoding="utf-8"))
    Path(sys.argv[2]).write_text(json.dumps(spec, indent=2), encoding="utf-8")
    info = spec.get("info", {})
    paths = spec.get("paths", {})
    print(f"{info} with {len(paths) if isinstance(paths, dict) else '?'} paths")


if __name__ == "__main__":
    main()
