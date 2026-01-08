#!/bin/bash

# Evita que apt-get pida confirmaciones interactivas
export DEBIAN_FRONTEND=noninteractive

# 1. Actualizar repositorios e instalar dependencias básicas
apt-get update
apt-get install -y docker.io curl git

# 2. Configurar Docker
systemctl start docker
systemctl enable docker

# 3. Instalar Docker Compose (v2.39.4)
# Lo movemos a /usr/bin que ya está en el PATH por defecto en Ubuntu
curl -L "https://github.com/docker/compose/releases/download/v2.39.4/docker-compose-$(uname -s)-$(uname -m)" -o /usr/bin/docker-compose
chmod +x /usr/bin/docker-compose

# 4. Configurar permisos para futuros usuarios
# Como no sabemos los nombres de usuario exactos aún, creamos un script 
# que se ejecute cada vez que alguien entre (bash) para asegurar que esté en el grupo docker.
cat <<EOF > /etc/profile.d/docker_permissions.sh
if [ -e /var/run/docker.sock ]; then
    sudo chown root:docker /var/run/docker.sock
fi
# Agregar al usuario actual al grupo docker dinámicamente
sudo usermod -aG docker \$USER
EOF

# 5. Crear directorio de trabajo para el proyecto
mkdir -p /opt/botcito
chown -R $(whoami):docker /opt/botcito
chmod -R 775 /opt/botcito

# Verificar instalaciones en el log (puedes ver esto en el Serial Port de GCP)
echo "Docker version: $(docker --version)"
echo "Docker Compose version: $(docker-compose --version)"