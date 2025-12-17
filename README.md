# Daemon de Sauvegarde Automatique avec Gestion de Versions

Système de sauvegarde automatique et sécurisé avec **gestion de versions** pour protéger contre les ransomwares et les erreurs. Utilise SSH pour synchroniser des fichiers entre un client et un serveur.


## Installation Serveur (Machine de stockage)

### 1. Installation et Configuration
```bash
# Installer les dépendances (crée un environnement virtuel)
make install-server

# Démarrer le service SSH (Crucial !)
sudo systemctl enable --now ssh

# Configurer le serveur (Génération de clés, dossiers...)
make setup-server
```

### 2. Configuration `server_config.json`
Le fichier est généré automatiquement, mais vous pouvez le modifier :
```json
{
  "backup_path": "~/backups",
  "ssh_port": 22,
  "allowed_users": []
}
```

### 3. Autoriser un Client
Pour qu'un client puisse se connecter, vous devez ajouter sa **clé publique** (`id_ed25519.pub`) dans le fichier des clés autorisées du serveur :
```bash
# Éditer le fichier
nano ~/.ssh/authorized_keys
# Coller la clé publique du client sur une nouvelle ligne
```

### 4. Interface Web
Pour suivre les sauvegardes :
```bash
make web-start
# Accès : http://localhost:5000 (Login: admin / Pass: admin)
```

# Installation Client

### Install Dépendence


# Installer
make install-client

# Éditer la configuration
nano client_config.json


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