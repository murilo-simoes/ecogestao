"""Cria o primeiro gestor sem expor senhas na linha de comando."""
import argparse
import getpass
import os

from backend.database import ROOT, connect, initialize
from backend.schemas import AccountCreate
from backend.security import hash_password

DEMO_EMAILS = ('gestor@demo.local', 'operador@demo.local', 'consulta@demo.local')


def create_first_manager(path, name, email, password):
    account = AccountCreate(name=name, email=email, role='gestor', password=password)
    if account.email in DEMO_EMAILS:
        raise ValueError('Use um e-mail próprio para a conta do gestor.')
    initialize(path, demo=False)
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        existing = db.execute(
            "SELECT 1 FROM users WHERE role='gestor' AND active=1 AND email NOT IN (?,?,?)",
            DEMO_EMAILS).fetchone()
        if existing:
            raise ValueError('Já existe um gestor próprio ativo. Use a gestão de contas na aplicação.')
        cursor = db.execute(
            'INSERT INTO users(name,email,password_hash,role,active) VALUES(?,?,?,?,1)',
            (account.name, account.email, hash_password(account.password), 'gestor'))
        demo_ids = [row['id'] for row in db.execute(
            'SELECT id FROM users WHERE email IN (?,?,?) AND active=1', DEMO_EMAILS)]
        if demo_ids:
            db.execute('UPDATE users SET active=0 WHERE email IN (?,?,?)', DEMO_EMAILS)
            db.execute('DELETE FROM sessions WHERE user_id IN (' + ','.join('?' for _ in demo_ids) + ')', demo_ids)
        return cursor.lastrowid, len(demo_ids)


def main():
    parser = argparse.ArgumentParser(description='Cria o primeiro gestor e desativa as contas de demonstração no mesmo banco.')
    parser.add_argument('--database', default=os.environ.get('ECOGESTAO_DB', str(ROOT / 'data/ecogestao.db')))
    parser.add_argument('--name', required=True)
    parser.add_argument('--email', required=True)
    args = parser.parse_args()
    password = getpass.getpass('Nova senha (mínimo de 12 caracteres): ')
    if password != getpass.getpass('Confirme a senha: '):
        parser.error('As senhas não coincidem.')
    try:
        identifier, disabled = create_first_manager(args.database, args.name, args.email, password)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f'Gestor criado: ID {identifier}. Contas de demonstração desativadas: {disabled}.')


if __name__ == '__main__':
    main()
