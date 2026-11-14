#!/bin/sh
# Bootstraps the emulated AWS account (LocalStack): S3 archive bucket, Secrets
# Manager vault, CloudWatch log group. Idempotent. Real AWS later: same script
# without --endpoint-url.
set -eu
EP="--endpoint-url ${AWS_ENDPOINT_URL:-http://localstack:4566}"
R="--region ${AWS_DEFAULT_REGION:-ap-south-1}"
BUCKET="${AWS_REPORTS_BUCKET:-repurpora-reports}"

aws $EP $R s3api create-bucket --bucket "$BUCKET" \
  --create-bucket-configuration LocationConstraint="${AWS_DEFAULT_REGION:-ap-south-1}" 2>/dev/null || true
aws $EP $R s3api put-bucket-encryption --bucket "$BUCKET" \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws $EP $R s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

SECRET=$(printf '{"SUPABASE_SECRET_KEY":"%s","FIRECRAWL_API_KEY":"%s","LANGSMITH_API_KEY":"%s","OLLAMA_PROXY_TOKEN":"%s"}' \
  "${SUPABASE_SECRET_KEY:-}" "${FIRECRAWL_API_KEY:-}" "${LANGSMITH_API_KEY:-}" "${OLLAMA_PROXY_TOKEN:-}")
aws $EP $R secretsmanager create-secret --name repurpora/app --secret-string "$SECRET" >/dev/null 2>&1 \
  || aws $EP $R secretsmanager put-secret-value --secret-id repurpora/app --secret-string "$SECRET" >/dev/null

aws $EP $R logs create-log-group --log-group-name /repurpora/audit 2>/dev/null || true
aws $EP $R logs put-retention-policy --log-group-name /repurpora/audit --retention-in-days 90

echo "LocalStack bootstrap complete: s3://$BUCKET, secret repurpora/app, log group /repurpora/audit"
