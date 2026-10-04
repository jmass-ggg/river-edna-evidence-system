import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import Integer
from sqlalchemy.dialects import postgresql

from app.db.models import ArrayType


def test_alembic_accepts_percent_encoded_database_credentials():
    backend_dir = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["DATABASE_URL"] = (
        "postgresql://example_user:example%40password@localhost/example_database"
    )

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=backend_dir,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "d4c8e1a907b2" in result.stdout


def test_array_type_matches_postgresql_array_schema():
    column_type = ArrayType(Integer())
    dialect = postgresql.dialect()

    assert isinstance(column_type.load_dialect_impl(dialect), postgresql.ARRAY)
    assert column_type.process_bind_param([1, 2, 3], dialect) == [1, 2, 3]
