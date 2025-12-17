
import os
import paramiko
from scp import SCPClient
import logging
import random
import string
import shlex
from ..common.utils import get_logger

logger = get_logger(__name__)

class SecureSSHClient:
    """Secure SSH Client for file transfer with versioning support"""

    def __init__(self, config):
        self.host = config.get('server_host')
        self.port = config.get('server_port', 22)
        self.username = config.get('server_username')
        self.key_file = config.get('ssh_key_file')
        self.remote_path = config.get('remote_backup_path')
        self.ssh_client = None

    def connect(self):
        """Establishes a secure SSH connection"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Connect with SSH key
            self.ssh_client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                key_filename=self.key_file,
                timeout=10
            )
            logger.info(f"SSH connection established with {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"SSH connection error: {e}")
            return False

    def disconnect(self):
        """Closes the SSH connection"""
        if self.ssh_client:
            self.ssh_client.close()
            logger.info("SSH connection closed")

    def ensure_connection(self):
        """Re-establishes connection if dropped"""
        if not self.ssh_client or not self.ssh_client.get_transport() or not self.ssh_client.get_transport().is_active():
            return self.connect()
        return True

    def send_file(self, local_file, relative_path):
        """Sends a file to the server via SCP with versioning"""
        try:
            if not self.ensure_connection():
                return False

            # Create temp dir on server
            temp_dir = os.path.join(self.remote_path, '.tmp')
            # Use shlex for remote path too, though it comes from config and is trusted-ish, better safe.
            # However mkdir -p usually takes straight path.
            # Using exec_command implies shell execution.
            
            # SAFE: escaping arguments
            safe_temp_dir = shlex.quote(temp_dir)
            stdin, stdout, stderr = self.ssh_client.exec_command(f'mkdir -p {safe_temp_dir}')
            if stdout.channel.recv_exit_status() != 0:
                 logger.error(f"Failed to create temp dir: {stderr.read().decode()}")
                 return False

            # Temp filename
            temp_name = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            temp_file = os.path.join(temp_dir, temp_name)

            # SCP transfer
            with SCPClient(self.ssh_client.get_transport()) as scp:
                scp.put(local_file, temp_file)

            # Call processing script on server
            # Assuming process_file.py is in a standard location relative to daemon setup
            # We might need a better way to locate it, but for now guarding the args is key.
            # The original code assumed: os.path.join(os.path.dirname(self.remote_path), 'daemon-sauvegarde', 'process_file.py')
            # This path logic seems a bit fragile but I will preserve it or improve if obviously broken.
            # I'll stick to preserving the logic but securing the args.
            
            start_path = os.path.dirname(self.remote_path) if self.remote_path.endswith('/') else os.path.dirname(self.remote_path + '/')
            # If remote_path is /home/user/backups, dirname is /home/user
            # Original code: os.path.dirname(self.remote_path)
            

            script_path = os.path.join(os.path.dirname(self.remote_path), 'daemon-sauvegarde', 'src', 'server', 'process_file.py')
            
            # SECURE COMMAND CONSTRUCTION
            cmd = (
                f'python3 {shlex.quote(script_path)} '
                f'{shlex.quote(temp_file)} '
                f'{shlex.quote(relative_path)} '
                f'{shlex.quote(self.remote_path)}'
            )
            
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode().strip()
            error_out = stderr.read().decode().strip()

            # Clean up temp file
            self.ssh_client.exec_command(f'rm -f {shlex.quote(temp_file)}')

            if exit_code == 0:
                logger.info(f"✓ File sent with version: {relative_path}")
                return True
            else:
                logger.error(f"✗ Protocol error: {output} {error_out}")
                return False

        except FileNotFoundError:
            logger.info(f"ℹ File vanished before transfer: {relative_path} (likely temporary)")
            return False
        except Exception as e:
            # Check if it's an SCP error related to missing file (sometimes wrapped)
            if "No such file" in str(e):
                 logger.info(f"ℹ File vanished during transfer: {relative_path}")
                 return False
            logger.error(f"✗ Error sending {relative_path}: {e}")
            return False

    def delete_remote_file(self, relative_path):
        """Marks a file as deleted on the server"""
        try:
            if not self.ensure_connection():
                return False


            script_path = os.path.join(os.path.dirname(self.remote_path), 'daemon-sauvegarde', 'src', 'server', 'process_file.py')
            
            # SECURE COMMAND
            cmd = (
                f'python3 {shlex.quote(script_path)} '
                f'/dev/null '  # dummy temp file
                f'{shlex.quote(relative_path)} '
                f'{shlex.quote(self.remote_path)} '
                f'deleted'
            )

            stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
            exit_code = stdout.channel.recv_exit_status()

            if exit_code == 0:
                logger.info(f"✓ File marked deleted: {relative_path}")
                return True
            else:
                logger.error(f"✗ Error deleting {relative_path}: {stdout.read().decode()}")
                return False

        except Exception as e:
            logger.error(f"✗ Error deleting {relative_path}: {e}")
            return False
