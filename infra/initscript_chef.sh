#!/bin/bash

# Actualizar el sistema
sudo apt-get update && sudo apt-get upgrade -y

# Instalar Docker
sudo apt-get install -y docker.io

# Configurar permisos de Docker
sudo groupadd docker || true
sudo usermod -aG docker $USER
# sudo usermod -aG docker raini
newgrp docker
# sudo usermod -aG sudo raini
# sudo chown -R $(whoami):$(whoami) .
# sudo chmod -R u+w .

# Crear carpeta /usr/local/bin si no existe
sudo mkdir -p /usr/local/bin

# Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.26.1/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Añadir /usr/local/bin al PATH
echo 'export PATH=/usr/local/bin:$PATH' >> ~/.bashrc
source ~/.bashrc

# Verificar instalaciones
docker --version
docker-compose --version