.PHONY: help install install-server install-client setup-server setup-client start-server start-client stop-client clean check-deps restore restore-interactive list-versions cleanup cleanup-dry-run stats setup-cron health-check


# Variables
SYSTEM_PYTHON := python3
VENV := venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
CLIENT_PID_FILE := .client.pid

# Couleurs pour l'affichage
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Affiche cette aide
	@echo "$(BLUE)=== Daemon de Sauvegarde - Makefile ===$(NC)"
	@echo ""
	@echo "$(GREEN)Commandes disponibles:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

check-deps: ## Vérifie les dépendances système
	@echo "$(BLUE)Vérification des dépendances...$(NC)"
	@command -v $(SYSTEM_PYTHON) >/dev/null 2>&1 || { echo "$(RED)Python3 n'est pas installé$(NC)"; exit 1; }
	@command -v ssh >/dev/null 2>&1 || { echo "$(RED)SSH n'est pas installé$(NC)"; exit 1; }
	@echo "$(GREEN)✓ Dépendances système OK$(NC)"

install: install-venv ## Installe les dépendances Python (client et serveur)

install-venv: check-deps ## Installe dans un environnement virtuel
	@echo "$(BLUE)Création de l'environnement virtuel...$(NC)"
	@$(SYSTEM_PYTHON) -m venv $(VENV)
	@echo "$(BLUE)Installation des dépendances...$(NC)"
	@$(PIP) install -r requirements.txt
	@echo "$(GREEN)✓ Environnement virtuel créé et configuré$(NC)"

install-server: install-venv ## Installe et configure le serveur
	@echo "$(BLUE)Installation du serveur terminée (venv)$(NC)"
	@echo "$(YELLOW)Lancez 'make setup-server' pour configurer$(NC)"

install-client: install-venv ## Installe et configure le client
	@echo "$(BLUE)Installation du client terminée (venv)$(NC)"
	@echo "$(YELLOW)Éditez client_config.json puis lancez 'make start-client'$(NC)"

setup-server: ## Configure le serveur (génère les clés SSH, etc.)
	@echo "$(BLUE)Configuration du serveur...$(NC)"
	@$(PYTHON) src/server/manager.py setup
	@echo "$(GREEN)✓ Serveur configuré$(NC)"

setup-client: ## Aide à la configuration du client
	@echo "$(BLUE)Configuration du client...$(NC)"
	@if [ ! -f client_config.json ]; then \
		echo "$(RED)Erreur: client_config.json n'existe pas$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Vérifiez client_config.json:$(NC)"
	@cat client_config.json
	@echo ""
	@echo "$(YELLOW)Testez la connexion SSH:$(NC)"
	@echo "  ssh -i ~/.ssh/id_ed25519 user@server_ip"
	@echo ""
	@echo "$(GREEN)Si la connexion fonctionne, lancez: make start-client$(NC)"

start-server: ## Démarre le serveur SSH (vérification uniquement)
	@echo "$(BLUE)Vérification du serveur SSH...$(NC)"
	@systemctl is-active ssh >/dev/null 2>&1 && echo "$(GREEN)✓ SSH actif$(NC)" || \
		(systemctl is-active sshd >/dev/null 2>&1 && echo "$(GREEN)✓ SSH actif$(NC)" || \
		echo "$(RED)✗ SSH inactif. Lancez: sudo systemctl start ssh$(NC)")
	@$(PYTHON) src/server/manager.py info

start-client: ## Démarre le daemon client
	@echo "$(BLUE)Démarrage du client de sauvegarde...$(NC)"
	@if [ ! -d sauvegarde ]; then \
		mkdir -p sauvegarde; \
		echo "$(GREEN)✓ Dossier 'sauvegarde' créé$(NC)"; \
	fi
	@$(PYTHON) src/client/daemon.py

start-client-bg: ## Démarre le client en arrière-plan
	@echo "$(BLUE)Démarrage du client en arrière-plan...$(NC)"
	@if [ ! -d sauvegarde ]; then \
		mkdir -p sauvegarde; \
		echo "$(GREEN)✓ Dossier 'sauvegarde' créé$(NC)"; \
	fi
	@nohup $(PYTHON) src/client/daemon.py > backup_client.log 2>&1 & echo $$! > $(CLIENT_PID_FILE)
	@echo "$(GREEN)✓ Client démarré (PID: $$(cat $(CLIENT_PID_FILE)))$(NC)"
	@echo "$(YELLOW)Logs: tail -f backup_client.log$(NC)"

stop-client: ## Arrête le daemon client en arrière-plan
	@if [ -f $(CLIENT_PID_FILE) ]; then \
		PID=$$(cat $(CLIENT_PID_FILE)); \
		if ps -p $$PID > /dev/null; then \
			echo "$(BLUE)Arrêt du client (PID: $$PID)...$(NC)"; \
			kill $$PID; \
			rm $(CLIENT_PID_FILE); \
			echo "$(GREEN)✓ Client arrêté$(NC)"; \
		else \
			echo "$(YELLOW)Le processus n'est plus actif$(NC)"; \
			rm $(CLIENT_PID_FILE); \
		fi \
	else \
		echo "$(YELLOW)Aucun client en arrière-plan détecté$(NC)"; \
	fi

status-client: ## Affiche le statut du client
	@if [ -f $(CLIENT_PID_FILE) ]; then \
		PID=$$(cat $(CLIENT_PID_FILE)); \
		if ps -p $$PID > /dev/null; then \
			echo "$(GREEN)✓ Client actif (PID: $$PID)$(NC)"; \
		else \
			echo "$(RED)✗ Client inactif (PID fichier obsolète)$(NC)"; \
		fi \
	else \
		echo "$(YELLOW)Client non démarré$(NC)"; \
	fi

logs: ## Affiche les logs du client
	@if [ -f backup_client.log ]; then \
		tail -f backup_client.log; \
	else \
		echo "$(YELLOW)Aucun fichier de log trouvé$(NC)"; \
	fi

logs-server: ## Affiche les logs SSH du serveur
	@$(PYTHON) src/server/manager.py logs

test-connection: ## Teste la connexion SSH au serveur
	@echo "$(BLUE)Test de connexion au serveur...$(NC)"
	@SERVER_HOST=$$(python3 -c "import json; print(json.load(open('client_config.json'))['server_host'])"); \
	SERVER_USER=$$(python3 -c "import json; print(json.load(open('client_config.json'))['server_username'])"); \
	SSH_KEY=$$(python3 -c "import json; import os; print(os.path.expanduser(json.load(open('client_config.json'))['ssh_key_file']))"); \
	echo "$(YELLOW)Connexion à $$SERVER_USER@$$SERVER_HOST...$(NC)"; \
	ssh -i $$SSH_KEY -o ConnectTimeout=5 $$SERVER_USER@$$SERVER_HOST "echo '$(GREEN)✓ Connexion SSH réussie$(NC)'" || \
	echo "$(RED)✗ Échec de connexion$(NC)"

clean: ## Nettoie les fichiers temporaires
	@echo "$(BLUE)Nettoyage...$(NC)"
	@rm -f *.pyc
	@rm -rf __pycache__
	@rm -f *.log
	@rm -f $(CLIENT_PID_FILE)
	@rm -f *.swp *.swo
	@echo "$(GREEN)✓ Nettoyage terminé$(NC)"

clean-all: clean ## Nettoie tout (inclus venv)
	@echo "$(BLUE)Nettoyage complet...$(NC)"
	@rm -rf $(VENV)
	@echo "$(GREEN)✓ Nettoyage complet terminé$(NC)"

uninstall: clean-all ## Désinstalle complètement
	@echo "$(BLUE)Désinstallation...$(NC)"
	@$(PIP) uninstall -y watchdog paramiko scp 2>/dev/null || true
	@echo "$(GREEN)✓ Désinstallation terminée$(NC)"

info-server: ## Affiche les informations du serveur
	@$(PYTHON) src/server/manager.py info

info-client: ## Affiche la configuration du client
	@echo "$(BLUE)Configuration du client:$(NC)"
	@if [ -f client_config.json ]; then \
		cat client_config.json; \
	else \
		echo "$(RED)client_config.json introuvable$(NC)"; \
	fi

backup-test: ## Crée un fichier de test dans sauvegarde/
	@echo "$(BLUE)Création d'un fichier de test...$(NC)"
	@mkdir -p sauvegarde
	@echo "Test de sauvegarde - $$(date)" > sauvegarde/test_$$(date +%s).txt
	@echo "$(GREEN)✓ Fichier de test créé dans sauvegarde/$(NC)"

watch-backup: ## Surveille le dossier de sauvegarde en temps réel
	@echo "$(BLUE)Surveillance du dossier sauvegarde/$(NC)"
	@watch -n 1 "ls -lah sauvegarde/"

# === Gestion des versions et restauration ===

restore-interactive: ## Mode interactif de restauration (serveur)
	@echo "$(BLUE)Lancement de la restauration interactive...$(NC)"
	@BACKUP_PATH=$$(grep -o '"backup_path"[[:space:]]*:[[:space:]]*"[^"]*"' server_config.json | cut -d'"' -f4 | sed 's|~|$(HOME)|'); \
	if [ -z "$$BACKUP_PATH" ]; then \
		BACKUP_PATH="$(HOME)/backups"; \
	fi; \
	$(PYTHON) src/server/restore.py "$$BACKUP_PATH" --interactive

restore: ## Restaure un fichier spécifique (usage: make restore FILE=path/to/file VERSION=timestamp)
	@if [ -z "$(FILE)" ] || [ -z "$(VERSION)" ]; then \
		echo "$(RED)Usage: make restore FILE=path/to/file VERSION=timestamp$(NC)"; \
		exit 1; \
	fi
	@BACKUP_PATH=$$(grep -o '"backup_path"[[:space:]]*:[[:space:]]*"[^"]*"' server_config.json | cut -d'"' -f4 | sed 's|~|$(HOME)|'); \
	if [ -z "$$BACKUP_PATH" ]; then \
		BACKUP_PATH="$(HOME)/backups"; \
	fi; \
	$(PYTHON) src/server/restore.py "$$BACKUP_PATH" --file "$(FILE)" --version "$(VERSION)"

restore-date: ## Restaure tous les fichiers à une date (usage: make restore-date DATE=2025-01-15)
	@if [ -z "$(DATE)" ]; then \
		echo "$(RED)Usage: make restore-date DATE=YYYY-MM-DD$(NC)"; \
		exit 1; \
	fi
	@BACKUP_PATH=$$(grep -o '"backup_path"[[:space:]]*:[[:space:]]*"[^"]*"' server_config.json | cut -d'"' -f4 | sed 's|~|$(HOME)|'); \
	if [ -z "$$BACKUP_PATH" ]; then \
		BACKUP_PATH="$(HOME)/backups"; \
	fi; \
	$(PYTHON) src/server/restore.py "$$BACKUP_PATH" --date "$(DATE)"

list-versions: ## Liste toutes les versions disponibles (optionnel: FILE=path/to/file)
	@BACKUP_PATH=$$(grep -o '"backup_path"[[:space:]]*:[[:space:]]*"[^"]*"' server_config.json | cut -d'"' -f4 | sed 's|~|$(HOME)|'); \
	if [ -z "$$BACKUP_PATH" ]; then \
		BACKUP_PATH="$(HOME)/backups"; \
	fi; \
	if [ -n "$(FILE)" ]; then \
		$(PYTHON) src/server/restore.py "$$BACKUP_PATH" --list --file "$(FILE)"; \
	else \
		$(PYTHON) src/server/restore.py "$$BACKUP_PATH" --list; \
	fi

cleanup: ## Nettoie les versions > 30 jours (serveur)
	@echo "$(BLUE)Nettoyage des anciennes versions...$(NC)"
	@BACKUP_PATH=$$(grep -o '"backup_path"[[:space:]]*:[[:space:]]*"[^"]*"' server_config.json | cut -d'"' -f4 | sed 's|~|$(HOME)|'); \
	if [ -z "$$BACKUP_PATH" ]; then \
		BACKUP_PATH="$(HOME)/backups"; \
	fi; \
	$(PYTHON) src/server/cleanup.py "$$BACKUP_PATH"

cleanup-dry-run: ## Simule le nettoyage sans supprimer (serveur)
	@echo "$(BLUE)Simulation du nettoyage...$(NC)"
	@BACKUP_PATH=$$(grep -o '"backup_path"[[:space:]]*:[[:space:]]*"[^"]*"' server_config.json | cut -d'"' -f4 | sed 's|~|$(HOME)|'); \
	if [ -z "$$BACKUP_PATH" ]; then \
		BACKUP_PATH="$(HOME)/backups"; \
	fi; \
	$(PYTHON) src/server/cleanup.py "$$BACKUP_PATH" --dry-run

cleanup-custom: ## Nettoie avec rétention personnalisée (usage: make cleanup-custom RETENTION=60)
	@if [ -z "$(RETENTION)" ]; then \
		echo "$(RED)Usage: make cleanup-custom RETENTION=days$(NC)"; \
		exit 1; \
	fi
	@BACKUP_PATH=$$(grep -o '"backup_path"[[:space:]]*:[[:space:]]*"[^"]*"' server_config.json | cut -d'"' -f4 | sed 's|~|$(HOME)|'); \
	if [ -z "$$BACKUP_PATH" ]; then \
		BACKUP_PATH="$(HOME)/backups"; \
	fi; \
	$(PYTHON) src/server/cleanup.py "$$BACKUP_PATH" --retention $(RETENTION)

stats: ## Affiche les statistiques des sauvegardes (serveur)
	@BACKUP_PATH=$$(grep -o '"backup_path"[[:space:]]*:[[:space:]]*"[^"]*"' server_config.json | cut -d'"' -f4 | sed 's|~|$(HOME)|'); \
	if [ -z "$$BACKUP_PATH" ]; then \
		BACKUP_PATH="$(HOME)/backups"; \
	fi; \
	$(PYTHON) src/server/cleanup.py "$$BACKUP_PATH" --stats

setup-cron: ## Configure le nettoyage automatique avec cron (serveur)
	@BACKUP_PATH=$$(grep -o '"backup_path"[[:space:]]*:[[:space:]]*"[^"]*"' server_config.json | cut -d'"' -f4 | sed 's|~|$(HOME)|'); \
	if [ -z "$$BACKUP_PATH" ]; then \
		BACKUP_PATH="$(HOME)/backups"; \
	fi; \
	$(PYTHON) src/server/cleanup.py "$$BACKUP_PATH" --setup-cron


# Alias communs
run-client: start-client ## Alias pour start-client
run-server: start-server ## Alias pour start-server

health-check: ## Health check complet du système (serveur)
	@echo "$(BLUE)Health Check du système...$(NC)"
	@BACKUP_PATH=$$(grep -o '"backup_path"[[:space:]]*:[[:space:]]*"[^"]*"' server_config.json | cut -d'"' -f4 | sed 's|~|$(HOME)|'); \
	if [ -z "$$BACKUP_PATH" ]; then \
		BACKUP_PATH="$(HOME)/backups"; \
	fi; \
	$(PYTHON) src/server/reliability.py "$$BACKUP_PATH" --health

# === Démarrage Automatique ===

install-service: ## Installe le service systemd (Linux uniquement)
	@echo "$(BLUE)Installation du service systemd...$(NC)"
	@if [ ! -f backup-client.service ]; then \
		echo "$(RED)Erreur: backup-client.service introuvable$(NC)"; \
		exit 1; \
	fi
	@sed "s|%i|$(USER)|g" backup-client.service > /tmp/backup-client@$(USER).service
	@sed -i "s|/home/%i|$(HOME)|g" /tmp/backup-client@$(USER).service
	@sudo cp /tmp/backup-client@$(USER).service /etc/systemd/system/backup-client.service
	@sudo systemctl daemon-reload
	@echo "$(GREEN)✓ Service installé$(NC)"
	@echo "$(YELLOW)Activez-le avec: make enable-service$(NC)"

enable-service: ## Active le démarrage automatique au boot
	@echo "$(BLUE)Activation du démarrage automatique...$(NC)"
	@sudo systemctl enable backup-client.service
	@sudo systemctl start backup-client.service
	@echo "$(GREEN)✓ Service activé et démarré$(NC)"
	@echo "$(YELLOW)Le daemon se lancera automatiquement au démarrage$(NC)"

disable-service: ## Désactive le démarrage automatique
	@echo "$(BLUE)Désactivation du service...$(NC)"
	@sudo systemctl stop backup-client.service
	@sudo systemctl disable backup-client.service
	@echo "$(GREEN)✓ Service désactivé$(NC)"

status-service: ## Affiche le statut du service systemd
	@sudo systemctl status backup-client.service

restart-service: ## Redémarre le service
	@echo "$(BLUE)Redémarrage du service...$(NC)"
	@sudo systemctl restart backup-client.service
	@echo "$(GREEN)✓ Service redémarré$(NC)"

logs-service: ## Affiche les logs du service systemd
	@sudo journalctl -u backup-client.service -f
