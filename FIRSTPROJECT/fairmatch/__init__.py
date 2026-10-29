"""FairMatch public interfaces for resource allocation ranking.

This package keeps the allocation logic independent from Django so the backend
can pass in plain Python dictionaries and receive JSON-serializable results.
"""

from .engine import (
    calculate_priority_score,
    check_eligibility,
    rank_needs,
    recommend_allocations,
    validate_need,
    validate_offer,
)

__all__ = [
    "calculate_priority_score",
    "check_eligibility",
    "rank_needs",
    "recommend_allocations",
    "validate_need",
    "validate_offer",
]
