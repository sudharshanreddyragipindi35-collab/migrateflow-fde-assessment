"""Tests never use the developer's database, uploads or hosted model credentials."""
import os
import tempfile
from pathlib import Path

test_root = Path(tempfile.mkdtemp(prefix="migrateflow-tests-"))
os.environ["DATABASE_URL"] = "sqlite:///" + (test_root / "test.db").as_posix()
os.environ["UPLOAD_ROOT"] = str(test_root / "uploads")
os.environ["MODEL_MODE"] = "fallback"
os.environ["ANTHROPIC_API_KEY"] = ""
