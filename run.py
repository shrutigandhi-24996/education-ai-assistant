"""Start the Education assistant API.

Locally: http://127.0.0.1:8001
On cloud (Render / HF Spaces / Railway): host/port come from $HOST and $PORT.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import uvicorn

from backend.app.config import settings

if __name__ == "__main__":
    host = os.environ.get("HOST", settings.host)
    port = int(os.environ.get("PORT", settings.port))
    uvicorn.run("backend.app.main:app", host=host, port=port, reload=False)
