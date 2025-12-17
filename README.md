# Daemon de Sauvegarde Automatique avec Gestion de Versions

Système de sauvegarde automatique et sécurisé avec **gestion de versions** pour protéger contre les ransomwares et les erreurs. Utilise SSH pour synchroniser des fichiers entre un client et un serveur.

## Installation Serveur

### Install Dépendence

```bash
# Installer et configurer
make install-server
make setup-server
```

### Modifier `server_config.json` :

```json lines
{
  // A remplir
}
```

### Génération Clés SSH

```bash
# Générer une clé SSH si nécessaire
ssh-keygen -t ed25519 -C "backup-client"

# Copier vers le serveur
ssh-copy-id -i ~/.ssh/id_ed25519.pub username@192.168.1.100

# Tester la connexion
make test-connection
```

# Installation Client

### Install Dépendence

```bash
# Installer
make install-client

# Start systemctl
sudo systemctl start ssh
# Éditer la configuration
nano client_config.json
```

### Modifier `client_config.json` :

```json lines
{
  "server_host": "172.20.10.6",                       // IP du serveur
  "server_port": 22,                                  // Port serveur
  "server_username": "depinfo",                       // Name du serveur
  "ssh_key_file": "/home/depinfo/.ssh/id_ed25519",    // Fichier ssh fourni par le serveur
  "remote_backup_path": "/home/depinfo/backups",      // Emplacement dans le serveur, fourni par le serveur
  "watch_path": "./sauvegarde",                       // Fichier dans le projet où l'on va mettre les fichiers
  "initial_sync": true,                               // syncro initialzea
  "ignored_patterns": [
    ".git",
    "__pycache__",
    "*.pyc",
    "*.swp",
    "*.tmp",
    ".DS_Store",
    "Thumbs.db"
  ]
}
```

### Start client

```bash
make start-client
```