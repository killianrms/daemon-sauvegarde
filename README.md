# 🛡️ Daemon de Sauvegarde - Guide de Présentation

Ce projet permet de sauvegarder automatiquement et de manière chiffrée les fichiers d'un client vers un serveur.

## 📋 Prérequis

- **Serveur** : Machine qui stocke les sauvegardes.
- **Client** : Machine utilisateur à sauvegarder.

---

## 🖥️ 1. Côté Serveur (Machine de Stockage)

Ouvrez un terminal et lancez ces commandes :

1.  **Installation**
    ```bash
    make install-server
    ```

2.  **Configuration Initiale** (Génération des clés, dossiers...)
    ```bash
    make setup-server
    ```

3.  **Démarrer le Service**
    ```bash
    make start-server
    ```
    > ℹ️ **Notez l'adresse IP et le port** qui s'affichent, vous en aurez besoin pour le client.

---

## 💻 2. Côté Client (Machine Utilisateur)

Ouvrez un terminal sur la machine à sauvegarder :

1.  **Installation**
    ```bash
    make install-client
    ```

2.  **Configuration**
    Ouvrez le fichier de configuration :
    ```bash
    nano client_config.json
    ```
    - Remplacez `server_host` par l'**IP du serveur**.
    - Vérifiez que `server_username` est correct (ex: `depinfo` ou votre utilisateur).

3.  **Démarrer la Surveillance**
    ```bash
    make start-client
    ```
    > Un dossier `sauvegarde/` sera créé automatiquement.

---

## 🚀 3. Démonstration (Le Test)

1.  Laissez tourner le client (`make start-client`) dans un terminal.
2.  Ouvrez un **nouveau terminal**.
3.  Lancez le test automatique :
    ```bash
    make backup-test
    ```
    - Un fichier test est créé dans `sauvegarde/`.
    - Il est détecté, chiffré et envoyé au serveur.
    - Il disparaît du dossier `sauvegarde/` (preuve de succès).

4.  Vérifiez sur le **Serveur** que le fichier est bien reçu :
    ```bash
    make list-versions
    ```

---

## 🛠️ Commandes Utiles

| Commande | Description |
| :--- | :--- |
| `make help` | Affiche la liste des commandes |
| `make start-server` | Lance le serveur SSH |
| `make start-client` | Lance le daemon de surveillance |
| `make backup-test` | Simule une sauvegarde (crée un fichier) |
| `make restore` | Restaure un fichier (suivre instructions) |
| `make clean` | Nettoie les fichiers temporaires |