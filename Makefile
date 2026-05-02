REGION     ?= ap-southeast-2
STACK_NAME ?= treehouse-cloud

export REGION
export STACK_NAME

.PHONY: deploy deploy-frontend deploy-api create-key outputs teardown

## Full deploy: CloudFormation stack + frontend S3 sync
deploy:
	@bash scripts/deploy.sh

## Re-sync frontend files to S3 only (no CloudFormation)
deploy-frontend:
	$(eval FRONTEND_BUCKET := $(shell aws cloudformation describe-stacks \
	  --stack-name $(STACK_NAME) \
	  --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
	  --output text --region $(REGION)))
	@aws s3 sync frontend/ s3://$(FRONTEND_BUCKET)/ \
	  --exclude ".DS_Store" \
	  --exclude "*.DS_Store" \
	  --cache-control "no-store" \
	  --region $(REGION)
	@aws s3 cp frontend/site.webmanifest s3://$(FRONTEND_BUCKET)/site.webmanifest \
	  --cache-control "max-age=3600" --content-type "application/manifest+json" --region $(REGION)
	@aws s3 sync frontend/icons/ s3://$(FRONTEND_BUCKET)/icons/ \
	  --cache-control "max-age=31536000" --region $(REGION)
	@aws s3 sync frontend/assets/ s3://$(FRONTEND_BUCKET)/assets/ \
	  --cache-control "max-age=31536000" --region $(REGION)
	@echo "Frontend deployed."

## Re-package and push Lambda code only (no CloudFormation)
deploy-api:
	$(eval ACCOUNT_ID := $(shell aws sts get-caller-identity --query Account --output text))
	$(eval DEPLOY_BUCKET := $(STACK_NAME)-deploy-$(ACCOUNT_ID))
	$(eval ZIP_DIR := $(shell mktemp -d /tmp/treehouse-XXXXXX))
	@(cd api && zip -j -q $(ZIP_DIR)/lambda.zip handler.py)
	@aws s3 cp $(ZIP_DIR)/lambda.zip s3://$(DEPLOY_BUCKET)/lambda.zip --region $(REGION)
	@rm -rf $(ZIP_DIR)
	@aws lambda update-function-code \
	  --function-name $(STACK_NAME)-api \
	  --s3-bucket $(DEPLOY_BUCKET) \
	  --s3-key lambda.zip \
	  --region $(REGION) > /dev/null
	@echo "Lambda updated."

## Run integration test: push a snapshot and verify it appears in history
test:
	@python3 scripts/test_history.py

## Generate a new API key and store it in SSM (also rotates existing key)
create-key:
	@bash scripts/create_key.sh

## Print stack outputs (dashboard URL, ingest endpoint, bucket name)
outputs:
	@aws cloudformation describe-stacks \
	  --stack-name $(STACK_NAME) \
	  --query 'Stacks[0].Outputs' \
	  --output table \
	  --region $(REGION)

## Destroy the entire stack (irreversible — deletes all data)
teardown:
	@echo "WARNING: This will delete the stack and all DynamoDB data."
	@read -p "Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ]
	@aws cloudformation delete-stack --stack-name $(STACK_NAME) --region $(REGION)
	@echo "Stack deletion initiated."
