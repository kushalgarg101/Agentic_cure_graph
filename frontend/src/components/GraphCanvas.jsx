import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { ZoomIn, ZoomOut, Maximize2, Eye, EyeOff, Layers } from 'lucide-react';
import './GraphCanvas.css';

const NODE_TYPES = {
    patient:        { color: '#F000FF', label: 'Patient',    size: 14 },
    disease:        { color: '#FF3366', label: 'Disease',    size: 10 },
    symptom:        { color: '#FFB800', label: 'Symptom',    size: 7  },
    biomarker:      { color: '#00F0FF', label: 'Biomarker',  size: 7  },
    drug:           { color: '#00FF9D', label: 'Drug',       size: 10 },
    gene:           { color: '#7B61FF', label: 'Gene',       size: 6  },
    protein:        { color: '#2B80FF', label: 'Protein',    size: 6  },
    pathway:        { color: '#FF6E40', label: 'Pathway',    size: 6  },
    research_paper: { color: '#8892B0', label: 'Paper',      size: 5  },
    hypothesis:     { color: '#FFF500', label: 'Hypothesis', size: 9  },
};

const getNodeMeta = (node) => NODE_TYPES[node.type] || { color: '#FFFFFF', label: node.type, size: 5 };

export default function GraphCanvas({ graphData }) {
    const fgRef = useRef();
    const containerRef = useRef();
    const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
    const [hoverNode, setHoverNode] = useState(null);
    const [legendOpen, setLegendOpen] = useState(true);
    const [showLabels, setShowLabels] = useState(true);

    // Responsive sizing based on container
    useEffect(() => {
        const measure = () => {
            if (containerRef.current) {
                const rect = containerRef.current.getBoundingClientRect();
                setDimensions({ width: rect.width, height: rect.height });
            }
        };
        measure();
        window.addEventListener('resize', measure);
        return () => window.removeEventListener('resize', measure);
    }, []);

    // Center + zoom on data change
    useEffect(() => {
        if (graphData?.nodes?.length > 0 && fgRef.current) {
            setTimeout(() => {
                const fg = fgRef.current;
                fg.d3Force('charge').strength(-350);
                fg.d3Force('link').distance(70);
                fg.zoomToFit(600, 80);
            }, 300);
        }
    }, [graphData]);

    // Build adjacency index for hover highlighting
    const adjacency = useMemo(() => {
        const map = new Map();
        if (!graphData?.links) return map;
        graphData.links.forEach(link => {
            const src = link.source?.id || link.source;
            const tgt = link.target?.id || link.target;
            if (!map.has(src)) map.set(src, new Set());
            if (!map.has(tgt)) map.set(tgt, new Set());
            map.get(src).add(tgt);
            map.get(tgt).add(src);
        });
        return map;
    }, [graphData]);

    const isConnected = useCallback((nodeId) => {
        if (!hoverNode) return true;
        const hId = hoverNode.id || hoverNode;
        if (nodeId === hId) return true;
        return adjacency.get(hId)?.has(nodeId) || false;
    }, [hoverNode, adjacency]);

    // Zoom helpers
    const handleZoomIn = () => fgRef.current?.zoom(1.5, 400);
    const handleZoomOut = () => fgRef.current?.zoom(0.66, 400);
    const handleFit = () => fgRef.current?.zoomToFit(600, 80);

    // Node rendering
    const drawNode = useCallback((node, ctx, globalScale) => {
        // Guard: skip rendering if node coordinates are not yet computed by the force layout
        if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;

        const meta = getNodeMeta(node);
        const highlighted = hoverNode ? isConnected(node.id) : true;
        const isHoveredNode = hoverNode && (node.id === (hoverNode.id || hoverNode));
        
        // Dynamic opacity based on zoom and highlight state
        let alpha = highlighted ? 1 : Math.max(0.05, 0.15 - (globalScale * 0.05));
        const radius = meta.size / globalScale;
        const nodeColor = meta.color;

        ctx.save();
        ctx.globalAlpha = alpha;

        // Enhanced Glow (Outer)
        if (highlighted) {
            ctx.shadowColor = nodeColor;
            ctx.shadowBlur = (isHoveredNode ? 24 : 15) / globalScale;
            
            // For hovered node, draw a large subtle outer halo
            if (isHoveredNode) {
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius * 3, 0, 2 * Math.PI);
                ctx.fillStyle = `${nodeColor}1A`; // 10% opacity
                ctx.fill();
            }
        }

        // Main Body Fill with radial gradient for 3D effect
        const grad = ctx.createRadialGradient(
            node.x - radius * 0.3, node.y - radius * 0.3, 0,
            node.x, node.y, radius
        );
        grad.addColorStop(0, '#FFFFFF');
        grad.addColorStop(0.3, nodeColor);
        grad.addColorStop(1, '#000000'); // Fades to dark edges

        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
        ctx.fillStyle = highlighted ? grad : nodeColor; // Flat color if dimmed
        ctx.fill();
        ctx.shadowBlur = 0; // Turn off shadow so it doesn't apply to the stroke

        // Hover Ring
        if (isHoveredNode) {
            ctx.beginPath();
            ctx.arc(node.x, node.y, radius + (6 / globalScale), 0, 2 * Math.PI);
            ctx.strokeStyle = '#FFFFFF';
            ctx.lineWidth = 2 / globalScale;
            ctx.setLineDash([4 / globalScale, 4 / globalScale]);
            ctx.stroke();
            ctx.setLineDash([]);
        }

        // Label Rendering
        if (showLabels && (globalScale > 0.8 || isHoveredNode)) {
            const label = node.label || node.id;
            const fontSize = (isHoveredNode ? 14 : 11) / globalScale;
            ctx.font = `600 ${fontSize}px var(--font-base), sans-serif`;
            const textWidth = ctx.measureText(label).width;
            
            const padX = fontSize * 0.6;
            const padY = fontSize * 0.3;
            const pillW = textWidth + padX * 2;
            const pillH = fontSize + padY * 2.5;
            const textY = node.y + radius + (padY + (isHoveredNode ? 10 : 5) / globalScale);

            const pillX = node.x - pillW / 2;
            const pillY = textY - pillH / 2;
            const roundness = pillH / 2;

            // Draw rounded pill background
            ctx.beginPath();
            ctx.moveTo(pillX + roundness, pillY);
            ctx.lineTo(pillX + pillW - roundness, pillY);
            ctx.quadraticCurveTo(pillX + pillW, pillY, pillX + pillW, pillY + roundness);
            ctx.lineTo(pillX + pillW, pillY + pillH - roundness);
            ctx.quadraticCurveTo(pillX + pillW, pillY + pillH, pillX + pillW - roundness, pillY + pillH);
            ctx.lineTo(pillX + roundness, pillY + pillH);
            ctx.quadraticCurveTo(pillX, pillY + pillH, pillX, pillY + pillH - roundness);
            ctx.lineTo(pillX, pillY + roundness);
            ctx.quadraticCurveTo(pillX, pillY, pillX + roundness, pillY);
            ctx.closePath();

            ctx.fillStyle = isHoveredNode ? 'rgba(6, 9, 19, 0.95)' : 'rgba(6, 9, 19, 0.8)';
            ctx.fill();

            // Pill Border
            ctx.strokeStyle = highlighted ? `${nodeColor}66` : 'rgba(255,255,255,0.05)';
            ctx.lineWidth = (isHoveredNode ? 1.5 : 1) / globalScale;
            ctx.stroke();

            // Draw Text
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = isHoveredNode ? '#FFFFFF' : (highlighted ? '#E2E8F0' : '#8892B0');
            ctx.fillText(label, node.x, textY);
            
            // Sub-label for hovered nodes (shows type)
            if (isHoveredNode && globalScale > 0.5) {
                const subFontSize = 8 / globalScale;
                ctx.font = `500 ${subFontSize}px var(--font-base), sans-serif`;
                ctx.fillStyle = nodeColor;
                ctx.fillText(meta.label.toUpperCase(), node.x, textY + pillH/2 + subFontSize/2 + (2/globalScale));
            }
        }

        ctx.restore();
    }, [hoverNode, isConnected, showLabels]);

    // Edge rendering
    const drawLink = useCallback((link, ctx, globalScale) => {
        const highlighted = hoverNode ? isConnected(link.source?.id || link.source) && isConnected(link.target?.id || link.target) : true;
        
        ctx.save();
        ctx.globalAlpha = highlighted ? 0.35 : 0.05;

        const srcMeta = getNodeMeta(link.source);
        const tgtMeta = getNodeMeta(link.target);
        
        // Validate coordinates to prevent "non-finite double value" Canvas errors
        const sx = link.source.x;
        const sy = link.source.y;
        const tx = link.target.x;
        const ty = link.target.y;

        if (typeof sx !== 'number' || typeof sy !== 'number' || typeof tx !== 'number' || typeof ty !== 'number' ||
            !Number.isFinite(sx) || !Number.isFinite(sy) || !Number.isFinite(tx) || !Number.isFinite(ty)) {
            ctx.restore();
            return;
        }

        // Gradient stroke for edges
        const grad = ctx.createLinearGradient(sx, sy, tx, ty);
        grad.addColorStop(0, srcMeta.color);
        grad.addColorStop(1, tgtMeta.color);
        
        ctx.strokeStyle = grad;
        ctx.lineWidth = (highlighted ? 1.5 : 0.5) / globalScale;
        
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.lineTo(tx, ty);
        ctx.stroke();

        // Arrow
        if (highlighted && globalScale > 0.3) {
            const dir = Math.atan2(ty - sy, tx - sx);
            
            // Validate dir is a finite number
            if (Number.isFinite(dir)) {
                const tgtR = tgtMeta.size / globalScale;
                const arrowLen = 5 / globalScale;
                const arrowWidth = 0.5;
                
                const endX = tx - Math.cos(dir) * (tgtR + 2/globalScale);
                const endY = ty - Math.sin(dir) * (tgtR + 2/globalScale);
                
                ctx.fillStyle = tgtMeta.color;
                ctx.globalAlpha = 0.8;
                ctx.beginPath();
                ctx.moveTo(endX, endY);
                ctx.lineTo(endX - arrowLen * Math.cos(dir - arrowWidth), endY - arrowLen * Math.sin(dir - arrowWidth));
                ctx.lineTo(endX - arrowLen * Math.cos(dir + arrowWidth), endY - arrowLen * Math.sin(dir + arrowWidth));
                ctx.closePath();
                ctx.fill();
            }
        }

        ctx.restore();
    }, [hoverNode, isConnected]);

    // Empty state
    if (!graphData?.nodes?.length) {
        return (
            <div className="gc-container" ref={containerRef}>
                <div className="gc-empty">
                    <div className="gc-empty-brand">
                        <div className="gc-empty-ring-outer" />
                        <div className="gc-empty-ring-inner" />
                        <div className="gc-empty-core" />
                    </div>
                    <p className="gc-empty-title">CURE GRAPH</p>
                    <p className="gc-empty-sub">Connecting the dots across millions of biomedical relationships.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="gc-container" ref={containerRef}>
            <ForceGraph2D
                ref={fgRef}
                width={dimensions.width}
                height={dimensions.height}
                graphData={graphData}
                nodeColor={() => 'transparent'}
                nodeRelSize={1}
                nodeCanvasObjectMode={() => 'replace'}
                nodeCanvasObject={drawNode}
                linkCanvasObjectMode={() => 'replace'}
                linkCanvasObject={drawLink}
                onNodeHover={setHoverNode}
                onNodeClick={(node) => {
                    if (node) {
                        fgRef.current.centerAt(node.x, node.y, 800);
                        fgRef.current.zoom(2.5, 800);
                    }
                }}
                enableNodeDrag={true}
                enableZoomPanInteraction={true}
                backgroundColor="transparent"
                cooldownTicks={250}
                warmupTicks={50}
            />

            {/* Badge */}
            <div className="gc-badge">
                {graphData.nodes.length} nodes · {graphData.links.length} edges
            </div>

            {/* Zoom Controls */}
            <div className="gc-controls">
                <button onClick={handleZoomIn} title="Zoom in"><ZoomIn size={18} /></button>
                <button onClick={handleZoomOut} title="Zoom out"><ZoomOut size={18} /></button>
                <button onClick={handleFit} title="Fit to view"><Maximize2 size={18} /></button>
            </div>

            {/* Label Toggle at Bottom Center */}
            <div className="gc-label-toggle">
                <button onClick={() => setShowLabels(v => !v)}>
                    {showLabels ? <EyeOff size={16} /> : <Eye size={16} />}
                    <span>{showLabels ? 'Hide Labels' : 'Show Labels'}</span>
                </button>
            </div>

            {/* Legend */}
            <div className={`gc-legend ${legendOpen ? 'gc-legend-open' : ''}`}>
                <button className="gc-legend-toggle" onClick={() => setLegendOpen(v => !v)}>
                    <Layers size={16} className="gc-legend-icon" />
                    <span>{legendOpen ? 'Legend' : `${Object.keys(NODE_TYPES).length} Types`}</span>
                    <span className="gc-legend-arrow">{legendOpen ? '▾' : '▸'}</span>
                </button>
                {legendOpen && (
                    <div className="gc-legend-items">
                        {Object.entries(NODE_TYPES).map(([key, val]) => (
                            <div key={key} className="gc-legend-item">
                                <span className="gc-legend-dot" style={{ 
                                    background: val.color, 
                                    boxShadow: `0 0 10px ${val.color}99`,
                                    borderColor: `${val.color}99` 
                                }} />
                                <span>{val.label}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
