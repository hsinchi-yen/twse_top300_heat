import atexit
import os
import tempfile

# Use a temp file-based SQLite so all connections share the same database.
# Must be set before main.py is imported (which creates the engine).
_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db_file.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file.name}"

atexit.register(os.unlink, _db_file.name)
