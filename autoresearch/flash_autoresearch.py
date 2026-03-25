"""Flash Autoresearch: image prompt optimization loop.

Karpathy-style autoresearch that explores the prompt mutation space for
Flash's image generation pipeline. Mutates style, lighting, composition,
and detail keywords; measures image quality via CLIP similarity (or
synthetic scores in dry-run mode); and tracks the Pareto frontier of
quality vs cost.

Usage:
    python -m autoresearch.flash_autoresearch --dry-run --iterations 10
    python -m autoresearch.flash_autoresearch --iterations 50 --flash-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Prompt mutation space
# ---------------------------------------------------------------------------

STYLE_KEYWORDS: List[str] = [
    "photorealistic",
    "cinematic",
    "oil painting",
    "watercolor",
    "digital art",
    "hyperrealistic",
    "impressionist",
    "concept art",
    "matte painting",
    "cel shaded",
    "noir",
    "retro futurism",
    "vaporwave",
    "documentary",
    "graphic novel",
]

LIGHTING_TERMS: List[str] = [
    "golden hour",
    "dramatic chiaroscuro",
    "soft diffused light",
    "harsh overhead sun",
    "neon glow",
    "candlelight",
    "backlit silhouette",
    "volumetric fog",
    "studio lighting",
    "moonlight",
    "fluorescent",
    "rim lighting",
    "ambient occlusion",
    "overcast flat",
]

COMPOSITION_TERMS: List[str] = [
    "rule of thirds",
    "centered symmetry",
    "extreme close-up",
    "wide establishing shot",
    "dutch angle",
    "bird's eye view",
    "worm's eye view",
    "over the shoulder",
    "leading lines",
    "frame within frame",
    "shallow depth of field",
    "deep focus",
    "split screen",
]

DETAIL_LEVELS: List[str] = [
    "minimal detail, clean lines",
    "moderate detail, balanced textures",
    "high detail, intricate textures",
    "ultra detail, 8k, micro textures",
    "photographic grain, film emulation",
    "painterly brushstrokes, loose detail",
]

NEGATIVE_PROMPTS: List[str] = [
    "blurry, out of focus",
    "bad anatomy, distorted",
    "low quality, jpeg artifacts",
    "watermark, text overlay",
    "oversaturated, blown highlights",
    "",  # no negative prompt
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class PromptConfig:
    """A single point in the prompt mutation space."""

    style: str
    lighting: str
    composition: str
    detail: str
    negative: str
    cfg_scale: float = 7.5  # guidance scale 3.0–15.0
    seed: int = 42

    def config_hash(self) -> str:
        raw = f"{self.style}|{self.lighting}|{self.composition}|{self.detail}|{self.negative}|{self.cfg_scale}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    def to_prompt_text(self) -> str:
        parts = [self.style, self.lighting, self.composition, self.detail]
        return ", ".join(p for p in parts if p)

    def to_negative_text(self) -> str:
        return self.negative


@dataclass
class RunResult:
    """Result of a single autoresearch iteration."""

    iteration: int
    config: PromptConfig
    config_hash: str
    clip_score: float
    cost_usd: float
    duration_s: float
    is_dry_run: bool
    timestamp: float = field(default_factory=time.time)

    def quality_per_dollar(self) -> float:
        if self.cost_usd <= 0:
            return float("inf")
        return self.clip_score / self.cost_usd


@dataclass
class ParetoPoint:
    """A point on the Pareto frontier (quality vs cost)."""

    config_hash: str
    clip_score: float
    cost_usd: float
    config: Dict[str, Any]


# ---------------------------------------------------------------------------
# Mutation engine
# ---------------------------------------------------------------------------


def random_config(rng: random.Random) -> PromptConfig:
    """Sample a random point in the mutation space."""
    return PromptConfig(
        style=rng.choice(STYLE_KEYWORDS),
        lighting=rng.choice(LIGHTING_TERMS),
        composition=rng.choice(COMPOSITION_TERMS),
        detail=rng.choice(DETAIL_LEVELS),
        negative=rng.choice(NEGATIVE_PROMPTS),
        cfg_scale=round(rng.uniform(3.0, 15.0), 1),
    )


def mutate_config(cfg: PromptConfig, rng: random.Random) -> PromptConfig:
    """Mutate one or two dimensions of an existing config."""
    fields_to_mutate = rng.sample(
        ["style", "lighting", "composition", "detail", "negative", "cfg_scale"],
        k=rng.randint(1, 2),
    )
    new = PromptConfig(
        style=cfg.style,
        lighting=cfg.lighting,
        composition=cfg.composition,
        detail=cfg.detail,
        negative=cfg.negative,
        cfg_scale=cfg.cfg_scale,
        seed=cfg.seed,
    )
    for f in fields_to_mutate:
        if f == "style":
            new.style = rng.choice(STYLE_KEYWORDS)
        elif f == "lighting":
            new.lighting = rng.choice(LIGHTING_TERMS)
        elif f == "composition":
            new.composition = rng.choice(COMPOSITION_TERMS)
        elif f == "detail":
            new.detail = rng.choice(DETAIL_LEVELS)
        elif f == "negative":
            new.negative = rng.choice(NEGATIVE_PROMPTS)
        elif f == "cfg_scale":
            new.cfg_scale = round(rng.uniform(3.0, 15.0), 1)
    return new


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def synthetic_clip_score(cfg: PromptConfig, rng: random.Random) -> Tuple[float, float]:
    """Deterministic-ish synthetic CLIP score for dry-run mode.

    Returns (clip_score, cost_usd). The score is derived from the config
    hash so identical configs always produce similar scores, plus small
    noise for realism.
    """
    h = cfg.config_hash()
    # Derive a base score from the hash (0.55–0.85 range)
    hash_int = int(h, 16)
    base = 0.55 + (hash_int % 1000) / 1000.0 * 0.30

    # Some combos get bonuses
    if "cinematic" in cfg.style and "golden hour" in cfg.lighting:
        base += 0.04
    if "photorealistic" in cfg.style and "high detail" in cfg.detail:
        base += 0.03
    if cfg.cfg_scale > 10.0:
        base -= 0.02  # too high guidance hurts quality
    if cfg.cfg_scale < 5.0:
        base -= 0.01

    # Add small noise
    noise = rng.gauss(0, 0.015)
    clip_score = max(0.0, min(1.0, base + noise))

    # Synthetic cost: higher cfg_scale costs more, detail level matters
    detail_mult = 1.0
    if "ultra" in cfg.detail:
        detail_mult = 1.5
    elif "high" in cfg.detail:
        detail_mult = 1.2
    elif "minimal" in cfg.detail:
        detail_mult = 0.7
    cost = round(0.30 * detail_mult * (0.8 + cfg.cfg_scale / 30.0), 4)

    return clip_score, cost


def live_score(
    cfg: PromptConfig,
    flash_url: str,
    query: str = "A dramatic historical moment captured in time",
) -> Tuple[float, float]:
    """Call Flash API, generate an image, score it with CLIP.

    Not implemented yet — placeholder for live mode.
    """
    raise NotImplementedError(
        "Live scoring requires Flash API integration. Use --dry-run for synthetic scoring."
    )


# ---------------------------------------------------------------------------
# Pareto frontier
# ---------------------------------------------------------------------------


def update_pareto(frontier: List[ParetoPoint], candidate: ParetoPoint) -> List[ParetoPoint]:
    """Add candidate to Pareto frontier if it is non-dominated.

    A point dominates another if it has both higher quality AND lower cost.
    Returns the updated frontier.
    """
    new_frontier: List[ParetoPoint] = []
    dominated = False

    for p in frontier:
        # Does existing point dominate candidate?
        if p.clip_score >= candidate.clip_score and p.cost_usd <= candidate.cost_usd:
            if p.clip_score > candidate.clip_score or p.cost_usd < candidate.cost_usd:
                dominated = True
        # Does candidate dominate existing point?
        if candidate.clip_score >= p.clip_score and candidate.cost_usd <= p.cost_usd:
            if candidate.clip_score > p.clip_score or candidate.cost_usd < p.cost_usd:
                continue  # drop dominated point
        new_frontier.append(p)

    if not dominated:
        new_frontier.append(candidate)

    return new_frontier


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def run_autoresearch(
    iterations: int,
    dry_run: bool = True,
    flash_url: Optional[str] = None,
    output_dir: str = "autoresearch/results",
    seed: int = 42,
) -> None:
    """Run the autoresearch loop."""
    rng = random.Random(seed)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    results_file = out / "results.jsonl"
    pareto_file = out / "pareto.json"

    frontier: List[ParetoPoint] = []
    best_score = 0.0
    best_config: Optional[PromptConfig] = None
    current_config = random_config(rng)

    print(f"Flash Autoresearch — {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"Iterations: {iterations}")
    print(f"Output: {out}")
    print("-" * 60)

    with open(results_file, "a") as f:
        for i in range(iterations):
            t0 = time.time()

            # Score
            if dry_run:
                clip_score, cost = synthetic_clip_score(current_config, rng)
            else:
                if not flash_url:
                    raise ValueError("--flash-url required for live mode")
                clip_score, cost = live_score(current_config, flash_url)

            duration = time.time() - t0

            result = RunResult(
                iteration=i,
                config=current_config,
                config_hash=current_config.config_hash(),
                clip_score=round(clip_score, 4),
                cost_usd=cost,
                duration_s=round(duration, 3),
                is_dry_run=dry_run,
            )

            # Write JSONL
            record = {
                "iteration": result.iteration,
                "config_hash": result.config_hash,
                "clip_score": result.clip_score,
                "cost_usd": result.cost_usd,
                "quality_per_dollar": round(result.quality_per_dollar(), 4)
                if result.cost_usd > 0
                else None,
                "duration_s": result.duration_s,
                "is_dry_run": result.is_dry_run,
                "timestamp": result.timestamp,
                "config": asdict(result.config),
            }
            f.write(json.dumps(record) + "\n")
            f.flush()

            # Update Pareto
            candidate = ParetoPoint(
                config_hash=result.config_hash,
                clip_score=result.clip_score,
                cost_usd=result.cost_usd,
                config=asdict(current_config),
            )
            frontier = update_pareto(frontier, candidate)

            # Track best
            improved = ""
            if clip_score > best_score:
                best_score = clip_score
                best_config = current_config
                improved = " *BEST*"

            print(
                f"[{i + 1:>4}/{iterations}] "
                f"CLIP={result.clip_score:.4f}  "
                f"cost=${result.cost_usd:.4f}  "
                f"Q/$={result.quality_per_dollar():.2f}  "
                f"pareto={len(frontier)}  "
                f"hash={result.config_hash}"
                f"{improved}"
            )

            # Mutate: 70% mutate best, 20% mutate current, 10% random
            roll = rng.random()
            if best_config and roll < 0.7:
                current_config = mutate_config(best_config, rng)
            elif roll < 0.9:
                current_config = mutate_config(current_config, rng)
            else:
                current_config = random_config(rng)

    # Write Pareto frontier
    pareto_data = {
        "frontier_size": len(frontier),
        "best_clip_score": best_score,
        "iterations": iterations,
        "dry_run": dry_run,
        "points": [asdict(p) for p in sorted(frontier, key=lambda x: x.clip_score, reverse=True)],
    }
    with open(pareto_file, "w") as f:
        json.dump(pareto_data, f, indent=2)

    print("-" * 60)
    print(f"Best CLIP score: {best_score:.4f}")
    print(f"Pareto frontier: {len(frontier)} points")
    print(f"Results: {results_file}")
    print(f"Pareto:  {pareto_file}")

    if best_config:
        print(f"\nBest config:")
        print(f"  Style:       {best_config.style}")
        print(f"  Lighting:    {best_config.lighting}")
        print(f"  Composition: {best_config.composition}")
        print(f"  Detail:      {best_config.detail}")
        print(f"  CFG scale:   {best_config.cfg_scale}")
        print(f"  Negative:    {best_config.negative or '(none)'}")
        print(f"  Prompt:      {best_config.to_prompt_text()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Flash Autoresearch: image prompt optimization loop"
    )
    parser.add_argument(
        "--iterations", type=int, default=50, help="Number of iterations (default: 50)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use synthetic CLIP scores instead of calling Flash API",
    )
    parser.add_argument(
        "--flash-url",
        type=str,
        default=None,
        help="Flash API base URL for live mode",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="autoresearch/results",
        help="Directory for output files (default: autoresearch/results)",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    args = parser.parse_args()

    run_autoresearch(
        iterations=args.iterations,
        dry_run=args.dry_run,
        flash_url=args.flash_url,
        output_dir=args.output_dir,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
