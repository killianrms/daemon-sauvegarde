
import os
import paramiko
import logging
import shlex
import json
import base64
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
        self.agent_stdin = None
        self.agent_stdout = None
        self.agent_channel = None

    def connect(self):
        """Establishes a secure SSH connection and starts the agent"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            self.ssh_client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                key_filename=self.key_file,
                timeout=10
            )
            logger.info(f"SSH connection established with {self.host}:{self.port}")
            
            # Start persistent agent
            return self.start_agent()
            
        except Exception as e:
            logger.error(f"SSH connection error: {e}")
            return False

    def start_agent(self):
        """Starts the remote agent process"""
        try:
            # Locate agent script
            # Assuming standard layout
            script_path = os.path.join(os.path.dirname(self.remote_path), 'daemon-sauvegarde', 'src', 'server', 'agent.py')
            safe_path = shlex.quote(script_path)
            safe_root = shlex.quote(self.remote_path)
            
            cmd = f'python3 {safe_path} {safe_root}'
            
            self.agent_stdin, self.agent_stdout, stderr = self.ssh_client.exec_command(cmd)
            
            # Read header
            first_line = self.agent_stdout.readline()
            if not first_line:
                error = stderr.read().decode()
                logger.error(f"Agent failed to start: {error}")
                return False
                
            try:
                resp = json.loads(first_line)
                if resp.get('status') == 'ready':
                    logger.info("✓ Remote Agent ready")
                    return True
                else:
                    logger.error(f"Agent init failed: {resp}")
                    return False
            except json.JSONDecodeError:
                logger.error(f"Invalid agent handshake: {first_line}")
                return False

        except Exception as e:
            logger.error(f"Failed to start agent: {e}")
            return False

    def ensure_connection(self):
        """Re-establishes connection if dropped"""
        if self.ssh_client and self.ssh_client.get_transport() and self.ssh_client.get_transport().is_active():
             if self.agent_stdin and not self.agent_stdin.channel.closed:
                 return True
        
        logger.warning("Connection lost. Reconnecting...")
        return self.connect()

    def _send_agent_command(self, cmd_dict):
        """Send a JSON command to the agent and wait for response of same type"""
        try:
            if not self.ensure_connection():
                return None
                
            payload = json.dumps(cmd_dict) + '\n'
            self.agent_stdin.write(payload)
            self.agent_stdin.flush()
            
            response_line = self.agent_stdout.readline()
            if not response_line:
                logger.error("Agent closed connection unexpectedly")
                self.ssh_client.close() # Force reset
                return None
                
            return json.loads(response_line)
            
        except Exception as e:
            logger.error(f"Agent communication error: {e}")
            self.ssh_client.close()
            return None

    def disconnect(self):
        """Closes the SSH connection"""
        if self.ssh_client:
            self.ssh_client.close()
            logger.info("SSH connection closed")

    def send_file(self, local_file, relative_path):
        """Sends a file to the server via Persistant Agent (Delta Sync Optimized)"""
        try:
            from src.common.delta_sync import DeltaSync
            ds = DeltaSync()
            
            # 1. Ask server for signature of existing file
            sig_cmd = {"cmd": "get_signature", "path": relative_path}
            sig_resp = self._send_agent_command(sig_cmd)
            
            used_delta = False
            
            if sig_resp and sig_resp.get('status') == 'ok' and sig_resp.get('signature'):
                 # Server has a previous version
                 signature = sig_resp['signature']
                 
                 # Calculate Delta
                 # Check if file is too small to bother? (e.g. < 4KB)
                 local_size = os.path.getsize(local_file)
                 if local_size > 4096:
                     try:
                         delta = ds.generate_delta(local_file, signature)
                         
                         # Check efficiency
                         eff = ds.get_efficiency(local_size, delta)
                         # If reduction > 10% (avoid overhead for nothing)
                         if eff['reduction_percent'] > 10:
                             # Send Delta
                             cmd = {
                                 "cmd": "save_delta",
                                 "path": relative_path,
                                 "delta": delta
                             }
                             resp = self._send_agent_command(cmd)
                             
                             if resp and resp.get('status') == 'ok':
                                 logger.info(f"✓ File synced (Delta: -{eff['reduction_percent']:.1f}%): {relative_path}")
                                 return True
                             else:
                                 logger.warning(f"⚠ Delta sync failed, falling back to full: {resp}")
                     except Exception as e:
                         logger.warning(f"⚠ Delta generation error: {e}")
            
            # Fallback to Full Send
            # Read file data
            with open(local_file, 'rb') as f:
                data = f.read()
                
            # Base64 encode
            b64_data = base64.b64encode(data).decode()
            
            cmd = {
                "cmd": "save_version",
                "path": relative_path,
                "data": b64_data
            }
            
            resp = self._send_agent_command(cmd)
            
            if resp and resp.get('status') == 'ok':
                logger.info(f"✓ File sent (Full): {relative_path}")
                return True
            else:
                msg = resp.get('message') if resp else "No response"
                logger.error(f"✗ Server error for {relative_path}: {msg}")
                return False

        except FileNotFoundError:
            logger.info(f"ℹ File vanished: {relative_path}")
            return False
        except Exception as e:
            logger.error(f"✗ Error sending {relative_path}: {e}")
            return False

    def delete_remote_file(self, relative_path):
        """Marks a file as deleted on the server"""
        cmd = {
            "cmd": "delete_file",
            "path": relative_path
        }
        resp = self._send_agent_command(cmd)
        
        if resp and resp.get('status') == 'ok':
            logger.info(f"✓ File marked deleted: {relative_path}")
            return True
        else:
             msg = resp.get('message') if resp else "No response"
             logger.error(f"✗ Error deleting {relative_path}: {msg}")
             return False
