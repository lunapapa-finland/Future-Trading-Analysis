// Functions for button interactions
function toggleAllTrades() {
    const plotElement = document.getElementById('plot_assemble');
    const statisticElement = document.getElementById('plot_statistic');
    if (plotElement){
        const tradingTracesStartIndex = 86;
        const tradingTracesEndIndex = plotElement.data.length - 1;

        // Toggle visibility for trading traces
        for (let i = tradingTracesStartIndex; i <= tradingTracesEndIndex; i++) {
            const currentVisibility = plotElement.data[i].visible;
            const newVisibility = (currentVisibility === 'legendonly' ? true : 'legendonly');
            Plotly.restyle(plotElement, {'visible': newVisibility}, [i]);
        }
    }

    // Toggle visibility of the entire statistics plot
    statisticElement.style.display = (statisticElement.style.display === 'none' ? 'block' : 'none');
}

function toggleSummary() {
    const summaryElement = document.getElementById('plot_summary');
    summaryElement.style.display = (summaryElement.style.display === 'none' ? 'block' : 'none');
}

function synchronizeAnnotations() {
    const plotElement = document.getElementById('plot_assemble');
    if (!plotElement) return;
    const offset = 5;  // Specific offset based on plot configuration
    const updatedAnnotations = plotElement.layout.annotations.map((ann, idx) => {
        const traceIndex = idx + offset;
        if (plotElement.data[traceIndex] && plotElement.data[traceIndex].visible === 'legendonly') {
            return {...ann, visible: false};
        } else if (plotElement.data[traceIndex]) {
            return {...ann, visible: true};
        }
        return ann;
    });

    Plotly.relayout(plotElement, {'annotations': updatedAnnotations});
}

// Periodically synchronize annotations
setInterval(synchronizeAnnotations, 500);  // Adjust time as needed

function replayCandlesticks() {
    const plotElement = document.getElementById('plot_assemble');
    if (!plotElement) return;
    const allCandleTraces = plotElement.data.filter(trace => trace.name.startsWith("Candle"));
    const anyVisible = allCandleTraces.some(trace => trace.visible !== 'legendonly');
    const newVisibility = anyVisible ? 'legendonly' : true;
    const traceIndices = allCandleTraces.map(trace => plotElement.data.indexOf(trace));

    Plotly.restyle(plotElement, {'visible': newVisibility}, traceIndices);
}

function initializeVisibility() {
    const plotElement = document.getElementById('plot_assemble');
    if (plotElement){
        // Start with all trading traces hidden
        const tradingTracesStartIndex = 86;
        const tradingTracesEndIndex = plotElement.data.length - 1;
        for (let i = tradingTracesStartIndex; i <= tradingTracesEndIndex; i++) {
            Plotly.restyle(plotElement, {'visible': 'legendonly'}, [i]);
        }

    }
    const statisticElement = document.getElementById('plot_statistic');

}

// Initialize visibility on document load
document.addEventListener('DOMContentLoaded', initializeVisibility);

function resizePlot() {
    const width = window.innerWidth * 0.95;
    const height = window.innerHeight * 0.95;
    const plotElementAssemble = document.getElementById('plot_assemble')
    const plotElementStatistic = document.getElementById('plot_statistic')
    const plotElementSummary = document.getElementById('plot_summary')
    if (!plotElementAssemble){
        plotElements = [plotElementAssemble, plotElementStatistic, plotElementSummary];
    }
    else{
        plotElements = [plotElementStatistic, plotElementSummary];
    }

    plotElements.forEach(function(elem) {
        if (elem && typeof Plotly !== 'undefined' && elem.data) {
            elem.style.width = `${width}px`;
            elem.style.height = `${height}px`;
            Plotly.relayout(elem, {width: width, height: height}).catch(error => {
                console.error("Failed to resize plot:", error);
            });
        }
    });
}

window.onresize = resizePlot;
window.onload = resizePlot;

