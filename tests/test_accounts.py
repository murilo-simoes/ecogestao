"""Contas próprias, migração e revogação de acesso."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.database import connect, initialize
from backend.main import create_app
from manage_users import create_first_manager


def signin(client, email, password):
    response = client.post('/api/auth/login', json={'email': email, 'password': password})
    if response.status_code == 200:
        client.headers['X-CSRF-Token'] = response.json()['csrf']
    return response


def test_bootstrap_preserves_existing_data_and_disables_demo_accounts(tmp_path):
    path = tmp_path / 'existing.db'
    initialize(path, demo=True)
    with connect(path) as db:
        records_before = db.execute('SELECT COUNT(*) FROM records').fetchone()[0]
    identifier, disabled = create_first_manager(path, 'Gestora Real', 'REAL@exemplo.com', 'senha longa e exclusiva 2026')
    assert identifier > 3 and disabled == 3
    with TestClient(create_app(path, demo=False)) as client:
        assert signin(client, 'gestor@demo.local', 'EcoDemo2026!').status_code == 401
        signed_in = signin(client, 'real@exemplo.com', 'senha longa e exclusiva 2026')
        assert signed_in.status_code == 200 and signed_in.json()['demo'] is True
        assert len(client.get('/api/records').json()) == records_before
        users = client.get('/api/admin/users').json()
        assert len([u for u in users if u['active']]) == 1
        assert all('password' not in u for u in users)
    with pytest.raises(ValueError, match='Já existe'):
        create_first_manager(path, 'Outra', 'outra@exemplo.com', 'outra senha longa 2026')


def test_manager_controls_accounts_and_reset_revokes_session(tmp_path):
    path = tmp_path / 'fresh.db'
    create_first_manager(path, 'Gestor', 'gestor@exemplo.com', 'senha inicial longa 2026')
    app = create_app(path, demo=False)
    with TestClient(app) as manager, TestClient(app) as operator:
        signed_in = signin(manager, 'gestor@exemplo.com', 'senha inicial longa 2026')
        assert signed_in.status_code == 200 and signed_in.json()['demo'] is False
        created = manager.post('/api/admin/users', json={'name':'Operadora','email':'OPERADORA@exemplo.com','role':'operador','password':'senha da operadora 2026'})
        assert created.status_code == 201
        user = created.json()
        assert user['email'] == 'operadora@exemplo.com' and 'password' not in user
        assert signin(operator, user['email'], 'senha da operadora 2026').status_code == 200
        assert operator.get('/api/admin/users').status_code == 403
        assert manager.post('/api/admin/users', json={'name':'Outra','email':user['email'],'role':'consulta','password':'senha bem comprida'}).status_code == 409
        assert manager.post('/api/admin/users', json={'name':'Outra','email':'outra@exemplo.com','role':'consulta','password':'EcoDemo2026!'}).status_code == 422
        assert manager.post(f'/api/admin/users/{user["id"]}/password', json={'new_password':'nova senha da operadora 2026'}).status_code == 204
        assert operator.get('/api/auth/me').status_code == 401
        assert signin(operator, user['email'], 'senha da operadora 2026').status_code == 401
        assert signin(operator, user['email'], 'nova senha da operadora 2026').status_code == 200
        changed = manager.put(f'/api/admin/users/{user["id"]}', json={'name':'Operadora','email':user['email'],'role':'consulta','active':False})
        assert changed.status_code == 200
        assert operator.get('/api/auth/me').status_code == 401
        assert signin(operator, user['email'], 'nova senha da operadora 2026').status_code == 401
        assert all(u['id'] != user['id'] for u in manager.get('/api/users').json())
        assert manager.put(f'/api/admin/users/{user["id"]}', json={'name':'Operadora','email':user['email'],'role':'operador','active':True}).status_code == 200
        assert signin(operator, user['email'], 'nova senha da operadora 2026').status_code == 200
        audit = manager.get('/api/audit').text
        assert 'senha da operadora' not in audit and 'password_hash' not in audit


def test_password_change_and_last_manager_guards(tmp_path):
    path = tmp_path / 'password.db'
    create_first_manager(path, 'Gestor', 'gestor@exemplo.com', 'senha inicial longa 2026')
    app = create_app(path, demo=False)
    with TestClient(app) as first, TestClient(app) as second:
        assert signin(first, 'gestor@exemplo.com', 'senha inicial longa 2026').status_code == 200
        assert signin(second, 'gestor@exemplo.com', 'senha inicial longa 2026').status_code == 200
        own_id = first.get('/api/auth/me').json()['id']
        payload = {'name':'Gestor','email':'gestor@exemplo.com','role':'consulta','active':True}
        assert first.put(f'/api/admin/users/{own_id}', json=payload).status_code == 409
        payload['role'] = 'gestor'; payload['active'] = False
        assert first.put(f'/api/admin/users/{own_id}', json=payload).status_code == 409
        assert first.post('/api/auth/password', json={'current_password':'errada','new_password':'nova senha bem longa 2026'}).status_code == 403
        assert first.post('/api/auth/password', json={'current_password':'senha inicial longa 2026','new_password':'curta'}).status_code == 422
        assert first.post('/api/auth/password', json={'current_password':'senha inicial longa 2026','new_password':'nova senha bem longa 2026'}).status_code == 204
        assert first.get('/api/auth/me').status_code == 200
        assert second.get('/api/auth/me').status_code == 401
        assert signin(second, 'gestor@exemplo.com', 'senha inicial longa 2026').status_code == 401
        assert signin(second, 'gestor@exemplo.com', 'nova senha bem longa 2026').status_code == 200


def test_legacy_users_table_gets_active_column(tmp_path):
    path = tmp_path / 'legacy.db'
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('gestor','operador','consulta')))")
    initialize(path, demo=False)
    with connect(path) as db:
        assert 'active' in [row['name'] for row in db.execute('PRAGMA table_info(users)')]


def test_normal_mode_requires_bootstrap(tmp_path):
    with pytest.raises(RuntimeError, match='Nenhum gestor ativo'):
        with TestClient(create_app(tmp_path / 'empty.db', demo=False)):
            pass
