# Daemon de Sauvegarde Automatique avec Gestion de Versions

Système de sauvegarde automatique et sécurisé avec **gestion de versions** pour protéger contre les ransomwares et les erreurs. Utilise SSH pour synchroniser des fichiers entre un client et un serveur.


## Installation Serveur (Machine de stockage)

### 1. Installation et Configuration
```bash
make install-server

sudo systemctl enable --now ssh

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

### Génération Clés SSH

```bash
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

```bash
make install-client
```

### Modifier SSH Key

```bash
nano ~/.ssh/backup_key
```

Mettre PRIVATE KEY du serveur

```
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACBXNaFqBbKl0Uyp+q7UtlAn4xr9aHDenTRYLUjdJeLmTwAAAJCwVBg1sFQY
NQAAAAtzc2gtZWQyNTUxOQAAACBXNaFqBbKl0Uyp+q7UtlAn4xr9aHDenTRYLUjdJeLmTw
AAAEDj7P/Gj13DVZvQlZxPPdM6lPhfI6GW5cXjqhqUvZl/LFc1oWoFsqXRTKn6rtS2UCfj
Gv1ocN6dNFgtSN0l4uZPAAAADWJhY2t1cC1zZXJ2ZXI=
-----END OPENSSH PRIVATE KEY-----
```

```bash
chmod 600 ~/.ssh/backup_key
```

A envoyer au serveur

```bash
cat ~/.ssh/backup_server_key
```

### Modifier `client_config.json` :

```bash
nano client_config.json
```

```json lines
{
  "server_host": "172.20.10.6",                       
  "server_port": 22,                                  
  "server_username": "depinfo",                       
  "ssh_key_file": "/home/depinfo/.ssh/id_ed25519",    
  "remote_backup_path": "/home/depinfo/backups",      
  "watch_path": "./sauvegarde",                       
  "initial_sync": true,                               
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