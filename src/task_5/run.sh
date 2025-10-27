#!/bin/bash
BUCKET="mineria-benchmark-maraosoc-data"
SOURCE=s3://${BUCKET}/data/
EXPERIMENT="polars_streaming"

# Absolute path to this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_PATH="${SCRIPT_DIR}/user_data.sh"

# Print initial info
echo "============================================================"
echo " Bucket: ${BUCKET}"
echo " Source: ${SOURCE}"
echo "============================================================"

# copy main.py to s3
aws s3 cp  "main.py"  s3://${BUCKET}/scripts/${EXPERIMENT}/main.py --region us-east-2 --profile maraosoc

cd "/infrastructure"

export AWS_PROFILE="maraosoc"
export TF_VAR_profile="maraosoc"
export TF_VAR_region="us-east-2"
export TF_VAR_owner="maraosoc"

terraform init  -backend-config="key=${EXPERIMENT}/backend.tfstate"

terraform apply -var="script_path=${SCRIPT_PATH}"\
                -var="source_name=${SOURCE}"\
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
  if aws s3 ls "${S3_FILE}" >/dev/null 2>&1; then
    echo "File found in S3."
    break
  fi
  echo "Waiting for results... attempt $i/10"
  sleep 30
done

# Show results
if aws s3 ls "${S3_FILE}" >/dev/null 2>&1; then
  echo
  echo "Results of (${EXPERIMENT}):"
  echo "------------------------------------------------------------"
  aws s3 cp "${S3_FILE}" - | cat
  echo "------------------------------------------------------------"
 
else
  echo "No results found after waiting."
fi

# Finish execution and destroy infrastructure
echo
echo "Destroying infrastructure..."
terraform destroy -var="script_path=${SCRIPT_PATH}"\
                -var="source_name=${SOURCE}"\
                -var="bucket_name=${BUCKET}"\
                -var="experiment_name=${EXPERIMENT}"\
                -auto-approve || true

echo
echo "Execution finished. Press [any key] to exit..."
read

# uv run $EXPERIMENT/main.py $SOURCE
