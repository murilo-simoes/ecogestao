# EcoGestão

Aplicação acadêmica de gestão ambiental organizacional. Implementa serviços HTTP próprios e uma interface web que os consome por `fetch`. Registra água, energia, resíduos, metas, ações corretivas, setores e parceiros. Todos os dados iniciais são fictícios.

## Requisitos

Python 3.12 e navegador atualizado. Internet apenas para instalar dependências; a aplicação e seus recursos visuais funcionam localmente após a instalação. O teste automatizado de interface usa Google Chrome instalado. Validado no Windows com Python 3.12.14.

## Instalar e executar no Windows

Abra o PowerShell na pasta `software` e execute:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

Acesse [EcoGestão local](http://127.0.0.1:8000). O banco `data/ecogestao.db` é criado automaticamente no primeiro início. Encerre com `Ctrl+C`. Os dados persistem entre execuções.

Em Linux/macOS, use `python3.12 -m venv .venv` e `.venv/bin/python` nos comandos equivalentes. A suíte de interface fornecida usa o canal Chrome, que precisa estar instalado.

Não é necessário ativar o ambiente virtual, alterar a política de execução do PowerShell ou instalar um servidor de banco.

## Contas de demonstração

| E-mail | Senha | Permissões |
|---|---|---|
| gestor@demo.local | EcoDemo2026! | Todas as funções, exclusões e histórico |
| operador@demo.local | EcoDemo2026! | Consulta, criação e edição de registros e ações |
| consulta@demo.local | EcoDemo2026! | Leitura e relatórios |

Contas são pré-configuradas pelo inicializador. Não há tela de gestão de usuários nem recuperação de senha nesta versão. O software foi preparado para demonstração local, não para publicação direta na internet com essas credenciais.

## Interface e datas

A interface usa a fonte Inter, incluída localmente em `frontend/fonts` sob a licença SIL Open Font License (`frontend/fonts/OFL.txt`). Não depende de um serviço de fontes externo. Todos os campos e filtros de data são apresentados e preenchidos como **DD/MM/AAAA**. A aplicação valida dias e meses antes de enviar a data à API; o contrato HTTP e o SQLite continuam a utilizar `AAAA-MM-DD`.

## Uso e regras

1. Entre como gestor. O painel abre com setembro de 2026, mês dos dados de exemplo.
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
  browser_flow.py  fluxo real no navegador
run.py             inicialização local
init_db.py         inicialização explícita de banco
```

O servidor entrega os arquivos estáticos e os serviços, mas a interface acessa os dados exclusivamente pela API. A arquitetura é orientada a recursos HTTP, inspirada em REST. Como utiliza sessões no servidor, não se reivindica adesão integral à restrição de ausência de estado de sessão do REST estrito.

## API

Contrato gerado em [OpenAPI](http://127.0.0.1:8000/api/openapi.json). A tela Serviços e API também consulta esse contrato real, sem depender de CDN externa.

As principais rotas são `/api/auth/login`, `/api/auth/me`, `/api/auth/logout`, `/api/sectors`, `/api/partners`, `/api/users`, `/api/records`, `/api/goals`, `/api/actions`, `/api/dashboard`, `/api/reports/records.csv` e `/api/audit`. Criação usa POST; atualização usa PUT com identificador. DELETE está disponível para registros, metas e ações, somente ao gestor. Setores e parceiros são inativados por PUT.

Exemplo no PowerShell, com o programa em execução:

```powershell
$login = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/auth/login' -Method Post -ContentType 'application/json' -Body '{"email":"gestor@demo.local","password":"EcoDemo2026!"}' -SessionVariable sessaoEco
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/records?start=2026-09-01&end=2026-09-30' -WebSession $sessaoEco
$cabecalhosEco = @{ 'X-CSRF-Token' = $login.csrf }
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/auth/logout' -Method Post -WebSession $sessaoEco -Headers $cabecalhosEco
```

Sessões duram oito horas, usam cookie HttpOnly e SameSite Strict. Escritas exigem o cabeçalho X-CSRF-Token obtido no login. Senhas usam PBKDF2-HMAC-SHA256 com sal individual e 600.000 iterações; tokens de sessão são guardados como hash. Consultas SQL recebem parâmetros. Mudanças e auditoria compartilham transação. O limitador de tentativas de login é local ao processo; não substitui proteção de produção.

`ECOGESTAO_DB` permite escolher outro banco. `ECOGESTAO_HTTPS=1` marca cookies como Secure, mas não configura TLS: qualquer uso em rede pública exigiria implantação com HTTPS, troca de contas, gestão de usuários, operação de backup e revisão de segurança próprias.

## Banco e dados de exemplo

`database/schema.sql` cria tabelas e chaves estrangeiras. `database/seed.sql` fornece os dados ambientais e pressupõe os três usuários criados pelo inicializador com senhas derivadas.

```powershell
.\.venv\Scripts\python.exe init_db.py --database data\outra_demonstracao.db
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
.\.venv\Scripts\python.exe run.py
```

Em outro terminal, na mesma pasta:

```powershell
.\.venv\Scripts\python.exe tests\browser_flow.py
```

O fluxo cria itens com E2E no nome. Deve ser executado uma vez por banco novo, pois nomes repetidos são recusados. As evidências vão para `test-results`; capturas para a pasta irmã `documentacao/imagens`. Os testes não substituem uma auditoria de segurança ou ensaio de carga em produção.

## Apresentação acadêmica

Mostre login, painel, cadastros, registro de resíduo, criação de meta, ação com evidência, relatório CSV e contrato OpenAPI. Alterne para consulta para demonstrar restrição de escrita. O fonte completo acompanha a entrega; o Word reproduz trechos selecionados. A ficha de atividades será acrescentada pelo grupo.
