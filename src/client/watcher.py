from watchdog.events import FileSystemEventHandler
from pathlib import Path
import fnmatch
from ..common.utils import get_logger

logger = get_logger(__name__)

class BackupHandler(FileSystemEventHandler):
    """Event handler for file monitoring"""

    def __init__(self, watch_path, ssh_client, ignored_patterns=None):
        self.watch_path = Path(watch_path).resolve()
        self.ssh_client = ssh_client
        self.ignored_patterns = ignored_patterns or ['.git', '__pycache__', '*.pyc', '*.swp', '*.tmp']

    def should_ignore(self, path):
        """Checks if a file should be ignored using glob patterns"""
        path_obj = Path(path)
        name = path_obj.name
        
        for pattern in self.ignored_patterns:
            # Check matches on filename (e.g. *.swp matching file.swp)
            if fnmatch.fnmatch(name, pattern):
                return True
            # Also check if exact pattern exists in string (legacy substring support)
            # but usually fnmatch is enough.
            
        return False

    def get_relative_path(self, abs_path):
        """Gets relative path from watched directory"""
        try:
            return str(Path(abs_path).relative_to(self.watch_path))
        except ValueError:
            return str(abs_path) # Fallback

    def on_created(self, event):
        """Called when a file is created"""
        if event.is_directory or self.should_ignore(event.src_path):
            return

        logger.info(f"New file detected: {event.src_path}")
        relative_path = self.get_relative_path(event.src_path)
        self.ssh_client.send_file(event.src_path, relative_path)

    def on_modified(self, event):
        """Called when a file is modified"""
        if event.is_directory or self.should_ignore(event.src_path):
            return

        logger.info(f"File modified: {event.src_path}")
        relative_path = self.get_relative_path(event.src_path)
        self.ssh_client.send_file(event.src_path, relative_path)

    def on_deleted(self, event):
        """Called when a file is deleted"""
        if event.is_directory or self.should_ignore(event.src_path):
            return

        logger.info(f"File deleted: {event.src_path}")
        relative_path = self.get_relative_path(event.src_path)
        self.ssh_client.delete_remote_file(relative_path)

    def on_moved(self, event):
        """Called when a file is moved/renamed"""
        if event.is_directory or self.should_ignore(event.src_path):
            return

        logger.info(f"File moved: {event.src_path} -> {event.dest_path}")
        src_relative = self.get_relative_path(event.src_path)
        dest_relative = self.get_relative_path(event.dest_path)

        # Delete old file and send new one
        self.ssh_client.delete_remote_file(src_relative)
        self.ssh_client.send_file(event.dest_path, dest_relative)
