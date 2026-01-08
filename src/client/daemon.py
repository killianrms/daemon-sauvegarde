
import os
import sys
import time
from pathlib import Path
from watchdog.observers import Observer

# Add src to path if running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common.config import ConfigManager
from src.common.utils import setup_logging, get_logger
from src.client.ssh_client import SecureSSHClient
from src.client.watcher import BackupHandler

logger = get_logger(__name__)

class BackupDaemon:
    """Main Backup Daemon"""

    def __init__(self, config_file='client_config.json'):
        self.config_manager = ConfigManager(config_file)
        self.config = self.config_manager.config
        
        self.watch_path = self.config.get('watch_path', './sauvegarde')
        self.ssh_client = SecureSSHClient(self.config)
        self.observer = None
        self.running = True
        
        # Signals
        import signal
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def handle_signal(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        self.stop()

    def initial_sync(self):
        """Initial synchronization of all files"""
        logger.info("Performing initial synchronization...")
        watch_dir = Path(self.watch_path)

        if not watch_dir.exists():
            logger.error(f"Watch directory {self.watch_path} does not exist")
            return False

        for root, dirs, files in os.walk(watch_dir):
            if not self.running: break
            
            for file in files:
                if not self.running: break
                
                if '.git' in root or '__pycache__' in root:
                    continue
                    
                file_path = os.path.join(root, file)
                relative_path = str(Path(file_path).relative_to(watch_dir))
                self.ssh_client.send_file(file_path, relative_path)

        logger.info("Initial synchronization completed")
        return True

    def start(self):
        """Starts the backup daemon"""
        setup_logging('backup_client.log')
        logger.info("Starting Backup Daemon...")

        # Create watch dir if needed
        os.makedirs(self.watch_path, exist_ok=True)
        logger.info(f"Watching directory: {os.path.abspath(self.watch_path)}")

        # Connect to server
        if not self.ssh_client.connect():
            logger.error("Could not connect to server. Retrying in 5 seconds...")
            sys.exit(1)

        # Initial Sync
        if self.config.get('initial_sync', True):
            self.initial_sync()

        # Start Watching
        event_handler = BackupHandler(
            self.watch_path,
            self.ssh_client,
            self.config.get('ignored_patterns')
        )

        self.observer = Observer()
        self.observer.schedule(event_handler, self.watch_path, recursive=True)
        self.observer.start()

        logger.info("✓ Surveillance active. Press Ctrl+C to stop.")

        while self.running:
            time.sleep(0.5)
            # Check SSH health?
            # ssh_client.ensure_connection() is called on send_file, but maybe we should keepalive?
            # For now relying on on-demand reconnect.

        self.stop()

    def stop(self):
        """Stops the daemon"""
        if not self.running: # Already stopped logic
             pass # Or re-entrant safety
             
        logger.info("Stopping daemon...")
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.ssh_client.disconnect()
        logger.info("Daemon stopped")

if __name__ == '__main__':
    daemon = BackupDaemon()
    daemon.start()
