(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const uid = prefix => `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
  const now = () => new Date().toLocaleTimeString('zh-CN', { hour12: false });
  const deepClone = value => JSON.parse(JSON.stringify(value));

  const refs = {
    viewport: $('#viewport'), world: $('#world'), nodes: $('#nodesLayer'), svg: $('#connectionsSvg'),
    library: $('#nodeLibrary'), inspector: $('#inspectorContent'), hint: $('#connectionHint'),
    empty: $('#emptyCanvas'), minimap: $('#minimap canvas'), log: $('#activityLog'),
    progress: $('#runProgress'), progressBar: $('#runProgressBar'), activityState: $('#activityState'),
    workflowName: $('#workflowName'), canvasTitle: $('#canvasTitle'), zoomLabel: $('#zoomReset')
  };

  const palette = {
    input_file: '#4fc3df', input_folder: '#4fc3df', separator: '#9a6cf2', output_folder: '#54d69a'
  };
  const icons = { input_file: '♪', input_folder: '▱', separator: '⌁', output_folder: '↳' };
  const labels = { input_file: '单个音频', input_folder: '音频文件夹', separator: '音频处理', output_folder: '输出文件夹' };
  const functionLabels = {
    vocal_separation: '人声 / 伴奏分离', vocals: '人声 / 伴奏分离',
    stem_separation: '多音轨 / 乐器分离', multi_stem: '多音轨 / 乐器分离', multistem_separation: '多音轨 / 乐器分离',
    denoise: '降噪', noise_reduction: '降噪', dereverb: '去混响 / 去回声',
    deecho: '去混响 / 去回声', karaoke: '去和声 / 人声清理',
    vocal_cleanup: '去和声 / 人声清理', unknown: '待确认', other: '其他'
  };

  const state = {
    workflow: { id: uid('workflow'), name: '人声处理工作流', nodes: [], edges: [] },
    models: [], selectedNode: null, selectedEdge: null, pendingPort: null,
    transform: { x: 0, y: 0, scale: 1 }, panning: null, dragging: null,
    history: [], historyIndex: -1, running: false, runId: null, eventSource: null,
    activityCollapsed: false, dirty: false, modelCacheUsed: false
  };

  function normalizeOutputs(raw) {
    let outputs = raw.outputs || raw.stems || raw.instruments || raw.output_stems || [];
    if (typeof outputs === 'string') outputs = outputs.split(/[,/|]/).map(x => x.trim()).filter(Boolean);
    if (!Array.isArray(outputs) && outputs && typeof outputs === 'object') outputs = Object.keys(outputs);
    outputs = outputs.map((item, index) => {
      if (typeof item === 'string') return { id: item.toLowerCase().replace(/\s+/g, '_'), label: item };
      return { id: item.id || item.name || item.stem || `output_${index + 1}`, label: item.label || item.name || item.stem || `Output ${index + 1}` };
    });
    if (!outputs.length) outputs = [{ id: 'output', label: '输出' }];
    return outputs;
  }

  function inferFunction(model) {
    const explicit = String(model.function || model.task || model.category || '').toLowerCase();
    if (explicit && explicit !== 'other') return explicit;
    const text = `${model.name || ''} ${model.filename || ''} ${normalizeOutputs(model).map(x => x.id).join(' ')}`.toLowerCase();
    if (/denoise|noise|杂音|降噪/.test(text)) return 'denoise';
    if (/dereverb|de.?reverb|echo|混响/.test(text)) return 'dereverb';
    if (/karaoke|backing.?vocal|harmony|和声/.test(text)) return 'vocal_cleanup';
    if (/drum|bass|guitar|piano|4.?stem|6.?stem|multi/.test(text) || normalizeOutputs(model).length > 2) return 'stem_separation';
    if (/vocal|instrument|voice|人声/.test(text)) return 'vocal_separation';
    return 'unknown';
  }

  function normalizeModel(raw, index) {
    const filename = raw.filename || raw.file || raw.model_filename || raw.id || `model-${index + 1}`;
    const architecture = raw.architecture || raw.arch || raw.type || raw.model_type || 'Unknown';
    const installed = raw.installed ?? raw.is_installed ?? raw.local ?? raw.available_locally ?? true;
    const model = {
      id: String(raw.id || filename), filename: String(filename),
      name: String(raw.display_name || raw.friendly_name || raw.name || filename.replace(/\.(ckpt|pth|pt|onnx)$/i, '')),
      architecture: String(architecture), installed: Boolean(installed), outputs: normalizeOutputs(raw),
      confidence: raw.confidence || raw.metadata_confidence || 'unknown', source: raw.metadata_source || raw.source || ''
    };
    model.function = raw.needs_confirmation ? 'unknown' : inferFunction({...raw, ...model});
    return model;
  }

  function unwrapModels(payload) {
    const list = Array.isArray(payload) ? payload : payload?.models || payload?.items || payload?.data || [];
    return Array.isArray(list) ? list.map(normalizeModel) : [];
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }, ...options
    });
    const text = await response.text();
    let data = null;
    try { data = text ? JSON.parse(text) : {}; } catch { data = { message: text }; }
    if (!response.ok) {
      const detail = data.detail || data.error || data.message;
      const message = typeof detail === 'string' ? detail : detail?.message || (detail?.errors ? detail.errors.join('；') : detail ? JSON.stringify(detail) : `${response.status} ${response.statusText}`);
      throw new Error(message);
    }
    return data;
  }

  function toast(message, type = '') {
    const item = document.createElement('div');
    item.className = `toast ${type}`;
    item.textContent = message;
    $('#toastStack').append(item);
    setTimeout(() => item.remove(), 3400);
  }

  function log(message, type = '') {
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.innerHTML = `<time>${now()}</time><span>${escapeHtml(message)}</span>`;
    refs.log.append(line);
    refs.log.scrollTop = refs.log.scrollHeight;
  }

  async function loadModels(forceNetwork = false) {
    const cached = localStorage.getItem('audioflow:model-cache');
    if (cached && !forceNetwork) {
      try {
        state.models = unwrapModels(JSON.parse(cached));
        state.modelCacheUsed = true;
        renderLibrary();
        $('#modelCount').textContent = `${state.models.filter(x => x.installed).length} 个已安装模型 · 缓存`;
      } catch { /* ignore corrupt cache */ }
    }
    try {
      const payload = await api('/api/models');
      state.models = unwrapModels(payload);
      localStorage.setItem('audioflow:model-cache', JSON.stringify(state.models));
      $('#apiStatus').className = 'status-dot ok';
      $('#apiStatus').title = '后端已连接';
      $('#modelCount').textContent = `${state.models.filter(x => x.installed).length} 个已安装模型`;
      renderLibrary();
    } catch (error) {
      $('#apiStatus').className = 'status-dot error';
      $('#apiStatus').title = '后端暂不可用';
      if (!state.models.length) $('#modelCount').textContent = '模型服务暂不可用';
      log(`模型列表读取失败：${error.message}`, 'error');
      renderLibrary();
    }
  }

  async function refreshModels(scope) {
    $('#refreshToggle').classList.add('spin');
    $('#refreshMenu').classList.add('hidden');
    toast(scope === 'local' ? '正在后台扫描本地模型…' : '正在同步在线模型目录…');
    log(scope === 'local' ? '开始扫描本地模型' : '开始同步在线模型目录');
    try {
      const result = await api('/api/models/refresh', { method: 'POST', body: JSON.stringify({ scope, force: scope !== 'local' }) });
      if (result.models || Array.isArray(result)) {
        state.models = unwrapModels(result);
        localStorage.setItem('audioflow:model-cache', JSON.stringify(state.models));
        renderLibrary();
      } else {
        await pollRefresh(result.task_id || result.id);
      }
      await loadModels(true);
      toast('模型列表已刷新', 'success');
      log('模型列表刷新完成', 'success');
    } catch (error) {
      toast(`刷新失败：${error.message}`, 'error');
      log(`刷新失败：${error.message}`, 'error');
    } finally { $('#refreshToggle').classList.remove('spin'); }
  }

  async function pollRefresh(id) {
    if (!id) return;
    for (let i = 0; i < 120; i++) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      try {
        const result = await api(`/api/models/refresh/${encodeURIComponent(id)}`);
        if (result.status === 'failed') throw new Error(result.error || '刷新任务失败');
        if (['complete', 'completed', 'success'].includes(result.status)) return result;
      } catch (error) {
        if (error.message.includes('404')) return;
        throw error;
      }
    }
    throw new Error('刷新超时，请稍后重试');
  }

  function fixedTemplates() {
    return [
      { type: 'input_file', title: '单个音频文件', subtitle: '选择一个音频作为输入', group: '输入', color: palette.input_file },
      { type: 'input_folder', title: '音频文件夹', subtitle: '批量扫描文件夹中的音频', group: '输入', color: palette.input_folder },
      { type: 'output_folder', title: '输出到文件夹', subtitle: '命名并保存处理结果', group: '输出', color: palette.output_folder }
    ];
  }

  function renderLibrary() {
    const search = $('#modelSearch').value.trim().toLowerCase();
    const architecture = $('#architectureFilter').value;
    const installed = state.models.filter(model => model.installed);
    const architectures = [...new Set(installed.map(x => x.architecture).filter(Boolean))].sort();
    const previous = architecture;
    $('#architectureFilter').innerHTML = '<option value="">全部架构</option>' + architectures.map(x => `<option value="${escapeHtml(x)}">${escapeHtml(x)}</option>`).join('');
    $('#architectureFilter').value = architectures.includes(previous) ? previous : '';

    const groups = new Map();
    const matches = item => !search || `${item.title} ${item.subtitle} ${item.architecture || ''}`.toLowerCase().includes(search);
    fixedTemplates().filter(matches).forEach(item => {
      if (!groups.has(item.group)) groups.set(item.group, []);
      groups.get(item.group).push(item);
    });
    installed.filter(model => (!architecture || model.architecture === architecture) && matches({ title:model.name, subtitle:model.function, architecture:model.architecture })).forEach(model => {
      const group = functionLabels[model.function] || (model.function === 'unknown' ? '待确认' : '其他');
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push({ type: 'separator', title: model.name, subtitle: `${model.architecture} · ${model.outputs.map(x => x.label).join(' / ')}`, group, model, color: palette.separator });
    });
    const order = ['输入','人声 / 伴奏分离','多音轨 / 乐器分离','降噪','去混响 / 去回声','去和声 / 人声清理','其他','待确认','输出'];
    const html = order.filter(group => groups.has(group)).map(group => {
      const items = groups.get(group);
      return `<section class="library-group" data-group="${escapeHtml(group)}">
        <button class="group-heading"><span>${escapeHtml(group)} <em>${items.length}</em></span><span>⌄</span></button>
        <div class="group-items">${items.map(item => `<div class="node-template" draggable="true" data-template-id="${escapeHtml(item.model?.id || item.type)}" data-type="${item.type}" style="--item-color:${item.color}">
          <span class="template-icon">${icons[item.type]}</span><span class="template-copy"><b title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</b><span title="${escapeHtml(item.subtitle)}">${escapeHtml(item.subtitle)}</span></span><span class="drag-dots">⠿</span>
        </div>`).join('')}</div></section>`;
    }).join('');
    refs.library.innerHTML = html || '<div class="empty-library">没有符合条件的已安装模型。<br>可点击右上角刷新按钮重新扫描。</div>';
    $$('.group-heading', refs.library).forEach(button => button.addEventListener('click', () => button.closest('.library-group').classList.toggle('collapsed')));
    $$('.node-template', refs.library).forEach(template => {
      template.addEventListener('dragstart', event => event.dataTransfer.setData('application/x-audioflow-node', JSON.stringify({ type: template.dataset.type, id: template.dataset.templateId })));
      template.addEventListener('dblclick', () => addFromTemplate(template.dataset.type, template.dataset.templateId));
    });
  }

  function makeNode(type, x, y, model = null) {
    const base = { id: uid('node'), type, data: { x: Math.round(x), y: Math.round(y), title: labels[type] || '节点', config: {} } };
    if (type === 'input_file') {
      base.data.title = '单个音频文件'; base.data.outputs = [{ id:'audio', label:'音频' }]; base.data.config = { path: '' };
    } else if (type === 'input_folder') {
      base.data.title = '音频文件夹'; base.data.outputs = [{ id:'audio', label:'音频批次' }]; base.data.config = { path:'', recursive:true, include:'*.wav;*.flac;*.mp3;*.m4a' };
    } else if (type === 'output_folder') {
      base.data.title = '输出到文件夹'; base.data.inputs = [{ id:'audio', label:'音频' }]; base.data.config = { path:'outputs', naming:'{basename}_{stem}.{ext}', format:'wav', conflict:'rename' };
    } else if (type === 'separator') {
      base.data.title = model?.name || 'Audio Separator';
      base.data.model_id = model?.id || '';
      base.data.model_filename = model?.filename || '';
      base.data.architecture = model?.architecture || 'Unknown';
      base.data.function = model?.function || 'unknown';
      base.data.inputs = [{ id:'audio', label:'音频' }];
      base.data.outputs = model?.outputs || [{ id:'output', label:'输出' }];
      base.data.config = { output_format:'wav', normalization_threshold:0.9 };
    }
    return base;
  }

  function addFromTemplate(type, templateId, position = null) {
    const center = screenToWorld(refs.viewport.clientWidth * .45, refs.viewport.clientHeight * .42);
    const model = type === 'separator' ? state.models.find(x => x.id === templateId) : null;
    const node = makeNode(type, position?.x ?? center.x, position?.y ?? center.y, model);
    state.workflow.nodes.push(node);
    selectNode(node.id);
    commit('添加节点');
    renderGraph();
  }

  function getInputs(node) { return node.data.inputs || []; }
  function getOutputs(node) { return node.data.outputs || []; }

  function nodeHtml(node) {
    const typeLabel = node.type === 'separator' ? (functionLabels[node.data.function] || '音频处理') : labels[node.type];
    const info = node.type === 'separator'
      ? `<div class="node-info-row"><span>模型</span><strong title="${escapeHtml(node.data.model_filename)}">${escapeHtml(node.data.model_filename || node.data.title)}</strong></div><div class="node-info-row"><span>架构</span><strong>${escapeHtml(node.data.architecture || 'Unknown')}</strong></div>`
      : node.type === 'input_folder' ? `<div class="node-info-row"><span>扫描</span><strong>${node.data.config.recursive ? '包含子文件夹' : '当前文件夹'}</strong></div>`
      : node.type === 'output_folder' ? `<div class="node-info-row"><span>格式</span><strong>${escapeHtml((node.data.config.format || 'wav').toUpperCase())}</strong></div>`
      : `<div class="node-info-row"><span>来源</span><strong>${node.data.config.path ? '已选择' : '未选择'}</strong></div>`;
    const inputs = getInputs(node).map(port => `<div class="port-row"><div class="port-label"><i class="port input" data-direction="input" data-port="${escapeHtml(port.id)}" style="--port-color:#55c9e5"></i><span>${escapeHtml(port.label || port.id)}</span></div></div>`).join('');
    const outputs = getOutputs(node).map((port, i) => `<div class="port-row"><div class="port-label output"><span>${escapeHtml(port.label || port.id)}</span><i class="port output" data-direction="output" data-port="${escapeHtml(port.id)}" style="--port-color:${i % 2 ? '#f3a45f' : '#9a6cf2'}"></i></div></div>`).join('');
    return `<article class="node ${state.selectedNode === node.id ? 'selected' : ''}" data-node-id="${node.id}" style="left:${node.data.x}px;top:${node.data.y}px;--node-color:${palette[node.type] || palette.separator}">
      <header class="node-header"><span class="node-header-icon">${icons[node.type] || '◇'}</span><span class="node-title"><b>${escapeHtml(node.data.title)}</b><span>${escapeHtml(typeLabel)}</span></span><button class="node-menu" title="删除节点">•••</button></header>
      <div class="node-body"><div class="node-info">${info}</div>${inputs}${outputs}</div>
      <footer class="node-footer"><span class="node-badge">${node.type === 'separator' ? escapeHtml(node.data.architecture || 'MODEL') : escapeHtml(node.type.replace('_',' '))}</span><button class="node-remove" title="删除节点">×</button></footer>
    </article>`;
  }

  function renderGraph() {
    refs.nodes.innerHTML = state.workflow.nodes.map(nodeHtml).join('');
    $$('.node', refs.nodes).forEach(element => bindNode(element));
    requestAnimationFrame(() => { renderEdges(); drawMinimap(); });
    refs.empty.classList.toggle('hidden', state.workflow.nodes.length > 0);
    $('#nodeCount').textContent = `${state.workflow.nodes.length} 个节点`;
    $('#edgeCount').textContent = `${state.workflow.edges.length} 条连接`;
    refs.workflowName.value = state.workflow.name;
    refs.canvasTitle.textContent = state.workflow.name;
    renderInspector();
  }

  function bindNode(element) {
    const id = element.dataset.nodeId;
    element.addEventListener('pointerdown', event => {
      if (event.target.closest('.port,.node-remove,.node-menu')) return;
      selectNode(id); renderSelection();
    });
    $('.node-header', element).addEventListener('pointerdown', event => startNodeDrag(event, id));
    $$('.port', element).forEach(port => port.addEventListener('click', event => {
      event.stopPropagation(); handlePort(id, port.dataset.port, port.dataset.direction, port);
    }));
    $$('.node-remove,.node-menu', element).forEach(button => button.addEventListener('click', event => { event.stopPropagation(); removeNode(id); }));
  }

  function startNodeDrag(event, id) {
    if (event.button !== 0) return;
    event.stopPropagation();
    const node = state.workflow.nodes.find(x => x.id === id);
    selectNode(id); renderSelection();
    state.dragging = { id, startX:event.clientX, startY:event.clientY, nodeX:node.data.x, nodeY:node.data.y, moved:false };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handlePort(nodeId, portId, direction, element) {
    if (direction === 'output') {
      $$('.port.pending').forEach(x => x.classList.remove('pending'));
      state.pendingPort = { nodeId, portId };
      element.classList.add('pending');
      refs.hint.classList.remove('hidden');
      return;
    }
    if (!state.pendingPort) { toast('请先选择一个输出端口'); return; }
    if (state.pendingPort.nodeId === nodeId) { toast('节点不能连接到自身', 'error'); cancelConnection(); return; }
    const duplicate = state.workflow.edges.some(edge => edge.source === state.pendingPort.nodeId && edge.source_handle === state.pendingPort.portId && edge.target === nodeId && edge.target_handle === portId);
    if (duplicate) { toast('此连接已存在'); cancelConnection(); return; }
    state.workflow.edges = state.workflow.edges.filter(edge => !(edge.target === nodeId && edge.target_handle === portId));
    state.workflow.edges.push({ source:state.pendingPort.nodeId, source_handle:state.pendingPort.portId, target:nodeId, target_handle:portId });
    cancelConnection(); commit('创建连接'); renderGraph();
  }

  function cancelConnection() {
    state.pendingPort = null; $$('.port.pending').forEach(x => x.classList.remove('pending')); refs.hint.classList.add('hidden'); renderEdges();
  }

  function portCenter(nodeId, portId, direction) {
    const nodeEl = $(`.node[data-node-id="${CSS.escape(nodeId)}"]`, refs.nodes);
    const portEl = nodeEl?.querySelector(`.port.${direction}[data-port="${CSS.escape(portId)}"]`);
    if (!nodeEl || !portEl) return null;
    const portRect = portEl.getBoundingClientRect();
    const viewportRect = refs.viewport.getBoundingClientRect();
    return screenToWorld(
      portRect.left + portRect.width / 2 - viewportRect.left,
      portRect.top + portRect.height / 2 - viewportRect.top
    );
  }

  function bezier(a, b) {
    const dx = Math.max(60, Math.abs(b.x - a.x) * .46);
    return `M ${a.x} ${a.y} C ${a.x + dx} ${a.y}, ${b.x - dx} ${b.y}, ${b.x} ${b.y}`;
  }

  function renderEdges() {
    refs.svg.innerHTML = '';
    state.workflow.edges.forEach((edge, index) => {
      const a = portCenter(edge.source, edge.source_handle, 'output');
      const b = portCenter(edge.target, edge.target_handle, 'input');
      if (!a || !b) return;
      const group = document.createElementNS('http://www.w3.org/2000/svg','g');
      group.dataset.edgeIndex = index;
      const path = bezier(a,b);
      group.innerHTML = `<path class="edge-line ${state.selectedEdge === index ? 'active' : ''}" d="${path}"/><path class="edge-hit" d="${path}"/>`;
      $('.edge-hit', group).addEventListener('click', event => { event.stopPropagation(); state.selectedEdge = index; state.selectedNode = null; renderSelection(); renderEdges(); renderInspector(); });
      refs.svg.append(group);
    });
  }

  function selectNode(id) { state.selectedNode = id; state.selectedEdge = null; }
  function renderSelection() {
    $$('.node', refs.nodes).forEach(element => element.classList.toggle('selected', element.dataset.nodeId === state.selectedNode));
  }

  function removeNode(id) {
    state.workflow.nodes = state.workflow.nodes.filter(x => x.id !== id);
    state.workflow.edges = state.workflow.edges.filter(x => x.source !== id && x.target !== id);
    if (state.selectedNode === id) state.selectedNode = null;
    commit('删除节点'); renderGraph();
  }

  function removeSelected() {
    if (state.selectedNode) removeNode(state.selectedNode);
    else if (state.selectedEdge !== null) {
      state.workflow.edges.splice(state.selectedEdge, 1); state.selectedEdge = null; commit('删除连接'); renderGraph();
    }
  }

  function renderInspector() {
    const node = state.workflow.nodes.find(x => x.id === state.selectedNode);
    if (!node) {
      refs.inspector.innerHTML = state.selectedEdge !== null
        ? `<div class="inspector-empty"><div>⌁</div><b>已选择连接</b><span>按 Delete 删除这条连接</span><button class="danger-button" id="deleteEdge" style="width:150px">删除连接</button></div>`
        : '<div class="inspector-empty"><div>◇</div><b>未选择节点</b><span>选择画布中的节点来编辑参数</span></div>';
      $('#deleteEdge')?.addEventListener('click', removeSelected);
      return;
    }
    const c = node.data.config || (node.data.config = {});
    let fields = '';
    if (node.type === 'input_file') fields = field('path','音频文件路径',c.path,'例如：inputs/song.wav','text');
    if (node.type === 'input_folder') fields = field('path','输入文件夹',c.path,'例如：inputs','text') + field('include','文件筛选',c.include,'使用分号分隔扩展名','text') + selectField('recursive','扫描子文件夹',String(c.recursive),[['true','是'],['false','否']]);
    if (node.type === 'output_folder') fields = field('path','输出文件夹',c.path,'例如：outputs/vocals','text') + field('naming','命名模板',c.naming,'可用：{basename} {stem} {ext}','text') + `<div class="field-inline">${selectField('format','输出格式',c.format,[['wav','WAV'],['flac','FLAC'],['mp3','MP3']])}${selectField('conflict','重名策略',c.conflict,[['rename','自动编号'],['overwrite','覆盖'],['skip','跳过']])}</div>`;
    if (node.type === 'separator') fields = selectField('output_format','中间格式',c.output_format,[['wav','WAV'],['flac','FLAC']]) + field('normalization_threshold','峰值上限',c.normalization_threshold ?? 0.9,'范围：大于 0 且不超过 1','number');
    const model = node.type === 'separator' ? `<div class="inspector-section"><h2>模型信息</h2><div class="model-summary"><span class="template-icon" style="--item-color:${palette.separator}">⌁</span><div><b>${escapeHtml(node.data.title)}</b><span>${escapeHtml(node.data.architecture)} · ${escapeHtml(functionLabels[node.data.function] || '待确认')}</span></div></div><div class="tag-list">${getOutputs(node).map(x => `<span class="tag">${escapeHtml(x.label)}</span>`).join('')}</div></div>` : '';
    refs.inspector.innerHTML = `<div class="inspector-section"><h2>节点</h2>${field('__title','显示名称',node.data.title,'','text')}<div class="field-inline">${field('__x','X 坐标',node.data.x,'','number')}${field('__y','Y 坐标',node.data.y,'','number')}</div></div>${model}<div class="inspector-section"><h2>参数</h2>${fields || '<div class="field"><small>此节点没有可编辑参数。</small></div>'}</div><div class="inspector-section"><button class="danger-button" id="deleteNode">删除此节点</button></div>`;
    $$('input[data-field],select[data-field]', refs.inspector).forEach(input => input.addEventListener('change', () => updateNodeField(node, input.dataset.field, input.value)));
    $('#deleteNode').addEventListener('click', () => removeNode(node.id));
  }

  function field(key, label, value, help = '', type = 'text') {
    return `<label class="field"><span>${label}</span><input data-field="${key}" type="${type}" value="${escapeHtml(value)}">${help ? `<small>${help}</small>` : ''}</label>`;
  }
  function selectField(key, label, value, options) {
    return `<label class="field"><span>${label}</span><select data-field="${key}">${options.map(([v,l]) => `<option value="${v}" ${String(value) === v ? 'selected' : ''}>${l}</option>`).join('')}</select></label>`;
  }
  function updateNodeField(node, key, value) {
    if (key === '__title') node.data.title = value || labels[node.type];
    else if (key === '__x' || key === '__y') node.data[key.slice(2)] = Number(value) || 0;
    else if (key === 'normalization_threshold') node.data.config[key] = Math.min(1, Math.max(0.01, Number(value) || 0.9));
    else node.data.config[key] = value === 'true' ? true : value === 'false' ? false : value;
    commit('修改节点参数'); renderGraph();
  }

  function applyTransform() {
    const {x,y,scale} = state.transform;
    refs.world.style.transform = `translate(${x}px,${y}px) scale(${scale})`;
    refs.viewport.style.setProperty('--grid-x', `${x % (20 * scale)}px`);
    refs.viewport.style.setProperty('--grid-y', `${y % (20 * scale)}px`);
    refs.viewport.querySelector('.canvas-grid').style.backgroundSize = `${20 * scale}px ${20 * scale}px`;
    refs.zoomLabel.textContent = `${Math.round(scale * 100)}%`;
    drawMinimap();
  }
  function screenToWorld(x,y) { return { x:(x - state.transform.x) / state.transform.scale, y:(y - state.transform.y) / state.transform.scale }; }
  function setZoom(scale, anchorX = refs.viewport.clientWidth/2, anchorY = refs.viewport.clientHeight/2) {
    const old = state.transform.scale; const next = Math.min(1.8, Math.max(.35, scale));
    const wx = (anchorX-state.transform.x)/old, wy=(anchorY-state.transform.y)/old;
    state.transform.scale=next; state.transform.x=anchorX-wx*next; state.transform.y=anchorY-wy*next; applyTransform();
  }
  function fitView() {
    if (!state.workflow.nodes.length) { state.transform={x:0,y:0,scale:1}; applyTransform(); return; }
    const minX=Math.min(...state.workflow.nodes.map(n=>n.data.x)), minY=Math.min(...state.workflow.nodes.map(n=>n.data.y));
    const maxX=Math.max(...state.workflow.nodes.map(n=>n.data.x+224)), maxY=Math.max(...state.workflow.nodes.map(n=>n.data.y+180));
    const scale=Math.min(1.15, Math.max(.35, Math.min((refs.viewport.clientWidth-100)/(maxX-minX),(refs.viewport.clientHeight-100)/(maxY-minY))));
    state.transform={scale,x:(refs.viewport.clientWidth-(minX+maxX)*scale)/2,y:(refs.viewport.clientHeight-(minY+maxY)*scale)/2}; applyTransform();
  }

  function drawMinimap() {
    const canvas=refs.minimap, ctx=canvas.getContext('2d'), w=canvas.width,h=canvas.height;
    ctx.clearRect(0,0,w,h); ctx.fillStyle='#11151d';ctx.fillRect(0,0,w,h);
    if (!state.workflow.nodes.length) return;
    const minX=Math.min(0,...state.workflow.nodes.map(n=>n.data.x-100)), minY=Math.min(0,...state.workflow.nodes.map(n=>n.data.y-100));
    const maxX=Math.max(900,...state.workflow.nodes.map(n=>n.data.x+330)), maxY=Math.max(600,...state.workflow.nodes.map(n=>n.data.y+260));
    const s=Math.min(w/(maxX-minX),h/(maxY-minY));
    state.workflow.edges.forEach(edge=>{ const a=state.workflow.nodes.find(n=>n.id===edge.source),b=state.workflow.nodes.find(n=>n.id===edge.target);if(!a||!b)return;ctx.strokeStyle='#4c5362';ctx.beginPath();ctx.moveTo((a.data.x+224-minX)*s,(a.data.y+70-minY)*s);ctx.lineTo((b.data.x-minX)*s,(b.data.y+70-minY)*s);ctx.stroke(); });
    state.workflow.nodes.forEach(node=>{ctx.fillStyle=palette[node.type]+'b8';ctx.fillRect((node.data.x-minX)*s,(node.data.y-minY)*s,Math.max(4,224*s),Math.max(3,75*s));});
    const vx=(-state.transform.x/state.transform.scale-minX)*s,vy=(-state.transform.y/state.transform.scale-minY)*s;
    ctx.strokeStyle='#dde2eb';ctx.lineWidth=1;ctx.strokeRect(vx,vy,refs.viewport.clientWidth/state.transform.scale*s,refs.viewport.clientHeight/state.transform.scale*s);
  }

  function workflowPayload() {
    const nodes = state.workflow.nodes.map(original => {
      const node = deepClone(original), config = node.data.config || {};
      if (node.type === 'input_file') node.data.path = config.path || node.data.path || '';
      if (node.type === 'input_folder') {
        node.data.path = config.path || node.data.path || '';
        node.data.recursive = config.recursive ?? node.data.recursive ?? true;
        const include = config.include || '';
        node.data.extensions = include.split(/[;,\s]+/).filter(Boolean).map(ext => ext.replace(/^\*?/, '')).filter(ext => /^\.[a-z0-9]+$/i.test(ext));
      }
      if (node.type === 'separator') {
        node.data.outputs = getOutputs(node).map(port => port.id);
        node.data.options = { ...(node.data.options || {}), ...config };
      }
      if (node.type === 'output_folder') {
        node.data.path = config.path || node.data.path || '';
        node.data.naming_template = config.naming || node.data.naming_template || '{relative_dir}/{basename}_{stem}.{ext}';
        node.data.conflict = config.conflict || node.data.conflict || 'rename';
        node.data.format = config.format || node.data.format || 'wav';
      }
      delete node.data.config;
      return node;
    });
    return { id:state.workflow.id, name:state.workflow.name, version:1, nodes, edges:deepClone(state.workflow.edges) };
  }
  function commit(reason) {
    state.dirty=true; $('.save-dot').style.background= '#f2ad5f'; $('.save-dot').title='有未保存的更改';
    const snapshot=JSON.stringify(state.workflow);
    if (state.history[state.historyIndex]===snapshot) return;
    state.history=state.history.slice(0,state.historyIndex+1);state.history.push(snapshot);if(state.history.length>60)state.history.shift();state.historyIndex=state.history.length-1;
    localStorage.setItem('audioflow:autosave', JSON.stringify(workflowPayload()));
  }
  function restoreHistory(index) {
    if(index<0||index>=state.history.length)return;state.historyIndex=index;state.workflow=JSON.parse(state.history[index]);state.selectedNode=null;state.selectedEdge=null;renderGraph();
  }

  async function saveWorkflow() {
    state.workflow.name=refs.workflowName.value.trim()||'未命名工作流'; const payload=workflowPayload();
    localStorage.setItem('audioflow:autosave',JSON.stringify(payload));
    try { await api('/api/workflows',{method:'POST',body:JSON.stringify(payload)}); log('工作流已保存到本地服务','success'); }
    catch(error){ log(`服务端保存不可用，已保存浏览器副本：${error.message}`,'muted'); }
    const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;a.download=`${payload.name.replace(/[\\/:*?"<>|]/g,'_')}.audioflow.json`;a.click();URL.revokeObjectURL(url);
    state.dirty=false;$('.save-dot').style.background='var(--green)';$('.save-dot').title='已保存';toast('工作流已保存并导出','success');
  }
  function loadWorkflowData(payload) {
    if(!payload||!Array.isArray(payload.nodes)||!Array.isArray(payload.edges))throw new Error('不是有效的 AudioFlow 工作流');
    payload.nodes.forEach((node,i)=>{
      node.data=node.data||{};node.data.x=Number(node.data.x ?? node.position?.x ?? 80+i*260);node.data.y=Number(node.data.y ?? node.position?.y ?? 100);
      if (node.type === 'separator') node.data.outputs = normalizeOutputs(node.data);
      if (node.type === 'input_file') node.data.outputs = normalizeOutputs({outputs:node.data.outputs || [{id:'audio',label:'音频'}]});
      if (node.type === 'input_folder') node.data.outputs = normalizeOutputs({outputs:node.data.outputs || [{id:'audio',label:'音频批次'}]});
      if (node.type === 'output_folder') node.data.inputs = node.data.inputs || [{id:'audio',label:'音频'}];
      node.data.config=node.data.config||{};
      if (node.type === 'input_file') node.data.config.path ??= node.data.path || '';
      if (node.type === 'input_folder') { node.data.config.path ??= node.data.path || ''; node.data.config.recursive ??= node.data.recursive ?? true; node.data.config.include ??= (node.data.extensions || []).map(ext=>`*${ext}`).join(';'); }
      if (node.type === 'separator') node.data.config = {...(node.data.options || {}),...node.data.config};
      if (node.type === 'output_folder') node.data.config = {path:node.data.path || '',naming:node.data.naming_template || '{basename}_{stem}.{ext}',format:node.data.format || 'wav',conflict:node.data.conflict || 'rename',...node.data.config};
    });
    state.workflow={id:payload.id||uid('workflow'),name:payload.name||'已加载工作流',nodes:payload.nodes,edges:payload.edges};state.selectedNode=null;state.selectedEdge=null;state.history=[];state.historyIndex=-1;commit('加载工作流');renderGraph();fitView();toast('工作流已加载','success');
  }

  async function runWorkflow() {
    if(state.running)return;
    if(!state.workflow.nodes.length){toast('工作流中没有节点','error');return;}
    state.workflow.name=refs.workflowName.value.trim()||state.workflow.name;
    state.running=true;$('#runWorkflow').classList.add('running');$('#runWorkflow').innerHTML='<span>◌</span> 正在运行';$('#cancelRun').classList.remove('hidden');refs.activityState.className='activity-state running';refs.progress.classList.remove('hidden');refs.progressBar.style.width='3%';
    log(`开始运行「${state.workflow.name}」`);
    try {
      const result=await api('/api/runs',{method:'POST',body:JSON.stringify({workflow:workflowPayload()})});
      state.runId=result.id||result.run_id||result.task_id;if(!state.runId)throw new Error('服务未返回运行 ID');
      log(`运行任务已创建：${state.runId}`);subscribeRun(state.runId);
    } catch(error){finishRun('failed',error.message);}
  }
  function subscribeRun(id) {
    if(state.eventSource)state.eventSource.close();
    const source=new EventSource(`/api/runs/${encodeURIComponent(id)}/events`);state.eventSource=source;
    source.onmessage=event=>{try{handleRunEvent(JSON.parse(event.data));}catch{log(event.data);}};
    ['started','node_started','node_completed','file_started','file_completed','progress','completed','failed','cancelled'].forEach(type => source.addEventListener(type,event=>{try{handleRunEvent({...JSON.parse(event.data),type});}catch{log(event.data);}}));
    source.addEventListener('log',event=>{try{handleRunEvent(JSON.parse(event.data));}catch{log(event.data);}});
    source.onerror=()=>{source.close();if(state.running)pollRun(id);};
  }
  async function pollRun(id) {
    while(state.running&&state.runId===id){try{const result=await api(`/api/runs/${encodeURIComponent(id)}`);handleRunEvent(result);if(['completed','complete','success','failed','error','cancelled','canceled'].includes(String(result.status).toLowerCase()))return;}catch(error){log(`状态查询失败：${error.message}`,'error');}await new Promise(r=>setTimeout(r,1200));}
  }
  function handleRunEvent(event) {
    if(event.message||event.log)log(event.message||event.log,event.level==='error'?'error':'');
    const progress=Number(event.progress??event.percent);if(Number.isFinite(progress))refs.progressBar.style.width=`${progress<=1?progress*100:progress}%`;
    if(event.node_id){$$('.node.running').forEach(n=>n.classList.remove('running'));$(`.node[data-node-id="${CSS.escape(event.node_id)}"]`)?.classList.add('running');}
    const status=String(event.status||event.type||'').toLowerCase();
    if(['completed','complete','success','done'].includes(status))finishRun('success',event.message||'工作流运行完成');
    if(['failed','error'].includes(status))finishRun('failed',event.error||event.message||'工作流运行失败');
    if(['cancelled','canceled'].includes(status))finishRun('cancelled','运行已取消');
  }
  function finishRun(status,message) {
    state.running=false;if(state.eventSource){state.eventSource.close();state.eventSource=null;}$('#runWorkflow').classList.remove('running');$('#runWorkflow').innerHTML='<span>▶</span> 运行工作流';$('#cancelRun').classList.add('hidden');$$('.node.running').forEach(n=>n.classList.remove('running'));
    refs.activityState.className=`activity-state ${status==='success'?'success':status==='failed'?'error':''}`;refs.progressBar.style.width=status==='success'?'100%':'0';log(message,status==='success'?'success':status==='failed'?'error':'muted');toast(message,status==='success'?'success':status==='failed'?'error':'');state.runId=null;
  }
  async function cancelRun() {
    if(!state.runId)return;log('正在取消运行…');
    try{await api(`/api/runs/${encodeURIComponent(state.runId)}`,{method:'DELETE'});}catch{try{await api(`/api/runs/${encodeURIComponent(state.runId)}/cancel`,{method:'POST'});}catch(error){toast(`取消失败：${error.message}`,'error');return;}}finishRun('cancelled','运行已取消');
  }

  function bindGlobalEvents() {
    refs.viewport.addEventListener('pointerdown',event=>{if(event.button!==0||event.target.closest('.node,.edge-hit'))return;state.selectedNode=null;state.selectedEdge=null;renderSelection();renderEdges();renderInspector();state.panning={x:event.clientX,y:event.clientY,tx:state.transform.x,ty:state.transform.y};refs.viewport.classList.add('panning');refs.viewport.setPointerCapture(event.pointerId);});
    refs.viewport.addEventListener('pointermove',event=>{
      if(state.panning){state.transform.x=state.panning.tx+event.clientX-state.panning.x;state.transform.y=state.panning.ty+event.clientY-state.panning.y;applyTransform();}
      if(state.dragging){const node=state.workflow.nodes.find(x=>x.id===state.dragging.id);if(!node)return;const dx=(event.clientX-state.dragging.startX)/state.transform.scale,dy=(event.clientY-state.dragging.startY)/state.transform.scale;node.data.x=Math.round(state.dragging.nodeX+dx);node.data.y=Math.round(state.dragging.nodeY+dy);state.dragging.moved=Math.abs(dx)+Math.abs(dy)>2;const el=$(`.node[data-node-id="${CSS.escape(node.id)}"]`);el.style.left=`${node.data.x}px`;el.style.top=`${node.data.y}px`;renderEdges();drawMinimap();}
    });
    refs.viewport.addEventListener('pointerup',()=>{if(state.dragging?.moved)commit('移动节点');state.panning=null;state.dragging=null;refs.viewport.classList.remove('panning');});
    refs.viewport.addEventListener('wheel',event=>{event.preventDefault();const rect=refs.viewport.getBoundingClientRect();setZoom(state.transform.scale*(event.deltaY>0?.9:1.1),event.clientX-rect.left,event.clientY-rect.top);},{passive:false});
    refs.viewport.addEventListener('dragover',event=>{event.preventDefault();event.dataTransfer.dropEffect='copy';});
    refs.viewport.addEventListener('drop',event=>{event.preventDefault();try{const data=JSON.parse(event.dataTransfer.getData('application/x-audioflow-node'));const rect=refs.viewport.getBoundingClientRect(),p=screenToWorld(event.clientX-rect.left,event.clientY-rect.top);addFromTemplate(data.type,data.id,{x:p.x-112,y:p.y-25});}catch{}});
    document.addEventListener('keydown',event=>{if(['INPUT','SELECT','TEXTAREA'].includes(event.target.tagName))return;if(event.key==='Delete'||event.key==='Backspace')removeSelected();if(event.key==='Escape')cancelConnection();if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z'){event.preventDefault();restoreHistory(state.historyIndex+(event.shiftKey?1:-1));}if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='s'){event.preventDefault();saveWorkflow();}});
    $('#zoomIn').addEventListener('click',()=>setZoom(state.transform.scale*1.12));$('#zoomOut').addEventListener('click',()=>setZoom(state.transform.scale*.88));$('#zoomReset').addEventListener('click',()=>{state.transform={x:0,y:0,scale:1};applyTransform();});$('#fitView').addEventListener('click',fitView);
    $('#undoButton').addEventListener('click',()=>restoreHistory(state.historyIndex-1));$('#redoButton').addEventListener('click',()=>restoreHistory(state.historyIndex+1));
    $('#modelSearch').addEventListener('input',renderLibrary);$('#architectureFilter').addEventListener('change',renderLibrary);
    $('#refreshToggle').addEventListener('click',event=>{event.stopPropagation();$('#refreshMenu').classList.toggle('hidden');});document.addEventListener('click',()=>$('#refreshMenu').classList.add('hidden'));$$('#refreshMenu button').forEach(b=>b.addEventListener('click',()=>refreshModels(b.dataset.scope)));
    refs.workflowName.addEventListener('input',()=>{state.workflow.name=refs.workflowName.value;refs.canvasTitle.textContent=refs.workflowName.value;commit('重命名工作流');});
    $('#saveWorkflow').addEventListener('click',saveWorkflow);$('#loadWorkflow').addEventListener('click',()=>$('#workflowFile').click());$('#workflowFile').addEventListener('change',async event=>{try{loadWorkflowData(JSON.parse(await event.target.files[0].text()));}catch(error){toast(`加载失败：${error.message}`,'error');}event.target.value='';});
    $('#newWorkflow').addEventListener('click',()=>{if(state.dirty&&!confirm('当前工作流有未保存的更改，仍要新建吗？'))return;state.workflow={id:uid('workflow'),name:'未命名工作流',nodes:[],edges:[]};state.history=[];state.historyIndex=-1;commit('新建工作流');renderGraph();});
    $('#runWorkflow').addEventListener('click',runWorkflow);$('#cancelRun').addEventListener('click',cancelRun);$('#closeInspector').addEventListener('click',()=>{state.selectedNode=null;state.selectedEdge=null;renderSelection();renderEdges();renderInspector();});
    $('#activityToggle').addEventListener('click',()=>{$('.activity-panel').classList.toggle('collapsed');$('#activityChevron').textContent=$('.activity-panel').classList.contains('collapsed')?'⌄':'⌃';});
    window.addEventListener('resize',drawMinimap);
  }

  function initWorkflow() {
    const saved=localStorage.getItem('audioflow:autosave');
    if(saved){try{loadWorkflowData(JSON.parse(saved));state.dirty=false;$('.save-dot').style.background='var(--green)';return;}catch{/* ignore */}}
    const input=makeNode('input_folder',80,150), output=makeNode('output_folder',445,180);state.workflow.nodes=[input,output];commit('初始工作流');state.dirty=false;renderGraph();
  }

  bindGlobalEvents();initWorkflow();applyTransform();loadModels();
})();
