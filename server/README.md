# Hashed Control Plane API Server

FastAPI backend for AI Agent Governance - manages policies, agents, and audit logs.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd server
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your Supabase credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
DEBUG=true
```

### 3. Setup Database

Run the SQL schema in your Supabase project:

```bash
# In Supabase SQL Editor, run:
# database/schema.sql
```

### 4. Run Server

```bash
python server.py
```

Or with uvicorn directly:
```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Server will be available at: `http://localhost:8000`

## 📚 API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔑 Authentication

All endpoints (except `/health`) require authentication via `X-API-KEY` header:

```bash
curl -H "X-API-KEY: your-api-key-here" http://localhost:8000/v1/agents
```

## 📍 Endpoints Overview

### Health Check
- `GET /health` - Health check endpoint

### Agent Management
- `POST /v1/agents/register` - Register a new AI agent
- `GET /v1/agents` - List all agents in organization

### Policy Management
- `GET /v1/policies/sync?agent_public_key=xxx` - Sync policies for an agent (used by SDK)
- `POST /v1/policies` - Create a new policy
- `GET /v1/policies` - List all policies

### Log Ingestion
- `POST /v1/logs/batch` - Receive batch of audit logs from SDK

### Audit & Analytics
- `GET /v1/logs` - Query audit logs with filters
- `GET /v1/analytics/summary` - Get analytics summary

### Approval Queue
- `GET /v1/approvals/pending` - List pending approval requests
- `POST /v1/approvals/{id}/decide` - Approve or reject a request

## 🔐 Security Features

- **API Key Authentication**: All requests require valid API key
- **Signature Verification**: Ed25519 signatures verified for audit logs
- **Row Level Security (RLS)**: Supabase RLS policies isolate organizations
- **CORS**: Configurable CORS for frontend integration

## 📊 Example Usage

### Register an Agent

```bash
curl -X POST http://localhost:8000/v1/agents/register \
  -H "X-API-KEY: test_api_key_12345678901234567890123456789012" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Customer Service Bot",
    "public_key": "a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890",
    "agent_type": "customer_service",
    "description": "Handles customer inquiries"
  }'
```

### Create a Policy

```bash
curl -X POST http://localhost:8000/v1/policies \
  -H "X-API-KEY: test_api_key_12345678901234567890123456789012" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "transfer_money",
    "max_amount": 1000.0,
    "allowed": true,
    "requires_approval": false
  }'
```

### Sync Policies (SDK calls this)

```bash
curl "http://localhost:8000/v1/policies/sync?agent_public_key=a1b2c3d4..." \
  -H "X-API-KEY: test_api_key_12345678901234567890123456789012"
```

### Query Audit Logs

```bash
curl "http://localhost:8000/v1/logs?tool_name=transfer_money&limit=50" \
  -H "X-API-KEY: test_api_key_12345678901234567890123456789012"
```

## 🐳 Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY .env .

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t hashed-server .
docker run -p 8000:8000 --env-file .env hashed-server
```

## ☁️ Cloud Deployment

### Deploy to Fly.io

```bash
# Install fly CLI
curl -L https://fly.io/install.sh | sh

# Launch app
fly launch

# Set secrets
fly secrets set SUPABASE_URL=xxx SUPABASE_SERVICE_KEY=xxx

# Deploy
fly deploy
```

### Deploy to Railway

1. Connect your GitHub repo to Railway
2. Add environment variables in Railway dashboard
3. Railway will auto-deploy on push

### Deploy to Render

1. Connect repo to Render
2. Select "Web Service"
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn server:app --host 0.0.0.0 --port $PORT`
5. Add environment variables

## 🔧 Development

### Run Tests

```bash
pytest tests/
```

### Format Code

```bash
black server.py
ruff check server.py
```

### Watch for Changes

```bash
uvicorn server:app --reload
```

## 📈 Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00",
  "service": "hashed-control-plane"
}
```

### Logs

Server logs to stdout. In production, use a log aggregation service like:
- Datadog
- New Relic
- Papertrail
- CloudWatch

## 🐛 Troubleshooting

### "SUPABASE_URL not set"
Make sure `.env` file exists and contains valid Supabase credentials.

### "Invalid API key"
Check that your API key exists in the `organizations` table and `is_active = true`.

### Agent not found
Ensure the agent is registered with `POST /v1/agents/register` before syncing policies.

### Signature verification failed
Verify the public key matches the one used to sign the message and the signature is in correct hex format.

## 📝 License

MIT License - See LICENSE file for details.

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📧 Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/hashed-sdk/issues
- Email: support@hashed.dev
