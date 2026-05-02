#!/usr/bin/env bash
# Generate a new API key and store it in SSM Parameter Store.
# Overwrites any existing key — use this to rotate as well.
# Usage: bash scripts/create_key.sh
# Env vars: REGION (default: ap-southeast-2)
set -euo pipefail

REGION="${REGION:-ap-southeast-2}"
PARAM_NAME="/treehouse/api-key"

# Generate 32 random bytes as a 64-char hex string
KEY=$(openssl rand -hex 32)

echo "==> Storing API key in SSM Parameter Store..."
aws ssm put-parameter \
  --name "$PARAM_NAME" \
  --value "$KEY" \
  --type "SecureString" \
  --overwrite \
  --region "$REGION" \
  --description "Treehouse Cloud ingest API key" \
  > /dev/null

echo ""
echo "============================================================"
echo "  Treehouse API Key"
echo "============================================================"
echo "  SSM path:  $PARAM_NAME  (region: $REGION)"
echo ""
echo "  Your key — copy this now, it will not be shown again:"
echo ""
echo "  $KEY"
echo ""
echo "  Configure Openclaw:"
echo "    POST to: https://<your-cloudfront-domain>/ingest"
echo "    Header:  X-API-Key: $KEY"
echo "    Body:    application/json  (dashboard-snapshot.json payload)"
echo ""
echo "  Run 'make outputs' to get your CloudFront domain."
echo "============================================================"
