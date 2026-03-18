import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { ZoomIn, ZoomOut, Maximize2, Eye, EyeOff } from 'lucide-react';
import './GraphCanvas.css';

const NODE_TYPES = {
    patient:        { color: '#E040FB', label: 'Patient',    size: 12 },
    disease:        { color: '#FF5252', label: 'Disease',    size: 9  },
    symptom:        { color: '#FFB020', label: 'Symptom',    size: 7  },
    biomarker:      { color: '#00E5FF', label: 'Biomarker',  size: 7  },
    drug:           { color: '#00FFA3', label: 'Drug',       size: 9  },
    gene:           { color: '#7C4DFF', label: 'Gene',       size: 6  },
    protein:        { color: '#448AFF', label: 'Protein',    size: 6  },
    pathway:        { color: '#FF6E40', label: 'Pathway',    size: 6  },
    research_paper: { color: '#9E9E9E', label: 'Paper',      size: 5  },
    hypothesis:     { color: '#FFEA00', label: 'Hypothesis', size: 8  },
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
                fg.d3Force('charge').strength(-300);
                fg.d3Force('link').distance(60);
                fg.zoomToFit(600, 60);
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
    const handleZoomIn = () => fgRef.current?.zoom(1.4, 300);
    const handleZoomOut = () => fgRef.current?.zoom(0.7, 300);
    const handleFit = () => fgRef.current?.zoomToFit(400, 60);

    // Node rendering
    const drawNode = useCallback((node, ctx, globalScale) => {
        const meta = getNodeMeta(node);
        const highlighted = hoverNode ? isConnected(node.id) : true;
        const alpha = highlighted ? 1 : 0.12;
        const radius = meta.size / globalScale;
        const nodeColor = meta.color;

        ctx.save();
        ctx.globalAlpha = alpha;

        // Outer glow
        if (highlighted) {
            ctx.shadowColor = nodeColor;
            ctx.shadowBlur = 12 / globalScale;
        }

        // Main circle
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
        ctx.fillStyle = nodeColor;
        ctx.fill();
        ctx.shadowBlur = 0;

        // Inner bright core
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius * 0.45, 0, 2 * Math.PI);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.45)';
        ctx.fill();

        // Hovered node ring
        if (hoverNode && (node.id === (hoverNode.id || hoverNode))) {
            ctx.beginPath();
            ctx.arc(node.x, node.y, radius + 3 / globalScale, 0, 2 * Math.PI);
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1.5 / globalScale;
            ctx.stroke();
        }

        // Label
        if (showLabels && globalScale > 0.6) {
            const label = node.label || node.id;
            const fontSize = 11 / globalScale;
            ctx.font = `500 ${fontSize}px 'Outfit', -apple-system, sans-serif`;
            const textWidth = ctx.measureText(label).width;
            const padX = fontSize * 0.5;
            const padY = fontSize * 0.25;
            const pillW = textWidth + padX * 2;
            const pillH = fontSize + padY * 2;
            const textY = node.y + radius + (padY + 3 / globalScale);

            // Pill background
            const pillX = node.x - pillW / 2;
            const pillY = textY - pillH / 2;
            const r = pillH / 2;
            ctx.beginPath();
            ctx.moveTo(pillX + r, pillY);
            ctx.lineTo(pillX + pillW - r, pillY);
            ctx.quadraticCurveTo(pillX + pillW, pillY, pillX + pillW, pillY + r);
            ctx.lineTo(pillX + pillW, pillY + pillH - r);
            ctx.quadraticCurveTo(pillX + pillW, pillY + pillH, pillX + pillW - r, pillY + pillH);
            ctx.lineTo(pillX + r, pillY + pillH);
            ctx.quadraticCurveTo(pillX, pillY + pillH, pillX, pillY + pillH - r);
            ctx.lineTo(pillX, pillY + r);
            ctx.quadraticCurveTo(pillX, pillY, pillX + r, pillY);
            ctx.closePath();
            ctx.fillStyle = 'rgba(11, 15, 25, 0.88)';
            ctx.fill();
            ctx.strokeStyle = highlighted ? `${nodeColor}44` : 'rgba(255,255,255,0.05)';
            ctx.lineWidth = 0.6 / globalScale;
            ctx.stroke();

            // Text
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = highlighted ? '#E2E8F0' : '#555';
            ctx.fillText(label, node.x, textY);
        }

        ctx.restore();
    }, [hoverNode, isConnected, showLabels]);

    // Edge rendering
    const drawLink = useCallback((link, ctx, globalScale) => {
        const highlighted = hoverNode ? isConnected(link.source?.id || link.source) && isConnected(link.target?.id || link.target) : true;
        ctx.save();
        ctx.globalAlpha = highlighted ? 0.25 : 0.03;

        const srcMeta = getNodeMeta(link.source);
        ctx.strokeStyle = srcMeta.color;
        ctx.lineWidth = (highlighted ? 1.2 : 0.5) / globalScale;
        ctx.beginPath();
        ctx.moveTo(link.source.x, link.source.y);
        ctx.lineTo(link.target.x, link.target.y);
        ctx.stroke();

        // Arrow
        if (highlighted && globalScale > 0.4) {
            const dir = Math.atan2(link.target.y - link.source.y, link.target.x - link.source.x);
            const tgtMeta = getNodeMeta(link.target);
            const tgtR = tgtMeta.size / globalScale;
            const arrowLen = 4 / globalScale;
            const endX = link.target.x - Math.cos(dir) * tgtR;
            const endY = link.target.y - Math.sin(dir) * tgtR;
            ctx.fillStyle = srcMeta.color;
            ctx.beginPath();
            ctx.moveTo(endX, endY);
            ctx.lineTo(endX - arrowLen * Math.cos(dir - 0.4), endY - arrowLen * Math.sin(dir - 0.4));
            ctx.lineTo(endX - arrowLen * Math.cos(dir + 0.4), endY - arrowLen * Math.sin(dir + 0.4));
            ctx.closePath();
            ctx.fill();
        }

        ctx.restore();
    }, [hoverNode, isConnected]);

    // Empty state
    if (!graphData?.nodes?.length) {
        return (
            <div className="gc-container" ref={containerRef}>
                <div className="gc-empty">
                    <div className="gc-empty-ring" />
                    <div className="gc-empty-inner" />
                    <p className="gc-empty-title">Cure Graph</p>
                    <p className="gc-empty-sub">Submit patient data to visualize the biomedical reasoning graph</p>
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
                nodeLabel={node => {
                    const meta = getNodeMeta(node);
                    return `${node.label || node.id}  [${meta.label}]`;
                }}
                nodeColor={() => 'transparent'}
                nodeRelSize={1}
                nodeCanvasObjectMode={() => 'replace'}
                nodeCanvasObject={drawNode}
                linkCanvasObjectMode={() => 'replace'}
                linkCanvasObject={drawLink}
                onNodeHover={setHoverNode}
                onNodeClick={(node) => {
                    if (node) {
                        fgRef.current.centerAt(node.x, node.y, 600);
                        fgRef.current.zoom(2.5, 600);
                    }
                }}
                enableNodeDrag={true}
                enableZoomPanInteraction={true}
                backgroundColor="transparent"
                cooldownTicks={200}
                warmupTicks={50}
            />

            {/* Zoom Controls */}
            <div className="gc-controls">
                <button onClick={handleZoomIn} title="Zoom in"><ZoomIn size={16} /></button>
                <button onClick={handleZoomOut} title="Zoom out"><ZoomOut size={16} /></button>
                <button onClick={handleFit} title="Fit to view"><Maximize2 size={16} /></button>
            </div>

            {/* Label Toggle */}
            <div className="gc-label-toggle">
                <button onClick={() => setShowLabels(v => !v)} title={showLabels ? 'Hide labels' : 'Show labels'}>
                    {showLabels ? <Eye size={14} /> : <EyeOff size={14} />}
                    <span>Labels</span>
                </button>
            </div>

            {/* Legend */}
            <div className={`gc-legend ${legendOpen ? 'gc-legend-open' : ''}`}>
                <button className="gc-legend-toggle" onClick={() => setLegendOpen(v => !v)}>
                    <span className="gc-legend-dot" />
                    <span>{legendOpen ? 'Legend' : `${Object.keys(NODE_TYPES).length}`}</span>
                    <span className="gc-legend-arrow">{legendOpen ? '▾' : '▸'}</span>
                </button>
                {legendOpen && (
                    <div className="gc-legend-items">
                        {Object.entries(NODE_TYPES).map(([key, val]) => (
                            <div key={key} className="gc-legend-item">
                                <span className="gc-legend-dot" style={{ background: val.color, boxShadow: `0 0 6px ${val.color}88` }} />
                                <span>{val.label}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Node count badge */}
            <div className="gc-badge">
                {graphData.nodes.length} nodes · {graphData.links.length} edges
            </div>
        </div>
    );
}
