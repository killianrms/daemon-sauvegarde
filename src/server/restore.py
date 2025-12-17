#!/usr/bin/env python3
"""
Script de restauration de fichiers depuis les versions sauvegardées
"""

import os
import sys
import shutil
import argparse
from datetime import datetime
from pathlib import Path
from version_manager import VersionManager

class RestoreManager:
    """Gestionnaire de restauration de fichiers"""

    def __init__(self, backup_root):
        self.backup_root = Path(backup_root).expanduser()
        self.vm = VersionManager(backup_root)

    def list_files(self):
        """Liste tous les fichiers ayant des versions"""
        print("\n=== Fichiers avec versions disponibles ===\n")

        versions = self.vm.list_versions()
        files_dict = {}

        for file_path, timestamp, file_size, action, created_at in versions:
            if file_path not in files_dict:
                files_dict[file_path] = []
            files_dict[file_path].append((timestamp, file_size, action, created_at))

        for idx, (file_path, versions_list) in enumerate(sorted(files_dict.items()), 1):
            print(f"{idx}. {file_path}")
            print(f"   Versions: {len(versions_list)}")
            latest = versions_list[0]
            print(f"   Dernière modif: {latest[0]} ({latest[2]})")
            print()

        return list(files_dict.keys())

    def list_versions_for_file(self, file_path):
        """Liste toutes les versions d'un fichier spécifique"""
        print(f"\n=== Versions de: {file_path} ===\n")

        versions = self.vm.list_versions(file_path)

        if not versions:
            print("Aucune version trouvée pour ce fichier.")
            return []

        version_list = []
        for idx, (fp, timestamp, file_size, action, created_at) in enumerate(versions, 1):
            size_mb = file_size / (1024 * 1024) if file_size else 0
            date_str = datetime.strptime(timestamp.split('_')[0], "%Y-%m-%d").strftime("%d/%m/%Y")
            time_str = timestamp.split('_')[1].replace('-', ':')

            print(f"{idx}. {date_str} {time_str}")
            print(f"   Action: {action}")
            print(f"   Taille: {size_mb:.2f} MB")
            print(f"   Timestamp: {timestamp}")
            print()

            version_list.append(timestamp)

        return version_list


    def restore_version(self, file_path, timestamp, destination=None):
        """Restaure une version spécifique d'un fichier"""
        try:
            import sqlite3
            import gzip
            import json

            # Obtenir les métadonnées complètes depuis la base de données
            conn = sqlite3.connect(self.vm.metadata_db)
            cursor = conn.cursor()
            
            # Fetch essential columns + encryption cols
            cursor.execute('''
                SELECT version_path, is_compressed, is_deduplicated, dedup_ref, is_encrypted, encryption_metadata
                FROM file_versions
                WHERE file_path = ? AND version_timestamp = ?
            ''', (file_path, timestamp))

            result = cursor.fetchone()

            if not result:
                print(f"✗ Version introuvable: {timestamp}")
                conn.close()
                return False

            version_path_rel, is_compressed, is_deduplicated, dedup_ref, is_encrypted, enc_meta_json = result
            encryption_metadata = json.loads(enc_meta_json) if enc_meta_json else None
            
            # If dedup, fetch the actual blob details from dedup_store
            if is_deduplicated and dedup_ref:
                cursor.execute('''
                    SELECT dedup_path, is_encrypted, encryption_metadata 
                    FROM dedup_store 
                    WHERE file_hash = ?
                ''', (dedup_ref,))
                dedup_res = cursor.fetchone()
                if dedup_res:
                    version_path_rel, is_encrypted, enc_meta_json = dedup_res
                    encryption_metadata = json.loads(enc_meta_json) if enc_meta_json else None
                else:
                    print(f"⚠ Référence de déduplication introuvable: {dedup_ref}")
                    # Fallback to version info if possible? No, dedup relies on store.
            
            conn.close()

            # Construire le chemin complet
            source_path = self.vm.backup_root / version_path_rel
            
            if not source_path.exists():
                 # Handle case where extension might differ if not stored exactly as path in DB? 
                 # My save logic stored the relative path (including extension) in DB.
                 # So source_path should be correct.
                 print(f"✗ Fichier source introuvable: {source_path}")
                 # Debug info
                 print(f"  Cherché: {source_path}")
                 return False

            # Déterminer la destination
            if destination is None:
                destination = Path.cwd() / "restored" / file_path
            else:
                destination = Path(destination)

            # Créer les répertoires si nécessaire
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # Pipeline de restauration: Source -> [Decrypt] -> [Decompress] -> Dest
            
            current_source = source_path
            temp_decrypted = None
            
            # 1. Déchiffrement
            if is_encrypted:
                if not self.vm.encryption_manager:
                     print("✗ Erreur: Fichier chiffré mais le chiffrement n'est pas activé/configuré sur ce serveur.")
                     return False
                
                print(f"  🔓 Déchiffrement en cours...")
                temp_decrypted = source_path.with_suffix(source_path.suffix + '.dec_temp')
                try:
                    self.vm.encryption_manager.decrypt_file(source_path, temp_decrypted)
                    current_source = temp_decrypted
                except Exception as e:
                    print(f"✗ Échec du déchiffrement: {e}")
                    if temp_decrypted and temp_decrypted.exists(): temp_decrypted.unlink()
                    return False

            # 2. Décompression + Copie finale
            try:
                if is_compressed:
                    print(f"  📦 Décompression en cours...")
                    with gzip.open(current_source, 'rb') as f_in:
                        with open(destination, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                else:
                    shutil.copy2(current_source, destination)
            finally:
                # Cleanup temp file if created
                if temp_decrypted and temp_decrypted.exists():
                    temp_decrypted.unlink()

            print(f"✓ Fichier restauré: {destination}")
            if is_encrypted:
                print(f"  (fichier déchiffré)")
            if is_deduplicated:
                print(f"  (fichier dédupliqué)")
            
            return True

        except Exception as e:
            print(f"✗ Erreur lors de la restauration: {e}")
            import traceback
            traceback.print_exc()
            return False

    def restore_all_at_date(self, target_date, destination=None):
        """Restaure tous les fichiers à une date spécifique"""
        try:
            # Convertir la date en format timestamp
            target_dt = datetime.strptime(target_date, "%Y-%m-%d")
            target_str = target_dt.strftime("%Y-%m-%d")

            print(f"\n=== Restauration à la date: {target_date} ===\n")

            # Obtenir toutes les versions
            versions = self.vm.list_versions()

            # Grouper par fichier et trouver la version la plus proche avant la date cible
            files_to_restore = {}
            for file_path, timestamp, file_size, action, created_at in versions:
                version_date = timestamp.split('_')[0]

                # Si la version est avant ou égale à la date cible
                if version_date <= target_str:
                    # Si le fichier n'est pas encore dans le dict ou si cette version est plus récente
                    if file_path not in files_to_restore or timestamp > files_to_restore[file_path]['timestamp']:
                        files_to_restore[file_path] = {
                            'timestamp': timestamp,
                            'action': action
                        }

            # Restaurer les fichiers (sauf ceux supprimés)
            restored_count = 0
            for file_path, info in files_to_restore.items():
                if info['action'] != 'deleted':
                    dest = Path(destination) / file_path if destination else None
                    if self.restore_version(file_path, info['timestamp'], dest):
                        restored_count += 1

            print(f"\n✓ {restored_count} fichiers restaurés")
            return True

        except Exception as e:
            print(f"✗ Erreur lors de la restauration: {e}")
            return False

    def interactive_restore(self):
        """Mode interactif de restauration"""
        print("\n" + "="*50)
        print("   RESTAURATION DE FICHIERS - Mode Interactif")
        print("="*50)

        while True:
            print("\nOptions:")
            print("1. Lister tous les fichiers avec versions")
            print("2. Restaurer un fichier spécifique")
            print("3. Restaurer tous les fichiers à une date")
            print("4. Quitter")

            choice = input("\nVotre choix: ").strip()

            if choice == '1':
                self.list_files()

            elif choice == '2':
                file_path = input("\nChemin du fichier (relatif): ").strip()
                versions = self.list_versions_for_file(file_path)

                if versions:
                    version_idx = input("\nNuméro de version à restaurer: ").strip()
                    try:
                        idx = int(version_idx) - 1
                        if 0 <= idx < len(versions):
                            destination = input("\nDestination (vide pour ./restored/): ").strip()
                            dest = destination if destination else None
                            self.restore_version(file_path, versions[idx], dest)
                        else:
                            print("✗ Numéro invalide")
                    except ValueError:
                        print("✗ Veuillez entrer un numéro valide")

            elif choice == '3':
                date_str = input("\nDate de restauration (YYYY-MM-DD): ").strip()
                destination = input("\nDestination (vide pour ./restored/): ").strip()
                dest = destination if destination else "./restored"
                self.restore_all_at_date(date_str, dest)

            elif choice == '4':
                print("\nAu revoir!")
                break

            else:
                print("✗ Choix invalide")


def main():
    parser = argparse.ArgumentParser(
        description='Restauration de fichiers depuis les sauvegardes versionnées'
    )
    parser.add_argument(
        'backup_root',
        help='Chemin racine des sauvegardes'
    )
    parser.add_argument(
        '--file', '-f',
        help='Fichier spécifique à restaurer'
    )
    parser.add_argument(
        '--version', '-v',
        help='Timestamp de la version à restaurer'
    )
    parser.add_argument(
        '--date', '-d',
        help='Restaurer tous les fichiers à cette date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--destination', '-o',
        help='Dossier de destination (défaut: ./restored/)'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='Lister les fichiers disponibles'
    )
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Mode interactif'
    )

    args = parser.parse_args()

    rm = RestoreManager(args.backup_root)

    if args.interactive:
        rm.interactive_restore()
    elif args.list:
        if args.file:
            rm.list_versions_for_file(args.file)
        else:
            rm.list_files()
    elif args.file and args.version:
        rm.restore_version(args.file, args.version, args.destination)
    elif args.date:
        rm.restore_all_at_date(args.date, args.destination)
    else:
        # Par défaut, mode interactif
        rm.interactive_restore()


if __name__ == '__main__':
    main()
