"""Inicialização local. Execute a partir da pasta software."""
import uvicorn

if __name__ == '__main__':
    uvicorn.run('backend.main:app', host='127.0.0.1', port=8000)
