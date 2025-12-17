#!/usr/bin/env python3
"""
Module de fiabilité et tests automatiques
Vérifie l'intégrité des sauvegardes et teste la restauration
"""

import os
import sys
import random
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from version_manager import VersionManager
from restore import RestoreManager

class ReliabilityManager:
    """Gestionnaire de fiabilité et tests automatiques"""

    def __init__(self, backup_root):
        self.backup_root = Path(backup_root).expanduser()
        self.vm = VersionManager(backup_root)
        self.rm = RestoreManager(backup_root)
        self.test_db = self.backup_root / "reliability_tests.db"
        self.init_database()

    def init_database(self):
        """Initialise la base de données des tests"""
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS integrity_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                version_timestamp TEXT NOT NULL,
                expected_hash TEXT NOT NULL,
                actual_hash TEXT,
                status TEXT,
                checked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                error_message TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS restore_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                version_timestamp TEXT NOT NULL,
                test_status TEXT,
                restore_time_ms INTEGER,
                files_match BOOLEAN,
                tested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                error_message TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_type TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT,
                checked_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def check_file_integrity(self, file_path, timestamp, expected_hash):
        """
        Vérifie l'intégrité d'une version de fichier

        Args:
            file_path: Chemin relatif du fichier
            timestamp: Timestamp de la version
            expected_hash: Hash SHA256 attendu

        Returns:
            dict: Résultat de la vérification
        """
        try:
            # Récupérer le fichier de la version
            conn = sqlite3.connect(self.vm.metadata_db)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT version_path, is_compressed, is_deduplicated, dedup_ref
                FROM file_versions
                WHERE file_path = ? AND version_timestamp = ?
            ''', (file_path, timestamp))

            result = cursor.fetchone()
            conn.close()

            if not result:
                return {
                    'status': 'error',
                    'error': 'Version not found',
                    'expected_hash': expected_hash,
                    'actual_hash': None
                }

            version_path_rel, is_compressed, is_deduplicated, dedup_ref = result

            # Déterminer le chemin du fichier
            if is_deduplicated and dedup_ref:
                source_path = self.vm.backup_root / dedup_ref
                if not source_path.exists():
                    source_path = self.vm.backup_root / (dedup_ref + '.gz')
            else:
                source_path = self.vm.backup_root / version_path_rel

            if not source_path.exists():
                return {
                    'status': 'error',
                    'error': 'File not found',
                    'expected_hash': expected_hash,
                    'actual_hash': None,
                    'path': str(source_path)
                }

            # Décompresser si nécessaire et calculer le hash
            if is_compressed:
                import gzip
                with gzip.open(source_path, 'rb') as f:
                    data = f.read()
            else:
                with open(source_path, 'rb') as f:
                    data = f.read()

            actual_hash = hashlib.sha256(data).hexdigest()

            # Comparer
            status = 'ok' if actual_hash == expected_hash else 'mismatch'

            result = {
                'status': status,
                'expected_hash': expected_hash,
                'actual_hash': actual_hash,
                'file_size': len(data),
                'is_compressed': bool(is_compressed),
                'is_deduplicated': bool(is_deduplicated)
            }

            # Enregistrer dans la DB
            self._record_integrity_check(file_path, timestamp, expected_hash, actual_hash, status)

            return result

        except Exception as e:
            error_msg = str(e)
            self._record_integrity_check(file_path, timestamp, expected_hash, None, 'error', error_msg)

            return {
                'status': 'error',
                'error': error_msg,
                'expected_hash': expected_hash,
                'actual_hash': None
            }

    def _record_integrity_check(self, file_path, timestamp, expected_hash, actual_hash, status, error=None):
        """Enregistre un test d'intégrité"""
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO integrity_checks
            (file_path, version_timestamp, expected_hash, actual_hash, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (file_path, timestamp, expected_hash, actual_hash, status, error))

        conn.commit()
        conn.close()

    def run_random_integrity_checks(self, sample_size=10):
        """
        Vérifie l'intégrité d'un échantillon aléatoire de fichiers

        Args:
            sample_size: Nombre de fichiers à vérifier

        Returns:
            dict: Résultats des vérifications
        """
        print(f"\n=== Vérification d'intégrité de {sample_size} fichiers aléatoires ===\n")

        # Récupérer un échantillon aléatoire
        conn = sqlite3.connect(self.vm.metadata_db)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT file_path, version_timestamp, file_hash
            FROM file_versions
            WHERE file_hash IS NOT NULL
            ORDER BY RANDOM()
            LIMIT ?
        ''', (sample_size,))

        samples = cursor.fetchall()
        conn.close()

        if not samples:
            print("Aucun fichier à vérifier")
            return {'total': 0, 'ok': 0, 'mismatch': 0, 'errors': 0}

        results = {'total': 0, 'ok': 0, 'mismatch': 0, 'errors': 0}

        for file_path, timestamp, expected_hash in samples:
            print(f"Vérification: {file_path} ({timestamp[:10]})...", end=' ')

            result = self.check_file_integrity(file_path, timestamp, expected_hash)
            results['total'] += 1

            if result['status'] == 'ok':
                print("✓ OK")
                results['ok'] += 1
            elif result['status'] == 'mismatch':
                print(f"✗ CORRUPTION DÉTECTÉE")
                results['mismatch'] += 1
            else:
                print(f"✗ Erreur: {result.get('error', 'Unknown')}")
                results['errors'] += 1

        print(f"\n📊 Résultats:")
        print(f"  Total vérifié: {results['total']}")
        print(f"  ✓ OK: {results['ok']}")
        print(f"  ✗ Corruptions: {results['mismatch']}")
        print(f"  ⚠ Erreurs: {results['errors']}")

        success_rate = (results['ok'] / results['total'] * 100) if results['total'] > 0 else 0
        print(f"  Taux de réussite: {success_rate:.1f}%\n")

        return results

    def test_restore(self, file_path, timestamp):
        """
        Teste la restauration d'un fichier

        Args:
            file_path: Chemin relatif du fichier
            timestamp: Timestamp de la version

        Returns:
            dict: Résultat du test
        """
        import time

        try:
            # Créer un dossier temporaire
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir = Path(temp_dir)
                restore_path = temp_dir / "restored" / file_path

                # Mesurer le temps de restauration
                start_time = time.time()
                success = self.rm.restore_version(file_path, timestamp, str(restore_path))
                restore_time = int((time.time() - start_time) * 1000)  # en ms

                if not success or not restore_path.exists():
                    result = {
                        'status': 'error',
                        'error': 'Restore failed',
                        'restore_time_ms': restore_time
                    }
                else:
                    # Vérifier que le fichier restauré correspond
                    # (on ne peut pas comparer avec l'original car il peut ne plus exister)
                    restored_hash = hashlib.sha256(open(restore_path, 'rb').read()).hexdigest()

                    result = {
                        'status': 'ok',
                        'restore_time_ms': restore_time,
                        'restored_hash': restored_hash,
                        'file_size': restore_path.stat().st_size
                    }

                # Enregistrer
                self._record_restore_test(file_path, timestamp, result['status'], restore_time, result.get('error'))

                return result

        except Exception as e:
            error_msg = str(e)
            self._record_restore_test(file_path, timestamp, 'error', 0, error_msg)

            return {
                'status': 'error',
                'error': error_msg
            }

    def _record_restore_test(self, file_path, timestamp, status, restore_time, error=None):
        """Enregistre un test de restauration"""
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO restore_tests
            (file_path, version_timestamp, test_status, restore_time_ms, error_message)
            VALUES (?, ?, ?, ?, ?)
        ''', (file_path, timestamp, status, restore_time, error))

        conn.commit()
        conn.close()

    def run_random_restore_tests(self, sample_size=5):
        """
        Teste la restauration d'un échantillon aléatoire

        Args:
            sample_size: Nombre de fichiers à tester

        Returns:
            dict: Résultats des tests
        """
        print(f"\n=== Tests de restauration de {sample_size} fichiers aléatoires ===\n")

        # Récupérer un échantillon
        conn = sqlite3.connect(self.vm.metadata_db)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT file_path, version_timestamp
            FROM file_versions
            WHERE action != 'deleted'
            ORDER BY RANDOM()
            LIMIT ?
        ''', (sample_size,))

        samples = cursor.fetchall()
        conn.close()

        results = {'total': 0, 'ok': 0, 'errors': 0, 'total_time_ms': 0}

        for file_path, timestamp in samples:
            print(f"Test restauration: {file_path} ({timestamp[:10]})...", end=' ')

            result = self.test_restore(file_path, timestamp)
            results['total'] += 1

            if result['status'] == 'ok':
                print(f"✓ OK ({result['restore_time_ms']}ms)")
                results['ok'] += 1
                results['total_time_ms'] += result['restore_time_ms']
            else:
                print(f"✗ Erreur: {result.get('error', 'Unknown')}")
                results['errors'] += 1

        if results['ok'] > 0:
            avg_time = results['total_time_ms'] / results['ok']
            print(f"\n📊 Résultats:")
            print(f"  Total testé: {results['total']}")
            print(f"  ✓ Réussis: {results['ok']}")
            print(f"  ✗ Échecs: {results['errors']}")
            print(f"  Temps moyen: {avg_time:.0f}ms\n")

        return results

    def health_check(self):
        """Effectue un check complet de santé du système"""
        print("\n=== Health Check du Système ===\n")

        checks = []

        # 1. Vérifier l'espace disque
        disk_check = self._check_disk_space()
        checks.append(disk_check)
        print(f"1. Espace disque: {disk_check['status']}")
        print(f"   {disk_check['details']}\n")

        # 2. Vérifier la base de données
        db_check = self._check_database()
        checks.append(db_check)
        print(f"2. Base de données: {db_check['status']}")
        print(f"   {db_check['details']}\n")

        # 3. Vérifier l'intégrité (échantillon)
        integrity_check = self._check_integrity_sample()
        checks.append(integrity_check)
        print(f"3. Intégrité: {integrity_check['status']}")
        print(f"   {integrity_check['details']}\n")

        # Enregistrer les résultats
        for check in checks:
            self._record_health_check(check['type'], check['status'], check['details'])

        # Résumé
        all_ok = all(c['status'] == 'ok' for c in checks)
        if all_ok:
            print("✓ Système en bon état\n")
        else:
            print("⚠ Problèmes détectés\n")

        return {'checks': checks, 'overall_status': 'ok' if all_ok else 'warning'}

    def _check_disk_space(self):
        """Vérifie l'espace disque"""
        try:
            stat = shutil.disk_usage(self.backup_root)
            percent_used = (stat.used / stat.total) * 100
            free_gb = stat.free / (1024**3)

            if percent_used > 90:
                status = 'critical'
                details = f"⚠ CRITIQUE: {percent_used:.1f}% utilisé, {free_gb:.1f} GB libres"
            elif percent_used > 80:
                status = 'warning'
                details = f"⚠ Attention: {percent_used:.1f}% utilisé, {free_gb:.1f} GB libres"
            else:
                status = 'ok'
                details = f"{percent_used:.1f}% utilisé, {free_gb:.1f} GB libres"

            return {'type': 'disk_space', 'status': status, 'details': details}

        except Exception as e:
            return {'type': 'disk_space', 'status': 'error', 'details': str(e)}

    def _check_database(self):
        """Vérifie l'intégrité de la base de données"""
        try:
            conn = sqlite3.connect(self.vm.metadata_db)
            cursor = conn.cursor()

            # Check integrity
            cursor.execute('PRAGMA integrity_check')
            result = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM file_versions')
            count = cursor.fetchone()[0]

            conn.close()

            if result == 'ok':
                status = 'ok'
                details = f"{count} versions en base, intégrité OK"
            else:
                status = 'error'
                details = f"Erreur d'intégrité: {result}"

            return {'type': 'database', 'status': status, 'details': details}

        except Exception as e:
            return {'type': 'database', 'status': 'error', 'details': str(e)}

    def _check_integrity_sample(self):
        """Vérifie l'intégrité d'un échantillon"""
        try:
            results = self.run_random_integrity_checks(sample_size=5)

            if results['mismatch'] > 0:
                status = 'error'
                details = f"⚠ {results['mismatch']} corruptions détectées sur {results['total']}"
            elif results['errors'] > 0:
                status = 'warning'
                details = f"{results['errors']} erreurs sur {results['total']}"
            else:
                status = 'ok'
                details = f"{results['ok']}/{results['total']} fichiers OK"

            return {'type': 'integrity', 'status': status, 'details': details}

        except Exception as e:
            return {'type': 'integrity', 'status': 'error', 'details': str(e)}

    def _record_health_check(self, check_type, status, details):
        """Enregistre un health check"""
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO health_checks (check_type, status, details)
            VALUES (?, ?, ?)
        ''', (check_type, status, details))

        conn.commit()
        conn.close()


def main():
    """Test du module de fiabilité"""
    import argparse

    parser = argparse.ArgumentParser(description='Tests de fiabilité des sauvegardes')
    parser.add_argument('backup_root', help='Dossier racine des sauvegardes')
    parser.add_argument('--integrity', '-i', type=int, help='Vérifier N fichiers aléatoires')
    parser.add_argument('--restore', '-r', type=int, help='Tester N restaurations')
    parser.add_argument('--health', action='store_true', help='Health check complet')

    args = parser.parse_args()

    rm = ReliabilityManager(args.backup_root)

    if args.integrity:
        rm.run_random_integrity_checks(args.integrity)
    elif args.restore:
        rm.run_random_restore_tests(args.restore)
    elif args.health:
        rm.health_check()
    else:
        # Par défaut, faire un health check
        rm.health_check()


if __name__ == '__main__':
    main()
