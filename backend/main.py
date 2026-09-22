"""Servidor HTTP e contratos da aplicação EcoGestão."""
import csv
import io
import os
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .database import ROOT, audit, connect, initialize
from .schemas import AccountCreate, AccountUpdate, Action, Goal, Login, Partner, PasswordChange, PasswordReset, Record, Sector
from .security import hash_password, token_hash, verify_password
from .services import goal_results, list_records, period_filter, remove, save


def create_app(db_path=None, demo=None):
    demo = os.environ.get('ECOGESTAO_DEMO') == '1' if demo is None else demo
    path = str(db_path or os.environ.get('ECOGESTAO_DB', ROOT / 'data/ecogestao.db'))

    @asynccontextmanager
    async def lifespan(app):
        initialize(path, demo)
        with connect(path) as db:
            app.state.demo_data = bool(db.execute("SELECT 1 FROM app_settings WHERE key='demo_data' AND value='1'").fetchone())
        if not demo:
            with connect(path) as db:
                if db.execute("SELECT 1 FROM users WHERE active=1 AND email IN ('gestor@demo.local','operador@demo.local','consulta@demo.local')").fetchone():
                    raise RuntimeError('Contas públicas de demonstração ainda estão ativas. Execute manage_users.py para criar o gestor e desativá-las.')
                if not db.execute("SELECT 1 FROM users WHERE role='gestor' AND active=1").fetchone():
                    raise RuntimeError('Nenhum gestor ativo. Execute manage_users.py antes de iniciar o servidor.')
        yield

    app = FastAPI(title='EcoGestão API', version='1.0.0', lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url='/api/openapi.json',
                  description='Serviços HTTP de gestão ambiental.')
    app.state.db_path = path
    failures = {}

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Não devolver input recebido, especialmente em erros de autenticação.
        messages = ['.'.join(str(x) for x in e['loc'][1:])+': '+e['msg'].removeprefix('Value error, ') for e in error.errors()]
        return JSONResponse(status_code=422, content={'detail': '; '.join(messages)})

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(request, error):
        return JSONResponse(status_code=409, content={'detail': 'Conflito de dados: verifique nomes repetidos e vínculos obrigatórios.'})

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request, error):
        return JSONResponse(status_code=503, content={'detail': 'Banco de dados indisponível. Tente novamente.'})

    @app.middleware('http')
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
        if request.url.path.startswith('/api/') or request.url.path == '/':
            response.headers['Cache-Control'] = 'no-store'
        return response

    def current_user(request: Request):
        token = request.cookies.get('ecogestao_session', '')
        with connect(path) as db:
            row = db.execute('SELECT u.id,u.name,u.email,u.role,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id '
                             'WHERE s.token_hash=? AND s.expires_at>? AND u.active=1', (token_hash(token), time.time())).fetchone()
        if not row:
            raise HTTPException(401, 'Sessão inválida ou expirada. Entre novamente.')
        user = dict(row)
        if request.method not in {'GET', 'HEAD', 'OPTIONS'} and not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), user['csrf']):
            raise HTTPException(403, 'Token de proteção da sessão inválido.')
        return user

    def writer(user=Depends(current_user)):
        if user['role'] == 'consulta':
            raise HTTPException(403, 'Este perfil permite somente consulta.')
        return user

    def manager(user=Depends(current_user)):
        if user['role'] != 'gestor':
            raise HTTPException(403, 'Operação exclusiva do gestor.')
        return user

    @app.post('/api/auth/login', tags=['Sessão'])
    def login(payload: Login, request: Request, response: Response):
        key = request.client.host if request.client else 'local'
        recent = [t for t in failures.get(key, []) if time.time()-t < 60]
        if len(recent) >= 10:
            raise HTTPException(429, 'Muitas tentativas. Aguarde um minuto.')
        with connect(path) as db:
            user = db.execute('SELECT * FROM users WHERE email=?', (payload.email.lower(),)).fetchone()
            if not user or not user['active'] or not verify_password(payload.password, user['password_hash']):
                failures[key] = recent+[time.time()]
                raise HTTPException(401, 'E-mail ou senha incorretos.')
            failures.pop(key, None)
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            db.execute('DELETE FROM sessions WHERE expires_at<=?', (time.time(),))
            old_token = request.cookies.get('ecogestao_session')
            if old_token:
                db.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash(old_token),))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)', (token_hash(token), user['id'], csrf, time.time()+28800))
        response.set_cookie('ecogestao_session', token, max_age=28800, httponly=True,
                            samesite='strict', secure=os.environ.get('ECOGESTAO_HTTPS') == '1')
        return {'id': user['id'], 'name': user['name'], 'role': user['role'], 'csrf': csrf, 'demo': app.state.demo_data}

    @app.get('/api/auth/me', tags=['Sessão'])
    def me(user=Depends(current_user)):
        return {**user, 'demo': app.state.demo_data}

    @app.post('/api/auth/logout', status_code=204, tags=['Sessão'])
    def logout(request: Request, response: Response, user=Depends(current_user)):
        with connect(path) as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash(request.cookies['ecogestao_session']),))
        response.delete_cookie('ecogestao_session')

    @app.post('/api/auth/password', status_code=204, tags=['Sessão'])
    def change_password(payload: PasswordChange, request: Request, user=Depends(current_user)):
        with connect(path) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT password_hash FROM users WHERE id=?', (user['id'],)).fetchone()
            if not verify_password(payload.current_password, row['password_hash']):
                raise HTTPException(403, 'Senha atual incorreta.')
            if verify_password(payload.new_password, row['password_hash']):
                raise HTTPException(422, 'A nova senha deve ser diferente da atual.')
            db.execute('UPDATE users SET password_hash=? WHERE id=?', (hash_password(payload.new_password), user['id']))
            db.execute('DELETE FROM sessions WHERE user_id=? AND token_hash<>?',
                       (user['id'], token_hash(request.cookies['ecogestao_session'])))
            audit(db, user['id'], 'alterar_senha', 'users', user['id'])

    @app.get('/api/users', tags=['Cadastros'])
    def users(user=Depends(current_user)):
        with connect(path) as db:
            return [dict(r) for r in db.execute('SELECT id,name,role FROM users WHERE active=1 ORDER BY name')]

    @app.get('/api/admin/users', tags=['Contas'])
    def managed_users(user=Depends(manager)):
        with connect(path) as db:
            return [dict(r) for r in db.execute('SELECT id,name,email,role,active FROM users ORDER BY name')]

    @app.post('/api/admin/users', status_code=201, tags=['Contas'])
    def create_user(payload: AccountCreate, user=Depends(manager)):
        with connect(path) as db:
            cursor = db.execute('INSERT INTO users(name,email,password_hash,role,active) VALUES(?,?,?,?,1)',
                                (payload.name, payload.email, hash_password(payload.password), payload.role))
            result = dict(db.execute('SELECT id,name,email,role,active FROM users WHERE id=?',
                                     (cursor.lastrowid,)).fetchone())
            audit(db, user['id'], 'criar', 'users', result['id'], after=result)
            return result

    @app.put('/api/admin/users/{identifier}', tags=['Contas'])
    def update_user(identifier: int, payload: AccountUpdate, user=Depends(manager)):
        with connect(path) as db:
            db.execute('BEGIN IMMEDIATE')
            before_row = db.execute('SELECT id,name,email,role,active FROM users WHERE id=?', (identifier,)).fetchone()
            if not before_row:
                raise HTTPException(404, 'Conta não encontrada.')
            before = dict(before_row)
            if identifier == user['id'] and (payload.role != 'gestor' or not payload.active):
                raise HTTPException(409, 'O gestor não pode remover o próprio acesso.')
            if before['role'] == 'gestor' and before['active'] and (payload.role != 'gestor' or not payload.active):
                remaining = db.execute("SELECT COUNT(*) FROM users WHERE role='gestor' AND active=1 AND id<>?", (identifier,)).fetchone()[0]
                if not remaining:
                    raise HTTPException(409, 'É necessário manter ao menos um gestor ativo.')
            db.execute('UPDATE users SET name=?,email=?,role=?,active=? WHERE id=?',
                       (payload.name, payload.email, payload.role, int(payload.active), identifier))
            if before['role'] != payload.role or not payload.active:
                db.execute('DELETE FROM sessions WHERE user_id=?', (identifier,))
            result = dict(db.execute('SELECT id,name,email,role,active FROM users WHERE id=?', (identifier,)).fetchone())
            audit(db, user['id'], 'alterar', 'users', identifier, before, result)
            return result

    @app.post('/api/admin/users/{identifier}/password', status_code=204, tags=['Contas'])
    def reset_user_password(identifier: int, payload: PasswordReset, user=Depends(manager)):
        if identifier == user['id']:
            raise HTTPException(409, 'Use a troca de senha da própria conta.')
        with connect(path) as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM users WHERE id=?', (identifier,)).fetchone():
                raise HTTPException(404, 'Conta não encontrada.')
            db.execute('UPDATE users SET password_hash=? WHERE id=?', (hash_password(payload.new_password), identifier))
            db.execute('DELETE FROM sessions WHERE user_id=?', (identifier,))
            audit(db, user['id'], 'redefinir_senha', 'users', identifier)

    @app.get('/api/sectors', tags=['Cadastros'])
    def sectors(user=Depends(current_user)):
        with connect(path) as db:
            return [dict(r) for r in db.execute('SELECT * FROM sectors ORDER BY name')]

    @app.post('/api/sectors', status_code=201, tags=['Cadastros'])
    def create_sector(payload: Sector, user=Depends(manager)):
        with connect(path) as db:
            return save(db, 'sectors', payload, user)

    @app.put('/api/sectors/{identifier}', tags=['Cadastros'])
    def update_sector(identifier: int, payload: Sector, user=Depends(manager)):
        with connect(path) as db:
            return save(db, 'sectors', payload, user, identifier)

    @app.get('/api/partners', tags=['Cadastros'])
    def partners(user=Depends(current_user)):
        with connect(path) as db:
            return [dict(r) for r in db.execute('SELECT * FROM partners ORDER BY name')]

    @app.post('/api/partners', status_code=201, tags=['Cadastros'])
    def create_partner(payload: Partner, user=Depends(manager)):
        with connect(path) as db:
            return save(db, 'partners', payload, user)

    @app.put('/api/partners/{identifier}', tags=['Cadastros'])
    def update_partner(identifier: int, payload: Partner, user=Depends(manager)):
        with connect(path) as db:
            return save(db, 'partners', payload, user, identifier)

    @app.get('/api/records', tags=['Registros'])
    def records(start: date | None = None, end: date | None = None, sector_id: int | None = None, user=Depends(current_user)):
        with connect(path) as db:
            return list_records(db, start, end, sector_id)

    @app.post('/api/records', status_code=201, tags=['Registros'])
    def create_record(payload: Record, user=Depends(writer)):
        with connect(path) as db:
            return save(db, 'records', payload, user)

    @app.put('/api/records/{identifier}', tags=['Registros'])
    def update_record(identifier: int, payload: Record, user=Depends(writer)):
        with connect(path) as db:
            return save(db, 'records', payload, user, identifier)

    @app.delete('/api/records/{identifier}', status_code=204, tags=['Registros'])
    def delete_record(identifier: int, user=Depends(manager)):
        with connect(path) as db:
            remove(db, 'records', identifier, user)

    @app.get('/api/goals', tags=['Metas'])
    def goals(user=Depends(current_user)):
        with connect(path) as db:
            return goal_results(db)

    @app.post('/api/goals', status_code=201, tags=['Metas'])
    def create_goal(payload: Goal, user=Depends(manager)):
        with connect(path) as db:
            return save(db, 'goals', payload, user)

    @app.put('/api/goals/{identifier}', tags=['Metas'])
    def update_goal(identifier: int, payload: Goal, user=Depends(manager)):
        with connect(path) as db:
            return save(db, 'goals', payload, user, identifier)

    @app.delete('/api/goals/{identifier}', status_code=204, tags=['Metas'])
    def delete_goal(identifier: int, user=Depends(manager)):
        with connect(path) as db:
            remove(db, 'goals', identifier, user)

    @app.get('/api/actions', tags=['Ações'])
    def actions(user=Depends(current_user)):
        with connect(path) as db:
            return [dict(r) for r in db.execute('SELECT a.*,s.name sector_name,u.name owner_name FROM actions a '
                'JOIN sectors s ON s.id=a.sector_id JOIN users u ON u.id=a.owner_id ORDER BY a.due_date,a.id')]

    @app.post('/api/actions', status_code=201, tags=['Ações'])
    def create_action(payload: Action, user=Depends(writer)):
        with connect(path) as db:
            return save(db, 'actions', payload, user)

    @app.put('/api/actions/{identifier}', tags=['Ações'])
    def update_action(identifier: int, payload: Action, user=Depends(writer)):
        with connect(path) as db:
            return save(db, 'actions', payload, user, identifier)

    @app.delete('/api/actions/{identifier}', status_code=204, tags=['Ações'])
    def delete_action(identifier: int, user=Depends(manager)):
        with connect(path) as db:
            remove(db, 'actions', identifier, user)

    @app.get('/api/dashboard', tags=['Relatórios'])
    def dashboard(start: date | None = None, end: date | None = None, sector_id: int | None = None, user=Depends(current_user)):
        with connect(path) as db:
            rows = list_records(db, start, end, sector_id)
            totals = {}
            for metric in ['agua', 'energia', 'residuos']:
                values = [r['quantity'] for r in rows if r['metric'] == metric]
                totals[metric] = {'count': len(values), 'total': round(sum(values), 3) if values else None}
            where, args = (' WHERE sector_id=?', [sector_id]) if sector_id else ('', [])
            actions = [dict(r) for r in db.execute('SELECT * FROM actions'+where, args)]
            return {'totals': totals, 'record_count': len(rows),
                    'open_actions': sum(a['status'] != 'concluida' for a in actions),
                    'overdue_actions': sum(a['status'] != 'concluida' and a['due_date'] < date.today().isoformat() for a in actions),
                    'action_scope': 'Todos os prazos; filtro de setor aplicado.'}

    @app.get('/api/reports/records.csv', tags=['Relatórios'])
    def export_records(start: date | None = None, end: date | None = None, sector_id: int | None = None, user=Depends(current_user)):
        with connect(path) as db:
            records = list_records(db, start, end, sector_id)
        buffer = io.StringIO(newline='')
        output = csv.writer(buffer, delimiter=';')
        output.writerow(['ID','Data','Indicador','Quantidade','Unidade','Setor','Parceiro','Tipo de resíduo','Destinação','Observação'])
        units = {'agua': 'm³', 'energia': 'kWh', 'residuos': 'kg'}
        def safe(value):
            text = str(value or '')
            return "'"+text if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else text
        for r in records:
            output.writerow([r['id'], r['date'], r['metric'], str(r['quantity']).replace('.', ','), units[r['metric']],
                             *[safe(r[k]) for k in ['sector_name','partner_name','waste_type','destination','note']]])
        return Response('\ufeff'+buffer.getvalue(), media_type='text/csv; charset=utf-8',
                        headers={'Content-Disposition': 'attachment; filename="registros_ambientais.csv"'})

    @app.get('/api/audit', tags=['Auditoria'])
    def history(user=Depends(manager)):
        with connect(path) as db:
            return [dict(r) for r in db.execute('SELECT a.*,u.name user_name FROM audit a JOIN users u ON u.id=a.user_id ORDER BY a.id DESC')]

    @app.get('/', include_in_schema=False)
    def index():
        return FileResponse(ROOT / 'frontend/index.html')

    app.mount('/assets', StaticFiles(directory=ROOT / 'frontend'), name='assets')
    return app


app = create_app()
