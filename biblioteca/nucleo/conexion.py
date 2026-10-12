"""
CAPA 1 · CONEXIÓN — acceso a PostgreSQL (Neon).

Solo sabe abrir y cerrar conexiones. No contiene SQL de negocio ni reglas.
"""
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from nucleo.configuracion import DATABASE_URL


class _PGConn:
    """
    Envoltorio delgado sobre una conexión psycopg para poder seguir escribiendo
    conn.execute(sql, params).fetchone() / .fetchall(), igual que con sqlite3.
    """
    __slots__ = ("_conn",)

    def __init__(self, raw_conn):
        self._conn = raw_conn

    def execute(self, sql: str, params=()):
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


@contextmanager
def get_conn():
    """Abre una conexión; hace commit si todo sale bien y rollback si algo falla."""
    raw = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    conn = _PGConn(raw)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
