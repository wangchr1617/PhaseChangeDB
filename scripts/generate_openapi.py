import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

OUT_PATH = ROOT / "app" / "api" / "openapi.json"


def main():
    schema = app.openapi()
    content = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
    OUT_PATH.write_text(content, encoding="utf-8")
    print(f"Generated {OUT_PATH} ({len(content)} bytes)")


if __name__ == "__main__":
    main()
