#!/usr/bin/env python3
"""
Client de sauvegarde automatique
Surveille un dossier et envoie les fichiers modifiés au serveur via SSH
"""

import os
import sys
import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import paramiko
from scp import SCPClient
import json
import hashlib

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backup_client.log'),
        logging.StreamHandler()
    ]
)

class BackupConfig:
    """Gestion de la configuration du client"""

    def __init__(self, config_file='client_config.json'):
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self):
        """Charge la configuration depuis le fichier JSON"""
        if not os.path.exists(self.config_file):
            logging.error(f"Fichier de configuration {self.config_file} introuvable")
            sys.exit(1)

        with open(self.config_file, 'r') as f:
            return json.load(f)

    def get(self, key, default=None):
        """Récupère une valeur de configuration"""
        return self.config.get(key, default)


class SecureSSHClient:
    """Client SSH sécurisé pour le transfert de fichiers"""

    def __init__(self, config):
        self.host = config.get('server_host')
        self.port = config.get('server_port', 22)
        self.username = config.get('server_username')
        self.key_file = config.get('ssh_key_file')
        self.remote_path = config.get('remote_backup_path')
        self.ssh_client = None

    def connect(self):
        """Établit une connexion SSH sécurisée"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Connexion avec clé SSH
            self.ssh_client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                key_filename=self.key_file,
                timeout=10
            )
            logging.info(f"Connexion SSH établie avec {self.host}:{self.port}")
            return True
        except Exception as e:
            logging.error(f"Erreur de connexion SSH: {e}")
            return False

    def disconnect(self):
        """Ferme la connexion SSH"""
        if self.ssh_client:
            self.ssh_client.close()
            logging.info("Connexion SSH fermée")

    def send_file(self, local_file, relative_path):
        """Envoie un fichier au serveur via SCP avec gestion de versions"""
        try:
            # Reconnecter si nécessaire
            if not self.ssh_client or not self.ssh_client.get_transport() or not self.ssh_client.get_transport().is_active():
                self.connect()

            # Créer un dossier temporaire sur le serveur
            temp_dir = os.path.join(self.remote_path, '.tmp')
            stdin, stdout, stderr = self.ssh_client.exec_command(f'mkdir -p "{temp_dir}"')
            stdout.channel.recv_exit_status()

            # Nom du fichier temporaire
            import random
            import string
            temp_name = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            temp_file = os.path.join(temp_dir, temp_name)

            # Transfert du fichier vers le temporaire
            with SCPClient(self.ssh_client.get_transport()) as scp:
                scp.put(local_file, temp_file)

            # Appeler le script de traitement avec gestion de versions
            script_path = os.path.join(os.path.dirname(self.remote_path), 'daemon-sauvegarde', 'process_file.py')
            cmd = f'python3 "{script_path}" "{temp_file}" "{relative_path}" "{self.remote_path}"'
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode().strip()

            # Nettoyer le fichier temporaire
            self.ssh_client.exec_command(f'rm -f "{temp_file}"')

            if exit_code == 0:
                logging.info(f"✓ Fichier envoyé avec version: {relative_path}")
                return True
            else:
                logging.error(f"✗ Erreur de traitement: {output}")
                return False

        except Exception as e:
            logging.error(f"✗ Erreur lors de l'envoi de {relative_path}: {e}")
            return False

    def delete_remote_file(self, relative_path):
        """Supprime un fichier sur le serveur avec sauvegarde de version"""
        try:
            if not self.ssh_client or not self.ssh_client.get_transport() or not self.ssh_client.get_transport().is_active():
                self.connect()

            # Appeler le script de traitement avec action "deleted"
            script_path = os.path.join(os.path.dirname(self.remote_path), 'daemon-sauvegarde', 'process_file.py')
            cmd = f'python3 "{script_path}" "/dev/null" "{relative_path}" "{self.remote_path}" "deleted"'
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
            exit_code = stdout.channel.recv_exit_status()

            if exit_code == 0:
                logging.info(f"✓ Fichier supprimé avec version sauvegardée: {relative_path}")
                return True
            else:
                logging.error(f"✗ Erreur lors de la suppression de {relative_path}")
                return False

        except Exception as e:
            logging.error(f"✗ Erreur lors de la suppression de {relative_path}: {e}")
            return False


class BackupHandler(FileSystemEventHandler):
    """Gestionnaire d'événements pour la surveillance de fichiers"""

    def __init__(self, watch_path, ssh_client, ignored_patterns=None):
        self.watch_path = Path(watch_path).resolve()
        self.ssh_client = ssh_client
        self.ignored_patterns = ignored_patterns or ['.git', '__pycache__', '*.pyc', '*.swp', '*.tmp']

    def should_ignore(self, path):
        """Vérifie si un fichier doit être ignoré"""
        path_str = str(path)
        for pattern in self.ignored_patterns:
            if pattern in path_str:
                return True
        return False

    def get_relative_path(self, abs_path):
        """Obtient le chemin relatif par rapport au dossier surveillé"""
        return str(Path(abs_path).relative_to(self.watch_path))

    def on_created(self, event):
        """Appelé quand un fichier est créé"""
        if event.is_directory or self.should_ignore(event.src_path):
            return

        logging.info(f"Nouveau fichier détecté: {event.src_path}")
        relative_path = self.get_relative_path(event.src_path)
        self.ssh_client.send_file(event.src_path, relative_path)

    def on_modified(self, event):
        """Appelé quand un fichier est modifié"""
        if event.is_directory or self.should_ignore(event.src_path):
            return

        logging.info(f"Fichier modifié: {event.src_path}")
        relative_path = self.get_relative_path(event.src_path)
        self.ssh_client.send_file(event.src_path, relative_path)

    def on_deleted(self, event):
        """Appelé quand un fichier est supprimé"""
        if event.is_directory or self.should_ignore(event.src_path):
            return

        logging.info(f"Fichier supprimé: {event.src_path}")
        relative_path = self.get_relative_path(event.src_path)
        self.ssh_client.delete_remote_file(relative_path)

    def on_moved(self, event):
        """Appelé quand un fichier est déplacé/renommé"""
        if event.is_directory or self.should_ignore(event.src_path):
            return

        logging.info(f"Fichier déplacé: {event.src_path} -> {event.dest_path}")
        src_relative = self.get_relative_path(event.src_path)
        dest_relative = self.get_relative_path(event.dest_path)

        # Supprimer l'ancien fichier et envoyer le nouveau
        self.ssh_client.delete_remote_file(src_relative)
        self.ssh_client.send_file(event.dest_path, dest_relative)


class BackupDaemon:
    """Daemon principal de sauvegarde"""

    def __init__(self, config_file='client_config.json'):
        self.config = BackupConfig(config_file)
        self.watch_path = self.config.get('watch_path', './sauvegarde')
        self.ssh_client = SecureSSHClient(self.config)
        self.observer = None

    def initial_sync(self):
        """Synchronisation initiale de tous les fichiers"""
        logging.info("Synchronisation initiale en cours...")
        watch_dir = Path(self.watch_path)

        if not watch_dir.exists():
            logging.error(f"Le dossier {self.watch_path} n'existe pas")
            return False

        for root, dirs, files in os.walk(watch_dir):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = str(Path(file_path).relative_to(watch_dir))
                self.ssh_client.send_file(file_path, relative_path)

        logging.info("Synchronisation initiale terminée")
        return True

    def start(self):
        """Démarre le daemon de sauvegarde"""
        logging.info("Démarrage du daemon de sauvegarde...")

        # Créer le dossier de sauvegarde s'il n'existe pas
        os.makedirs(self.watch_path, exist_ok=True)
        logging.info(f"Dossier surveillé: {os.path.abspath(self.watch_path)}")

        # Connexion au serveur
        if not self.ssh_client.connect():
            logging.error("Impossible de se connecter au serveur")
            sys.exit(1)

        # Synchronisation initiale
        if self.config.get('initial_sync', True):
            self.initial_sync()

        # Démarrer la surveillance
        event_handler = BackupHandler(
            self.watch_path,
            self.ssh_client,
            self.config.get('ignored_patterns')
        )

        self.observer = Observer()
        self.observer.schedule(event_handler, self.watch_path, recursive=True)
        self.observer.start()

        logging.info("✓ Surveillance active. Appuyez sur Ctrl+C pour arrêter.")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Arrête le daemon"""
        logging.info("Arrêt du daemon...")
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.ssh_client.disconnect()
        logging.info("Daemon arrêté")


if __name__ == '__main__':
    daemon = BackupDaemon()
    daemon.start()
