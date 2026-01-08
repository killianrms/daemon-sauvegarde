#!/usr/bin/env python3
"""
Remote Management Tool for Backup System
"""

import sys
import os
import argparse
import json

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.common.config import ConfigManager
from src.client.ssh_client import SecureSSHClient

def run_command(command, args=None):
    config_file = 'client_config.json'
    cm = ConfigManager(config_file)
    client = SecureSSHClient(cm.config)
    
    print(f"Connecting to {cm.config.get('server_host')}...")
    if not client.connect():
        print("✗ Connection failed.")
        sys.exit(1)
        
    cmd_payload = {"cmd": command}
    if args:
        cmd_payload.update(args)
        
    print(f"Executing '{command}'...")
    resp = client._send_agent_command(cmd_payload)
    
    client.disconnect()
    
    if resp and resp.get('status') == 'ok':
        print(f"✓ Success: {json.dumps(resp, indent=2)}")
    else:
        print(f"✗ Failed: {resp}")

def main():
    parser = argparse.ArgumentParser(description="Backup System Manager")
    subparsers = parser.add_subparsers(dest='action', help='Action to perform')
    
    # Prune
    prune_parser = subparsers.add_parser('prune', help='Run Retention Policy')
    prune_parser.add_argument('--path', help='Specific file path to prune')
    
    # GC
    gc_parser = subparsers.add_parser('gc', help='Run Garbage Collection')
    
    # Stats
    stats_parser = subparsers.add_parser('stats', help='Get Server Stats')
    
    args = parser.parse_args()
    
    if args.action == 'prune':
        payload = {}
        if args.path: payload['path'] = args.path
        run_command('prune', payload)
        
    elif args.action == 'gc':
        run_command('gc')
        
    elif args.action == 'stats':
        run_command('get_stats')
        
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
