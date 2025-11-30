# Temporal Navigation Guide

TIMEPOINT Flash includes a synthetic time system for navigating through history and generating connected temporal sequences.

---

## Concepts

### TemporalPoint

A `TemporalPoint` represents coordinates in time:

```python
class TemporalPoint:
    year: int           # Required: -10000 to 3000 (BCE as negative)
    month: int | None   # 1-12
    day: int | None     # 1-31
    hour: int | None    # 0-23
    minute: int | None  # 0-59
    second: int | None  # 0-59

    # Metadata
    season: str | None      # spring, summer, fall, winter
    time_of_day: str | None # dawn, morning, midday, afternoon, evening, night
    era: str | None         # Historical period name
```

### TimeUnit

Supported time units for navigation:

| Unit | Description |
|------|-------------|
| second | Seconds |
| minute | Minutes |
| hour | Hours |
| day | Days (default) |
| week | Weeks (7 days) |
| month | Months (~30 days) |
| year | Years (~365 days) |

### TemporalNavigator

The navigator generates new timepoints by stepping forward or backward in time while preserving context (characters, location, scene).

---

## API Usage

### Generate Next Moment

Step forward in time from an existing timepoint:

```bash
curl -X POST http://localhost:8000/api/v1/temporal/{timepoint-id}/next \
  -H "Content-Type: application/json" \
  -d '{"units": 1, "unit": "day"}'
```

**Examples:**

```bash
# One day later
{"units": 1, "unit": "day"}

# One week later
{"units": 1, "unit": "week"}

# 10 years later
{"units": 10, "unit": "year"}

# 6 hours later
{"units": 6, "unit": "hour"}
```

### Generate Prior Moment

Step backward in time:

```bash
curl -X POST http://localhost:8000/api/v1/temporal/{timepoint-id}/prior \
  -H "Content-Type: application/json" \
  -d '{"units": 5, "unit": "year"}'
```

### Get Temporal Sequence

Retrieve linked timepoints in a chain:

```bash
# Get both prior and next
curl "http://localhost:8000/api/v1/temporal/{id}/sequence?direction=both&limit=10"

# Get only prior moments
curl "http://localhost:8000/api/v1/temporal/{id}/sequence?direction=prior&limit=5"

# Get only next moments
curl "http://localhost:8000/api/v1/temporal/{id}/sequence?direction=next&limit=5"
```

---

## How It Works

### Step Calculation

When you navigate, the system:

1. Reads the source timepoint's temporal coordinates
2. Calculates the new temporal point using the step delta
3. Generates a context-aware query preserving:
   - Location
   - Characters (same people, aged appropriately)
   - Scene continuity
4. Runs the full generation pipeline
5. Links the new timepoint to the source

### Context Preservation

The navigator builds context from the source timepoint:

```
Source: "Declaration signing, July 4, 1776"
Navigation: +10 years

Generated Query:
"The same scene at Independence Hall, Philadelphia, 1786 CE,
continuing from the previous moment.

Characters: John Hancock, Benjamin Franklin, ...
Scene: Grand assembly hall..."
```

### Parent-Child Relationships

Timepoints are linked via `parent_id`:

```
Timepoint A (1776) -> parent_id: null
    |
    v (generate next)
Timepoint B (1777) -> parent_id: A
    |
    v (generate next)
Timepoint C (1778) -> parent_id: B
```

When generating "prior":
```
Timepoint D (1775) -> parent_id: null
    ^
    | (D becomes parent of A)
Timepoint A (1776) -> parent_id: D
```

---

## BCE Date Handling

BCE (Before Common Era) dates are represented as negative years:

| Date | Year Value |
|------|------------|
| 50 BCE | -50 |
| 500 BCE | -500 |
| 3000 BCE | -3000 |
| 1 CE | 1 |
| 2024 CE | 2024 |

### Example: Ancient Rome

```bash
# Create timepoint for Rome 50 BCE
curl -X POST http://localhost:8000/api/v1/timepoints/generate \
  -d '{"query": "rome 50 BCE"}'

# Navigate 100 years forward (to 50 CE)
curl -X POST http://localhost:8000/api/v1/temporal/{id}/next \
  -d '{"units": 100, "unit": "year"}'

# Navigate 500 years back (to 550 BCE)
curl -X POST http://localhost:8000/api/v1/temporal/{id}/prior \
  -d '{"units": 500, "unit": "year"}'
```

---

## Constraints

### Units Range

- Minimum: 1
- Maximum: 365

For larger jumps, make multiple requests or use larger units:
- Instead of 1000 days, use ~3 years
- Instead of 500 years, make multiple 100-year jumps

### Source Timepoint Requirements

The source timepoint must be:
- Completed (status = "completed")
- Have valid temporal coordinates (year at minimum)

Attempting to navigate from an incomplete timepoint returns 400 Bad Request.

---

## Use Cases

### Historical Timeline

Create a series of moments tracking an event:

```bash
# Start: Declaration signing
POST /generate {"query": "signing of the declaration"}

# 1 year later: Revolutionary War
POST /temporal/{id}/next {"units": 1, "unit": "year"}

# 5 years later: Constitution drafting
POST /temporal/{id}/next {"units": 5, "unit": "year"}

# 10 years later: Early Republic
POST /temporal/{id}/next {"units": 10, "unit": "year"}
```

### Day-in-the-Life

Track a single day hour by hour:

```bash
# Morning
POST /generate {"query": "leonardo's workshop florence 1503 morning"}

# Midday
POST /temporal/{id}/next {"units": 4, "unit": "hour"}

# Afternoon
POST /temporal/{id}/next {"units": 4, "unit": "hour"}

# Evening
POST /temporal/{id}/next {"units": 4, "unit": "hour"}
```

### Before and After

Show moments before and after a key event:

```bash
# The event
POST /generate {"query": "assassination of julius caesar"}

# 1 hour before
POST /temporal/{id}/prior {"units": 1, "unit": "hour"}

# 1 hour after
POST /temporal/{id}/next {"units": 1, "unit": "hour"}
```

---

## Best Practices

1. **Start with a clear anchor point** - Generate a well-defined historical moment first

2. **Use appropriate time units** - Hours for same-day, days/weeks for short-term, years for long-term

3. **Keep sequences manageable** - Build chains of 5-10 timepoints rather than hundreds

4. **Check completion status** - Always verify the source timepoint is complete before navigating

5. **Use the sequence endpoint** - Retrieve connected timepoints efficiently with `/sequence`

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| 404 Not Found | Timepoint ID doesn't exist | Verify the ID is correct |
| 400 Bad Request | Source not completed | Wait for generation to complete |
| 422 Validation Error | Invalid units (0, negative, >365) | Use valid range 1-365 |

### Example Error Response

```json
{
  "detail": "Source timepoint must be completed before navigation"
}
```
