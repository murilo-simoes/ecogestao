# EcoGestão

Aplicação acadêmica de gestão ambiental organizacional. Implementa serviços HTTP próprios e uma interface web que os consome por `fetch`. Registra água, energia, resíduos, metas, ações corretivas, setores e parceiros. Em um banco novo, o modo normal inicia sem contas nem dados fictícios; há um modo de demonstração opcional.

## Requisitos

Python 3.12 e navegador atualizado. Internet apenas para instalar dependências; a aplicação e seus recursos visuais funcionam localmente após a instalação. O teste automatizado de interface usa Google Chrome instalado. Validado no Windows com Python 3.12.14.

## Instalar e executar no Windows

Abra o PowerShell na pasta `software` e execute:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage_users.py --name "Gestor principal" --email gestor@seu-dominio.com
.\.venv\Scripts\python.exe run.py
```

Acesse [EcoGestão local](http://127.0.0.1:8000). O comando `manage_users.py` cria o banco, solicita a senha sem exibi-la e cadastra o primeiro gestor. Use uma senha própria com pelo menos 12 caracteres. O banco padrão é `data/ecogestao.db`; `ECOGESTAO_DB` seleciona outro arquivo e deve apontar para o mesmo banco em todos os comandos. Encerre o servidor com `Ctrl+C`. Os dados persistem entre execuções.

Em Linux/macOS, use `python3.12 -m venv .venv` e `.venv/bin/python` nos comandos equivalentes. A suíte de interface fornecida usa o canal Chrome, que precisa estar instalado.

Não é necessário ativar o ambiente virtual, alterar a política de execução do PowerShell ou instalar um servidor de banco.

## Contas e migração de um banco existente

O primeiro gestor é criado pelo comando acima. Depois de entrar, abra **Contas** para criar gestores, operadores e usuários de consulta, editar seus dados, desativá-los e redefinir suas senhas. Cada pessoa pode usar **Trocar minha senha**. A desativação impede novos acessos e encerra sessões, mas preserva registros e ações vinculados à conta. A aplicação impede remover o próprio acesso de gestor e deixar o banco sem gestor ativo. Não há cadastro público nem envio de senha por e-mail; o gestor deve comunicar a senha inicial por um canal apropriado.

Se o servidor já usa um banco com contas de demonstração, **faça backup do arquivo SQLite e pare o aplicativo**. Após atualizar o código, execute `manage_users.py` usando exatamente o mesmo caminho de banco do servidor. O comando cria seu gestor e desativa as três contas públicas e suas sessões numa transação, sem apagar os dados ambientais. Só então reinicie o aplicativo. Se as contas públicas ainda estiverem ativas, o servidor recusa iniciar no modo normal. Os registros fictícios antigos continuam identificados como demonstração; para operar exclusivamente com dados reais, use um banco novo e cadastre seus próprios setores e registros.

Em Linux, por exemplo, com o ambiente virtual já instalado e o mesmo `ECOGESTAO_DB` usado pelo serviço:

```bash
.venv/bin/python manage_users.py --name "Gestor principal" --email gestor@seu-dominio.com
```

Não passe a senha como argumento: o comando a solicita sem mostrá-la. Defina `ECOGESTAO_HTTPS=1` no serviço HTTPS para que o cookie de sessão receba a marca Secure. A aplicação deve ser publicada atrás de HTTPS; faça backup do banco antes de atualizações e reveja permissões do arquivo no servidor.

### Demonstração acadêmica local

Para gerar um banco separado com dados fictícios, use `init_db.py --demo` e inicie o servidor com `ECOGESTAO_DEMO=1`. Somente esse modo aceita as contas `gestor@demo.local`, `operador@demo.local` e `consulta@demo.local`, todas com a senha pública `EcoDemo2026!`. Nunca use `ECOGESTAO_DEMO=1` no servidor público.

```powershell
$env:ECOGESTAO_DB = Join-Path $PWD 'data\demonstracao.db'
.\.venv\Scripts\python.exe init_db.py --database $env:ECOGESTAO_DB --demo
$env:ECOGESTAO_DEMO = '1'
.\.venv\Scripts\python.exe run.py
```

## Avaliação pelo professor na instância publicada

A versão informada pelo grupo está em https://ecogestao.murilosimoes.com.br/. Para dar acesso ao professor, entre com o gestor principal, abra **Contas** e selecione **Nova conta**. Informe o nome e o e-mail institucional do professor, escolha **Gestor** para permitir também os testes de administração e defina uma senha inicial própria com pelo menos 12 caracteres. Para uma conta individual, comunique a senha diretamente ao professor por um canal privado e não a inclua no repositório ou em capturas de tela. Ele pode usar **Trocar minha senha** após entrar. Se o grupo optar por divulgar no Word uma conta compartilhada de demonstração, essa conta não deve ser usada para dados reais e sua senha deve ser alterada ou a conta desativada após a avaliação.

A existência da conta e o login na instância publicada devem ser conferidos no servidor depois do cadastro. O endereço foi verificado por uma consulta GET sobre HTTPS em 22/09/2026; os testes funcionais descritos neste projeto foram executados localmente.

## Interface e datas

A interface usa a fonte Inter, incluída localmente em `frontend/fonts` sob a licença SIL Open Font License (`frontend/fonts/OFL.txt`). Não depende de um serviço de fontes externo. Todos os campos e filtros de data são apresentados e preenchidos como **DD/MM/AAAA**. A aplicação valida dias e meses antes de enviar a data à API; o contrato HTTP e o SQLite continuam a utilizar `AAAA-MM-DD`.

## Uso e regras

1. Entre com a conta do gestor. O painel abre no mês corrente; no modo de demonstração, ajuste o filtro para setembro de 2026 para ver os dados iniciais.
2. Cadastre setores e parceiros. É possível editar e inativar cadastros sem apagar seus vínculos históricos. Para corrigir um registro vinculado a cadastro inativo, reative o cadastro primeiro.
3. Em Registros ambientais, informe a quantidade efetivamente consumida, e não a leitura acumulada do medidor. Água utiliza m³; energia, kWh; resíduos, kg. Quantidades devem ser maiores que zero. Ausência de medição não é registrada como zero.
4. Para resíduos, informe tipo, destinação e parceiro responsável. Datas futuras são recusadas. Um registro representa o consumo atribuído à data informada ou uma coleta de resíduos; o programa não divide automaticamente faturas entre meses.
5. Metas são limites máximos por indicador, setor e intervalo inclusivo. Não são admitidas metas com períodos sobrepostos para o mesmo indicador e setor. A situação é calculada a partir dos registros; ausência de dados aparece como tal, sem afirmar cumprimento da meta.
6. Ações possuem descrição, responsável, prazo e estado. A conclusão exige evidência textual. Evidências documentais anexadas e assinatura digital não fazem parte desta versão.
7. O painel filtra os consumos pelo intervalo e setor. As metas usam seu próprio período completo. Pendências de ações usam todos os prazos, com o setor filtrado. A interface informa essas diferenças.
8. Relatórios permite filtrar, baixar CSV separado por ponto e vírgula e imprimir pelo navegador. O CSV inclui cabeçalho, unidade e proteção contra fórmulas em campos textuais.
9. Histórico permite ao gestor inspecionar autor, data, operação e valores anteriores/posteriores de alterações. O horário é armazenado em UTC e exibido no fuso do navegador.

Não há cálculo de emissões, sensores, geolocalização, integração com órgãos ambientais ou certificação ISO. O vínculo com a família ISO 14000 é o apoio a registros, responsabilidades, monitoramento e melhoria de procedimentos. O sistema não comprova a destinação física do resíduo nem uma redução ambiental real.

## Arquitetura e arquivos

```text
backend/
  main.py          rotas HTTP, autenticação, permissões e relatórios
  schemas.py       contratos e validações de entrada
  services.py      regras e operações de negócio
  database.py      conexões, inicialização e auditoria
  security.py      derivação de senhas e hash de sessões
frontend/
  index.html       estrutura da interface
  styles.css       estilos responsivos e impressão
  app.js           consumo da API e interação
database/
  schema.sql       criação de tabelas e restrições
  seed.sql         dados fictícios de demonstração
tests/
  test_api.py      testes de aceitação e integração
  browser_flow.py  fluxo ambiental no navegador
  browser_accounts.py  gestão de contas no navegador
  test_accounts.py  testes de migração e autenticação
run.py             inicialização local
init_db.py         inicialização explícita de banco
manage_users.py    criação segura do primeiro gestor
```

O servidor entrega os arquivos estáticos e os serviços, mas a interface acessa os dados exclusivamente pela API. A arquitetura é orientada a recursos HTTP, inspirada em REST. Como utiliza sessões no servidor, não se reivindica adesão integral à restrição de ausência de estado de sessão do REST estrito.

## API

Contrato gerado em [OpenAPI](http://127.0.0.1:8000/api/openapi.json). A tela Serviços e API também consulta esse contrato real, sem depender de CDN externa.

As principais rotas são `/api/auth/login`, `/api/auth/me`, `/api/auth/logout`, `/api/auth/password`, `/api/admin/users`, `/api/sectors`, `/api/partners`, `/api/users`, `/api/records`, `/api/goals`, `/api/actions`, `/api/dashboard`, `/api/reports/records.csv` e `/api/audit`. Criação usa POST; atualização usa PUT com identificador. DELETE está disponível para registros, metas e ações, somente ao gestor. Setores e parceiros são inativados por PUT.

Exemplo no PowerShell com o modo de demonstração local em execução:

```powershell
$login = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/auth/login' -Method Post -ContentType 'application/json' -Body '{"email":"gestor@demo.local","password":"EcoDemo2026!"}' -SessionVariable sessaoEco
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/records?start=2026-09-01&end=2026-09-30' -WebSession $sessaoEco
$cabecalhosEco = @{ 'X-CSRF-Token' = $login.csrf }
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/auth/logout' -Method Post -WebSession $sessaoEco -Headers $cabecalhosEco
```

Sessões duram oito horas, usam cookie HttpOnly e SameSite Strict. Escritas exigem o cabeçalho X-CSRF-Token obtido no login. Senhas usam PBKDF2-HMAC-SHA256 com sal individual e 600.000 iterações; tokens de sessão são guardados como hash. Consultas SQL recebem parâmetros. Mudanças e auditoria compartilham transação. O limitador de tentativas de login é local ao processo; não substitui proteção de produção.

`ECOGESTAO_DB` permite escolher outro banco. `ECOGESTAO_HTTPS=1` marca cookies como Secure, mas não configura TLS. A proteção pública também depende de HTTPS, administração do servidor, backups e revisão de segurança próprias.

## Banco e dados de exemplo

`database/schema.sql` cria tabelas e chaves estrangeiras. `database/seed.sql` fornece os dados ambientais e pressupõe os três usuários criados pelo inicializador com senhas derivadas.

```powershell
.\.venv\Scripts\python.exe init_db.py --database data\outra_demonstracao.db --demo
```

O inicializador não sobrescreve dados existentes. Para outra demonstração, escolha um arquivo novo com `ECOGESTAO_DB`. Faça cópias do banco com o servidor parado. Não apague dados reais para reproduzir testes.

## Executar testes

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q --junitxml=test-results/api.xml
```

Cada teste de API usa um banco temporário próprio. Para testar a interface, inicie um servidor com banco novo e separado do banco normal:

```powershell
$env:ECOGESTAO_DB = Join-Path $PWD 'test-results\browser_novo.db'
$env:ECOGESTAO_DEMO = '1'
.\.venv\Scripts\python.exe run.py
```

Em outro terminal, na mesma pasta:

```powershell
.\.venv\Scripts\python.exe tests\browser_flow.py
```

O fluxo ambiental cria itens com E2E no nome. Deve ser executado uma vez por banco novo, pois nomes repetidos são recusados. As evidências vão para `test-results`; capturas para a pasta irmã `documentacao/imagens`. `tests/browser_accounts.py` verifica o modo de contas próprias em um banco separado com primeiro gestor criado por `manage_users.py`. Para repetir esse fluxo, use o nome `Gestor E2E`, e-mail `gestor-e2e@exemplo.com` e senha `Senha inicial E2E 2026` apenas no banco temporário; configure `ECOGESTAO_TEST_URL` para a porta da instância correspondente. Os testes não substituem uma auditoria de segurança ou ensaio de carga em produção.

## Apresentação acadêmica

Mostre login, painel, cadastros, registro de resíduo, criação de meta, ação com evidência, relatório CSV e contrato OpenAPI. Alterne para consulta para demonstrar restrição de escrita. O fonte completo acompanha a entrega; o Word reproduz trechos selecionados. A ficha de atividades será acrescentada pelo grupo.
