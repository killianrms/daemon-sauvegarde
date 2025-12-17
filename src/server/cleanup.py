#!/usr/bin/env python3
"""
Script de nettoyage automatique des anciennes versions
Supprime les versions de sauvegarde plus anciennes que la période de rétention
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

try:
    from .version_manager import VersionManager
except ImportError:
    # Direct execution fallback
    import sys, os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from version_manager import VersionManager

def cleanup_versions(backup_root, retention_days=30, dry_run=False):
    """Nettoie les anciennes versions"""
    print(f"\n{'='*60}")
    print(f"   NETTOYAGE DES VERSIONS")
    print(f"{'='*60}\n")
    print(f"Dossier de sauvegarde: {backup_root}")
    print(f"Rétention: {retention_days} jours")
    print(f"Mode: {'SIMULATION' if dry_run else 'RÉEL'}\n")

    if dry_run:
        print("⚠️  MODE SIMULATION - Aucune suppression ne sera effectuée\n")

    vm = VersionManager(backup_root)

    # Statistiques avant nettoyage
    stats_before = vm.get_statistics()
    print("Statistiques AVANT nettoyage:")
    print(f"  - Versions totales: {stats_before['total_versions']}")
    print(f"  - Fichiers uniques: {stats_before['unique_files']}")
    print(f"  - Espace utilisé: {stats_before['total_size'] / (1024*1024):.2f} MB\n")

    if not dry_run:
        # Effectuer le nettoyage
        deleted_count = vm.cleanup_old_versions(retention_days)

        # Statistiques après nettoyage
        stats_after = vm.get_statistics()
        print("\nStatistiques APRÈS nettoyage:")
        print(f"  - Versions totales: {stats_after['total_versions']}")
        print(f"  - Fichiers uniques: {stats_after['unique_files']}")
        print(f"  - Espace utilisé: {stats_after['total_size'] / (1024*1024):.2f} MB")

        space_freed = (stats_before['total_size'] - stats_after['total_size']) / (1024*1024)
        print(f"\n✓ Espace libéré: {space_freed:.2f} MB")
    else:
        # Mode simulation - juste compter ce qui serait supprimé
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d_%H-%M-%S")

        versions_dir = Path(backup_root).expanduser() / "versions"
        count = 0
        size = 0

        for version_dir in sorted(versions_dir.iterdir()):
            if version_dir.is_dir() and version_dir.name < cutoff_str:
                dir_size = sum(f.stat().st_size for f in version_dir.rglob('*') if f.is_file())
                size += dir_size
                count += 1
                print(f"  Serait supprimé: {version_dir.name}")

        print(f"\n📊 Résultat de la simulation:")
        print(f"  - {count} versions seraient supprimées")
        print(f"  - {size / (1024*1024):.2f} MB seraient libérés")


def setup_cron(backup_root, retention_days=30):
    """Configure une tâche cron pour le nettoyage automatique"""
    print("\n=== Configuration de cron ===\n")

    script_path = Path(__file__).resolve()
    cron_command = f"0 2 * * * {sys.executable} {script_path} {backup_root} --retention {retention_days}"

    print("Ajoutez cette ligne à votre crontab pour un nettoyage quotidien à 2h du matin:")
    print(f"\n{cron_command}\n")
    print("Pour éditer votre crontab:")
    print("  crontab -e")
    print("\nOu utilisez cette commande pour l'ajouter automatiquement:")
    print(f'  (crontab -l 2>/dev/null; echo "{cron_command}") | crontab -')


def show_statistics(backup_root):
    """Affiche les statistiques détaillées"""
    vm = VersionManager(backup_root)
    stats = vm.get_statistics()

    print("\n" + "="*60)
    print("   STATISTIQUES DES SAUVEGARDES")
    print("="*60 + "\n")

    print(f"📊 Vue d'ensemble:")
    print(f"  - Versions totales: {stats['total_versions']}")
    print(f"  - Fichiers uniques: {stats['unique_files']}")
    print(f"  - Espace total: {stats['total_size'] / (1024*1024):.2f} MB")
    print(f"  - Espace moyen/version: {(stats['total_size'] / stats['total_versions']) / 1024:.2f} KB" if stats['total_versions'] > 0 else "  - Espace moyen: N/A")

    if stats['daily_stats']:
        print(f"\n📅 Activité des 30 derniers jours:")
        for day, count in stats['daily_stats'][:7]:  # Afficher les 7 derniers jours
            print(f"  {day}: {count} versions")

    # Calcul de l'espace potentiellement libérable
    from datetime import datetime, timedelta
    cutoff_date = datetime.now() - timedelta(days=30)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d_%H-%M-%S")

    versions_dir = Path(backup_root).expanduser() / "versions"
    old_size = 0
    old_count = 0

    if versions_dir.exists():
        for version_dir in versions_dir.iterdir():
            if version_dir.is_dir() and version_dir.name < cutoff_str:
                dir_size = sum(f.stat().st_size for f in version_dir.rglob('*') if f.is_file())
                old_size += dir_size
                old_count += 1

        print(f"\n🧹 Nettoyage disponible:")
        print(f"  - {old_count} versions > 30 jours")
        print(f"  - {old_size / (1024*1024):.2f} MB peuvent être libérés")
        if old_count > 0:
            print(f"\n💡 Lancez: python3 cleanup.py {backup_root}")


def main():
    parser = argparse.ArgumentParser(
        description='Nettoyage automatique des anciennes versions de sauvegarde'
    )
    parser.add_argument(
        'backup_root',
        help='Chemin racine des sauvegardes'
    )
    parser.add_argument(
        '--retention', '-r',
        type=int,
        default=30,
        help='Nombre de jours de rétention (défaut: 30)'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Mode simulation (ne supprime rien)'
    )
    parser.add_argument(
        '--setup-cron',
        action='store_true',
        help='Affiche la configuration cron'
    )
    parser.add_argument(
        '--stats', '-s',
        action='store_true',
        help='Affiche les statistiques'
    )

    args = parser.parse_args()

    if args.stats:
        show_statistics(args.backup_root)
    elif args.setup_cron:
        setup_cron(args.backup_root, args.retention)
    else:
        cleanup_versions(args.backup_root, args.retention, args.dry_run)


if __name__ == '__main__':
    main()
