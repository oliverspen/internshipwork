const _RESULT_COLUMN_DEFS = [
  {
    key: 'source_name',
    label: 'source name',
    defaultSelected: true,
    getter: (row) => _displaySourceName(row),
  },
  {
    key: 'source_type',
    label: 'source type',
    defaultSelected: true,
    render: (row) => {
      const type = row.source_type ?? (row.merge_name ? 'merge' : '—');
      return `<span class="tag tag-${_esc(type)}">${_esc(type)}</span>`;
    },
  },
  {
    key: 'stream_phase',
    label: 'stream phase',
    defaultSelected: true,
  },
  {
    key: 'total_massflow',
    label: 'massflow (kg/hr)',
    defaultSelected: true,
    getter: (row) => row.total_massflow ?? row.flow_kg_per_h ?? null,
  },
  {
    key: 'temperature_kelvin',
    label: 'temperature (C)',
    defaultSelected: true,
    getter: (row) => {
      if (row.temperature_kelvin != null) return fmtCelsiusFromKelvin(row.temperature_kelvin);
      if (row.temperature_celsius != null) return Number(row.temperature_celsius).toFixed(2);
      return '—';
    },
  },
  {
    key: 'density_kg_per_m3',
    label: 'density (kg/m3)',
    defaultSelected: false,
  },
];

const _RESULT_COLUMN_LABEL_ALIASES = {
  source_name: 'source name',
  source_type: 'source type',
  stream_phase: 'stream phase',
  total_massflow: 'massflow (kg/hr)',
  flow_kg_per_h: 'massflow (kg/hr)',
  temperature_kelvin: 'temperature (C)',
  temperature_celsius: 'temperature (C)',
  density_kg_per_m3: 'density (kg/m3)',
};

const _RESULT_ALIAS_KEYS_TO_HIDE = new Set([
  'flow_kg_per_h',
  'temperature_celsius',
]);

let _resultsSelectedColumns = [];
let _resultsAvailableColumns = [];
let _latestResultRows = [];

function _isPlainObject(value) {
  return Object.prototype.toString.call(value) === '[object Object]';
}

function _flattenResultKeys(obj, prefix = '') {
  const keys = [];
  Object.entries(obj || {}).forEach(([rawKey, value]) => {
    const key = prefix ? `${prefix}.${rawKey}` : rawKey;
    if (_isPlainObject(value)) {
      keys.push(..._flattenResultKeys(value, key));
      return;
    }
    keys.push(key);
  });
  return keys;
}

function _getResultPathValue(obj, path) {
  return String(path || '').split('.').reduce((acc, part) => {
    if (acc == null) return undefined;
    return acc[part];
  }, obj);
}

function _humanizeResultKey(key) {
  const rawKey = String(key || '');
  if (_RESULT_COLUMN_LABEL_ALIASES[rawKey]) return _RESULT_COLUMN_LABEL_ALIASES[rawKey];
  if (rawKey.startsWith('tocomo_input.')) {
    const species = rawKey.slice('tocomo_input.'.length);
    return `inlet ${species} (molar ppm)`;
  }
  if (rawKey.startsWith('final.')) {
    const species = rawKey.slice('final.'.length);
    return `predicted ${species} (molar ppm)`;
  }

  return rawKey.replaceAll('_', ' ').replaceAll('.', ' / ');
}

function _formatNumericCell(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return _esc(String(value));
  const abs = Math.abs(n);
  if (abs === 0) return '0';
  if (abs >= 1000) return n.toFixed(1);
  if (abs >= 1) return n.toFixed(3).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1');

  // Keep small values in plain decimal form for readability in the table.
  for (const digits of [3, 4, 5, 6, 8, 10, 12]) {
    const text = n.toFixed(digits).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1');
    if (text !== '0' && text !== '-0') return text;
  }
  return n.toString();
}

function _renderResultCell(col, row) {
  if (typeof col.render === 'function') return col.render(row);
  const raw = typeof col.getter === 'function' ? col.getter(row) : _getResultPathValue(row, col.key);
  if (raw == null || raw === '') return '—';
  if (typeof raw === 'string') return _esc(raw);
  if (typeof raw === 'number') {
    const key = String(col.key || '');
    if (key.startsWith('tocomo_input.') || key.startsWith('final.')) {
      return Number.isFinite(raw) ? raw.toFixed(2) : _esc(String(raw));
    }
    return _formatNumericCell(raw);
  }
  if (typeof raw === 'boolean') return raw ? 'true' : 'false';
  if (Array.isArray(raw) || _isPlainObject(raw)) return _esc(JSON.stringify(raw));
  return _esc(String(raw));
}

function _buildResultColumns(rows) {
  const discoveredKeys = new Set();
  rows.forEach(row => {
    _flattenResultKeys(row).forEach(key => discoveredKeys.add(key));
  });

  const defByKey = new Map(_RESULT_COLUMN_DEFS.map(def => [def.key, def]));
  const columns = [];

  _RESULT_COLUMN_DEFS.forEach(def => {
    const hasData = rows.some(row => {
      const value = typeof def.getter === 'function' ? def.getter(row) : _getResultPathValue(row, def.key);
      return value != null && value !== '' && value !== '—';
    });
    if (hasData || def.defaultSelected) columns.push(def);
  });

  Array.from(discoveredKeys)
    .filter(key => !defByKey.has(key) && !_RESULT_ALIAS_KEYS_TO_HIDE.has(key))
    .sort((a, b) => a.localeCompare(b))
    .forEach(key => {
      columns.push({ key, label: _humanizeResultKey(key), defaultSelected: false });
    });

  return columns;
}

function _renderResultColumnPicker(columns) {
  const controls = document.getElementById('results-controls');
  const picker = document.getElementById('results-column-picker');
  const toggleBtn = document.getElementById('results-filter-toggle');
  if (!controls || !picker) return;
  if (!columns.length) {
    controls.style.display = 'none';
    controls.classList.remove('open');
    if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'false');
    picker.innerHTML = '';
    return;
  }

  const selected = new Set(_resultsSelectedColumns);
  picker.innerHTML = columns.map(col => `
    <label class="result-col-option">
      <input
        type="checkbox"
        data-col-key="${_esc(col.key)}"
        ${selected.has(col.key) ? 'checked' : ''}
        onchange="toggleResultColumn('${_esc(col.key)}', this.checked)">
      <span>${_esc(col.label)}</span>
    </label>
  `).join('');
  const isOpen = controls.classList.contains('open');
  controls.style.display = isOpen ? 'block' : 'none';
  if (toggleBtn) toggleBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
}

function toggleResultsFilterPanel() {
  const controls = document.getElementById('results-controls');
  const toggleBtn = document.getElementById('results-filter-toggle');
  if (!controls || !_resultsAvailableColumns.length) return;
  const nextOpen = !controls.classList.contains('open');
  controls.classList.toggle('open', nextOpen);
  controls.style.display = nextOpen ? 'block' : 'none';
  if (toggleBtn) {
    toggleBtn.setAttribute('aria-expanded', nextOpen ? 'true' : 'false');
  }
}

function toggleResultColumn(columnKey, checked) {
  const key = String(columnKey || '');
  if (!key) return;
  const availableKeys = new Set(_resultsAvailableColumns.map(col => col.key));
  const selected = new Set(_resultsSelectedColumns.filter(k => availableKeys.has(k)));
  if (checked) selected.add(key);
  else selected.delete(key);

  if (!selected.size) {
    selected.add(key);
    status('At least one parameter must stay visible in Results Summary.', 'info');
  }

  _resultsSelectedColumns = Array.from(selected);
  _renderResultColumnPicker(_resultsAvailableColumns);
  _renderResultTable(_latestResultRows);
}

function _renderResultTable(rows) {
  const thead = document.getElementById('results-thead');
  const tbody = document.getElementById('results-tbody');
  if (!thead || !tbody) return;

  const selectedColumns = _resultsAvailableColumns.filter(col => _resultsSelectedColumns.includes(col.key));
  if (!selectedColumns.length) {
    thead.innerHTML = '';
    tbody.innerHTML = '<tr><td>No parameters selected.</td></tr>';
    return;
  }

  thead.innerHTML = `<tr>${selectedColumns.map(col => `<th>${_esc(col.label)}</th>`).join('')}</tr>`;
  tbody.innerHTML = rows.map(row => `
    <tr>
      ${selectedColumns.map(col => `<td>${_renderResultCell(col, row)}</td>`).join('')}
    </tr>
  `).join('');
}

function showTable(rows) {
  if (!rows?.length) return;
  _latestResultRows = rows;
  document.getElementById('results-card').style.display = 'block';

  _resultsAvailableColumns = _buildResultColumns(rows);
  const availableKeys = new Set(_resultsAvailableColumns.map(col => col.key));
  const retainedSelection = _resultsSelectedColumns.filter(key => availableKeys.has(key));
  if (retainedSelection.length) {
    _resultsSelectedColumns = retainedSelection;
  } else {
    const defaults = _resultsAvailableColumns
      .filter(col => col.defaultSelected)
      .map(col => col.key);
    _resultsSelectedColumns = defaults.length ? defaults : (_resultsAvailableColumns[0] ? [_resultsAvailableColumns[0].key] : []);
  }

  _renderResultColumnPicker(_resultsAvailableColumns);
  _renderResultTable(rows);
}

// Init

document.getElementById('model-sel').addEventListener('change', () => {
  updateDynamicRunSettingsVisibility();
  if (_isDynamicModel(document.getElementById('model-sel').value)) {
    hideResultsSummary();
  }
  if (_cfg && document.getElementById('config-modal')?.classList.contains('open')) {
    renderConfigEditor();
  }
  loadSessions();
});
loadMaps();
updateDynamicRunSettingsVisibility();
loadSessions();

// Modal helpers

function openModal(id) { document.getElementById(id).classList.add('open'); }
function closeModal(id) { document.getElementById(id).classList.remove('open'); }

