# Time Travel

Jump forward or backward from any scene to explore what happens next—or what led up to it.

---

## What You Can Do

**Track an event over time:**
```
1945: Trinity detonation
  → +1 day: Potsdam Conference telegram
  → +3 weeks: Hiroshima
```

**Explore a single day:**
```
Morning: Leonardo in his workshop
  → +4 hours: Midday meal with apprentices
  → +4 hours: Afternoon painting session
  → +4 hours: Evening by candlelight
```

**See before and after:**
```
← 1 hour: Turing answers the door
The moment: Police interrogation
→ 1 hour: Turing alone
```

---

## How To Use It

**Jump forward:**
```bash
curl -X POST http://localhost:8000/api/v1/temporal/{id}/next \
  -H "Content-Type: application/json" \
  -d '{"units": 1, "unit": "year"}'
```

**Response:**
```json
{
  "source_id": "550e8400-...",
  "target_id": "661f9511-...",
  "source_year": 1776,
  "target_year": 1777,
  "direction": "next",
  "units": 1,
  "unit": "year",
  "message": "Generated moment 1 year(s) forward"
}
```

Then fetch the full scene: `GET /api/v1/timepoints/{target_id}?full=true`

**Jump backward:**
```bash
curl -X POST http://localhost:8000/api/v1/temporal/{id}/prior \
  -H "Content-Type: application/json" \
  -d '{"units": 1, "unit": "hour"}'
```

**Time units:** `second`, `minute`, `hour`, `day`, `week`, `month`, `year`

**Range:** 1-365 units per jump

---

## What Gets Preserved

When you jump in time, the system keeps:

- **Location** - Same place
- **Characters** - Same people (aged appropriately for large jumps)
- **Context** - The story continues coherently

Example:
```
Source: Trinity test, July 16, 1945
Jump: +1 day

Result: S-10000 bunker, Jornada del Muerto, July 17, 1945
- Same location
- Same characters (processing the aftermath)
- Story reflects what happened in between
```

---

## Linked Scenes

Scenes created through time travel are linked together. Get the full chain:

```bash
curl "http://localhost:8000/api/v1/temporal/{id}/sequence?direction=both"
```

```json
{
  "center": {"id": "...", "year": 1945, "slug": "trinity-test-abc123"},
  "prior": [
    {"id": "...", "year": 1945, "slug": "trinity-preparation-def456"}
  ],
  "next": [
    {"id": "...", "year": 1945, "slug": "trinity-aftermath-ghi789"}
  ]
}
```

Note: Each entry includes `id`, `year`, and `slug`. When a timepoint has multiple children (from separate time-jumps), the sequence follows the most recently created child.

---

## BCE Dates

Dates before year 1 use negative numbers:

| Date | API Value |
|------|-----------|
| 50 BCE | -50 |
| 500 BCE | -500 |
| 44 BCE (Caesar's death) | -44 |

```bash
# Start at Rome 50 BCE
curl -X POST .../generate -d '{"query": "rome 50 BCE"}'

# Jump 100 years forward to 50 CE
curl -X POST .../temporal/{id}/next -d '{"units": 100, "unit": "year"}'
```

---

## Visibility

Time travel respects timepoint visibility. When `AUTH_ENABLED=true`:

- **Public source** — anyone can jump forward/backward
- **Private source, owner** — allowed (new scene inherits the source's visibility)
- **Private source, non-owner** — 403 Forbidden

---

## Tips

1. **Start with a clear moment** - The sharper your initial scene, the better the time jumps work

2. **Match units to your story** - Hours for same-day drama, years for historical arcs

3. **Keep chains short** - 5-10 linked scenes work better than 100

4. **Check completion first** - You can only time-travel from a completed scene

---

*Last updated: 2026-02-16*
