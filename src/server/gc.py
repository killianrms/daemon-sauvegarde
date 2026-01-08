#!/usr/bin/env python3
"""
Garbage Collector for Deduplication Store
Removes blocks that are no longer referenced by any file version.
"""

import sys
import os
import sqlite3
import shutil
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from version_manager import VersionManager

def cleanup_dedup(backup_root):
    vm = VersionManager(backup_root)
    print(f"🧹 Starting Deduplication GC on {backup_root}...")
    
    conn = sqlite3.connect(vm.metadata_db)
    cursor = conn.cursor()
    
    # 1. Check ref_counts (Double check against file_versions table for safety?)
    # The ref_count in dedup_store is supposed to be accurate if maintained correctly.
    # But for safety, let's recalculate it? 
    # Recalculating is expensive but safer.
    # Let's trust ref_count first, but maybe in Omega Mode we should Re-Verify.
    
    # Let's rely on ref_count < 1 for now as per plan.
    
    cursor.execute('SELECT file_hash, dedup_path, ref_count FROM dedup_store WHERE ref_count <= 0')
    candidates = cursor.fetchall()
    
    if not candidates:
        print("✓ No orphaned blocks found.")
        conn.close()
        return

    print(f"Found {len(candidates)} orphaned blocks.")
    
    count = 0
    reclaimed_bytes = 0
    
    for row in candidates:
        file_hash, dedup_path_str, ref_count = row
        dedup_path = vm.backup_root / dedup_path_str
        
        # Verify it really is unused?
        # Safe strict mode: check if any file_version uses this hash
        cursor.execute('SELECT COUNT(*) FROM file_versions WHERE dedup_ref = ?', (file_hash,))
        actual_refs = cursor.fetchone()[0]
        
        if actual_refs > 0:
            print(f"⚠ Warning: Block {file_hash[:8]} has ref_count={ref_count} but actual_refs={actual_refs}. Repairing DB...")
            cursor.execute('UPDATE dedup_store SET ref_count = ? WHERE file_hash = ?', (actual_refs, file_hash))
            continue
            
        # Delete file
        if dedup_path.exists():
            try:
                size = dedup_path.stat().st_size
                dedup_path.unlink()
                reclaimed_bytes += size
            except OSError as e:
                print(f"Error deleting {dedup_path}: {e}")
                
        # Delete from DB
        cursor.execute('DELETE FROM dedup_store WHERE file_hash = ?', (file_hash,))
        count += 1
        
    conn.commit()
    conn.close()
    
    print(f"✓ Cleanup complete.")
    print(f"  Removed: {count} blocks")
    print(f"  Reclaimed: {reclaimed_bytes / (1024*1024):.2f} MB")

if __name__ == '__main__':
    # Try to load config
    root = os.path.expanduser('~/backups')
    # Or arg
    if len(sys.argv) > 1:
        root = sys.argv[1]
        
    cleanup_dedup(root)
