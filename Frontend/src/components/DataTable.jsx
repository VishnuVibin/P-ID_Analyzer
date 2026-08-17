import React, { useState } from 'react';

const DataTable = ({ symbols, connections, selectedId, onSelect }) => {
  const [activeTab, setActiveTab] = useState('symbols'); // 'symbols' or 'connections'

  const getBadgeClass = (type) => {
    const t = type.toLowerCase();
    if (t.includes('valve')) return 'badge valve';
    if (t.includes('instrument')) return 'badge instrument';
    if (t.includes('vessel') || t.includes('pump') || t.includes('compressor') || t.includes('drum') || t.includes('exchanger') || t.includes('blower') || t.includes('tower') || t.includes('furnace') || t.includes('reactor') || t.includes('mixer')) return 'badge vessel';
    if (t.includes('process line')) return 'badge process';
    if (t.includes('electric signal')) return 'badge electric';
    if (t.includes('pneumatic signal')) return 'badge pneumatic';
    return 'badge';
  };

  return (
    <div className="details-panel glass-panel">
      {/* Tabs Header */}
      <div className="tabs-header">
        <button 
          className={`tab-btn ${activeTab === 'symbols' ? 'active' : ''}`}
          onClick={() => setActiveTab('symbols')}
        >
          Symbols ({symbols.length})
        </button>
        <button 
          className={`tab-btn ${activeTab === 'connections' ? 'active' : ''}`}
          onClick={() => setActiveTab('connections')}
        >
          Connections ({connections.length})
        </button>
      </div>

      {/* Tab Contents */}
      <div className="tab-content">
        {activeTab === 'symbols' ? (
          symbols.length === 0 ? (
            <div className="empty-state">
              <p>No symbols detected yet.</p>
            </div>
          ) : (
            <table className="inventory-table">
              <thead>
                <tr>
                  <th>Tag</th>
                  <th>Type</th>
                  <th>Center</th>
                </tr>
              </thead>
              <tbody>
                {symbols.map((sym) => (
                  <tr 
                    key={sym.id}
                    className={selectedId === sym.id ? 'selected' : ''}
                    onClick={() => onSelect(sym.id)}
                  >
                    <td style={{ fontWeight: '600' }}>{sym.tag}</td>
                    <td>
                      <span className={getBadgeClass(sym.type)}>{sym.type}</span>
                    </td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      ({sym.center[0]}, {sym.center[1]})
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : (
          connections.length === 0 ? (
            <div className="empty-state">
              <p>No connections traced yet.</p>
            </div>
          ) : (
            <table className="inventory-table">
              <thead>
                <tr>
                  <th>From / To</th>
                  <th>Type</th>
                  <th>Pipeline Spec</th>
                </tr>
              </thead>
              <tbody>
                {connections.map((conn) => (
                  <tr 
                    key={conn.id}
                    className={selectedId === conn.id ? 'selected' : ''}
                    onClick={() => onSelect(conn.id)}
                  >
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                        <span style={{ fontWeight: '600', fontSize: '0.85rem' }}>{conn.source_tag}</span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>➔ {conn.target_tag}</span>
                      </div>
                    </td>
                    <td>
                      <span className={getBadgeClass(conn.type)}>{conn.type}</span>
                    </td>
                    <td style={{ fontSize: '0.85rem', color: conn.label ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                      {conn.label ? conn.label : 'N/A'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </div>
    </div>
  );
};

export default DataTable;
