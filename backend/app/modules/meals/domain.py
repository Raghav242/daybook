"""Pure recipe scaling and grocery merging rules.

Quantities are Decimal and rounded half-up to the grocery precision (0.001). Ingredients
merge only when their normalized names and units are identical. Units are compared after
casefolding, collapsing spaces and resolving a small table of spellings of the *same* unit
("grams" -> "g", "tbsp." -> "tbsp"). No conversion between different units is attempted:
cups and grams, or pieces and kilograms, stay on separate lines for the user to review.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

QUANTUM = Decimal("0.001")

# Spelling variants of identical units only. Never add conversions here.
UNIT_SPELLINGS = {
    "g": ("g", "gram", "grams", "gr"),
    "kg": ("kg", "kgs", "kilogram", "kilograms"),
    "mg": ("mg", "milligram", "milligrams"),
    "ml": ("ml", "milliliter", "milliliters", "millilitre", "millilitres"),
    "l": ("l", "liter", "liters", "litre", "litres"),
    "tsp": ("tsp", "tsp.", "teaspoon", "teaspoons"),
    "tbsp": ("tbsp", "tbsp.", "tablespoon", "tablespoons"),
    "cup": ("cup", "cups"),
    "oz": ("oz", "oz.", "ounce", "ounces"),
    "lb": ("lb", "lbs", "lb.", "pound", "pounds"),
    "piece": ("piece", "pieces", "pc", "pcs"),
    "clove": ("clove", "cloves"),
    "can": ("can", "cans"),
    "pinch": ("pinch", "pinches"),
}
_UNIT_LOOKUP = {
    spelling: unit for unit, spellings in UNIT_SPELLINGS.items() for spelling in spellings
}


def normalize_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def normalize_unit(unit: str) -> str:
    text = normalize_text(unit)
    return _UNIT_LOOKUP.get(text, text)


def scale(quantity: Decimal, recipe_servings: int, planned_servings: int) -> Decimal:
    """Scale an ingredient quantity to the planned servings, never rounding to zero."""
    if recipe_servings <= 0 or planned_servings <= 0:
        raise ValueError("Servings must be positive.")
    scaled = (Decimal(quantity) * planned_servings / recipe_servings).quantize(
        QUANTUM, rounding=ROUND_HALF_UP
    )
    return max(scaled, QUANTUM)


@dataclass
class Ingredient:
    name: str
    quantity: Decimal
    unit: str
    category: str
    source: str


@dataclass
class Line:
    key: str
    name: str
    unit: str
    quantity: Decimal
    category: str
    sources: list[str] = field(default_factory=list)
    # True when another line has the same ingredient name in a different unit.
    other_units: bool = False


def merge(ingredients: list[Ingredient]) -> list[Line]:
    """Combine compatible ingredients; keep incompatible units as separate lines."""
    lines: dict[tuple[str, str], Line] = {}
    for item in ingredients:
        name_key, unit_key = normalize_text(item.name), normalize_unit(item.unit)
        line = lines.get((name_key, unit_key))
        if line is None:
            line = lines[(name_key, unit_key)] = Line(
                key=f"{name_key}|{unit_key}",
                name=" ".join(item.name.split()),
                unit=" ".join(item.unit.split()),
                quantity=Decimal(0),
                category=item.category,
            )
        line.quantity += item.quantity
        line.category = line.category or item.category
        if item.source not in line.sources:
            line.sources.append(item.source)
    names: dict[str, int] = {}
    for name_key, _ in lines:
        names[name_key] = names.get(name_key, 0) + 1
    for (name_key, _), line in lines.items():
        line.other_units = names[name_key] > 1
    return sorted(lines.values(), key=lambda line: (line.category.casefold(), line.key))
