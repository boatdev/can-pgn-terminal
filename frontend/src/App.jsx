import { useState, useEffect, useCallback, useRef, Fragment } from 'react';

const API_BASE = '/api';
const RAW_POLL_INTERVAL = 1000;
const VALUES_POLL_INTERVAL = 2000;
const DEV_POLL_INTERVAL = 3000;

// ---- PGN names ----
const PGN_NAMES = {
  126992: 'System Time',
  127245: 'Rudder',
  127250: 'Vessel Heading',
  127251: 'Rate of Turn',
  127488: 'Engine Parameters',
  127508: 'Battery Status',
  128259: 'Speed, Water Ref.',
  128267: 'Water Depth',
  129025: 'Position',
  129026: 'COG & SOG',
  129029: 'GNSS Position',
  129033: 'Time & Date',
  129038: 'AIS Position',
  130306: 'Wind Data',
  130311: 'Environmental',
};

// ---- RawRow ----
function RawRow({ msg, idx, formatTime, formatValue, formatUnit }) {
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
        <td className="cell-id">{msg.source_id}</td>
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
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [deviceSubTab, setDeviceSubTab] = useState('values');

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

  const handlePauseToggle = () => {
    if (!rawPaused) { setRawPaused(true); }
    else { lastRawTs.current = null; setRawMessages([]); setRawPaused(false); }
  };

  const deviceInfo = devices.find((d) => d.source_id === selectedDevice);

  const deviceValues = values
    .filter((v) => v.source_id === selectedDevice)
    .filter((v) => PGN_NAMES[v.pgn])
    .sort((a, b) => a.pgn - b.pgn);

  const deviceRaw = rawMessages
    .filter((m) => m.source_id === selectedDevice)
    .slice(-200);

  const showDeviceList = !selectedDevice;

  return (
    <div className="app">
      <header className="header">
        <h1>🛥️ NMEA 2000 Web Terminal</h1>
        <div className="status-bar">
          <span className={`badge ${canConnected ? 'badge-live' : 'badge-disconnected'}`}>
            {canConnected ? '🔴 CAN Connected' : '🔴 CAN Disconnected'}
          </span>
          <span className="total">Devices: {total}</span>
        </div>
      </header>

      {loading && <div className="loader">Loading...</div>}
      {error && <div className="error">Server connection error: {error}</div>}

      {!canConnected && !loading && showDeviceList && (
        <div className="can-error">
          <h2>⚠️ Device Unavailable</h2>
          <p>{canError || 'CAN bus connection is not established. Check connection and settings.'}</p>
        </div>
      )}

      {!loading && !error && showDeviceList && (
        <main>
          {devices.length === 0 && canConnected && <div className="empty">No devices detected</div>}
          {devices.length > 0 && (
            <div className="table-wrapper">
              <table className="devices-table">
                <thead>
                  <tr>
                    <th>Source ID</th>
                    <th>PGN</th>
                    <th>Description</th>
                    <th>Manufacturer</th>
                    <th>Class</th>
                    <th>Function</th>
                    <th>Messages</th>
                    <th>First Seen</th>
                    <th>Last Activity</th>
                  </tr>
                </thead>
                <tbody>
                  {devices.map((d) => (
                    <tr
                      key={d.source_id}
                      className="device-row-clickable"
                      onClick={() => { setSelectedDevice(d.source_id); setDeviceSubTab('values'); }}
                    >
                      <td className="cell-id">{d.source_id}</td>
                      <td className="cell-pgn">{d.pgn}</td>
                      <td>{d.description}</td>
                      <td>{d.manufacturer || '—'}</td>
                      <td>{d.device_class || '—'}</td>
                      <td>{d.device_function || '—'}</td>
                      <td className="cell-num">{d.message_count}</td>
                      <td>{formatTime(d.first_seen)}</td>
                      <td>{formatTime(d.last_seen)} <span className="elapsed"> {elapsed(d.last_seen)} ago</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </main>
      )}

      {!loading && !error && !showDeviceList && deviceInfo && (
        <>
          <div className="device-detail-bar">
            <button className="tab-btn back-btn" onClick={() => { setSelectedDevice(null); }}>
              ← All Devices
            </button>
            <div className="device-detail-info">
              <span className="cell-id">Source {deviceInfo.source_id}</span>
              <span className="detail-sep">|</span>
              <span className="cell-pgn">PGN {deviceInfo.pgn}</span>
              <span className="detail-sep">|</span>
              <span>{deviceInfo.description}</span>
              {deviceInfo.manufacturer && (
                <><span className="detail-sep">|</span><span>{deviceInfo.manufacturer}</span></>
              )}
              <span className="detail-sep">|</span>
              <span className="detail-msg-count">{deviceInfo.message_count} msgs</span>
            </div>
          </div>

          <nav className="tabs">
            <button
              className={`tab-btn ${deviceSubTab === 'values' ? 'active' : ''}`}
              onClick={() => setDeviceSubTab('values')}
            >
              📊 Values
              {deviceValues.length > 0 && <span className="tab-count">{deviceValues.length}</span>}
            </button>
            <button
              className={`tab-btn ${deviceSubTab === 'raw' ? 'active' : ''}`}
              onClick={() => setDeviceSubTab('raw')}
            >
              📋 Raw Messages
              {deviceRaw.length > 0 && <span className="tab-count">{deviceRaw.length}</span>}
            </button>
          </nav>

          <main>
            {deviceSubTab === 'values' && (
              <>
                {deviceValues.length === 0 && (
                  <div className="empty">No decoded values for this device</div>
                )}
                {deviceValues.length > 0 && (
                  <div className="values-grid">
                    {deviceValues.map((entry) => (
                      <div key={entry.pgn} className="value-card">
                        <div className="value-card-header">
                          PGN {entry.pgn} — {PGN_NAMES[entry.pgn] || 'Unknown'}
                        </div>
                        <div className="value-card-body">
                          <table className="pgn-fields-table">
                            <thead><tr><th>Parameter</th><th>Value</th><th>Unit</th></tr></thead>
                            <tbody>
                              {(entry.fields || []).map((f) => (
                                <tr key={f.key}>
                                  <td className="pgn-field-name">{f.name || f.key}</td>
                                  <td className="pgn-field-value">{formatValue(f.value, f.unit)}</td>
                                  <td className="pgn-field-unit">{formatUnit(f.unit)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

            {deviceSubTab === 'raw' && (
              <>
                <div className="raw-controls">
                  <button className="tab-btn" onClick={handlePauseToggle}>
                    {rawPaused ? '▶ Resume' : '⏸ Pause'}
                  </button>
                  <span className="raw-info">
                    Messages from Source {selectedDevice}: {deviceRaw.length}
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
                      {deviceRaw.length === 0 && (
                        <tr><td colSpan={7} className="empty-cell">No data. Waiting for messages...</td></tr>
                      )}
                      {[...deviceRaw].reverse().map((m, idx) => (
                        <RawRow key={`${m.timestamp}-${idx}`} msg={m} idx={deviceRaw.length - idx} formatTime={formatTime} formatValue={formatValue} formatUnit={formatUnit} />
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </main>
        </>
      )}
    </div>
  );
}