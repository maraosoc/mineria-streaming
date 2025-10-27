#!/bin/bash
set -x  # Print commands for debugging

BUCKET="${bucket_name}"
EXPERIMENT="${experiment_name}"
SOURCE="${source_name}"

# Log file for debugging
LOGFILE="/home/ubuntu/user_data.log"
exec > >(tee -a $${LOGFILE}) 2>&1

echo "=== Starting user_data script ==="
echo "Bucket: $${BUCKET}"
echo "Experiment: $${EXPERIMENT}"
echo "Source: $${SOURCE}"

export HOME=/home/ubuntu

# Actualizar sistema e instalar dependencias básicas
echo "=== Updating system and installing dependencies ==="
sudo apt update
sudo apt install -y python3 python3-pip python3-venv awscli

# Upgrade pip
echo "=== Upgrading pip ==="
python3 -m pip install --upgrade pip

# Instalar dependencias de Python con usuario ubuntu (no root)
echo "=== Installing Python packages ==="
python3 -m pip install --user pandas polars

# Verificar instalación
echo "=== Verifying installations ==="
python3 --version
python3 -c "import polars; print(f'Polars version: {polars.__version__}')" || echo "ERROR: Polars not installed"
python3 -c "import pandas; print(f'Pandas version: {pandas.__version__}')" || echo "ERROR: Pandas not installed"

# Descargar el script de main.py 
echo "=== Downloading main.py from S3 ==="
aws s3 sync s3://$${BUCKET}/scripts/$${EXPERIMENT}/ /home/ubuntu/$${EXPERIMENT}/

# Verificar que main.py existe
if [ ! -f "/home/ubuntu/$${EXPERIMENT}/main.py" ]; then
    echo "ERROR: main.py not found after download"
    exit 1
fi

# Descargar los datos de entrada
echo "=== Downloading data from S3 ==="
aws s3 sync s3://$${BUCKET}/data/ /home/ubuntu/$${EXPERIMENT}/data/

# Verificar que hay datos
DATA_COUNT=$$(ls -1 /home/ubuntu/$${EXPERIMENT}/data/*.json 2>/dev/null | wc -l)
echo "Found $${DATA_COUNT} JSON files"

if [ $${DATA_COUNT} -eq 0 ]; then
    echo "ERROR: No JSON files found in data directory"
    exit 1
fi

# Cambiar al directorio del experimento
cd /home/ubuntu/$${EXPERIMENT}/

# Ejecutar el script y capturar toda la salida
echo "=== Executing main.py ==="
python3 main.py --input /home/ubuntu/$${EXPERIMENT}/data > /home/ubuntu/output.log 2>&1
EXIT_CODE=$$?

# Agregar información de ejecución
echo "" >> /home/ubuntu/output.log
echo "=== Execution completed ===" >> /home/ubuntu/output.log
echo "Exit code: $${EXIT_CODE}" >> /home/ubuntu/output.log
echo "Timestamp: $$(date)" >> /home/ubuntu/output.log

# Subir resultados a S3
echo "=== Uploading results to S3 ==="
aws s3 cp "/home/ubuntu/output.log" s3://$${BUCKET}/results/$${EXPERIMENT}/output.log

# También subir el log de user_data para debugging
aws s3 cp "$${LOGFILE}" s3://$${BUCKET}/results/$${EXPERIMENT}/user_data.log

echo "=== Script completed successfully ==="
