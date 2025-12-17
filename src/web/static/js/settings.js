// ===== Settings Page JavaScript =====

// Charger la configuration au démarrage
document.addEventListener('DOMContentLoaded', () => {
    loadConfig();
});

async function loadConfig() {
    try {
        const data = await apiCall('/api/config');
        const config = data.config;

        document.getElementById('backup-path').value = config.backup_path;
        document.getElementById('compression-enabled').checked = config.compression_enabled;
        document.getElementById('dedup-enabled').checked = config.deduplication_enabled;

        // Afficher la version Python
        document.getElementById('python-version').textContent = 'Python 3.x';
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

async function simulateCleanup() {
    const retentionDays = parseInt(document.getElementById('retention-days').value);

    if (!retentionDays || retentionDays < 1) {
        showNotification('Veuillez entrer un nombre de jours valide', 'error');
        return;
    }

    try {
        const data = await apiCall('/api/cleanup', {
            method: 'POST',
            body: JSON.stringify({
                retention_days: retentionDays,
                dry_run: true
            })
        });

        const resultsDiv = document.getElementById('cleanup-results');
        resultsDiv.style.display = 'block';
        resultsDiv.innerHTML = `
            <div class="cleanup-info">
                <h4>📊 Simulation du nettoyage</h4>
                <p><strong>${data.would_delete}</strong> versions seraient supprimées</p>
                <p><strong>${formatSize(data.space_to_free)}</strong> d'espace serait libéré</p>
                <p class="help-text">Rétention: ${retentionDays} jours</p>
            </div>
        `;

        resultsDiv.className = 'results-box info-box';
    } catch (error) {
        console.error('Cleanup simulation error:', error);
    }
}

async function performCleanup() {
    const retentionDays = parseInt(document.getElementById('retention-days').value);

    if (!retentionDays || retentionDays < 1) {
        showNotification('Veuillez entrer un nombre de jours valide', 'error');
        return;
    }

    if (!confirm(`⚠️ Attention !\n\nCette action va supprimer définitivement toutes les versions de plus de ${retentionDays} jours.\n\nÊtes-vous sûr de vouloir continuer ?`)) {
        return;
    }

    try {
        const data = await apiCall('/api/cleanup', {
            method: 'POST',
            body: JSON.stringify({
                retention_days: retentionDays,
                dry_run: false
            })
        });

        const resultsDiv = document.getElementById('cleanup-results');
        resultsDiv.style.display = 'block';
        resultsDiv.innerHTML = `
            <div class="cleanup-success">
                <h4>✓ Nettoyage terminé</h4>
                <p><strong>${data.deleted_count}</strong> versions supprimées</p>
                <p class="help-text">${data.message}</p>
            </div>
        `;

        resultsDiv.className = 'results-box success-box';
        showNotification('Nettoyage effectué avec succès !', 'success');
    } catch (error) {
        console.error('Cleanup error:', error);
    }
}

// Ajouter des styles pour les résultats
const style = document.createElement('style');
style.textContent = `
    .results-box {
        margin-top: 1rem;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border-left: 4px solid;
    }
    .info-box {
        background: #dbeafe;
        border-left-color: #3b82f6;
    }
    .info-box h4 {
        color: #1e40af;
        margin-bottom: 0.5rem;
    }
    .success-box {
        background: #d1fae5;
        border-left-color: #10b981;
    }
    .success-box h4 {
        color: #065f46;
        margin-bottom: 0.5rem;
    }
    .cleanup-info p,
    .cleanup-success p {
        margin: 0.5rem 0;
        color: #1e293b;
    }
`;
document.head.appendChild(style);
