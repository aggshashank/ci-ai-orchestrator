# Ollama Setup Guide — Local LLM for Windows

Ollama runs LLMs entirely on your machine. No API key, no cost, no internet required after download.

## Step 1 — Install Ollama

Download from: https://ollama.com/download/windows

Run the installer. Ollama runs as a background service on `http://localhost:11434`.

Verify:
```bash
curl http://localhost:11434/api/tags
# Expected: {"models":[]} (empty until you pull a model)
```

---

## Step 2 — Pull Required Models

### LLM: llama3.1 (8B) — recommended default

```bash
ollama pull llama3.1
# Downloads ~4.7GB. Requires: 8GB RAM minimum, 16GB recommended.
# Time: 5–15 min depending on internet speed
```

### Embedding model: nomic-embed-text

```bash
ollama pull nomic-embed-text
# Downloads ~274MB. Required for RAG (policy document search).
```

Verify both are available:
```bash
ollama list
# Should show:
# NAME                    ID              SIZE    MODIFIED
# llama3.1:latest         ...             4.7 GB  ...
# nomic-embed-text:latest ...             274 MB  ...
```

---

## Step 3 — Hardware Requirements

| RAM     | Recommended Model    | Notes |
|---------|---------------------|-------|
| 8 GB    | `phi3` or `llama3.1`| llama3.1 will be slow, phi3 is faster |
| 16 GB   | `llama3.1`          | Good performance, ~3–8s per response |
| 32 GB   | `llama3.1:70b`      | Much better reasoning quality |
| GPU     | Any model           | 10x faster — set in .env |

Check your RAM: Task Manager → Performance → Memory

---

## Step 4 — GPU Acceleration (Optional but Recommended)

Ollama auto-detects NVIDIA and AMD GPUs.

**NVIDIA GPU:**
```bash
# Verify CUDA is available to Ollama
ollama run llama3.1 "say hello"
# Check Ollama logs for: "using CUDA device"
```

**No GPU / CPU only:**
llama3.1 8B will take 5–15 seconds per response on CPU.
This is fine for the POC — just expect slower agent execution.

---

## Step 5 — Test the LLM

```bash
# Quick sanity check
ollama run llama3.1 "Return a JSON object with key hello and value world. Only JSON."
# Expected: {"hello": "world"}

# Test embedding
curl http://localhost:11434/api/embeddings \
  -d '{"model": "nomic-embed-text", "prompt": "credit score utilization"}'
# Expected: {"embedding": [0.123, -0.456, ...]} (768 numbers)
```

---

## Step 6 — Model Selection Guide

If llama3.1 is too slow on your machine, alternatives:

```bash
# Faster, lighter (2.3GB, 8GB RAM)
ollama pull phi3
# Update .env: OLLAMA_MODEL=phi3

# Fast + good JSON (4.1GB, 8GB RAM)
ollama pull mistral
# Update .env: OLLAMA_MODEL=mistral

# Best quality if you have 32GB RAM
ollama pull llama3.1:70b
# Update .env: OLLAMA_MODEL=llama3.1:70b
```

---

## Troubleshooting

**Ollama not responding:**
```bash
# Restart the Ollama service
# Windows: Search "Services" → find "Ollama" → Restart
# Or: Task Manager → find ollama.exe → End Task, then relaunch
```

**Model generates prose instead of JSON:**
```
The model sometimes adds markdown or explanation. The agents include
explicit prompts: "Return ONLY a JSON object. No explanation. No markdown."
The format="json" parameter in llm_provider.py constrains token sampling.
If issues persist, try mistral which is more reliable for structured output.
```

**Out of memory error:**
```bash
# Use a smaller model
ollama pull phi3
# Edit .env: OLLAMA_MODEL=phi3
```
