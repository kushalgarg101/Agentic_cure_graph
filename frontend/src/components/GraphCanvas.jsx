import React, { useRef, useEffect, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

export default function GraphCanvas({ graphData }) {
    const fgRef = useRef();
    const [dimensions, setDimensions] = useState({ width: window.innerWidth, height: window.innerHeight });

    useEffect(() => {
        const handleResize = () => {
            setDimensions({ width: window.innerWidth, height: window.innerHeight });
        };
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    // Recenter graph whenever data changes
    useEffect(() => {
        if (graphData && graphData.nodes && graphData.nodes.length > 0 && fgRef.current) {
            setTimeout(() => {
                fgRef.current.d3Force('charge').strength(-400);
                fgRef.current.zoomToFit(400, 50);
            }, 200);
        }
    }, [graphData]);

    const getNodeColor = (node) => {
        switch (node.type) {
            case 'patient': return '#E040FB';         // Magenta
            case 'disease': return '#FF5252';         // Red
            case 'symptom': return '#FFB020';         // Amber
            case 'biomarker': return '#00E5FF';       // Cyan
            case 'drug': return '#00FFA3';            // Green
            case 'gene': return '#7C4DFF';            // Deep purple
            case 'protein': return '#448AFF';         // Blue
            case 'pathway': return '#FF6E40';         // Deep orange
            case 'research_paper': return '#9E9E9E';  // Grey
            case 'hypothesis': return '#FFEA00';      // Yellow
            default: return '#FFFFFF';
        }
    };

    const getEdgeColor = () => {
        return 'rgba(255, 255, 255, 0.15)';
    };

    if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
        return (
            <div className="graph-placeholder">
                <p>Awaiting patient intelligence to render Cure Graph...</p>
            </div>
        );
    }

    return (
        <div className="graph-container">
            <ForceGraph2D
                ref={fgRef}
                width={dimensions.width}
                height={dimensions.height}
                graphData={graphData}
                nodeLabel="id"
                nodeColor={getNodeColor}
                nodeRelSize={6}
                linkColor={getEdgeColor}
                linkWidth={1.5}
                linkDirectionalArrowLength={3.5}
                linkDirectionalArrowRelPos={1}
                nodeCanvasObject={(node, ctx, globalScale) => {
                    const nodeColor = getNodeColor(node);
                    const nodeRadius = 5;

                    // 1. Draw node circle with glow
                    ctx.shadowColor = nodeColor;
                    ctx.shadowBlur = 10;
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, nodeRadius, 0, 2 * Math.PI, false);
                    ctx.fillStyle = nodeColor;
                    ctx.fill();
                    ctx.shadowBlur = 0; // reset

                    // 2. Draw text label below the node
                    // Use node.label if available, fallback to id
                    const label = node.label || node.id;
                    const fontSize = 11 / globalScale;
                    ctx.font = `${fontSize}px Sans-Serif`;
                    const textWidth = ctx.measureText(label).width;
                    const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.4);

                    // Place text just below the node
                    const textY = node.y + nodeRadius + (fontSize / 2) + (4 / globalScale);

                    // Background pill
                    ctx.fillStyle = 'rgba(11, 15, 25, 0.85)';
                    ctx.fillRect(
                        node.x - bckgDimensions[0] / 2,
                        textY - bckgDimensions[1] / 2,
                        bckgDimensions[0],
                        bckgDimensions[1]
                    );

                    // Subtle border around pill to match node color
                    ctx.strokeStyle = nodeColor;
                    ctx.lineWidth = 0.5 / globalScale;
                    ctx.strokeRect(
                        node.x - bckgDimensions[0] / 2,
                        textY - bckgDimensions[1] / 2,
                        bckgDimensions[0],
                        bckgDimensions[1]
                    );

                    // Text
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillStyle = '#E2E8F0';
                    ctx.fillText(label, node.x, textY);
                }}
                backgroundColor="transparent"
            />
            {/* Color Legend */}
            <div className="legend-overlay glass-panel">
                <div className="legend-item"><span className="legend-dot" style={{ background: '#E040FB' }}></span> Patient</div>
                <div className="legend-item"><span className="legend-dot" style={{ background: '#FF5252' }}></span> Disease</div>
                <div className="legend-item"><span className="legend-dot" style={{ background: '#FFB020' }}></span> Symptom</div>
                <div className="legend-item"><span className="legend-dot" style={{ background: '#00E5FF' }}></span> Biomarker</div>
                <div className="legend-item"><span className="legend-dot" style={{ background: '#00FFA3' }}></span> Drug</div>
                <div className="legend-item"><span className="legend-dot" style={{ background: '#7C4DFF' }}></span> Gene</div>
                <div className="legend-item"><span className="legend-dot" style={{ background: '#448AFF' }}></span> Protein</div>
                <div className="legend-item"><span className="legend-dot" style={{ background: '#FF6E40' }}></span> Pathway</div>
                <div className="legend-item"><span className="legend-dot" style={{ background: '#9E9E9E' }}></span> Paper</div>
                <div className="legend-item"><span className="legend-dot" style={{ background: '#FFEA00' }}></span> Hypothesis</div>
            </div>
        </div>
    );
}
