# Daemon de Sauvegarde Automatique avec Gestion de Versions

Système de sauvegarde automatique et sécurisé avec **gestion de versions** pour protéger contre les ransomwares et les erreurs. Utilise SSH pour synchroniser des fichiers entre un client et un serveur.

## 🎯 Fonctionnalités principales

### Sauvegarde automatique
- ✅ Surveillance en temps réel des fichiers (création, modification, suppression, déplacement)
- ✅ Transfert sécurisé via SSH/SCP avec chiffrement
- ✅ Synchronisation initiale automatique
- ✅ Support des sous-dossiers (récursif)
- ✅ Filtrage de fichiers (ignore .git, __pycache__, etc.)
- ✅ Logging détaillé des opérations
- ✅ Reconnexion automatique en cas de déconnexion


### Gestion de versions et Sécurité (NOUVEAU !)
- ✅ **Historique complet de tous les fichiers**
- ✅ **Rétention de 30 jours par défaut** (configurable)
- ✅ **Chiffrement AES-256** des sauvegardes archivées (Protection au repos)
- ✅ **Protection contre les ransomwares** - possibilité de restaurer avant l'attaque
- ✅ **Restauration à une date précise** - revenez à n'importe quel moment
- ✅ **Base de données SQLite** pour métadonnées
- ✅ **Nettoyage automatique** des anciennes versions
- ✅ **Statistiques détaillées** sur l'utilisation
- ✅ **Interface Web** avec authentification pour la gestion

## Architecture

- **Serveur** : Votre PC qui reçoit, chiffre et stocke les sauvegardes
- **Client** : PC distant qui surveille un dossier et envoie automatiquement les modifications

### Structure de stockage

```
~/backups/
├── current/              # Fichiers actuels
├── versions/             # Versions horodatées
│   ├── 2025-01-15_14-30-00-123456/
│   ├── 2025-01-15_15-45-00-789012/
│   └── ...
└── metadata.db          # Base de données des versions
```

## Prérequis

### Sur le serveur (votre PC)
- Python 3.7+
- Serveur SSH (OpenSSH)
- Accès réseau

### Sur le client
- Python 3.7+
- Accès réseau au serveur
- Clé SSH pour l'authentification

## Installation rapide avec Makefile

### 1. Configuration du serveur (votre PC)

```bash
# Cloner le dépôt
git clone git@github.com:killianrms/daemon-sauvegarde.git
cd daemon-sauvegarde

# Installer et configurer
make install-server
make setup-server
```

### 2. Configuration du client

```bash
# Sur le PC client, cloner le dépôt
git clone git@github.com:killianrms/daemon-sauvegarde.git
cd daemon-sauvegarde

# Installer
make install-client

# Éditer la configuration
nano client_config.json
```

Modifier `client_config.json` :

```json
{
  "server_host": "192.168.1.100",
  "server_username": "votre_username",
  "ssh_key_file": "~/.ssh/id_ed25519",
  "remote_backup_path": "/home/votre_username/backups",
  "watch_path": "./sauvegarde",
  "initial_sync": true
}
```

### 3. Configuration SSH

```bash
# Générer une clé SSH si nécessaire
ssh-keygen -t ed25519 -C "backup-client"

# Copier vers le serveur
ssh-copy-id -i ~/.ssh/id_ed25519.pub username@192.168.1.100

# Tester la connexion
make test-connection
```

### 4. Démarrer le client

```bash
make start-client
```

## Utilisation

### Commandes de base

#### Sur le client

```bash
make start-client          # Démarre le daemon (interactif)
make start-client-bg       # Démarre en arrière-plan
make stop-client           # Arrête le daemon
make status-client         # Vérifie le statut
make logs                  # Affiche les logs
```

#### Sur le serveur

```bash
make start-server          # Vérifie que SSH est actif
make info-server           # Affiche les infos du serveur
make logs-server           # Logs SSH récents
```

### 🔄 Gestion des versions (Serveur)

#### Statistiques

```bash
make stats                 # Affiche les statistiques détaillées
```

Exemple de sortie :
```
📊 Vue d'ensemble:
  - Versions totales: 145
  - Fichiers uniques: 23
  - Espace total: 256.45 MB
  - Espace moyen/version: 1.77 MB

📅 Activité des 30 derniers jours:
  2025-01-15: 12 versions
  2025-01-14: 8 versions
```

#### Restauration interactive

```bash
make restore-interactive
```

Menu interactif pour :
- Lister tous les fichiers avec versions
- Restaurer un fichier spécifique
- Restaurer tous les fichiers à une date

#### Restaurer un fichier spécifique

```bash
# Lister les versions d'un fichier
make list-versions FILE=documents/rapport.pdf

# Restaurer une version spécifique
make restore FILE=documents/rapport.pdf VERSION=2025-01-15_14-30-00-123456
```

#### Restaurer à une date précise

```bash
# Restaure tous les fichiers tels qu'ils étaient le 15 janvier 2025
make restore-date DATE=2025-01-15
```

Les fichiers restaurés seront dans le dossier `./restored/`

#### Nettoyage des anciennes versions

```bash
# Simuler le nettoyage (ne supprime rien)
make cleanup-dry-run

# Nettoyer les versions > 30 jours
make cleanup

# Nettoyer avec rétention personnalisée (60 jours)
make cleanup-custom RETENTION=60
```

#### Automatiser le nettoyage avec cron

```bash
# Affiche la commande cron à ajouter
make setup-cron
```

Cela affichera :
```bash
# Pour un nettoyage quotidien à 2h du matin
0 2 * * * /usr/bin/python3 /path/to/cleanup.py /home/user/backups --retention 30
```

## Scénarios d'utilisation

### 🛡️ Protection contre ransomware

Si vous détectez un ransomware qui a chiffré vos fichiers aujourd'hui :

```bash
# 1. Arrêter le client immédiatement
make stop-client

# 2. Sur le serveur, restaurer à hier
make restore-date DATE=2025-01-14

# 3. Récupérer les fichiers sains dans ./restored/
```

### 📝 Récupérer une ancienne version d'un document

```bash
# Lister les versions
make list-versions FILE=rapport.docx

# Restaurer la version de ce matin
make restore FILE=rapport.docx VERSION=2025-01-15_09-00-00-123456
```

### 🧹 Maintenance régulière

```bash
# Vérifier l'espace utilisé
make stats

# Simuler le nettoyage
make cleanup-dry-run

# Nettoyer si nécessaire
make cleanup
```

## Commandes Makefile complètes

### Installation
```bash
make help                  # Affiche toutes les commandes
make install              # Installe les dépendances
make install-venv         # Crée un environnement virtuel
make install-server       # Installe côté serveur
make install-client       # Installe côté client
```

### Configuration
```bash
make setup-server         # Configure le serveur
make setup-client         # Aide à configurer le client
make test-connection      # Teste la connexion SSH
```

### Opération
```bash
make start-client         # Démarre le client
make start-client-bg      # Démarre en arrière-plan
make stop-client          # Arrête le client
make status-client        # Statut du client
make logs                 # Logs du client
make logs-server          # Logs SSH du serveur
```

### Restauration
```bash
make restore-interactive  # Mode interactif
make restore FILE=... VERSION=...  # Restaure un fichier
make restore-date DATE=...         # Restaure à une date
make list-versions        # Liste toutes les versions
make list-versions FILE=...        # Versions d'un fichier
```

### Maintenance
```bash
make stats                # Statistiques
make cleanup              # Nettoie > 30 jours
make cleanup-dry-run      # Simulation
make cleanup-custom RETENTION=60  # Rétention personnalisée
make setup-cron           # Configure cron
```

### Utilitaires
```bash
make info-server          # Infos serveur
make info-client          # Infos client
make backup-test          # Crée un fichier test
make clean                # Nettoie les temporaires
```

## Sécurité

- **Chiffrement** : Toutes les communications SSH sont chiffrées
- **Authentification** : Clés SSH uniquement (pas de mot de passe)
- **Isolation** : Le serveur ne reçoit que dans le dossier configuré
- **Versions** : Protection contre la suppression et la modification malveillante
- **Logs** : Toutes les opérations sont enregistrées

### Recommandations

1. **Clés SSH** : Utilisez des clés ED25519 ou RSA 4096 bits
2. **Pare-feu** : Limitez l'accès SSH aux IPs connues
3. **Nettoyage** : Configurez le nettoyage automatique avec cron
4. **Surveillance** : Vérifiez régulièrement les statistiques
5. **Tests** : Testez la restauration régulièrement

```bash
# Configuration pare-feu (serveur)
sudo ufw allow from 192.168.1.0/24 to any port 22
```


## Structure du projet

```
daemon-sauvegarde/
├── src/
│   ├── client/            # Code du client (daemon, watcher, ssh)
│   ├── server/            # Code du serveur (version_manager, restore, encryption)
│   ├── web/               # Interface web
│   └── common/            # Code partagé (config, utils)
├── client_config.json     # Configuration client
├── server_config.json     # Configuration serveur
├── requirements.txt       # Dépendances Python
├── Makefile              # Commandes automatisées
├── .gitignore
└── README.md
```

## Dépannage

### Le client ne se connecte pas

```bash
# Vérifier la connectivité
ping 192.168.1.100

# Tester SSH
make test-connection

# Vérifier les permissions de la clé
chmod 600 ~/.ssh/id_ed25519
```

### Les fichiers ne sont pas versionnés

```bash
# Vérifier les logs client
make logs

# Vérifier que process_file.py est accessible sur le serveur
ssh user@server "ls -la ~/daemon-sauvegarde/process_file.py"

# Vérifier les permissions
chmod +x ~/daemon-sauvegarde/process_file.py
```

### Erreur "metadata.db locked"

```bash
# Vérifier qu'aucun autre processus n'accède à la DB
lsof ~/backups/metadata.db

# Si nécessaire, redémarrer
make stop-client
make start-client
```

### Espace disque insuffisant

```bash
# Vérifier l'utilisation
make stats

# Simuler le nettoyage
make cleanup-dry-run

# Nettoyer avec rétention réduite
make cleanup-custom RETENTION=15
```

## Performance

- **Surveillance** : Utilise `watchdog` pour des événements en temps réel
- **Transfert** : SCP optimisé avec compression
- **Stockage** : Versions incrémentales (seuls les fichiers modifiés sont sauvegardés)
- **Base de données** : SQLite avec index pour des requêtes rapides
- **Nettoyage** : Opération en arrière-plan, sans impact sur les sauvegardes

## Exemples avancés

### Script de sauvegarde automatique

```bash
#!/bin/bash
# backup-cron.sh

cd /home/user/daemon-sauvegarde

# Vérifier le statut
make status-client || make start-client-bg

# Nettoyer si nécessaire (une fois par semaine)
if [ $(date +%u) -eq 1 ]; then
    make cleanup
fi
```

### Restauration après incident

```bash
# 1. Identifier la date avant l'incident
make stats

# 2. Lister les fichiers disponibles
make list-versions

# 3. Restaurer tout à la bonne date
make restore-date DATE=2025-01-14

# 4. Vérifier les fichiers restaurés
ls -lR ./restored/

# 5. Copier où nécessaire
rsync -av ./restored/ /destination/
```

## Contribution

Ce projet est open source. N'hésitez pas à contribuer !

## Support

- Consultez les logs : `make logs` ou `make logs-server`
- Vérifiez votre configuration SSH
- Consultez les statistiques : `make stats`

## Licence

Ce projet est libre d'utilisation.

---

**Note importante** : Ce système offre une protection robuste contre la perte de données, mais ne remplace pas une stratégie de sauvegarde complète (3-2-1 : 3 copies, 2 supports différents, 1 hors site).
