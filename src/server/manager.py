#!/usr/bin/env python3
"""
Serveur de sauvegarde
Script d'aide pour la configuration du serveur SSH
"""

import os
import sys
import json
import subprocess
from pathlib import Path

class BackupServer:
    """Configuration et gestion du serveur de sauvegarde"""

    def __init__(self, config_file='server_config.json'):
        self.config_file = config_file
        self.config = self.load_or_create_config()

    def load_or_create_config(self):
        """Charge ou crée la configuration du serveur"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        else:
            # Configuration par défaut
            config = {
                'backup_path': os.path.expanduser('~/backups'),
                'ssh_port': 22,
                'allowed_users': []
            }
            self.save_config(config)
            return config

    def save_config(self, config=None):
        """Sauvegarde la configuration"""
        if config:
            self.config = config
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    def setup(self):
        """Configure le serveur de sauvegarde"""
        print("=== Configuration du serveur de sauvegarde ===\n")

        # Créer le dossier de sauvegarde
        backup_path = self.config['backup_path']
        os.makedirs(backup_path, exist_ok=True)
        print(f"✓ Dossier de sauvegarde créé: {backup_path}")

        # Vérifier SSH
        self.check_ssh_service()

        # Générer une paire de clés SSH si nécessaire
        self.setup_ssh_keys()

        print("\n=== Configuration terminée ===")
        print(f"Les sauvegardes seront stockées dans: {backup_path}")
        print("\nÉtapes suivantes:")
        print("1. Copiez la clé publique SSH vers le client")
        print("2. Configurez le fichier client_config.json sur le client")
        print("3. Lancez le client avec: python3 client.py")

    def check_ssh_service(self):
        """Vérifie que le service SSH est actif"""
        try:
            result = subprocess.run(['systemctl', 'is-active', 'ssh'],
                                    capture_output=True, text=True)
            if result.stdout.strip() == 'active':
                print("✓ Service SSH actif")
                return True
            else:
                print("⚠ Service SSH non actif")
                print("Pour l'activer: sudo systemctl start ssh")
                print("Pour l'activer au démarrage: sudo systemctl enable ssh")
                return False
        except FileNotFoundError:
            try:
                result = subprocess.run(['systemctl', 'is-active', 'sshd'],
                                        capture_output=True, text=True)
                if result.stdout.strip() == 'active':
                    print("✓ Service SSH actif")
                    return True
            except:
                pass
            print("⚠ Impossible de vérifier le service SSH")
            print("Assurez-vous qu'un serveur SSH est installé (openssh-server)")
            return False

    def setup_ssh_keys(self):
        """Configure les clés SSH pour le serveur"""
        ssh_dir = Path.home() / '.ssh'
        ssh_dir.mkdir(mode=0o700, exist_ok=True)

        key_file = ssh_dir / 'backup_server_key'
        pub_key_file = ssh_dir / 'backup_server_key.pub'

        if key_file.exists():
            print(f"✓ Clés SSH existantes trouvées: {key_file}")
        else:
            print("Génération d'une nouvelle paire de clés SSH...")
            subprocess.run([
                'ssh-keygen', '-t', 'ed25519',
                '-f', str(key_file),
                '-N', '',
                '-C', 'backup-server'
            ])
            print(f"✓ Clés SSH générées: {key_file}")

        # Afficher la clé publique
        if pub_key_file.exists():
            with open(pub_key_file, 'r') as f:
                pub_key = f.read()
            print(f"\n--- Clé publique SSH ---")
            print(pub_key)
            print("------------------------\n")
            print("Ajoutez cette clé au fichier ~/.ssh/authorized_keys du serveur")

    def get_server_info(self):
        """Affiche les informations du serveur"""
        print("\n=== Informations du serveur ===")
        print(f"Dossier de sauvegarde: {self.config['backup_path']}")
        print(f"Port SSH: {self.config['ssh_port']}")

        # Obtenir l'adresse IP
        try:
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
            ips = result.stdout.strip().split()
            if ips:
                print(f"Adresse IP: {ips[0]}")
        except:
            print("Adresse IP: (non détectée)")

        print("\nUtilisez ces informations pour configurer le client")

    def show_logs(self):
        """Affiche les derniers logs d'accès SSH"""
        print("\n=== Derniers accès SSH ===")
        try:
            subprocess.run(['tail', '-n', '20', '/var/log/auth.log'])
        except:
            try:
                subprocess.run(['tail', '-n', '20', '/var/log/secure'])
            except:
                print("Impossible d'accéder aux logs SSH")


def main():
    """Menu principal du serveur"""
    server = BackupServer()

    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == 'setup':
            server.setup()
        elif command == 'info':
            server.get_server_info()
        elif command == 'logs':
            server.show_logs()
        else:
            print(f"Commande inconnue: {command}")
            print_usage()
    else:
        server.setup()


def print_usage():
    """Affiche l'aide"""
    print("Usage: python3 server.py [commande]")
    print("\nCommandes:")
    print("  setup   - Configure le serveur (par défaut)")
    print("  info    - Affiche les informations du serveur")
    print("  logs    - Affiche les logs SSH récents")


if __name__ == '__main__':
    main()
