"""Conexões curtas e transações por operação de negócio."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .security import hash_password

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def connect(path):
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize(path, demo=False):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.executescript((ROOT / 'database/schema.sql').read_text(encoding='utf-8'))
        if demo and not db.execute('SELECT 1 FROM users').fetchone():
            for name, email, role in [
                ('Gestor Demonstração', 'gestor@demo.local', 'gestor'),
                ('Operador Demonstração', 'operador@demo.local', 'operador'),
                ('Consulta Demonstração', 'consulta@demo.local', 'consulta'),
            ]:
                db.execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)',
                           (name, email, hash_password('EcoDemo2026!'), role))
            db.executescript((ROOT / 'database/seed.sql').read_text(encoding='utf-8'))


def audit(db, user_id, operation, entity, entity_id, before=None, after=None):
    db.execute('INSERT INTO audit(user_id,timestamp,operation,entity,entity_id,before_json,after_json) '
               'VALUES(?,?,?,?,?,?,?)',
               (user_id, datetime.now(timezone.utc).isoformat(), operation, entity, entity_id,
                json.dumps(before, ensure_ascii=False) if before else None,
                json.dumps(after, ensure_ascii=False) if after else None))
