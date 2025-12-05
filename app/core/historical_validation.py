"""Historical validation and anachronism prevention.

This module provides era-specific validation, negative prompt injection,
and concept bleed detection to prevent anachronisms in generated images.

Key features:
- Era-specific negative prompts to exclude anachronistic elements
- Commonly confused period detection
- Mutual exclusion rules for incompatible visual elements
- Famous scene/artwork drift detection

Examples:
    >>> from app.core.historical_validation import get_era_negative_prompts
    >>> negatives = get_era_negative_prompts(1799, "France")
    >>> print(negatives)
    ['roman toga', 'ancient sandals', 'laurel wreath', ...]

Tests:
    - tests/unit/test_historical_validation.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple


# ==============================================================================
# Era Definitions and Date Ranges
# ==============================================================================

class EraRange(NamedTuple):
    """A historical era with start/end years."""
    name: str
    start: int  # negative for BCE
    end: int
    region: str | None = None  # Optional regional restriction


# Major historical eras (used for concept isolation)
ERAS = [
    # Ancient
    EraRange("ancient_egypt", -3100, -30, "Egypt"),
    EraRange("ancient_greece", -800, -146, "Greece"),
    EraRange("roman_republic", -509, -27, "Rome"),
    EraRange("roman_empire", -27, 476, "Rome"),

    # Medieval
    EraRange("early_medieval", 476, 1000, "Europe"),
    EraRange("high_medieval", 1000, 1300, "Europe"),
    EraRange("late_medieval", 1300, 1500, "Europe"),

    # Early Modern
    EraRange("renaissance", 1400, 1600, "Europe"),
    EraRange("tudor_england", 1485, 1603, "England"),
    EraRange("stuart_england", 1603, 1714, "England"),
    EraRange("colonial_america", 1607, 1776, "America"),

    # Revolutionary Era
    EraRange("american_revolution", 1765, 1791, "America"),
    EraRange("french_revolution", 1789, 1799, "France"),
    EraRange("napoleonic", 1799, 1815, "France"),

    # 19th Century
    EraRange("victorian", 1837, 1901, "Britain"),
    EraRange("american_civil_war", 1861, 1865, "America"),
    EraRange("gilded_age", 1870, 1900, "America"),

    # 20th Century
    EraRange("edwardian", 1901, 1910, "Britain"),
    EraRange("world_war_1", 1914, 1918, None),
    EraRange("interwar", 1918, 1939, None),
    EraRange("world_war_2", 1939, 1945, None),
    EraRange("cold_war", 1947, 1991, None),
]


def get_era_for_year(year: int, location: str | None = None) -> str | None:
    """Determine the historical era for a given year and location.

    Args:
        year: The year (negative for BCE)
        location: Optional location hint

    Returns:
        Era name or None if no match
    """
    location_lower = (location or "").lower()

    for era in ERAS:
        if era.start <= year <= era.end:
            # Check regional match if specified
            if era.region:
                region_lower = era.region.lower()
                if region_lower in location_lower or not location:
                    return era.name
            else:
                return era.name

    return None


# ==============================================================================
# Era-Specific Negative Prompts
# ==============================================================================

# Elements to EXCLUDE for each era (prevents concept bleed from similar periods)
ERA_NEGATIVE_PROMPTS: dict[str, list[str]] = {
    # Ancient Greece - exclude Roman and Egyptian elements
    "ancient_greece": [
        "roman toga", "roman armor", "gladiator", "colosseum",
        "egyptian hieroglyphics", "pharaoh", "pyramid",
        "medieval armor", "knights", "castles",
    ],

    # Roman Republic/Empire - exclude Greek idealization and medieval
    "roman_republic": [
        "greek idealized", "parthenon", "greek columns only",
        "medieval armor", "knights", "castles", "chainmail",
        "renaissance clothing", "doublet",
    ],
    "roman_empire": [
        "medieval armor", "knights", "castles", "chainmail",
        "renaissance clothing", "viking helmet",
    ],

    # Medieval - exclude ancient and early modern
    "early_medieval": [
        "roman toga", "greek chiton", "plate armor", "full plate",
        "renaissance doublet", "ruff collar", "musket", "firearm",
    ],
    "high_medieval": [
        "roman toga", "greek chiton", "renaissance doublet",
        "ruff collar", "musket", "firearm", "tricorn hat",
    ],
    "late_medieval": [
        "roman toga", "greek chiton", "musket",
        "tricorn hat", "powdered wig", "bicorne hat",
    ],

    # Tudor - exclude Stuart and earlier
    "tudor_england": [
        "powdered wig", "tricorn hat", "roman toga",
        "medieval chainmail", "plate armor on civilians",
        "cavalier hat", "restoration fashion",
    ],

    # Stuart - exclude Tudor and Georgian
    "stuart_england": [
        "tudor ruff", "elizabethan collar", "powdered wig",
        "tricorn hat", "georgian fashion", "roman toga",
    ],

    # French Revolution (1789-1799) - CRITICAL: exclude Roman/Napoleonic
    "french_revolution": [
        # Roman elements (major source of confusion)
        "roman toga", "ancient toga", "roman sandals", "ancient sandals",
        "laurel wreath", "laurel crown", "roman senator",
        "marble columns greek", "roman forum", "colosseum",
        "gladius sword", "roman armor", "centurion",

        # Napoleonic elements (post-1799)
        "napoleon emperor", "imperial eagle", "napoleonic uniform",
        "bicorne with cockade vertical", "marshal baton",
        "empire waist gown", "empire style dress",

        # American Revolution (different aesthetic)
        "continental army uniform", "american revolutionary",
        "tricorn with american cockade",

        # Anachronistic elements
        "electric lighting", "gas lamp", "photograph", "camera",
        "industrial machinery", "steam engine",
    ],

    # Napoleonic Era (1799-1815) - exclude Revolutionary and Roman
    "napoleonic": [
        # Revolutionary elements (pre-1799)
        "sans-culottes", "phrygian cap red", "revolutionary tribunal",
        "jacobin", "guillotine scene",

        # Roman elements
        "roman toga", "ancient sandals", "laurel wreath crown",
        "roman senator costume", "roman forum scene",

        # Victorian elements (post-1815)
        "top hat", "victorian dress", "crinoline", "bustle",
        "gaslight", "industrial factory",
    ],

    # American Revolution - exclude French Revolution specifics
    "american_revolution": [
        "french revolutionary", "jacobin", "phrygian cap",
        "sans-culottes", "guillotine", "bastille",
        "napoleonic uniform", "bicorne napoleon",
        "roman toga", "ancient greek",
    ],

    # Victorian Era - exclude earlier and Edwardian
    "victorian": [
        "georgian wig", "powdered wig", "tricorn hat",
        "medieval armor", "renaissance doublet",
        "edwardian motoring", "automobile", "airplane",
        "electric streetlight", "neon",
    ],

    # WWI - exclude WWII equipment
    "world_war_1": [
        "m1 helmet", "stahlhelm ww2", "german ww2 uniform",
        "sherman tank", "tiger tank", "jet aircraft",
        "radar dish", "atomic symbol",
        "victorian dress", "top hat civilian",
    ],

    # WWII - exclude WWI and Cold War
    "world_war_2": [
        "brodie helmet", "pickelhaube", "ww1 biplane",
        "cavalry charge", "horse cavalry combat",
        "jet fighter modern", "helicopter combat",
        "nuclear missile", "space satellite",
        "smartphone", "computer monitor",
    ],
}


def get_era_negative_prompts(year: int, location: str | None = None) -> list[str]:
    """Get negative prompts appropriate for the given year and location.

    Args:
        year: The year (negative for BCE)
        location: Optional location hint

    Returns:
        List of elements to exclude from image generation
    """
    era = get_era_for_year(year, location)

    if era and era in ERA_NEGATIVE_PROMPTS:
        return ERA_NEGATIVE_PROMPTS[era].copy()

    # Default negative prompts for unknown eras
    return [
        "anachronistic elements",
        "modern technology",
        "contemporary clothing",
    ]


# ==============================================================================
# Commonly Confused Periods Detection
# ==============================================================================

@dataclass
class ConfusionRisk:
    """Represents a risk of era confusion."""
    target_era: str
    confused_with: str
    risk_level: float  # 0-1
    distinguishing_features: list[str]
    warning: str


# Pairs of commonly confused historical periods
CONFUSION_PAIRS: list[ConfusionRisk] = [
    ConfusionRisk(
        target_era="french_revolution",
        confused_with="roman_republic",
        risk_level=0.9,
        distinguishing_features=[
            "French 1790s dress coat and breeches (NOT toga)",
            "Powdered wigs or natural hair (NOT laurel wreaths)",
            "Indoor legislative chamber (NOT outdoor forum)",
            "Chandeliers and candles (NOT torches)",
            "French tricolor cockade (NOT Roman eagle)",
        ],
        warning="CRITICAL: French Revolution scenes often drift toward Roman imagery. "
                "The Death of Marat and Jacques-Louis David's neoclassical style causes "
                "AI models to confuse 1790s France with ancient Rome. "
                "Explicitly specify: French dress coats, NOT togas."
    ),
    ConfusionRisk(
        target_era="french_revolution",
        confused_with="napoleonic",
        risk_level=0.7,
        distinguishing_features=[
            "Revolutionary cockade (NOT imperial eagle)",
            "Sans-culottes or bourgeois dress (NOT military uniform dominant)",
            "Directoire fashion for women (NOT empire waist)",
            "Pre-1799 setting",
        ],
        warning="Distinguish Revolutionary period (1789-1799) from Napoleonic era (1799-1815). "
                "Revolutionary dress differs significantly from Imperial military uniforms."
    ),
    ConfusionRisk(
        target_era="american_revolution",
        confused_with="french_revolution",
        risk_level=0.6,
        distinguishing_features=[
            "Blue Continental Army coats (NOT French blue)",
            "American tricorn style (NOT French styles)",
            "Colonial architecture (NOT French neoclassical)",
            "English language documents (NOT French)",
        ],
        warning="American and French Revolutions have different aesthetics despite "
                "occurring in the same era. American colonial vs French neoclassical."
    ),
    ConfusionRisk(
        target_era="world_war_1",
        confused_with="world_war_2",
        risk_level=0.8,
        distinguishing_features=[
            "Brodie/Adrian/Stahlhelm (NOT M1/later Stahlhelm)",
            "Trench warfare setting (NOT mobile warfare)",
            "Bolt-action rifles dominant (NOT semi-auto)",
            "Biplanes (NOT monoplanes)",
            "No tanks early war, primitive tanks later",
        ],
        warning="WWI and WWII have distinct equipment, uniforms, and warfare styles. "
                "WWI: trenches, biplanes, primitive tanks. WWII: mobile warfare, "
                "advanced aircraft, iconic tanks."
    ),
    ConfusionRisk(
        target_era="tudor_england",
        confused_with="stuart_england",
        risk_level=0.7,
        distinguishing_features=[
            "Tudor: Large ruffs, doublets, codpieces",
            "Stuart: Cavalier hats, falling collars, looser cuts",
            "Tudor: Flat caps, gable hoods",
            "Stuart: Wide-brimmed hats, natural hair/wigs",
        ],
        warning="Tudor (1485-1603) and Stuart (1603-1714) fashion differs significantly. "
                "Ruffs and doublets vs cavalier style."
    ),
    ConfusionRisk(
        target_era="ancient_greece",
        confused_with="roman_republic",
        risk_level=0.7,
        distinguishing_features=[
            "Greek: Chiton and himation (NOT toga)",
            "Greek: Hoplite armor with round shield (NOT rectangular scutum)",
            "Greek: Column styles (Doric, Ionic, Corinthian)",
            "Roman: Toga with specific draping, different armor",
        ],
        warning="Greek and Roman cultures have distinct dress, armor, and architecture "
                "despite both being 'ancient classical.'"
    ),
]


def detect_confusion_risks(
    year: int,
    location: str | None = None,
    query: str = "",
) -> list[ConfusionRisk]:
    """Detect potential era confusion risks for a given query.

    Args:
        year: The target year
        location: Optional location hint
        query: The original query text

    Returns:
        List of ConfusionRisk objects for potential confusions
    """
    era = get_era_for_year(year, location)
    if not era:
        return []

    risks = []
    for pair in CONFUSION_PAIRS:
        if pair.target_era == era:
            risks.append(pair)

    # Sort by risk level
    risks.sort(key=lambda r: r.risk_level, reverse=True)
    return risks


# ==============================================================================
# Famous Scene / Artwork Detection
# ==============================================================================

@dataclass
class FamousSceneReference:
    """A famous historical artwork or scene that may cause drift."""
    name: str
    artist: str | None
    year_created: int | None
    depicts_era: str
    depicts_year_approx: int
    visual_elements: list[str]
    correction_guidance: str


# Famous artworks that often cause concept bleed
FAMOUS_SCENES: list[FamousSceneReference] = [
    FamousSceneReference(
        name="Death of Caesar",
        artist="Various (esp. Vincenzo Camuccini)",
        year_created=1806,
        depicts_era="roman_republic",
        depicts_year_approx=-44,
        visual_elements=["toga", "roman senate", "stabbing", "marble columns"],
        correction_guidance="If depicting a non-Roman assassination, explicitly specify "
                           "the correct period dress and architecture. Avoid toga imagery."
    ),
    FamousSceneReference(
        name="Washington Crossing the Delaware",
        artist="Emanuel Leutze",
        year_created=1851,
        depicts_era="american_revolution",
        depicts_year_approx=1776,
        visual_elements=["boat", "ice", "flag", "standing figure"],
        correction_guidance="This composition often bleeds into other river crossing scenes. "
                           "Specify exact historical context and period details."
    ),
    FamousSceneReference(
        name="Death of Marat",
        artist="Jacques-Louis David",
        year_created=1793,
        depicts_era="french_revolution",
        depicts_year_approx=1793,
        visual_elements=["bathtub", "letter", "wound", "neoclassical simplicity"],
        correction_guidance="David's neoclassical style may pull generation toward Roman "
                           "aesthetics. Explicitly request French Revolutionary dress."
    ),
    FamousSceneReference(
        name="Oath of the Horatii",
        artist="Jacques-Louis David",
        year_created=1784,
        depicts_era="roman_republic",
        depicts_year_approx=-669,
        visual_elements=["three swords", "raised arms", "roman architecture", "toga"],
        correction_guidance="This iconic pose with raised swords may appear in non-Roman "
                           "oath scenes. Specify correct period if not Roman."
    ),
    FamousSceneReference(
        name="Liberty Leading the People",
        artist="Eugene Delacroix",
        year_created=1830,
        depicts_era="french_revolution",  # Actually July Revolution, but often confused
        depicts_year_approx=1830,
        visual_elements=["woman with flag", "barricade", "tricolor", "bare chest"],
        correction_guidance="Often conflated with 1789 Revolution. This depicts 1830 "
                           "July Revolution. Different fashion and context."
    ),
    FamousSceneReference(
        name="Napoleon Crossing the Alps",
        artist="Jacques-Louis David",
        year_created=1801,
        depicts_era="napoleonic",
        depicts_year_approx=1800,
        visual_elements=["rearing horse", "pointing upward", "red cape", "bicorne"],
        correction_guidance="Iconic Napoleon imagery may bleed into other mounted leader "
                           "portraits. Specify correct leader and period."
    ),
    FamousSceneReference(
        name="Signing of the Declaration of Independence",
        artist="John Trumbull",
        year_created=1819,
        depicts_era="american_revolution",
        depicts_year_approx=1776,
        visual_elements=["men at table", "document", "colonial dress", "formal gathering"],
        correction_guidance="This formal signing scene composition may appear in other "
                           "document-signing moments. Specify exact historical context."
    ),
]


def detect_famous_scene_risks(query: str, year: int) -> list[FamousSceneReference]:
    """Detect if query might drift toward famous artwork compositions.

    Args:
        query: The original query text
        year: The target year

    Returns:
        List of potentially influential famous scenes
    """
    query_lower = query.lower()
    risks = []

    # Keyword detection
    keywords_to_scenes = {
        ("caesar", "assassination", "ides", "march", "stabbing", "senate"): "Death of Caesar",
        ("crossing", "delaware", "washington", "boat", "river"): "Washington Crossing the Delaware",
        ("marat", "bathtub", "assassination", "charlotte"): "Death of Marat",
        ("oath", "sword", "brothers", "horatii"): "Oath of the Horatii",
        ("liberty", "barricade", "leading", "flag"): "Liberty Leading the People",
        ("napoleon", "alps", "horse", "crossing"): "Napoleon Crossing the Alps",
        ("declaration", "independence", "signing", "trumbull"): "Signing of the Declaration of Independence",
    }

    for keywords, scene_name in keywords_to_scenes.items():
        if any(kw in query_lower for kw in keywords):
            for scene in FAMOUS_SCENES:
                if scene.name == scene_name:
                    risks.append(scene)
                    break

    return risks


# ==============================================================================
# Mutual Exclusion Rules
# ==============================================================================

# Visual elements that should NEVER appear together
MUTUAL_EXCLUSIONS: list[tuple[set[str], set[str], str]] = [
    # Clothing
    (
        {"roman toga", "toga", "ancient roman dress"},
        {"bicorne hat", "tricorn hat", "powdered wig", "18th century coat"},
        "Roman dress cannot appear with 18th-century European fashion"
    ),
    (
        {"medieval plate armor", "full plate", "knight armor"},
        {"ancient toga", "greek chiton", "roman sandals"},
        "Medieval armor cannot appear with ancient classical dress"
    ),
    (
        {"victorian dress", "crinoline", "bustle"},
        {"medieval dress", "renaissance gown", "elizabethan ruff"},
        "Victorian fashion cannot appear with pre-18th century dress"
    ),

    # Weapons
    (
        {"gladius", "roman sword", "pilum javelin"},
        {"musket", "flintlock", "bayonet", "rifle"},
        "Ancient Roman weapons cannot appear with firearms"
    ),
    (
        {"medieval longbow", "crossbow medieval"},
        {"machine gun", "automatic weapon", "modern rifle"},
        "Medieval ranged weapons cannot appear with modern firearms"
    ),

    # Architecture
    (
        {"roman forum", "roman columns", "colosseum"},
        {"gothic cathedral", "medieval castle", "half-timbered"},
        "Roman architecture cannot appear with medieval European architecture"
    ),
    (
        {"ancient greek temple", "parthenon", "acropolis"},
        {"art deco building", "skyscraper", "modern architecture"},
        "Ancient Greek architecture cannot appear with modern buildings"
    ),

    # Technology
    (
        {"horse-drawn carriage", "oil lamp", "candle light"},
        {"automobile", "electric light", "neon sign"},
        "Pre-electric technology cannot appear with electrical technology"
    ),
    (
        {"quill pen", "parchment", "wax seal"},
        {"typewriter", "computer", "smartphone"},
        "Ancient/medieval writing tools cannot appear with modern devices"
    ),
]


@dataclass
class ExclusionViolation:
    """A detected mutual exclusion violation."""
    element_a: str
    element_b: str
    reason: str


def check_mutual_exclusions(elements: list[str]) -> list[ExclusionViolation]:
    """Check if a list of elements contains mutually exclusive items.

    Args:
        elements: List of visual elements to check

    Returns:
        List of violations found
    """
    elements_lower = {e.lower() for e in elements}
    violations = []

    for set_a, set_b, reason in MUTUAL_EXCLUSIONS:
        found_a = elements_lower & set_a
        found_b = elements_lower & set_b

        if found_a and found_b:
            violations.append(ExclusionViolation(
                element_a=", ".join(found_a),
                element_b=", ".join(found_b),
                reason=reason,
            ))

    return violations


# ==============================================================================
# Comprehensive Validation
# ==============================================================================

@dataclass
class HistoricalValidationResult:
    """Complete validation result for a historical scene."""
    year: int
    location: str | None
    era: str | None
    negative_prompts: list[str]
    confusion_risks: list[ConfusionRisk]
    famous_scene_risks: list[FamousSceneReference]
    exclusion_violations: list[ExclusionViolation]
    accuracy_warnings: list[str] = field(default_factory=list)
    confidence_score: float = 1.0

    def get_combined_negative_prompt(self) -> str:
        """Get all negative prompts as a single string."""
        all_negatives = self.negative_prompts.copy()

        # Add warnings from confusion risks
        for risk in self.confusion_risks:
            if risk.risk_level > 0.7:
                # Add the confused-with era's typical elements
                confused_era = risk.confused_with
                if confused_era in ERA_NEGATIVE_PROMPTS:
                    # Get a few key items from the confused era
                    all_negatives.extend(ERA_NEGATIVE_PROMPTS[confused_era][:5])

        # Deduplicate
        seen = set()
        unique = []
        for item in all_negatives:
            if item.lower() not in seen:
                seen.add(item.lower())
                unique.append(item)

        return ", ".join(unique)

    def get_distinguishing_guidance(self) -> str:
        """Get guidance on how to distinguish from confused eras."""
        if not self.confusion_risks:
            return ""

        guidance_parts = []
        for risk in self.confusion_risks[:2]:  # Top 2 risks
            features = "\n  - ".join(risk.distinguishing_features[:3])
            guidance_parts.append(
                f"To distinguish from {risk.confused_with}:\n  - {features}"
            )

        return "\n\n".join(guidance_parts)


def validate_historical_scene(
    year: int,
    location: str | None = None,
    query: str = "",
    visual_elements: list[str] | None = None,
) -> HistoricalValidationResult:
    """Perform comprehensive historical validation.

    Args:
        year: The target year
        location: Optional location hint
        query: The original query
        visual_elements: Optional list of visual elements to validate

    Returns:
        HistoricalValidationResult with all validation data
    """
    era = get_era_for_year(year, location)
    negative_prompts = get_era_negative_prompts(year, location)
    confusion_risks = detect_confusion_risks(year, location, query)
    famous_scene_risks = detect_famous_scene_risks(query, year)

    # Check exclusions if elements provided
    exclusion_violations = []
    if visual_elements:
        exclusion_violations = check_mutual_exclusions(visual_elements)

    # Calculate confidence score
    confidence = 1.0
    if confusion_risks:
        # Reduce confidence based on confusion risk
        max_risk = max(r.risk_level for r in confusion_risks)
        confidence -= max_risk * 0.3
    if famous_scene_risks:
        confidence -= 0.1 * len(famous_scene_risks)
    if exclusion_violations:
        confidence -= 0.2 * len(exclusion_violations)
    confidence = max(0.1, confidence)

    # Generate warnings
    warnings = []
    for risk in confusion_risks:
        if risk.risk_level > 0.6:
            warnings.append(risk.warning)
    for scene in famous_scene_risks:
        warnings.append(scene.correction_guidance)
    for violation in exclusion_violations:
        warnings.append(f"EXCLUSION VIOLATION: {violation.reason}")

    return HistoricalValidationResult(
        year=year,
        location=location,
        era=era,
        negative_prompts=negative_prompts,
        confusion_risks=confusion_risks,
        famous_scene_risks=famous_scene_risks,
        exclusion_violations=exclusion_violations,
        accuracy_warnings=warnings,
        confidence_score=confidence,
    )
