// Load maps

async function loadMaps(preferredMapName = null, options = {}) {
  const shouldOpenPopup = Boolean(options?.openPopup);
  try {
    const maps = await api('/api/maps/');
    const sel = document.getElementById('map-sel');
    const list = document.getElementById('map-list');
    const previousSelection = String(sel?.value || '').trim();

    let selectedMapName = '';
    if (maps.length) {
      const preferred = String(preferredMapName || '').trim();
      if (preferred && maps.some(m => m.name === preferred)) {
        selectedMapName = preferred;
      } else if (previousSelection && maps.some(m => m.name === previousSelection)) {
        selectedMapName = previousSelection;
      } else {
        selectedMapName = String(maps[0].name);
      }
    }
    if (sel) {
      sel.value = selectedMapName;
    }

    if (list) {
      list.innerHTML = maps.length
        ? maps.map(map => `
            <div class="map-item">
              <div class="map-item-details">
                <span class="map-item-name">${_esc(map.name)}</span>
                <span class="map-item-meta">${map.merge_count} merge${map.merge_count === 1 ? '' : 's'}</span>
              </div>
              <div class="map-item-actions">
                <button
                  class="btn btn-sm map-item-pick ${selectedMapName === map.name ? 'is-active' : ''}"
                  type="button"
                  data-map-name="${encodeURIComponent(String(map.name))}"
                  onclick="selectMapFromList(decodeURIComponent(this.dataset.mapName))">Select</button>
                <button
                  class="btn btn-sm map-item-delete"
                  type="button"
                  data-map-name="${encodeURIComponent(String(map.name))}"
                  onclick="deleteMapFromList(decodeURIComponent(this.dataset.mapName))">Delete</button>
              </div>
            </div>
          `).join('')
        : '<div class="empty">No maps saved</div>';
    }

    if (maps.length) {
      if (shouldOpenPopup) {
        await onMapSelectionChange({ openPopup: true });
      } else {
        await previewSelectedMap();
      }
    } else {
      showMapPreviewMessage('No saved maps yet. Create one to preview it here.');
    }
  } catch {
    showMapPreviewMessage('Could not load saved maps.');
  }
}

function selectMapFromList(mapName) {
  const sel = document.getElementById('map-sel');
  if (!sel) return;
  sel.value = mapName;
  loadMaps(mapName, { openPopup: true });
}

async function deleteMapFromList(mapName) {
  const selectedName = String(mapName || '').trim();
  if (!selectedName) {
    alert('Select a pipeline map to delete first.');
    return;
  }

  const confirmed = window.confirm(`Delete pipeline map '${selectedName}'? This cannot be undone.`);
  if (!confirmed) return;

  try {
    await api(`/api/maps/${encodeURIComponent(selectedName)}`, { method: 'DELETE' });
    closeModal('map-vars-modal');
    await loadMaps();
    status(`Deleted pipeline map '${selectedName}'.`, 'ok');
  } catch (e) {
    alert('Could not delete map: ' + e.message);
  }
}

async function deleteSelectedMap() {
  const sel = document.getElementById('map-sel');
  const mapName = String(sel?.value || '').trim();
  return deleteMapFromList(mapName);
}

function _plantLabelByIndex(plantInputs, plantIndex) {
  const idx = Number(plantIndex);
  if (!Number.isFinite(idx) || idx < 0) return `Plant ${plantIndex}`;
  const plant = Array.isArray(plantInputs) ? plantInputs[idx] : null;
  const configuredName = String(plant?.name || '').trim();
  return configuredName || `Plant ${idx + 1}`;
}

let _currentPlantInputs = [];

function _displaySourceName(row, plantInputs = _currentPlantInputs) {
  const srcType = String(row?.source_type || '').trim();
  const srcName = row?.source_name ?? row?.merge_name;
  if (srcType !== 'plant') return srcName ?? '—';
  return _plantLabelByIndex(plantInputs, srcName);
}

function _normalizePhase(rawPhase) {
  return String(rawPhase || '').trim().toLowerCase();
}

function _validateSinglePhasePlants(plantInputs, plantIndexes = null) {
  const indexes = Array.isArray(plantIndexes)
    ? plantIndexes
    : (plantInputs || []).map((_, idx) => idx);

  const usedPhases = new Set();
  const usedPlants = [];

  indexes.forEach(idx => {
    const plant = Array.isArray(plantInputs) ? plantInputs[Number(idx)] : null;
    if (!plant) return;
    const phase = _normalizePhase(plant.stream_phase);
    if (!phase) return;
    usedPhases.add(phase);
    usedPlants.push(`${plant.name || `Plant ${Number(idx) + 1}`} (${phase})`);
  });

  if (usedPhases.size <= 1) return { ok: true };
  return {
    ok: false,
    message: `Only single-phase systems are allowed. Mixed phases detected: ${usedPlants.join(', ')}`,
  };
}

function _extractPlantIndexesFromMap(mapData, fallbackPlantCount = 0) {
  const selected = Array.isArray(mapData?.selected_plant_indexes)
    ? mapData.selected_plant_indexes
      .map(idx => Number(idx))
      .filter(idx => Number.isInteger(idx) && idx >= 0)
    : [];
  if (selected.length) {
    return Array.from(new Set(selected)).sort((a, b) => a - b);
  }

  const defs = Array.isArray(mapData?.merge_definitions) ? mapData.merge_definitions : [];
  const indexes = new Set();

  defs.forEach(def => {
    (def?.sources || []).forEach(source => {
      const srcType = Array.isArray(source) ? source[0] : null;
      const srcValue = Array.isArray(source) ? source[1] : null;
      if (srcType !== 'plant') return;
      const idx = Number(srcValue);
      if (Number.isFinite(idx) && idx >= 0) indexes.add(idx);
    });
  });

  // If a map has no merge definitions, treat all plants as participating.
  if (!indexes.size && Number.isFinite(fallbackPlantCount) && fallbackPlantCount > 0) {
    for (let i = 0; i < fallbackPlantCount; i += 1) indexes.add(i);
  }

  return Array.from(indexes).sort((a, b) => a - b);
}

function renderMapVariablesPopup(mapName, mapData, plantInputs = []) {
  const content = document.getElementById('map-vars-content');
  const defs = Array.isArray(mapData?.merge_definitions) ? mapData.merge_definitions : [];
  const pipeInputs = mapData?.merge_pipe_inputs || {};
  const storageName = String(mapData?.storage_name || 'Storage').trim() || 'Storage';

  const mergeDefsHtml = defs.length
    ? `<ul class="map-vars-list">${defs.map(def => {
      const sources = (def.sources || [])
        .map(([srcType, srcVal]) => srcType === 'plant' ? `plant:${_plantLabelByIndex(plantInputs, srcVal)}` : `merge:${srcVal}`)
        .join(', ');
      return `<li><strong>${_esc(def.merge_name)}</strong> ← ${_esc(sources)}</li>`;
    }).join('')}</ul>`
    : '<div class="empty" style="padding:.5rem 0">No merge definitions in this map.</div>';

  const mergeVars = Object.entries(pipeInputs);
  const mergeVarsHtml = mergeVars.length
    ? `<ul class="map-vars-list">${mergeVars.map(([name, val]) => {
      const length = val?.pipelength ?? '—';
      const diameter = val?.pipediameter ?? '—';
      return `<li><strong>${_esc(name)}</strong>: length=${_esc(length)}, diameter=${_esc(diameter)}</li>`;
    }).join('')}</ul>`
    : '<div class="empty" style="padding:.5rem 0">No merge pipe inputs in this map.</div>';

  content.innerHTML = `
    <div class="map-vars-title">Map: ${_esc(mapName)}</div>
    <div class="map-vars-section">
      <h3>Storage</h3>
      <ul class="map-vars-list"><li><strong>Name</strong>: ${_esc(storageName)}</li></ul>
    </div>
    <div class="map-vars-section">
      <h3>Merge Definitions</h3>
      ${mergeDefsHtml}
    </div>
    <div class="map-vars-section">
      <h3>Merge Pipe Inputs</h3>
      ${mergeVarsHtml}
    </div>
  `;
}

async function onMapSelectionChange(options = {}) {
  const shouldOpenPopup = options?.openPopup !== false;
  const mapName = document.getElementById('map-sel').value;
  if (!mapName) {
    showMapPreviewMessage('Select a pipeline map to preview it here.');
    return;
  }

  showMapLoading(`Loading interactive pipeline map: ${mapName}...`);

  try {
    const [mapData, cfg] = await _loadMapAndConfigWithRetry(mapName);
    const plantInputs = Array.isArray(cfg?.plant_inputs) ? cfg.plant_inputs : [];
    _currentPlantInputs = plantInputs;
    renderMapPreview(mapName, mapData, plantInputs, null, 'Previewing saved map', { interactive: true });
    renderMapVariablesPopup(mapName, mapData, plantInputs);
    if (shouldOpenPopup) {
      openModal('map-vars-modal');
    }
  } catch (e) {
    showMapPreviewMessage(`Could not load map preview: ${e.message}`);
  }
}

