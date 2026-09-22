"""Regras compartilhadas pelos endpoints e relatórios."""
from datetime import date, datetime, timezone
from fastapi import HTTPException
from .database import audit

# Identificadores SQL vêm exclusivamente desta lista interna, nunca do cliente.
TABLES = {'sectors', 'partners', 'records', 'goals', 'actions'}


def require_row(db, table, identifier, active=False):
    if table not in TABLES | {'users'}:
        raise ValueError('Tabela não permitida')
    row = db.execute(f'SELECT * FROM {table} WHERE id=?', (identifier,)).fetchone()
    if not row:
        raise HTTPException(404, 'Registro relacionado não encontrado.')
    if active and not row['active']:
        raise HTTPException(409, 'O cadastro relacionado está inativo.')
    return dict(row)


def save(db, table, payload, user, identifier=None):
    if table not in TABLES:
        raise ValueError('Tabela não permitida')
    if not db.in_transaction:
        db.execute('BEGIN IMMEDIATE')
    before = require_row(db, table, identifier) if identifier else None
    data = payload.model_dump(mode='json')
    if 'sector_id' in data:
        require_row(db, 'sectors', data['sector_id'], active=True)
    if data.get('partner_id'):
        require_row(db, 'partners', data['partner_id'], active=True)
    if table == 'actions':
        owner = require_row(db, 'users', data['owner_id'])
        if owner['role'] == 'consulta':
            raise HTTPException(422, 'Responsável deve ser gestor ou operador.')
        data['completed_at'] = ((before or {}).get('completed_at') or datetime.now(timezone.utc).isoformat()) if data['status'] == 'concluida' else None
    if table == 'records' and not identifier:
        data['created_by'] = user['id']
    if table == 'goals':
        overlap = db.execute('SELECT id FROM goals WHERE metric=? AND sector_id=? '
                             'AND start_date<=? AND end_date>=? AND id<>?',
                             (data['metric'], data['sector_id'], data['end_date'], data['start_date'], identifier or 0)).fetchone()
        if overlap:
            raise HTTPException(409, 'Já existe meta desse indicador e setor em período sobreposto.')
    if identifier:
        db.execute(f'UPDATE {table} SET '+','.join(f'{key}=?' for key in data)+' WHERE id=?',
                   [*data.values(), identifier])
    else:
        cursor = db.execute(f'INSERT INTO {table}('+','.join(data)+') VALUES('+','.join('?' for _ in data)+')', list(data.values()))
        identifier = cursor.lastrowid
    result = require_row(db, table, identifier)
    audit(db, user['id'], 'alterar' if before else 'criar', table, identifier, before, result)
    return result


def remove(db, table, identifier, user):
    if table not in {'records', 'goals', 'actions'}:
        raise ValueError('Remoção não permitida')
    before = require_row(db, table, identifier)
    db.execute(f'DELETE FROM {table} WHERE id=?', (identifier,))
    audit(db, user['id'], 'excluir', table, identifier, before)


def period_filter(start, end, sector_id, prefix=''):
    if start and end and start > end:
        raise HTTPException(422, 'Período inicial posterior ao final.')
    clauses, args = [], []
    for value, clause in [(start, f'{prefix}date>=?'), (end, f'{prefix}date<=?'), (sector_id, f'{prefix}sector_id=?')]:
        if value is not None:
            clauses.append(clause)
            args.append(value.isoformat() if isinstance(value, date) else value)
    return (' WHERE '+' AND '.join(clauses) if clauses else ''), args


def list_records(db, start=None, end=None, sector_id=None):
    where, args = period_filter(start, end, sector_id, 'r.')
    return [dict(r) for r in db.execute('SELECT r.*,s.name sector_name,p.name partner_name FROM records r '
            'JOIN sectors s ON s.id=r.sector_id LEFT JOIN partners p ON p.id=r.partner_id'+where+' ORDER BY r.date DESC,r.id DESC', args)]


def goal_results(db):
    return [dict(r) for r in db.execute('SELECT g.*,s.name sector_name,COUNT(r.id) record_count, '
        'CASE WHEN COUNT(r.id)=0 THEN NULL ELSE ROUND(SUM(r.quantity),3) END actual '
        'FROM goals g JOIN sectors s ON s.id=g.sector_id LEFT JOIN records r '
        'ON r.metric=g.metric AND r.sector_id=g.sector_id AND r.date BETWEEN g.start_date AND g.end_date '
        'GROUP BY g.id ORDER BY g.end_date DESC,g.id DESC')]
