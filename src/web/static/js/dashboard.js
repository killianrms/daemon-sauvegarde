// ===== Dashboard JavaScript =====

let statsData = null;

// Charger les statistiques au démarrage
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
});

async function loadStats() {
    try {
        const data = await apiCall('/api/stats');
        statsData = data.stats;
        updateDashboard(statsData);
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

function updateDashboard(stats) {
    // Mettre à jour les cartes de statistiques
    document.getElementById('total-versions').textContent = stats.total_versions.toLocaleString();
    document.getElementById('unique-files').textContent = stats.unique_files.toLocaleString();
    document.getElementById('total-size').textContent = formatSize(stats.total_size);
    document.getElementById('compression-ratio').textContent = stats.compression_ratio.toFixed(1) + '%';
    document.getElementById('space-saved').textContent = formatSize(stats.space_saved);
    document.getElementById('dedup-count').textContent = stats.deduplicated_count.toLocaleString();

    // Mettre à jour les barres de stockage
    const compressionRatio = stats.compressed_size / stats.total_size;
    document.getElementById('bar-compressed').style.width = (compressionRatio * 100) + '%';
    document.getElementById('size-original').textContent = formatSize(stats.total_size);
    document.getElementById('size-compressed').textContent = formatSize(stats.compressed_size);

    // Créer le graphique d'activité
    createActivityChart(stats.daily_stats);
}

function createActivityChart(dailyStats) {
    const canvas = document.getElementById('activityCanvas');
    const ctx = canvas.getContext('2d');

    // Préparer les données (les 7 derniers jours)
    const last7Days = dailyStats.slice(0, 7).reverse();
    const labels = last7Days.map(stat => {
        const date = new Date(stat[0]);
        return date.toLocaleDateString('fr-FR', { month: 'short', day: 'numeric' });
    });
    const values = last7Days.map(stat => stat[1]);

    // Dessiner le graphique simple
    canvas.width = canvas.offsetWidth;
    canvas.height = 200;

    const maxValue = Math.max(...values, 1);
    const barWidth = canvas.width / values.length;
    const padding = 20;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Dessiner les barres
    values.forEach((value, index) => {
        const barHeight = (value / maxValue) * (canvas.height - 40);
        const x = index * barWidth + 10;
        const y = canvas.height - barHeight - padding;

        // Gradient pour les barres
        const gradient = ctx.createLinearGradient(0, y, 0, canvas.height - padding);
        gradient.addColorStop(0, '#667eea');
        gradient.addColorStop(1, '#764ba2');

        ctx.fillStyle = gradient;
        ctx.fillRect(x, y, barWidth - 20, barHeight);

        // Labels
        ctx.fillStyle = '#64748b';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(labels[index], x + (barWidth - 20) / 2, canvas.height - 5);

        // Valeurs
        ctx.fillStyle = '#1e293b';
        ctx.font = 'bold 14px sans-serif';
        ctx.fillText(value, x + (barWidth - 20) / 2, y - 5);
    });
}

async function refreshStats() {
    showNotification('Actualisation en cours...', 'info');
    await loadStats();
    showNotification('Statistiques actualisées !', 'success');
}

async function runCleanup() {
    if (!confirm('Voulez-vous nettoyer les versions de plus de 30 jours ?')) {
        return;
    }

    try {
        const data = await apiCall('/api/cleanup', {
            method: 'POST',
            body: JSON.stringify({
                retention_days: 30,
                dry_run: false
            })
        });

        showNotification(data.message, 'success');
        await loadStats();
    } catch (error) {
        console.error('Cleanup error:', error);
    }
}
