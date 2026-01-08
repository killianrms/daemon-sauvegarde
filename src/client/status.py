#!/usr/bin/env python3
"""
CLI Status Tool for Backup System
"""

import sys
import os
import json

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.common.config import ConfigManager
from src.client.ssh_client import SecureSSHClient

def get_human_size(bytes_val):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f} PB"

def main():
    config_file = 'client_config.json'
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
        
    cm = ConfigManager(config_file)
    client = SecureSSHClient(cm.config)
    
    print("Connecting to server...")
    if not client.connect():
        print("✗ Could not connect to server.")
        sys.exit(1)
        
    cmd = {"cmd": "get_stats"}
    resp = client._send_agent_command(cmd)
    
    if resp and resp.get('status') == 'ok':
        stats = resp.get('stats', {})
        print("\n=== 📊 Backup System Status ===")
        print(f"Files Tracked:    {stats.get('file_count', 0)}")
        print(f"Total Versions:   {stats.get('version_count', 0)}")
        print(f"Disk Usage:       {get_human_size(stats.get('total_stored_size_bytes', 0))}")
        
        dedup_blks = stats.get('dedup_blocks', 0)
        dedup_refs = stats.get('dedup_references', 0)
        
        print(f"Deduplication:    {dedup_blks} blocks shared by {dedup_refs} versions")
        
        if dedup_blks and dedup_refs:
            ratio = dedup_refs / dedup_blks
            print(f"Dedup Ratio:      {ratio:.2f}x")
            
    else:
        print(f"✗ Error fetching stats: {resp}")
        
    client.disconnect()

if __name__ == '__main__':
    main()
