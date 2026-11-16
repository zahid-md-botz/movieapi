"""Start the same self-contained Python application locally and on Railway."""
import os
from pathlib import Path
import uvicorn

if __name__ == "__main__":
    if not os.environ.get("RELAY_SECRET"):
        raise SystemExit("Configure RELAY_SECRET before starting the private origin.")
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.environ.get("PORT", "3000")),
                app_dir=str(Path(__file__).resolve().parent), access_log=False)
