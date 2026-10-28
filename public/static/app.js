'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels = {altura:'Trabalho em Altura',confinado:'Espaço Confinado',eletricidade:'Eletricidade',quente:'Trabalho a Quente'};
const colors = {altura:'#0077B6',confinado:'#6D4C9F',eletricidade:'#C98A00',quente:'#D6293B'};
const roles = {emitente:'Emitente / Técnico de Segurança',executante:'Executante Responsável',supervisor:'Responsável pela Área'};
const states = {aberta:'Aberta',encerrada:'Encerrada',cancelada:'Cancelada'};
const St = {user:null,csrf:'',catalog:null,view:'home',items:[],record:null,total:0,page:1,
  category:'todas',status:'todas',search:'',form:null,error:'',busy:false,stream:null,photo:null,canvas:null,
  modalRole:null,cameraGeneration:0,listGeneration:0,history:[],draftAvailable:false,searchTimer:null};
const time = value => value ? new Intl.DateTimeFormat('pt-BR',{dateStyle:'short',timeStyle:'short',timeZone:'America/Sao_Paulo'}).format(new Date(value)) : '—';
const localTime = value => value ? value.split('T').reverse().join(' · ') : '—';
const canWrite = () => St.user && ['admin','operador'].includes(St.user.role);
const draftKey = () => 'pts-draft-v1:' + St.user.username;
function toast(message){const el=$('#toast');el.textContent=message;el.classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.classList.remove('show'),4500);}
async function api(path, options={}){
  const headers = {'X-CSRF-Token':St.csrf,...options.headers};
  if(options.body) headers['Content-Type']='application/json';
  const response=await fetch(path,{...options,headers,cache:'no-store',credentials:'same-origin'});
  const data=await response.json().catch(()=>({erro:'Resposta inesperada do servidor.'}));
  if(!response.ok){
    if(response.status===401 && !path.endsWith('/login')) {clearSensitive();St.user=null;renderLogin();}
    throw new Error(data.erro || 'Não foi possível concluir a operação.');
  }
  return data;
}
function bar(title,back=false){return `<header class="appbar"><div class="appbar-row">${back?'<button class="back-btn" data-action="home" aria-label="Voltar à lista">←</button>':''}<div><div class="appbar-title">🦺 ${esc(title)}</div><div class="appbar-sub">${esc(St.user?.name || 'Permissão de Trabalho Seguro')}${St.user?' · '+esc(St.user.role):''}</div></div>${St.user?'<button class="btn-link" data-action="logout">Sair</button>':''}</div></header><div class="hazard-rule"></div>`;}
function mount(html){$('#app').innerHTML=html;$('#app').setAttribute('aria-busy','false');associateLabels();}
function associateLabels(){document.querySelectorAll('.field').forEach((field,i)=>{const label=$('label',field),input=$('input,textarea,select',field);if(label&&input){input.id ||= 'field-'+i;label.htmlFor=input.id;}});}
function renderLogin(configured=true){
  mount(bar('PTS')+`<div class="content login"><div class="section"><div class="login-logo" aria-hidden="true">🦺</div><h1 class="detail-title">Permissão de Trabalho Seguro</h1><p class="small">Protótipo acadêmico · UNIVESP</p>${!configured?'<div class="notice">O acesso ainda não foi configurado. No computador do projeto, execute <code>python manage.py setup</code> e reinicie o servidor.</div>':''}<form id="loginForm"><div class="field"><label>Usuário</label><input name="username" autocomplete="username" maxlength="100" required autocapitalize="none"></div><div class="field"><label>Senha</label><input name="password" type="password" autocomplete="current-password" maxlength="256" required></div><button class="btn-primary" type="submit" ${configured?'':'disabled'}>Entrar</button><p id="loginError" class="submit-error" role="alert"></p></form></div><p class="small">Acesso restrito à equipe. Fotografias associadas às assinaturas não constituem reconhecimento biométrico.</p></div>`);
}
async function init(){
  try{
    const data=await api('/api/auth/session');St.csrf=data.csrf;St.user=data.user;
    if(!St.user){renderLogin(data.configured);return;}
    await startSession();
  }catch(error){mount(bar('PTS')+`<div class="content"><div class="notice error" role="alert">${esc(error.message)}</div><button class="btn-secondary" data-action="reload">Tentar novamente</button></div>`);}
}
async function startSession(){
  St.catalog=await api('/api/catalogo');
  try{St.draftAvailable=!!sessionStorage.getItem(draftKey());}catch{}
  await loadList();
}
async function loadList(){
  const generation=++St.listGeneration;
  const params=new URLSearchParams({page:St.page,limit:20,categoria:St.category,status:St.status,q:St.search});
  try{const result=await api('/api/pts?'+params);if(generation!==St.listGeneration||!St.user)return;St.items=result.items;St.total=result.total;St.error='';}
  catch(error){if(generation!==St.listGeneration||!St.user)return;St.error=error.message;}
  if(St.view==='home') renderHome();
}
function renderHome(){
  const focus=document.activeElement?.id==='search';const caret=focus?$('#search').selectionStart:0;
  mount(bar('PTS')+`<div class="content"><div class="list-toolbar">${canWrite()?'<button class="btn-primary" data-action="new">＋ Nova PTS</button>':''}<button class="btn-secondary" data-action="refresh">Atualizar</button></div>${St.draftAvailable&&canWrite()?'<div class="notice">Há um rascunho nesta aba, sem fotos nem assinaturas. <button class="btn-link" data-action="restore-draft">Retomar</button><button class="btn-link" data-action="discard-draft">Descartar</button></div>':''}<div class="search-box"><input id="search" type="search" aria-label="Buscar por local, número ou empresa" placeholder="Local, número ou empresa" value="${esc(St.search)}" maxlength="200"></div><div class="chip-row" aria-label="Categoria">${[['todas','Todas'],...Object.entries(labels)].map(([key,label])=>`<button class="chip ${St.category===key?'active':''}" data-action="filter-category" data-value="${key}" aria-pressed="${St.category===key}">${label}</button>`).join('')}</div><div class="chip-row" aria-label="Status">${[['todas','Todos os status'],...Object.entries(states)].map(([key,label])=>`<button class="chip ${St.status===key?'active':''}" data-action="filter-status" data-value="${key}" aria-pressed="${St.status===key}">${label}</button>`).join('')}</div>${St.error?`<div class="notice error" role="alert">${esc(St.error)}<button class="btn-link" data-action="refresh">Tentar novamente</button></div>`:`<p class="small">${St.total} permissão(ões) encontrada(s)</p>${St.items.map(r=>`<button class="pts-card" style="--cat-color:${colors[r.categoria]}" data-action="detail" data-id="${esc(r.id)}"><div class="pts-card-top"><div><div class="pts-num mono">${esc(r.numero)}</div><div class="pts-local">${esc(r.local)}</div><div class="pts-cat-label">${esc(labels[r.categoria])}</div></div><span class="status-badge status-${esc(r.status)}">${esc(states[r.status])}</span></div><div class="pts-meta"><span>${esc(r.empresa)}</span><span>${time(r.createdAt)}</span></div></button>`).join('')}${!St.items.length?'<div class="empty-state"><b>Nenhuma PTS encontrada</b>Altere os filtros ou crie uma permissão.</div>':''}<div class="list-toolbar"><button class="btn-secondary" data-action="previous" ${St.page<=1?'disabled':''}>Anterior</button><span class="small">Página ${St.page} de ${Math.max(1,Math.ceil(St.total/20))}</span><button class="btn-secondary" data-action="next" ${St.page*20>=St.total?'disabled':''}>Próxima</button></div>`}</div>`);
  if(focus&&$('#search')){$('#search').focus();$('#search').setSelectionRange?.(caret,caret);}
}
function newForm(){
  const parts=new Intl.DateTimeFormat('sv-SE',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date()).replace(' ','T');
  return {categoria:null,dataEmissao:St.catalog.hoje,local:'',empresa:'',descricao:'',equipe:'',validadeInicio:parts,validadeFim:'',checklistRisco:{},checklistEpi:{},assinaturas:{emitente:null,executante:null,supervisor:null},contatosEnvio:Array.from({length:3},()=>({tipo:'email',valor:''})),requestId:crypto.randomUUID()};
}
function persistDraft(){
  if(!St.form||!St.user)return;
  // Rascunho temporário por aba: nunca persiste evidências, senhas ou tokens.
  const {assinaturas,requestId,...fields}=St.form;
  try{sessionStorage.setItem(draftKey(),JSON.stringify(fields));St.draftAvailable=true;}catch{}
}
function removeDraft(){try{sessionStorage.removeItem(draftKey());}catch{}St.draftAvailable=false;}
function invalidateSignatures(){
  if(!St.form)return;
  if(Object.values(St.form.assinaturas).some(Boolean)){
    St.form.assinaturas={emitente:null,executante:null,supervisor:null};
    $('#signatures') && ($('#signatures').innerHTML=renderSignatures());
    toast('Dados alterados. Colete novamente as três assinaturas.');
  }
}
function readiness(){
  const f=St.form,missing=[];
  if(!f?.categoria)return ['categoria'];
  for(const [key,label] of [['local','local'],['empresa','empresa'],['descricao','descrição'],['equipe','equipe'],['dataEmissao','emissão'],['validadeInicio','início da validade'],['validadeFim','fim da validade']]) if(!f[key]?.trim())missing.push(label);
  if(f.validadeInicio&&f.validadeFim&&f.validadeInicio>=f.validadeFim) missing.push('validade em ordem cronológica');
  if(f.dataEmissao!==St.catalog.hoje||f.validadeInicio?.slice(0,10)!==f.dataEmissao)missing.push('emissão e início na data de hoje');
  const epi=St.catalog.epi.every((_,i)=>f.checklistEpi[i]===true),risk=St.catalog.checklists[f.categoria].every((_,i)=>f.checklistRisco[i]===true);
  if(!epi||!risk)missing.push('checklist completo');
  if(!Object.keys(roles).every(role=>f.assinaturas[role]))missing.push('três assinaturas');
  return missing;
}
function updateReady(){
  const button=$('#emit');if(!button)return;
  const missing=readiness();button.disabled=!!missing.length||St.busy;
  $('#pending').textContent=missing.length?'Pendente: '+missing.join(' · '):'Dados completos. Pronto para emitir.';
}
function inputField(key,label,type='text',limit=300){const f=St.form;return `<div class="field"><label>${label}</label><input type="${type}" name="${key}" value="${esc(f[key])}" maxlength="${limit}" required ${key==='dataEmissao'?'readonly':''}></div>`;}
function renderSignatures(){return Object.entries(roles).map(([role,label])=>{const sig=St.form.assinaturas[role];return `<div class="sig-block"><div class="sig-role">${label}</div>${sig?`<div class="sig-preview"><div class="face-img-wrap"><img src="${esc(sig.foto)}" alt="Foto de ${esc(sig.nome)}"></div><div class="sig-img-wrap"><img src="${esc(sig.imagem)}" alt="Assinatura de ${esc(sig.nome)}"></div><div class="sig-info"><b>${esc(sig.nome)}</b>Fotografia associada à assinatura<br>${time(sig.dataHora)}</div></div>`:''}<button type="button" class="btn-sign ${sig?'signed':''}" data-action="sign" data-role="${role}">${sig?'Refazer assinatura':'Fotografar e assinar'}</button></div>`;}).join('');}
function renderForm(){
  const f=St.form;
  mount(bar('Nova PTS',true)+`<div class="content"><div class="notice">A emissão exige todos os dados, o checklist e três assinaturas com foto. Alterações posteriores no formulário exigem novas assinaturas.</div><div class="section"><h2 class="section-title">1 · Categoria de risco</h2><div class="cat-grid">${Object.entries(labels).map(([key,label])=>`<button type="button" class="cat-card ${f.categoria===key?'sel':''}" style="--cat-color:${colors[key]}" data-action="choose-category" data-value="${key}" aria-pressed="${f.categoria===key}"><span class="cat-name">${label}</span></button>`).join('')}</div></div>${f.categoria?`<form id="permitForm" novalidate><section class="section"><h2 class="section-title">2 · Dados gerais</h2><p class="small">O número será atribuído pelo servidor após a emissão. Horários de São Paulo.</p><div class="row2">${inputField('dataEmissao','Data de emissão','date')}${inputField('empresa','Empresa executante','text',200)}</div>${inputField('local','Local / Setor')}<div class="row2">${inputField('validadeInicio','Validade — início','datetime-local')}${inputField('validadeFim','Validade — fim','datetime-local')}</div>${[['descricao','Descrição do trabalho',5000],['equipe','Equipe executante (um nome por linha)',3000]].map(([key,label,limit])=>`<div class="field"><label>${label}</label><textarea name="${key}" maxlength="${limit}" required>${esc(f[key])}</textarea></div>`).join('')}</section><section class="section"><h2 class="section-title">3 · Checklist de segurança</h2>${[['epi','EPIs',St.catalog.epi,'checklistEpi'],['risco','Específico da categoria',St.catalog.checklists[f.categoria],'checklistRisco']].map(([key,label,items,field])=>`<h3 class="small">${label}</h3>${items.map((item,i)=>`<label class="check-item"><input type="checkbox" data-check="${field}" data-index="${i}" ${f[field][i]?'checked':''}><span class="check-label">${esc(item)}</span></label>`).join('')}`).join('')}<p class="small">Catálogo ${esc(St.catalog.versao)} · checklist do protótipo sujeito a revisão técnica.</p></section><section class="section"><h2 class="section-title">4 · Assinaturas</h2><p class="small">Fotografia como evidência visual; sem comparação biométrica automatizada.</p><div id="signatures">${renderSignatures()}</div></section><section class="section"><h2 class="section-title">5 · Contatos (opcional, até três)</h2>${f.contatosEnvio.map((c,i)=>`<div class="contact-row"><select aria-label="Canal do contato ${i+1}" data-contact="${i}" data-field="tipo"><option value="email" ${c.tipo==='email'?'selected':''}>E-mail</option><option value="whatsapp" ${c.tipo==='whatsapp'?'selected':''}>WhatsApp</option></select><input type="${c.tipo==='email'?'email':'tel'}" aria-label="Contato ${i+1}" data-contact="${i}" data-field="valor" maxlength="254" placeholder="${c.tipo==='email'?'nome@empresa.com':'País, DDD e número'}" value="${esc(c.valor)}"></div>`).join('')}<p class="small">No compartilhamento manual, escolha o destinatário no aplicativo de destino e confira o anexo.</p></section><div class="sticky-footer"><button id="emit" type="submit" class="btn-primary">Emitir PTS</button><p id="pending" class="footer-hint" aria-live="polite"></p><p id="submitError" class="submit-error" role="alert"></p></div></form>`:'<p class="footer-hint">Selecione a categoria para continuar.</p>'}</div>`);
  updateReady();
}
function kv(label,value){return `<div class="kv"><span class="k">${esc(label)}</span><span class="v">${esc(value||'—')}</span></div>`;}
function readSignature(label,sig){return `<div class="sig-block"><div class="sig-role">${esc(label)}</div>${sig?`<div class="sig-preview">${sig.foto?`<div class="face-img-wrap"><img src="${esc(sig.foto)}" alt="Fotografia de ${esc(sig.nome)}" loading="lazy"></div>`:''}${sig.imagem?`<div class="sig-img-wrap"><img src="${esc(sig.imagem)}" alt="Assinatura de ${esc(sig.nome)}" loading="lazy"></div>`:''}<div class="sig-info"><b>${esc(sig.nome)}</b>Recebida: ${sig.legado?'não registrado no protótipo anterior':time(sig.recebidaEm||sig.dataHora)}${sig.dataHoraDispositivo?'<br>Dispositivo: '+time(sig.dataHoraDispositivo):''}</div></div>`:'Sem evidência registrada'}</div>`;}
function renderDetail(){
  const r=St.record;
  if(!r)return;
  const snapshot=r.checklistTextos||{epi:St.catalog.epi,risco:St.catalog.checklists[r.categoria]};
  const expired=r.status==='aberta'&&r.validadeFim&&new Date(r.validadeFim+'-03:00').getTime()<Date.now();
  const events={emissao:'Emissão',encerramento:'Encerramento',cancelamento:'Cancelamento',envio_solicitado:'Envio solicitado',envio_aceito_provedor:'Envio aceito pelo provedor (entrega não confirmada)',envio_falhou:'Falha no envio',importacao_legado:'Importação do protótipo anterior'};
  mount(bar('Detalhes da PTS',true)+`<div class="content"><div class="detail-header" style="--cat-color:${colors[r.categoria]}"><div class="detail-num">${esc(r.numero)}</div><h1 class="detail-title">${esc(r.local)}</h1><div class="detail-cat">${esc(labels[r.categoria])} · ${esc(states[r.status])}</div></div>${expired?'<div class="notice">Validade vencida. Esta permissão não deve ser usada para iniciar ou continuar atividades.</div>':''}${r.legado?'<div class="notice">Registro legado importado. Evidências e datas anteriores não foram verificadas retroativamente.</div>':''}<section class="section"><h2 class="section-title">Dados gerais</h2>${kv('Empresa',r.empresa)}${kv('Emissão',r.dataEmissao)}${kv('Validade — início',localTime(r.validadeInicio))}${kv('Validade — fim',localTime(r.validadeFim))}${kv('Fuso horário',r.fuso||'America/Sao_Paulo')}${kv('Registrada por',r.criadaPor)}${kv('Recebida pelo servidor',time(r.createdAt))}</section><section class="section"><h2 class="section-title">Descrição do trabalho</h2><p style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(r.descricao)}</p><h2 class="section-title">Equipe executante</h2><p style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(r.equipe)}</p></section><section class="section"><h2 class="section-title">Checklist · ${esc(r.checklistVersao||'legado')}</h2>${[['EPIs',snapshot.epi,r.checklistEpi],['Específico',snapshot.risco,r.checklistRisco]].map(([title,items,map])=>`<h3 class="small">${title}</h3>${items.map((item,i)=>`<p class="check-readonly">${map?.[i]===true?'☑':'☐'} ${esc(item)}</p>`).join('')}`).join('')}</section><section class="section"><h2 class="section-title">Assinaturas e fotografias</h2>${Object.entries(roles).map(([key,label])=>readSignature(label,r.assinaturas?.[key])).join('')}<p class="small">Evidências visuais associadas; sem reconhecimento biométrico.</p></section>${r.encerramento?`<section class="section">${readSignature('Encerramento',r.encerramento)}<p style="white-space:pre-wrap">${esc(r.encerramento.observacoes)}</p></section>`:''}${r.cancelamento?`<section class="section"><h2 class="section-title">Cancelamento</h2>${kv('Responsável',r.cancelamento.autor)}${kv('Data',time(r.cancelamento.dataHora))}<p>${esc(r.cancelamento.motivo)}</p></section>`:''}<section class="section"><h2 class="section-title">Documento e compartilhamento</h2><button class="btn-primary" data-action="pdf">Baixar PDF</button><button class="btn-secondary" data-action="share">Compartilhar PDF</button><p class="small">Escolha o aplicativo e o destinatário. Quando o compartilhamento de arquivos não estiver disponível, baixe o PDF e anexe manualmente.</p>${(r.contatosEnvio||[]).map((c,i)=>c.valor?`<div>${kv(c.tipo==='email'?'E-mail':'WhatsApp',c.valor)}<button class="btn-secondary" data-action="contact" data-index="${i}">Abrir ${c.tipo==='email'?'e-mail':'WhatsApp'} com mensagem</button>${St.catalog.autoSend&&canWrite()?`<button class="btn-secondary" data-action="auto-send" data-index="${i}">Solicitar envio pelo servidor</button>`:''}</div>`:'').join('')}</section>${r.status==='aberta'&&canWrite()?'<button class="btn-primary" data-action="close">Encerrar PTS</button>':''}${r.status==='aberta'&&St.user.role==='admin'?'<button class="btn-danger-outline" data-action="cancel">Cancelar com motivo</button>':''}<section class="section" style="margin-top:14px"><h2 class="section-title">Histórico</h2><ul class="history">${St.history.map(event=>`<li><b>${esc(events[event.action]||event.action)}</b><br>${esc(event.actor)} · ${time(event.at)}${event.details.motivo?'<br>'+esc(event.details.motivo):''}</li>`).join('')}</ul></section></div>`);
}
async function openDetail(id){
  const generation=++St.listGeneration;
  const [record,history]=await Promise.all([api('/api/pts/'+id),api('/api/pts/'+id+'/historico')]);
  if(generation!==St.listGeneration||!St.user)return;
  St.record=record;St.history=history;St.view='detail';renderDetail();window.scrollTo(0,0);
}
function stopCamera(){St.cameraGeneration++;if(St.stream)St.stream.getTracks().forEach(track=>track.stop());St.stream=null;}
function closeModal(){stopCamera();St.photo=null;St.canvas=null;St.modalRole=null;$('#sigOverlay')?.remove();document.body.classList.remove('modal-open');St.lastFocus?.focus();}
function fitCanvas(){
  const state=St.canvas;if(!state)return;
  const old=document.createElement('canvas');old.width=state.el.width;old.height=state.el.height;old.getContext('2d').drawImage(state.el,0,0);
  const rect=state.el.getBoundingClientRect(),ratio=Math.min(devicePixelRatio||1,2);
  state.el.width=Math.round(rect.width*ratio);state.el.height=Math.round(rect.height*ratio);
  state.ctx=state.el.getContext('2d');state.ctx.setTransform(ratio,0,0,ratio,0,0);
  state.ctx.lineWidth=2.4;state.ctx.lineCap='round';state.ctx.lineJoin='round';state.ctx.strokeStyle='#191D25';
  if(state.length>0)state.ctx.drawImage(old,0,0,old.width,old.height,0,0,rect.width,rect.height);
  state.drawing=false;
}
function initCanvas(){
  const el=$('#sigCanvas');St.canvas={el,ctx:null,drawing:false,length:0,last:null};fitCanvas();
  const position=e=>{const box=el.getBoundingClientRect();return [e.clientX-box.left,e.clientY-box.top];};
  el.addEventListener('pointerdown',e=>{if(e.button!==0)return;St.canvas.drawing=true;St.canvas.last=position(e);el.setPointerCapture(e.pointerId);e.preventDefault();});
  el.addEventListener('pointermove',e=>{const state=St.canvas;if(!state?.drawing)return;const point=position(e);state.ctx.beginPath();state.ctx.moveTo(...state.last);state.ctx.lineTo(...point);state.ctx.stroke();state.length+=Math.hypot(point[0]-state.last[0],point[1]-state.last[1]);state.last=point;});
  for(const type of ['pointerup','pointercancel','lostpointercapture'])el.addEventListener(type,()=>{if(St.canvas)St.canvas.drawing=false;});
}
async function openSignature(role){
  if(!canWrite()||St.modalRole)return;
  St.lastFocus=document.activeElement;St.modalRole=role;St.photo=null;
  const overlay=document.createElement('div');overlay.className='modal-overlay';overlay.id='sigOverlay';
  overlay.innerHTML=`<section class="modal-sheet" role="dialog" aria-modal="true" aria-labelledby="sigTitle"><h2 class="modal-title" id="sigTitle">${esc(roles[role]||'Encerramento da PTS')}</h2><p class="small">Capture uma fotografia do signatário e sua assinatura. A foto é uma evidência visual, sem comparação biométrica.</p><div class="field"><label for="sigName">Nome completo do signatário</label><input id="sigName" type="text" maxlength="120" autocomplete="off" required></div>${role==='encerramento'?'<div class="field"><label for="sigObs">Observações de encerramento</label><textarea id="sigObs" maxlength="5000"></textarea></div>':''}<div class="face-wrap"><video id="faceVideo" autoplay playsinline muted></video><img id="facePreview" class="hidden" alt="Fotografia capturada"></div><button class="btn-face" id="capture" data-action="capture" disabled>Capturar foto</button><button class="btn-face hidden" id="retake" data-action="retake">Repetir foto</button><p id="cameraStatus" class="face-status" role="status">Solicitando acesso à câmera…</p><label for="sigCanvas">Desenhe sua assinatura</label><canvas id="sigCanvas" aria-label="Área para desenhar assinatura"></canvas><div class="canvas-actions"><button class="btn-clear" data-action="clear-signature">Limpar</button><button class="btn-primary" data-action="confirm-signature">Confirmar</button></div><p id="sigError" class="submit-error" role="alert"></p><button class="btn-close-modal" data-action="dismiss-modal">Cancelar</button></section>`;
  document.body.appendChild(overlay);document.body.classList.add('modal-open');initCanvas();$('#sigName').focus();
  const generation=++St.cameraGeneration;
  try{
    if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia)throw new Error('A câmera precisa de HTTPS. No computador, use localhost; no celular, use o endereço HTTPS publicado.');
    const stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:640},height:{ideal:480}},audio:false});
    if(generation!==St.cameraGeneration||!St.modalRole){stream.getTracks().forEach(track=>track.stop());return;}
    St.stream=stream;const video=$('#faceVideo');video.srcObject=stream;await video.play();
    if(generation!==St.cameraGeneration)return;
    $('#capture').disabled=false;$('#cameraStatus').textContent='Posicione o rosto e capture a fotografia.';
  }catch(error){if(generation===St.cameraGeneration&&$('#cameraStatus'))$('#cameraStatus').textContent=error.message.includes('HTTPS')?error.message:'Não foi possível acessar a câmera. Autorize o acesso nas configurações do navegador e abra esta tela novamente.';}
}
function capture(){
  const video=$('#faceVideo');if(!video?.videoWidth)throw new Error('Aguarde a câmera carregar.');
  const canvas=document.createElement('canvas');const scale=Math.min(640/video.videoWidth,480/video.videoHeight,1);
  canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
  St.photo=canvas.toDataURL('image/jpeg',.78);$('#facePreview').src=St.photo;$('#facePreview').classList.remove('hidden');video.classList.add('hidden');$('#capture').classList.add('hidden');$('#retake').classList.remove('hidden');$('#cameraStatus').textContent='Foto capturada. Confira a imagem antes de confirmar.';
}
async function confirmSignature(){
  const nome=$('#sigName').value.trim();if(!nome)throw new Error('Informe o nome do signatário.');
  if(!St.photo)throw new Error('Capture a fotografia antes de confirmar.');
  if(!St.canvas||St.canvas.length<40)throw new Error('Desenhe a assinatura; um simples toque não é suficiente.');
  // Exporta em resolução limitada mesmo em aparelhos com alta densidade de pixels.
  const source=St.canvas.el,output=document.createElement('canvas');output.width=640;output.height=Math.round(640*source.height/source.width);
  const ctx=output.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,output.width,output.height);ctx.drawImage(source,0,0,output.width,output.height);
  const sig={nome,imagem:output.toDataURL('image/png'),foto:St.photo,dataHora:Date.now()};
  if(St.modalRole==='encerramento'){
    sig.observacoes=$('#sigObs').value.trim();
    await api('/api/pts/'+St.record.id+'/encerrar',{method:'PUT',body:JSON.stringify(sig)});
    const id=St.record.id;closeModal();await openDetail(id);toast('PTS encerrada.');
  }else{
    St.form.assinaturas[St.modalRole]=sig;closeModal();$('#signatures').innerHTML=renderSignatures();updateReady();toast('Assinatura e fotografia associadas.');
  }
}
async function getPdf(){
  const response=await fetch('/api/pts/'+St.record.id+'/pdf',{cache:'no-store'});
  if(!response.ok){const data=await response.json();throw new Error(data.erro||'Não foi possível gerar o PDF.');}
  return response.blob();
}
function download(blob){const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=St.record.numero+'.pdf';document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60_000);}
async function share(){
  const blob=await getPdf(),file=new File([blob],St.record.numero+'.pdf',{type:'application/pdf'});
  if(navigator.canShare?.({files:[file]})){
    // Uma segunda ação explícita mantém a ativação exigida pelo Safari após o download.
    const button=document.createElement('button');button.className='btn-primary';button.textContent='PDF pronto — escolher aplicativo';button.dataset.action='share-ready';
    $('#shareReady')?.remove();button.id='shareReady';$('#app .content').prepend(button);button.focus();
    button.addEventListener('click',async()=>{button.disabled=true;try{await navigator.share({files:[file],title:file.name});button.remove();}catch(error){if(error.name!=='AbortError')toast('Baixe o PDF e anexe manualmente.');}finally{button.disabled=false;}});
    toast('PDF pronto. Toque em “escolher aplicativo”.');
  }else{download(blob);toast('PDF baixado. Anexe o arquivo no e-mail ou WhatsApp.');}
}
function clearSensitive(){closeModal();St.listGeneration++;clearTimeout(St.searchTimer);St.items=[];St.record=null;St.history=[];St.form=null;St.catalog=null;}
async function home(){
  if(St.form){if(Object.values(St.form.assinaturas).some(Boolean)&&!confirm('Voltar à lista? O rascunho preserva os dados, mas as fotos e assinaturas serão descartadas.'))return;persistDraft();}
  clearTimeout(St.searchTimer);St.listGeneration++;St.form=null;St.record=null;St.view='home';await loadList();window.scrollTo(0,0);
}
async function action(name,button){
  if(name==='reload'){location.reload();return;}
  if(name==='home'){await home();return;}
  if(name==='logout'){if(St.form&&!confirm('Sair e descartar o rascunho desta aba?'))return;await api('/api/auth/logout',{method:'POST'});removeDraft();clearSensitive();St.user=null;await init();return;}
  if(name==='refresh'){St.page=1;await loadList();return;}
  if(name==='new'){if(!canWrite())return;St.catalog=await api('/api/catalogo');St.form=newForm();St.view='form';renderForm();window.scrollTo(0,0);return;}
  if(name==='restore-draft'){
    St.catalog=await api('/api/catalogo');
    const saved=JSON.parse(sessionStorage.getItem(draftKey())||'null');if(!saved)return;
    St.form={...newForm(),...saved,assinaturas:{emitente:null,executante:null,supervisor:null}};
    if(!labels[St.form.categoria])St.form.categoria=null;
    St.view='form';renderForm();toast('Rascunho retomado. Confira a validade e colete novas assinaturas.');return;
  }
  if(name==='discard-draft'){removeDraft();renderHome();return;}
  if(name==='filter-category'||name==='filter-status'){St[name==='filter-category'?'category':'status']=button.dataset.value;St.page=1;await loadList();return;}
  if(name==='previous'||name==='next'){St.page+=name==='next'?1:-1;await loadList();return;}
  if(name==='detail'){await openDetail(button.dataset.id);return;}
  if(name==='choose-category'){
    if(St.form.categoria===button.dataset.value)return;invalidateSignatures();St.form.categoria=button.dataset.value;St.form.checklistRisco={};St.form.checklistEpi={};persistDraft();renderForm();return;
  }
  if(name==='sign'){await openSignature(button.dataset.role);return;}
  if(name==='close'){await openSignature('encerramento');return;}
  if(name==='dismiss-modal'){closeModal();return;}
  if(name==='capture'){capture();return;}
  if(name==='retake'){St.photo=null;$('#facePreview').classList.add('hidden');$('#faceVideo').classList.remove('hidden');$('#capture').classList.remove('hidden');$('#retake').classList.add('hidden');return;}
  if(name==='clear-signature'){St.canvas.ctx.clearRect(0,0,St.canvas.el.width,St.canvas.el.height);St.canvas.length=0;return;}
  if(name==='confirm-signature'){await confirmSignature();return;}
  if(name==='pdf'){download(await getPdf());return;}
  if(name==='share'){await share();return;}
  if(name==='contact'){
    const contact=St.record.contatosEnvio[Number(button.dataset.index)];
    const message=`Segue a PTS ${St.record.numero}. O PDF deve ser anexado manualmente.`;
    if(contact.tipo==='email'){location.href='mailto:'+encodeURIComponent(contact.valor)+'?subject='+encodeURIComponent(St.record.numero)+'&body='+encodeURIComponent(message);}
    else window.open('https://wa.me/'+contact.valor+'?text='+encodeURIComponent(message),'_blank','noopener,noreferrer');
    toast('Anexe o PDF baixado antes de enviar a mensagem.');return;
  }
  if(name==='auto-send'){
    await api('/api/pts/'+St.record.id+'/enviar',{method:'POST',body:JSON.stringify({contato_index:Number(button.dataset.index)})});
    await openDetail(St.record.id);toast('Envio aceito pelo provedor; entrega não confirmada.');return;
  }
  if(name==='cancel'){
    const reason=prompt('Informe o motivo do cancelamento (o histórico será preservado):');if(!reason?.trim())return;
    await api('/api/pts/'+St.record.id+'/cancelar',{method:'POST',body:JSON.stringify({motivo:reason})});await openDetail(St.record.id);toast('PTS cancelada, com histórico preservado.');
  }
}
document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-action]');if(!button||button.disabled||St.busy)return;
  const name=button.dataset.action;
  const exclusive=['confirm-signature','cancel','auto-send','logout','pdf','share','detail','new','home'].includes(name);
  if(exclusive){St.busy=true;button.disabled=true;if(St.modalRole)$('.modal-sheet')?.setAttribute('aria-busy','true');}
  try{await action(name,button);}catch(error){const target=St.modalRole?$('#sigError'):null;if(target)target.textContent=error.message;else toast(error.message);}
  finally{if(exclusive){St.busy=false;button.disabled=false;$('.modal-sheet')?.removeAttribute('aria-busy');updateReady();}}
});
document.addEventListener('input',event=>{
  const input=event.target;
  if(input.id==='search'){St.search=input.value;St.page=1;clearTimeout(St.searchTimer);St.listGeneration++;St.searchTimer=setTimeout(loadList,300);return;}
  if(input.closest('#permitForm')&&input.name){invalidateSignatures();St.form[input.name]=input.value;persistDraft();updateReady();}
  if(input.dataset.contact!==undefined&&input.dataset.field==='valor'){
    // Contatos também fazem parte do documento submetido.
    invalidateSignatures();St.form.contatosEnvio[Number(input.dataset.contact)].valor=input.value;persistDraft();updateReady();
  }
});
document.addEventListener('change',event=>{
  const input=event.target;
  if(input.dataset.check){invalidateSignatures();St.form[input.dataset.check][Number(input.dataset.index)]=input.checked;persistDraft();updateReady();}
  if(input.dataset.contact!==undefined&&input.dataset.field==='tipo'){
    invalidateSignatures();St.form.contatosEnvio[Number(input.dataset.contact)].tipo=input.value;
    const field=input.parentElement.querySelector('input');field.type=input.value==='email'?'email':'tel';field.placeholder=input.value==='email'?'nome@empresa.com':'País, DDD e número';persistDraft();updateReady();
  }
});
document.addEventListener('submit',async event=>{
  event.preventDefault();if(St.busy)return;
  const form=event.target;if(!['loginForm','permitForm'].includes(form.id))return;
  St.busy=true;const button=$('button[type=submit]',form);button.disabled=true;
  try{
    if(form.id==='loginForm'){
      const values=new FormData(form);const data=await api('/api/auth/login',{method:'POST',body:JSON.stringify(Object.fromEntries(values))});
      St.user=data.user;St.csrf=data.csrf;St.view='home';form.reset();await startSession();
    }else{
      const missing=readiness();if(missing.length)throw new Error('Preencha: '+missing.join(', '));
      const {requestId,...payload}=St.form;
      const record=await api('/api/pts',{method:'POST',headers:{'Idempotency-Key':requestId},body:JSON.stringify(payload)});
      removeDraft();St.form=null;await openDetail(record.id);toast('PTS emitida com sucesso.');
    }
  }catch(error){const target=form.id==='loginForm'?$('#loginError'):$('#submitError');if(target)target.textContent=error.message;else toast(error.message);}
  finally{St.busy=false;button.disabled=false;updateReady();}
});
document.addEventListener('keydown',event=>{
  if(!St.modalRole)return;
  if(event.key==='Escape'&&!St.busy){closeModal();return;}
  if(event.key==='Tab'){
    const controls=[...$('#sigOverlay').querySelectorAll('button:not(:disabled),input,textarea')].filter(el=>!el.classList.contains('hidden'));
    if(event.shiftKey&&document.activeElement===controls[0]){event.preventDefault();controls.at(-1).focus();}
    else if(!event.shiftKey&&document.activeElement===controls.at(-1)){event.preventDefault();controls[0].focus();}
  }
});
let resizeTimer;window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(fitCanvas,150);});
window.addEventListener('pagehide',()=>{stopCamera();});
window.addEventListener('offline',()=>toast('Sem conexão. A emissão e o encerramento precisam de internet.'));
window.addEventListener('online',()=>toast('Conexão restabelecida.'));
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
init();
