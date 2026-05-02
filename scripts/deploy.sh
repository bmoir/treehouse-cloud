#!/usr/bin/env bash
# Full deploy: packages Lambda, runs CloudFormation, syncs frontend to S3.
# Usage: bash scripts/deploy.sh
# Env vars: STACK_NAME (default: treehouse-cloud), REGION (default: ap-southeast-2)
set -euo pipefail

STACK_NAME="${STACK_NAME:-treehouse-cloud}"
REGION="${REGION:-ap-southeast-2}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT_DIR"

echo "Stack:  $STACK_NAME"
echo "Region: $REGION"
echo ""

# ── 1. Derive deploy bucket name (stable per account) ─────────────────────
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
DEPLOY_BUCKET="${STACK_NAME}-deploy-${ACCOUNT_ID}"

echo "==> Ensuring deploy bucket exists: $DEPLOY_BUCKET"
if ! aws s3api head-bucket --bucket "$DEPLOY_BUCKET" --region "$REGION" 2>/dev/null; then
  aws s3 mb "s3://$DEPLOY_BUCKET" --region "$REGION"
  # Block all public access on the deploy bucket
  aws s3api put-public-access-block \
    --bucket "$DEPLOY_BUCKET" \
    --public-access-block-configuration \
      "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
    --region "$REGION"
fi

# ── 2. Package Lambda ──────────────────────────────────────────────────────
echo "==> Building Lambda package..."
ZIP_DIR=$(mktemp -d /tmp/treehouse-XXXXXX)
ZIP_FILE="$ZIP_DIR/lambda.zip"
trap 'rm -rf "$ZIP_DIR"' EXIT
(cd api && zip -j -q "$ZIP_FILE" handler.py)

echo "==> Uploading Lambda package to S3..."
aws s3 cp "$ZIP_FILE" "s3://$DEPLOY_BUCKET/lambda.zip" --region "$REGION"

# ── 3. Deploy CloudFormation stack ────────────────────────────────────────
echo "==> Deploying CloudFormation stack..."
aws cloudformation deploy \
  --template-file infra/cloudformation.yaml \
  --stack-name "$STACK_NAME" \
  --parameter-overrides \
    LambdaS3Bucket="$DEPLOY_BUCKET" \
    LambdaS3Key=lambda.zip \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION"

# ── 4. Get stack outputs ──────────────────────────────────────────────────
echo "==> Reading stack outputs..."
FRONTEND_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
  --output text \
  --region "$REGION")

CF_DOMAIN=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDomain`].OutputValue' \
  --output text \
  --region "$REGION")

# ── 5. Sync frontend files ────────────────────────────────────────────────
echo "==> Uploading frontend files to S3..."
# HTML: no-store so CloudFront doesn't serve stale HTML after a redeploy
aws s3 cp frontend/index.html "s3://$FRONTEND_BUCKET/index.html" \
  --cache-control "no-store" \
  --content-type "text/html; charset=utf-8" \
  --region "$REGION"
aws s3 cp frontend/loki.html "s3://$FRONTEND_BUCKET/loki.html" \
  --cache-control "no-store" \
  --content-type "text/html; charset=utf-8" \
  --region "$REGION"
# Webmanifest: short cache (PWA install)
aws s3 cp frontend/site.webmanifest "s3://$FRONTEND_BUCKET/site.webmanifest" \
  --cache-control "max-age=3600" \
  --content-type "application/manifest+json" \
  --region "$REGION"
# Icons: long cache — these never change unless explicitly redeployed
aws s3 sync frontend/icons/ "s3://$FRONTEND_BUCKET/icons/" \
  --cache-control "max-age=31536000" \
  --region "$REGION"

# ── 6. Done ───────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Treehouse Cloud deployed!"
echo "============================================================"
echo "  Desktop:  https://$CF_DOMAIN/"
echo "  Mobile:   https://$CF_DOMAIN/loki.html"
echo "  Ingest:   https://$CF_DOMAIN/ingest"
echo "  Snapshot: https://$CF_DOMAIN/snapshot"
echo ""
echo "  Next steps:"
echo "    1. Run 'make create-key' to generate an API key"
echo "    2. Configure Openclaw to POST snapshots to the ingest URL"
echo "       with header:  X-API-Key: <your-key>"
echo "============================================================"
