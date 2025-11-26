# TIMEPOINT Flash - API Examples

Ready-to-run code examples for the TIMEPOINT Flash API.

## Prerequisites

1. **Start the server:**
   ```bash
   cd ..  # Go to project root
   ./tp serve
   ```

2. **Server runs on:** `http://localhost:8000`

---

## Quick Examples

### Python

```bash
# Basic client (generate + wait + fetch)
python3 python_client.py

# Stream progress in real-time (SSE)
python3 stream_progress.py
```

### JavaScript (Node.js)

```bash
# Install dependencies
npm install node-fetch eventsource

# Run example
node javascript_client.js
```

### Bash (curl)

```bash
# Make executable
chmod +x curl_examples.sh

# Run all examples
./curl_examples.sh
```

---

## Files

| File | Description |
|------|-------------|
| `python_client.py` | Complete Python example (requests library) |
| `stream_progress.py` | Real-time progress streaming (SSE) |
| `javascript_client.js` | Node.js/browser example (fetch + EventSource) |
| `curl_examples.sh` | Bash script with curl one-liners |

---

## What You'll Learn

- How to create a timepoint
- How to monitor progress (SSE streaming)
- How to fetch results
- How to list all timepoints
- Error handling
- Rate limiting

---

## No Authentication Required!

Just start the server and run the examples. No API keys, tokens, or setup needed for the client.

The only key you need is `OPENROUTER_API_KEY` in the server's `.env` file.

---

**Built with ⚡ FastAPI | 🧠 LangGraph | 🍌 Gemini Nano Banana**
