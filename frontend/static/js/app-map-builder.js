
const MB = {
  step: 1,
  mode: 'create',
  name: '',
  _editingMapName: null,
  plants: [],
  merges: [],
  editMergeIndex: -1,
  availableNodes: [],
  storageName: 'Storage',
  _savedNodePositions: {},
  _manualNodePositions: {},
  _draftGraphState: null,
};

async function openMapBuilder() {
  const cfg = await api('/api/config/');
  const titleEl = document.getElementById('map-modal-title');
  if (titleEl) titleEl.textContent = 'Create Pipeline Map';
  MB._plants = cfg.plant_inputs;
  MB._mergePipeInputs = cfg.merge_pipe_inputs || {};
  MB.storageName = (cfg.storage_name || 'Storage').trim() || 'Storage';
  MB.step = 1;
  MB.mode = 'create';
  MB.name = '';
  MB._editingMapName = null;
  MB.plants = [];
  MB.merges = [];
  MB.editMergeIndex = -1;
  MB.availableNodes = [];
  MB._savedNodePositions = {};
  MB._lastLayout = null;
  MB._manualNodePositions = {};
  MB._draftGraphState = null;
  renderMBStep1();
  renderMBDraftReview();
  openModal('map-modal');
}

async function openMapEditor() {
  const mapName = (document.getElementById('map-sel')?.value || '').trim();
  if (!mapName) {
    alert('Select a pipeline map to edit first.');
    return;
  }

  try {
    const [cfg, mapData] = await Promise.all([
      api('/api/config/'),
      api(`/api/maps/${encodeURIComponent(mapName)}`),
    ]);

    const titleEl = document.getElementById('map-modal-title');
    if (titleEl) titleEl.textContent = `Edit Pipeline Map: ${mapName}`;

    MB._plants = cfg.plant_inputs;
    MB._mergePipeInputs = cfg.merge_pipe_inputs || {};
    MB.storageName = (mapData?.storage_name || cfg.storage_name || 'Storage').trim() || 'Storage';
    MB.step = 1;
    MB.mode = 'edit';
    MB.name = mapName;
    MB._editingMapName = mapName;
    MB.plants = _extractPlantIndexesFromMap(mapData, cfg.plant_inputs?.length || 0);
    MB.merges = (Array.isArray(mapData?.merge_definitions) ? mapData.merge_definitions : []).map(def => {
      const mergeName = String(def?.merge_name || '').trim();
      const configured = mapData?.merge_pipe_inputs?.[mergeName] || MB._mergePipeInputs?.[mergeName] || {};
      return {
        merge_name: mergeName,
        sources: Array.isArray(def?.sources) ? def.sources : [],
        pipelength: Number(configured?.pipelength ?? 10000),
        pipediameter: Number(configured?.pipediameter ?? 0.5),
      };
    });
    MB.editMergeIndex = -1;
    MB.availableNodes = [];
    MB._savedNodePositions = _cloneLayoutUnits(mapData?.node_positions || {});
    MB._lastLayout = null;
    MB._manualNodePositions = {};
    MB._draftGraphState = null;

    renderMBStep1();
    renderMBDraftReview();
    openModal('map-modal');
  } catch (e) {
    alert('Could not open map editor: ' + e.message);
  }
}

function updateMBPlantsFromStep1() {
  MB.plants = Array.from(document.querySelectorAll('#mb-step1 input[type=checkbox]:checked')).map(e => +e.value);
  renderMBDraftReview();
}

function selectAllMBPlants() {
  const allIndexes = MB._plants.map((_, i) => i);
  if (!allIndexes.length) {
    MB.plants = [];
    renderMBStep1();
    return;
  }

  const selectedPhase = MB.plants.length
    ? _normalizePhase(MB._plants[MB.plants[0]]?.stream_phase)
    : _normalizePhase(MB._plants[allIndexes[0]]?.stream_phase);

  const nextSelection = allIndexes.filter(i => {
    const phase = _normalizePhase(MB._plants[i]?.stream_phase);
    return !selectedPhase || !phase || phase === selectedPhase;
  });

  MB.plants = nextSelection;
  renderMBStep1();

  if (nextSelection.length < allIndexes.length) {
    alert(`Selected all ${selectedPhase || 'compatible'} plants. Some plants were skipped because pipeline maps only support one phase at a time.`);
  }
}

function onMBPlantToggle(event, plantIndex) {
  if (event.target.checked) {
    const currentPhases = new Set(
      MB.plants.map(i => _normalizePhase(MB._plants[i]?.stream_phase)).filter(Boolean)
    );
    const newPhase = _normalizePhase(MB._plants[plantIndex]?.stream_phase);
    if (currentPhases.size > 0 && newPhase && !currentPhases.has(newPhase)) {
      const existingPhase = [...currentPhases][0];
      alert(`Cannot add plant: phase '${newPhase}' conflicts with existing selection (${existingPhase}). All plants in a pipeline map must have the same phase.`);
      event.target.checked = false;
      return;
    }
  }
  updateMBPlantsFromStep1();
}

function updateMBStorageName() {
  MB.storageName = (document.getElementById('mb-storage-name')?.value || MB.storageName || 'Storage').trim() || 'Storage';
  renderMBDraftReview();
}

function renderMBStep1() {
  setWizardStep(1);
  document.getElementById('mb-step1').innerHTML = `
    <div class="section-label" style="display:flex;justify-content:space-between;align-items:center">
      <span>Select active plants</span>
      <button class="btn btn-sm" type="button" onclick="selectAllMBPlants()">Select All</button>
    </div>
    ${MB._plants.map((p, i) => `
      <label style="display:flex;align-items:center;gap:.5rem;padding:.35rem 0;cursor:pointer">
        <input type="checkbox" value="${i}" ${MB.plants.includes(i)?'checked':''}
          onchange="onMBPlantToggle(event, ${i})">
        <span>${p.name}</span>
        <span style="font-size:.75rem;color:#718096">${p.stream_phase} · ${p.flowrate} kg/hr · ${p.temperature_celsius}°C</span>
      </label>`).join('')}`;

  renderMBDraftReview();
}

function renderMBStep3() {
  setWizardStep(3);
  const mapNameLocked = MB.mode === 'edit' && Boolean(MB._editingMapName);
  document.getElementById('mb-step3').innerHTML = `
    <div class="section-label" style="margin-top:0">Finalize map</div>
    <div class="field-row" style="margin-bottom:1rem">
      <label style="max-width:420px"><span>Map name</span>
        <input id="mb-name" placeholder="e.g. my_pipeline" value="${_esc(MB.name)}" oninput="MB.name = this.value.trim()" ${mapNameLocked ? 'disabled' : ''}>
      </label>
    </div>
    ${mapNameLocked
      ? '<div class="empty" style="text-align:left;padding:0 0 .65rem 0;color:#4a5568">Editing existing map. Save will update this map in place.</div>'
      : ''}
    <div class="section-label" style="margin-top:0">Storage</div>
    <div class="field-row" style="margin-bottom:1rem">
      <label style="max-width:360px"><span>Storage node name</span>
        <input id="mb-storage-name" placeholder="e.g. Terminal Tank" value="${_esc(MB.storageName || 'Storage')}" oninput="updateMBStorageName()">
      </label>
    </div>
    <div class="empty" style="text-align:left;padding:0;color:#4a5568">
      Storage is connected from all terminal nodes in your map.
    </div>
  `;

  renderMBDraftReview();
}

function goMBNext() {
  if (MB.step === 1) {
    renderMBStep2();
    return;
  }
  if (MB.step === 2) {
    _autoCommitPendingMBStep2Selections();
    renderMBStep3();
  }
}

function _mapMBSourceSelectionsToBackendSources(srcs) {
  return srcs.map(src => {
    if (src.type === 'plant') {
      const plantIdx = MB._plants.findIndex(p => p.name === src.id);
      if (plantIdx !== -1 && MB.plants.includes(plantIdx)) return ['plant', plantIdx];
    }
    return ['merge', src.id];
  });
}

function _autoSavePendingMBMergeEdit() {
  if (!Number.isFinite(MB.editMergeIndex) || MB.editMergeIndex < 0) return false;
  const merge = MB.merges[MB.editMergeIndex];
  if (!merge) return false;

  const srcs = Array.from(
    document.querySelectorAll(`input[name="mb-edit-src-${MB.editMergeIndex}"]:checked`)
  ).map(e => ({
    id: e.value,
    type: e.dataset.type,
  }));

  if (srcs.length < 2) return false;
  merge.sources = _mapMBSourceSelectionsToBackendSources(srcs);
  MB.editMergeIndex = -1;
  return true;
}

function _autoAddPendingMBMerge() {
  const mergeNameEl = document.getElementById('mb-mname');
  if (!mergeNameEl) return false;

  const name = String(mergeNameEl.value || '').trim();
  if (!name) return false;
  if (MB.merges.some(m => m.merge_name === name)) return false;

  const srcs = Array.from(document.querySelectorAll('input[name="mb-src"]:checked')).map(e => ({
    id: e.value,
    type: e.dataset.type,
  }));
  if (srcs.length < 2) return false;

  const len = +document.getElementById('mb-mlen').value;
  const diam = +document.getElementById('mb-mdiam').value;
  const sources = _mapMBSourceSelectionsToBackendSources(srcs);

  MB.merges.push({ merge_name: name, sources, pipelength: len, pipediameter: diam });
  MB.editMergeIndex = -1;
  return true;
}

function _autoCommitPendingMBStep2Selections() {
  const didSaveEdit = _autoSavePendingMBMergeEdit();
  const didAddMerge = _autoAddPendingMBMerge();
  if (didSaveEdit || didAddMerge) {
    renderMBDraftReview();
  }
}

function goMBBack() {
  if (MB.step === 3) {
    renderMBStep2();
    return;
  }
  if (MB.step === 2) {
    renderMBStep1();
  }
}

function renderMBStep2() {
  setWizardStep(2);
  // Available nodes = selected plants + already-added merges
  MB.availableNodes = [
    ...MB.plants.map(i => ({ id: MB._plants[i].name, type: 'plant' })),
    ...MB.merges.map(m => ({ id: m.merge_name, type: 'merge' })),
  ];

  const configuredMergeNames = Object.keys(MB._mergePipeInputs || {}).filter(
    name => String(name).toLowerCase() !== 'default'
  );
  const usedMergeNames = new Set(MB.merges.map(m => m.merge_name));
  const unusedMergeNames = configuredMergeNames.filter(name => !usedMergeNames.has(name));

  const nodeChips = MB.availableNodes.map(n =>
    `<span class="chip chip-${n.type}">${n.id}</span>`).join('');

  const mergeList = MB.merges.length
    ? MB.merges.map((m, i) => `
        <div class="merge-def-row">
          <div style="flex:1">
            <span class="merge-def-name">${m.merge_name}</span>
            <span class="merge-def-meta"> ← ${m.sources.map(s=>s[1]).join(', ')} · ${m.pipelength} m · ⌀${m.pipediameter} m</span>
            ${MB.editMergeIndex === i ? `
              <div style="margin-top:.55rem;padding:.65rem;background:#edf2f7;border:1px solid #e2e8f0;border-radius:8px">
                <div class="section-label" style="margin-top:0">Edit sources (select >= 2)</div>
                ${MB.availableNodes
                  .filter(n => n.id !== m.merge_name)
                  .map(n => {
                    const checked = (m.sources || []).some(([srcType, srcValue]) =>
                      (srcType === 'plant' && n.type === 'plant' && MB._plants[srcValue]?.name === n.id)
                      || (srcType === 'merge' && n.type === 'merge' && String(srcValue) === String(n.id))
                    );
                    return `
                      <label style="display:flex;align-items:center;gap:.5rem;padding:.22rem 0;cursor:pointer">
                        <input type="checkbox" name="mb-edit-src-${i}" value="${_esc(n.id)}" data-type="${_esc(n.type)}" ${checked ? 'checked' : ''}>
                        <span class="chip chip-${n.type}" style="pointer-events:none">${_esc(n.id)}</span>
                      </label>`;
                  }).join('')}
                <div style="display:flex;gap:.45rem;flex-wrap:wrap;margin-top:.55rem">
                  <button class="btn btn-sm" type="button" onclick="saveMBMergeEdit(${i})">Save</button>
                  <button class="btn btn-sm" type="button" onclick="cancelMBMergeEdit()">Cancel</button>
                </div>
              </div>
            ` : ''}
          </div>
          <div style="display:flex;gap:.35rem;align-items:flex-start">
            <button class="btn btn-sm" type="button" onclick="startMBMergeEdit(${i})">Edit</button>
            <button class="btn btn-sm" style="background:#fff5f5;color:#c53030" onclick="removeMBMerge(${i})">✕</button>
          </div>
        </div>`).join('')
    : '<p style="color:#a0aec0;font-size:.85rem">No merges added yet - click "Add Merge" or skip to save without merges.</p>';

  document.getElementById('mb-step2').innerHTML = `
    <div class="section-label">Current nodes</div>
    <div class="node-chips">${nodeChips}</div>

    <div class="section-label">Added merges</div>
    <div id="mb-merge-list">${mergeList}</div>

    <details style="margin-top:1rem">
      <summary style="cursor:pointer;font-weight:600;color:#2b6cb0;font-size:.9rem">&#43; Add Merge</summary>
      <div style="padding:1rem;background:#f7fafc;border-radius:8px;margin-top:.5rem">
        <div class="field-row">
          <label><span>Merge name (from config)</span>
            <select id="mb-mname" onchange="syncMBMergePipeDefaults()">
              ${unusedMergeNames.length
                ? unusedMergeNames.map(name => `<option value="${_esc(name)}">${_esc(name)}</option>`).join('')
                : '<option value="">No configured merges left</option>'}
            </select>
          </label>
          <label><span>Pipe length (m)</span><input id="mb-mlen" type="number" value="${unusedMergeNames.length ? Number(MB._mergePipeInputs[unusedMergeNames[0]]?.pipelength ?? 10000) : ''}" ${unusedMergeNames.length ? '' : 'disabled'}></label>
          <label><span>Pipe diameter (m)</span><input id="mb-mdiam" type="number" step="any" value="${unusedMergeNames.length ? Number(MB._mergePipeInputs[unusedMergeNames[0]]?.pipediameter ?? 0.5) : ''}" ${unusedMergeNames.length ? '' : 'disabled'}></label>
        </div>
        <div class="section-label">Source nodes (select >= 2)</div>
        ${MB.availableNodes.map(n => `
          <label style="display:flex;align-items:center;gap:.5rem;padding:.25rem 0;cursor:pointer">
            <input type="checkbox" name="mb-src" value="${n.id}" data-type="${n.type}">
            <span class="chip chip-${n.type}" style="pointer-events:none">${n.id}</span>
          </label>`).join('')}
        <button class="btn btn-primary" style="margin-top:.75rem;width:auto;padding:.45rem 1.2rem" onclick="addMBMerge()" ${unusedMergeNames.length ? '' : 'disabled'}>Add</button>
      </div>
    </details>`;

  renderMBDraftReview();
}

function syncMBMergePipeDefaults() {
  const mergeName = document.getElementById('mb-mname')?.value;
  const mergeCfg = MB._mergePipeInputs?.[mergeName];
  const lenInput = document.getElementById('mb-mlen');
  const diamInput = document.getElementById('mb-mdiam');
  if (!lenInput || !diamInput) return;
  if (!mergeCfg) {
    lenInput.value = '';
    diamInput.value = '';
    return;
  }
  lenInput.value = Number(mergeCfg.pipelength ?? 10000);
  diamInput.value = Number(mergeCfg.pipediameter ?? 0.5);
}

function addMBMerge() {
  const name = document.getElementById('mb-mname').value.trim();
  const len = +document.getElementById('mb-mlen').value;
  const diam = +document.getElementById('mb-mdiam').value;
  const srcs = Array.from(document.querySelectorAll('input[name="mb-src"]:checked')).map(e => ({
    id: e.value,
    type: e.dataset.type,
  }));
  if (!name) { alert('Select a merge name from config.'); return; }
  if (srcs.length < 2) { alert('Select at least 2 source nodes.'); return; }
  if (MB.merges.some(m => m.merge_name === name)) { alert('That merge has already been added.'); return; }

  // Build sources as [["plant"|"merge", index/name]] matching backend format.
  const sources = _mapMBSourceSelectionsToBackendSources(srcs);

  MB.merges.push({ merge_name: name, sources, pipelength: len, pipediameter: diam });
  MB.editMergeIndex = -1;
  renderMBStep2();
}

function removeMBMerge(i) {
  MB.merges.splice(i, 1);
  if (MB.editMergeIndex === i) MB.editMergeIndex = -1;
  if (MB.editMergeIndex > i) MB.editMergeIndex -= 1;
  renderMBStep2();
}

function startMBMergeEdit(i) {
  MB.editMergeIndex = i;
  renderMBStep2();
}

function cancelMBMergeEdit() {
  MB.editMergeIndex = -1;
  renderMBStep2();
}

function saveMBMergeEdit(i) {
  const merge = MB.merges[i];
  if (!merge) return;

  const srcs = Array.from(document.querySelectorAll(`input[name="mb-edit-src-${i}"]:checked`)).map(e => ({
    id: e.value,
    type: e.dataset.type,
  }));

  if (srcs.length < 2) { alert('Select at least 2 source nodes.'); return; }

  const sources = _mapMBSourceSelectionsToBackendSources(srcs);

  merge.sources = sources;
  MB.editMergeIndex = -1;
  renderMBStep2();
}

function renderMBDraftReview() {
  const host = document.getElementById('mb-review');
  if (!host || !MB._plants) return;
  MB.storageName = (document.getElementById('mb-storage-name')?.value || MB.storageName || 'Storage').trim() || 'Storage';

  const nodes = new Map();
  const edges = [];
  const addNode = (id, label, type) => {
    if (!nodes.has(id)) nodes.set(id, { id, label, type });
  };

  MB.plants.forEach(plantIdx => {
    const plant = MB._plants[plantIdx];
    if (!plant) return;
    addNode(`plant:${plantIdx}`, plant.name || `Plant ${plantIdx + 1}`, 'plant');
  });

  MB.merges.forEach(merge => {
    const mergeId = `merge:${merge.merge_name}`;
    addNode(mergeId, merge.merge_name, 'merge');

    (merge.sources || []).forEach(([srcType, srcValue]) => {
      if (srcType === 'plant') {
        const idx = Number(srcValue);
        const plant = MB._plants[idx];
        const pid = `plant:${idx}`;
        addNode(pid, plant?.name || `Plant ${idx + 1}`, 'plant');
        edges.push([pid, mergeId]);
      } else {
        const mid = `merge:${srcValue}`;
        addNode(mid, String(srcValue), 'merge');
        edges.push([mid, mergeId]);
      }
    });
  });

  // Storage should appear at the end of map building (storage step), not during plants/merges editing.
  if (nodes.size && MB.step === 3) {
    const storageId = `storage:${MB.storageName}`;
    addNode(storageId, MB.storageName, 'storage');

    const outgoing = new Set(edges.map(([src]) => src));
    Array.from(nodes.values())
      .filter(node => node.type !== 'storage' && !outgoing.has(node.id))
      .forEach(node => edges.push([node.id, storageId]));
  }

  if (!nodes.size) {
    MB._draftGraphState = null;
    host.innerHTML = '<div class="empty" style="padding:1rem 0">Select plants to start the map review.</div>';
    return;
  }

  const layoutUnits = _computeOverlapAwareLayout(
    Array.from(nodes.values()),
    edges,
    MB._lastLayout || null,
  );
  Object.entries(MB._savedNodePositions || {}).forEach(([id, p]) => {
    if (!layoutUnits[id]) return;
    const x = Number(p?.x);
    const y = Number(p?.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return;
    layoutUnits[id] = { x, y };
  });
  MB._lastLayout = layoutUnits;

  const xs = Object.values(layoutUnits).map(p => p.x);
  const ys = Object.values(layoutUnits).map(p => p.y);
  const minX = xs.length ? Math.min(...xs) : 0;
  const maxX = xs.length ? Math.max(...xs) : 0;
  const maxAbsY = ys.length ? Math.max(...ys.map(y => Math.abs(y))) : 0;

  const xScale = 180;
  const yScale = 105;
  const xPad = 120;
  const yPad = 100;
  const width = Math.max(1200, (maxX - minX) * xScale + xPad * 2 + 100);
  const height = Math.max(760, (maxAbsY * 2) * yScale + yPad * 2 + 100);
  const positions = {};

  Object.entries(layoutUnits).forEach(([id, p]) => {
    positions[id] = {
      x: xPad + (p.x - minX) * xScale,
      y: (height / 2) - p.y * yScale,
    };
  });

  const activeNodeIds = new Set(Object.keys(positions));
  const nextManualPositions = {};
  Object.entries(MB._manualNodePositions || {}).forEach(([id, p]) => {
    if (!activeNodeIds.has(id) || !p) return;
    positions[id] = { x: Number(p.x), y: Number(p.y) };
    nextManualPositions[id] = { x: Number(p.x), y: Number(p.y) };
  });
  MB._manualNodePositions = nextManualPositions;

  const outgoingByNode = new Map();
  const incomingByNode = new Map();
  edges.forEach(([src, dst], idx) => {
    if (!outgoingByNode.has(src)) outgoingByNode.set(src, []);
    if (!incomingByNode.has(dst)) incomingByNode.set(dst, []);
    outgoingByNode.get(src).push(idx);
    incomingByNode.get(dst).push(idx);
  });

  MB._draftGraphState = {
    edges,
    positions,
    outgoingByNode,
    incomingByNode,
    nodes: Array.from(nodes.values()),
    nodeWidth: 56,
    nodeHeight: 32,
  };

  const edgeSvg = _renderMBDraftEdgePaths();
  const nodeSvg = _renderMBDraftNodes();

  host.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;gap:.6rem;margin-bottom:.4rem;flex-wrap:wrap;">
      <div style="font-size:.78rem;color:#4a5568">Drag nodes to tune the layout while you build.</div>
      <button class="btn btn-sm" type="button" onclick="resetMBDraftNodePositions()">Reset node positions</button>
    </div>
    <svg class="map-preview-svg" id="mb-review-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Draft pipeline map review">
      <defs>
        <marker id="mb-arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L10,4 L0,8 z" fill="#4a5568"></path>
        </marker>
      </defs>
      <g id="mb-review-edges">${edgeSvg}</g>
      <g id="mb-review-nodes">${nodeSvg}</g>
    </svg>
  `;

  enableMBDraftReviewInteractions();
}

function _mbDraftNodeRect(nodeId) {
  const state = MB._draftGraphState;
  if (!state) return null;
  const p = state.positions[nodeId];
  if (!p) return null;
  const hw = state.nodeWidth / 2;
  const hh = state.nodeHeight / 2;
  return {
    left: p.x - hw,
    right: p.x + hw,
    top: p.y - hh,
    bottom: p.y + hh,
    cx: p.x,
    cy: p.y,
  };
}

function _renderMBDraftEdgePaths() {
  const state = MB._draftGraphState;
  if (!state) return '';
  return state.edges.map(([src, dst], edgeIdx) => {
    const sourceRect = _mbDraftNodeRect(src);
    const targetRect = _mbDraftNodeRect(dst);
    if (!sourceRect || !targetRect) return '';

    const srcEdges = state.outgoingByNode.get(src) || [edgeIdx];
    const dstEdges = state.incomingByNode.get(dst) || [edgeIdx];
    const srcSlot = srcEdges.indexOf(edgeIdx);
    const dstSlot = dstEdges.indexOf(edgeIdx);

    const pathD = _buildClassicEdgePath({
      sourceRect,
      targetRect,
      srcSlot,
      srcCount: srcEdges.length,
      dstSlot,
      dstCount: dstEdges.length,
    });
    return `<path d="${pathD}" fill="none" stroke="#4a5568" stroke-width="2" marker-end="url(#mb-arrow)" />`;
  }).join('');
}

function _renderMBDraftNodes() {
  const state = MB._draftGraphState;
  if (!state) return '';
  const hw = state.nodeWidth / 2;
  const hh = state.nodeHeight / 2;
  return state.nodes.map(node => {
    const p = state.positions[node.id];
    const fill = node.type === 'plant' ? '#c6f6d5' : (node.type === 'storage' ? '#bee3f8' : '#feebc8');
    const stroke = node.type === 'plant' ? '#276749' : (node.type === 'storage' ? '#2c5282' : '#c05621');
    return `
      <g class="mb-node" data-node-id="${_esc(node.id)}" transform="translate(${p.x} ${p.y})">
        <rect x="${-hw}" y="${-hh}" rx="7" ry="7" width="${state.nodeWidth}" height="${state.nodeHeight}" fill="${fill}" stroke="${stroke}" stroke-width="1.8" />
        <text x="0" y="3.5" text-anchor="middle" font-size="10.5" fill="#2d3748">${_esc(node.label)}</text>
      </g>
    `;
  }).join('');
}

function _syncMBDraftSvg() {
  const state = MB._draftGraphState;
  if (!state) return;
  const edgesGroup = document.getElementById('mb-review-edges');
  const nodesGroup = document.getElementById('mb-review-nodes');
  if (!edgesGroup || !nodesGroup) return;
  edgesGroup.innerHTML = _renderMBDraftEdgePaths();
  nodesGroup.innerHTML = _renderMBDraftNodes();
}

function resetMBDraftNodePositions() {
  MB._manualNodePositions = {};
  renderMBDraftReview();
}

function enableMBDraftReviewInteractions() {
  const svg = document.getElementById('mb-review-svg');
  if (!svg) return;

  let nodeDragging = null;

  const pointFromEvent = (event) => {
    const rect = svg.getBoundingClientRect();
    const viewBox = svg.viewBox.baseVal;
    const sx = viewBox.width / rect.width;
    const sy = viewBox.height / rect.height;
    return {
      x: viewBox.x + (event.clientX - rect.left) * sx,
      y: viewBox.y + (event.clientY - rect.top) * sy,
    };
  };

  svg.style.touchAction = 'none';

  svg.onpointerdown = (event) => {
    const nodeEl = event.target.closest('.mb-node');
    if (!nodeEl || !MB._draftGraphState) return;
    const nodeId = nodeEl.getAttribute('data-node-id');
    const pos = MB._draftGraphState.positions[nodeId];
    if (!pos) return;

    const p = pointFromEvent(event);
    nodeDragging = {
      pointerId: event.pointerId,
      nodeId,
      dx: pos.x - p.x,
      dy: pos.y - p.y,
    };
    svg.setPointerCapture(event.pointerId);
    event.preventDefault();
  };

  svg.onpointermove = (event) => {
    if (!nodeDragging || !MB._draftGraphState) return;
    if (event.pointerId !== nodeDragging.pointerId) return;

    const p = pointFromEvent(event);
    const nx = p.x + nodeDragging.dx;
    const ny = p.y + nodeDragging.dy;

    MB._draftGraphState.positions[nodeDragging.nodeId] = { x: nx, y: ny };
    MB._manualNodePositions[nodeDragging.nodeId] = { x: nx, y: ny };
    _syncMBDraftSvg();
  };

  svg.onpointerup = (event) => {
    if (!nodeDragging) return;
    if (event.pointerId === nodeDragging.pointerId) {
      nodeDragging = null;
      svg.releasePointerCapture(event.pointerId);
    }
  };

  svg.onpointercancel = () => {
    nodeDragging = null;
  };
}

async function saveMBMap() {
  MB.name = (document.getElementById('mb-name')?.value || MB.name).trim();
  MB.storageName = (document.getElementById('mb-storage-name')?.value || MB.storageName || 'Storage').trim() || 'Storage';
  if (!MB.name) { alert('Enter a map name first.'); return; }
  if (!MB.plants.length) { alert('Select at least one plant.'); return; }

  const targetMapName = MB.mode === 'edit' && MB._editingMapName ? MB._editingMapName : MB.name;

  const mergeDefinitions = MB.merges.map(m => ({
    merge_name: m.merge_name,
    sources: m.sources,
  }));
  const mergePipeInputs = Object.fromEntries(
    MB.merges.map(m => [m.merge_name, { pipelength: m.pipelength, pipediameter: m.pipediameter }])
  );
  const nodePositions = _cloneLayoutUnits(
    _savedMapManualLayoutByMap.get(targetMapName)
      || MB._savedNodePositions
      || {}
  );

  try {
    await api(MB.mode === 'edit' ? `/api/maps/${encodeURIComponent(targetMapName)}` : '/api/maps/', {
      method: MB.mode === 'edit' ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: MB.name,
        pipeline_map: {
          merge_definitions: mergeDefinitions,
          merge_pipe_inputs: mergePipeInputs,
          selected_plant_indexes: MB.plants,
          storage_name: MB.storageName,
          node_positions: nodePositions,
        },
      }),
    });
    closeModal('map-modal');
    await loadMaps(targetMapName, { openPopup: true });
  } catch (e) {
    alert('Save failed: ' + e.message);
  }
}

function setWizardStep(n) {
  [1, 2, 3].forEach(i => {
    document.getElementById('mb-step' + i).classList.toggle('active', i === n);
    const s = document.getElementById('wstep' + i);
    s.classList.toggle('active', i === n);
    s.classList.toggle('done', i < n);
  });
  document.getElementById('mb-next-btn').style.display = (n === 1 || n === 2) ? '' : 'none';
  document.getElementById('mb-back-btn').style.display = (n === 2 || n === 3) ? '' : 'none';
  document.getElementById('mb-save-btn').style.display = n === 3 ? '' : 'none';
  MB.step = n;
}
