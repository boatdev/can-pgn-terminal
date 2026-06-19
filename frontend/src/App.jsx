import { useState, useEffect, useCallback, useRef, Fragment, useMemo } from 'react';
import { PGN_NAMES } from './resources';

const API_BASE = '/api';
const RAW_POLL_INTERVAL = 1000;
const VALUES_POLL_INTERVAL = 2000;
const DEV_POLL_INTERVAL = 3000;

// ---- RawRow ----
function RawRow({ msg, idx, formatTime, formatValue, formatUnit, sourceLabel }) {
  const [expanded, setExpanded] = useState(false);
  const fields = msg.pgn_fields;
  const isNewFormat = Array.isArray(fields);
  const hasFields = fields && (isNewFormat ? fields.length > 0 : Object.keys(fields).length > 0);

  return (
    <Fragment>
      <tr
        className={`raw-main-row ${hasFields ? 'clickable' : ''}`}
        onClick={() => hasFields && setExpanded(!expanded)}
      >
        <td className="cell-num">{idx}</td>
        <td className="cell-time">{formatTime(msg.timestamp)}</td>
        <td className="cell-id">{sourceLabel(msg.source_id)}</td>
        <td className="cell-pgn">{msg.pgn}</td>
        <td className="cell-num">{msg.priority}</td>
        <td>
          {msg.description || '—'}
          {hasFields && <span className="expand-icon">{expanded ? ' ▾' : ' ▸'}</span>}
        </td>
        <td className="cell-raw-hex">{msg.raw_data}</td>
      </tr>
      {expanded && hasFields && (
        <tr className="raw-fields-row">
          <td colSpan={7} className="raw-fields-cell">
            <div className="pgn-fields">
              <div className="pgn-fields-title">Decoded PGN Fields:</div>
              <table className="pgn-fields-table">
                <thead><tr><th>Field</th><th>Value</th><th>Unit</th></tr></thead>
                <tbody>
                  {isNewFormat
                    ? fields.map((f) => (
                        <tr key={f.key}>
                          <td className="pgn-field-name">{f.name || f.key}</td>
                          <td className="pgn-field-value">{formatValue(f.value, f.unit)}</td>
                          <td className="pgn-field-unit">{formatUnit(f.unit)}</td>
                        </tr>
                      ))
                    : Object.entries(fields).map(([key, val]) => (
                        <tr key={key}>
                          <td className="pgn-field-name">{key}</td>
                          <td className="pgn-field-value">{formatValue(val, '')}</td>
                          <td className="pgn-field-unit"></td>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>
          </td>
        </tr>
      )}
    </Fragment>
  );
}

// ---- App ----
export default function App() {
  // --- data ---
  const [devices, setDevices] = useState([]);
  const [total, setTotal] = useState(0);
  const [mode, setMode] = useState('—');
  const [canConnected, setCanConnected] = useState(false);
  const [canError, setCanError] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rawMessages, setRawMessages] = useState([]);
  const [rawPaused, setRawPaused] = useState(false);
  const [values, setValues] = useState([]);

  const lastRawTs = useRef(null);

  // --- navigation ---
  // null = source list, number = viewing PGNs of that source
  const [selectedSourceId, setSelectedSourceId] = useState(null);
  // null = no PGN selected, { source_id, pgn, description } = detail view
  const [selectedPgn, setSelectedPgn] = useState(null);

  // ---- fetch ----
  const fetchDevices = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/devices`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setDevices(data.devices ?? []);
      setTotal(data.total ?? 0);
      setMode(data.mode ?? '—');
      setCanConnected(data.can_connected ?? false);
      setCanError(data.can_error ?? '');
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchRaw = useCallback(async () => {
    if (rawPaused) return;
    try {
      const since = lastRawTs.current ? `?since=${lastRawTs.current}` : '';
      const resp = await fetch(`${API_BASE}/raw-messages${since}`);
      if (!resp.ok) return;
      const data = await resp.json();
      if (data.messages && data.messages.length > 0) {
        setRawMessages((prev) => {
          const combined = [...prev, ...data.messages];
          return combined.length > 500 ? combined.slice(combined.length - 500) : combined;
        });
        lastRawTs.current = data.messages[data.messages.length - 1].timestamp;
      }
    } catch {}
  }, [rawPaused]);

  const fetchValues = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/values`);
      if (!resp.ok) return;
      const data = await resp.json();
      if (Array.isArray(data)) setValues(data);
    } catch {}
  }, []);

  useEffect(() => {
    fetchDevices();
    fetchRaw();
    fetchValues();
    const d = setInterval(fetchDevices, DEV_POLL_INTERVAL);
    const r = setInterval(fetchRaw, RAW_POLL_INTERVAL);
    const v = setInterval(fetchValues, VALUES_POLL_INTERVAL);
    return () => { clearInterval(d); clearInterval(r); clearInterval(v); };
  }, [fetchDevices, fetchRaw, fetchValues]);

  const formatValue = (value, unit) => {
    if (unit === 'rad' && typeof value === 'number') {
      return `${(value * (180 / Math.PI)).toFixed(1)}°`;
    }
    if (typeof value === 'object' && value !== null) return JSON.stringify(value, null, 2);
    return String(value ?? '—');
  };

  const formatUnit = (unit) => (unit === 'rad' ? '°' : unit || '');

  const formatTime = (ts) => {
    if (!ts) return '—';
    return new Date(ts * 1000).toLocaleTimeString('en-US', { hour12: false });
  };

  const elapsed = (ts) => {
    if (!ts) return '—';
    const s = Math.floor(Date.now() / 1000 - ts);
    if (s < 60) return `${s}s`;
    if (s < 3600) return `${Math.floor(s / 60)}m`;
    return `${Math.floor(s / 3600)}h`;
  };

  // ---- Build a lookup: source_id → manufacturer name from devices ----
  const deviceManufacturers = useMemo(() => {
    const map = {};
    for (const d of devices) {
      if (d.manufacturer) {
        map[d.source_id] = d.manufacturer;
      }
    }
    return map;
  }, [devices]);

  /** Return human-readable label for a source_id, falling back to "Source N". */
  const sourceLabel = useCallback(
    (id) => {
      const mfg = deviceManufacturers[id];
      return mfg ? `${mfg} (${id})` : `Source ${id}`;
    },
    [deviceManufacturers],
  );

  // ---- PGN groups: unique (source_id, pgn) pairs from values + rawMessages ----
  const pgnGroups = useMemo(() => {
    const seen = new Set();
    const items = [];

    // Primary: from decoded values
    for (const v of values) {
      const key = `${v.source_id}:${v.pgn}`;
      if (!seen.has(key)) {
        seen.add(key);
        const rawMatch = rawMessages.find(
          (m) => m.source_id === v.source_id && m.pgn === v.pgn
        );
        items.push({
          source_id: v.source_id,
          pgn: v.pgn,
          description: rawMatch?.description || PGN_NAMES[v.pgn] || '',
        });
      }
    }

    // Supplement: raw messages that don't have decoded values yet
    for (const m of rawMessages) {
      const key = `${m.source_id}:${m.pgn}`;
      if (!seen.has(key)) {
        seen.add(key);
        items.push({
          source_id: m.source_id,
          pgn: m.pgn,
          description: m.description || PGN_NAMES[m.pgn] || '',
        });
      }
    }

    // Group by source_id and sort
    const map = {};
    for (const item of items) {
      if (!map[item.source_id]) map[item.source_id] = [];
      map[item.source_id].push(item);
    }
    for (const key of Object.keys(map)) {
      map[key].sort((a, b) => a.pgn - b.pgn);
    }
    return Object.entries(map).sort((a, b) => Number(a[0]) - Number(b[0]));
  }, [rawMessages, values]);

  // ---- Source table: merge devices metadata with PGN counts ----
  const sourceTable = useMemo(() => {
    // Build PGN count map from pgnGroups
    const pgnCount = {};
    for (const [sourceId, pgns] of pgnGroups) {
      pgnCount[Number(sourceId)] = pgns.length;
    }

    // Collect all known source IDs
    const ids = new Set();
    for (const d of devices) ids.add(d.source_id);
    for (const sid of Object.keys(pgnCount)) ids.add(Number(sid));

    const rows = [];
    for (const id of ids) {
      const dev = devices.find((d) => d.source_id === id);
      const count = pgnCount[id] || 0;
      // Skip sources with no PGNs and no device info
      if (count === 0 && !dev) continue;
      rows.push({
        source_id: id,
        manufacturer: dev?.manufacturer || '',
        device_class: dev?.device_class || '',
        device_function: dev?.device_function || '',
        pgn_count: count,
      });
    }
    rows.sort((a, b) => a.source_id - b.source_id);
    return rows;
  }, [devices, pgnGroups]);

  // ---- Filtered PGNs for selected source ----
  const filteredPgns = useMemo(() => {
    if (selectedSourceId === null) return [];
    const entry = pgnGroups.find(([sid]) => Number(sid) === selectedSourceId);
    return entry ? entry[1] : [];
  }, [pgnGroups, selectedSourceId]);

  // ---- Detail data for selected PGN ----
  const selectedValues = useMemo(() => {
    if (!selectedPgn) return null;
    return values.find(
      (v) => v.source_id === selectedPgn.source_id && v.pgn === selectedPgn.pgn
    ) || null;
  }, [values, selectedPgn]);

  const selectedRaw = useMemo(() => {
    if (!selectedPgn) return [];
    return rawMessages
      .filter(
        (m) =>
          m.source_id === selectedPgn.source_id && m.pgn === selectedPgn.pgn
      )
      .slice(-200);
  }, [rawMessages, selectedPgn]);

  // ---- Raw pause handler ----
  const handlePauseToggle = () => {
    if (!rawPaused) {
      setRawPaused(true);
    } else {
      lastRawTs.current = null;
      setRawMessages([]);
      setRawPaused(false);
    }
  };

  // ---- Navigation: go back from PGN detail to source PGN list ----
  const handleBackToSource = () => {
    setSelectedPgn(null);
  };

  // ---- Navigation: go back from source PGN list to source selection ----
  const handleBackToSources = () => {
    setSelectedSourceId(null);
    setSelectedPgn(null);
  };

  // Determine current view level
  const showSourceList = selectedSourceId === null && !selectedPgn;
  const showSourcePgns = selectedSourceId !== null && !selectedPgn;
  const showPgnDetail = selectedPgn !== null;

  return (
    <div className="app">
      <header className="header">
        <h1>🛥️ NMEA 2000 Web Terminal</h1>
        <div className="status-bar">
          <span className={`badge ${canConnected ? 'badge-live' : 'badge-disconnected'}`}>
            {canConnected ? '🟢 CAN Connected' : '🔴 CAN Disconnected'}
          </span>
          <span className="total">Sources: {pgnGroups.length} | Devices: {total}</span>
        </div>
      </header>

      {loading && <div className="loader">Loading...</div>}
      {error && <div className="error">Server connection error: {error}</div>}

      {!canConnected && !loading && !showPgnDetail && (
        <div className="can-error">
          <h2>⚠️ Device Unavailable</h2>
          <p>{canError || 'CAN bus connection is not established. Check connection and settings.'}</p>
        </div>
      )}

      {/* ================================================================
          LEVEL 1: Source list — select a source to see its PGNs
          ================================================================ */}
      {!loading && !error && showSourceList && (
        <main>
          <div className="section-header">
            <h2 className="section-title">📡 Sources</h2>
            <span className="section-subtitle">
              Select a source to see all its PGNs
            </span>
          </div>
          {sourceTable.length === 0 && canConnected && (
            <div className="empty">No sources detected. Waiting for CAN messages...</div>
          )}
          {sourceTable.length === 0 && !canConnected && (
            <div className="empty">No sources available.</div>
          )}
          {sourceTable.length > 0 && (
            <div className="table-wrapper">
              <table className="devices-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Manufacturer</th>
                    <th>Class</th>
                    <th>Function</th>
                    <th>PGNs</th>
                  </tr>
                </thead>
                <tbody>
                  {sourceTable.map((row) => (
                    <tr
                      key={row.source_id}
                      className="device-row-clickable"
                      onClick={() => setSelectedSourceId(row.source_id)}
                    >
                      <td className="cell-id">{row.source_id}</td>
                      <td>{row.manufacturer || '—'}</td>
                      <td>{row.device_class || '—'}</td>
                      <td>{row.device_function || '—'}</td>
                      <td className="cell-num">{row.pgn_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </main>
      )}

      {/* ================================================================
          LEVEL 2: PGN list for selected source
          ================================================================ */}
      {!loading && !error && showSourcePgns && (
        <main>
          <div className="device-detail-bar">
            <button className="tab-btn back-btn" onClick={handleBackToSources}>
              ← All Sources
            </button>
            <div className="device-detail-info">
              <span className="cell-id">{sourceLabel(selectedSourceId)}</span>
              <span className="detail-sep">|</span>
              <span>{filteredPgns.length} PGN{filteredPgns.length !== 1 ? 's' : ''}</span>
            </div>
          </div>

          {filteredPgns.length === 0 ? (
            <div className="empty">No PGN data for this source. Waiting for messages...</div>
          ) : (
            <div className="table-wrapper">
              <table className="devices-table pgn-table">
                <thead>
                  <tr>
                    <th>PGN</th>
                    <th>Description</th>
                    <th>PGN Name</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPgns.map((item) => (
                    <tr
                      key={`${item.source_id}:${item.pgn}`}
                      className="pgn-row-clickable"
                      onClick={() => setSelectedPgn(item)}
                    >
                      <td className="cell-pgn">{item.pgn}</td>
                      <td>{item.description || '—'}</td>
                      <td>{PGN_NAMES[item.pgn] || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </main>
      )}

      {/* ================================================================
          LEVEL 3: PGN Detail (Value + RAW)
          ================================================================ */}
      {!loading && !error && showPgnDetail && selectedPgn && (
        <>
          <div className="device-detail-bar">
            <button className="tab-btn back-btn" onClick={handleBackToSources}>
              ← All Sources
            </button>
            <div className="device-detail-info">
              <span className="crumb" onClick={handleBackToSource}>
                {sourceLabel(selectedPgn.source_id)}
              </span>
              <span className="detail-sep">▸</span>
              <span className="cell-pgn">PGN {selectedPgn.pgn}</span>
              <span className="detail-sep">▸</span>
              <span>{selectedPgn.description || PGN_NAMES[selectedPgn.pgn] || 'Unknown'}</span>
            </div>
          </div>

          <main className="pgn-detail-main">
            {/* ---- Values section ---- */}
            <section className="pgn-detail-section">
              <h2 className="pgn-detail-section-title">📊 Value</h2>
              {!selectedValues || !selectedValues.fields || selectedValues.fields.length === 0 ? (
                <div className="empty">No decoded values for this PGN</div>
              ) : (
                <div className="table-wrapper">
                  <table className="pgn-fields-table">
                    <thead>
                      <tr>
                        <th>Parameter</th>
                        <th>Value</th>
                        <th>Unit</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedValues.fields.map((f) => (
                        <tr key={f.key}>
                          <td className="pgn-field-name">{f.name || f.key}</td>
                          <td className="pgn-field-value">{formatValue(f.value, f.unit)}</td>
                          <td className="pgn-field-unit">{formatUnit(f.unit)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* ---- RAW section ---- */}
            <section className="pgn-detail-section">
              <h2 className="pgn-detail-section-title">📋 Raw Messages</h2>
              <div className="raw-controls">
                <button className="tab-btn" onClick={handlePauseToggle}>
                  {rawPaused ? '▶ Resume' : '⏸ Pause'}
                </button>
                <span className="raw-info">
                  Messages for PGN {selectedPgn.pgn}: {selectedRaw.length}
                  {rawPaused ? ' | Stream Paused' : ' | ▶ Stream Active'}
                </span>
              </div>
              <div className="table-wrapper">
                <table className="devices-table raw-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Time</th>
                      <th>Source</th>
                      <th>PGN</th>
                      <th>Pri</th>
                      <th>Description</th>
                      <th>Raw Data (hex)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedRaw.length === 0 && (
                      <tr>
                        <td colSpan={7} className="empty-cell">
                          No raw messages for this PGN. Waiting for data...
                        </td>
                      </tr>
                    )}
                    {[...selectedRaw].reverse().map((m, idx) => (
                      <RawRow
                        key={`${m.timestamp}-${idx}`}
                        msg={m}
                        idx={selectedRaw.length - idx}
                        formatTime={formatTime}
                        formatValue={formatValue}
                        formatUnit={formatUnit}
                        sourceLabel={sourceLabel}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </main>
        </>
      )}
    </div>
  );
}