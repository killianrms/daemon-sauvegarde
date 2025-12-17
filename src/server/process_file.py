#!/usr/bin/env python3
"""
Script côté serveur pour recevoir et traiter les fichiers avec gestion de versions
"""

import os
import sys
import shutil
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from version_manager import VersionManager

def process_file(temp_file, relative_path, backup_root, action='modified'):
    """Traite un fichier reçu avec gestion de versions"""
    try:
        vm = VersionManager(backup_root)

        if action == 'deleted':
            success = vm.delete_file(relative_path)
        else:
            success = vm.save_version(temp_file, relative_path)

        if success:
            print(f"OK: {relative_path}")
            return 0
        else:
            print(f"ERROR: Failed to process {relative_path}")
            return 1

    except Exception as e:
        print(f"ERROR: {e}")
        return 1

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Usage: process_file.py <temp_file> <relative_path> <backup_root> [action]")
        sys.exit(1)

    temp_file = sys.argv[1]
    relative_path = sys.argv[2]
    backup_root = sys.argv[3]
    action = sys.argv[4] if len(sys.argv) > 4 else 'modified'

    sys.exit(process_file(temp_file, relative_path, backup_root, action))
