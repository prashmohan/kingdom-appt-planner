"""Constants and configuration values for the Kingdom Appointment Planner."""

DEFAULT_SLOT_COUNT: int = 49

SCORING_MULTIPLIERS: dict[str, dict[str, int]] = {
    "construction": {
        "speedups": 30,
        "truegold": 2000,
        "tempered_truegold": 30000,
    },
    "training": {"speedups": 90},
    "research": {"speedups": 30, "truegold_dust": 1000},
}

RESERVED_SLUGS: set[str] = {
    "admin",
    "create",
    "distribute",
    "event",
    "export_csv",
    "guide",
    "static",
    "success",
    "confirm",
    "unlock",
    "delete",
    "manual_assign",
    "unset",
    "override_resources",
    "update_alliance",
    "submission-success",
    "favicon.ico",
    "superadmin",
}


def compute_score(day_type: str, raw_data: dict[str, int]) -> int:
    """Calculate resource score for a given day type using standardized multipliers."""
    multipliers = SCORING_MULTIPLIERS.get(day_type, {})
    return sum(int(raw_data.get(k, 0)) * mult for k, mult in multipliers.items())
