# Eval System Roadmap

Future enhancements for the TIMEPOINT Flash evaluation system.

---

## Current State (v2.2.0)

- Multi-model latency comparison (`/api/v1/eval/compare`)
- Presets: verified, google_native, openrouter, all
- CLI: `eval.sh` with interactive mode
- Metrics: latency (min/max/avg/median), success rate, ranking
- 35+ unit tests

**Gap**: Measures speed only, not quality.

---

## Enhancement Pathways

### A. Quality Scoring (LLM-as-Judge)

Score outputs on domain-specific dimensions:
- Historical accuracy
- Temporal consistency
- Character authenticity
- Dialog period-appropriateness
- Anachronism detection

**Endpoint**: `POST /api/v1/eval/quality`

---

### B. Pipeline Evaluation

Test full 10-agent pipeline, not just raw text:
- Step-by-step timing
- Schema validation per step
- Error rate tracking
- Completeness checks

**Endpoint**: `POST /api/v1/eval/pipeline`

---

### C. Benchmark Dataset

Golden test set for regression testing:
```
evals/
├── datasets/
│   ├── golden_queries.json    # 50 curated queries
│   ├── ground_truth.json      # Expected facts
│   └── edge_cases.json        # BCE dates, obscure events
└── baselines/
    └── v2.2.0_results.json
```

**CLI**: `./eval.sh --regression`

---

### D. Cost Tracking

- Token counting (input/output)
- Cost estimation per model
- Cost/quality efficiency ratio

---

### E. Historical Accuracy Checker

Domain-specific validation:
- Character existence verification
- Date plausibility
- Location accessibility
- Anachronism detection in dialog

---

### F. Persistent Results + Dashboard

- Store eval runs in database
- Track results over time
- Compare runs (A/B testing)
- CI integration

---

## Architecture Comparison Eval

**Core question**: Can one frontier model one-shot what 10 specialized agents produce?

### The Matchup

| Mode | Description |
|------|-------------|
| **Pipeline** | 10 agents (Flash/2.0), parallel execution, specialized prompts |
| **Monolith** | 1 frontier model (Opus 4.5, GPT-4o), single mega-prompt |

### Comparison Dimensions

| Dimension | Pipeline | Monolith |
|-----------|----------|----------|
| Latency | ~15-30s | ~10-20s |
| Cost | ~$0.02 | ~$0.15-0.30 |
| Reliability | Graceful degradation | Single point of failure |
| Quality | Specialized prompts | General capability |

### Quality Judging

Use LLM judge to score both outputs:
- Historical accuracy
- Character depth
- Dialog authenticity
- Scene vividness
- Narrative coherence
- Schema completeness

### Frontier Models to Test

- Claude Opus 4.5
- GPT-4o
- Gemini 2.5 Pro
- Claude Sonnet 4

### Output

```
VERDICT: Pipeline wins on quality (8.9 vs 8.6)
         Monolith wins on speed (32% faster)
         Pipeline wins on cost (13x cheaper)
```

**Endpoint**: `POST /api/v1/eval/architecture/compare`
**CLI**: `./eval.sh --architecture "query"`

---

## Priority Matrix

| Pathway | Effort | Value | Priority |
|---------|--------|-------|----------|
| B. Pipeline Eval | 2d | High | 1 |
| A. Quality Scoring | 2-3d | High | 2 |
| Architecture Comparison | 3-4d | High | 3 |
| C. Benchmark Dataset | 3-4d | High | 4 |
| D. Cost Tracking | 1d | Medium | 5 |
| F. Persistent Results | 2-3d | Medium | 6 |
| E. Historical Checker | 4-5d | High | 7 |

---

## Research Questions

1. Does specialization beat generalization?
2. Is frontier model overhead worth the cost?
3. Where do monolith models fail? (dialog? relationships?)
4. Can we hybrid? (frontier for some steps, small for others)
5. What's the optimal cost/quality trade-off point?

---

*Last updated: 2025-12-10*
