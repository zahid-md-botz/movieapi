"""Create a clean deliverable and inventory without shipping local keys/caches."""
import hashlib
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parent
workspace = root.parent
original = workspace / "attached_assets/0_movieapi_1794822500764.zip"
output = workspace / "generated-artifacts"
output.mkdir(exist_ok=True)
inventory = []
with zipfile.ZipFile(original) as source:
    for item in source.infolist():
        if item.is_dir():
            inventory.append({"path": item.filename, "kind": "directory"})
            continue
        data = source.read(item)
        private = item.filename.startswith((".data/", ".wrangler/"))
        row = {"path": item.filename, "bytes": len(data),
               "sha256": hashlib.sha256(data).hexdigest(),
               "handling": "excluded local runtime state; original retained" if private else "source inspected"}
        if not private:
            text = data.decode("utf-8")
            if item.filename.endswith(".json"):
                json.loads(text)
                row["jsonValid"] = True
            current = root / item.filename
            canonical = root / "public" / item.filename
            if canonical.is_file() and current.is_file() and current.read_bytes() == canonical.read_bytes():
                row["handling"] = "deduplicated to public/" + item.filename
            elif current.is_file():
                row["changed"] = current.read_bytes() != data
        inventory.append(row)

(root / "SOURCE-INVENTORY.json").write_text(json.dumps(inventory, indent=2) + "\n")
target = output / "movieapi-railway-cloudflare.zip"
excluded = {"node_modules", ".data", ".wrangler", "__pycache__", ".git"}
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
    for file in sorted(root.rglob("*")):
        rel = file.relative_to(root)
        if not file.is_file() or any(p in excluded for p in rel.parts):
            continue
        if file.name.startswith((".env", ".dev.vars")) or file.suffix == ".pyc":
            continue
        if len(rel.parts) == 1:
            canonical = root / "public" / file.name
            if canonical.is_file() and file.read_bytes() == canonical.read_bytes():
                continue
        archive.write(file, "movieapi/" + rel.as_posix())
    for file in sorted((workspace / "provider-reference").glob("*")):
        if file.is_file():
            archive.write(file, "movieapi/provider-reference/" + file.name)
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    for needed in ["python-origin/engine.py", "python-origin/curl_transport.py",
                   "python-origin/Dockerfile", "DEPLOYMENT-GUIDE.md", "runtime-worker.js", "public/index.html"]:
        assert "movieapi/" + needed in archive.namelist()
print(f"Created {target.name}: {target.stat().st_size} bytes")
