import React, { useState, useRef, useEffect } from 'react';

const PidViewer = ({ 
  imageUrl, 
  width, 
  height, 
  symbols, 
  connections, 
  selectedId, 
  onSelectSymbol, 
  layers 
}) => {
  const [zoom, setZoom] = useState(0.5); // Start slightly zoomed out to fit
  const [offset, setOffset] = useState({ x: 50, y: 50 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const containerRef = useRef(null);

  // Auto-center and fit image on load
  useEffect(() => {
    if (imageUrl && containerRef.current && width && height) {
      const container = containerRef.current;
      const fitZoom = Math.min(
        (container.clientWidth - 40) / width,
        (container.clientHeight - 40) / height
      );
      setZoom(fitZoom || 0.5);
      
      const newX = (container.clientWidth - width * fitZoom) / 2;
      const newY = (container.clientHeight - height * fitZoom) / 2;
      setOffset({ x: newX, y: newY });
    }
  }, [imageUrl, width, height]);

  // Handle zooming via mouse wheel
  const handleWheel = (e) => {
    if (!containerRef.current) return;

    const zoomIntensity = 0.1;
    const container = containerRef.current;
    const rect = container.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    // Coordinates relative to the image coordinates before zoom change
    const imageX = (mouseX - offset.x) / zoom;
    const imageY = (mouseY - offset.y) / zoom;

    const zoomFactor = e.deltaY < 0 ? (1 + zoomIntensity) : (1 - zoomIntensity);
    const newZoom = Math.min(Math.max(zoom * zoomFactor, 0.1), 5.0);

    // Recalculate offset so the mouse cursor stays over the same image point
    const newOffsetX = mouseX - imageX * newZoom;
    const newOffsetY = mouseY - imageY * newZoom;

    setZoom(newZoom);
    setOffset({ x: newOffsetX, y: newOffsetY });
  };

  // Mouse drag listeners for panning
  const handleMouseDown = (e) => {
    if (e.button !== 0) return; // Only left click drag
    setIsDragging(true);
    dragStart.current = { x: e.clientX - offset.x, y: e.clientY - offset.y };
  };

  const handleMouseMove = (e) => {
    if (!isDragging) return;
    setOffset({
      x: e.clientX - dragStart.current.x,
      y: e.clientY - dragStart.current.y
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleReset = () => {
    if (!containerRef.current || !width || !height) return;
    const container = containerRef.current;
    const fitZoom = Math.min(
      (container.clientWidth - 40) / width,
      (container.clientHeight - 40) / height
    );
    setZoom(fitZoom);
    setOffset({
      x: (container.clientWidth - width * fitZoom) / 2,
      y: (container.clientHeight - height * fitZoom) / 2
    });
  };

  const getOverlayColor = (type) => {
    switch (type) {
      case 'Instrument': return 'var(--color-instrument)';
      case 'Valve': return 'var(--color-valve)';
      case 'Vessel': return 'var(--color-vessel)';
      default: return 'var(--secondary)';
    }
  };

  const getConnectionColor = (type) => {
    switch (type) {
      case 'Process Line': return 'var(--color-process-line)';
      case 'Electric Signal': return 'var(--color-electric)';
      case 'Pneumatic Signal': return 'var(--color-pneumatic)';
      default: return 'var(--text-secondary)';
    }
  };

  return (
    <div 
      className="canvas-container" 
      ref={containerRef}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      style={{ touchAction: 'none' }}
    >
      <div 
        className="pid-canvas-wrapper"
        style={{
          transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`,
          width: `${width}px`,
          height: `${height}px`
        }}
      >
        {imageUrl && (
          <img 
            src={imageUrl}
            alt="P&ID Diagram"
            className="pid-image"
            style={{ width: `${width}px`, height: `${height}px` }}
          />
        )}

        <svg 
          className="canvas-overlay"
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
        >
          {/* 1. Connections (Lines) Layer */}
          {layers.connection && connections.map((conn) => {
            const isSelected = selectedId === conn.id;
            const strokeColor = getConnectionColor(conn.type);
            const isDashed = conn.type === 'Electric Signal';
            const isTicked = conn.type === 'Pneumatic Signal';

            // Format path points for polyline
            const ptsString = conn.path.map(pt => `${pt[0]},${pt[1]}`).join(' ');

            return (
              <g key={conn.id} className="svg-connection-group" style={{ pointerEvents: 'auto', cursor: 'pointer' }} onClick={() => onSelectSymbol(conn.id)}>
                {/* Thick invisible hover track for easier selecting */}
                <polyline
                  points={ptsString}
                  fill="none"
                  stroke="transparent"
                  strokeWidth={20}
                />
                
                {/* Visual Line */}
                <polyline
                  points={ptsString}
                  fill="none"
                  stroke={strokeColor}
                  strokeWidth={isSelected ? 6 : 3}
                  strokeDasharray={isDashed ? "8,6" : isTicked ? "12,6,3,6" : "none"}
                  style={{
                    transition: 'stroke-width 0.2s',
                    filter: isSelected ? 'drop-shadow(0 0 4px ' + strokeColor + ')' : 'none'
                  }}
                />

                {/* Optional: label tooltip */}
                {conn.label && (
                  <text
                    x={conn.path[Math.floor(conn.path.length / 2)][0]}
                    y={conn.path[Math.floor(conn.path.length / 2)][1] - 8}
                    fill="#ffffff"
                    fontSize={10}
                    fontWeight="bold"
                    textAnchor="middle"
                    backgroundColor="rgba(0,0,0,0.8)"
                    style={{ pointerEvents: 'none', paintOrder: 'stroke', stroke: '#0f172a', strokeWidth: 3 }}
                  >
                    {conn.label}
                  </text>
                )}
              </g>
            );
          })}

          {/* 2. Symbols (Instruments, Valves, Vessels) Layer */}
          {symbols.map((sym) => {
            const isSelected = selectedId === sym.id;
            const color = getOverlayColor(sym.type);
            const [x0, y0, x1, y1] = sym.bbox;
            const w = x1 - x0;
            const h = y1 - y0;
            
            // Skip rendering based on layer switches
            if (sym.type === 'Instrument' && !layers.instrument) return null;
            if (sym.type === 'Valve' && !layers.valve) return null;
            if (sym.type === 'Vessel' && !layers.instrument) return null; // vessel grouped in instrument toggle

            return (
              <g 
                key={sym.id}
                className="svg-symbol-group"
                style={{ pointerEvents: 'auto', cursor: 'pointer' }}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectSymbol(sym.id);
                }}
              >
                {/* Hover box/circle */}
                {sym.type === 'Instrument' ? (
                  <circle
                    cx={sym.center[0]}
                    cy={sym.center[1]}
                    r={sym.radius + 2}
                    fill={isSelected ? 'rgba(6, 182, 212, 0.15)' : 'rgba(255,255,255,0.01)'}
                    stroke={color}
                    strokeWidth={isSelected ? 4 : 2}
                    style={{
                      transition: 'all 0.2s',
                      filter: isSelected ? 'drop-shadow(0 0 6px ' + color + ')' : 'none'
                    }}
                  />
                ) : (
                  <rect
                    x={x0 - 2}
                    y={y0 - 2}
                    width={w + 4}
                    height={h + 4}
                    fill={isSelected ? 'rgba(249, 115, 22, 0.15)' : 'rgba(255,255,255,0.01)'}
                    stroke={color}
                    strokeWidth={isSelected ? 4 : 2}
                    rx={sym.type === 'Valve' ? 4 : 8}
                    style={{
                      transition: 'all 0.2s',
                      filter: isSelected ? 'drop-shadow(0 0 6px ' + color + ')' : 'none'
                    }}
                  />
                )}

                {/* Text tag label just above symbol */}
                <text
                  x={sym.center[0]}
                  y={y0 - 8}
                  fill={color}
                  fontSize={11}
                  fontWeight="bold"
                  textAnchor="middle"
                  style={{ 
                    pointerEvents: 'none',
                    paintOrder: 'stroke',
                    stroke: '#0f172a',
                    strokeWidth: 3
                  }}
                >
                  {sym.tag}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Reset Floating Control */}
      <button 
        onClick={handleReset} 
        style={{
          position: 'absolute',
          bottom: '16px',
          right: '16px',
          zIndex: 5,
          background: 'rgba(30,41,59,0.85)',
          border: '1px solid var(--border-glass)',
          color: 'var(--text-primary)',
          padding: '0.5rem 1rem',
          borderRadius: 'var(--radius-sm)',
          cursor: 'pointer',
          fontSize: '0.8rem',
          fontWeight: 500,
          backdropFilter: 'blur(8px)'
        }}
      >
        Fit Screen
      </button>
    </div>
  );
};

export default PidViewer;
