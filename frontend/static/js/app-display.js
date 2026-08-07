// Display

function showMap(url) {
  document.getElementById('map-frame').src = url;
  document.getElementById('map-frame').style.display = 'block';
  document.getElementById('map-placeholder').style.display = 'none';
}

function setMapPanelTitle(title) {
  const titleEl = document.getElementById('map-panel-title');
  if (!titleEl) return;
  titleEl.textContent = title;
}

function _graphLabelFromUrl(url, index) {
  const fallback = `Graph ${index + 1}`;
  if (!url) return fallback;
  const parts = String(url).split('/');
  const fileName = parts[parts.length - 1] || '';
  if (!fileName) return fallback;
  const base = fileName.replace(/\.png$/i, '').replace(/[_-]+/g, ' ').trim();
  return base ? base.replace(/\b\w/g, c => c.toUpperCase()) : fallback;
}

function renderDynamicGraphs(graphUrls, mapName, mapData = null, plantInputs = []) {
  const uniqueUrls = Array.isArray(graphUrls)
    ? Array.from(new Set(graphUrls.filter(Boolean).map(String)))
    : [];

  const placeholder = document.getElementById('map-placeholder');
  const frame = document.getElementById('map-frame');
  frame.style.display = 'none';
  frame.src = 'about:blank';

  if (!uniqueUrls.length) {
    setMapPanelTitle('Dynamic Graphs');
    showMapPreviewMessage('Dynamic run completed, but no graph images were found for this session.');
    return;
  }

  const options = uniqueUrls
    .map((url, idx) => `<option value="${_esc(url)}">${_esc(_graphLabelFromUrl(url, idx))}</option>`)
    .join('');
  const initialUrl = uniqueUrls[0];

  setMapPanelTitle('Dynamic Graphs');
  placeholder.className = '';
  const mapSectionHtml = mapData
    ? `
      <div class="dynamic-map-preview-section">
        <div class="map-preview-title">Interactive map for <strong>${_esc(mapName)}</strong></div>
        <div id="dynamic-map-preview-host"></div>
      </div>
    `
    : '';

  placeholder.innerHTML = `
    <div class="map-preview-wrap dynamic-graphs-wrap">
      <div class="dynamic-graphs-header">
        <div class="map-preview-title">Graphs for <strong>${_esc(mapName)}</strong></div>
        <div class="dynamic-graphs-controls">
          <label for="dynamic-graph-select">Graph</label>
          <select id="dynamic-graph-select" onchange="switchDynamicGraph()">${options}</select>
          <a id="dynamic-graph-open" class="btn btn-sm link" href="${_esc(initialUrl)}" target="_blank">Open full size</a>
        </div>
      </div>
      <div class="dynamic-graph-stage">
        <img id="dynamic-graph-image" class="dynamic-graph-image" src="${_esc(initialUrl)}" alt="Dynamic simulation graph">
      </div>
    </div>
    ${mapSectionHtml}
  `;
  placeholder.style.display = 'block';

  if (mapData) {
    const mapHost = document.getElementById('dynamic-map-preview-host');
    if (mapHost) {
      renderMapPreview(
        mapName,
        mapData,
        plantInputs,
        null,
        'Interactive map',
        {
          interactive: true,
          placeholderEl: mapHost,
          suppressPanelTitle: true,
        },
      );
    }
  }
}

function switchDynamicGraph() {
  const select = document.getElementById('dynamic-graph-select');
  const img = document.getElementById('dynamic-graph-image');
  const link = document.getElementById('dynamic-graph-open');
  const selectedUrl = String(select?.value || '');
  if (!selectedUrl || !img || !link) return;
  img.src = selectedUrl;
  link.href = selectedUrl;
}

function hideResultsSummary() {
  const card = document.getElementById('results-card');
  const controls = document.getElementById('results-controls');
  const toggleBtn = document.getElementById('results-filter-toggle');
  const thead = document.getElementById('results-thead');
  const tbody = document.getElementById('results-tbody');
  if (thead) thead.innerHTML = '';
  if (tbody) tbody.innerHTML = '';
  if (controls) {
    controls.style.display = 'none';
    controls.classList.remove('open');
  }
  if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'false');
  if (card) card.style.display = 'none';
}

function showMapLoading(message = 'Loading interactive pipeline map...') {
  const placeholder = document.getElementById('map-placeholder');
  const frame = document.getElementById('map-frame');
  if (!placeholder || !frame) return;

  setMapPanelTitle('Interactive Pipeline Map');
  frame.style.display = 'none';
  frame.src = 'about:blank';
  placeholder.className = '';
  placeholder.innerHTML = `
    <div class="map-loading-wrap">
      <button class="btn map-loading-btn" type="button" disabled>
        <span class="spinner spinner-dark" aria-hidden="true"></span>
        ${_esc(message)}
      </button>
    </div>
  `;
  placeholder.style.display = 'block';
}

function showMapPreviewMessage(message) {
  const placeholder = document.getElementById('map-placeholder');
  const frame = document.getElementById('map-frame');
  frame.style.display = 'none';
  frame.src = 'about:blank';
  placeholder.className = 'empty';
  placeholder.textContent = message;
  placeholder.style.display = 'block';
}

function _esc(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function _formatTooltipRows(title, values) {
  const lines = [title];
  Object.entries(values || {}).forEach(([k, v]) => {
    const num = Number(v);
    if (!Number.isFinite(num) || num === 0) return;
    lines.push(`${k}: ${num.toFixed(1)}`);
  });
  return lines.join('\n');
}

function _escAttrMultiline(text) {
  return _esc(String(text ?? '')).replaceAll('\n', '&#10;');
}

const _savedMapLastLayoutByMap = new Map();

function _topoSortNodes(nodeIds, edges) {
  const incoming = new Map(nodeIds.map(id => [id, 0]));
  const outgoing = new Map(nodeIds.map(id => [id, []]));

  edges.forEach(([src, dst]) => {
    if (!incoming.has(src) || !incoming.has(dst)) return;
    incoming.set(dst, incoming.get(dst) + 1);
    outgoing.get(src).push(dst);
  });

  const queue = nodeIds.filter(id => incoming.get(id) === 0);
  const order = [];
  while (queue.length) {
    const id = queue.shift();
    order.push(id);
    (outgoing.get(id) || []).forEach(next => {
      incoming.set(next, incoming.get(next) - 1);
      if (incoming.get(next) === 0) queue.push(next);
    });
  }

  if (order.length < nodeIds.length) {
    nodeIds.forEach(id => {
      if (!order.includes(id)) order.push(id);
    });
  }
  return order;
}

function _computeOverlapAwareLayout(nodes, edges, previousPositions = null) {
  const nodeById = new Map(nodes.map(n => [n.id, n]));
  const nodeIds = nodes.map(n => n.id);
  if (!nodeIds.length) return {};

  const predsByNode = new Map(nodeIds.map(id => [id, []]));
  edges.forEach(([src, dst]) => {
    if (predsByNode.has(dst) && nodeById.has(src)) predsByNode.get(dst).push(src);
  });

  const order = _topoSortNodes(nodeIds, edges);

  const depth = {};
  order.forEach(id => {
    const preds = predsByNode.get(id) || [];
    depth[id] = preds.length ? Math.max(...preds.map(p => (depth[p] ?? 0) + 1)) : 0;
  });

  const grouped = {};
  nodeIds.forEach(id => {
    const d = depth[id] ?? 0;
    if (!grouped[d]) grouped[d] = [];
    grouped[d].push(id);
  });

  const typeRank = { plant: 0, merge: 1, storage: 2 };
  const baseRank = (id) => {
    const n = nodeById.get(id);
    const rank = typeRank[n?.type] ?? 3;
    if (n?.type === 'plant') {
      return [rank, Number(n?.plantIndex ?? Number.MAX_SAFE_INTEGER), String(n?.label || id)];
    }
    if (n?.type === 'merge') {
      return [rank, Number(n?.mergeOrder ?? Number.MAX_SAFE_INTEGER), String(n?.label || id)];
    }
    return [rank, Number.MAX_SAFE_INTEGER, String(n?.label || id)];
  };

  const compareRank = (ra, rb) => {
    for (let i = 0; i < Math.max(ra.length, rb.length); i += 1) {
      const av = ra[i];
      const bv = rb[i];
      if (av === bv) continue;
      if (typeof av === 'string' || typeof bv === 'string') return String(av).localeCompare(String(bv));
      return Number(av) - Number(bv);
    }
    return 0;
  };

  const levelNumbers = Object.keys(grouped).map(Number).sort((a, b) => a - b);
  levelNumbers.forEach(level => {
    const ids = grouped[level];
    ids.sort((a, b) => {
      if (previousPositions?.[a] && previousPositions?.[b]) {
        return previousPositions[b].y - previousPositions[a].y;
      }
      return compareRank(baseRank(a), baseRank(b));
    });
  });

  for (let i = 1; i < levelNumbers.length; i += 1) {
    const level = levelNumbers[i];
    const ids = grouped[level];
    const orderedBefore = levelNumbers.slice(0, i).flatMap(lv => grouped[lv] || []);
    const prevIndex = new Map(orderedBefore.map((id, idx) => [id, idx]));

    ids.sort((a, b) => {
      const apreds = predsByNode.get(a) || [];
      const bpreds = predsByNode.get(b) || [];
      const abar = apreds.length
        ? apreds.reduce((acc, p) => acc + (prevIndex.get(p) ?? orderedBefore.length + 999), 0) / apreds.length
        : Number.MAX_SAFE_INTEGER;
      const bbar = bpreds.length
        ? bpreds.reduce((acc, p) => acc + (prevIndex.get(p) ?? orderedBefore.length + 999), 0) / bpreds.length
        : Number.MAX_SAFE_INTEGER;
      if (abar !== bbar) return abar - bbar;
      return compareRank(baseRank(a), baseRank(b));
    });
  }

  const buildPositions = (horizontalGap, verticalGap) => {
    const p = {};
    levelNumbers.forEach(level => {
      const ids = grouped[level];
      const count = ids.length;
      const spread = verticalGap * (count - 1);
      const start = spread / 2;
      ids.forEach((id, idx) => {
        p[id] = {
          x: level * horizontalGap,
          y: count === 1 ? 0 : (start - idx * verticalGap),
        };
      });
    });
    return p;
  };

  const hasOverlap = p => {
    const ids = Object.keys(p);
    const xMin = 1.05;
    const yMin = 1.05;
    for (let i = 0; i < ids.length; i += 1) {
      const a = p[ids[i]];
      for (let j = i + 1; j < ids.length; j += 1) {
        const b = p[ids[j]];
        if (Math.abs(a.x - b.x) < xMin && Math.abs(a.y - b.y) < yMin) return true;
      }
    }
    return false;
  };

  let positions = buildPositions(1.0, 1.0);
  if (hasOverlap(positions)) positions = buildPositions(1.5, 1.35);
  return positions;
}

function _inflateRect(rect, pad) {
  return {
    left: rect.left - pad,
    right: rect.right + pad,
    top: rect.top - pad,
    bottom: rect.bottom + pad,
  };
}

function _pointInRect(point, rect) {
  return point.x >= rect.left && point.x <= rect.right && point.y >= rect.top && point.y <= rect.bottom;
}

function _segmentIntersectsRect(a, b, rect) {
  // Router emits orthogonal paths. Check horizontal/vertical segment collision.
  if (a.x === b.x) {
    const x = a.x;
    if (x < rect.left || x > rect.right) return false;
    const minY = Math.min(a.y, b.y);
    const maxY = Math.max(a.y, b.y);
    return maxY >= rect.top && minY <= rect.bottom;
  }
  if (a.y === b.y) {
    const y = a.y;
    if (y < rect.top || y > rect.bottom) return false;
    const minX = Math.min(a.x, b.x);
    const maxX = Math.max(a.x, b.x);
    return maxX >= rect.left && minX <= rect.right;
  }

  // Safety fallback for diagonal fallback segments.
  const minX = Math.min(a.x, b.x);
  const maxX = Math.max(a.x, b.x);
  const minY = Math.min(a.y, b.y);
  const maxY = Math.max(a.y, b.y);
  return !(maxX < rect.left || minX > rect.right || maxY < rect.top || minY > rect.bottom);
}

function _polylineIntersectsRect(points, rect) {
  for (let i = 0; i < points.length - 1; i += 1) {
    if (_segmentIntersectsRect(points[i], points[i + 1], rect)) return true;
  }
  return false;
}

function _simplifyOrthogonalPolyline(points) {
  if (points.length <= 2) return points;
  const out = [points[0]];
  for (let i = 1; i < points.length - 1; i += 1) {
    const a = out[out.length - 1];
    const b = points[i];
    const c = points[i + 1];
    const sameVertical = a.x === b.x && b.x === c.x;
    const sameHorizontal = a.y === b.y && b.y === c.y;
    if (sameVertical || sameHorizontal) continue;
    out.push(b);
  }
  out.push(points[points.length - 1]);
  return out;
}

function _gridRouteOrthogonal(start, end, obstacles, bounds, step = 10) {
  const pad = step * 2;
  const minX = Math.floor((Math.min(start.x, end.x, bounds.minX) - pad) / step) * step;
  const maxX = Math.ceil((Math.max(start.x, end.x, bounds.maxX) + pad) / step) * step;
  const minY = Math.floor((Math.min(start.y, end.y, bounds.minY) - pad) / step) * step;
  const maxY = Math.ceil((Math.max(start.y, end.y, bounds.maxY) + pad) / step) * step;

  const toCell = (p) => ({
    x: Math.round((p.x - minX) / step),
    y: Math.round((p.y - minY) / step),
  });
  const toPoint = (c) => ({ x: minX + c.x * step, y: minY + c.y * step });
  const key = (c) => `${c.x},${c.y}`;

  const startCell = toCell(start);
  const endCell = toCell(end);

  const isBlocked = (cell) => {
    const p = toPoint(cell);
    return obstacles.some(rect => _pointInRect(p, rect));
  };

  const h = (a, b) => Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
  const open = [{ cell: startCell, f: h(startCell, endCell), g: 0 }];
  const cameFrom = new Map();
  const gScore = new Map([[key(startCell), 0]]);
  const closed = new Set();

  while (open.length) {
    open.sort((a, b) => a.f - b.f);
    const current = open.shift();
    const ck = key(current.cell);
    if (closed.has(ck)) continue;
    closed.add(ck);

    if (current.cell.x === endCell.x && current.cell.y === endCell.y) {
      const cells = [current.cell];
      let k = ck;
      while (cameFrom.has(k)) {
        const prev = cameFrom.get(k);
        cells.push(prev);
        k = key(prev);
      }
      cells.reverse();
      return cells.map(toPoint);
    }

    const neighbors = [
      { x: current.cell.x + 1, y: current.cell.y },
      { x: current.cell.x - 1, y: current.cell.y },
      { x: current.cell.x, y: current.cell.y + 1 },
      { x: current.cell.x, y: current.cell.y - 1 },
    ];

    neighbors.forEach(next => {
      const p = toPoint(next);
      if (p.x < minX || p.x > maxX || p.y < minY || p.y > maxY) return;
      if (isBlocked(next)) return;

      const nk = key(next);
      const tentativeG = current.g + 1;
      const prevG = gScore.get(nk);
      if (prevG != null && tentativeG >= prevG) return;

      cameFrom.set(nk, current.cell);
      gScore.set(nk, tentativeG);
      open.push({ cell: next, g: tentativeG, f: tentativeG + h(next, endCell) });
    });
  }

  return null;
}

function _buildOrthogonalEdgeRoute({
  sourceRect,
  targetRect,
  srcSlot,
  srcCount,
  dstSlot,
  dstCount,
  obstacleRects,
  bounds,
}) {
  const slotOffset = (slot, total, step) => (total <= 1 ? 0 : (slot - (total - 1) / 2) * step);
  const yStart = sourceRect.cy + slotOffset(srcSlot, srcCount, 10);
  const yEnd = targetRect.cy + slotOffset(dstSlot, dstCount, 12);

  const start = { x: sourceRect.right + 2, y: yStart };
  const end = { x: targetRect.left - 2, y: yEnd };

  const mainRoute = _gridRouteOrthogonal(start, end, obstacleRects, bounds, 10);
  if (mainRoute?.length) {
    const route = _simplifyOrthogonalPolyline([start, ...mainRoute, end]);
    if (!obstacleRects.some(rect => _polylineIntersectsRect(route, rect))) return route;
  }

  // Fallback corridor routing above or below all nodes.
  const yTop = bounds.minY - 24;
  const yBottom = bounds.maxY + 24;
  const topRoute = _simplifyOrthogonalPolyline([
    start,
    { x: start.x + 20, y: start.y },
    { x: start.x + 20, y: yTop },
    { x: end.x - 20, y: yTop },
    { x: end.x - 20, y: end.y },
    end,
  ]);
  if (!obstacleRects.some(rect => _polylineIntersectsRect(topRoute, rect))) return topRoute;

  const bottomRoute = _simplifyOrthogonalPolyline([
    start,
    { x: start.x + 20, y: start.y },
    { x: start.x + 20, y: yBottom },
    { x: end.x - 20, y: yBottom },
    { x: end.x - 20, y: end.y },
    end,
  ]);
  return bottomRoute;
}

function _polylineToPathD(points) {
  if (!points.length) return '';
  return points.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
}

function _buildClassicEdgePath({ sourceRect, targetRect, srcSlot, srcCount, dstSlot, dstCount }) {
  const slotOffset = (slot, total, step) => (total <= 1 ? 0 : (slot - (total - 1) / 2) * step);
  const startX = sourceRect.right + 2;
  const startY = sourceRect.cy + slotOffset(srcSlot, srcCount, 9);
  const endX = targetRect.left - 2;
  const endY = targetRect.cy + slotOffset(dstSlot, dstCount, 10);
  return `M ${startX} ${startY} L ${endX} ${endY}`;
}

let _mapPreviewPanX = 0;
let _mapPreviewPanY = 0;
let _mapPreviewZoom = 1;
let _mapPreviewGraphState = null;
const _savedMapManualLayoutByMap = new Map();
const _layoutPersistTimersByMap = new Map();

function _cloneLayoutUnits(layout) {
  const out = {};
  Object.entries(layout || {}).forEach(([id, p]) => {
    const x = Number(p?.x);
    const y = Number(p?.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return;
    out[id] = { x, y };
  });
  return out;
}

function _schedulePersistMapLayout(mapName, nodePositions) {
  const key = String(mapName || '').trim();
  if (!key) return;

  const existing = _layoutPersistTimersByMap.get(key);
  if (existing) clearTimeout(existing);

  const layoutToSave = _cloneLayoutUnits(nodePositions);
  const timer = setTimeout(async () => {
    _layoutPersistTimersByMap.delete(key);
    try {
      await api(`/api/maps/${encodeURIComponent(key)}/layout`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_positions: layoutToSave }),
      });
    } catch {
      // Keep UI responsive even if persistence fails; map remains interactive.
    }
  }, 180);

  _layoutPersistTimersByMap.set(key, timer);
}

function _layoutUnitsToScreenPositions(layoutUnits, viewport) {
  const positions = {};
  Object.entries(layoutUnits || {}).forEach(([id, p]) => {
    positions[id] = {
      x: viewport.xPad + (Number(p.x) - viewport.minX) * viewport.xScale,
      y: (viewport.height / 2) - Number(p.y) * viewport.yScale,
    };
  });
  return positions;
}

function _screenPositionsToLayoutUnits(positions, viewport) {
  const layout = {};
  Object.entries(positions || {}).forEach(([id, p]) => {
    const x = Number(p?.x);
    const y = Number(p?.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return;
    layout[id] = {
      x: ((x - viewport.xPad) / viewport.xScale) + viewport.minX,
      y: ((viewport.height / 2) - y) / viewport.yScale,
    };
  });
  return layout;
}

function _renderEdgePathsFromState(state) {
  if (!state) return '';
  const { nodes, edges, positions, edgeTooltipBySourceId, nodeWidth, nodeHeight } = state;
  const halfW = nodeWidth / 2;
  const halfH = nodeHeight / 2;

  const outgoingByNode = new Map();
  const incomingByNode = new Map();
  edges.forEach(([src, dst], idx) => {
    if (!outgoingByNode.has(src)) outgoingByNode.set(src, []);
    if (!incomingByNode.has(dst)) incomingByNode.set(dst, []);
    outgoingByNode.get(src).push(idx);
    incomingByNode.get(dst).push(idx);
  });

  const nodeRects = new Map();
  Array.from(nodes.values()).forEach(node => {
    const p = positions[node.id];
    nodeRects.set(node.id, {
      left: p.x - halfW,
      right: p.x + halfW,
      top: p.y - halfH,
      bottom: p.y + halfH,
      cx: p.x,
      cy: p.y,
    });
  });

  return edges.map(([src, dst], edgeIdx) => {
    const sourceRect = nodeRects.get(src);
    const targetRect = nodeRects.get(dst);
    if (!sourceRect || !targetRect) return '';

    const srcEdges = outgoingByNode.get(src) || [edgeIdx];
    const dstEdges = incomingByNode.get(dst) || [edgeIdx];
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

    const tip = edgeTooltipBySourceId.get(src);
    const encodedTip = tip ? _escAttrMultiline(tip) : '';
    return `
      <path d="${pathD}" fill="none" stroke="#4a5568" stroke-width="2" marker-end="url(#arrow)">${tip ? `<title>${_esc(tip)}</title>` : ''}</path>
      <path d="${pathD}" fill="none" stroke="transparent" stroke-width="14" data-tip="${encodedTip}"></path>
    `;
  }).join('');
}

function _renderInteractiveMapEdges() {
  if (!_mapPreviewGraphState) return;
  const edgesGroup = document.getElementById('map-preview-edges');
  if (!edgesGroup) return;
  edgesGroup.innerHTML = _renderEdgePathsFromState(_mapPreviewGraphState);
}

function _renderInteractiveMapNodesIntoDom() {
  if (!_mapPreviewGraphState) return;
  const nodesGroup = document.getElementById('map-preview-nodes');
  if (!nodesGroup) return;
  nodesGroup.innerHTML = _renderInteractiveMapNodes();
}

function _renderInteractiveMapNodes() {
  if (!_mapPreviewGraphState) return '';
  const { nodes, positions, nodeTooltipById, nodeWidth, nodeHeight } = _mapPreviewGraphState;
  const halfW = nodeWidth / 2;
  const halfH = nodeHeight / 2;
  return Array.from(nodes.values()).map(node => {
    const p = positions[node.id];
    const fill = node.type === 'plant' ? '#c6f6d5' : (node.type === 'storage' ? '#bee3f8' : '#feebc8');
    const stroke = node.type === 'plant' ? '#276749' : (node.type === 'storage' ? '#2c5282' : '#c05621');
    const tip = nodeTooltipById.get(node.id);
    const encodedTip = tip ? _escAttrMultiline(tip) : '';
    return `
      <g data-node-id="${_esc(node.id)}" transform="translate(${p.x} ${p.y})" style="cursor:move">
        <rect x="${-halfW}" y="${-halfH}" rx="8" ry="8" width="${nodeWidth}" height="${nodeHeight}" fill="${fill}" stroke="${stroke}" stroke-width="2" ${tip ? `data-tip="${encodedTip}"` : ''}>${tip ? `<title>${_esc(tip)}</title>` : ''}</rect>
        <text x="0" y="5" text-anchor="middle" font-size="12" fill="#2d3748" style="pointer-events:none">${_esc(node.label)}</text>
      </g>
    `;
  }).join('');
}

function _applyMapPreviewTransform() {
  const viewport = document.getElementById('map-preview-viewport');
  if (!viewport) return;
  viewport.setAttribute('transform', `translate(${_mapPreviewPanX} ${_mapPreviewPanY}) scale(${_mapPreviewZoom})`);
}

function resetMapPreviewView() {
  _mapPreviewPanX = 0;
  _mapPreviewPanY = 0;
  _mapPreviewZoom = 1;
  _applyMapPreviewTransform();
}

function resetMapPreviewNodes() {
  if (!_mapPreviewGraphState?.autoLayoutUnits || !_mapPreviewGraphState?.viewport) return;
  const autoLayout = _cloneLayoutUnits(_mapPreviewGraphState.autoLayoutUnits);
  const nextPositions = _layoutUnitsToScreenPositions(autoLayout, _mapPreviewGraphState.viewport);
  _mapPreviewGraphState.layoutUnits = autoLayout;
  _mapPreviewGraphState.positions = nextPositions;
  _mapPreviewGraphState.originalPositions = Object.fromEntries(
    Object.entries(nextPositions).map(([id, p]) => [id, { x: p.x, y: p.y }]),
  );

  _savedMapManualLayoutByMap.delete(_mapPreviewGraphState.mapName);
  _savedMapLastLayoutByMap.set(_mapPreviewGraphState.mapName, autoLayout);
  _schedulePersistMapLayout(_mapPreviewGraphState.mapName, {});

  _renderInteractiveMapNodesIntoDom();
  _renderInteractiveMapEdges();
}

function enableMapPreviewInteractions() {
  const stage = document.getElementById('map-preview-stage');
  const svg = document.getElementById('map-preview-svg');
  const tooltip = document.getElementById('map-hover-tooltip');
  if (!stage || !svg || !tooltip) return;

  resetMapPreviewView();

  let dragging = false;
  let startClientX = 0;
  let startClientY = 0;
  let startPanX = 0;
  let startPanY = 0;
  let nodeDragging = null;

  svg.addEventListener('wheel', (event) => {
    event.preventDefault();
    const factor = event.deltaY < 0 ? 1.1 : 0.9;
    _mapPreviewZoom = Math.max(0.6, Math.min(3.0, _mapPreviewZoom * factor));
    _applyMapPreviewTransform();
  }, { passive: false });

  svg.addEventListener('mousedown', (event) => {
    if (event.button !== 0) return;

    const nodeGroup = event.target?.closest?.('[data-node-id]');
    if (nodeGroup) {
      const nodeId = nodeGroup.getAttribute('data-node-id');
      if (_mapPreviewGraphState?.positions?.[nodeId]) {
        nodeDragging = {
          nodeId,
          startClientX: event.clientX,
          startClientY: event.clientY,
          startX: _mapPreviewGraphState.positions[nodeId].x,
          startY: _mapPreviewGraphState.positions[nodeId].y,
          moved: false,
        };
        svg.style.cursor = 'grabbing';
        event.preventDefault();
        return;
      }
    }

    dragging = true;
    startClientX = event.clientX;
    startClientY = event.clientY;
    startPanX = _mapPreviewPanX;
    startPanY = _mapPreviewPanY;
    svg.style.cursor = 'grabbing';
  });

  window.addEventListener('mousemove', (event) => {
    const hit = event.target?.closest?.('[data-tip]');
    if (hit && stage.contains(hit)) {
      const tip = hit.getAttribute('data-tip') || '';
      tooltip.textContent = tip;
      tooltip.style.display = 'block';
      const rect = stage.getBoundingClientRect();
      tooltip.style.left = `${Math.min(rect.width - 16, event.clientX - rect.left + 12)}px`;
      tooltip.style.top = `${Math.min(rect.height - 16, event.clientY - rect.top + 12)}px`;
    } else {
      tooltip.style.display = 'none';
    }

    if (nodeDragging) {
      const vb = svg.viewBox?.baseVal;
      if (!vb || !svg.clientWidth || !svg.clientHeight) return;
      const dx = event.clientX - nodeDragging.startClientX;
      const dy = event.clientY - nodeDragging.startClientY;
      if (!nodeDragging.moved && (Math.abs(dx) > 3 || Math.abs(dy) > 3)) {
        nodeDragging.moved = true;
      }
      const scaleX = vb.width / svg.clientWidth;
      const scaleY = vb.height / svg.clientHeight;
      const nx = nodeDragging.startX + (dx * scaleX) / _mapPreviewZoom;
      const ny = nodeDragging.startY + (dy * scaleY) / _mapPreviewZoom;

      _mapPreviewGraphState.positions[nodeDragging.nodeId] = { x: nx, y: ny };

      const nodeEl = svg.querySelector(`[data-node-id="${CSS.escape(nodeDragging.nodeId)}"]`);
      if (nodeEl) nodeEl.setAttribute('transform', `translate(${nx} ${ny})`);
      _renderInteractiveMapEdges();
      return;
    }

    if (!dragging) return;
    const vb = svg.viewBox?.baseVal;
    if (!vb || !svg.clientWidth || !svg.clientHeight) return;
    const dx = event.clientX - startClientX;
    const dy = event.clientY - startClientY;
    const scaleX = vb.width / svg.clientWidth;
    const scaleY = vb.height / svg.clientHeight;
    _mapPreviewPanX = startPanX + (dx * scaleX) / _mapPreviewZoom;
    _mapPreviewPanY = startPanY + (dy * scaleY) / _mapPreviewZoom;
    _applyMapPreviewTransform();
  });

  window.addEventListener('mouseup', () => {
    if (nodeDragging && _mapPreviewGraphState?.viewport) {
      if (nodeDragging.moved) {
        const layoutUnits = _screenPositionsToLayoutUnits(_mapPreviewGraphState.positions, _mapPreviewGraphState.viewport);
        _mapPreviewGraphState.layoutUnits = layoutUnits;
        _savedMapManualLayoutByMap.set(_mapPreviewGraphState.mapName, _cloneLayoutUnits(layoutUnits));
        _savedMapLastLayoutByMap.set(_mapPreviewGraphState.mapName, _cloneLayoutUnits(layoutUnits));
        _schedulePersistMapLayout(_mapPreviewGraphState.mapName, layoutUnits);
      } else {
        void openConfigEditorForMapNode(nodeDragging.nodeId);
      }
    }
    nodeDragging = null;
    dragging = false;
    svg.style.cursor = 'grab';
  });

  stage.addEventListener('mouseleave', () => {
    tooltip.style.display = 'none';
  });

  svg.style.cursor = 'grab';
}

function renderMapPreview(
  mapName,
  mapData,
  plantInputs = [],
  simulationRows = null,
  titlePrefix = 'Previewing saved map',
  options = {},
) {
  const suppressPanelTitle = Boolean(options?.suppressPanelTitle);
  if (!suppressPanelTitle) setMapPanelTitle('Interactive Pipeline Map');
  const interactive = Boolean(options?.interactive);
  const placeholder = options?.placeholderEl || document.getElementById('map-placeholder');
  const frame = document.getElementById('map-frame');
  if (frame) {
    frame.style.display = 'none';
    frame.src = 'about:blank';
  }
  if (!placeholder) return;

  const defs = Array.isArray(mapData?.merge_definitions) ? mapData.merge_definitions : [];
  const selectedPlantIndexes = _extractPlantIndexesFromMap(mapData, plantInputs.length);

  const nodes = new Map();
  const edges = [];
  const addNode = (id, label, type, meta = {}) => {
    if (!nodes.has(id)) {
      nodes.set(id, { id, label, type, ...meta });
      return;
    }
    Object.assign(nodes.get(id), meta);
  };

  defs.forEach((def, mergeIdx) => {
    const mergeId = `merge:${def.merge_name}`;
    addNode(mergeId, def.merge_name, 'merge', { mergeOrder: mergeIdx });
    (def.sources || []).forEach(src => {
      const [srcType, srcValue] = src;
      if (srcType === 'plant') {
        const id = `plant:${srcValue}`;
        addNode(id, _plantLabelByIndex(plantInputs, srcValue), 'plant', { plantIndex: Number(srcValue) });
        edges.push([id, mergeId]);
      } else {
        const id = `merge:${srcValue}`;
        addNode(id, String(srcValue), 'merge');
        edges.push([id, mergeId]);
      }
    });
  });

  if (!defs.length) {
    selectedPlantIndexes.forEach(plantIndex => {
      const id = `plant:${plantIndex}`;
      addNode(id, _plantLabelByIndex(plantInputs, plantIndex), 'plant', { plantIndex });
    });
  }

  const storageName = String(mapData?.storage_name || 'Storage').trim() || 'Storage';
  const storageId = `storage:${storageName}`;
  addNode(storageId, storageName, 'storage');

  const nodeTooltipById = new Map();
  const edgeTooltipBySourceId = new Map();
  if (Array.isArray(simulationRows)) {
    simulationRows.forEach(row => {
      const srcType = String(row?.source_type || '');
      const srcName = row?.source_name;
      let nodeId = null;
      if (srcType === 'plant') nodeId = `plant:${srcName}`;
      else if (srcType === 'merge') nodeId = `merge:${srcName}`;
      else if (srcType === 'storage') nodeId = `storage:${srcName}`;
      if (!nodeId) return;

      const metaLines = [
        `${srcType}: ${String(_displaySourceName(row, plantInputs))}`,
        `phase: ${row?.stream_phase ?? '—'}`,
        `temperature (°C): ${fmtCelsiusFromKelvin(row?.temperature_kelvin)}`,
        `flow (kg/hr): ${row?.total_massflow ?? '—'}`,
      ];
      const inLines = _formatTooltipRows('Inlet concentration', row?.tocomo_input || {});
      nodeTooltipById.set(nodeId, `${metaLines.join('\n')}\n\n${inLines}`);

      const edgeTooltip = _formatTooltipRows('Formation of corrosive contaminants', row?.final || {});
      if (edgeTooltip && edgeTooltip !== 'Formation of corrosive contaminants') {
        edgeTooltipBySourceId.set(nodeId, edgeTooltip);
      }
    });
  }

  // Connect storage from all terminal nodes (nodes with no outgoing edge),
  // so storage is always represented even in edge-case map definitions.
  const outgoing = new Set(edges.map(([src]) => src));
  Array.from(nodes.values())
    .filter(node => node.type !== 'storage' && !outgoing.has(node.id))
    .forEach(node => edges.push([node.id, storageId]));

  const previousLayout = _savedMapLastLayoutByMap.get(mapName) || null;
  const computedLayoutUnits = _computeOverlapAwareLayout(
    Array.from(nodes.values()),
    edges,
    previousLayout,
  );
  const autoLayoutUnits = _cloneLayoutUnits(computedLayoutUnits);
  const persistedLayout = _savedMapManualLayoutByMap.get(mapName) || _cloneLayoutUnits(mapData?.node_positions || {});
  const layoutUnits = _cloneLayoutUnits(computedLayoutUnits);
  Object.entries(persistedLayout || {}).forEach(([id, p]) => {
    if (!layoutUnits[id]) return;
    layoutUnits[id] = { x: Number(p.x), y: Number(p.y) };
  });

  _savedMapLastLayoutByMap.set(mapName, _cloneLayoutUnits(layoutUnits));
  if (Object.keys(persistedLayout || {}).length) {
    _savedMapManualLayoutByMap.set(mapName, _cloneLayoutUnits(layoutUnits));
  } else {
    _savedMapManualLayoutByMap.delete(mapName);
  }

  const xs = Object.values(layoutUnits).map(p => p.x);
  const ys = Object.values(layoutUnits).map(p => p.y);
  const minX = xs.length ? Math.min(...xs) : 0;
  const maxX = xs.length ? Math.max(...xs) : 0;
  const maxAbsY = ys.length ? Math.max(...ys.map(y => Math.abs(y))) : 0;

  const xScale = 180;
  const yScale = 110;
  const xPad = 120;
  const yPad = 80;
  const width = Math.max(780, (maxX - minX) * xScale + xPad * 2 + 80);
  const height = Math.max(520, (maxAbsY * 2) * yScale + yPad * 2 + 80);
  const positions = {};

  Object.entries(layoutUnits).forEach(([id, p]) => {
    positions[id] = {
      x: xPad + (p.x - minX) * xScale,
      y: (height / 2) - p.y * yScale,
    };
  });

  _mapPreviewGraphState = {
    mapName,
    nodes,
    edges,
    layoutUnits: _cloneLayoutUnits(layoutUnits),
    autoLayoutUnits,
    positions,
    originalPositions: Object.fromEntries(Object.entries(positions).map(([id, p]) => [id, { x: p.x, y: p.y }])),
    viewport: {
      xScale,
      yScale,
      xPad,
      minX,
      height,
    },
    nodeTooltipById,
    edgeTooltipBySourceId,
    nodeWidth: 76,
    nodeHeight: 40,
  };

  const edgeSvg = _renderEdgePathsFromState(_mapPreviewGraphState);
  const nodeSvg = _renderInteractiveMapNodes();

  placeholder.className = '';
  const svgContent = interactive
    ? `
      <div class="map-preview-controls">
        <button class="btn btn-sm" type="button" onclick="resetMapPreviewView()">Reset View</button>
        <button class="btn btn-sm" type="button" onclick="resetMapPreviewNodes()">Reset Nodes</button>
      </div>
      <div class="map-preview-stage" id="map-preview-stage">
        <svg class="map-preview-svg" id="map-preview-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Pipeline map preview">
          <defs>
            <marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L10,4 L0,8 z" fill="#4a5568"></path>
            </marker>
          </defs>
          <g id="map-preview-viewport">
            <g id="map-preview-edges">${edgeSvg}</g>
            <g id="map-preview-nodes">${nodeSvg}</g>
          </g>
        </svg>
        <div class="map-hover-tooltip" id="map-hover-tooltip"></div>
      </div>
    `
    : `
      <svg class="map-preview-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Pipeline map preview">
        <defs>
          <marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L10,4 L0,8 z" fill="#4a5568"></path>
          </marker>
        </defs>
        ${edgeSvg}
        ${nodeSvg}
      </svg>
    `;

  placeholder.innerHTML = `
    <div class="map-preview-wrap">
      <div class="map-preview-title">${_esc(titlePrefix)}: <strong>${_esc(mapName)}</strong></div>
      ${svgContent}
    </div>
  `;
  placeholder.style.display = 'block';
  if (interactive) enableMapPreviewInteractions();
}

async function previewSelectedMap() {
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
  } catch (e) {
    showMapPreviewMessage(`Could not load map preview: ${e.message}`);
  }
}

