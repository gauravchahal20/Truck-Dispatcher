import os
import sys
from pathlib import Path
import pytest

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Configure isolated test database
test_db_path = backend_dir / "test_trucklead.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{test_db_path.as_posix()}"

@pytest.fixture(scope="session", autouse=True)
def clean_test_db():
    # Teardown after test session
    yield
    if test_db_path.exists():
        try:
            test_db_path.unlink()
        except Exception:
            pass
