'use strict';
const $ = (q) => document.querySelector(q);
const state = {user:null, page:'dashboard', sectors:[], partners:[], users:[], rows:[], editing:null};
const names = {dashboard:'Visão geral', records:'Registros ambientais', goals:'Metas', actions:'Ações corretivas', sectors:'Setores', partners:'Parceiros', reports:'Relatórios', audit:'Histórico de alterações', api:'Serviços e API'};
const metrics = {agua:'Água', energia:'Energia', residuos:'Resíduos'};
const units = {agua:'m³', energia:'kWh', residuos:'kg'};
const statuses = {aberta:'Aberta', em_andamento:'Em andamento', concluida:'Concluída'};
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = (v) => v == null ? 'Sem dados' : Number(v).toLocaleString('pt-BR',{maximumFractionDigits:3});
const dateLabel = (v) => v ? String(v).slice(0,10).split('-').reverse().join('/') : '';
function dateISO(value) {
  if (!value) return '';
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value.trim());
  if (!match) throw new Error('Informe a data no formato DD/MM/AAAA.');
  const [, day, month, year] = match;
  const date = new Date(Date.UTC(Number(year), Number(month)-1, Number(day)));
  if (date.getUTCFullYear()!==Number(year) || date.getUTCMonth()+1!==Number(month) || date.getUTCDate()!==Number(day)) {
    throw new Error('Informe uma data válida no formato DD/MM/AAAA.');
  }
  return `${year}-${month}-${day}`;
}
const canWrite = () => state.user?.role !== 'consulta';
const isManager = () => state.user?.role === 'gestor';

async function api(path, options={}) {
  const response = await fetch('/api'+path, {...options, headers:{'Content-Type':'application/json','X-CSRF-Token':state.user?.csrf || '',...options.headers}});
  if (!response.ok) {
    const body = await response.json().catch(()=>({detail:'Não foi possível ler a resposta do servidor.'}));
    if (response.status===401 && state.user) {state.user=null;showLogin();}
    throw new Error(body.detail || 'Não foi possível concluir a operação.');
  }
  return response.status===204 ? null : response.json();
}
function notify(message, error=false) {$('#notice').textContent=message;$('#notice').className=error?'error-notice':'';$('#notice').hidden=false;}
function showLogin() {$('#app').hidden=true;$('#login-screen').hidden=false;$('#password').value='';}
function query() {const p=new URLSearchParams();[['start','#filter-start'],['end','#filter-end']].forEach(([k,id])=>{if($(id).value)p.set(k,dateISO($(id).value));});if($('#filter-sector').value)p.set('sector_id',$('#filter-sector').value);return '?'+p.toString();}
function option(value,label,selected=false) {return `<option value="${esc(value)}" ${selected?'selected':''}>${esc(label)}</option>`;}
async function loadLookups() {
  [state.sectors,state.partners,state.users]=await Promise.all([api('/sectors'),api('/partners'),api('/users')]);
  const chosen=$('#filter-sector').value;
  $('#filter-sector').innerHTML=option('','Todos os setores')+state.sectors.map(s=>option(s.id,s.name,String(s.id)===chosen)).join('');
}
async function enter(user) {
  state.user=user;$('#login-screen').hidden=true;$('#app').hidden=false;
  $('#user-name').textContent=user.name;$('#user-role').textContent={gestor:'Gestor ambiental',operador:'Operador',consulta:'Somente consulta'}[user.role];
  document.querySelectorAll('.manager-only').forEach(el=>el.hidden=!isManager());
  await loadLookups();await navigate('dashboard');
}
$('#login-form').addEventListener('submit',async(e)=>{e.preventDefault();const button=e.target.querySelector('button');button.disabled=true;$('#login-error').textContent='';try{await enter(await api('/auth/login',{method:'POST',body:JSON.stringify({email:$('#email').value,password:$('#password').value})}));}catch(err){$('#login-error').textContent=err.message;}finally{button.disabled=false;}});
$('#logout').addEventListener('click',async()=>{try{await api('/auth/logout',{method:'POST'});state.user=null;showLogin();}catch(err){notify(err.message,true);}});
document.querySelectorAll('nav button').forEach(button=>button.addEventListener('click',()=>navigate(button.dataset.page)));
$('#apply-filter').addEventListener('click',()=>render().then(()=>{$('#notice').hidden=true;}).catch(err=>notify(err.message,true)));
async function navigate(page) {state.page=page;$('#page-title').textContent=names[page];$('#notice').hidden=true;document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('selected',b.dataset.page===page));$('#filters').hidden=!['dashboard','records','reports'].includes(page);try{await render();}catch(err){notify(err.message,true);}}
function empty() {return '<div class="empty">Nenhum registro encontrado.<br>Revise os filtros ou cadastre um novo item.</div>';}
function table(headers,rows) {return rows.length?`<div class="table-wrap"><table><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`:empty();}
function rowButtons(id,allow=true) {return allow?`<div class="row-actions"><button data-edit="${id}">Editar</button>${isManager()&&['records','goals','actions'].includes(state.page)?`<button data-delete="${id}" class="danger">Excluir</button>`:''}</div>`:'';}
function goalBadge(g) {if(g.actual==null)return '<span class="badge neutral">Sem registros</span>';return `<span class="badge ${g.actual>g.limit_value?'warning':''}">${g.actual>g.limit_value?'Limite excedido':'Dentro do limite'}</span>`;}
function toolbar(text,editable=true) {return `<div class="toolbar"><p>${text}</p>${editable?'<button id="new-item">Novo registro</button>':''}</div>`;}
function bindRows() {
 $('#new-item')?.addEventListener('click',()=>edit());
 document.querySelectorAll('[data-edit]').forEach(b=>b.addEventListener('click',()=>edit(state.rows.find(r=>r.id===Number(b.dataset.edit)))));
 document.querySelectorAll('[data-delete]').forEach(b=>b.addEventListener('click',async()=>{
   if(!confirm('Excluir este registro? A operação ficará no histórico.'))return;
   try{await api(`/${state.page}/${b.dataset.delete}`,{method:'DELETE'});await render();notify('Registro excluído.');}catch(err){notify(err.message,true);}
 }));
}
async function render() {
 const page=state.page, content=$('#content');
 if(page==='dashboard') {
   const [data,goals]=await Promise.all([api('/dashboard'+query()),api('/goals')]);
   const sector=$('#filter-sector').value;
   const selected=goals.filter(g=>!sector||String(g.sector_id)===sector);
   content.innerHTML=`<div class="stats">${Object.keys(metrics).map((m,i)=>`<article class="stat ${['water','energy','waste'][i]}"><p class="label">${m==='residuos'?'Resíduos gerados':'Consumo de '+metrics[m].toLowerCase()}</p><span class="value">${number(data.totals[m].total)}</span>${data.totals[m].total==null?'':`<span class="unit">${units[m]}</span>`}<small>${data.totals[m].count} registros no período selecionado</small></article>`).join('')}</div><div class="two-columns"><article class="panel"><div class="panel-heading"><h2>Acompanhamento de metas</h2><span class="badge neutral">${selected.length} metas</span></div><p class="note">Cada meta considera seu próprio período completo. O filtro de setor é aplicado.</p>${selected.length?selected.map(g=>`<div class="goal-row"><div><p>${esc(g.title)}</p><small>${dateLabel(g.start_date)} a ${dateLabel(g.end_date)} · ${number(g.actual)} / ${number(g.limit_value)} ${units[g.metric]}</small></div>${goalBadge(g)}</div>`).join(''):empty()}</article><article class="panel"><h2>Ações em acompanhamento</h2><div class="action-summary"><div><strong>${data.open_actions}</strong><small>em aberto</small></div><div><strong>${data.overdue_actions}</strong><small>com prazo vencido</small></div></div><p class="note">Todos os prazos, respeitando o setor escolhido. Ações concluídas saem da contagem de pendências.</p><div class="metrics-guide"><h3>Leitura dos indicadores</h3><p>Água em metros cúbicos, energia em quilowatt-hora e resíduos em quilogramas. Grandezas diferentes são acompanhadas separadamente.</p></div></article></div>`;
 } else if(page==='records'||page==='reports') {
   state.rows=await api('/records'+query());
   const reporting=page==='reports';
   const description=reporting?'Relatório dos registros filtrados. Exportação com os mesmos dados e unidades.':'Consumos do período e movimentações de resíduos. Quantidade é consumo, não leitura acumulada de medidor.';
   content.innerHTML=toolbar(description,!reporting&&canWrite())+(reporting?'<div class="toolbar"><button id="download-csv">Baixar CSV</button><button id="print-report" class="secondary">Imprimir relatório</button></div>':'')+`<div class="panel">${table(['Data','Indicador','Quantidade','Setor','Destinação / observação',...(reporting?[]:['Ações'])],state.rows.map(r=>[esc(dateLabel(r.date)),esc(metrics[r.metric]),`${number(r.quantity)} ${units[r.metric]}`,esc(r.sector_name),r.metric==='residuos'?`${esc(r.waste_type)} · ${esc(r.destination)}<br><small>${esc(r.partner_name)}${r.note?' · '+esc(r.note):''}</small>`:esc(r.note),...(reporting?[]:[rowButtons(r.id,canWrite())])]))}</div>`;
   if(reporting){$('#download-csv').onclick=()=>{try{location.href='/api/reports/records.csv'+query();}catch(err){notify(err.message,true);}};$('#print-report').onclick=()=>window.print();}
 } else if(page==='goals') {
   state.rows=await api('/goals');
   content.innerHTML=toolbar('Limites máximos por setor e período. Metas sobrepostas para o mesmo indicador não são permitidas.',isManager())+`<div class="panel">${table(['Meta','Setor / período','Realizado / limite','Situação','Ações'],state.rows.map(g=>[esc(g.title),`${esc(g.sector_name)}<br><small>${dateLabel(g.start_date)} a ${dateLabel(g.end_date)}</small>`,`${number(g.actual)} / ${number(g.limit_value)} ${units[g.metric]}`,goalBadge(g),rowButtons(g.id,isManager())]))}</div>`;
 } else if(page==='actions') {
   state.rows=await api('/actions');
   content.innerHTML=toolbar('Organize responsáveis e prazos. Para concluir uma ação, registre sua evidência.',canWrite())+`<div class="panel">${table(['Ação','Setor / responsável','Prazo','Situação','Ações'],state.rows.map(a=>[`${esc(a.title)}<br><small>${esc(a.description)}${a.evidence?'<br>Evidência: '+esc(a.evidence):''}</small>`,`${esc(a.sector_name)}<br><small>${esc(a.owner_name)}</small>`,dateLabel(a.due_date),`<span class="badge ${a.status==='concluida'?'':a.due_date<new Date().toLocaleDateString('sv-SE')?'warning':'neutral'}">${esc(statuses[a.status])}</span>`,rowButtons(a.id,canWrite())]))}</div>`;
 } else if(['sectors','partners'].includes(page)) {
   state.rows=await api('/'+page);
   content.innerHTML=toolbar('Cadastros inativos preservam o histórico e deixam de aceitar novos vínculos.',isManager())+`<div class="panel">${table(['Nome',...(page==='partners'?['Contato']:[]),'Situação','Ações'],state.rows.map(r=>[esc(r.name),...(page==='partners'?[esc(r.contact)]:[]),`<span class="badge ${r.active?'':'neutral'}">${r.active?'Ativo':'Inativo'}</span>`,rowButtons(r.id,isManager())]))}</div>`;
 } else if(page==='audit') {
   state.rows=await api('/audit');
   content.innerHTML='<p class="note">Histórico de criação, alteração e exclusão. Horários exibidos no fuso do navegador. Dados iniciais de demonstração não são alterações de usuários.</p>'+`<div class="panel">${table(['Data e hora','Usuário','Operação','Entidade','Detalhes'],state.rows.map(r=>[esc(new Date(r.timestamp).toLocaleString('pt-BR')),esc(r.user_name),esc(r.operation),esc(r.entity)+' #'+r.entity_id,`<details><summary>Ver alteração</summary><p>Antes: ${esc(r.before_json||'Não existia')}</p><p>Depois: ${esc(r.after_json||'Excluído')}</p></details>`]))}</div>`;
 } else if(page==='api') {
   const spec=await api('/openapi.json');
   content.innerHTML=`<article class="panel"><h2>Contrato dos serviços</h2><p class="note">Interface web e API comunicam-se por HTTP e JSON. Escritas autenticadas exigem cookie de sessão e cabeçalho X-CSRF-Token. O contrato abaixo vem do servidor em execução.</p><p><a href="/api/openapi.json" target="_blank" rel="noopener">Abrir contrato OpenAPI em JSON</a></p>${Object.entries(spec.paths).flatMap(([path,methods])=>Object.entries(methods).map(([method,op])=>`<div class="api-row"><strong>${esc(method.toUpperCase())}</strong><div><code>${esc(path)}</code><br><small>${esc(op.summary)}</small></div></div>`)).join('')}</article>`;
 }
 bindRows();
}

function field(name,label,type='text',value='',options=null,wide=false) {
 const id='field-'+name;
 let control;
 if(options)control=`<select id="${id}" name="${name}">${options.map(([v,l])=>option(v,l,String(v)===String(value))).join('')}</select>`;
 else if(type==='textarea')control=`<textarea id="${id}" name="${name}" maxlength="2000">${esc(value)}</textarea>`;
 else control=`<input id="${id}" name="${name}" type="${type==='date'?'text':type}" value="${esc(type==='date'?dateLabel(value):value)}" ${type==='date'?'inputmode="numeric" placeholder="DD/MM/AAAA" pattern="[0-9]{2}/[0-9]{2}/[0-9]{4}"':''} ${type==='number'?'min="0.001" max="1000000000" step="any"':''} ${['note','contact','evidence'].includes(name)?'':'required'} maxlength="${type==='date'?10:2000}">`;
 return `<label class="${wide?'wide':''}">${esc(label)}${control}</label>`;
}
function edit(row={}) {
 state.editing=row.id||null;$('#editor-title').textContent=(row.id?'Editar ':'Novo ')+({records:'registro ambiental',goals:'objetivo ambiental',actions:'plano de ação',sectors:'setor',partners:'parceiro'}[state.page]);
 const sectors=state.sectors.filter(s=>s.active||s.id===row.sector_id).map(s=>[s.id,s.name+(s.active?'':' (inativo)')]);
 const partners=[['','Selecione'],...state.partners.filter(p=>p.active||p.id===row.partner_id).map(p=>[p.id,p.name+(p.active?'':' (inativo)')])];
 const metricOptions=Object.entries(metrics);let fields='';
 if(state.page==='records') {
   fields=field('metric','Indicador','text',row.metric||'agua',metricOptions)+field('date','Data do consumo ou coleta','date',row.date||new Date().toLocaleDateString('sv-SE'))+field('quantity','Quantidade na unidade do indicador','number',row.quantity||'')+field('sector_id','Setor','text',row.sector_id||'',sectors)+field('partner_id','Parceiro de destinação','text',row.partner_id||'',partners)+field('waste_type','Tipo de resíduo','text',row.waste_type||'')+field('destination','Destinação','text',row.destination||'')+field('note','Observação','textarea',row.note||'',null,true);
 } else if(state.page==='goals') {
   fields=field('title','Título','text',row.title||'',null,true)+field('metric','Indicador','text',row.metric||'agua',metricOptions)+field('sector_id','Setor','text',row.sector_id||'',sectors)+field('start_date','Início','date',row.start_date||'')+field('end_date','Fim','date',row.end_date||'')+field('limit_value','Limite na unidade do indicador','number',row.limit_value||'');
 } else if(state.page==='actions') {
   fields=field('title','Título','text',row.title||'',null,true)+field('description','Descrição da ação','textarea',row.description||'',null,true)+field('sector_id','Setor','text',row.sector_id||'',sectors)+field('owner_id','Responsável','text',row.owner_id||'',state.users.filter(u=>u.role!=='consulta').map(u=>[u.id,u.name]))+field('due_date','Prazo','date',row.due_date||'')+field('status','Situação','text',row.status||'aberta',Object.entries(statuses))+field('evidence','Evidência de conclusão','textarea',row.evidence||'',null,true);
 } else {
   fields=field('name','Nome','text',row.name||'',null,true)+(state.page==='partners'?field('contact','Contato','text',row.contact||'',null,true):'')+field('active','Situação','text',row.active===0?'0':'1',[['1','Ativo'],['0','Inativo']]);
 }
 $('#fields').innerHTML=fields;$('#form-error').textContent='';
 if(state.page==='records') {
   const toggle=()=>{const waste=$('#field-metric').value==='residuos';['partner_id','waste_type','destination'].forEach(n=>{const el=$('#field-'+n);el.closest('label').hidden=!waste;el.required=waste;});};$('#field-metric').onchange=toggle;toggle();
 }
 if(state.page==='actions') {const toggle=()=>{$('#field-evidence').required=$('#field-status').value==='concluida';$('#field-evidence').closest('label').hidden=$('#field-status').value!=='concluida';};$('#field-status').onchange=toggle;toggle();}
 $('#editor').showModal();
}
$('#close-editor').onclick=$('#cancel-editor').onclick=()=>$('#editor').close();
$('#edit-form').addEventListener('submit',async(e)=>{
 e.preventDefault();const payload=Object.fromEntries(new FormData(e.target));
 ['sector_id','partner_id','owner_id','quantity','limit_value'].forEach(k=>{if(k in payload)payload[k]=payload[k]?Number(payload[k]):null;});
 if('active' in payload)payload.active=payload.active==='1';
 if(state.page==='records'&&payload.metric!=='residuos'){payload.partner_id=null;payload.waste_type='';payload.destination='';}
 if(state.page==='actions'&&payload.status!=='concluida')payload.evidence='';
 $('#save-button').disabled=true;$('#form-error').textContent='';
 try{for(const key of ['date','start_date','end_date','due_date'])if(key in payload)payload[key]=dateISO(payload[key]);await api('/'+state.page+(state.editing?'/'+state.editing:''),{method:state.editing?'PUT':'POST',body:JSON.stringify(payload)});$('#editor').close();await loadLookups();await render();notify('Registro salvo com sucesso.');}catch(err){$('#form-error').textContent=err.message;}finally{$('#save-button').disabled=false;}
});
api('/auth/me').then(enter).catch(()=>showLogin());
