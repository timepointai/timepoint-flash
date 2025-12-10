# Time Travel

Jump forward or backward from any scene to explore what happens next—or what led up to it.

---

## What You Can Do

**Track an event over time:**
```
1776: Declaration signing
  → +1 year: Revolutionary War battles
  → +7 years: Treaty of Paris, war ends
  → +11 years: Constitutional Convention
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
← 1 hour before: Caesar enters the Senate
The moment: Assassination
→ 1 hour after: Chaos erupts in Rome
```

---

## How To Use It

**Jump forward:**
```bash
curl -X POST http://localhost:8000/api/v1/temporal/{id}/next \
  -H "Content-Type: application/json" \
  -d '{"units": 1, "unit": "year"}'
```

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
Source: Declaration signing, July 4, 1776
Jump: +10 years

Result: Independence Hall, 1786
- Same location
- Same characters (now 10 years older)
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
  "center": {"year": 1776, "slug": "declaration-signing"},
  "prior": [
    {"year": 1775, "slug": "continental-congress"}
  ],
  "next": [
    {"year": 1777, "slug": "valley-forge"},
    {"year": 1783, "slug": "treaty-of-paris"}
  ]
}
```

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

## Tips

1. **Start with a clear moment** - The sharper your initial scene, the better the time jumps work

2. **Match units to your story** - Hours for same-day drama, years for historical arcs

3. **Keep chains short** - 5-10 linked scenes work better than 100

4. **Check completion first** - You can only time-travel from a completed scene
