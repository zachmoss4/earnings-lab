"""Package only the reviewed app and built assets, never local research or data."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "release/earnings-lab-v0.1.3.zip"
if not (ROOT / "dist/index.html").exists():
    raise SystemExit("Run npm run build first.")
paths = ["earnings_lab", "web", "public", "dist", "docs", "reference", "tests", "scripts",
         "README.md", "CHANGELOG.md", "THIRD_PARTY_NOTICES.md", "launch.py", "Launch.command",
         "requirements.txt", "requirements-tested.txt", "package.json", "package-lock.json", "index.html",
         "tsconfig.json", "vite.config.ts", ".gitignore", ".prettierrc.json"]
OUT.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as archive:
    for item in paths:
        path = ROOT / item
        files = path.rglob("*") if path.is_dir() else [path]
        for file in sorted(files):
            if file.is_file() and "__pycache__" not in file.parts and file.suffix not in [".pyc", ".tmp"]:
                archive.write(file, "earnings-lab/" + file.relative_to(ROOT).as_posix())
print(f"Packaged {OUT.name} ({OUT.stat().st_size:,} bytes)")
