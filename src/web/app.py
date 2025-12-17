#!/usr/bin/env python3
"""
Interface Web pour le système de sauvegarde
Permet de visualiser, gérer et restaurer les sauvegardes via un navigateur
"""

from flask import Flask, render_template, jsonify, request, send_file, Response
from pathlib import Path
import json
import os
import sys
from datetime import datetime
import threading


# Ajouter le répertoire racine du projet au path pour les imports absolus
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.server.version_manager import VersionManager
from src.server.restore import RestoreManager

app = Flask(__name__)


from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

auth = HTTPBasicAuth()
users = {}

# Configuration
CONFIG_FILE = 'server_config.json'
backup_root = None
version_manager = None
restore_manager = None

def load_config():
    """Charge la configuration du serveur"""
    global backup_root, version_manager, restore_manager, users
    
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            backup_root = Path(config.get('backup_path', '~/backups')).expanduser()
    else:
        backup_root = Path.home() / 'backups'

    # Configuration de l'authentification
    admin_password = config.get('web_password')
    if not admin_password:
        # Mot de passe par défaut si non configuré
        default_pwd = "admin"
        users = {
            "admin": generate_password_hash(default_pwd)
        }
        print(f"⚠️  ATTENTION: Mot de passe Web par défaut utilisé ('admin'). Configurez 'web_password' dans server_config.json")
    else:
        users = {
            "admin": generate_password_hash(admin_password)
        }

    version_manager = VersionManager(backup_root)
    restore_manager = RestoreManager(backup_root)

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None

# Charger la config au démarrage
load_config()

# ============ Routes HTML ============

@app.route('/')
@auth.login_required
def index():
    """Page d'accueil avec dashboard"""
    return render_template('index.html')

@app.route('/files')
@auth.login_required
def files_page():
    """Page de liste des fichiers"""
    return render_template('files.html')


@app.route('/restore')
@auth.login_required
def restore_page():
    """Page de restauration"""
    return render_template('restore.html')

@app.route('/settings')
@auth.login_required
def settings_page():
    """Page de paramètres"""
    return render_template('settings.html')

# ============ API Routes ============


@app.route('/api/stats')
@auth.login_required
def api_stats():
    """Retourne les statistiques globales"""
    try:
        stats = version_manager.get_statistics()

        return jsonify({
            'success': True,
            'stats': {
                'total_versions': stats['total_versions'],
                'unique_files': stats['unique_files'],
                'total_size': stats['total_size'],
                'compressed_size': stats.get('compressed_total_size', stats['total_size']),
                'compression_ratio': stats.get('compression_ratio', 0),
                'space_saved': stats.get('space_saved', 0),
                'compressed_count': stats.get('compressed_count', 0),
                'deduplicated_count': stats.get('deduplicated_count', 0),
                'dedup_files': stats.get('dedup_files', 0),
                'daily_stats': stats['daily_stats']
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/files')
@auth.login_required
def api_files():
    """Liste tous les fichiers avec leurs versions"""
    try:
        import sqlite3
        conn = sqlite3.connect(version_manager.metadata_db)
        cursor = conn.cursor()

        # Obtenir tous les fichiers uniques avec leur dernière version
        cursor.execute('''
            SELECT
                file_path,
                MAX(version_timestamp) as last_modified,
                COUNT(*) as version_count,
                (SELECT file_size FROM file_versions WHERE file_path = fv.file_path
                 ORDER BY version_timestamp DESC LIMIT 1) as size,
                (SELECT action FROM file_versions WHERE file_path = fv.file_path
                 ORDER BY version_timestamp DESC LIMIT 1) as last_action
            FROM file_versions fv
            GROUP BY file_path
            ORDER BY last_modified DESC
        ''')

        files = []
        for row in cursor.fetchall():
            files.append({
                'path': row[0],
                'last_modified': row[1],
                'version_count': row[2],
                'size': row[3],
                'last_action': row[4]
            })

        conn.close()

        return jsonify({
            'success': True,
            'files': files
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/files/<path:file_path>/versions')
@auth.login_required
def api_file_versions(file_path):
    """Liste toutes les versions d'un fichier"""
    try:
        import sqlite3
        conn = sqlite3.connect(version_manager.metadata_db)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                version_timestamp,
                file_size,
                compressed_size,
                file_hash,
                action,
                is_compressed,
                is_deduplicated,
                created_at
            FROM file_versions
            WHERE file_path = ?
            ORDER BY version_timestamp DESC
        ''', (file_path,))

        versions = []
        for row in cursor.fetchall():
            versions.append({
                'timestamp': row[0],
                'size': row[1],
                'compressed_size': row[2],
                'hash': row[3],
                'action': row[4],
                'is_compressed': bool(row[5]),
                'is_deduplicated': bool(row[6]),
                'created_at': row[7]
            })

        conn.close()

        return jsonify({
            'success': True,
            'versions': versions
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/restore', methods=['POST'])
@auth.login_required
def api_restore():
    """Restaure un fichier spécifique"""
    try:
        data = request.json
        file_path = data.get('file_path')
        timestamp = data.get('timestamp')

        if not file_path or not timestamp:
            return jsonify({'success': False, 'error': 'Missing parameters'}), 400

        # Créer un dossier temporaire pour la restauration
        restore_dir = Path('/tmp/backup_restore') / datetime.now().strftime('%Y%m%d_%H%M%S')

        success = restore_manager.restore_version(file_path, timestamp, restore_dir / file_path)

        if success:
            restored_file = restore_dir / file_path
            return jsonify({
                'success': True,
                'download_url': f'/api/download/{file_path}?timestamp={timestamp}'
            })
        else:
            return jsonify({'success': False, 'error': 'Restore failed'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/download/<path:file_path>')
@auth.login_required
def api_download(file_path):
    """Télécharge un fichier restauré"""
    try:
        timestamp = request.args.get('timestamp')

        # Restaurer temporairement le fichier
        restore_dir = Path('/tmp/backup_restore') / timestamp
        restore_file = restore_dir / file_path

        if not restore_file.exists():
            restore_manager.restore_version(file_path, timestamp, restore_file)

        if restore_file.exists():
            return send_file(
                restore_file,
                as_attachment=True,
                download_name=Path(file_path).name
            )
        else:
            return jsonify({'success': False, 'error': 'File not found'}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/cleanup', methods=['POST'])
@auth.login_required
def api_cleanup():
    """Nettoie les anciennes versions"""
    try:
        data = request.json
        retention_days = data.get('retention_days', 30)
        dry_run = data.get('dry_run', False)

        if not dry_run:
            deleted_count = version_manager.cleanup_old_versions(retention_days)
            return jsonify({
                'success': True,
                'deleted_count': deleted_count,
                'message': f'{deleted_count} versions supprimées'
            })
        else:
            # Mode simulation
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            cutoff_str = cutoff_date.strftime("%Y-%m-%d_%H-%M-%S")

            versions_dir = version_manager.versions_dir
            count = 0
            size = 0

            for version_dir in sorted(versions_dir.iterdir()):
                if version_dir.is_dir() and version_dir.name < cutoff_str:
                    dir_size = sum(f.stat().st_size for f in version_dir.rglob('*') if f.is_file())
                    size += dir_size
                    count += 1

            return jsonify({
                'success': True,
                'dry_run': True,
                'would_delete': count,
                'space_to_free': size,
                'message': f'{count} versions seraient supprimées ({size / (1024*1024):.2f} MB)'
            })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search')
@auth.login_required
def api_search():
    """Recherche dans les fichiers"""
    try:
        query = request.args.get('q', '').lower()

        if not query:
            return jsonify({'success': False, 'error': 'No query provided'}), 400

        import sqlite3
        conn = sqlite3.connect(version_manager.metadata_db)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT file_path
            FROM file_versions
            WHERE file_path LIKE ?
            ORDER BY file_path
            LIMIT 50
        ''', (f'%{query}%',))

        results = [row[0] for row in cursor.fetchall()]
        conn.close()

        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/config')
@auth.login_required
def api_config():
    """Retourne la configuration actuelle"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

        return jsonify({
            'success': True,
            'config': {
                'backup_path': config.get('backup_path'),
                'compression_enabled': version_manager.enable_compression,
                'deduplication_enabled': version_manager.enable_deduplication
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def run_server(host='0.0.0.0', port=5000, debug=False):
    """Lance le serveur web"""
    print(f"\n{'='*60}")
    print(f"   Interface Web de Sauvegarde")
    print(f"{'='*60}\n")
    print(f"🌐 Serveur démarré sur: http://{host}:{port}")
    print(f"📁 Dossier de sauvegarde: {backup_root}")
    print(f"\nAppuyez sur Ctrl+C pour arrêter\n")

    app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Interface Web de Sauvegarde')
    parser.add_argument('--host', default='0.0.0.0', help='Adresse d\'écoute (défaut: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000, help='Port d\'écoute (défaut: 5000)')
    parser.add_argument('--debug', action='store_true', help='Mode debug')

    args = parser.parse_args()

    run_server(host=args.host, port=args.port, debug=args.debug)
