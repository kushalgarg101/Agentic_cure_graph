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
                    const label = node.id;
                    const fontSize = 12 / globalScale;
                    ctx.font = `${fontSize}px Sans-Serif`;
                    const textWidth = ctx.measureText(label).width;
                    const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2);

                    ctx.fillStyle = 'rgba(11, 15, 25, 0.8)';
                    ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);

                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillStyle = getNodeColor(node);
                    ctx.fillText(label, node.x, node.y);

                    // Add a subtle glow
                    ctx.shadowColor = getNodeColor(node);
                    ctx.shadowBlur = 10;
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, 4, 0, 2 * Math.PI, false);
                    ctx.fillStyle = getNodeColor(node);
                    ctx.fill();
                    ctx.shadowBlur = 0; // reset
                }}
                backgroundColor="transparent"
            />
        </div>
    );
}
