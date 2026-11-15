"""Create, exercise, and remove two temporary PostgreSQL recovery databases."""

import os
from pathlib import Path
import subprocess
import sys
import uuid

import psycopg
from psycopg import sql


def main():
    prefix = "pdc_rehearsal_" + uuid.uuid4().hex[:12]
    names = [prefix + "_source", prefix + "_restored"]
    with psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ.get("POSTGRES_PORT", "5432"),
        user=os.environ["POSTGRES_USER"],
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        dbname="postgres",
        autocommit=True,
    ) as admin:
        created = []
        try:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            env = dict(
                os.environ,
                REHEARSAL_USE_POSTGRES="1",
                REHEARSAL_SOURCE_DB=names[0],
                REHEARSAL_TARGET_DB=names[1],
            )
            subprocess.run(
                [sys.executable, "scripts/rehearse_recovery.py"],
                cwd=Path(__file__).resolve().parent.parent,
                env=env,
                check=True,
            )
        finally:
            for name in created:
                assert name in names and name.startswith(prefix)
                admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
