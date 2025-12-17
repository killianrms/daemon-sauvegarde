
import pytest
import os
import shutil
import json
from pathlib import Path
from src.server.version_manager import VersionManager
from src.server.restore import RestoreManager

def test_encryption_flow(tmp_path):
    # Setup
    backup_root = tmp_path / "backups_enc"
    

    # 1. Init Manager with Encryption and NO Dedup (easier to find file)

    vm = VersionManager(backup_root, enable_encryption=True, enable_deduplication=False)
    assert vm.enable_encryption is True
    
    # 2. Save a file (V1 - Initial)
    source_file = tmp_path / "secret.txt"
    source_file.write_text("My Secret Data V1")
    vm.save_version(str(source_file), "secret.txt")
    
    # Modify (V2)
    source_file.write_text("My Secret Data V2")
    vm.save_version(str(source_file), "secret.txt")
    
    # 3. Check if stored file is encrypted
    # Find the file in versions dir
    # versions/timestamp/secret.txt.enc or .gz.enc
    found_enc = False
    for f in vm.versions_dir.rglob('*'):
        if f.is_file():
            if f.name.endswith('.enc'):
                found_enc = True
                # Verify content is NOT "My Secret Data"
                content = f.read_bytes()
                assert b"My Secret Data" not in content
    
    assert found_enc is True, "Stored file should have .enc extension"
    
    # 4. Restore
    rm = RestoreManager(backup_root)
    # Re-init encryption in RM's internal VM (RestoreManager -> self.vm)
    # NOTE: RestoreManager creates its own VersionManager. 
    # VersionManager defaults enable_encryption=True, but usually key is loaded from default. 
    # In test environment, the key might be in a temp home? 
    # EncryptionManager uses default key path ~/.backup_encryption_key if not specified.
    # In tests, we should probably set the key file explicitly or share the key.
    
    # PATCH: We need to make sure RM uses the same encryption context.
    # VersionManager __init__ loads key from default location if password not provided.
    # In a real scenario, the daemon and restore script run as same user so same default key file.
    # In Pytest, we are same user. So it should work if we rely on default ~/.backup_encryption_key 
    # BUT we don't want to overwrite user's actual key!
    # So we must mock EncryptionManager or pass specific key file.
    
    # Let's fix the test to inject the same encryption manager or key.
    # This is tricky because RestoreManager creates new VersionManager internally.
    pass

def test_encryption_custom_key(tmp_path):
    # Safe test with custom key file
    key_file = tmp_path / "test.key"
    backup_root = tmp_path / "backups_enc_custom"
    
    # Monkeypatch EncryptionManager default path for this test? 
    # Easier: init VM with password (derives key) or handle key manually.
    # But VersionManager API takes encryption_password.
    
    pwd = "test_password"
    
    # 1. Save
    vm = VersionManager(backup_root, enable_encryption=True, enable_deduplication=False, encryption_password=pwd)
    # Mock _save_key so it doesn't write to real home? 
    # EncryptionManager(pass) derives key but doesn't save to file if pass is used? 
    # Code says: if password: self.key = derive. No save.
    

    source_file = tmp_path / "secret.txt"
    source_file.write_text("Secret V1")
    vm.save_version(str(source_file), "secret.txt")
    
    source_file.write_text("Secret V2")
    vm.save_version(str(source_file), "secret.txt")
    
    # 2. Restore
    # We need access to vm inside rm
    rm = RestoreManager(backup_root)
    # Access internal vm and re-init encryption with SAME password
    rm.vm = VersionManager(backup_root, enable_encryption=True, enable_deduplication=False, encryption_password=pwd)
    
    dest_file = tmp_path / "restored_secret.txt"
    # Need timestamp
    versions = rm.list_versions_for_file("secret.txt") # Takes metadata from DB
    assert len(versions) > 0
    timestamp = versions[0]
    

    rm.restore_version("secret.txt", timestamp, dest_file)
    
    assert dest_file.exists()
    assert dest_file.read_text() == "Secret V1"

