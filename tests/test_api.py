"""Testes de aceitação da API com banco independente por teste."""
import csv
import io
import time
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.database import connect


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path/'test.db')) as instance:
        yield instance


def login(client, role='gestor'):
    response = client.post('/api/auth/login', json={'email':role+'@demo.local','password':'EcoDemo2026!'})
    assert response.status_code == 200
    client.headers['X-CSRF-Token'] = response.json()['csrf']
    return response.json()


def record(**changes):
    return dict(metric='agua', date='2026-01-10', quantity=12.5, sector_id=1, **changes)


def test_home_uses_versioned_assets_and_is_not_cached(client):
    response = client.get('/')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert '/assets/app.js?v=20260922-2' in response.text
    assert '/assets/styles.css?v=20260922-2' in response.text
    script = client.get('/assets/app.js?v=20260922-2')
    assert script.status_code == 200
    assert 'function dateISO(value)' in script.text


def test_session_lifecycle_and_cookie(client):
    assert client.get('/api/records').status_code == 401
    response=client.post('/api/auth/login',json={'email':'gestor@demo.local','password':'errada'})
    assert response.status_code==401
    login(client)
    assert client.get('/api/auth/me').json()['role']=='gestor'
    assert client.post('/api/auth/logout').status_code==204
    assert client.get('/api/auth/me').status_code==401


def test_session_expiration_and_csrf(client):
    login(client)
    del client.headers['X-CSRF-Token']
    assert client.post('/api/records',json=record()).status_code==403
    with connect(client.app.state.db_path) as db:
        assert len(db.execute('SELECT token_hash FROM sessions').fetchone()[0])==64
        db.execute('UPDATE sessions SET expires_at=?',(time.time()-1,))
    assert client.get('/api/records').status_code==401


@pytest.mark.parametrize('role,code',[('gestor',201),('operador',403),('consulta',403)])
def test_sector_permission(client,role,code):
    login(client,role)
    assert client.post('/api/sectors',json={'name':'Novo setor'}).status_code==code


@pytest.mark.parametrize('role,code',[('gestor',201),('operador',201),('consulta',403)])
def test_record_permission(client,role,code):
    login(client,role)
    assert client.post('/api/records',json=record()).status_code==code


def test_record_crud_persistence_and_audit(client):
    login(client)
    response=client.post('/api/records',json=record())
    assert response.status_code==201
    identifier=response.json()['id']
    payload=record();payload['quantity']=27
    assert client.put(f'/api/records/{identifier}',json=payload).status_code==200
    with connect(client.app.state.db_path) as db:
        assert db.execute('SELECT quantity FROM records WHERE id=?',(identifier,)).fetchone()[0]==27
    assert client.delete(f'/api/records/{identifier}').status_code==204
    operations=[a['operation'] for a in client.get('/api/audit').json() if a['entity_id']==identifier]
    assert operations==['excluir','alterar','criar']
    assert client.delete(f'/api/records/{identifier}').status_code==404


@pytest.mark.parametrize('key,value',[('quantity',0),('quantity',-1),('quantity',1e20),('metric','gas'),('sector_id',-2),('date','invalida'),('date',(date.today()+timedelta(days=1)).isoformat())])
def test_reject_invalid_record(client,key,value):
    login(client);payload=record();payload[key]=value
    assert client.post('/api/records',json=payload).status_code==422


def test_waste_requires_destination_and_partner(client):
    login(client);payload=record();payload['metric']='residuos'
    assert client.post('/api/records',json=payload).status_code==422
    payload.update(partner_id=1,waste_type='Papel',destination='Reciclagem')
    assert client.post('/api/records',json=payload).status_code==201
    payload['metric']='agua'
    assert client.post('/api/records',json=payload).status_code==422


def test_inactive_sector_and_partner_preserve_history(client):
    login(client)
    assert client.put('/api/sectors/1',json={'name':'Administrativo','active':False}).status_code==200
    assert client.post('/api/records',json=record()).status_code==409
    assert any(r['sector_id']==1 for r in client.get('/api/records').json())
    assert client.put('/api/partners/1',json={'name':'Cooperativa Exemplo','contact':'Teste','active':False}).status_code==200
    payload=record();payload.update(metric='residuos',sector_id=2,partner_id=1,waste_type='Papel',destination='Reciclagem')
    assert client.post('/api/records',json=payload).status_code==409


def test_missing_related_entity_and_duplicate_names(client):
    login(client)
    payload=record();payload['sector_id']=999
    assert client.post('/api/records',json=payload).status_code==404
    assert client.post('/api/sectors',json={'name':'Administrativo'}).status_code==409
    assert client.post('/api/partners',json={'name':'Parceiro novo','contact':'Exemplo'}).status_code==201


def test_dashboard_separates_units_and_distinguishes_no_data(client):
    login(client)
    data=client.get('/api/dashboard?start=2026-09-01&end=2026-09-30').json()
    assert data['totals']['agua']=={'count':2,'total':145}
    assert data['totals']['energia']['total']==4280
    assert data['totals']['residuos']['total']==235
    data=client.get('/api/dashboard?start=2025-01-01&end=2025-01-31').json()
    assert data['totals']['agua']['total'] is None
    assert client.get('/api/records?start=2026-09-30&end=2026-09-01').status_code==422
    assert client.get('/api/dashboard?sector_id=1&start=2026-09-01').json()['totals']['agua']['total']==35


def test_goal_overlap_limits_and_results(client):
    login(client)
    goal={'title':'Teste de meta','metric':'agua','sector_id':1,'start_date':'2026-01-01','end_date':'2026-01-31','limit_value':10}
    created=client.post('/api/goals',json=goal)
    assert created.status_code==201
    identifier=created.json()['id']
    assert client.post('/api/goals',json=goal).status_code==409
    result=next(g for g in client.get('/api/goals').json() if g['id']==identifier)
    assert result['actual'] is None and result['record_count']==0
    client.post('/api/records',json=record())
    result=next(g for g in client.get('/api/goals').json() if g['id']==identifier)
    assert result['actual']==12.5 and result['actual']>result['limit_value']
    goal['limit_value']=20
    assert client.put(f'/api/goals/{identifier}',json=goal).status_code==200
    goal['end_date']='2025-01-01'
    assert client.put(f'/api/goals/{identifier}',json=goal).status_code==422
    assert client.delete(f'/api/goals/{identifier}').status_code==204


def test_action_completion_requires_evidence(client):
    login(client,'operador')
    payload={'title':'Revisar equipamentos','description':'Conferir funcionamento dos equipamentos','sector_id':1,'owner_id':2,'due_date':'2026-12-01'}
    response=client.post('/api/actions',json=payload)
    assert response.status_code==201
    identifier=response.json()['id'];payload['status']='concluida'
    assert client.put(f'/api/actions/{identifier}',json=payload).status_code==422
    payload['evidence']='Checklist preenchido e inspeção registrada.'
    completed=client.put(f'/api/actions/{identifier}',json=payload)
    assert completed.status_code==200 and completed.json()['completed_at']
    assert client.delete(f'/api/actions/{identifier}').status_code==403
    login(client)
    assert client.delete(f'/api/actions/{identifier}').status_code==204


def test_action_owner_cannot_be_readonly(client):
    login(client)
    payload={'title':'Teste de ação','description':'Teste de atribuição','sector_id':1,'owner_id':3,'due_date':'2026-12-01'}
    assert client.post('/api/actions',json=payload).status_code==422


def test_csv_uses_same_filter_and_neutralizes_formula(client):
    login(client);payload=record(note='=HYPERLINK("example")')
    client.post('/api/records',json=payload)
    response=client.get('/api/reports/records.csv?start=2026-01-01&end=2026-01-31&sector_id=1')
    assert response.status_code==200 and 'attachment' in response.headers['content-disposition']
    rows=list(csv.reader(io.StringIO(response.text.lstrip('\ufeff')),delimiter=';'))
    assert len(rows)==2 and rows[1][3]=='12,5' and rows[1][-1].startswith("'=")


def test_readonly_access_audit_denied_and_openapi(client):
    login(client,'consulta')
    for endpoint in ['/sectors','/partners','/users','/records','/goals','/actions','/dashboard','/reports/records.csv']:
        assert client.get('/api'+endpoint).status_code==200
    assert client.get('/api/audit').status_code==403
    schema=client.get('/api/openapi.json').json()
    assert '/api/records' in schema['paths'] and 'post' in schema['paths']['/api/records']
    assert client.get('/').status_code==200


def test_failed_operation_does_not_create_audit_record(client):
    login(client)
    initial=len(client.get('/api/audit').json())
    payload=record();payload['sector_id']=99999
    assert client.post('/api/records',json=payload).status_code==404
    assert len(client.get('/api/audit').json())==initial
