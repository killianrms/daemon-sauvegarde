// ===== Files Page JavaScript =====

let allFiles = [];
let currentFile = null;

// Charger les fichiers au démarrage
document.addEventListener('DOMContentLoaded', () => {
    loadFiles();
});

async function loadFiles() {
    try {
        const data = await apiCall('/api/files');
        allFiles = data.files;
        displayFiles(allFiles);
    } catch (error) {
        console.error('Error loading files:', error);
        document.getElementById('files-list').innerHTML = `
            <tr><td colspan="6" class="loading" style="color: #ef4444;">
                Erreur de chargement: ${error.message}
            </td></tr>
        `;
    }
}

// Correction pour date invalide
function formatDate(timestampStr) {
    if (!timestampStr) return 'N/A';
    // Le format timestampStr est "YYYY-MM-DD_HH-MM-SS-ffffff"
    // On doit le transformer en format lisible par Date() ou le parser manuellement
    try {
        const parts = timestampStr.split('_');
        if (parts.length < 2) return timestampStr;

        const datePart = parts[0]; // YYYY-MM-DD
        const timePart = parts[1].split('-').slice(0, 3).join(':'); // HH:MM:SS

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
    // Retire ./sauvegarde/ ou sauvegarde/ du début
    return path.replace(/^(\.\/)?sauvegarde\//, '');
}

function displayFiles(files) {
    const tbody = document.getElementById('files-list');

    if (files.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="loading">Aucun fichier trouvé</td></tr>';
        return;
    }

    tbody.innerHTML = files.map(file => {
        const statusClass = file.last_action === 'deleted' ? 'danger' : 'success';
        const statusText = file.last_action === 'deleted' ? '🗑️ Supprimé' : '✓ Actif';
        const displayPath = cleanPath(file.path);

        return `
            <tr>
                <td>
                    <strong>${escapeHtml(displayPath)}</strong>
                </td>
                <td>${formatDate(file.last_modified)}</td>
                <td>
                    <span class="badge">${file.version_count} version(s)</span>
                </td>
                <td>${formatSize(file.size)}</td>
                <td>
                    <span class="status status-${statusClass}">${statusText}</span>
                </td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="viewVersions('${escapeHtml(file.path)}')">
                        📜 Détails
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteFile('${escapeHtml(file.path)}')">
                        🗑️ Tout supprimer
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

async function viewVersions(filePath) {
    currentFile = filePath;

    try {
        const data = await apiCall(`/api/files/${encodeURIComponent(filePath)}/versions`);
        const versions = data.versions;
        const displayPath = cleanPath(filePath);

        document.getElementById('modal-title').textContent = `Versions de: ${displayPath}`;

        const versionsList = document.getElementById('versions-list');
        versionsList.innerHTML = versions.map(version => {
            const actionIcon = version.action === 'deleted' ? '🗑️' : version.action === 'modified' ? '✏️' : '➕';
            const compressionInfo = version.is_compressed ? '📦 Compressé' : '';
            const dedupInfo = version.is_deduplicated ? '⚡ Dédupliqué' : '';

            return `
                <div class="version-item">
                    <div class="version-header">
                        <span class="version-date">${actionIcon} ${formatDate(version.timestamp)}</span>
                        <span class="version-action">${version.action}</span>
                    </div>
                    <div class="version-details">
                        <span>Taille: ${formatSize(version.size)}</span>
                        ${version.compressed_size ? `<span>Stocké: ${formatSize(version.compressed_size)}</span>` : ''}
                        ${compressionInfo ? `<span class="badge badge-success">${compressionInfo}</span>` : ''}
                        ${dedupInfo ? `<span class="badge badge-info">${dedupInfo}</span>` : ''}
                    </div>
                    <div class="version-actions">
                        <button class="btn btn-sm btn-success" onclick="restoreFile('${escapeHtml(filePath)}', '${version.timestamp}')">
                            🔄 Restaurer
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="deleteVersion('${escapeHtml(filePath)}', '${version.timestamp}')">
                            🗑️ Supprimer cette version
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        document.getElementById('versions-modal').style.display = 'block';
    } catch (error) {
        console.error('Error loading versions:', error);
    }
}

async function deleteFile(filePath) {
    if (!confirm(`Etes-vous sûr de vouloir supprimer TOUT l'historique de "${cleanPath(filePath)}" ?\nCette action est irréversible.`)) {
        return;
    }

    try {
        await apiCall('/api/delete', {
            method: 'POST',
            body: JSON.stringify({
                file_path: filePath,
                delete_all: true
            })
        });

        showNotification('Fichier et historique supprimés !', 'success');
        loadFiles(); // Recharger la liste
    } catch (error) {
        console.error('Delete error:', error);
        showNotification('Erreur lors de la suppression: ' + error.message, 'error');
    }
}

async function deleteVersion(filePath, timestamp) {
    if (!confirm('Voulez-vous vraiment supprimer cette version ?')) {
        return;
    }

    try {
        await apiCall('/api/delete', {
            method: 'POST',
            body: JSON.stringify({
                file_path: filePath,
                timestamp: timestamp
            })
        });

        showNotification('Version supprimée !', 'success');
        viewVersions(filePath); // Rafraîchir la liste des versions
        loadFiles(); // Rafraîchir aussi la liste principale (compteurs)
    } catch (error) {
        console.error('Delete version error:', error);
        showNotification('Erreur suppression version: ' + error.message, 'error');
    }
}

async function restoreFile(filePath, timestamp) {
    if (!confirm(`Voulez-vous restaurer cette version de "${cleanPath(filePath)}" ?`)) {
        return;
    }

    try {
        const data = await apiCall('/api/restore', {
            method: 'POST',
            body: JSON.stringify({
                file_path: filePath,
                timestamp: timestamp
            })
        });

        showNotification('Fichier restauré avec succès !', 'success');

        // Proposer le téléchargement
        if (data.download_url) {
            const link = document.createElement('a');
            link.href = data.download_url;
            link.click();
        }

        closeModal();
    } catch (error) {
        console.error('Restore error:', error);
    }
}

function closeModal() {
    document.getElementById('versions-modal').style.display = 'none';
}

function searchFiles() {
    const query = document.getElementById('search-input').value.toLowerCase();

    if (!query) {
        displayFiles(allFiles);
        return;
    }

    const filtered = allFiles.filter(file =>
        file.path.toLowerCase().includes(query)
    );

    displayFiles(filtered);
}

async function refreshFiles() {
    showNotification('Actualisation en cours...', 'info');
    await loadFiles();
    showNotification('Liste actualisée !', 'success');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Fermer le modal en cliquant en dehors
window.onclick = function (event) {
    const modal = document.getElementById('versions-modal');
    if (event.target === modal) {
        closeModal();
    }
}

// Ajouter des styles pour les versions
const style = document.createElement('style');
style.textContent = `
    .version-item {
        background: #f8fafc;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0.5rem;
        border-left: 4px solid #3b82f6;
    }
    .version-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.5rem;
    }
    .version-date {
        font-weight: 600;
        color: #1e293b;
    }
    .version-action {
        padding: 0.25rem 0.75rem;
        background: #e2e8f0;
        border-radius: 0.25rem;
        font-size: 0.875rem;
    }
    .version-details {
        display: flex;
        gap: 1rem;
        margin: 0.5rem 0;
        font-size: 0.875rem;
        color: #64748b;
    }
    .version-actions {
        margin-top: 0.75rem;
    }
    .badge {
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-success {
        background: #10b981;
        color: white;
    }
    .badge-info {
        background: #3b82f6;
        color: white;
    }
    .status {
        padding: 0.25rem 0.75rem;
        border-radius: 0.25rem;
        font-size: 0.875rem;
    }
    .status-success {
        background: #d1fae5;
        color: #065f46;
    }
    .status-danger {
        background: #fee2e2;
        color: #991b1b;
    }
`;
document.head.appendChild(style);
