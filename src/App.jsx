import React, { useState } from 'react';
import { 
  UploadCloud, 
  Layers, 
  FileSpreadsheet, 
  Cpu, 
  Eye, 
  Compass, 
  AlertCircle 
} from 'lucide-react';
import PidViewer from './components/PidViewer';
import DataTable from './components/DataTable';
import './App.css';

function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null); // API response payload
  const [selectedId, setSelectedId] = useState(null);

  // Layer switches
  const [layers, setLayers] = useState({
    instrument: true,
    valve: true,
    connection: true
  });

  const toggleLayer = (layer) => {
    setLayers(prev => ({ ...prev, [layer]: !prev[layer] }));
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      handleUpload(selectedFile);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const selectedFile = e.dataTransfer.files[0];
      setFile(selectedFile);
      handleUpload(selectedFile);
    }
  };

  const handleUpload = async (uploadFile) => {
    setLoading(true);
    setError(null);
    setData(null);
    setSelectedId(null);

    const formData = new FormData();
    formData.append('file', uploadFile);

    try {
      const response = await fetch('http://localhost:5000/api/process', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to process file');
      }

      const result = await response.json();
      setData(result);
    } catch (err) {
      console.error(err);
      setError(err.message || 'An error occurred while uploading and parsing the document.');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadExcel = () => {
    window.open('http://localhost:5000/api/download_excel', '_blank');
  };

  const handleSelectId = (id) => {
    setSelectedId(id);
  };

  return (
    <div className="app-container">
      {/* Dashboard Header */}
      <header>
        <div className="title-container">
          <h1>
            <Compass size={28} style={{ verticalAlign: 'middle', marginRight: '8px', color: 'var(--secondary)' }} />
            P&ID Intelligent Auto-Parser
          </h1>
          <div className="subtitle">Identify equipment, instruments, and trace topology maps automatically.</div>
        </div>
      </header>

      {/* Main Workspace */}
      <main className="animate-fade">
        {/* Upload Box (Visible when no data or during upload) */}
        {(!data || loading) && (
          <div 
            className="upload-card glass-panel"
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onClick={() => document.getElementById('file-input').click()}
          >
            <input 
              type="file" 
              id="file-input" 
              style={{ display: 'none' }} 
              accept=".pdf,.png,.jpg,.jpeg"
              onChange={handleFileChange}
            />
            <div className="upload-icon-container">
              <UploadCloud size={40} />
            </div>
            {loading ? (
              <>
                <h3>Analyzing Diagram...</h3>
                <p>Running OCR engine and pathfinders. This will take a few seconds.</p>
                <div className="spinner"></div>
              </>
            ) : (
              <>
                <h3>Upload P&ID Diagram</h3>
                <p>Drag and drop a vector PDF or image (PNG/JPG), or click to browse</p>
                <button className="upload-btn">Select File</button>
              </>
            )}
          </div>
        )}

        {/* Error Alert Box */}
        {error && (
          <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem', borderColor: 'red', display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <AlertCircle size={32} style={{ color: 'red' }} />
            <div>
              <h4 style={{ color: 'red', fontWeight: '600' }}>Processing Error</h4>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>{error}</p>
            </div>
          </div>
        )}

        {/* Active Analysis Dashboard */}
        {data && !loading && (
          <div className="dashboard-grid animate-slide">
            
            {/* Left: Zoomable Viewer */}
            <div className="viewer-panel glass-panel">
              <div className="panel-header">
                <div className="panel-title">
                  <Cpu size={20} style={{ color: 'var(--secondary)' }} />
                  Visual Topographic Map
                </div>
                
                {/* Layers Visibility Toggles */}
                <div className="layer-toggles">
                  <button 
                    className={`layer-btn instrument ${layers.instrument ? 'active' : ''}`}
                    onClick={() => toggleLayer('instrument')}
                  >
                    <Layers size={14} /> Instruments / Vessels
                  </button>
                  <button 
                    className={`layer-btn valve ${layers.valve ? 'active' : ''}`}
                    onClick={() => toggleLayer('valve')}
                  >
                    <Layers size={14} /> Valves
                  </button>
                  <button 
                    className={`layer-btn connection ${layers.connection ? 'active' : ''}`}
                    onClick={() => toggleLayer('connection')}
                  >
                    <Layers size={14} /> Connections
                  </button>
                </div>
              </div>

              {/* Viewport Canvas wrapper */}
              <PidViewer
                imageUrl={data.image_url}
                width={data.width}
                height={data.height}
                symbols={data.symbols}
                connections={data.connections}
                selectedId={selectedId}
                onSelectSymbol={handleSelectId}
                layers={layers}
              />
            </div>

            {/* Right: Data Tables and Export */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <DataTable
                symbols={data.symbols}
                connections={data.connections}
                selectedId={selectedId}
                onSelect={handleSelectId}
              />

              {/* Action Drawer */}
              <div className="action-footer">
                <button 
                  className="upload-btn" 
                  style={{ marginRight: 'auto', background: 'rgba(255,255,255,0.05)', color: 'var(--text-primary)', border: '1px solid var(--border-glass)', boxShadow: 'none' }}
                  onClick={() => setData(null)}
                >
                  Process Another
                </button>
                
                <button className="export-btn" onClick={handleDownloadExcel}>
                  <FileSpreadsheet size={18} />
                  Export Component Inventory (.xlsx)
                </button>
              </div>
            </div>

          </div>
        )}
      </main>
    </div>
  );
}

export default App;
