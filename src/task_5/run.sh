#!/bin/bash
BUCKET="mineria-benchmark-maraosoc-data"
SOURCE=s3://${BUCKET}/data/
EXPERIMENT="polars_streaming"

# Absolute path to this script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Print initial info
echo "============================================================"
echo " Bucket: ${BUCKET}"
echo " Source: ${SOURCE}"
echo " Experiment: ${EXPERIMENT}"
echo "============================================================"

# copy main.py to s3
echo "Uploading main.py to S3..."
aws s3 cp "${SCRIPT_DIR}/main.py" s3://${BUCKET}/scripts/${EXPERIMENT}/main.py --region us-east-2 --profile maraosoc

# Change to infrastructure directory
cd "${SCRIPT_DIR}/infrastructure"

export AWS_PROFILE="maraosoc"
export TF_VAR_profile="maraosoc"
export TF_VAR_region="us-east-2"
export TF_VAR_owner="maraosoc"

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
echo "This may take 3-5 minutes while EC2 installs dependencies and processes data..."

# Wait up to 10 minutes (20 attempts x 30 seconds)
for i in {1..20}; do
  if aws s3 ls "${S3_FILE}" --profile ${AWS_PROFILE} --region us-east-2 >/dev/null 2>&1; then
    echo "File found in S3!"
    break
  fi
  echo "Waiting for results... attempt $i/20 ($(($i * 30)) seconds elapsed)"
  sleep 30
done

# Show results
if aws s3 ls "${S3_FILE}" --profile ${AWS_PROFILE} --region us-east-2 >/dev/null 2>&1; then
  echo
  echo "Results of (${EXPERIMENT}):"
  echo "------------------------------------------------------------"
  aws s3 cp "${S3_FILE}" - --profile ${AWS_PROFILE} --region us-east-2 | cat
  echo "------------------------------------------------------------"
  
  # Also show user_data.log for debugging
  echo
  echo "User Data Log (for debugging):"
  echo "------------------------------------------------------------"
  aws s3 cp "s3://${BUCKET}/results/${EXPERIMENT}/user_data.log" - --profile ${AWS_PROFILE} --region us-east-2 2>/dev/null | tail -50 || echo "User data log not available"
  echo "------------------------------------------------------------"
 
else
  echo "No results found after waiting 10 minutes."
  echo "Checking if user_data.log exists for debugging..."
  if aws s3 ls "s3://${BUCKET}/results/${EXPERIMENT}/user_data.log" --profile ${AWS_PROFILE} --region us-east-2 >/dev/null 2>&1; then
    echo "Found user_data.log, showing last 100 lines:"
    echo "------------------------------------------------------------"
    aws s3 cp "s3://${BUCKET}/results/${EXPERIMENT}/user_data.log" - --profile ${AWS_PROFILE} --region us-east-2 | tail -100
    echo "------------------------------------------------------------"
  else
    echo "No logs found. The instance may still be initializing."
    echo "You can check CloudWatch logs or connect via SSM to debug."
  fi
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

# uv run $EXPERIMENT/main.py $SOURCE
