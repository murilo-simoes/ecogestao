"""Cria tabelas e dados fictícios sem sobrescrever banco existente."""
import argparse
from backend.database import initialize

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', default='data/ecogestao.db')
    args = parser.parse_args()
    initialize(args.database, demo=True)
    print(f'Banco inicializado: {args.database}')
