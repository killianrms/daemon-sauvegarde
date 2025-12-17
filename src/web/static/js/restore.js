// ===== Restore Page JavaScript =====

let selectedFile = null;

// Définir la date max à aujourd'hui
document.addEventListener('DOMContentLoaded', () => {
    const today = new Date().toISOString().split('T')[0];
    const dateInput = document.getElementById('restore-date');
    if (dateInput) {
        dateInput.max = today;
        dateInput.value = today;
    }
});

// Correction pour date invalide
function formatDate(timestampStr) {
    if (!timestampStr) return 'N/A';
    try {
        const parts = timestampStr.split('_');
        if (parts.length < 2) return timestampStr;

        const datePart = parts[0];
        const timePart = parts[1].split('-').slice(0, 3).join(':');

        const date = new Date(`${datePart}T${timePart}`);

        return new Intl.DateTimeFormat('fr-FR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        }).format(date);
    } catch (e) {
        return timestampStr;
    }
}

function cleanPath(path) {
    return path.replace(/^(\.\/)?sauvegarde\//, '');
}

async function searchFilesForRestore() {
    const query = document.getElementById('file-search').value.toLowerCase();

    if (query.length < 2) {
        document.getElementById('file-results').innerHTML = '';
        return;
    }

    try {
        const data = await apiCall(`/api/search?q=${encodeURIComponent(query)}`);
        const results = data.results;

        const resultsDiv = document.getElementById('file-results');
        resultsDiv.innerHTML = results.map(filePath => `
            <div class="search-result-item" onclick="selectFileForRestore('${escapeHtml(filePath)}')">
                📄 ${escapeHtml(cleanPath(filePath))}
            </div>
        `).join('');
    } catch (error) {
        console.error('Search error:', error);
    }
}

async function selectFileForRestore(filePath) {
    selectedFile = filePath;
    document.getElementById('file-search').value = cleanPath(filePath); // Affiche le chemin propre
    document.getElementById('file-results').innerHTML = '';

    // Charger les versions
    try {
        const data = await apiCall(`/api/files/${encodeURIComponent(filePath)}/versions`);
        const versions = data.versions;

        const timeline = document.getElementById('versions-timeline');
        timeline.innerHTML = versions.map(version => {
            const isRestorable = version.size > 0;
            const restoreBtn = isRestorable
                ? `<button class="btn btn-sm btn-primary" onclick="restoreFileVersion('${escapeHtml(filePath)}', '${version.timestamp}')">🔄 Restaurer cette version</button>`
                : `<button class="btn btn-sm btn-secondary" disabled title="Fichier vide">🚫 Vide</button>`;

            return `
                <div class="timeline-item">
                    <div class="timeline-marker"></div>
                    <div class="timeline-content">
                        <div class="timeline-header">
                            <strong>${formatDate(version.timestamp)}</strong>
                            <span class="version-badge">${version.action}</span>
                        </div>
                        <div class="timeline-details">
                            Taille: ${formatSize(version.size)}
                            ${version.is_compressed ? ' • 📦 Compressé' : ''}
                            ${version.is_deduplicated ? ' • ⚡ Dédupliqué' : ''}
                        </div>
                        ${restoreBtn}
                    </div>
                </div>
            `;
        }).join('');

        document.getElementById('selected-file-versions').style.display = 'block';
    } catch (error) {
        console.error('Error loading versions:', error);
    }
}

async function restoreFileVersion(filePath, timestamp) {
    if (!confirm(`Voulez-vous restaurer cette version de "${filePath}" ?`)) {
        return;
    }

    showProgress(true, 'Restauration en cours...');

    try {
        const data = await apiCall('/api/restore', {
            method: 'POST',
            body: JSON.stringify({
                file_path: filePath,
                timestamp: timestamp
            })
        });

        showProgress(false);
        showResults(true, `Fichier restauré avec succès !`, data.download_url, filePath);
    } catch (error) {
        showProgress(false);
        showNotification(`Erreur: ${error.message}`, 'error');
    }
}

async function restoreAtDate() {
    const date = document.getElementById('restore-date').value;

    if (!date) {
        showNotification('Veuillez sélectionner une date', 'error');
        return;
    }

    if (!confirm(`Voulez-vous restaurer tous les fichiers à la date du ${date} ?`)) {
        return;
    }

    showProgress(true, 'Restauration de tous les fichiers en cours...');

    // Simulation pour l'instant
    setTimeout(() => {
        showProgress(false);
        showResults(true, `Tous les fichiers ont été restaurés à la date du ${date}`, null, null);
    }, 2000);
}

function showProgress(show, text = '') {
    const progressDiv = document.getElementById('restore-progress');
    progressDiv.style.display = show ? 'block' : 'none';

    if (show) {
        document.getElementById('progress-text').textContent = text;
        // Animer la barre de progression
        let progress = 0;
        const interval = setInterval(() => {
            progress += 10;
            document.getElementById('progress-bar-fill').style.width = progress + '%';
            if (progress >= 100) clearInterval(interval);
        }, 200);
    }
}

function showResults(show, text = '', downloadUrl = null, fileName = null) {
    const resultsDiv = document.getElementById('restore-results');
    resultsDiv.style.display = show ? 'block' : 'none';

    if (show) {
        document.getElementById('results-text').textContent = text;

        if (downloadUrl && fileName) {
            document.getElementById('download-links').innerHTML = `
                <a href="${downloadUrl}" class="btn btn-success" download>
                    ⬇️ Télécharger ${fileName}
                </a>
            `;
        }
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Ajouter des styles pour la timeline et les résultats
const style = document.createElement('style');
style.textContent = `
    .search-results {
        max-height: 300px;
        overflow-y: auto;
        border: 2px solid #e2e8f0;
        border-radius: 0.5rem;
        margin-top: 0.5rem;
    }
    .search-result-item {
        padding: 0.75rem 1rem;
        cursor: pointer;
        border-bottom: 1px solid #e2e8f0;
        transition: background 0.2s;
    }
    .search-result-item:hover {
        background: #f8fafc;
    }
    .versions-container {
        margin-top: 1.5rem;
        padding: 1.5rem;
        background: #f8fafc;
        border-radius: 0.5rem;
    }
    .timeline-item {
        position: relative;
        padding-left: 2rem;
        padding-bottom: 2rem;
        border-left: 2px solid #e2e8f0;
    }
    .timeline-item:last-child {
        border-left: none;
    }
    .timeline-marker {
        position: absolute;
        left: -6px;
        top: 0;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: #3b82f6;
    }
    .timeline-content {
        background: white;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }
    .timeline-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.5rem;
    }
    .version-badge {
        padding: 0.25rem 0.75rem;
        background: #e2e8f0;
        border-radius: 0.25rem;
        font-size: 0.875rem;
    }
    .timeline-details {
        color: #64748b;
        font-size: 0.875rem;
        margin: 0.5rem 0;
    }
    .results-container {
        background: #d1fae5;
        border: 2px solid #10b981;
        padding: 2rem;
        border-radius: 0.75rem;
        text-align: center;
    }
    .results-container h3 {
        color: #065f46;
        margin-bottom: 1rem;
    }
    #download-links {
        margin-top: 1rem;
    }
`;
document.head.appendChild(style);
