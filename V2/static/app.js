document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    loadDashboard();

    document.getElementById('calcBtn').addEventListener('click', calculateShares);
    document.getElementById('updateBtn').addEventListener('click', updateData);
    document.getElementById('historyBtn').addEventListener('click', loadHistoricalPortfolio);

    // Set default dates to today
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('historyDate').value = today;
    document.getElementById('calcDate').value = today;
});

let returnsChart, portfolioChart, calcPieChart;

async function loadDashboard() {
    const res = await fetch('/api/backtest');
    const data = await res.json();
    if (!data.error) {
        updateReturnsChart(data);
    }

    const pRes = await fetch('/api/portfolio');
    const pData = await pRes.json();
    updatePortfolioChart(pData.weights);
    updateTable(pData.details);
}

function initCharts() {
    const ctxR = document.getElementById('returnsChart').getContext('2d');
    returnsChart = new Chart(ctxR, {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Cumulative Return', data: [], borderColor: '#4f46e5', tension: 0.1, pointRadius: 0, borderWidth: 2, fill: false }] },
        options: { responsive: true, scales: { y: { beginAtZero: false, ticks: { color: '#f8fafc' } }, x: { ticks: { color: '#f8fafc' } } }, plugins: { legend: { labels: { color: '#f8fafc' } } } }
    });

    const ctxP = document.getElementById('portfolioChart').getContext('2d');
    portfolioChart = new Chart(ctxP, {
        type: 'pie',
        data: { labels: [], datasets: [{ data: [], backgroundColor: ['#4f46e5', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4'] }] },
        options: { responsive: true, plugins: { legend: { position: 'right', labels: { color: '#f8fafc' } } } }
    });

    const ctxC = document.getElementById('calcPieChart').getContext('2d');
    calcPieChart = new Chart(ctxC, {
        type: 'doughnut',
        data: { labels: [], datasets: [{ data: [], backgroundColor: ['#4f46e5', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4'] }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { color: '#f8fafc' } } } }
    });
}

function updateReturnsChart(data) {
    returnsChart.data.labels = data.map(d => d['Unnamed: 0'].substring(0, 10)); // Fixed incorrect CSV index key
    returnsChart.data.datasets[0].data = data.map(d => d.Cumulative);
    returnsChart.update();
}

function updatePortfolioChart(weights) {
    const labels = Object.keys(weights);
    const data = Object.values(weights).map(w => (w * 100).toFixed(2));

    portfolioChart.data.labels = labels;
    portfolioChart.data.datasets[0].data = data;
    portfolioChart.update();
}

async function loadHistoricalPortfolio() {
    const date = document.getElementById('historyDate').value;
    const pRes = await fetch(`/api/portfolio?date=${date}`);
    const data = await pRes.json();
    updatePortfolioChart(data.weights);
    updateTable(data.details);
}

function updateTable(details) {
    const tbody = document.querySelector('#holdingsTable tbody');
    tbody.innerHTML = '';

    // Fallback if backend hasn't properly attached details yet
    if (!details) return;

    for (const [code, info] of Object.entries(details)) {
        if (info.weight > 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td><span style="font-weight: 600; color: #f8fafc;">${code}</span></td>
                            <td>${info.name}</td>
                            <td>${(info.weight * 100).toFixed(2)}%</td>
                            <td>${info.price.toLocaleString()} KRW</td>`;
            tbody.appendChild(tr);
        }
    }
}

async function calculateShares() {
    const amount = document.getElementById('investAmount').value;
    const mode = document.getElementById('calcMode').value;
    const date = document.getElementById('calcDate').value;
    const res = await fetch(`/api/calculator?amount=${amount}&mode=${mode}&date=${date}`);
    const data = await res.json();

    const resultsDiv = document.getElementById('calcResults');
    resultsDiv.classList.remove('calc-results-hidden');

    // Header
    const header = document.querySelector('.calc-header');
    header.innerHTML = `<h4>Status: <span style="color: ${data.is_valid ? '#10b981' : '#ef4444'}">${data.is_valid ? '✅ Valid' : '❌ Out of Range'}</span> | Diff: ${(data.diff_pct * 100).toFixed(2)}% | Spent: ${data.total_spent.toLocaleString()} KRW</h4>`;

    // Table
    const tbody = document.querySelector('#calcTable tbody');
    tbody.innerHTML = '';

    const labels = [];
    const chartData = [];

    // Use stock capital as pie chart weight mapping for accurate representation
    for (const [code, count] of Object.entries(data.shares)) {
        if (count > 0) {
            labels.push(code);
            const capital = data.stock_capital[code] || 0;
            chartData.push(capital);

            const tr = document.createElement('tr');
            tr.innerHTML = `<td><span style="font-weight: 600; color: #f8fafc;">${code}</span></td>
                            <td>${data.names ? data.names[code] : '-'}</td>
                            <td>${count.toLocaleString()}</td>
                            <td style="color: #10b981;">${capital.toLocaleString()} KRW</td>`;
            tbody.appendChild(tr);
        }
    }

    // Update Chart
    calcPieChart.data.labels = labels;
    calcPieChart.data.datasets[0].data = chartData;
    calcPieChart.update();
}

async function updateData() {
    await fetch('/api/update', { method: 'POST' });
    alert('Update started! Please refresh in a few minutes.');
}
