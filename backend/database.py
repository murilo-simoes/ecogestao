"""Conexões curtas e transações por operação de negócio."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .security import hash_password, verify_password

ROOT = Path(__file__).resolve().parents[1]
DEMO_ACCOUNTS = (
    ('Gestor Demonstração', 'gestor@demo.local', 'gestor'),
    ('Operador Demonstração', 'operador@demo.local', 'operador'),
    ('Consulta Demonstração', 'consulta@demo.local', 'consulta'),
)
DEMO_EMAILS = tuple(email for _, email, _ in DEMO_ACCOUNTS)
FIXED_MANAGER_EMAIL = DEMO_EMAILS[0]
FIXED_MANAGER_PASSWORD = 'Testegestao1'
OPTIONAL_DEMO_EMAILS = DEMO_EMAILS[1:]


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
    """Inicializa o banco e retorna o total de contas opcionais desativadas."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.executescript((ROOT / 'database/schema.sql').read_text(encoding='utf-8'))
        # Bancos anteriores à gestão de contas preservam usuários e seus vínculos.
        if not any(row['name'] == 'active' for row in db.execute('PRAGMA table_info(users)')):
            db.execute('ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))')
        if demo and not db.execute('SELECT 1 FROM users').fetchone():
            for name, email, role in DEMO_ACCOUNTS:
                password = FIXED_MANAGER_PASSWORD if email == FIXED_MANAGER_EMAIL else 'EcoDemo2026!'
                db.execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)',
                           (name, email, hash_password(password), role))
            db.executescript((ROOT / 'database/seed.sql').read_text(encoding='utf-8'))

        if not db.in_transaction:
            db.execute('BEGIN IMMEDIATE')
        # Recuperar o mesmo cadastro conserva os vínculos de registros e ações antigos.
        manager = db.execute('SELECT * FROM users WHERE email=? COLLATE NOCASE ORDER BY email=? DESC,id LIMIT 1',
                             (FIXED_MANAGER_EMAIL, FIXED_MANAGER_EMAIL)).fetchone()
        if manager is None:
            db.execute('INSERT INTO users(name,email,password_hash,role,active) VALUES(?,?,?,?,1)',
                       (DEMO_ACCOUNTS[0][0], FIXED_MANAGER_EMAIL, hash_password(FIXED_MANAGER_PASSWORD), 'gestor'))
        else:
            try:
                password_matches = verify_password(FIXED_MANAGER_PASSWORD, manager['password_hash'])
            except ValueError:
                password_matches = False
            if not password_matches or not manager['active'] or manager['role'] != 'gestor' or manager['email'] != FIXED_MANAGER_EMAIL:
                password_hash = manager['password_hash'] if password_matches else hash_password(FIXED_MANAGER_PASSWORD)
                db.execute("UPDATE users SET email=?,password_hash=?,role='gestor',active=1 WHERE id=?",
                           (FIXED_MANAGER_EMAIL, password_hash, manager['id']))
                db.execute('DELETE FROM sessions WHERE user_id=?', (manager['id'],))

        disabled = 0
        if not demo:
            disabled = db.execute('UPDATE users SET active=0 WHERE email IN (?,?) AND active=1',
                                  OPTIONAL_DEMO_EMAILS).rowcount
            db.execute('DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE email IN (?,?))',
                       OPTIONAL_DEMO_EMAILS)
        # A etiqueta acompanha os registros fictícios mesmo após trocar as contas.
        if db.execute('SELECT 1 FROM records r JOIN users u ON u.id=r.created_by WHERE u.email IN (?,?) LIMIT 1',
                      OPTIONAL_DEMO_EMAILS).fetchone():
            db.execute("INSERT OR IGNORE INTO app_settings(key,value) VALUES('demo_data','1')")
        return disabled


def audit(db, user_id, operation, entity, entity_id, before=None, after=None):
    db.execute('INSERT INTO audit(user_id,timestamp,operation,entity,entity_id,before_json,after_json) '
               'VALUES(?,?,?,?,?,?,?)',
               (user_id, datetime.now(timezone.utc).isoformat(), operation, entity, entity_id,
                json.dumps(before, ensure_ascii=False) if before else None,
                json.dumps(after, ensure_ascii=False) if after else None))
