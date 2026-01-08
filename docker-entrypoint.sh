#!/bin/bash

# Generates host keys if missing
ssh-keygen -A

# Start Web Interface in background (as 'backup' user)
su backup -c "python3 /app/src/web/app.py" &

# Start SSH Daemon (foreground)
exec /usr/sbin/sshd -D -e
