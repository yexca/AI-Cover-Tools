(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const uid = prefix => `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
  const i18n = window.AudioFlowI18n;
  const t = (key, params) => i18n.t(key, params);
  const plural = (key, count, params) => i18n.plural(key, count, params);
  const now = () => i18n.formatTime();
  const deepClone = value => JSON.parse(JSON.stringify(value));
  const ACTIVE_RUN_STATUSES = new Set(['queued', 'running', 'cancelling']);
  const TERMINAL_RUN_STATUSES = new Set(['completed', 'complete', 'success', 'done', 'failed', 'error', 'cancelled', 'canceled']);
  const LEGACY_AUTOSAVE_KEY = 'audioflow:autosave';
  const LEGACY_AUTOSAVE_DIRTY_KEY = 'audioflow:autosave-dirty';
  const DRAFT_INDEX_KEY = 'audioflow:draft-index-v2';
  const DRAFT_KEY_PREFIX = 'audioflow:draft-v2:';
  const TAB_STATE_KEY = 'audioflow:workflow-tabs-v2';
  const SIDEBAR_LAYOUT_KEY = 'audioflow:sidebar-layout-v1';
  const SIDEBAR_LIMITS = {
    library: { min:220, max:520, defaultWidth:320 },
    inspector: { min:260, max:520, defaultWidth:360 }
  };
  const MAX_DRAFTS = 20;

  function readSidebarLayout() {
    try { return JSON.parse(localStorage.getItem(SIDEBAR_LAYOUT_KEY) || '{}'); }
    catch { return {}; }
  }

  const savedSidebarLayout = readSidebarLayout();

  const refs = {
    viewport: $('#viewport'), world: $('#world'), nodes: $('#nodesLayer'), svg: $('#connectionsSvg'),
    library: $('#nodeLibrary'), inspector: $('#inspectorContent'), hint: $('#connectionHint'),
    empty: $('#emptyCanvas'), minimap: $('#minimap canvas'), log: $('#activityLog'),
    progress: $('#runProgress'), progressBar: $('#runProgressBar'), activityState: $('#activityState'),
    workflowName: $('#workflowName'), canvasTitle: $('#canvasTitle'), zoomLabel: $('#zoomReset'),
    workflowList: $('#workflowList'), workflowTabs: $('#workflowTabs'), runList: $('#runList'), activeRunCount: $('#activeRunCount'),
    appShell: $('.app-shell'), libraryPanel: $('#libraryPanel'), inspectorPanel: $('#propertiesPanel'),
    libraryResizer: $('#libraryResizer'), inspectorResizer: $('#inspectorResizer')
  };

  const palette = {
    input_file: '#4fc3df', input_folder: '#4fc3df', separator: '#9a6cf2',
    slicer: '#f3a45f', peak_normalize: '#e66f8f', output_folder: '#54d69a'
  };
  const icons = { input_file: '♪', input_folder: '▱', separator: '⌁', slicer: '✂', peak_normalize: '↕', output_folder: '↳' };
  const nodeTypeKeys = {
    input_file: 'node.type.inputFile', input_folder: 'node.type.inputFolder',
    separator: 'node.type.separator', slicer: 'node.type.slicer',
    peak_normalize: 'node.type.peakNormalize', output_folder: 'node.type.outputFolder'
  };
  const nodeTitleKeys = {
    input_file: 'node.template.inputFile.title', input_folder: 'node.template.inputFolder.title',
    slicer: 'node.template.slicer.title', peak_normalize: 'node.template.peakNormalize.title',
    output_folder: 'node.template.outputFolder.title'
  };
  const functionGroups = {
    vocal_separation: 'vocalSeparation', vocals: 'vocalSeparation',
    stem_separation: 'stemSeparation', multi_stem: 'stemSeparation', multistem_separation: 'stemSeparation',
    denoise: 'denoise', noise_reduction: 'denoise', dereverb: 'dereverb', deecho: 'dereverb',
    karaoke: 'vocalCleanup', vocal_cleanup: 'vocalCleanup', unknown: 'needsConfirmation', other: 'other'
  };
  const groupOrder = ['input','vocalSeparation','stemSeparation','denoise','dereverb','vocalCleanup','preparation','other','needsConfirmation','output'];
  const nodeTypeLabel = type => t(nodeTypeKeys[type] || 'node.type.fallback');
  const functionGroup = value => functionGroups[value] || 'other';
  const functionLabel = value => t(`node.function.${functionGroup(value) === 'needsConfirmation' ? 'unknown' : functionGroup(value)}`);
  const groupLabel = group => t(`group.${group}`);

  const state = {
    workflow: { id: uid('workflow'), name: t('workflow.defaultName'), nodes: [], edges: [] },
    models: [], selectedNode: null, selectedEdge: null, pendingPort: null, connectionDrag: null,
    libraryVisible: !window.matchMedia('(max-width:650px)').matches,
    inspectorVisible: !window.matchMedia('(max-width:800px)').matches,
    libraryWidth: Number(savedSidebarLayout.libraryWidth) || SIDEBAR_LIMITS.library.defaultWidth,
    inspectorWidth: Number(savedSidebarLayout.inspectorWidth) || SIDEBAR_LIMITS.inspector.defaultWidth,
    transform: { x: 0, y: 0, scale: 1 }, panning: null, dragging: null,
    sidebarResize: null,
    history: [], historyIndex: -1, running: false, validatingWorkflowIds: new Set(), cancelling: false, runId: null, runStatus: null, eventSource: null, runRefreshTimer: null,
    validation: { nodeErrors: {}, edgeErrors: {}, globalErrors: [], errors: [] },
    activityCollapsed: false, dirty: false, modelCacheUsed: false, modelServiceUnavailable: false,
    workflows: [], workflowSavePending: false, runs: [],
    editors: new Map(), openWorkflowIds: [], activeWorkflowId: null
  };
  let libraryDrawerMode = window.matchMedia('(max-width:650px)').matches;
  let inspectorDrawerMode = window.matchMedia('(max-width:800px)').matches;

  function normalizeOutputs(raw) {
    let outputs = raw.outputs || raw.stems || raw.instruments || raw.output_stems || [];
    if (typeof outputs === 'string') outputs = outputs.split(/[,/|]/).map(x => x.trim()).filter(Boolean);
    if (!Array.isArray(outputs) && outputs && typeof outputs === 'object') outputs = Object.keys(outputs);
    outputs = outputs.map((item, index) => {
      // Handles are an execution contract with audio-separator. Keep the exact
      // registry stem (including case and spaces); labels are presentation only.
      if (typeof item === 'string') return { id: item, label: item };
      return { id: item.id || item.name || item.stem || `output_${index + 1}`, label: item.label || item.name || item.stem || t('port.output') + ` ${index + 1}` };
    });
    if (!outputs.length) outputs = [{ id: 'output', label: t('port.output') }];
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
      const message = typeof detail === 'string' ? detail : detail?.message || (detail?.errors ? detail.errors.join('; ') : detail ? JSON.stringify(detail) : t('error.http', { status:response.status, statusText:response.statusText }));
      const error = new Error(message);
      error.status = response.status;
      error.code = data?.error?.code || data?.detail?.error?.code || null;
      error.payload = data;
      throw error;
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

  function formatDateTime(value) {
    if (!value) return '';
    try { return i18n.formatDateTime(value); } catch { return String(value); }
  }

  function showManager(id) {
    $$('.manager-overlay').forEach(manager => manager.classList.toggle('hidden', manager.id !== id));
  }

  function closeManager(id) {
    $(`#${CSS.escape(id)}`)?.classList.add('hidden');
  }

  function draftStorageKey(id) {
    return `${DRAFT_KEY_PREFIX}${encodeURIComponent(id)}`;
  }

  function readDraftIndex() {
    try {
      const value = JSON.parse(localStorage.getItem(DRAFT_INDEX_KEY) || '[]');
      return Array.isArray(value) ? value.filter(item => item && typeof item.id === 'string') : [];
    } catch { return []; }
  }

  function writeDraftIndex(index) {
    try { localStorage.setItem(DRAFT_INDEX_KEY, JSON.stringify(index)); } catch { /* storage may be unavailable */ }
  }

  function readDraft(id) {
    try {
      const value = JSON.parse(localStorage.getItem(draftStorageKey(id)) || 'null');
      return value && value.workflow?.id === id ? value : null;
    } catch { return null; }
  }

  function removeDraft(id) {
    try { localStorage.removeItem(draftStorageKey(id)); } catch { /* storage may be unavailable */ }
    writeDraftIndex(readDraftIndex().filter(item => item.id !== id));
  }

  function writeDraft(record) {
    let index = readDraftIndex().filter(item => item.id !== record.workflow.id);
    const entry = { id:record.workflow.id, name:record.workflow.name, updatedAt:record.updatedAt };
    index.push(entry);
    while (index.length > MAX_DRAFTS) {
      const evicted = index.shift();
      if (evicted?.id !== record.workflow.id) {
        try { localStorage.removeItem(draftStorageKey(evicted.id)); } catch { /* storage may be unavailable */ }
      }
    }
    try {
      localStorage.setItem(draftStorageKey(record.workflow.id), JSON.stringify(record));
      writeDraftIndex(index);
      return true;
    } catch {
      while (index.length > 1) {
        const evicted = index.shift();
        try {
          localStorage.removeItem(draftStorageKey(evicted.id));
          localStorage.setItem(draftStorageKey(record.workflow.id), JSON.stringify(record));
          writeDraftIndex(index);
          return true;
        } catch { /* keep evicting old drafts */ }
      }
      return false;
    }
  }

  function persistTabState() {
    try {
      sessionStorage.setItem(TAB_STATE_KEY, JSON.stringify({
        openIds:state.openWorkflowIds,
        activeId:state.activeWorkflowId
      }));
    } catch { /* storage may be unavailable */ }
  }

  function readTabState() {
    try {
      const value = JSON.parse(sessionStorage.getItem(TAB_STATE_KEY) || 'null');
      return value && Array.isArray(value.openIds) ? value : null;
    } catch { return null; }
  }

  function captureActiveEditor() {
    const editor = state.editors.get(state.activeWorkflowId);
    if (!editor) return;
    editor.workflow = state.workflow;
    editor.history = state.history;
    editor.historyIndex = state.historyIndex;
    editor.dirty = state.dirty;
    editor.transform = {...state.transform};
  }

  function registerEditor(workflow, { dirty = true, persisted = Number(workflow.revision || 0) > 0 } = {}) {
    workflow.revision = Number(workflow.revision || 0);
    const editor = {
      workflow,
      history:[JSON.stringify(workflow)],
      historyIndex:0,
      dirty:Boolean(dirty),
      persisted:Boolean(persisted),
      transform:{x:0,y:0,scale:1}
    };
    state.editors.set(workflow.id, editor);
    if (!state.openWorkflowIds.includes(workflow.id)) state.openWorkflowIds.push(workflow.id);
    return editor;
  }

  function renderWorkflowTabs() {
    refs.workflowTabs.innerHTML = state.openWorkflowIds.map(id => {
      const editor = state.editors.get(id);
      if (!editor) return '';
      const activeRun = state.runs.some(run => run.workflow_id === id && ACTIVE_RUN_STATUSES.has(normalizeRunStatus(run.status)));
      const classes = [id === state.activeWorkflowId ? 'active' : '', editor.dirty ? 'dirty' : '', activeRun ? 'running' : ''].filter(Boolean).join(' ');
      return `<div class="workflow-tab ${classes}" role="tab" aria-selected="${id === state.activeWorkflowId}" data-workflow-tab="${escapeHtml(id)}"><span class="workflow-tab-state"></span><button class="workflow-tab-label" data-activate-workflow="${escapeHtml(id)}" title="${escapeHtml(editor.workflow.name)}">${escapeHtml(editor.workflow.name)}</button><button class="workflow-tab-close" data-close-workflow="${escapeHtml(id)}" title="${escapeHtml(t('workflow.tabs.close'))}">×</button></div>`;
    }).join('');
    $$('[data-activate-workflow]', refs.workflowTabs).forEach(button => button.addEventListener('click', () => activateWorkflowEditor(button.dataset.activateWorkflow)));
    $$('[data-close-workflow]', refs.workflowTabs).forEach(button => button.addEventListener('click', event => { event.stopPropagation();closeWorkflowEditor(button.dataset.closeWorkflow); }));
  }

  function activateWorkflowEditor(id, { fit = false } = {}) {
    const editor = state.editors.get(id);
    if (!editor) return false;
    flushActiveInspectorField();
    captureActiveEditor();
    resetGraphInteractions();
    state.activeWorkflowId = id;
    state.workflow = editor.workflow;
    state.history = editor.history;
    state.historyIndex = editor.historyIndex;
    state.transform = {...editor.transform};
    state.selectedNode = null;
    state.selectedEdge = null;
    clearValidation();
    refs.workflowName.value = state.workflow.name;
    refs.canvasTitle.textContent = state.workflow.name;
    setDirty(editor.dirty);
    applyTransform();
    renderGraph();
    if (fit) fitView();
    persistTabState();
    renderWorkflowTabs();
    reconcileActiveWorkflowRun();
    return true;
  }

  function closeWorkflowEditor(id) {
    const editor = state.editors.get(id);
    if (!editor) return;
    if (editor.dirty && !confirm(t('workflow.confirm.close', { name:editor.workflow.name }))) return;
    const index = state.openWorkflowIds.indexOf(id);
    const wasActive = id === state.activeWorkflowId;
    removeDraft(id);
    state.editors.delete(id);
    state.openWorkflowIds = state.openWorkflowIds.filter(item => item !== id);
    if (wasActive) {
      state.activeWorkflowId = null;
      const nextId = state.openWorkflowIds[Math.min(index, state.openWorkflowIds.length - 1)];
      if (nextId) activateWorkflowEditor(nextId);
      else createNewWorkflow();
    } else {
      persistTabState();
      renderWorkflowTabs();
    }
  }

  function renderModelStatus() {
    const count = state.models.filter(model => model.installed).length;
    if (state.modelServiceUnavailable && !state.models.length) $('#modelCount').textContent = t('library.api.modelsUnavailable');
    else $('#modelCount').textContent = plural(state.modelCacheUsed ? 'library.models.installedCached' : 'library.models.installed', count);
    if ($('#apiStatus').classList.contains('ok')) $('#apiStatus').title = t('library.api.connected');
    if ($('#apiStatus').classList.contains('error')) $('#apiStatus').title = t('library.api.unavailable');
  }

  async function loadModels(forceNetwork = false) {
    const cached = localStorage.getItem('audioflow:model-cache');
    if (cached && !forceNetwork) {
      try {
        state.models = unwrapModels(JSON.parse(cached));
        state.modelCacheUsed = true;
        renderLibrary();
        renderModelStatus();
      } catch { /* ignore corrupt cache */ }
    }
    try {
      const payload = await api('/api/models');
      state.models = unwrapModels(payload);
      localStorage.setItem('audioflow:model-cache', JSON.stringify(state.models));
      state.modelCacheUsed = false;
      state.modelServiceUnavailable = false;
      $('#apiStatus').className = 'status-dot ok';
      renderModelStatus();
      renderLibrary();
    } catch (error) {
      state.modelServiceUnavailable = true;
      $('#apiStatus').className = 'status-dot error';
      renderModelStatus();
      log(t('library.api.modelsReadFailed', { error:error.message }), 'error');
      renderLibrary();
    }
  }

  async function refreshModels(scope) {
    $('#refreshToggle').classList.add('spin');
    $('#refreshMenu').classList.add('hidden');
    toast(t(scope === 'local' ? 'library.refresh.local.started' : 'library.refresh.catalog.started'));
    log(t(scope === 'local' ? 'library.refresh.local.log' : 'library.refresh.catalog.log'));
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
      toast(t('library.refresh.completed'), 'success');
      log(t('library.refresh.completed'), 'success');
    } catch (error) {
      toast(t('library.refresh.failed', { error:error.message }), 'error');
      log(t('library.refresh.failed', { error:error.message }), 'error');
    } finally { $('#refreshToggle').classList.remove('spin'); }
  }

  async function pollRefresh(id) {
    if (!id) return;
    for (let i = 0; i < 120; i++) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      try {
        const result = await api(`/api/models/refresh/${encodeURIComponent(id)}`);
        if (result.status === 'failed') throw new Error(result.error || t('library.refresh.taskFailed'));
        if (['complete', 'completed', 'success'].includes(result.status)) return result;
      } catch (error) {
        if (error.message.includes('404')) return;
        throw error;
      }
    }
    throw new Error(t('library.refresh.timeout'));
  }

  function fixedTemplates() {
    return [
      { type: 'input_file', title: t('node.template.inputFile.title'), subtitle: t('node.template.inputFile.description'), group: 'input', color: palette.input_file },
      { type: 'input_folder', title: t('node.template.inputFolder.title'), subtitle: t('node.template.inputFolder.description'), group: 'input', color: palette.input_folder },
      { type: 'slicer', title: t('node.template.slicer.title'), subtitle: t('node.template.slicer.description'), group: 'preparation', color: palette.slicer },
      { type: 'peak_normalize', title: t('node.template.peakNormalize.title'), subtitle: t('node.template.peakNormalize.description'), group: 'preparation', color: palette.peak_normalize },
      { type: 'output_folder', title: t('node.template.outputFolder.title'), subtitle: t('node.template.outputFolder.description'), group: 'output', color: palette.output_folder }
    ];
  }

  function renderLibrary() {
    const search = $('#modelSearch').value.trim().toLowerCase();
    const architecture = $('#architectureFilter').value;
    const installed = state.models.filter(model => model.installed);
    const architectures = [...new Set(installed.map(x => x.architecture).filter(Boolean))].sort();
    const previous = architecture;
    $('#architectureFilter').innerHTML = `<option value="">${escapeHtml(t('library.filter.allArchitectures'))}</option>` + architectures.map(x => `<option value="${escapeHtml(x)}">${escapeHtml(x)}</option>`).join('');
    $('#architectureFilter').value = architectures.includes(previous) ? previous : '';

    const groups = new Map();
    const matches = item => !search || `${item.title} ${item.subtitle} ${item.architecture || ''}`.toLowerCase().includes(search);
    fixedTemplates().filter(matches).forEach(item => {
      if (!groups.has(item.group)) groups.set(item.group, []);
      groups.get(item.group).push(item);
    });
    installed.filter(model => (!architecture || model.architecture === architecture) && matches({ title:model.name, subtitle:functionLabel(model.function), architecture:model.architecture })).forEach(model => {
      const group = functionGroup(model.function);
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push({ type: 'separator', title: model.name, subtitle: `${model.architecture} · ${model.outputs.map(x => x.label).join(' / ')}`, group, model, color: palette.separator });
    });
    const html = groupOrder.filter(group => groups.has(group)).map(group => {
      const items = groups.get(group);
      return `<section class="library-group" data-group="${escapeHtml(group)}">
        <button class="group-heading"><span>${escapeHtml(groupLabel(group))} <em>${i18n.formatNumber(items.length)}</em></span><span>⌄</span></button>
        <div class="group-items">${items.map(item => `<div class="node-template" draggable="true" data-template-id="${escapeHtml(item.model?.id || item.type)}" data-type="${item.type}" style="--item-color:${item.color}">
          <span class="template-icon">${icons[item.type]}</span><span class="template-copy"><b title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</b><span title="${escapeHtml(item.subtitle)}">${escapeHtml(item.subtitle)}</span></span><span class="drag-dots">⠿</span>
        </div>`).join('')}</div></section>`;
    }).join('');
    refs.library.innerHTML = html || `<div class="empty-library">${escapeHtml(t('library.models.empty')).replace(/\n/g, '<br>')}</div>`;
    $$('.group-heading', refs.library).forEach(button => button.addEventListener('click', () => button.closest('.library-group').classList.toggle('collapsed')));
    $$('.node-template', refs.library).forEach(template => {
      template.addEventListener('dragstart', event => event.dataTransfer.setData('application/x-audioflow-node', JSON.stringify({ type: template.dataset.type, id: template.dataset.templateId })));
      template.addEventListener('dblclick', () => addFromTemplate(template.dataset.type, template.dataset.templateId));
    });
  }

  function makeNode(type, x, y, model = null) {
    const base = { id: uid('node'), type, data: { x: Math.round(x), y: Math.round(y), title: '', title_customized: false, config: {} } };
    if (type === 'input_file') {
      base.data.outputs = [{ id:'audio', label:'audio' }]; base.data.config = { path: '' };
    } else if (type === 'input_folder') {
      base.data.outputs = [{ id:'audio', label:'audio' }]; base.data.config = { path:'', recursive:true, include:'*.wav;*.flac;*.mp3;*.m4a' };
    } else if (type === 'output_folder') {
      base.data.inputs = [{ id:'audio', label:'audio' }]; base.data.config = { path:'outputs', naming:'{basename}_{stem}.{ext}', format:'wav', conflict:'rename' };
    } else if (type === 'separator') {
      base.data.title = model?.name || 'Audio Separator';
      base.data.title_customized = true;
      base.data.model_id = model?.id || '';
      base.data.model_filename = model?.filename || '';
      base.data.architecture = model?.architecture || 'Unknown';
      base.data.function = model?.function || 'unknown';
      base.data.inputs = [{ id:'audio', label:'audio' }];
      base.data.outputs = model?.outputs || [{ id:'output', label:'output' }];
      base.data.config = { output_format:'wav', normalization_threshold:0.9 };
    } else if (type === 'slicer') {
      base.data.inputs = [{ id:'audio', label:'audio' }];
      base.data.outputs = [{ id:'audio', label:'audio' }];
      base.data.config = { threshold:-40, min_length:5000, min_interval:300, hop_size:10, max_sil_kept:1000, output_format:'wav' };
    } else if (type === 'peak_normalize') {
      base.data.inputs = [{ id:'audio', label:'audio' }];
      base.data.outputs = [{ id:'audio', label:'audio' }];
      base.data.config = { target_peak_db:-3 };
    }
    return base;
  }

  function addFromTemplate(type, templateId, position = null) {
    flushActiveInspectorField();
    resetGraphInteractions();
    const center = screenToWorld(refs.viewport.clientWidth * .45, refs.viewport.clientHeight * .42);
    const model = type === 'separator' ? state.models.find(x => x.id === templateId) : null;
    const node = makeNode(type, position?.x ?? center.x, position?.y ?? center.y, model);
    state.workflow.nodes.push(node);
    selectNode(node.id);
    commit('添加节点');
    renderGraph();
    document.body.classList.remove('library-open');
  }

  function getInputs(node) { return node.data.inputs || []; }
  function getOutputs(node) { return node.data.outputs || []; }

  function defaultNodeTitle(node) {
    if (node.type === 'separator') return node.data.title || 'Audio Separator';
    return t(nodeTitleKeys[node.type] || nodeTypeKeys[node.type] || 'node.type.fallback');
  }

  function nodeTitle(node) {
    return node.data.title_customized ? (node.data.title || defaultNodeTitle(node)) : defaultNodeTitle(node);
  }

  function isLocalizedDefaultTitle(node) {
    if (!node.data.title || node.type === 'separator') return false;
    const keys = [nodeTitleKeys[node.type], nodeTypeKeys[node.type]].filter(Boolean);
    return Object.values(window.AudioFlowLocales || {}).some(locale => keys.some(key => locale[key] === node.data.title));
  }

  function portLabel(node, port, direction) {
    if (port.id === 'audio') return t(node.type === 'input_folder' && direction === 'output' ? 'port.audioBatch' : 'port.audio');
    if (node.type !== 'separator' && port.id === 'output') return t('port.output');
    return port.label || port.id;
  }

  function nodeHtml(node) {
    const typeLabel = node.type === 'separator' ? functionLabel(node.data.function) : nodeTypeLabel(node.type);
    const validationErrors = state.validation.nodeErrors[node.id] || [];
    const info = node.type === 'separator'
      ? `<div class="node-info-row"><span>${escapeHtml(t('node.info.model'))}</span><strong title="${escapeHtml(node.data.model_filename)}">${escapeHtml(node.data.model_filename || nodeTitle(node))}</strong></div><div class="node-info-row"><span>${escapeHtml(t('node.info.architecture'))}</span><strong>${escapeHtml(node.data.architecture || t('model.architecture.unknown'))}</strong></div>`
      : node.type === 'input_folder' ? `<div class="node-info-row"><span>${escapeHtml(t('node.info.scan'))}</span><strong>${escapeHtml(t(node.data.config.recursive ? 'node.info.includeSubfolders' : 'node.info.currentFolder'))}</strong></div>`
      : node.type === 'slicer' ? `<div class="node-info-row"><span>${escapeHtml(t('node.info.format'))}</span><strong>${escapeHtml((node.data.config.output_format || 'wav').toUpperCase())}</strong></div>`
      : node.type === 'peak_normalize' ? `<div class="node-info-row"><span>${escapeHtml(t('node.info.targetPeak'))}</span><strong>${escapeHtml(String(node.data.config.target_peak_db ?? -3))} dB</strong></div>`
      : node.type === 'output_folder' ? `<div class="node-info-row"><span>${escapeHtml(t('node.info.format'))}</span><strong>${escapeHtml((node.data.config.format || 'wav').toUpperCase())}</strong></div>`
      : `<div class="node-info-row"><span>${escapeHtml(t('node.info.source'))}</span><strong>${escapeHtml(t(node.data.config.path ? 'node.info.selected' : 'node.info.notSelected'))}</strong></div>`;
    const inputs = getInputs(node).map(port => `<div class="port-row"><div class="port-label"><i class="port input" data-direction="input" data-port="${escapeHtml(port.id)}" style="--port-color:#55c9e5"></i><span>${escapeHtml(portLabel(node, port, 'input'))}</span></div></div>`).join('');
    const outputs = getOutputs(node).map((port, i) => `<div class="port-row"><div class="port-label output"><span>${escapeHtml(portLabel(node, port, 'output'))}</span><i class="port output" data-direction="output" data-port="${escapeHtml(port.id)}" style="--port-color:${i % 2 ? '#f3a45f' : '#9a6cf2'}"></i></div></div>`).join('');
    return `<article class="node ${state.selectedNode === node.id ? 'selected' : ''} ${validationErrors.length ? 'validation-error' : ''}" data-node-id="${node.id}" title="${escapeHtml(validationErrors.length ? friendlyValidationError(validationErrors[0]) : '')}" style="left:${node.data.x}px;top:${node.data.y}px;--node-color:${palette[node.type] || palette.separator}">
      <header class="node-header"><span class="node-header-icon">${icons[node.type] || '◇'}</span><span class="node-title"><b>${escapeHtml(nodeTitle(node))}</b><span>${escapeHtml(typeLabel)}</span></span>${validationErrors.length ? '<span class="node-error-mark">!</span>' : ''}<button class="node-menu" title="${escapeHtml(t('node.action.delete'))}">•••</button></header>
      <div class="node-body"><div class="node-info">${info}</div>${inputs}${outputs}</div>
      <footer class="node-footer"><span class="node-badge">${node.type === 'separator' ? escapeHtml(node.data.architecture || 'MODEL') : escapeHtml(node.type.replace('_',' '))}</span><button class="node-remove" title="${escapeHtml(t('node.action.delete'))}">×</button></footer>
    </article>`;
  }

  function renderGraph() {
    refs.nodes.innerHTML = state.workflow.nodes.map(nodeHtml).join('');
    $$('.node', refs.nodes).forEach(element => bindNode(element));
    requestAnimationFrame(() => { renderEdges(); drawMinimap(); });
    refs.empty.classList.toggle('hidden', state.workflow.nodes.length > 0);
    $('#nodeCount').textContent = plural('canvas.nodeCount', state.workflow.nodes.length);
    $('#edgeCount').textContent = plural('canvas.edgeCount', state.workflow.edges.length);
    refs.workflowName.value = state.workflow.name;
    refs.canvasTitle.textContent = state.workflow.name;
    renderInspector();
  }

  function bindNode(element) {
    const id = element.dataset.nodeId;
    element.addEventListener('pointerdown', event => {
      if (event.target.closest('.port,.node-remove,.node-menu')) return;
      selectNode(id); renderSelection(); renderInspector();
    });
    $('.node-header', element).addEventListener('pointerdown', event => startNodeDrag(event, id));
    $$('.port', element).forEach(port => {
      port.addEventListener('pointerdown', event => startPortDrag(event, id, port.dataset.port, port.dataset.direction, port));
      port.addEventListener('click', event => { event.preventDefault(); event.stopPropagation(); });
    });
    $$('.node-remove,.node-menu', element).forEach(button => button.addEventListener('click', event => { event.stopPropagation(); removeNode(id); }));
  }

  function startNodeDrag(event, id) {
    if (event.button !== 0 || event.target.closest('button,input,select,textarea,a,.port')) return;
    cancelPointerInteractions(true);
    cancelConnection();
    event.stopPropagation();
    event.preventDefault();
    const node = state.workflow.nodes.find(x => x.id === id);
    const usesInspectorDrawer = window.matchMedia('(max-width:800px)').matches;
    selectNode(id, { revealInspector:!usesInspectorDrawer }); renderSelection(); renderInspector();
    if (usesInspectorDrawer) setInspectorVisible(false);
    state.dragging = { id, pointerId:event.pointerId, captureEl:event.currentTarget, startX:event.clientX, startY:event.clientY, nodeX:node.data.x, nodeY:node.data.y, moved:false };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function startPortDrag(event, nodeId, portId, direction, element) {
    if (event.button !== 0) return;
    cancelPointerInteractions(true);
    event.preventDefault();
    event.stopPropagation();
    const usesInspectorDrawer = window.matchMedia('(max-width:800px)').matches;
    selectNode(nodeId, { revealInspector:!usesInspectorDrawer }); renderSelection(); renderInspector();
    if (usesInspectorDrawer) setInspectorVisible(false);
    const point = clientToWorld(event.clientX, event.clientY);
    const incoming = direction === 'input'
      ? state.workflow.edges.find(edge => edge.target === nodeId && edge.target_handle === portId)
      : null;
    state.connectionDrag = {
      pointerId: event.pointerId, captureEl: element, origin: { nodeId, portId, direction },
      point, startX: event.clientX, startY: event.clientY, moved: false,
      target: null, replacedEdgeId: incoming?.id || null
    };
    refs.viewport.classList.add('connecting');
    markCompatiblePorts(direction, nodeId);
    element.classList.add('pending');
    refs.hint.textContent = t(direction === 'output' ? 'connection.dragToInput' : 'connection.dragToOutput');
    refs.hint.classList.remove('hidden');
    element.setPointerCapture(event.pointerId);
    renderEdges();
  }

  function clientToWorld(clientX, clientY) {
    const rect = refs.viewport.getBoundingClientRect();
    return screenToWorld(clientX - rect.left, clientY - rect.top);
  }

  function portDescriptor(element) {
    const node = element?.closest('.node');
    if (!node || !element.classList.contains('port')) return null;
    return { nodeId: node.dataset.nodeId, portId: element.dataset.port, direction: element.dataset.direction, element };
  }

  function compatiblePorts(a, b) {
    const directions = new Set([a?.direction, b?.direction]);
    return Boolean(a && b && directions.has('input') && directions.has('output') && directions.size === 2 && a.nodeId !== b.nodeId);
  }

  function workflowHasPort(descriptor) {
    if (!descriptor || !['input','output'].includes(descriptor.direction)) return false;
    const node = state.workflow.nodes.find(item => item.id === descriptor.nodeId);
    if (!node) return false;
    const ports = descriptor.direction === 'input' ? getInputs(node) : getOutputs(node);
    return ports.some(port => String(port?.id ?? port) === String(descriptor.portId));
  }

  function connectionTargetAt(clientX, clientY, origin) {
    const element = document.elementFromPoint(clientX, clientY)?.closest?.('.port');
    const target = portDescriptor(element);
    return compatiblePorts(origin, target) ? target : null;
  }

  function markCompatiblePorts(direction, originNodeId) {
    $$('.port', refs.nodes).forEach(port => {
      const nodeId = port.closest('.node')?.dataset.nodeId;
      port.classList.toggle('compatible', port.dataset.direction !== direction && nodeId !== originNodeId);
      port.classList.remove('drop-target');
    });
  }

  function updateConnectionDrag(event) {
    const drag = state.connectionDrag;
    if (!drag || event.pointerId !== drag.pointerId) return;
    drag.point = clientToWorld(event.clientX, event.clientY);
    drag.moved ||= Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) >= 4;
    drag.target = connectionTargetAt(event.clientX, event.clientY, drag.origin);
    $$('.port.drop-target', refs.nodes).forEach(port => port.classList.remove('drop-target'));
    drag.target?.element.classList.add('drop-target');
    renderEdges();
  }

  function connectPorts(first, second) {
    if (!compatiblePorts(first, second) || !workflowHasPort(first) || !workflowHasPort(second)) {
      toast(t('validation.invalidCheck'), 'error');
      return false;
    }
    const output = first.direction === 'output' ? first : second;
    const input = first.direction === 'input' ? first : second;
    const duplicate = state.workflow.edges.some(edge => edge.source === output.nodeId && edge.source_handle === output.portId && edge.target === input.nodeId && edge.target_handle === input.portId);
    if (duplicate) { toast(t('connection.duplicate')); return false; }
    state.workflow.edges = state.workflow.edges.filter(edge => !(edge.target === input.nodeId && edge.target_handle === input.portId));
    state.workflow.edges.push({ id:uid('edge'), source:output.nodeId, source_handle:output.portId, target:input.nodeId, target_handle:input.portId });
    commit('创建连接');
    state.selectedEdge = state.workflow.edges.length - 1;
    state.selectedNode = null;
    setInspectorVisible(true);
    return true;
  }

  function finishConnectionDrag(event, cancelled = false) {
    const drag = state.connectionDrag;
    if (!drag || (event && event.pointerId !== drag.pointerId)) return false;
    if (event && !cancelled) updateConnectionDrag(event);
    let connected = false;
    if (!cancelled && drag.target) {
      connected = connectPorts(drag.origin, drag.target);
      state.pendingPort = null;
    } else if (!cancelled && !drag.moved) {
      if (state.pendingPort && compatiblePorts(state.pendingPort, drag.origin)) {
        connected = connectPorts(state.pendingPort, drag.origin);
        state.pendingPort = null;
      } else if (state.pendingPort && state.pendingPort.nodeId === drag.origin.nodeId && state.pendingPort.portId === drag.origin.portId) {
        state.pendingPort = null;
      } else {
        state.pendingPort = { ...drag.origin };
      }
    } else {
      state.pendingPort = null;
    }
    state.connectionDrag = null;
    releasePointerCapture(drag);
    refs.viewport.classList.remove('connecting');
    clearPortHighlights();
    if (state.pendingPort) {
      const pending = findPortElement(state.pendingPort);
      pending?.classList.add('pending');
      refs.hint.textContent = t('connection.clickOpposite');
      refs.hint.classList.remove('hidden');
    } else refs.hint.classList.add('hidden');
    if (connected) renderGraph(); else renderEdges();
    return true;
  }

  function findPortElement(descriptor) {
    return $(`.node[data-node-id="${CSS.escape(descriptor.nodeId)}"] .port.${descriptor.direction}[data-port="${CSS.escape(descriptor.portId)}"]`, refs.nodes);
  }

  function clearPortHighlights() {
    $$('.port.pending,.port.compatible,.port.drop-target', refs.nodes).forEach(port => port.classList.remove('pending','compatible','drop-target'));
  }

  function cancelConnection() {
    if (state.connectionDrag) finishConnectionDrag(null, true);
    state.pendingPort = null;
    clearPortHighlights();
    refs.hint.classList.add('hidden');
    renderEdges();
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
      if (state.connectionDrag?.replacedEdgeId && edge.id === state.connectionDrag.replacedEdgeId) return;
      const a = portCenter(edge.source, edge.source_handle, 'output');
      const b = portCenter(edge.target, edge.target_handle, 'input');
      if (!a || !b) return;
      const group = document.createElementNS('http://www.w3.org/2000/svg','g');
      group.dataset.edgeIndex = index;
      group.dataset.edgeId = edge.id || '';
      const path = bezier(a,b);
      const invalid = Boolean(state.validation.edgeErrors[edge.id]);
      group.innerHTML = `<path class="edge-line ${state.selectedEdge === index ? 'active' : ''} ${invalid ? 'validation-error' : ''}" d="${path}"/><path class="edge-hit" d="${path}"/>`;
      $('.edge-hit', group).addEventListener('click', event => { event.stopPropagation(); state.selectedEdge = index; state.selectedNode = null; setInspectorVisible(true); renderSelection(); renderEdges(); renderInspector(); });
      refs.svg.append(group);
    });
    const drag = state.connectionDrag;
    if (drag) {
      const origin = portCenter(drag.origin.nodeId, drag.origin.portId, drag.origin.direction);
      if (origin) {
        const a = drag.origin.direction === 'output' ? origin : drag.point;
        const b = drag.origin.direction === 'output' ? drag.point : origin;
        const path = bezier(a,b);
        const preview = document.createElementNS('http://www.w3.org/2000/svg','g');
        preview.innerHTML = `<path class="edge-preview-halo" d="${path}"/><path class="edge-preview" d="${path}"/>`;
        refs.svg.append(preview);
      }
    }
  }

  function clampSidebarWidth(value, side) {
    const limits = SIDEBAR_LIMITS[side];
    return Math.min(limits.max, Math.max(limits.min, Math.round(Number(value) || limits.defaultWidth)));
  }

  function currentSidebarWidth(side) {
    const property = side === 'library' ? '--library-width' : '--inspector-width';
    const value = parseFloat(getComputedStyle(document.documentElement).getPropertyValue(property));
    return Number.isFinite(value) ? value : SIDEBAR_LIMITS[side].defaultWidth;
  }

  function applySidebarWidths() {
    let libraryWidth = clampSidebarWidth(state.libraryWidth, 'library');
    let inspectorWidth = clampSidebarWidth(state.inspectorWidth, 'inspector');
    if (window.innerWidth > 800) {
      const canvasMinimum = window.innerWidth <= 1050 ? 300 : 420;
      const handleWidth = (state.libraryVisible ? 6 : 0) + (state.inspectorVisible ? 6 : 0);
      const available = Math.max(0, window.innerWidth - canvasMinimum - handleWidth);
      const libraryUsed = state.libraryVisible ? libraryWidth : 0;
      const inspectorUsed = state.inspectorVisible ? inspectorWidth : 0;
      const excess = libraryUsed + inspectorUsed - available;
      if (excess > 0 && state.libraryVisible && state.inspectorVisible) {
        const librarySlack = libraryWidth - SIDEBAR_LIMITS.library.min;
        const inspectorSlack = inspectorWidth - SIDEBAR_LIMITS.inspector.min;
        const totalSlack = librarySlack + inspectorSlack;
        if (totalSlack > 0) {
          libraryWidth -= excess * librarySlack / totalSlack;
          inspectorWidth -= excess * inspectorSlack / totalSlack;
        }
      } else if (excess > 0 && state.libraryVisible) {
        libraryWidth = Math.max(SIDEBAR_LIMITS.library.min, libraryWidth - excess);
      } else if (excess > 0 && state.inspectorVisible) {
        inspectorWidth = Math.max(SIDEBAR_LIMITS.inspector.min, inspectorWidth - excess);
      }
    } else if (window.innerWidth > 650 && state.libraryVisible) {
      libraryWidth = Math.min(libraryWidth, Math.max(SIDEBAR_LIMITS.library.min, window.innerWidth - 300));
    }
    libraryWidth = Math.round(libraryWidth);
    inspectorWidth = Math.round(inspectorWidth);
    document.documentElement.style.setProperty('--library-width', `${libraryWidth}px`);
    document.documentElement.style.setProperty('--inspector-width', `${inspectorWidth}px`);
    refs.libraryResizer?.setAttribute('aria-valuenow', String(libraryWidth));
    refs.inspectorResizer?.setAttribute('aria-valuenow', String(inspectorWidth));
    refs.libraryResizer?.setAttribute('aria-valuemax', String(Math.round(sidebarMaximum('library'))));
    refs.inspectorResizer?.setAttribute('aria-valuemax', String(Math.round(sidebarMaximum('inspector'))));
    return { library:libraryWidth, inspector:inspectorWidth };
  }

  function persistSidebarLayout() {
    try { localStorage.setItem(SIDEBAR_LAYOUT_KEY, JSON.stringify({ libraryWidth:state.libraryWidth, inspectorWidth:state.inspectorWidth })); }
    catch { /* storage may be unavailable */ }
  }

  function scheduleSidebarRedraw() {
    requestAnimationFrame(() => { renderEdges(); drawMinimap(); });
  }

  function setLibraryVisible(visible) {
    const nextVisible = Boolean(visible);
    const layoutChanged = state.libraryVisible !== nextVisible || document.body.classList.contains('library-open') !== nextVisible;
    state.libraryVisible = nextVisible;
    document.body.classList.toggle('library-open', state.libraryVisible);
    document.body.classList.toggle('library-hidden', !state.libraryVisible);
    refs.libraryPanel?.setAttribute('aria-hidden', String(!state.libraryVisible));
    if (refs.libraryPanel) refs.libraryPanel.inert = !state.libraryVisible;
    const toggle = $('#toggleLibrary');
    toggle?.setAttribute('aria-expanded', String(state.libraryVisible));
    toggle?.classList.toggle('active', state.libraryVisible);
    if (refs.libraryResizer) refs.libraryResizer.tabIndex = state.libraryVisible ? 0 : -1;
    if (!state.libraryVisible && refs.libraryPanel?.contains(document.activeElement)) toggle?.focus();
    applySidebarWidths();
    if (layoutChanged) scheduleSidebarRedraw();
  }

  function setInspectorVisible(visible) {
    const nextVisible = Boolean(visible);
    const layoutChanged = state.inspectorVisible !== nextVisible || document.body.classList.contains('inspector-open') !== nextVisible;
    state.inspectorVisible = nextVisible;
    document.body.classList.toggle('inspector-open', state.inspectorVisible);
    document.body.classList.toggle('inspector-hidden', !state.inspectorVisible);
    const panel = refs.inspectorPanel;
    const toggle = $('#toggleInspector');
    panel?.setAttribute('aria-hidden', String(!state.inspectorVisible));
    if (panel) panel.inert = !state.inspectorVisible;
    toggle?.setAttribute('aria-expanded', String(state.inspectorVisible));
    toggle?.classList.toggle('active', state.inspectorVisible);
    if (refs.inspectorResizer) refs.inspectorResizer.tabIndex = state.inspectorVisible ? 0 : -1;
    if (!state.inspectorVisible && panel?.contains(document.activeElement)) toggle?.focus();
    applySidebarWidths();
    if (layoutChanged) scheduleSidebarRedraw();
  }

  function sidebarMaximum(side) {
    if (window.innerWidth <= 800) return SIDEBAR_LIMITS[side].max;
    const otherSide = side === 'library' ? 'inspector' : 'library';
    const otherVisible = otherSide === 'library' ? state.libraryVisible : state.inspectorVisible;
    const otherWidth = otherVisible ? currentSidebarWidth(otherSide) : 0;
    const canvasMinimum = window.innerWidth <= 1050 ? 300 : 420;
    const handleWidth = (state.libraryVisible ? 6 : 0) + (state.inspectorVisible ? 6 : 0);
    return Math.max(SIDEBAR_LIMITS[side].min, Math.min(SIDEBAR_LIMITS[side].max, window.innerWidth - canvasMinimum - handleWidth - otherWidth));
  }

  function setSidebarWidth(side, width, persist = false) {
    const widthKey = side === 'library' ? 'libraryWidth' : 'inspectorWidth';
    state[widthKey] = Math.min(sidebarMaximum(side), clampSidebarWidth(width, side));
    const applied = applySidebarWidths();
    state[widthKey] = applied[side];
    if (persist) persistSidebarLayout();
  }

  function bindSidebarResizer(resizer, side) {
    if (!resizer) return;
    const widthKey = side === 'library' ? 'libraryWidth' : 'inspectorWidth';
    const direction = side === 'library' ? 1 : -1;
    resizer.addEventListener('pointerdown', event => {
      if (event.button !== 0) return;
      event.preventDefault();
      state.libraryWidth = currentSidebarWidth('library');
      state.inspectorWidth = currentSidebarWidth('inspector');
      state.sidebarResize = { side, widthKey, direction, pointerId:event.pointerId, startX:event.clientX, startWidth:state[widthKey], element:resizer };
      resizer.classList.add('active');
      document.body.classList.add('sidebar-resizing');
      resizer.setPointerCapture(event.pointerId);
    });
    const updateResize = event => {
      const resize = state.sidebarResize;
      if (!resize || resize.pointerId !== event.pointerId || resize.side !== side) return;
      event.preventDefault();
      setSidebarWidth(side, resize.startWidth + (event.clientX - resize.startX) * resize.direction);
    };
    const finishResize = event => {
      const resize = state.sidebarResize;
      if (!resize || resize.side !== side || (event.pointerId != null && resize.pointerId !== event.pointerId)) return;
      state.sidebarResize = null;
      resizer.classList.remove('active');
      document.body.classList.remove('sidebar-resizing');
      try { if (resizer.hasPointerCapture(resize.pointerId)) resizer.releasePointerCapture(resize.pointerId); } catch { /* capture may already be gone */ }
      persistSidebarLayout();
      scheduleSidebarRedraw();
    };
    document.addEventListener('pointermove', updateResize, { passive:false });
    document.addEventListener('pointerup', finishResize);
    document.addEventListener('pointercancel', finishResize);
    resizer.addEventListener('lostpointercapture', finishResize);
    window.addEventListener('blur', finishResize);
    resizer.addEventListener('keydown', event => {
      let nextWidth = currentSidebarWidth(side);
      const step = event.shiftKey ? 30 : 10;
      if (event.key === 'Home') nextWidth = SIDEBAR_LIMITS[side].min;
      else if (event.key === 'End') nextWidth = sidebarMaximum(side);
      else if (event.key === 'ArrowLeft') nextWidth += side === 'library' ? -step : step;
      else if (event.key === 'ArrowRight') nextWidth += side === 'library' ? step : -step;
      else return;
      event.preventDefault();
      setSidebarWidth(side, nextWidth, true);
      scheduleSidebarRedraw();
    });
  }

  function handleViewportResize() {
    const nextLibraryDrawerMode = window.matchMedia('(max-width:650px)').matches;
    const nextInspectorDrawerMode = window.matchMedia('(max-width:800px)').matches;
    if (nextLibraryDrawerMode !== libraryDrawerMode) {
      libraryDrawerMode = nextLibraryDrawerMode;
      setLibraryVisible(!libraryDrawerMode);
    }
    if (nextInspectorDrawerMode !== inspectorDrawerMode) {
      inspectorDrawerMode = nextInspectorDrawerMode;
      setInspectorVisible(!inspectorDrawerMode);
    }
    applySidebarWidths();
    drawMinimap();
  }

  function selectNode(id, { revealInspector = true } = {}) {
    state.selectedNode = id;
    state.selectedEdge = null;
    if (revealInspector) setInspectorVisible(true);
  }
  function renderSelection() {
    $$('.node', refs.nodes).forEach(element => element.classList.toggle('selected', element.dataset.nodeId === state.selectedNode));
  }

  function flushActiveInspectorField() {
    const active = document.activeElement;
    if (!active || !refs.inspector.contains(active) || !active.matches('input[data-field],select[data-field]')) return;
    active.blur();
  }

  function resetGraphInteractions() {
    cancelPointerInteractions(true);
    cancelConnection();
  }

  function removeNode(id) {
    flushActiveInspectorField();
    resetGraphInteractions();
    state.workflow.nodes = state.workflow.nodes.filter(x => x.id !== id);
    state.workflow.edges = state.workflow.edges.filter(x => x.source !== id && x.target !== id);
    if (state.selectedNode === id) state.selectedNode = null;
    commit('删除节点'); renderGraph();
  }

  function removeSelected() {
    if (state.selectedNode) removeNode(state.selectedNode);
    else if (state.selectedEdge !== null) {
      flushActiveInspectorField();
      resetGraphInteractions();
      state.workflow.edges.splice(state.selectedEdge, 1); state.selectedEdge = null; commit('删除连接'); renderGraph();
    }
  }

  function renderInspector() {
    flushActiveInspectorField();
    const node = state.workflow.nodes.find(x => x.id === state.selectedNode);
    const edge = state.selectedEdge !== null ? state.workflow.edges[state.selectedEdge] : null;
    setInspectorVisible(state.inspectorVisible);
    if (!node) {
      const edgeValidation = edge ? state.validation.edgeErrors[edge.id] || [] : [];
      refs.inspector.innerHTML = edge
        ? `${edgeValidation.length ? `<div class="inspector-section validation-section"><h2>${escapeHtml(t('validation.connectionNeedsFix'))}</h2>${edgeValidation.map(error => `<div class="validation-item">${escapeHtml(friendlyValidationError(error))}</div>`).join('')}</div>` : ''}<div class="inspector-empty"><div>⌁</div><b>${escapeHtml(t('inspector.edge.title'))}</b><span>${escapeHtml(t('inspector.edge.description'))}</span><button class="danger-button" id="deleteEdge" style="width:150px">${escapeHtml(t('inspector.edge.delete'))}</button></div>`
        : `<div class="inspector-empty"><div>◇</div><b>${escapeHtml(t('inspector.empty.title'))}</b><span>${escapeHtml(t('inspector.empty.description'))}</span></div>`;
      $('#deleteEdge')?.addEventListener('click', removeSelected);
      return;
    }
    const c = node.data.config || (node.data.config = {});
    const nodeValidation = state.validation.nodeErrors[node.id] || [];
    let fields = '';
    if (node.type === 'input_file') fields = pathField('path',t('inspector.field.audioFilePath'),c.path,t('inspector.field.audioFilePath.example'),'audio_file');
    if (node.type === 'input_folder') fields = pathField('path',t('inspector.field.inputFolder'),c.path,t('inspector.field.inputFolder.example'),'input_directory') + field('include',t('inspector.field.fileFilter'),c.include,t('inspector.field.fileFilter.help'),'text') + selectField('recursive',t('inspector.field.recursive'),String(c.recursive),[['true',t('inspector.option.yes')],['false',t('inspector.option.no')]]);
    if (node.type === 'output_folder') fields = pathField('path',t('inspector.field.outputFolder'),c.path,t('inspector.field.outputFolder.example'),'output_directory') + field('naming',t('inspector.field.namingTemplate'),c.naming,t('inspector.field.namingTemplate.help'),'text') + `<div class="field-inline">${selectField('format',t('inspector.field.outputFormat'),c.format,[['wav','WAV'],['flac','FLAC'],['mp3','MP3']])}${selectField('conflict',t('inspector.field.conflict'),c.conflict,[['rename',t('inspector.option.rename')],['overwrite',t('inspector.option.overwrite')],['skip',t('inspector.option.skip')]])}</div>`;
    if (node.type === 'separator') fields = selectField('output_format',t('inspector.field.intermediateFormat'),c.output_format,[['wav','WAV'],['flac','FLAC']]) + field('normalization_threshold',t('inspector.field.peakLimit'),c.normalization_threshold ?? 0.9,t('inspector.field.peakLimit.help'),'number');
    if (node.type === 'slicer') fields = selectField('output_format',t('inspector.field.intermediateFormat'),c.output_format,[['wav','WAV'],['flac','FLAC'],['mp3','MP3']]) + field('threshold',t('inspector.field.silenceThreshold'),c.threshold ?? -40,t('inspector.field.silenceThreshold.help'),'number') + field('min_length',t('inspector.field.minLength'),c.min_length ?? 5000,t('inspector.field.milliseconds'),'number') + field('min_interval',t('inspector.field.minInterval'),c.min_interval ?? 300,t('inspector.field.milliseconds'),'number') + field('hop_size',t('inspector.field.hopSize'),c.hop_size ?? 10,t('inspector.field.milliseconds'),'number') + field('max_sil_kept',t('inspector.field.maxSilenceKept'),c.max_sil_kept ?? 1000,t('inspector.field.milliseconds'),'number');
    if (node.type === 'peak_normalize') fields = field('target_peak_db',t('inspector.field.targetPeak'),c.target_peak_db ?? -3,t('inspector.field.targetPeak.help'),'number');
    const model = node.type === 'separator' ? `<div class="inspector-section"><h2>${escapeHtml(t('inspector.section.model'))}</h2><div class="model-summary"><span class="template-icon" style="--item-color:${palette.separator}">⌁</span><div><b>${escapeHtml(nodeTitle(node))}</b><span>${escapeHtml(node.data.architecture)} · ${escapeHtml(functionLabel(node.data.function))}</span></div></div><div class="tag-list">${getOutputs(node).map(x => `<span class="tag">${escapeHtml(x.label)}</span>`).join('')}</div></div>` : '';
    const validationBlock = nodeValidation.length ? `<div class="inspector-section validation-section"><h2>${escapeHtml(t('validation.needsFix'))}</h2>${nodeValidation.map(error => `<div class="validation-item">${escapeHtml(friendlyValidationError(error))}</div>`).join('')}</div>` : '';
    refs.inspector.innerHTML = `${validationBlock}<div class="inspector-section"><h2>${escapeHtml(t('inspector.section.node'))}</h2>${field('__title',t('inspector.field.displayName'),nodeTitle(node),'','text')}<div class="field-inline">${field('__x',t('inspector.field.x'),node.data.x,'','number')}${field('__y',t('inspector.field.y'),node.data.y,'','number')}</div></div>${model}<div class="inspector-section"><h2>${escapeHtml(t('inspector.section.parameters'))}</h2>${fields || `<div class="field"><small>${escapeHtml(t('inspector.noEditableParameters'))}</small></div>`}</div><div class="inspector-section"><button class="danger-button" id="deleteNode">${escapeHtml(t('inspector.action.deleteNode'))}</button></div>`;
    $$('input[data-field],select[data-field]', refs.inspector).forEach(input => bindInspectorField(input, node));
    $$('.path-picker', refs.inspector).forEach(button => button.addEventListener('click', () => pickPath(button, node)));
    $('#deleteNode').addEventListener('click', () => removeNode(node.id));
  }

  function field(key, label, value, help = '', type = 'text') {
    return `<label class="field"><span>${label}</span><input data-field="${key}" type="${type}" value="${escapeHtml(value)}">${help ? `<small>${help}</small>` : ''}</label>`;
  }
  function pathField(key, label, value, help, kind) {
    const status = t(value ? 'path.status.set' : 'path.status.empty');
    return `<label class="field path-field"><span>${label}</span><span class="path-field-row"><input data-field="${key}" type="text" value="${escapeHtml(value)}"><button type="button" class="path-picker" data-kind="${kind}" data-field="${key}">${escapeHtml(t('path.browse'))}</button></span><small class="field-status ${value ? 'valid' : ''}">${escapeHtml(status)}</small>${help ? `<small>${help}</small>` : ''}</label>`;
  }
  function selectField(key, label, value, options) {
    return `<label class="field"><span>${label}</span><select data-field="${key}">${options.map(([v,l]) => `<option value="${v}" ${String(value) === v ? 'selected' : ''}>${l}</option>`).join('')}</select></label>`;
  }
  function bindInspectorField(input, node) {
    input.dataset.initialValue = input.value;
    if (input.tagName === 'SELECT') {
      input.addEventListener('change', () => updateNodeField(node, input.dataset.field, input.value, input));
      return;
    }
    input.addEventListener('keydown', event => {
      if (event.key === 'Enter') { event.preventDefault(); input.blur(); }
      if (event.key === 'Escape') { input.value = input.dataset.initialValue; input.blur(); }
    });
    input.addEventListener('blur', () => {
      if (input.value !== input.dataset.initialValue) updateNodeField(node, input.dataset.field, input.value, input);
    });
  }

  function updateNodeField(node, key, value, input = null) {
    const numericValue = String(value).trim() === '' ? NaN : Number(value);
    if (key === '__title') {
      node.data.title = value.trim();
      node.data.title_customized = Boolean(node.data.title);
    }
    else if (key === '__x' || key === '__y') node.data[key.slice(2)] = Number(value) || 0;
    else if (key === 'normalization_threshold') node.data.config[key] = Math.min(1, Math.max(0.01, Number(value) || 0.9));
    else if (key === 'threshold') node.data.config[key] = Math.min(0, Math.max(-120, Number.isFinite(numericValue) ? numericValue : -40));
    else if (['min_length','min_interval','hop_size','max_sil_kept'].includes(key)) node.data.config[key] = Math.max(1, Math.round(Number.isFinite(numericValue) ? numericValue : 1));
    else if (key === 'target_peak_db') node.data.config[key] = Math.min(0, Math.max(-60, Number.isFinite(numericValue) ? numericValue : -3));
    else if (key === 'path') node.data.config[key] = String(value ?? '').trim();
    else node.data.config[key] = value === 'true' ? true : value === 'false' ? false : value;
    if (input) {
      const displayed = key === '__title' ? nodeTitle(node) : key === '__x' || key === '__y' ? node.data[key.slice(2)] : node.data.config[key];
      input.value = String(displayed);
      input.dataset.initialValue = input.value;
      if (key === 'path') {
        const path = node.data.config.path;
        setPathStatus(input.closest('.path-field'), t(path ? 'path.status.manualSaved' : 'path.status.required'), path ? 'valid' : 'error');
      }
    }
    commit('修改节点参数');
    refreshNodePresentation(node);
  }

  function refreshNodePresentation(node) {
    const element = $(`.node[data-node-id="${CSS.escape(node.id)}"]`, refs.nodes);
    if (!element) return;
    element.style.left = `${node.data.x}px`;
    element.style.top = `${node.data.y}px`;
    $('.node-title b', element).textContent = nodeTitle(node);
    const summary = $('.node-info-row strong', element);
    if (summary && node.type === 'input_file') summary.textContent = t(node.data.config.path ? 'node.info.selected' : 'node.info.notSelected');
    if (summary && node.type === 'input_folder') summary.textContent = t(node.data.config.recursive ? 'node.info.includeSubfolders' : 'node.info.currentFolder');
    if (summary && node.type === 'slicer') summary.textContent = String(node.data.config.output_format || 'wav').toUpperCase();
    if (summary && node.type === 'peak_normalize') summary.textContent = `${node.data.config.target_peak_db ?? -3} dB`;
    if (summary && node.type === 'output_folder') summary.textContent = String(node.data.config.format || 'wav').toUpperCase();
    renderEdges(); drawMinimap();
  }

  function setPathStatus(field, message, type = '') {
    const status = $('.field-status', field);
    if (!status) return;
    status.textContent = message;
    status.className = `field-status ${type}`;
  }

  async function pickPath(button, node) {
    const workflowAtRequest = state.workflow;
    const nodeAtRequest = node;
    const requestIsCurrent = () => state.workflow === workflowAtRequest && state.workflow.nodes.includes(nodeAtRequest);
    const key = button.dataset.field;
    const field = button.closest('.path-field');
    const input = $(`input[data-field="${CSS.escape(key)}"]`, field);
    button.disabled = true;
    button.classList.add('loading');
    setPathStatus(field, t('path.status.opening'));
    try {
      const result = await api('/api/dialog/pick', { method:'POST', body:JSON.stringify({ kind:button.dataset.kind, initial_path:input.value.trim() || null, locale:i18n.getLocale() }) });
      if (!requestIsCurrent()) return;
      if (result.cancelled || !result.path) { setPathStatus(field, t(input.value ? 'path.status.cancelledKept' : 'path.status.cancelled')); return; }
      input.value = result.path;
      updateNodeField(node, key, result.path, input);
      setPathStatus(field, t('path.status.picked'), 'valid');
      toast(t('path.filled'), 'success');
    } catch (error) {
      if (!requestIsCurrent()) return;
      const keyByCode = {
        dialog_busy:'path.dialogBusy', unsupported_audio_file:'path.unsupportedAudio', loopback_required:'path.localOnly'
      };
      const message = keyByCode[error.code] ? t(keyByCode[error.code]) : error.message;
      setPathStatus(field, t('path.pickFailed', { error:message }), 'error');
      toast(t('path.unavailable', { error:message }), 'error');
    } finally {
      button.disabled = false;
      button.classList.remove('loading');
    }
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
    state.workflow.edges.forEach(edge => { edge.id ||= uid('edge'); });
    const nodes = state.workflow.nodes.map(original => {
      const node = deepClone(original), config = node.data.config || {};
      const hasConfiguredPath = Object.prototype.hasOwnProperty.call(config, 'path');
      const path = String(hasConfiguredPath ? config.path ?? '' : node.data.path ?? '').trim();
      if (node.type === 'input_file') node.data.path = path;
      if (node.type === 'input_folder') {
        node.data.path = path;
        node.data.recursive = config.recursive ?? node.data.recursive ?? true;
        const include = config.include || '';
        node.data.extensions = include.split(/[;,\s]+/).filter(Boolean).map(ext => ext.replace(/^\*?/, '')).filter(ext => /^\.[a-z0-9]+$/i.test(ext));
      }
      if (node.type === 'separator') {
        node.data.outputs = getOutputs(node).map(port => port.id);
        node.data.options = { ...(node.data.options || {}), ...config };
      }
      if (node.type === 'slicer') {
        node.data.threshold = Number(config.threshold ?? -40);
        node.data.min_length = Number(config.min_length ?? 5000);
        node.data.min_interval = Number(config.min_interval ?? 300);
        node.data.hop_size = Number(config.hop_size ?? 10);
        node.data.max_sil_kept = Number(config.max_sil_kept ?? 1000);
        node.data.output_format = config.output_format || 'wav';
      }
      if (node.type === 'peak_normalize') node.data.target_peak_db = Number(config.target_peak_db ?? -3);
      if (node.type === 'output_folder') {
        node.data.path = path;
        node.data.naming_template = config.naming || node.data.naming_template || '{relative_dir}/{basename}_{stem}.{ext}';
        node.data.conflict = config.conflict || node.data.conflict || 'rename';
        node.data.format = config.format || node.data.format || 'wav';
      }
      delete node.data.config;
      return node;
    });
    return {
      id:state.workflow.id,
      name:state.workflow.name,
      version:1,
      revision:Number(state.workflow.revision || 0),
      nodes,
      edges:deepClone(state.workflow.edges)
    };
  }

  function setDirty(value) {
    state.dirty = Boolean(value);
    const editor = state.editors.get(state.activeWorkflowId);
    if (editor) editor.dirty = state.dirty;
    const dot = $('.save-dot');
    dot.style.background = state.dirty ? '#f2ad5f' : 'var(--green)';
    dot.title = t(state.dirty ? 'workflow.status.dirty' : 'workflow.status.saved');
    renderWorkflowTabs();
  }

  function persistAutosave(payload = workflowPayload()) {
    const editor = state.editors.get(state.activeWorkflowId);
    if (!editor) return;
    editor.workflow = state.workflow;
    editor.history = state.history;
    editor.historyIndex = state.historyIndex;
    editor.dirty = state.dirty;
    if (!state.dirty && editor.persisted) removeDraft(payload.id);
    else writeDraft({ workflow:payload, dirty:state.dirty, persisted:editor.persisted, updatedAt:Date.now() });
    persistTabState();
  }

  function commit(reason) {
    clearValidation();
    const snapshot=JSON.stringify(state.workflow);
    if (state.history[state.historyIndex]===snapshot) return;
    setDirty(true);
    state.history=state.history.slice(0,state.historyIndex+1);state.history.push(snapshot);if(state.history.length>60)state.history.shift();state.historyIndex=state.history.length-1;
    persistAutosave();
  }
  function restoreHistory(index) {
    const previousIndex = state.historyIndex;
    const delta = index - previousIndex;
    flushActiveInspectorField();
    const targetIndex = state.historyIndex === previousIndex ? index : state.historyIndex + delta;
    if (targetIndex < 0 || targetIndex >= state.history.length) return;
    resetGraphInteractions();
    state.historyIndex=targetIndex;state.workflow=JSON.parse(state.history[targetIndex]);state.selectedNode=null;state.selectedEdge=null;clearValidation();renderGraph();
    setDirty(true);persistAutosave();
  }

  async function persistWorkflow(asCopy = false) {
    if (state.workflowSavePending) return;
    flushActiveInspectorField();
    const currentName = refs.workflowName.value.trim() || t('workflow.untitled');
    let name = currentName;
    if (asCopy) {
      name = window.prompt(t('workflow.saveAs.prompt'), `${currentName} ${t('workflow.saveAs.copySuffix')}`)?.trim();
      if (!name) return;
    }
    const payload = workflowPayload();
    payload.name = name;
    if (asCopy) { payload.id = uid('workflow');payload.revision = 0; }
    const exists = !asCopy && payload.revision > 0;
    const path = exists ? `/api/workflows/${encodeURIComponent(payload.id)}` : '/api/workflows';
    const method = exists ? 'PUT' : 'POST';
    state.workflowSavePending = true;
    $('#saveWorkflow').disabled = true;
    $('#saveAsWorkflow').disabled = true;
    try {
      const saved = await api(path, { method, body:JSON.stringify(payload) });
      const previousId = state.activeWorkflowId;
      state.workflow.id = saved.id;
      state.workflow.name = saved.name;
      state.workflow.revision = saved.revision;
      state.workflow.updated_at = saved.updated_at;
      if (previousId !== saved.id) {
        const editor = state.editors.get(previousId);
        state.editors.delete(previousId);
        state.openWorkflowIds = state.openWorkflowIds.map(id => id === previousId ? saved.id : id);
        state.activeWorkflowId = saved.id;
        if (editor) state.editors.set(saved.id, editor);
        removeDraft(previousId);
      }
      refs.workflowName.value = saved.name;
      refs.canvasTitle.textContent = saved.name;
      const editor = state.editors.get(saved.id);
      if (editor) { editor.workflow = state.workflow;editor.persisted = true; }
      state.history = [JSON.stringify(state.workflow)];
      state.historyIndex = 0;
      setDirty(false);
      persistAutosave(workflowPayload());
      log(t('workflow.message.savedServer'), 'success');
      toast(t(asCopy ? 'workflow.message.savedAs' : 'workflow.message.savedServer'), 'success');
      await fetchWorkflows({ quiet:true });
    } catch (error) {
      persistAutosave();
      const key = error.status === 409 ? 'workflow.message.saveConflict' : 'workflow.message.saveFailed';
      toast(t(key, { error:error.message }), 'error');
      log(t(key, { error:error.message }), 'error');
    } finally {
      state.workflowSavePending = false;
      $('#saveWorkflow').disabled = false;
      $('#saveAsWorkflow').disabled = false;
    }
  }

  async function saveWorkflow() { await persistWorkflow(false); }
  async function saveWorkflowAs() { await persistWorkflow(true); }

  function exportWorkflow() {
    flushActiveInspectorField();
    state.workflow.name = refs.workflowName.value.trim() || t('workflow.untitled');
    const payload = workflowPayload();
    const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;a.download=`${payload.name.replace(/[\\/:*?"<>|]/g,'_')}.audioflow.json`;a.click();URL.revokeObjectURL(url);
    toast(t('workflow.message.exported'),'success');
  }

  function loadWorkflowData(source, { dirty = true, notify = true, activate = true } = {}) {
    const payload = deepClone(source);
    if(!payload||!Array.isArray(payload.nodes)||!Array.isArray(payload.edges))throw new Error(t('workflow.message.invalid'));
    payload.nodes.forEach((node,i)=>{
      node.data=node.data||{};node.data.x=Number(node.data.x ?? node.position?.x ?? 80+i*260);node.data.y=Number(node.data.y ?? node.position?.y ?? 100);
      if (node.data.title_customized === undefined) node.data.title_customized = node.type === 'separator' || Boolean(node.data.title && !isLocalizedDefaultTitle(node));
      if (!node.data.title_customized && node.type !== 'separator') node.data.title = '';
      if (node.type === 'separator') node.data.outputs = normalizeOutputs(node.data);
      if (node.type === 'input_file') node.data.outputs = normalizeOutputs({outputs:node.data.outputs || [{id:'audio',label:'audio'}]});
      if (node.type === 'input_folder') node.data.outputs = normalizeOutputs({outputs:node.data.outputs || [{id:'audio',label:'audio'}]});
      if (node.type === 'slicer' || node.type === 'peak_normalize') { node.data.inputs = node.data.inputs || [{id:'audio',label:'audio'}]; node.data.outputs = node.data.outputs || [{id:'audio',label:'audio'}]; }
      if (node.type === 'output_folder') node.data.inputs = node.data.inputs || [{id:'audio',label:'audio'}];
      node.data.config=node.data.config||{};
      if (node.type === 'input_file') node.data.config.path = String(node.data.config.path ?? node.data.path ?? '').trim();
      if (node.type === 'input_folder') { node.data.config.path = String(node.data.config.path ?? node.data.path ?? '').trim(); node.data.config.recursive ??= node.data.recursive ?? true; node.data.config.include ??= (node.data.extensions || []).map(ext=>`*${ext}`).join(';'); }
      if (node.type === 'separator') node.data.config = {...(node.data.options || {}),...node.data.config};
      if (node.type === 'slicer') node.data.config = {threshold:node.data.threshold ?? -40,min_length:node.data.min_length ?? 5000,min_interval:node.data.min_interval ?? 300,hop_size:node.data.hop_size ?? 10,max_sil_kept:node.data.max_sil_kept ?? 1000,output_format:node.data.output_format || 'wav',...node.data.config};
      if (node.type === 'peak_normalize') node.data.config = {target_peak_db:node.data.target_peak_db ?? -3,...node.data.config};
      if (node.type === 'output_folder') { node.data.config = {path:node.data.path || '',naming:node.data.naming_template || '{basename}_{stem}.{ext}',format:node.data.format || 'wav',conflict:node.data.conflict || 'rename',...node.data.config}; node.data.config.path = String(node.data.config.path ?? '').trim(); }
    });
    payload.edges.forEach(edge => { edge.id ||= uid('edge'); });
    let id = payload.id || uid('workflow');
    const idChanged = state.editors.has(id);
    if (idChanged) id = uid('workflow');
    const workflow={
      id,
      name:payload.name||t('workflow.loadedName'),
      version:Number(payload.version || 1),
      revision:idChanged ? 0 : Number(payload.revision || 0),
      updated_at:payload.updated_at,
      nodes:payload.nodes,
      edges:payload.edges
    };
    registerEditor(workflow, { dirty, persisted:workflow.revision > 0 });
    if (activate) {
      activateWorkflowEditor(workflow.id, { fit:true });
      persistAutosave();
    }
    if (notify) toast(t('workflow.message.loaded'),'success');
    return workflow.id;
  }

  function createNewWorkflow() {
    flushActiveInspectorField();
    const workflow={id:uid('workflow'),name:t('workflow.untitled'),version:1,revision:0,nodes:[],edges:[]};
    registerEditor(workflow, { dirty:true, persisted:false });
    activateWorkflowEditor(workflow.id);
    persistAutosave();
  }

  function renderWorkflowList() {
    if (!state.workflows.length) {
      refs.workflowList.innerHTML = `<div class="manager-empty">${escapeHtml(t('workflow.manager.empty'))}</div>`;
      return;
    }
    refs.workflowList.innerHTML = state.workflows.map(item => {
      const current = item.id === state.workflow.id;
      return `<article class="manager-row ${current ? 'current' : ''}">
        <div class="manager-row-main"><div class="manager-row-title"><strong title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</strong>${current ? `<span class="manager-chip current">${escapeHtml(t('workflow.manager.current'))}</span>` : ''}</div><div class="manager-row-meta"><span>${escapeHtml(formatDateTime(item.updated_at))}</span><span>${escapeHtml(item.id)}</span></div></div>
        <div class="manager-row-actions"><button class="text-button" data-open-workflow="${escapeHtml(item.id)}">${escapeHtml(t('workflow.manager.open'))}</button><button class="icon-button" data-delete-workflow="${escapeHtml(item.id)}" title="${escapeHtml(t('workflow.manager.delete'))}">×</button></div>
      </article>`;
    }).join('');
    $$('[data-open-workflow]', refs.workflowList).forEach(button => button.addEventListener('click', () => openServerWorkflow(button.dataset.openWorkflow)));
    $$('[data-delete-workflow]', refs.workflowList).forEach(button => button.addEventListener('click', () => deleteServerWorkflow(button.dataset.deleteWorkflow)));
  }

  async function fetchWorkflows({ quiet = false } = {}) {
    if (!quiet) refs.workflowList.innerHTML = `<div class="manager-loading">${escapeHtml(t('manager.loading'))}</div>`;
    try {
      const result = await api('/api/workflows');
      state.workflows = Array.isArray(result.workflows) ? result.workflows : [];
      renderWorkflowList();
      renderWorkflowTabs();
      return state.workflows;
    } catch (error) {
      if (!quiet) refs.workflowList.innerHTML = `<div class="manager-empty">${escapeHtml(t('workflow.message.listFailed', { error:error.message }))}</div>`;
      return [];
    }
  }

  async function openServerWorkflow(id) {
    if (state.editors.has(id)) {
      activateWorkflowEditor(id);
      closeManager('workflowManager');
      return;
    }
    try {
      const workflow = await api(`/api/workflows/${encodeURIComponent(id)}`);
      loadWorkflowData(workflow, { dirty:false });
      closeManager('workflowManager');
    } catch (error) { toast(t('workflow.message.openFailed', { error:error.message }), 'error'); }
  }

  async function deleteServerWorkflow(id) {
    const item = state.workflows.find(workflow => workflow.id === id);
    if (!confirm(t('workflow.confirm.delete', { name:item?.name || id }))) return;
    try {
      await api(`/api/workflows/${encodeURIComponent(id)}`, { method:'DELETE' });
      state.workflows = state.workflows.filter(workflow => workflow.id !== id);
      const editor = state.editors.get(id);
      if (editor) {
        editor.persisted = false;
        editor.dirty = true;
        editor.workflow.revision = 0;
        if (state.activeWorkflowId === id) {
          state.workflow.revision = 0;
          setDirty(true);
          persistAutosave();
        } else {
          writeDraft({workflow:deepClone(editor.workflow),dirty:true,persisted:false,updatedAt:Date.now()});
        }
      }
      renderWorkflowList();
      renderWorkflowTabs();
      toast(t('workflow.message.deleted'), 'success');
    } catch (error) { toast(t('workflow.message.deleteFailed', { error:error.message }), 'error'); }
  }

  function friendlyValidationError(message) {
    const text = String(message || t('validation.invalid'));
    if (/Input file node .* is missing path/i.test(text)) return t('validation.inputFileMissingPath');
    if (/Input folder node .* is missing path/i.test(text)) return t('validation.inputFolderMissingPath');
    if (/Output node .* is missing path/i.test(text)) return t('validation.outputMissingPath');
    if (/Input audio file does not exist/i.test(text)) return t('validation.inputFileNotFound');
    if (/Input audio path is not a file/i.test(text)) return t('validation.inputPathNotFile');
    if (/Unsupported input audio extension/i.test(text)) return t('validation.inputExtensionUnsupported');
    if (/Input folder does not exist/i.test(text)) return t('validation.inputFolderNotFound');
    if (/Input folder path is not a directory/i.test(text)) return t('validation.inputPathNotFolder');
    if (/Output path is not a directory/i.test(text)) return t('validation.outputPathNotFolder');
    if (/Separator node .* has no audio input/i.test(text)) return t('validation.separatorMissingInput');
    if (/Slicer node .* has no audio input/i.test(text)) return t('validation.slicerMissingInput');
    if (/Peak normalize node .* has no audio input/i.test(text)) return t('validation.peakNormalizeMissingInput');
    if (/Slicer node .* (?:has invalid|requires|threshold|uses an unsupported)/i.test(text)) return t('validation.slicerSettingsInvalid');
    if (/Peak normalize node .* (?:has an invalid|target peak)/i.test(text)) return t('validation.peakNormalizeTargetInvalid');
    if (/Output node .* has no audio input/i.test(text)) return t('validation.outputMissingInput');
    if (/Workflow needs at least one input node/i.test(text)) return t('validation.workflowMissingInput');
    if (/Workflow needs at least one output node/i.test(text)) return t('validation.workflowMissingOutput');
    if (/unknown model/i.test(text)) return t('validation.unknownModel');
    if (/not installed/i.test(text)) return t('validation.modelNotInstalled');
    if (/output stems are unknown/i.test(text)) return t('validation.modelOutputsUnknown');
    if (/has no (?:input|output) port|has no output stem/i.test(text)) return t('validation.invalidPort');
    if (/cycle/i.test(text)) return t('validation.cycle');
    return text.replace(/node_[a-z0-9_]+/gi, t('validation.thisNode')).replace(/edge_[a-z0-9_]+/gi, t('validation.thisConnection'));
  }

  function clearValidation() {
    const hadErrors = state.validation.errors.length || Object.keys(state.validation.nodeErrors).length || Object.keys(state.validation.edgeErrors).length;
    state.validation = { nodeErrors:{}, edgeErrors:{}, globalErrors:[], errors:[] };
    $('.validation-banner', refs.viewport)?.remove();
    if (!hadErrors) return;
    $$('.node.validation-error', refs.nodes).forEach(node => { node.classList.remove('validation-error'); node.removeAttribute('title'); $('.node-error-mark', node)?.remove(); });
    $('.validation-section', refs.inspector)?.remove();
    renderEdges();
  }

  function applyValidation(result) {
    const errors = Array.isArray(result.errors) && result.errors.length ? result.errors : [t('validation.invalidCheck')];
    const nodeErrors = { ...(result.node_errors || {}) };
    const edgeErrors = { ...(result.edge_errors || {}) };
    if (!Object.keys(nodeErrors).length) {
      errors.forEach(error => {
        state.workflow.nodes.forEach(node => { if (String(error).includes(node.id)) (nodeErrors[node.id] ||= []).push(error); });
      });
    }
    if (!Object.keys(edgeErrors).length) errors.forEach(error => {
      state.workflow.edges.forEach(edge => { if (edge.id && String(error).includes(edge.id)) (edgeErrors[edge.id] ||= []).push(error); });
    });
    state.validation = { nodeErrors, edgeErrors, globalErrors:result.global_errors || [], errors };
    renderGraph();
    showValidationSummary(errors);
  }

  function showValidationSummary(errors) {
    $('.validation-banner', refs.viewport)?.remove();
    const banner = document.createElement('div');
    banner.className = 'validation-banner';
    const friendly = errors.map(friendlyValidationError);
    banner.innerHTML = `<div><b>${escapeHtml(t('validation.workflowNeedsFix'))}</b><span>${friendly.slice(0,3).map(escapeHtml).join(' · ')}${friendly.length > 3 ? ` · ${escapeHtml(plural('validation.more', friendly.length - 3))}` : ''}</span></div><button title="${escapeHtml(t('validation.close'))}">×</button>`;
    banner.querySelector('button').addEventListener('click', () => banner.remove());
    refs.viewport.append(banner);
    friendly.forEach(error => log(t('validation.log', { error }), 'error'));
    toast(plural('validation.issueCount', errors.length), 'error');
  }

  async function validateBeforeRun(payload, workflowId) {
    const result = await api('/api/workflows/validate', { method:'POST', body:JSON.stringify(payload) });
    if (!result.valid) {
      if (state.activeWorkflowId === workflowId) applyValidation(result);
      else toast(plural('validation.issueCount', Array.isArray(result.errors) ? result.errors.length : 1), 'error');
      return false;
    }
    if (state.activeWorkflowId === workflowId) clearValidation();
    return true;
  }

  async function runWorkflow() {
    const workflowId = state.activeWorkflowId;
    if(!workflowId||state.running||state.validatingWorkflowIds.has(workflowId))return;
    if(!state.workflow.nodes.length){toast(t('workflow.message.noNodes'),'error');return;}
    state.workflow.name=refs.workflowName.value.trim()||state.workflow.name;
    const payload = workflowPayload();
    state.validatingWorkflowIds.add(workflowId);renderRunControls();renderWorkflowTabs();
    try {
      log(t('validation.checking'));
      if (!await validateBeforeRun(payload, workflowId)) return;
      log(t('run.message.start', { name:payload.name }));
      const result=await api('/api/runs',{method:'POST',body:JSON.stringify({workflow:payload})});
      const runId=result.id||result.run_id||result.task_id;if(!runId)throw new Error(t('run.message.idMissing'));
      const run = {...result,id:runId,workflow_id:result.workflow_id||workflowId,workflow_name:result.workflow_name||payload.name,status:result.status||'queued'};
      upsertRun(run);
      if (state.activeWorkflowId === workflowId) attachRun(run);
      log(t('run.message.created', { id:runId }));
      renderRunList();renderWorkflowTabs();scheduleRunsRefresh();
    } catch(error){
      toast(t('validation.checkFailed', { error:error.message }), 'error');
      log(t('validation.checkFailed', { error:error.message }), 'error');
    } finally {
      state.validatingWorkflowIds.delete(workflowId);
      renderRunControls();renderWorkflowTabs();
    }
  }

  function renderRunControls() {
    const validating = state.validatingWorkflowIds.has(state.activeWorkflowId);
    const button = $('#runWorkflow');
    button.classList.toggle('running', state.running || validating);
    button.disabled = state.running || validating;
    const key = validating ? 'validation.checkingShort' : state.running ? 'workflow.action.running' : 'workflow.action.run';
    button.innerHTML = `<span>${state.running || validating ? '◌' : '▶'}</span> <span>${escapeHtml(t(key))}</span>`;
    const cancel = $('#cancelRun');
    cancel.classList.toggle('hidden', !state.running);
    cancel.disabled = state.cancelling;
    cancel.textContent = t(state.cancelling ? 'run.action.cancelling' : 'workflow.action.cancel');
  }

  function normalizeRunStatus(value) {
    const status = String(value || '').toLowerCase();
    if (['complete','success','done'].includes(status)) return 'completed';
    if (status === 'error') return 'failed';
    if (status === 'canceled') return 'cancelled';
    if (status === 'started') return 'running';
    return status;
  }

  function statusFromRunEvent(event, currentStatus = '') {
    const raw = String(event.status || event.type || '').toLowerCase();
    const normalized = normalizeRunStatus(raw);
    if (ACTIVE_RUN_STATUSES.has(normalized) || TERMINAL_RUN_STATUSES.has(normalized)) return normalized;
    if (['node_started','node_completed','file_started','file_completed','progress','log'].includes(raw)) {
      return normalizeRunStatus(currentStatus) === 'queued' ? 'running' : normalizeRunStatus(currentStatus);
    }
    return normalizeRunStatus(currentStatus);
  }

  function upsertRun(value) {
    const id = value?.id || value?.run_id;
    if (!id) return null;
    const index = state.runs.findIndex(run => run.id === id);
    const current = index >= 0 ? state.runs[index] : {};
    const next = {...current,...value,id};
    next.status = statusFromRunEvent(value, current.status || next.status) || 'queued';
    if (index >= 0) state.runs.splice(index, 1, next);
    else state.runs.unshift(next);
    return next;
  }

  function applyGlobalRunEvent(event) {
    const id = event?.run_id || event?.id;
    if (!id) return;
    const existing = state.runs.find(run => run.id === id);
    if (!existing) {
      const status = statusFromRunEvent(event);
      if (ACTIVE_RUN_STATUSES.has(status)) scheduleRunsRefresh(80);
      return;
    }
    const patch = {
      id,
      status:statusFromRunEvent(event, existing.status),
      message:event.message ?? existing.message,
      progress:event.progress ?? existing.progress,
      error:event.error ?? existing.error,
      outputs:event.outputs ?? existing.outputs
    };
    const run = upsertRun(patch);
    if (id === state.runId) handleRunEvent(event);
    renderRunList();renderWorkflowTabs();
    reconcileActiveWorkflowRun();
    if (run && (run.status === 'queued' || TERMINAL_RUN_STATUSES.has(run.status))) scheduleRunsRefresh();
  }

  function connectRunEvents() {
    if (typeof EventSource === 'undefined') return;
    if (state.eventSource) state.eventSource.close();
    const source = new EventSource('/api/events/runs');
    state.eventSource = source;
    source.onopen = () => fetchRuns({ quiet:true });
    source.onmessage = message => {
      try { applyGlobalRunEvent(JSON.parse(message.data)); }
      catch { log(message.data); }
    };
    // EventSource reconnects automatically and carries Last-Event-ID.
    source.onerror = () => scheduleRunsRefresh(500);
  }

  function scheduleRunsRefresh(delay = 250) {
    if (state.runRefreshTimer) return;
    state.runRefreshTimer = window.setTimeout(() => {
      state.runRefreshTimer = null;
      fetchRuns({ quiet:true });
    }, delay);
  }

  function localizedRunEvent(event, status) {
    if (status === 'started') return t('run.event.started');
    if (status === 'queued') return event.queue_position ? t('run.event.queuedPosition', { position:i18n.formatNumber(event.queue_position) }) : t('run.event.queued');
    if (status === 'cancelling') return t('run.event.cancelling');
    if (status === 'node_started') return t('run.event.nodeStarted', { node:nodeTitle(state.workflow.nodes.find(node => node.id === event.node_id) || { type:'separator', data:{ title:event.node_id || '' } }) });
    if (status === 'node_completed') return t('run.event.nodeCompleted', { node:nodeTitle(state.workflow.nodes.find(node => node.id === event.node_id) || { type:'separator', data:{ title:event.node_id || '' } }) });
    if (status === 'file_completed') return t('run.event.fileCompleted', { current:i18n.formatNumber(event.file_index || 0), total:i18n.formatNumber(event.file_count || 0) });
    return event.log || event.message || '';
  }

  function handleRunEvent(event) {
    const progress=Number(event.progress??event.percent);if(Number.isFinite(progress))refs.progressBar.style.width=`${progress<=1?progress*100:progress}%`;
    if(event.node_id){$$('.node.running').forEach(n=>n.classList.remove('running'));$(`.node[data-node-id="${CSS.escape(event.node_id)}"]`)?.classList.add('running');}
    const rawStatus=String(event.status||event.type||'').toLowerCase(), status=normalizeRunStatus(rawStatus);
    const lifecycleStatus = ['queued','running','cancelling'].includes(status) ? status : null;
    const statusChanged = lifecycleStatus && lifecycleStatus !== state.runStatus;
    if (lifecycleStatus) {
      state.runStatus = lifecycleStatus;
      state.cancelling = lifecycleStatus === 'cancelling';
      renderRunControls();
    }
    const terminal = TERMINAL_RUN_STATUSES.has(rawStatus);
    const message = localizedRunEvent(event, rawStatus);
    if (message && !terminal && (event.type || statusChanged)) log(message,event.level==='error'?'error':'');
    if(status==='completed')finishRun('success',t('run.message.completed'));
    if(status==='failed')finishRun('failed',event.error||event.message||t('run.message.failed'));
    if(status==='cancelled')finishRun('cancelled',t('run.message.cancelled'));
  }
  function finishRun(status,message) {
    state.running=false;state.cancelling=false;state.runStatus=status;renderRunControls();$$('.node.running').forEach(n=>n.classList.remove('running'));
    refs.activityState.className=`activity-state ${status==='success'?'success':status==='failed'?'error':''}`;refs.progressBar.style.width=status==='success'?'100%':'0';log(message,status==='success'?'success':status==='failed'?'error':'muted');toast(message,status==='success'?'success':status==='failed'?'error':'');state.runId=null;
    scheduleRunsRefresh();
  }

  function renderRunSummary() {
    const count = state.runs.filter(run => ACTIVE_RUN_STATUSES.has(normalizeRunStatus(run.status))).length;
    refs.activeRunCount.textContent = count > 99 ? '99+' : String(count);
    refs.activeRunCount.classList.toggle('hidden', count === 0);
  }

  function renderRunList() {
    renderRunSummary();
    if (!state.runs.length) {
      refs.runList.innerHTML = `<div class="manager-empty">${escapeHtml(t('run.manager.empty'))}</div>`;
      return;
    }
    refs.runList.innerHTML = state.runs.map(run => {
      const status = normalizeRunStatus(run.status) || 'queued';
      const active = ACTIVE_RUN_STATUSES.has(status);
      const current = run.id === state.runId;
      const progress = Math.max(0, Math.min(100, Number(run.progress || 0) * (Number(run.progress || 0) <= 1 ? 100 : 1)));
      const queue = status === 'queued' && run.queue_position ? t('run.manager.queuePosition', { position:i18n.formatNumber(run.queue_position) }) : '';
      const outputs = Array.isArray(run.outputs) && run.outputs.length ? plural('run.manager.outputs', run.outputs.length) : '';
      const details = run.error || run.message || '';
      return `<article class="manager-row ${current ? 'current' : ''}">
        <div class="manager-row-main"><div class="manager-row-title"><strong title="${escapeHtml(run.workflow_name || run.workflow_id)}">${escapeHtml(run.workflow_name || run.workflow_id)}</strong><span class="manager-chip ${escapeHtml(status)}">${escapeHtml(t(`run.status.${status}`))}</span></div><div class="manager-row-meta"><span>${escapeHtml(formatDateTime(run.created_at))}</span><span>${escapeHtml(queue || outputs || run.id.slice(0,12))}</span></div>${details ? `<div class="manager-row-message" title="${escapeHtml(details)}">${escapeHtml(details)}</div>` : ''}<div class="manager-progress"><span style="width:${progress}%"></span></div></div>
        <div class="manager-row-actions">${active ? `<button class="text-button" data-track-run="${escapeHtml(run.id)}" ${current ? 'disabled' : ''}>${escapeHtml(t(current ? 'run.manager.tracking' : 'run.manager.track'))}</button><button class="text-button" data-cancel-run="${escapeHtml(run.id)}" ${status === 'cancelling' ? 'disabled' : ''}>${escapeHtml(t(status === 'cancelling' ? 'run.action.cancelling' : 'workflow.action.cancel'))}</button>` : ''}</div>
      </article>`;
    }).join('');
    $$('[data-track-run]', refs.runList).forEach(button => button.addEventListener('click', () => trackRunById(button.dataset.trackRun)));
    $$('[data-cancel-run]', refs.runList).forEach(button => button.addEventListener('click', () => requestRunCancel(button.dataset.cancelRun)));
  }

  async function fetchRuns({ quiet = false } = {}) {
    if (!quiet) refs.runList.innerHTML = `<div class="manager-loading">${escapeHtml(t('manager.loading'))}</div>`;
    try {
      const result = await api('/api/runs');
      state.runs = Array.isArray(result.runs) ? result.runs : [];
      renderRunList();renderWorkflowTabs();reconcileActiveWorkflowRun();
      return state.runs;
    } catch (error) {
      if (!quiet) refs.runList.innerHTML = `<div class="manager-empty">${escapeHtml(t('run.message.listFailed', { error:error.message }))}</div>`;
      return [];
    }
  }

  function attachRun(run, recovered = false) {
    const status = normalizeRunStatus(run.status);
    if (!ACTIVE_RUN_STATUSES.has(status)) return;
    state.runId = run.id;state.running = true;state.runStatus = status;state.cancelling = status === 'cancelling';
    refs.activityState.className='activity-state running';refs.progress.classList.remove('hidden');
    const progress=Number(run.progress || 0);refs.progressBar.style.width=`${progress<=1?progress*100:progress}%`;
    renderRunControls();
    if (recovered) log(t('run.message.recovered', { name:run.workflow_name || run.workflow_id }), 'success');
  }

  function detachRun() {
    state.runId=null;state.running=false;state.cancelling=false;state.runStatus=null;
    refs.activityState.className='activity-state';refs.progress.classList.add('hidden');refs.progressBar.style.width='0';
    $$('.node.running').forEach(node => node.classList.remove('running'));
    renderRunControls();
  }

  function reconcileActiveWorkflowRun() {
    if (!state.activeWorkflowId) return;
    const tracked = state.runs.find(run => run.id === state.runId);
    if (tracked && tracked.workflow_id === state.activeWorkflowId && TERMINAL_RUN_STATUSES.has(normalizeRunStatus(tracked.status))) {
      handleRunEvent(tracked);
      return;
    }
    const active = state.runs.find(run => run.workflow_id === state.activeWorkflowId && ['running','cancelling'].includes(normalizeRunStatus(run.status)))
      || state.runs.find(run => run.workflow_id === state.activeWorkflowId && normalizeRunStatus(run.status) === 'queued');
    if (active) {
      if (active.id !== state.runId || !state.running) attachRun(active);
    } else if (state.runId || state.running) detachRun();
  }

  async function trackRunById(id) {
    try {
      const run = await api(`/api/runs/${encodeURIComponent(id)}`);
      if (state.editors.has(run.workflow_id)) activateWorkflowEditor(run.workflow_id);
      else if (run.workflow) loadWorkflowData(run.workflow, { dirty:false, notify:false });
      attachRun(run, true);
      closeManager('runManager');
      renderRunList();
    } catch (error) { toast(t('run.message.statusFailed', { error:error.message }), 'error'); }
  }

  async function recoverActiveRun() {
    await fetchRuns({ quiet:true });
    const run = state.runs.find(item => item.workflow_id === state.activeWorkflowId && ['running','cancelling'].includes(normalizeRunStatus(item.status)))
      || state.runs.find(item => item.workflow_id === state.activeWorkflowId && normalizeRunStatus(item.status) === 'queued');
    if (run) attachRun(run, true);
    else detachRun();
  }

  async function requestRunCancel(id) {
    if (!id) return;
    if (id === state.runId) log(t('run.message.cancelling'));
    try {
      const result = await api(`/api/runs/${encodeURIComponent(id)}`, { method:'DELETE' });
      if (id === state.runId) handleRunEvent(result);
      await fetchRuns({ quiet:true });
    } catch (error) { toast(t('run.message.cancelFailed', { error:error.message }), 'error'); }
  }

  async function cancelRun() {
    await requestRunCancel(state.runId);
  }

  function releasePointerCapture(interaction) {
    if (!interaction?.captureEl || interaction.pointerId == null) return;
    try {
      if (interaction.captureEl.hasPointerCapture(interaction.pointerId)) interaction.captureEl.releasePointerCapture(interaction.pointerId);
    } catch { /* capture may already be gone */ }
  }

  function cancelPointerInteractions(revertNode = true) {
    if (state.connectionDrag) finishConnectionDrag(null, true);
    if (state.dragging) {
      const drag = state.dragging;
      state.dragging = null;
      if (revertNode && drag.moved) {
        const node = state.workflow.nodes.find(item => item.id === drag.id);
        if (node) { node.data.x = drag.nodeX; node.data.y = drag.nodeY; refreshNodePresentation(node); }
      }
      releasePointerCapture(drag);
    }
    if (state.panning) {
      const pan = state.panning;
      state.panning = null;
      releasePointerCapture(pan);
    }
    refs.viewport.classList.remove('panning','node-dragging','connecting');
  }

  function startCanvasPan(event) {
    if (event.button !== 0 || event.target.closest('.node,.edge-hit,button,input,select,textarea,a')) return;
    cancelPointerInteractions(true);
    cancelConnection();
    event.preventDefault();
    state.selectedNode = null; state.selectedEdge = null;
    renderSelection(); renderEdges(); renderInspector();
    state.panning = { pointerId:event.pointerId, captureEl:refs.viewport, x:event.clientX, y:event.clientY, tx:state.transform.x, ty:state.transform.y };
    refs.viewport.classList.add('panning');
    refs.viewport.setPointerCapture(event.pointerId);
  }

  function handlePointerMove(event) {
    if (state.connectionDrag?.pointerId === event.pointerId) { updateConnectionDrag(event); return; }
    if (state.panning?.pointerId === event.pointerId) {
      event.preventDefault();
      state.transform.x = state.panning.tx + event.clientX - state.panning.x;
      state.transform.y = state.panning.ty + event.clientY - state.panning.y;
      applyTransform();
      return;
    }
    if (state.dragging?.pointerId === event.pointerId) {
      event.preventDefault();
      const drag = state.dragging;
      const node = state.workflow.nodes.find(item => item.id === drag.id);
      if (!node) { cancelPointerInteractions(); return; }
      const dx = (event.clientX - drag.startX) / state.transform.scale;
      const dy = (event.clientY - drag.startY) / state.transform.scale;
      node.data.x = Math.round(drag.nodeX + dx);
      node.data.y = Math.round(drag.nodeY + dy);
      drag.moved ||= Math.abs(dx) + Math.abs(dy) > 2;
      refs.viewport.classList.add('node-dragging');
      refreshNodePresentation(node);
    }
  }

  function finishPointerInteraction(event, cancelled = false) {
    if (state.connectionDrag?.pointerId === event.pointerId) { finishConnectionDrag(event, cancelled); refs.viewport.classList.remove('connecting'); return; }
    if (state.dragging?.pointerId === event.pointerId) {
      const drag = state.dragging;
      state.dragging = null;
      releasePointerCapture(drag);
      const node = state.workflow.nodes.find(item => item.id === drag.id);
      if (cancelled && node) { node.data.x = drag.nodeX; node.data.y = drag.nodeY; refreshNodePresentation(node); }
      else if (drag.moved) { commit('移动节点'); renderInspector(); }
      refs.viewport.classList.remove('node-dragging');
      return;
    }
    if (state.panning?.pointerId === event.pointerId) {
      const pan = state.panning;
      state.panning = null;
      releasePointerCapture(pan);
      refs.viewport.classList.remove('panning');
    }
  }

  function bindGlobalEvents() {
    refs.viewport.addEventListener('pointerdown', startCanvasPan);
    document.addEventListener('pointermove', handlePointerMove, { passive:false });
    document.addEventListener('pointerup', event => finishPointerInteraction(event, false));
    document.addEventListener('pointercancel', event => finishPointerInteraction(event, true));
    document.addEventListener('lostpointercapture', event => {
      const active = state.connectionDrag || state.dragging || state.panning;
      if (active?.pointerId === event.pointerId) finishPointerInteraction(event, true);
    });
    window.addEventListener('blur', () => { cancelPointerInteractions(true); cancelConnection(); });
    refs.viewport.addEventListener('wheel',event=>{event.preventDefault();const rect=refs.viewport.getBoundingClientRect();setZoom(state.transform.scale*(event.deltaY>0?.9:1.1),event.clientX-rect.left,event.clientY-rect.top);},{passive:false});
    refs.viewport.addEventListener('dragover',event=>{event.preventDefault();event.dataTransfer.dropEffect='copy';});
    refs.viewport.addEventListener('drop',event=>{event.preventDefault();try{const data=JSON.parse(event.dataTransfer.getData('application/x-audioflow-node'));const rect=refs.viewport.getBoundingClientRect(),p=screenToWorld(event.clientX-rect.left,event.clientY-rect.top);addFromTemplate(data.type,data.id,{x:p.x-112,y:p.y-25});}catch{}});
    document.addEventListener('keydown',event=>{
      const manager = $('.manager-overlay:not(.hidden)');
      if (event.key === 'Escape' && manager) { event.preventDefault(); manager.classList.add('hidden'); return; }
      if ((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='s') { event.preventDefault(); saveWorkflow(); return; }
      if(event.key==='Escape'&&(state.connectionDrag||state.pendingPort)){event.preventDefault();cancelConnection();return;}
      if (manager || ['INPUT','SELECT','TEXTAREA'].includes(event.target.tagName)) return;
      if(event.key==='Delete'||event.key==='Backspace')removeSelected();
      if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z'){event.preventDefault();restoreHistory(state.historyIndex+(event.shiftKey?1:-1));}
    });
    $('#zoomIn').addEventListener('click',()=>setZoom(state.transform.scale*1.12));$('#zoomOut').addEventListener('click',()=>setZoom(state.transform.scale*.88));$('#zoomReset').addEventListener('click',()=>{state.transform={x:0,y:0,scale:1};applyTransform();});$('#fitView').addEventListener('click',fitView);
    $('#undoButton').addEventListener('click',()=>restoreHistory(state.historyIndex-1));$('#redoButton').addEventListener('click',()=>restoreHistory(state.historyIndex+1));
    $('#modelSearch').addEventListener('input',renderLibrary);$('#architectureFilter').addEventListener('change',renderLibrary);
    $('#refreshToggle').addEventListener('click',event=>{event.stopPropagation();$('#refreshMenu').classList.toggle('hidden');});document.addEventListener('click',()=>$('#refreshMenu').classList.add('hidden'));$$('#refreshMenu button').forEach(b=>b.addEventListener('click',()=>refreshModels(b.dataset.scope)));
    refs.workflowName.addEventListener('input',()=>{state.workflow.name=refs.workflowName.value;refs.canvasTitle.textContent=refs.workflowName.value;commit('重命名工作流');});
    $('#saveWorkflow').addEventListener('click',saveWorkflow);
    $('#newWorkflow').addEventListener('click',createNewWorkflow);
    $('#toggleLibrary').addEventListener('click',()=>setLibraryVisible(!state.libraryVisible));
    $('#closeLibrary').addEventListener('click',()=>setLibraryVisible(false));
    bindSidebarResizer(refs.libraryResizer, 'library');
    bindSidebarResizer(refs.inspectorResizer, 'inspector');
    $('#manageWorkflows').addEventListener('click',()=>{showManager('workflowManager');fetchWorkflows();});
    $('#refreshWorkflows').addEventListener('click',()=>fetchWorkflows());
    $('#saveAsWorkflow').addEventListener('click',saveWorkflowAs);
    $('#exportWorkflow').addEventListener('click',exportWorkflow);
    $('#importWorkflow').addEventListener('click',()=>$('#workflowFile').click());
    $('#workflowFile').addEventListener('change',async event=>{try{const file=event.target.files[0];if(file){const payload=JSON.parse(await file.text());payload.revision=0;payload.id=uid('workflow');loadWorkflowData(payload);closeManager('workflowManager');}}catch(error){toast(t('workflow.message.loadFailed', { error:error.message }),'error');}event.target.value='';});
    $('#manageRuns').addEventListener('click',()=>{showManager('runManager');fetchRuns();});
    $('#refreshRuns').addEventListener('click',()=>fetchRuns());
    $$('.manager-close').forEach(button=>button.addEventListener('click',()=>closeManager(button.dataset.closeManager)));
    $$('.manager-overlay').forEach(manager=>manager.addEventListener('pointerdown',event=>{if(event.target===manager)closeManager(manager.id);}));
    $('#runWorkflow').addEventListener('click',runWorkflow);$('#cancelRun').addEventListener('click',cancelRun);
    $('#closeInspector').addEventListener('click',()=>setInspectorVisible(false));
    $('#toggleInspector').addEventListener('click',()=>setInspectorVisible(!state.inspectorVisible));
    $('#activityToggle').addEventListener('click',()=>{$('.activity-panel').classList.toggle('collapsed');$('#activityChevron').textContent=$('.activity-panel').classList.contains('collapsed')?'⌄':'⌃';});
    window.addEventListener('audioflow:localechange', renderLocalizedUI);
    window.addEventListener('resize',handleViewportResize);
  }

  function renderLocalizedUI() {
    if (state.connectionDrag || state.dragging || state.panning) cancelPointerInteractions(true);
    i18n.applyDocumentTranslations();
    renderLibrary();
    renderGraph();
    renderRunControls();
    renderModelStatus();
    setDirty(state.dirty);
    renderWorkflowTabs();
    renderWorkflowList();
    renderRunList();
    if (state.pendingPort) {
      findPortElement(state.pendingPort)?.classList.add('pending');
      refs.hint.textContent = t('connection.clickOpposite');
      refs.hint.classList.remove('hidden');
    }
  }

  async function initWorkflow() {
    await fetchWorkflows({ quiet:true });
    let savedTabs = readTabState();
    if (!savedTabs?.openIds?.length) {
      const drafts = readDraftIndex();
      const mostRecent = drafts.at(-1);
      if (mostRecent) savedTabs = { openIds:drafts.map(item => item.id), activeId:mostRecent.id };
    }

    if (savedTabs?.openIds?.length) {
      const catalogIds = new Set(state.workflows.map(item => item.id));
      for (const id of [...new Set(savedTabs.openIds)]) {
        const draft = readDraft(id);
        try {
          if (draft?.workflow) loadWorkflowData(draft.workflow, { dirty:Boolean(draft.dirty), notify:false, activate:false });
          else if (catalogIds.has(id)) loadWorkflowData(await api(`/api/workflows/${encodeURIComponent(id)}`), { dirty:false, notify:false, activate:false });
        } catch {
          if (draft) removeDraft(id);
        }
      }
      const activeId = state.editors.has(savedTabs.activeId) ? savedTabs.activeId : state.openWorkflowIds.at(-1);
      if (activeId) {
        activateWorkflowEditor(activeId, { fit:true });
        return;
      }
    }

    let legacySaved = null, legacyDirty = false;
    try {
      legacySaved=localStorage.getItem(LEGACY_AUTOSAVE_KEY);
      legacyDirty=localStorage.getItem(LEGACY_AUTOSAVE_DIRTY_KEY)==='1';
    } catch { /* storage may be unavailable */ }
    if (legacySaved) {
      try {
        const id = loadWorkflowData(JSON.parse(legacySaved), { dirty:legacyDirty, notify:false });
        try { localStorage.removeItem(LEGACY_AUTOSAVE_KEY);localStorage.removeItem(LEGACY_AUTOSAVE_DIRTY_KEY); } catch { /* storage may be unavailable */ }
        if (id) return;
      } catch { /* ignore corrupt legacy autosave */ }
    }

    const workflow={id:uid('workflow'),name:t('workflow.untitled'),version:1,revision:0,nodes:[],edges:[]};
    state.workflow = workflow;
    workflow.nodes=[makeNode('input_folder',80,150),makeNode('output_folder',445,180)];
    registerEditor(workflow, { dirty:true, persisted:false });
    activateWorkflowEditor(workflow.id, { fit:true });
    persistAutosave();
  }

  async function bootstrap() {
    bindGlobalEvents();setLibraryVisible(state.libraryVisible);setInspectorVisible(state.inspectorVisible);applySidebarWidths();applyTransform();renderRunControls();loadModels();
    await initWorkflow();
    await recoverActiveRun();
    connectRunEvents();
  }

  bootstrap();
  window.setInterval(()=>{
    if(state.runs.some(run=>ACTIVE_RUN_STATUSES.has(normalizeRunStatus(run.status)))||!$('#runManager').classList.contains('hidden'))fetchRuns({ quiet:true });
  },8000);
})();
