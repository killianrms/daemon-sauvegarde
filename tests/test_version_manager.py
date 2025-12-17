
import pytest
import os
from pathlib import Path
from src.server.version_manager import VersionManager

def test_version_manager_init(tmp_path):
    backup_root = tmp_path / "backups"
    vm = VersionManager(backup_root)
    
    assert vm.backup_root == backup_root
    assert vm.current_dir.exists()
    assert vm.versions_dir.exists()
    assert vm.metadata_db.exists()

def test_save_version(tmp_path):
    backup_root = tmp_path / "backups"
    vm = VersionManager(backup_root)
    
    # Create a dummy source file
    source_file = tmp_path / "test.txt"
    source_file.write_text("content v1")
    
    # Save version (first time)
    vm.save_version(str(source_file), "test.txt")
    
    assert (vm.current_dir / "test.txt").exists()
    assert (vm.current_dir / "test.txt").read_text() == "content v1"
    
    # Modify source
    source_file.write_text("content v2")
    
    # Save version (second time)
    vm.save_version(str(source_file), "test.txt")
    
    # Check current is updated
    assert (vm.current_dir / "test.txt").read_text() == "content v2"
    

    # Check stats (more reliable than FS if dedup is on)
    stats = vm.get_statistics()
    assert stats['total_versions'] == 1
