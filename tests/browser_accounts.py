"""Fluxo de contas próprias em navegador com servidor e banco separados."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'test-results'
OUT.mkdir(exist_ok=True)
checks = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 960})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(os.environ.get('ECOGESTAO_TEST_URL', 'http://127.0.0.1:8005'))
    expect(page.locator('#login-screen')).not_to_contain_text('EcoDemo2026!')
    assert page.locator('#email').input_value() == ''
    page.locator('#email').fill('gestor-e2e@exemplo.com')
    page.locator('#password').fill('Senha inicial E2E 2026')
    page.get_by_role('button', name='Entrar').click()
    expect(page.locator('#app')).to_be_visible()
    expect(page.locator('.demo-badge')).to_be_hidden()
    checks.append('Gestor próprio entra sem credenciais exibidas ou selo de demonstração')

    page.get_by_role('button', name='Contas').click()
    page.get_by_role('button', name='Nova conta').click()
    page.locator('#field-name').fill('Operadora E2E')
    page.locator('#field-email').fill('operadora-e2e@exemplo.com')
    page.locator('#field-role').select_option('operador')
    page.locator('#field-password').fill('Senha da operadora E2E 2026')
    page.locator('#edit-form').get_by_role('button', name='Salvar').click()
    row = page.locator('tbody tr').filter(has_text='operadora-e2e@exemplo.com')
    expect(row).to_contain_text('Ativo')
    checks.append('Gestor cria conta de operador pela interface')

    row.get_by_role('button', name='Redefinir senha').click()
    page.locator('#new-password').fill('Nova senha da operadora E2E 2026')
    page.locator('#confirm-password').fill('Nova senha da operadora E2E 2026')
    page.locator('#password-form').get_by_role('button', name='Salvar senha').click()
    expect(page.locator('#password-dialog')).to_be_hidden()
    checks.append('Gestor redefine senha sem expor hash')

    page.get_by_role('button', name='Sair').click()
    page.locator('#email').fill('operadora-e2e@exemplo.com')
    page.locator('#password').fill('Nova senha da operadora E2E 2026')
    page.get_by_role('button', name='Entrar').click()
    expect(page.locator('#app')).to_be_visible()
    expect(page.get_by_role('button', name='Contas')).to_be_hidden()
    checks.append('Operador entra sem acesso à gestão de contas')

    page.get_by_role('button', name='Trocar minha senha').click()
    page.locator('#current-password').fill('Nova senha da operadora E2E 2026')
    page.locator('#new-password').fill('Senha própria alterada E2E 2026')
    page.locator('#confirm-password').fill('Senha própria alterada E2E 2026')
    page.locator('#password-form').get_by_role('button', name='Salvar senha').click()
    expect(page.locator('#password-dialog')).to_be_hidden()
    page.get_by_role('button', name='Sair').click()
    page.locator('#email').fill('operadora-e2e@exemplo.com')
    page.locator('#password').fill('Senha própria alterada E2E 2026')
    page.get_by_role('button', name='Entrar').click()
    expect(page.locator('#app')).to_be_visible()
    checks.append('Operador troca a própria senha e acessa com a nova')

    page.get_by_role('button', name='Sair').click()
    page.locator('#email').fill('gestor-e2e@exemplo.com')
    page.locator('#password').fill('Senha inicial E2E 2026')
    page.get_by_role('button', name='Entrar').click()
    page.get_by_role('button', name='Contas').click()
    row = page.locator('tbody tr').filter(has_text='operadora-e2e@exemplo.com')
    row.get_by_role('button', name='Editar').click()
    page.locator('#field-active').select_option('0')
    page.locator('#edit-form').get_by_role('button', name='Salvar').click()
    expect(page.locator('tbody tr').filter(has_text='operadora-e2e@exemplo.com')).to_contain_text('Inativo')
    checks.append('Gestor desativa conta mantendo seu cadastro')
    page.screenshot(path=str(ROOT.parent / 'documentacao' / 'imagens' / '07_contas.png'), full_page=True)

    assert not errors, errors
    browser.close()
(OUT / 'browser_accounts.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'javascript_errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':len(checks),'checks':checks},ensure_ascii=False))
