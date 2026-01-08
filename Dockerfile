FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    openssh-server \
    && rm -rf /var/lib/apt/lists/*

# Setup SSH
RUN mkdir /var/run/sshd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config
# Enable Pubkey Auth, Disable Password Auth
RUN sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config

# Create backup user
RUN useradd -m -s /bin/bash backup && \
    mkdir -p /home/backup/.ssh && \
    chmod 700 /home/backup/.ssh && \
    chown -R backup:backup /home/backup

# App Setup
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ /app/src/
COPY server_config.json /home/backup/
# Ensure rights
RUN chown -R backup:backup /app /home/backup

# Volume for data
VOLUME /home/backup/backups
VOLUME /home/backup/.ssh

# Expose SSH
EXPOSE 22
# Expose Web Interface
EXPOSE 5000

# Startup script
COPY docker-entrypoint.sh /
RUN chmod +x /docker-entrypoint.sh

CMD ["/docker-entrypoint.sh"]
