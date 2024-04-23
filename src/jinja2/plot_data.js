document.addEventListener('DOMContentLoaded', function() {
    initPlotlyGraphs();
});

function initPlotlyGraphs() {
    const plotElementAssemble = document.getElementById('plot_assemble');
    if (plotElementAssemble){
        const assembleDataElement = document.getElementById('plot_assemble_data').textContent;
        const dataAssemble = JSON.parse(assembleDataElement);
        Plotly.newPlot(plotElementAssemble, dataAssemble.data, dataAssemble.layout, {scrollZoom: true});
        addZoomHandling(plotElementAssemble);
    }
    const plotElementStatistic = document.getElementById('plot_statistic');
    const statisticDataElement = document.getElementById('plot_statistic_data').textContent;
    const dataStatistic = JSON.parse(statisticDataElement);
    Plotly.newPlot(plotElementStatistic, dataStatistic.data, dataStatistic.layout);
}

function addZoomHandling(plotElement) {
    plotElement.on('plotly_afterplot', () => {
        const yAxisArea = plotElement.querySelector('.yaxislayer-above');
        if (yAxisArea) {
            yAxisArea.onwheel = debounceZoom(yAxisArea, plotElement);
        }
    });
}

function debounceZoom(yAxisArea, plotElement) {
    let timerId;
    return function(event) {
        event.preventDefault();
        if (timerId) {
            clearTimeout(timerId);
        }
        timerId = setTimeout(() => {
            applyZoom(event, plotElement);
        }, 100); // Adjust debounce rate as needed
    };
}

function applyZoom(event, plotElement) {
    const deltaY = event.deltaY * -0.005;
    const yaxis = plotElement.layout.yaxis;
    if (!yaxis) return;

    const rangeDiff = (yaxis.range[1] - yaxis.range[0]) * deltaY;
    const newRange = [yaxis.range[0] - rangeDiff, yaxis.range[1] + rangeDiff];

    Plotly.relayout(plotElement, {'yaxis.range': newRange});
}
