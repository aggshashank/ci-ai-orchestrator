# FAQ

## General

**Q: Is this production-ready?**
A: The architecture is production-grade (async FastAPI, Kafka, PostgreSQL, structured logging, Prometheus metrics), but the LLM component — Ollama running a local Llama 3 model — is CPU-bound and slow (~60s per agent on a 16 GB laptop without GPU). For production you'd swap the LLM provider to Groq, Bedrock, or Azure OpenAI. Everything else is production-capable.

**Q: Does this require cloud services?**
A: No. All services (Kafka, Qdrant, PostgreSQL, Ollama) run locally via Docker Compose. No API keys required.

**Q: What is ECOA compliance?**
A: The Equal Credit Opportunity Act requires lenders who decline credit to provide specific reasons ("adverse action codes"). This platform generates AA01–AA12 codes with plain-language descriptions. See `agents/explainability_agent.py`.

---

## LLM / Performance

**Q: Inference is very slow. How do I speed it up?**
A: Three options, in order of impact:
1. Use a smaller model (`OLLAMA_MODEL=phi3` — 3–4× faster)
2. Plug in a GPU (Ollama auto-detects CUDA/Metal — 20–30× faster)
3. Swap to a hosted API (`langchain-groq` — 50–100× faster, requires API key)

**Q: Can I use OpenAI instead of Ollama?**
A: Yes. Install `langchain-openai` and update `llm/factory.py` to return `ChatOpenAI(model="gpt-4o")`. The rest of the pipeline is LLM-agnostic.

**Q: What does the LLM cache do?**
A: The LLM response cache (controlled by `LLM_CACHE_ENABLED`) deduplicates identical prompts within a TTL window. For a simulation run over a dataset where many cases have similar inputs, this dramatically reduces Ollama calls. Disable it for production variability or testing with `LLM_CACHE_ENABLED=false`.

---

## Data / Rules

**Q: Where are the decision rules stored?**
A: In versioned YAML directories under `ai-orchestrator/strategies/`. No rules are hardcoded. All thresholds, weights, and ECOA mappings are in YAML files.

**Q: Can I change rules without redeploying?**
A: Yes. Use the Rule Editor in the dashboard or `PUT /api/v1/strategies/{version}/rules`. Changes are picked up immediately (the rules engine cache is cleared on save). For a new version, use `POST /api/v1/strategies/deploy`.

**Q: How do I add a new policy document for RAG?**
A: Add a `.txt` file to `policy-documents/` and re-run ingestion:
```bash
python -m rag.ingest
```
New chunks are upserted into Qdrant; existing chunks are unchanged.

---

## Fairness

**Q: Why do you use channel and credit tier rather than protected class data?**
A: ECOA/Reg B prohibits collecting or storing protected class information (race, sex, national origin) for credit decisions. Channel and credit tier are permissible proxy variables for identifying potential disparate impact patterns without violating fair lending law.

**Q: What is the 4/5ths rule?**
A: The 4/5ths rule (also called the 80% rule) is the standard disparate impact threshold from EEOC Uniform Guidelines. If any group's selection rate is less than 80% of the highest-performing group's rate, it is a potential adverse impact finding. The platform flags these as violations in the fairness report.

---

## Database

**Q: How do I apply migrations?**
```bash
cd ai-orchestrator
alembic upgrade head
```

**Q: How do I reset the database for local development?**
```bash
docker compose down -v   # drops volumes including DB
docker compose up -d
alembic upgrade head
python -m rag.ingest
```
