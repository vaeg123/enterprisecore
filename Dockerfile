FROM python:3.11-slim

# Install MariaDB (MySQL-compatible) + supervisor
RUN apt-get update && apt-get install -y \
    mariadb-server \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Make startup script executable
RUN chmod +x /app/scripts/start.sh

# Fly.io serves on 8080
EXPOSE 8080

CMD ["/app/scripts/start.sh"]
