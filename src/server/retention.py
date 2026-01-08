#!/usr/bin/env python3
"""
Retention Policy Manager
Implements Grandfather-Father-Son rotation logic.
"""

from datetime import datetime, timedelta
import logging

class RetentionManager:
    def __init__(self, version_manager):
        self.vm = version_manager

    def prune_history(self, file_path, dry_run=False):
        """
        Applies retention policy to a specific file.
        Policy:
        - Keep ALL versions < 1 day
        - Keep LATEST daily version < 7 days
        - Keep LATEST weekly version < 4 weeks
        - Keep LATEST monthly version < 12 months
        """
        # Get all versions sorted by date (newest first)
        versions = self.vm.get_file_versions(file_path) # Need to implement this getter or query DB directly
        if not versions:
            return 0

        # We need a structured list: [(timestamp_str, timestamp_dt), ...]
        parsed_versions = []
        for v in versions:
            # v is (timestamp, size, ...) from database usually
            # But let's check what vm methods return or just query DB ourselves.
            # Using VM internal methods is better if available.
            # Let's assume we query the DB here for control.
            pass
            
        pass 
        # Actually, let's inject the logic directly if VM doesn't expose clean list.
        # But for 'file_path', we need to query `file_versions`.
        
        conn = self.vm._get_db_connection() # Assuming helper or manually connect
        cursor = conn.cursor()
        cursor.execute('SELECT version_timestamp FROM file_versions WHERE file_path = ? ORDER BY version_timestamp DESC', (file_path,))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return 0
            
        ts_list = [row[0] for row in rows]
        to_delete = self._calculate_pruning(ts_list)
        
        deleted_count = 0
        if not dry_run and to_delete:
            for ts in to_delete:
                if self.vm.delete_specific_version(file_path, ts):
                    deleted_count += 1
                    
        return len(to_delete) if dry_run else deleted_count

    def _calculate_pruning(self, timestamp_strings):
        """
        Returns list of timestamps to delete.
        Input: list of strings 'YYYYMMDD_HHMMSS', sorted DESC (newest first).
        """
        keep = set()
        now = datetime.now()
        
        # Buckets
        daily_bucket = {}   # "YYYY-MM-DD" -> timestamp
        weekly_bucket = {}  # "YYYY-Wxx" -> timestamp
        monthly_bucket = {} # "YYYY-MM" -> timestamp
        
        for ts_str in timestamp_strings:
            try:
                dt = datetime.strptime(ts_str, '%Y%m%d_%H%M%S')
                age = now - dt
                
                # Rule 1: Keep all < 24h
                if age < timedelta(days=1):
                    keep.add(ts_str)
                    continue
                    
                # Rule 2: Daily for 7 days
                if age < timedelta(days=7):
                    day_key = dt.strftime('%Y-%m-%d')
                    # We want the LATEST of that day (which we see first since sorted DESC)
                    if day_key not in daily_bucket:
                        daily_bucket[day_key] = ts_str
                        keep.add(ts_str)
                    continue
                    
                # Rule 3: Weekly for 4 weeks (28 days)
                if age < timedelta(days=28):
                    week_key = dt.strftime('%Y-%U')
                    if week_key not in weekly_bucket:
                        weekly_bucket[week_key] = ts_str
                        keep.add(ts_str)
                    continue
                    
                # Rule 4: Monthly for 12 months (365 days)
                if age < timedelta(days=365):
                    month_key = dt.strftime('%Y-%m')
                    if month_key not in monthly_bucket:
                        monthly_bucket[month_key] = ts_str
                        keep.add(ts_str)
                    continue
                    
                # Else: Detete (Too old)
                
            except ValueError:
                pass # Ignore bad formats
                
        # Return what's NOT in keep
        to_delete = [ts for ts in timestamp_strings if ts not in keep]
        return to_delete

    def prune_all(self, dry_run=False):
        """Prunes all files in the system"""
        conn = self.vm._get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT file_path FROM file_versions')
        files = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        total_pruned = 0
        for f in files:
            total_pruned += self.prune_history(f, dry_run=dry_run)
        return total_pruned

if __name__ == '__main__':
    import argparse
    import os
    import sys
    
    # Add path to find version_manager
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from version_manager import VersionManager

    parser = argparse.ArgumentParser(description="Retention Policy Enforcer")
    parser.add_argument('--root', default='~/backups', help='Backup root directory')
    parser.add_argument('--dry-run', action='store_true', help='Do not delete, just count')
    args = parser.parse_args()
    
    root = os.path.expanduser(args.root)
    if not os.path.exists(root):
        print(f"Error: {root} does not exist.")
        sys.exit(1)
        
    vm = VersionManager(root)
    rm = RetentionManager(vm)
    
    print(f"📉 Running Retention Pruning on {root}...")
    count = rm.prune_all(dry_run=args.dry_run)
    
    if args.dry_run:
        print(f"Would prune {count} versions.")
    else:
        print(f"✓ Pruned {count} versions.")
