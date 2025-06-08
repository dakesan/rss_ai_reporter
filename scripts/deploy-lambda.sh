#!/bin/bash
set -e

# RSS AI Reporter Feedback Lambda デプロイスクリプト

# 設定
AWS_REGION=${AWS_REGION:-us-east-1}
ENVIRONMENT=${1:-dev}
STACK_NAME="rss-ai-reporter-feedback-${ENVIRONMENT}"

# カラー設定
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 RSS AI Reporter Feedback Lambda Deployment${NC}"
echo "=================================================="
echo "Environment: ${ENVIRONMENT}"
echo "Stack Name: ${STACK_NAME}"
echo "Region: ${AWS_REGION}"
echo ""

# 必要な環境変数をチェック
check_env_var() {
    if [ -z "${!1}" ]; then
        echo -e "${RED}❌ Error: $1 environment variable is not set${NC}"
        echo "Required environment variables:"
        echo "  - SLACK_SIGNING_SECRET"
        echo "  - GITHUB_TOKEN"
        echo "  - AWS_ACCESS_KEY_ID (or AWS profile configured)"
        echo "  - AWS_SECRET_ACCESS_KEY (or AWS profile configured)"
        echo ""
        echo "Example:"
        echo "  export SLACK_SIGNING_SECRET=\"your_slack_signing_secret\""
        echo "  export GITHUB_TOKEN=\"ghp_your_github_token\""
        echo "  ./scripts/deploy-lambda.sh dev"
        exit 1
    fi
}

echo -e "${YELLOW}🔍 Checking prerequisites...${NC}"

# 環境変数チェック
check_env_var "SLACK_SIGNING_SECRET"
check_env_var "GITHUB_TOKEN"

# AWS CLI チェック
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI is not installed${NC}"
    exit 1
fi

# SAM CLI チェック
if ! command -v sam &> /dev/null; then
    echo -e "${RED}❌ SAM CLI is not installed${NC}"
    echo "Install SAM CLI: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"
    exit 1
fi

# AWS認証チェック
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS authentication failed${NC}"
    echo "Configure AWS credentials with 'aws configure' or set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"
echo ""

# GitHubリポジトリを取得
GITHUB_REPO=$(git config --get remote.origin.url | sed 's/.*github.com[\/:]//; s/.git$//')
if [ -z "$GITHUB_REPO" ]; then
    GITHUB_REPO="dakesan/rss_ai_reporter"
    echo -e "${YELLOW}⚠️  Could not detect GitHub repo, using default: ${GITHUB_REPO}${NC}"
fi

echo -e "${YELLOW}🏗️  Building SAM application...${NC}"
sam build --use-container

echo ""
echo -e "${YELLOW}🚀 Deploying to AWS...${NC}"
sam deploy \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --capabilities CAPABILITY_IAM \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset \
    --resolve-s3 \
    --parameter-overrides \
        SlackSigningSecret="${SLACK_SIGNING_SECRET}" \
        GitHubToken="${GITHUB_TOKEN}" \
        GitHubRepo="${GITHUB_REPO}"

echo ""
echo -e "${YELLOW}📊 Getting deployment outputs...${NC}"

# スタック出力を取得
WEBHOOK_URL=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query 'Stacks[0].Outputs[?OutputKey==`SlackWebhookUrl`].OutputValue' \
    --output text)

HEALTH_URL=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query 'Stacks[0].Outputs[?OutputKey==`HealthCheckUrl`].OutputValue' \
    --output text)

API_URL=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query 'Stacks[0].Outputs[?OutputKey==`FeedbackApiUrl`].OutputValue' \
    --output text)

BUCKET_NAME=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" \
    --query 'Stacks[0].Outputs[?OutputKey==`FeedbackBucketName`].OutputValue' \
    --output text)

echo ""
echo -e "${YELLOW}🧪 Testing deployment...${NC}"

# ヘルスチェックテスト
if curl -f -s "${HEALTH_URL}" > /dev/null; then
    echo -e "${GREEN}✅ Health check passed${NC}"
else
    echo -e "${RED}❌ Health check failed${NC}"
    exit 1
fi

# API レスポンステスト
echo "Testing API endpoints..."
curl -s "${API_URL}/" | jq . > /dev/null && echo -e "${GREEN}✅ Root endpoint working${NC}"
curl -s "${API_URL}/slack/feedback/summary" | jq . > /dev/null && echo -e "${GREEN}✅ Summary endpoint working${NC}"

echo ""
echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo "=================================================="
echo ""
echo -e "${BLUE}📋 Deployment Summary${NC}"
echo "Environment: ${ENVIRONMENT}"
echo "Stack Name: ${STACK_NAME}"
echo "Region: ${AWS_REGION}"
echo "GitHub Repo: ${GITHUB_REPO}"
echo ""
echo -e "${BLUE}🔗 Endpoints${NC}"
echo "API Gateway: ${API_URL}"
echo "Slack Webhook: ${WEBHOOK_URL}"
echo "Health Check: ${HEALTH_URL}"
echo "S3 Bucket: ${BUCKET_NAME}"
echo ""
echo -e "${BLUE}📝 Next Steps${NC}"
echo "1. Configure your Slack App:"
echo "   - Go to https://api.slack.com/apps"
echo "   - Select your RSS AI Reporter app"
echo "   - Enable Interactive Components"
echo "   - Set Request URL: ${WEBHOOK_URL}"
echo ""
echo "2. Test the integration:"
echo "   uv run python src/main.py --slack-test-3"
echo ""
echo "3. Monitor logs:"
echo "   aws logs tail /aws/lambda/${STACK_NAME}-feedback-handler --follow"
echo ""

# 設定ファイル作成
cat > .env.lambda << EOF
# Lambda Deployment Configuration
AWS_REGION=${AWS_REGION}
STACK_NAME=${STACK_NAME}
WEBHOOK_URL=${WEBHOOK_URL}
HEALTH_URL=${HEALTH_URL}
API_URL=${API_URL}
BUCKET_NAME=${BUCKET_NAME}
GITHUB_REPO=${GITHUB_REPO}
ENVIRONMENT=${ENVIRONMENT}
EOF

echo -e "${GREEN}📄 Configuration saved to .env.lambda${NC}"
echo ""
echo -e "${YELLOW}💡 Tip: Source this file to set environment variables${NC}"
echo "   source .env.lambda"