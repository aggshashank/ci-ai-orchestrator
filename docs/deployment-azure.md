# Deployment — Azure

This guide covers deploying to Azure using Container Apps, Azure Event Hubs (Kafka protocol), and Azure Database for PostgreSQL.

## Architecture on Azure

```
Internet → Azure Front Door → Container Apps (ai-orchestrator)
                                       │
              ┌────────────────────────┼───────────────────┐
              ▼                        ▼                   ▼
       Azure Event Hubs         Azure PostgreSQL      Azure OpenAI
       (Kafka protocol)         (Flexible Server)     (optional LLM)
```

## Prerequisites

- Azure CLI (`az login`)
- Docker installed

## 1. Resource group and registry

```bash
az group create --name decisioning-rg --location eastus

az acr create --resource-group decisioning-rg \
  --name decisioningacr --sku Basic

az acr login --name decisioningacr
```

## 2. Build and push images

```bash
docker build -t decisioningacr.azurecr.io/ai-orchestrator:latest ./ai-orchestrator
docker push decisioningacr.azurecr.io/ai-orchestrator:latest

docker build -t decisioningacr.azurecr.io/dashboard:latest ./dashboard
docker push decisioningacr.azurecr.io/dashboard:latest
```

## 3. Azure Database for PostgreSQL

```bash
az postgres flexible-server create \
  --name decisioning-db \
  --resource-group decisioning-rg \
  --location eastus \
  --admin-user postgres \
  --admin-password <password> \
  --sku-name Standard_B2ms \
  --tier Burstable \
  --version 16 \
  --database-name decisioning
```

## 4. Azure Event Hubs (Kafka protocol)

Event Hubs supports the Kafka protocol at the Standard tier and above.

```bash
az eventhubs namespace create \
  --name decisioning-events \
  --resource-group decisioning-rg \
  --sku Standard

# Create topics (event hubs)
for topic in application.received recommendation.generated manual.review.required application.dlq; do
  az eventhubs eventhub create \
    --name "$topic" \
    --resource-group decisioning-rg \
    --namespace-name decisioning-events
done
```

Set `KAFKA_BOOTSTRAP_SERVERS=decisioning-events.servicebus.windows.net:9093` and configure SASL/PLAIN with the Event Hubs connection string.

## 5. LLM — Azure OpenAI (optional)

```bash
pip install langchain-openai
```

In `llm/factory.py`:
```python
from langchain_openai import AzureChatOpenAI

def get_llm():
    return AzureChatOpenAI(
        azure_deployment="gpt-4o",
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version="2024-02-01",
    )
```

## 6. Container Apps

```bash
az containerapp env create \
  --name decisioning-env \
  --resource-group decisioning-rg \
  --location eastus

az containerapp create \
  --name ai-orchestrator \
  --resource-group decisioning-rg \
  --environment decisioning-env \
  --image decisioningacr.azurecr.io/ai-orchestrator:latest \
  --cpu 1 --memory 2Gi \
  --min-replicas 1 --max-replicas 5 \
  --ingress external --target-port 8001 \
  --env-vars \
    DATABASE_URL="postgresql+asyncpg://postgres:<password>@decisioning-db.postgres.database.azure.com/decisioning" \
    KAFKA_BOOTSTRAP_SERVERS="decisioning-events.servicebus.windows.net:9093" \
    ACTIVE_STRATEGY_VERSION="v1.0.0"
```

## 7. Run migrations

```bash
az containerapp job create \
  --name run-migrations \
  --resource-group decisioning-rg \
  --environment decisioning-env \
  --image decisioningacr.azurecr.io/ai-orchestrator:latest \
  --replica-timeout 120 \
  --command "alembic" "upgrade" "head"

az containerapp job start --name run-migrations --resource-group decisioning-rg
```

## Cost estimate (East US, light load)

| Service | ~Cost/month |
|---|---|
| Azure PostgreSQL (B2ms) | $50 |
| Event Hubs Standard (1 TU) | $22 |
| Container Apps (2 replicas) | $60 |
| Azure OpenAI (gpt-4o, 1M tokens) | $5–20 |
| **Total** | **~$135–150** |
