"""Cria as tabelas; dados fictícios são opcionais e explícitos."""
import argparse
from backend.database import initialize

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', default='data/ecogestao.db')
    parser.add_argument('--demo', action='store_true', help='inclui contas e dados fictícios para apresentação local')
    args = parser.parse_args()
    initialize(args.database, demo=args.demo)
    print(f'Banco inicializado: {args.database}')
