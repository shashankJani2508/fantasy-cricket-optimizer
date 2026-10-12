"""Apply db/migrations/*.sql in order to one Postgres schema, once each.

    python -m db.migrate --schema dev --prepare-dev   # test run on a scratch copy first
    python -m db.migrate --schema public              # the real thing

--prepare-dev copies the two run 1 tables the migrations read (rubric_versions,
bt_player_match_points) into the dev schema, so the test never touches public tables.
"""
import argparse
from pathlib import Path

import psycopg
from psycopg import sql

from engine.env import env

MIGRATIONS = sorted((Path(__file__).parent / "migrations").glob("*.sql"))


def apply(conn, schema):
    conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
    conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
    done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
    for m in MIGRATIONS:
        if m.name in done:
            print(f"[migrate] {schema}: {m.name} already applied")
            continue
        with conn.transaction():
            conn.execute(m.read_text(encoding="utf8"))
            conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (m.name,))
        print(f"[migrate] {schema}: applied {m.name}")
    counts(conn)


def counts(conn):
    bt = conn.execute("SELECT count(*) FROM bt_player_match_points").fetchone()[0]
    pmp = conn.execute("SELECT count(*) FROM player_match_points WHERE source = 'cricsheet'").fetchone()[0]
    print(f"[migrate] bt_player_match_points {bt} rows; player_match_points (cricsheet) {pmp} rows; "
          f"{'MATCH' if bt == pmp else 'MISMATCH'}")
    if bt != pmp:
        raise SystemExit("row counts differ")


def prepare_dev(conn, schema):
    conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
    for t in ("rubric_versions", "bt_player_match_points"):
        exists = conn.execute("SELECT to_regclass(%s)", (f"{schema}.{t}",)).fetchone()[0]
        if not exists:
            conn.execute(sql.SQL("CREATE TABLE {}.{} (LIKE public.{} INCLUDING ALL)").format(
                sql.Identifier(schema), sql.Identifier(t), sql.Identifier(t)))
            conn.execute(sql.SQL("INSERT INTO {}.{} SELECT * FROM public.{}").format(
                sql.Identifier(schema), sql.Identifier(t), sql.Identifier(t)))
            print(f"[migrate] copied public.{t} into {schema}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", required=True)
    ap.add_argument("--prepare-dev", action="store_true")
    a = ap.parse_args()
    if a.schema == "public" and a.prepare_dev:
        raise SystemExit("--prepare-dev is only for a scratch schema")
    with psycopg.connect(env("DATABASE_URL"), autocommit=True) as conn:
        if a.prepare_dev:
            prepare_dev(conn, a.schema)
        apply(conn, a.schema)


if __name__ == "__main__":
    main()
