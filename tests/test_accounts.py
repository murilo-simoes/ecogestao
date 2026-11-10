"""Contas próprias, migração e revogação de acesso."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.database import connect, initialize
from backend.main import create_app
from backend.security import hash_password
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
    assert identifier > 3 and disabled == 2
    with TestClient(create_app(path, demo=False)) as client:
        assert signin(client, 'gestor@demo.local', 'EcoDemo2026!').status_code == 401
        assert signin(client, 'gestor@demo.local', 'Testegestao1').status_code == 200
        signed_in = signin(client, 'real@exemplo.com', 'senha longa e exclusiva 2026')
        assert signed_in.status_code == 200 and signed_in.json()['demo'] is True
        assert len(client.get('/api/records').json()) == records_before
        users = client.get('/api/admin/users').json()
        assert len([u for u in users if u['active']]) == 2
        assert all('password' not in u for u in users)
        demo_user = next(u for u in users if u['email'] == 'operador@demo.local')
        reactivation = {k: demo_user[k] for k in ('name', 'email', 'role')}
        reactivation['active'] = True
        assert client.put(f'/api/admin/users/{demo_user["id"]}', json=reactivation).status_code == 422
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


@pytest.mark.parametrize('demo', [False, True])
def test_fixed_manager_is_available_after_start_and_restart(tmp_path, demo):
    path = tmp_path / 'fixed.db'
    for _ in range(2):
        with TestClient(create_app(path, demo=demo)) as client:
            response = signin(client, 'gestor@demo.local', 'Testegestao1')
            assert response.status_code == 200 and response.json()['role'] == 'gestor'
            assert client.get('/api/admin/users').status_code == 200


def test_normal_mode_rejects_reserved_addresses_before_restart(tmp_path):
    path = tmp_path / 'reserved.db'
    email, password = 'gestor@exemplo.com', 'senha inicial longa 2026'
    identifier, _ = create_first_manager(path, 'Gestor', email, password)
    with TestClient(create_app(path, demo=False)) as client:
        assert signin(client, email, password).status_code == 200
        create = {'name': 'Outra conta', 'email': 'OPERADOR@demo.local',
                  'role': 'operador', 'password': 'senha longa para teste'}
        assert client.post('/api/admin/users', json=create).status_code == 422
        edit = {'name': 'Gestor', 'email': 'operador@demo.local', 'role': 'gestor', 'active': True}
        assert client.put(f'/api/admin/users/{identifier}', json=edit).status_code == 422

    with TestClient(create_app(path, demo=False)) as client:
        assert signin(client, email, password).status_code == 200
        assert len(client.get('/api/admin/users').json()) == 2


def test_fixed_manager_recovers_legacy_account_without_losing_records(tmp_path):
    path = tmp_path / 'legacy-demo.db'
    initialize(path, demo=True)
    with TestClient(create_app(path, demo=True)) as client:
        assert signin(client, 'gestor@demo.local', 'Testegestao1').status_code == 200
        old_cookie = client.cookies.get('ecogestao_session')
        records = client.get('/api/records').json()
    with connect(path) as db:
        db.execute("UPDATE users SET email='GESTOR@DEMO.LOCAL',active=0,role='consulta',password_hash=? WHERE id=1",
                   (hash_password('senha antiga de demonstração'),))

    with TestClient(create_app(path, demo=False)) as client:
        assert client.get('/api/auth/me', headers={'Cookie': f'ecogestao_session={old_cookie}'}).status_code == 401
        assert signin(client, 'gestor@demo.local', 'senha antiga de demonstração').status_code == 401
        response = signin(client, 'gestor@demo.local', 'Testegestao1')
        assert response.status_code == 200 and response.json()['id'] == 1
        assert client.get('/api/records').json() == records
        session = client.cookies.get('ecogestao_session')
        with connect(path) as db:
            original_hash = db.execute('SELECT password_hash FROM users WHERE id=1').fetchone()[0]
        initialize(path, demo=False)
        assert client.get('/api/auth/me').status_code == 200
        assert client.cookies.get('ecogestao_session') == session
        with connect(path) as db:
            assert db.execute('SELECT password_hash FROM users WHERE id=1').fetchone()[0] == original_hash


def test_fixed_manager_access_cannot_be_changed_by_account_management(tmp_path):
    path = tmp_path / 'fixed-guard.db'
    create_first_manager(path, 'Gestor próprio', 'gestor@exemplo.com', 'senha inicial longa 2026')
    with TestClient(create_app(path, demo=False)) as client:
        assert signin(client, 'gestor@demo.local', 'Testegestao1').status_code == 200
        identifier = client.get('/api/auth/me').json()['id']
        assert client.post('/api/auth/password', json={
            'current_password': 'Testegestao1', 'new_password': 'outra senha para teste'}).status_code == 409
        assert signin(client, 'gestor@exemplo.com', 'senha inicial longa 2026').status_code == 200
        account = {'name': 'Gestor fixo', 'email': 'gestor@demo.local', 'role': 'gestor', 'active': True}
        endpoint = f'/api/admin/users/{identifier}'
        for changes in [{'email': 'outro@exemplo.com'}, {'role': 'consulta'}, {'active': False}]:
            assert client.put(endpoint, json={**account, **changes}).status_code == 409
        assert client.post(endpoint+'/password', json={'new_password': 'outra senha para teste'}).status_code == 409
        assert signin(client, 'gestor@demo.local', 'Testegestao1').status_code == 200


def test_fixed_manager_normal_records_keep_their_original_data_label(tmp_path):
    path = tmp_path / 'normal-records.db'
    with TestClient(create_app(path, demo=False)) as client:
        assert signin(client, 'gestor@demo.local', 'Testegestao1').status_code == 200
        sector = client.post('/api/sectors', json={'name': 'Setor próprio'}).json()
        assert client.post('/api/records', json={
            'metric': 'agua', 'date': '2026-01-10', 'quantity': 5, 'sector_id': sector['id']}).status_code == 201
    with TestClient(create_app(path, demo=False)) as client:
        response = signin(client, 'gestor@demo.local', 'Testegestao1')
        assert response.status_code == 200 and response.json()['demo'] is False
        assert len(client.get('/api/records').json()) == 1
