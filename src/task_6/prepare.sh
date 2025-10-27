

aws s3 rm s3://cebaezc1-5615fae7e5b2bd6b/checkpoints/ --recursive

aws ssm send-command \
  --instance-ids "i-04c8c25f72fbc2cc7" \
  --document-name "AWS-RunShellScript" \
  --comment "Fetch entire app folder and unpack" \
  --parameters '{
    "commands": [
      "set -euo pipefail",
      "mkdir -p /home/hadoop/app",
      "aws s3 cp s3://cebaezc1-5615fae7e5b2bd6b/streaming/ /home/hadoop/app/ --recursive"
    ]
  }' \
  --output-s3-bucket-name cebaezc1-5615fae7e5b2bd6b \
  --output-s3-key-prefix ssm-logs/run-unpack
