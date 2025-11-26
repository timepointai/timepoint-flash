# AI Models in TIMEPOINT Flash

TIMEPOINT Flash uses state-of-the-art Google Gemini models for generating photorealistic historical scenes.

---

## Image Generation Models 🍌

TIMEPOINT Flash supports Google's cutting-edge Gemini image generation models, available via OpenRouter.

### Nano Banana (Gemini 2.5 Flash Image) - **RECOMMENDED**

**Default choice for most users**

✅ **Available via OpenRouter** (no separate Google API key needed!)

**Features:**
- **Native image generation** in Gemini 2.5+
- **Contextual understanding** - Generates images based on rich scene descriptions
- **Multi-turn conversations** - Can refine and edit images iteratively
- **Resolution:** 1024x1024px
- **Speed:** ~25-35 seconds per image
- **Quality:** Photorealistic, professional-grade output

**Pricing (via OpenRouter):**

1. **Production (Paid):** `google/gemini-2.5-flash-image`
   - **$0.001238 per image** (~808 images per dollar!)
   - Best for production workloads
   - Stable, consistent quality

2. **Free Preview:** `google/gemini-2.5-flash-image-preview:free`
   - **FREE** for testing and development
   - Same quality, rate limited
   - Perfect for getting started

**How to Use:**
```bash
# .env (Default - Recommended)
IMAGE_MODEL=google/gemini-2.5-flash-image

# Free preview for testing
IMAGE_MODEL=google/gemini-2.5-flash-image-preview:free
USE_FREE_MODELS=true
```

---

### Nano Banana Pro (Gemini 3 Pro Image) - **ADVANCED** 🚀

**NEW! For professional/enterprise use cases requiring maximum quality**

Built on Gemini 3 Pro with advanced reasoning and real-world knowledge integration.

**Advanced Features:**
- **Higher Resolution:** 2K (1080p) or 4K output
- **Industry-leading text rendering** - Perfectly legible text in images
- **Multilingual text** - Multiple languages in one image
- **Multi-image blending** - Combine up to 14 objects seamlessly
- **Identity preservation** - Maintain consistency across up to 5 people
- **Fine-grained controls:**
  - Localized edits
  - Lighting and focus adjustments
  - Camera transformations
- **Google Search integration** - Real-time information (weather, sports, etc.)

**Pricing (via OpenRouter):**
- **$0.00012 per image** (all resolutions: 1K/2K/4K!)
- **10x CHEAPER** than Nano Banana
- For comparison: Google's direct API charges $0.13-0.24, OpenRouter is 1000x cheaper!

**Model ID:** `google/gemini-3-pro-image-preview`

**When to Use Nano Banana Pro:**
- **Actually cheaper than Nano Banana!** Use it as your default
- Need 2K/4K resolution
- Require text rendering in images
- Building marketing materials with typography
- Need to maintain character consistency across scenes
- Require fine-grained creative control

**💡 Pro Tip:** Since Nano Banana Pro is cheaper AND better quality on OpenRouter, consider using it as your default!

**How to Use:**
```bash
# .env
IMAGE_MODEL=google/gemini-3-pro-image-preview
```

---

### Which Model Should I Use?

| Use Case | Model | OpenRouter Price | Why |
|----------|-------|------------------|-----|
| **Getting started** | Nano Banana (free preview) | FREE | Zero cost, same quality |
| **Production (best value)** | Nano Banana Pro | **$0.00012/img** | Cheaper + better quality! |
| **Budget production** | Nano Banana (paid) | $0.001238/img | Good if you don't need Pro features |
| **High-res outputs** | Nano Banana Pro | $0.00012/img | 2K/4K resolution |
| **Text in images** | Nano Banana Pro | $0.00012/img | Industry-leading typography |

**💡 New Recommendation:** Use Nano Banana Pro as your default! It's actually CHEAPER and higher quality than regular Nano Banana on OpenRouter.

---

## Text Models

### Gemini 1.5 Flash

**Purpose:** Fast logic, validation, and judging

- **Speed:** ~1-2 seconds per request
- **Use cases:**
  - Query validation (Judge agent)
  - Timeline generation
  - Quick decisions
- **Model ID:** `gemini-1.5-flash`

### Gemini 1.5 Pro

**Purpose:** Creative generation and complex reasoning

- **Quality:** Best for creative tasks
- **Use cases:**
  - Scene descriptions (Scene Builder agent)
  - Character development (Characters agent)
  - Dialog generation (Dialog agent)
  - Camera composition (Camera agent)
- **Model ID:** `gemini-1.5-pro`

---

## Model Pipeline

TIMEPOINT Flash uses 11 AI agents in sequence:

```
Query → Judge (Flash) → Timeline (Flash) → Scene (Pro) → Characters (Pro)
  → Moment (Pro) → Dialog (Pro) → Camera (Pro) → Graph (Flash)
  → Image Prompt (Flash) → Image Gen (Nano Banana 🍌) → Segmentation (Flash)
```

**Processing Time:**
- Judge: 1-2s
- Timeline: 1-2s
- Scene + Characters: 3-5s
- Moment + Dialog: 3-5s
- Camera + Graph: 2-3s
- Image Prompt: 1s
- **Image Generation: 25-35s** ← Nano Banana 🍌
- Segmentation: 2-3s

**Total:** 40-60 seconds end-to-end

---

## Cost Analysis

### Production Costs (Paid Models)

**Per Timepoint (full generation via OpenRouter):**
- Text generation (Flash/Pro): ~$0.005-0.01
- Image generation (Nano Banana): **$0.001238**
- Image generation (Nano Banana Pro): **$0.00012** ← Even cheaper!
- **Total: ~$0.005-0.011 per timepoint** (with Nano Banana Pro)

### Free Option

Use free preview models for testing:

```bash
# .env
IMAGE_MODEL=google/gemini-2.5-flash-image-preview:free
```

**Rate Limits (Free):**
- OpenRouter's standard free tier limits apply
- Typically 50-100 requests/day
- Perfect for development and testing

---

## Why OpenRouter?

### Benefits

1. **Single API Key** - Access all models with one key
2. **Automatic Fallbacks** - If one provider fails, tries alternatives
3. **Unified API** - Same interface for all models
4. **Usage Analytics** - Track costs and usage
5. **Free Tier** - Test before paying
6. **480+ Models** - Not locked to one provider

### Getting Started

1. Sign up at [openrouter.ai](https://openrouter.ai)
2. Get your API key (free!)
3. Add to `.env`: `OPENROUTER_API_KEY=your_key_here`
4. That's it! All Gemini models now available

---

## Alternative: Direct Google AI

If you prefer using Google AI directly (e.g., with Google Cloud credits):

```bash
# .env
GOOGLE_API_KEY=your_google_key_here
```

**Trade-offs:**
- ✅ Direct billing to Google account
- ✅ May have higher rate limits
- ❌ No automatic fallbacks
- ❌ Separate key management

**Recommendation:** Start with OpenRouter, switch to direct Google AI only if you have specific needs.

---

## Switching Models

### Using Free Models Globally

```bash
# .env
USE_FREE_MODELS=true
IMAGE_MODEL=google/gemini-2.5-flash-image-preview:free
```

### Custom Model Configuration

```bash
# .env
JUDGE_MODEL=gemini-1.5-flash
CREATIVE_MODEL=gemini-1.5-pro
IMAGE_MODEL=google/gemini-2.5-flash-image

# Or use different image model entirely:
# IMAGE_MODEL=stability-ai/stable-diffusion-xl
# IMAGE_MODEL=dall-e-3
```

---

## Model Switching

TIMEPOINT Flash is designed to easily switch models. Just update the environment variable:

```bash
# .env

# Standard: Nano Banana (recommended)
IMAGE_MODEL=google/gemini-2.5-flash-image

# Advanced: Nano Banana Pro (2K/4K, text rendering)
IMAGE_MODEL=google/gemini-3-pro-image-preview

# Free: Testing/development
IMAGE_MODEL=google/gemini-2.5-flash-image-preview:free
```

No code changes needed!

---

## Model Performance Tips

### Optimize for Speed

Use Flash models for everything except creative tasks:

```bash
JUDGE_MODEL=gemini-1.5-flash
CREATIVE_MODEL=gemini-1.5-flash  # Sacrifice quality for speed
IMAGE_MODEL=google/gemini-2.5-flash-image-preview:free
```

### Optimize for Quality

Use Pro models for richer outputs:

```bash
JUDGE_MODEL=gemini-1.5-flash      # Fast judge is fine
CREATIVE_MODEL=gemini-1.5-pro     # Best scenes/dialog
IMAGE_MODEL=google/gemini-2.5-flash-image  # Best images
```

### Budget Mode

Use all free models:

```bash
USE_FREE_MODELS=true
IMAGE_MODEL=google/gemini-2.5-flash-image-preview:free
```

---

## FAQs

### Q: Why is image generation slow (25-35s)?

A: Image generation is computationally expensive. Nano Banana generates high-quality photorealistic images, which takes time. This is actually **fast** for image generation!

### Q: Should I use Nano Banana or Nano Banana Pro?

A: **Use Nano Banana Pro** (Gemini 3 Pro Image) as your default:
- **10x cheaper** on OpenRouter ($0.00012 vs $0.001238)
- **Higher quality** - better text rendering, 2K/4K support
- **More features** - character consistency, advanced controls
- Same speed, better results

**Only use regular Nano Banana if:**
- You're on the free preview tier
- You specifically don't need Pro features
- You're using Google's direct API (not OpenRouter)

### Q: What's the difference between Nano Banana and regular Gemini?

A: "Nano Banana" (Gemini 2.5 Flash Image) and "Nano Banana Pro" (Gemini 3 Pro Image) are specifically optimized for **image generation**. Regular Gemini models (1.5 Flash, 1.5 Pro) are text-only.

### Q: Can I use other image models?

A: Yes! TIMEPOINT Flash supports any OpenRouter image model:

```bash
IMAGE_MODEL=stability-ai/stable-diffusion-xl
IMAGE_MODEL=dall-e-3
IMAGE_MODEL=google/gemini-3-pro-image-preview  # Nano Banana Pro
```

### Q: Do I need a separate Google API key?

A: **No!** OpenRouter provides access to all Gemini models (including Nano Banana Pro) with one key.

### Q: Is the free preview model as good as paid?

A: Yes, same quality! The free version just has rate limits. Perfect for testing.

### Q: How do I generate 4K images with Nano Banana Pro?

A: Use the `image_config` parameter in your API call:

```python
# Example (implementation varies by client)
image_config = {
    "resolution": "4K"  # or "2K", "1080p"
}
```

See OpenRouter's [image generation docs](https://openrouter.ai/docs/features/multimodal/image-generation) for details.

---

## Resources

- **OpenRouter Dashboard:** https://openrouter.ai/models
- **Google AI Models:** https://ai.google.dev/gemini-api/docs/models
- **Model Pricing:** https://openrouter.ai/google/gemini-2.5-flash-image
- **API Documentation:** [API.md](API.md)

---

**Built with 🍌 Gemini 2.5 Flash Image "Nano Banana"**
