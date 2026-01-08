#!/usr/bin/env python3
"""
Server-side Backup Agent
Runs as a persistent process handling commands via Stdin/Stdout.
Protocol: Line-delimited JSON.
"""

import sys
import os
import json
import base64
import signal
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from version_manager import VersionManager

class BackupAgent:
    def __init__(self, backup_root):
        self.backup_root = backup_root
        self.vm = VersionManager(backup_root)
        self.running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def handle_signal(self, signum, frame):
        self.running = False

    def respond(self, data):
        """Send JSON response to stdout"""
        try:
            sys.stdout.write(json.dumps(data) + '\n')
            sys.stdout.flush()
        except BrokenPipeError:
            self.running = False

    def run(self):
        """Main loop"""
        self.respond({"status": "ready", "version": "2.0"})
        
        while self.running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                
                try:
                    cmd_data = json.loads(line)
                    self.process_command(cmd_data)
                except json.JSONDecodeError:
                    self.respond({"error": "Invalid JSON"})
                except Exception as e:
                    self.respond({"error": str(e)})
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                # Fatal error
                sys.stderr.write(f"Agent Fatal Error: {e}\n")
                break

    def process_command(self, cmd):
        command = cmd.get('cmd')
        
        if command == 'ping':
            self.respond({"pong": True})
            
        elif command == 'save_version':
            self.handle_save_version(cmd)
            
        elif command == 'delete_file':
            self.handle_delete_file(cmd)
            
        elif command == 'get_signature':
            self.handle_get_signature(cmd)
            
        elif command == 'save_delta':
            self.handle_save_delta(cmd)
            
        elif command == 'get_stats':
            self.handle_get_stats(cmd)
            
        elif command == 'prune':
            self.handle_prune(cmd)
            
        elif command == 'gc':
            self.handle_gc(cmd)
            
        else:
            self.respond({"error": f"Unknown command: {command}"})

    def handle_gc(self, cmd):
        try:
            # Run GC logic
            # GC is in src/server/gc.py. 
            # It's a script not a class?
            # Let's check gc.py content. 
            # It has `cleanup_dedup(backup_root)`.
            
            from gc import cleanup_dedup
            
            # Capture output? cleanup_dedup prints to stdout.
            # We want to return status.
            # Modifying gc.py to return stats is better, but importing and running is OK.
            # We can just run it.
            
            # Actually, `cleanup_dedup` prints. 
            # Ideally we refactor gc.py to return dict.
            # But for now, we just run it and say OK.
            
            cleanup_dedup(self.vm.backup_root)
            self.respond({"status": "ok", "message": "Garbage Collection completed"})
            
        except Exception as e:
            self.respond({"status": "error", "message": str(e)})

    def handle_prune(self, cmd):
        relative_path = cmd.get('path') # Optional, if None prune all?
        # RetentionManager logic I wrote handles specific file. Prune all is usually a loop.
        
        try:
            from retention import RetentionManager
            rm = RetentionManager(self.vm)
            
            if relative_path:
                count = rm.prune_history(relative_path)
                self.respond({"status": "ok", "pruned": count})
            else:
                # Prune ALL files
                # Need to iterate all unique files
                conn = self.vm._get_db_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT DISTINCT file_path FROM file_versions')
                files = [row[0] for row in cursor.fetchall()]
                conn.close()
                
                total_pruned = 0
                for f in files:
                    total_pruned += rm.prune_history(f)
                    
                self.respond({"status": "ok", "pruned": total_pruned})
                
        except Exception as e:
            print(f"Prune Error: {e}") # Debug
            self.respond({"status": "error", "message": str(e)})

    def handle_get_stats(self, cmd):
        try:
             stats = self.vm.get_global_stats()
             self.respond({"status": "ok", "stats": stats})
        except Exception as e:
            self.respond({"status": "error", "message": str(e)})

    def handle_get_signature(self, cmd):
        relative_path = cmd.get('path')
        try:
             # Validate Path? VersionManager gets it and validates it.
             # Wait, does VM validate on get_file_signature? 
             # VM._validate_path is used in SAVE/DELETE. 
             # We should probably validate on GET too to avoid reading arbitrary files.
             # Check VM code... I only added validation to save_version and delete_file.
             # I SHOULD add it to get_file_signature in next step or now?
             # Let's trust VM handles it or will handle it. 
             # Actually, VM.get_file_signature queries DB by file_path. 
             # If path is ../../passwd, it won't be in DB. So it returns None. Safe.
             
             signature = self.vm.get_file_signature(relative_path)
             if signature:
                 self.respond({"status": "ok", "signature": signature})
             else:
                 self.respond({"status": "not_found"})
                 
        except Exception as e:
            self.respond({"status": "error", "message": str(e)})

    def handle_save_delta(self, cmd):
        relative_path = cmd.get('path')
        delta_data = cmd.get('delta')
        
        if not delta_data:
             self.respond({"status": "error", "message": "Missing delta data"})
             return
             
        try:
             success = self.vm.save_file_from_delta(relative_path, delta_data)
             if success:
                 self.respond({"status": "ok", "path": relative_path})
             else:
                 self.respond({"status": "error", "message": "Delta save failed"})
        except Exception as e:
            self.respond({"status": "error", "message": str(e)})

    def handle_save_version(self, cmd):
        relative_path = cmd.get('path')
        b64_data = cmd.get('data')
        # TODO: Support Delta in future command or flag
        
        try:
            # Decode data to temp file
            import tempfile
            
            # Using mkstemp to avoid name collisions in high concurrency? 
            # Agent is single threaded per connection, but good practice.
            fd, temp_path = tempfile.mkstemp(prefix='agent_upload_')
            with os.fdopen(fd, 'wb') as f:
                f.write(base64.b64decode(b64_data))
                
            try:
                # Process with VersionManager
                # Note: VersionManager now does path validation!
                success = self.vm.save_version(temp_path, relative_path)
                
                if success:
                    self.respond({"status": "ok", "path": relative_path})
                else:
                    self.respond({"status": "error", "message": "Save failed internally"})
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except Exception as e:
            self.respond({"status": "error", "message": str(e)})

    def handle_delete_file(self, cmd):
        relative_path = cmd.get('path')
        try:
            success = self.vm.delete_file(relative_path)
            if success:
                 self.respond({"status": "ok"})
            else:
                 self.respond({"status": "error", "message": "Delete failed"})
        except Exception as e:
            self.respond({"status": "error", "message": str(e)})

if __name__ == '__main__':
    # Parse args or config? 
    # Usually received via manager or just hardcoded/config file assumed in same dir.
    # Let's try to load server config or use arg.
    
    config_path = os.path.join(os.path.dirname(__file__), '../../server_config.json')
    backup_root = os.path.expanduser('~/backups')

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                c = json.load(f)
                backup_root = c.get('backup_path', backup_root)
        except:
            pass
            
    # Allow override via args
    if len(sys.argv) > 1:
        backup_root = sys.argv[1]
        
    agent = BackupAgent(backup_root)
    agent.run()
