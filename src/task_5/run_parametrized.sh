#!/bin/bash
# Script para ejecutar task_5 con parámetros opcionales

# Parámetros con valores por defecto
BUCKET="${1:-mineria-benchmark-maraosoc-data}"
EXPERIMENT="${2:-polars_streaming}"
SOURCE="s3://${BUCKET}/data/"
REGION="${3:-us-east-2}"
PROFILE="${4:-maraosoc}"

# Absolute path to this script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Print initial info
echo "============================================================"
echo " Bucket: ${BUCKET}"
echo " Source: ${SOURCE}"
echo " Experiment: ${EXPERIMENT}"
echo " Region: ${REGION}"
echo " Profile: ${PROFILE}"
echo "============================================================"
echo

# Validar que main.py existe
if [ ! -f "${SCRIPT_DIR}/main.py" ]; then
    echo "Error: main.py no encontrado en ${SCRIPT_DIR}"
    exit 1
fi

# copy main.py to s3
echo "Uploading main.py to S3..."
aws s3 cp "${SCRIPT_DIR}/main.py" s3://${BUCKET}/scripts/${EXPERIMENT}/main.py --region ${REGION} --profile ${PROFILE}

if [ $? -ne 0 ]; then
    echo "Error: No se pudo subir main.py a S3"
    exit 1
fi

# Change to infrastructure directory
cd "${SCRIPT_DIR}/infrastructure"

if [ ! -d "${SCRIPT_DIR}/infrastructure" ]; then
    echo "Error: Directorio infrastructure no encontrado"
    exit 1
fi

export AWS_PROFILE="${PROFILE}"
export TF_VAR_profile="${PROFILE}"
export TF_VAR_region="${REGION}"
export TF_VAR_owner="${PROFILE}"

terraform init -backend-config="key=${EXPERIMENT}/backend.tfstate"

terraform apply -var="source_name=${SOURCE}"\
                -var="bucket_name=${BUCKET}"\
                -var="experiment_name=${EXPERIMENT}"\
                -auto-approve

# Wait for EC2 to upload results
RESULT_PATH="results/${EXPERIMENT}/output.log"
S3_FILE="s3://${BUCKET}/${RESULT_PATH}"
echo
echo "Waiting for EC2 to upload results to ${S3_FILE} ..."

# Wait up to 5 minutes
for i in {1..10}; do
  if aws s3 ls "${S3_FILE}" --profile ${PROFILE} --region ${REGION} >/dev/null 2>&1; then
    echo "File found in S3."
    break
  fi
  echo "Waiting for results... attempt $i/10"
  sleep 30
done

# Show results
if aws s3 ls "${S3_FILE}" --profile ${PROFILE} --region ${REGION} >/dev/null 2>&1; then
  echo
  echo "Results of (${EXPERIMENT}):"
  echo "------------------------------------------------------------"
  aws s3 cp "${S3_FILE}" - --profile ${PROFILE} --region ${REGION} | cat
  echo "------------------------------------------------------------"
 
else
  echo "No results found after waiting."
fi

# Finish execution and destroy infrastructure
echo
echo "Destroying infrastructure..."
terraform destroy -var="source_name=${SOURCE}"\
                -var="bucket_name=${BUCKET}"\
                -var="experiment_name=${EXPERIMENT}"\
                -auto-approve || true

echo
echo "Execution finished. Press [any key] to exit..."
read
