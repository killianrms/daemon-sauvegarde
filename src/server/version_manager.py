#!/usr/bin/env python3
"""
Gestionnaire de versions pour le serveur de sauvegarde
Gère l'historique des fichiers avec rétention de 30 jours
Avec compression et déduplication
"""

import os
import sys
import json
import shutil

import sqlite3
import gzip
from datetime import datetime, timedelta
from pathlib import Path
import hashlib


try:
    from .cleanup import *
except ImportError:
    # Fallback/Direct execution
    # If running as script, 'cleanup' might be in same dir
    try:
        from cleanup import *
    except ImportError:
         print("Warning: Could not import cleanup module")
import hashlib
# ... (preserve other imports)

# Correction: Import EncryptionManager
try:
    from src.common.encryption import EncryptionManager
except ImportError:
    # Fallback if running from a different context
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from src.common.encryption import EncryptionManager

class VersionManager:
    """Gestionnaire de versions de fichiers"""

    def __init__(self, backup_root, enable_compression=True, enable_deduplication=True, enable_encryption=True, encryption_password=None):
        self.backup_root = Path(backup_root).expanduser()
        self.current_dir = self.backup_root / "current"
        self.versions_dir = self.backup_root / "versions"
        self.dedup_dir = self.backup_root / "dedup_store"
        self.metadata_db = self.backup_root / "metadata.db"

        self.enable_compression = enable_compression
        self.enable_deduplication = enable_deduplication
        self.enable_encryption = enable_encryption
        
        # Initialiser le chiffrement
        self.encryption_manager = None
        if self.enable_encryption:
            self.encryption_manager = EncryptionManager(password=encryption_password)

        # Créer les répertoires
        self.current_dir.mkdir(parents=True, exist_ok=True)
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        if self.enable_deduplication:
            self.dedup_dir.mkdir(parents=True, exist_ok=True)

        # Initialiser la base de données
        self.init_database()

    def init_database(self):
        """Initialise la base de données SQLite pour les métadonnées"""
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()

        cursor.execute('''

            CREATE TABLE IF NOT EXISTS file_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                version_timestamp TEXT NOT NULL,
                version_path TEXT NOT NULL,
                file_size INTEGER,
                compressed_size INTEGER,
                file_hash TEXT,
                dedup_ref TEXT,
                is_compressed BOOLEAN DEFAULT 0,
                is_deduplicated BOOLEAN DEFAULT 0,
                is_encrypted BOOLEAN DEFAULT 0,
                encryption_metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                action TEXT DEFAULT 'modified'
            )
        ''')

        # Check/Add optional columns for existing DBs
        try:
            cursor.execute("ALTER TABLE file_versions ADD COLUMN is_encrypted BOOLEAN DEFAULT 0")
            cursor.execute("ALTER TABLE file_versions ADD COLUMN encryption_metadata TEXT")
        except sqlite3.OperationalError:
            pass # Columns likely exist

        # Table pour la déduplication
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dedup_store (
                file_hash TEXT PRIMARY KEY,
                dedup_path TEXT NOT NULL,
                original_size INTEGER,
                compressed_size INTEGER,
                is_encrypted BOOLEAN DEFAULT 0,
                encryption_metadata TEXT,
                ref_count INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        try:
            cursor.execute("ALTER TABLE dedup_store ADD COLUMN is_encrypted BOOLEAN DEFAULT 0")
            cursor.execute("ALTER TABLE dedup_store ADD COLUMN encryption_metadata TEXT")
        except sqlite3.OperationalError:
            pass

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_file_path
            ON file_versions(file_path)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON file_versions(version_timestamp)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_file_hash
            ON file_versions(file_hash)
        ''')

        conn.commit()
        conn.close()

    def calculate_hash(self, file_path):
        """Calcule le hash SHA256 d'un fichier"""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            print(f"Erreur lors du calcul du hash: {e}")
            return None

    def compress_file(self, source_path, dest_path):
        """Compresse un fichier avec gzip"""
        try:
            with open(source_path, 'rb') as f_in:
                with gzip.open(str(dest_path) + '.gz', 'wb', compresslevel=6) as f_out:
                    shutil.copyfileobj(f_in, f_out)
            return str(dest_path) + '.gz'
        except Exception as e:
            print(f"Erreur lors de la compression: {e}")
            # En cas d'erreur, copier sans compression
            shutil.copy2(source_path, dest_path)
            return str(dest_path)

    def decompress_file(self, source_path, dest_path):
        """Décompresse un fichier gzip"""
        try:
            with gzip.open(source_path, 'rb') as f_in:
                with open(dest_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            return True
        except Exception as e:
            print(f"Erreur lors de la décompression: {e}")
            return False


    def get_or_create_dedup_file(self, file_path, file_hash, file_size):
        """Vérifie si le fichier existe déjà (déduplication) ou le crée. 
           Retourne (dedup_path, existed, encryption_metadata)"""
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()

        # Vérifier si le hash existe déjà
        cursor.execute('SELECT dedup_path, ref_count, encryption_metadata FROM dedup_store WHERE file_hash = ?', (file_hash,))
        result = cursor.fetchone()

        if result:
            # Fichier déjà présent, incrémenter le compteur
            dedup_path, ref_count, enc_meta_json = result
            cursor.execute('UPDATE dedup_store SET ref_count = ref_count + 1 WHERE file_hash = ?', (file_hash,))
            conn.commit()
            conn.close()
            print(f"  ⚡ Déduplication: fichier déjà présent (économie: {file_size / 1024:.2f} KB)")
            enc_meta = json.loads(enc_meta_json) if enc_meta_json else None
            return dedup_path, True, enc_meta
        else:
            # Nouveau fichier, le sauvegarder dans dedup_store
            dedup_path = self.dedup_dir / file_hash[:2] / file_hash[2:4] / file_hash
            dedup_path.parent.mkdir(parents=True, exist_ok=True)

            # --- PIPELINE: Compression -> Encryption ---
            

            # 1. Compression
            temp_path = dedup_path
            compressed_size = file_size
            
            if self.enable_compression:
                # compress_file ajoute .gz
                temp_path = Path(self.compress_file(file_path, dedup_path))
                compressed_size = temp_path.stat().st_size
                ratio = (1 - compressed_size / file_size) * 100 if file_size > 0 else 0
                print(f"  📦 Compression: {file_size / 1024:.2f} KB → {compressed_size / 1024:.2f} KB ({ratio:.1f}%)")
            else:
                shutil.copy2(file_path, temp_path)
            
            # 2. Chiffrement
            encryption_metadata = None
            final_path = temp_path
            is_encrypted = False
            
            if self.enable_encryption and self.encryption_manager:
                enc_path = Path(str(temp_path) + '.enc')
                encryption_metadata = self.encryption_manager.encrypt_file(temp_path, enc_path)
                
                # Delete temp
                if temp_path != dedup_path and temp_path.exists(): # if gz
                     temp_path.unlink()
                if temp_path == dedup_path and dedup_path.exists(): # if no compression
                     dedup_path.unlink()
                
                final_path = enc_path
                compressed_size = final_path.stat().st_size # Update size to encrypted size
                is_encrypted = True

            # Get relative path for DB
            # Note: final_path includes extension (.gz.enc), we need to store relatve path
            rel_path = str(final_path.relative_to(self.backup_root))
            meta_json = json.dumps(encryption_metadata) if encryption_metadata else None

            # Enregistrer dans la base
            cursor.execute('''
                INSERT INTO dedup_store (file_hash, dedup_path, original_size, compressed_size, ref_count, is_encrypted, encryption_metadata)
                VALUES (?, ?, ?, ?, 1, ?, ?)
            ''', (file_hash, rel_path, file_size, compressed_size, is_encrypted, meta_json))
            conn.commit()
            conn.close()

            return rel_path, False, encryption_metadata


    def save_version(self, file_path, relative_path):
        """Sauvegarde une version d'un fichier avec compression, déduplication et chiffrement"""
        try:
            # Chemin du fichier actuel (cache pour hash comparison)
            current_file = self.current_dir / relative_path
            current_file.parent.mkdir(parents=True, exist_ok=True)

            # Calculer le hash du nouveau fichier entrant
            new_hash = self.calculate_hash(file_path)
            new_size = Path(file_path).stat().st_size

            # Vérifier si le fichier existe déjà et s'il a changé
            is_new_file = not current_file.exists()
            if not is_new_file:
                old_hash = self.calculate_hash(current_file)
                if old_hash == new_hash:
                    # print(f"⊘ Fichier inchangé: {relative_path}")
                    return True

            # --- Création de la nouvelle version (Archivage du NOUVEAU fichier) ---
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
            
            # Variables pour les métadonnées
            version_path = None
            compressed_size = None
            is_compressed = self.enable_compression
            is_deduplicated = False
            dedup_ref = None
            is_encrypted = self.enable_encryption
            encryption_metadata = None

            # 1. Gestion avec Déduplication
            if self.enable_deduplication:
                # On stocke le fichier entrant (file_path)
                dedup_ref, was_dedup, enc_meta = self.get_or_create_dedup_file(file_path, new_hash, new_size)
                is_deduplicated = True
                encryption_metadata = enc_meta
                # Si dédupliqué, on n'a pas de fichier physique dans versions/, juste une ref.
                # Mais pour l'UI, on veut savoir "où" c'est ? C'est dans dedup_store.
                version_path = dedup_ref 
                
            else:
                # 2. Mode traditionnel (stockage complet dans versions/)
                version_subdir = self.versions_dir / timestamp
                version_subdir.mkdir(parents=True, exist_ok=True)
                version_file = version_subdir / relative_path
                version_file.parent.mkdir(parents=True, exist_ok=True)

                # Compression
                temp_path = version_file
                if self.enable_compression:
                    temp_path = Path(self.compress_file(file_path, version_file))
                    is_compressed = True
                else:
                    shutil.copy2(file_path, temp_path)

                # Chiffrement
                final_path = temp_path
                if self.enable_encryption and self.encryption_manager:
                    enc_path = Path(str(temp_path) + '.enc')
                    encryption_metadata = self.encryption_manager.encrypt_file(temp_path, enc_path)
                    
                    if temp_path.exists():
                        temp_path.unlink()
                        
                    final_path = enc_path
                    is_encrypted = True
                
                version_path = str(final_path.relative_to(self.backup_root))
                compressed_size = final_path.stat().st_size

            # Enregistrement en base de données
            self.record_version(
                relative_path,
                timestamp,
                version_path, 
                new_size,
                new_hash,
                'modified' if not is_new_file else 'created',
                is_compressed=is_compressed,
                is_deduplicated=is_deduplicated,
                dedup_ref=dedup_ref,
                is_encrypted=is_encrypted,
                encryption_metadata=encryption_metadata
            )

            print(f"✓ Version sauvegardée: {relative_path}")

            # Mettre à jour le fichier 'current' (en clair) pour les futures comparaisons
            # Note: On écrase l'ancien sans l'archiver car on vient d'archiver le NOUVEAU.
            # L'ancien est censé avoir été archivé lors de son arrivée précédente.
            shutil.copy2(file_path, current_file)
            
            return True

        except Exception as e:
            print(f"✗ Erreur lors de la sauvegarde de version: {e}")
            import traceback
            traceback.print_exc()
            return False


    def record_version(self, file_path, timestamp, version_path, file_size, file_hash, action,
                      compressed_size=None, is_compressed=False, is_deduplicated=False, dedup_ref=None,
                      is_encrypted=False, encryption_metadata=None):
        """Enregistre une version dans la base de données"""
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()
        

        meta_json = json.dumps(encryption_metadata) if encryption_metadata else None

        cursor.execute('''
            INSERT INTO file_versions
            (file_path, version_timestamp, version_path, file_size, compressed_size,
             file_hash, dedup_ref, is_compressed, is_deduplicated, is_encrypted, encryption_metadata, action)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (file_path, timestamp, version_path, file_size, compressed_size,
              file_hash, dedup_ref, is_compressed, is_deduplicated, is_encrypted, meta_json, action))

        conn.commit()
        conn.close()

    def delete_file(self, relative_path):
        """Supprime un fichier (garde une version avant suppression)"""
        try:
            current_file = self.current_dir / relative_path

            if current_file.exists():
                # Créer une version de suppression
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
                version_subdir = self.versions_dir / timestamp
                version_subdir.mkdir(parents=True, exist_ok=True)

                version_file = version_subdir / relative_path
                version_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(current_file, version_file)

                file_hash = self.calculate_hash(current_file)
                file_size = current_file.stat().st_size

                # Enregistrer la suppression
                self.record_version(
                    relative_path,
                    timestamp,
                    str(version_file.relative_to(self.backup_root)),
                    file_size,
                    file_hash,
                    'deleted'
                )

                # Supprimer le fichier actuel
                current_file.unlink()
                print(f"✓ Fichier supprimé (version sauvegardée): {relative_path}")

            return True
        except Exception as e:
            print(f"✗ Erreur lors de la suppression: {e}")
            return False

    def cleanup_old_versions(self, retention_days=30):
        """Nettoie les versions plus anciennes que retention_days"""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d_%H-%M-%S")

        deleted_count = 0
        deleted_size = 0

        print(f"Nettoyage des versions antérieures au {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}...")

        # Parcourir les répertoires de versions
        for version_dir in sorted(self.versions_dir.iterdir()):
            if version_dir.is_dir() and version_dir.name < cutoff_str:
                # Calculer la taille
                dir_size = sum(f.stat().st_size for f in version_dir.rglob('*') if f.is_file())
                deleted_size += dir_size

                # Supprimer le répertoire
                shutil.rmtree(version_dir)
                deleted_count += 1
                print(f"  ✓ Supprimé: {version_dir.name}")

        # Nettoyer la base de données
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM file_versions
            WHERE version_timestamp < ?
        ''', (cutoff_str,))
        db_deleted = cursor.rowcount
        conn.commit()
        conn.close()

        print(f"\n✓ Nettoyage terminé:")
        print(f"  - {deleted_count} répertoires de versions supprimés")
        print(f"  - {deleted_size / (1024*1024):.2f} MB libérés")
        print(f"  - {db_deleted} entrées supprimées de la base de données")

        return deleted_count

    def list_versions(self, file_path=None):
        """Liste toutes les versions disponibles"""
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()

        if file_path:
            cursor.execute('''
                SELECT file_path, version_timestamp, file_size, action, created_at
                FROM file_versions
                WHERE file_path = ?
                ORDER BY version_timestamp DESC
            ''', (file_path,))
        else:
            cursor.execute('''
                SELECT file_path, version_timestamp, file_size, action, created_at
                FROM file_versions
                ORDER BY version_timestamp DESC
                LIMIT 100
            ''')

        versions = cursor.fetchall()
        conn.close()

        return versions

    def get_version_path(self, file_path, timestamp):
        """Obtient le chemin complet d'une version spécifique"""
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT version_path
            FROM file_versions
            WHERE file_path = ? AND version_timestamp = ?
        ''', (file_path, timestamp))

        result = cursor.fetchone()
        conn.close()

        if result:
            return self.backup_root / result[0]
        return None

    def get_statistics(self):
        """Obtient des statistiques sur les sauvegardes"""
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()

        # Nombre total de versions
        cursor.execute('SELECT COUNT(*) FROM file_versions')
        total_versions = cursor.fetchone()[0]

        # Nombre de fichiers uniques
        cursor.execute('SELECT COUNT(DISTINCT file_path) FROM file_versions')
        unique_files = cursor.fetchone()[0]

        # Taille totale sans compression
        cursor.execute('SELECT SUM(file_size) FROM file_versions')
        total_size = cursor.fetchone()[0] or 0

        # Taille totale avec compression
        cursor.execute('SELECT SUM(COALESCE(compressed_size, file_size)) FROM file_versions')
        compressed_total_size = cursor.fetchone()[0] or 0

        # Statistiques de compression
        cursor.execute('SELECT COUNT(*) FROM file_versions WHERE is_compressed = 1')
        compressed_count = cursor.fetchone()[0]

        # Statistiques de déduplication
        cursor.execute('SELECT COUNT(*) FROM file_versions WHERE is_deduplicated = 1')
        deduplicated_count = cursor.fetchone()[0]

        # Nombre de fichiers uniques dans dedup_store
        cursor.execute('SELECT COUNT(*), SUM(original_size), SUM(compressed_size) FROM dedup_store')
        dedup_result = cursor.fetchone()
        dedup_files = dedup_result[0] or 0
        dedup_original_size = dedup_result[1] or 0
        dedup_compressed_size = dedup_result[2] or 0

        # Versions par jour (derniers 30 jours)
        cursor.execute('''
            SELECT DATE(created_at) as day, COUNT(*) as count
            FROM file_versions
            WHERE created_at >= date('now', '-30 days')
            GROUP BY day
            ORDER BY day DESC
        ''')
        daily_stats = cursor.fetchall()

        conn.close()

        # Calculs d'économie
        compression_ratio = (1 - compressed_total_size / total_size) * 100 if total_size > 0 else 0
        space_saved = total_size - compressed_total_size

        return {
            'total_versions': total_versions,
            'unique_files': unique_files,
            'total_size': total_size,
            'compressed_total_size': compressed_total_size,
            'compression_ratio': compression_ratio,
            'space_saved': space_saved,
            'compressed_count': compressed_count,
            'deduplicated_count': deduplicated_count,
            'dedup_files': dedup_files,
            'dedup_original_size': dedup_original_size,
            'dedup_compressed_size': dedup_compressed_size,
            'daily_stats': daily_stats
        }


def main():
    """Fonction principale pour les tests"""
    if len(sys.argv) < 2:
        print("Usage: python3 version_manager.py <backup_root>")
        sys.exit(1)

    backup_root = sys.argv[1]
    vm = VersionManager(backup_root)

    # Afficher des statistiques
    stats = vm.get_statistics()
    print("\n=== Statistiques des sauvegardes ===")
    print(f"Versions totales: {stats['total_versions']}")
    print(f"Fichiers uniques: {stats['unique_files']}")
    print(f"Taille totale: {stats['total_size'] / (1024*1024):.2f} MB")


if __name__ == '__main__':
    main()
