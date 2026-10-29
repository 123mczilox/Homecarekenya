from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_resource_type(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ")


def _normalize_unit(value: Any) -> str:
    unit = str(value or "").strip().lower()
    aliases = {
        "kg": "kg",
        "kilogram": "kg",
        "kilograms": "kg",
        "kgs": "kg",
        "g": "g",
        "gram": "g",
        "grams": "g",
        "lb": "lb",
        "lbs": "lb",
        "pound": "lb",
        "bags": "bags",
        "bag": "bags",
        "packet": "packet",
        "packets": "packet",
        "litres": "litres",
        "liters": "litres",
        "litre": "litres",
        "liter": "litres",
        "l": "litres",
    }
    return aliases.get(unit, unit)


def validate_need(need: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a single need record and return normalized information.

    The function does not query the database. It simply converts fields to a
    consistent format and flags issues when the data is missing or unusable.
    """
    if not isinstance(need, dict):
        return {
            "valid": False,
            "errors": ["Need must be a dictionary."],
            "warnings": [],
        }

    errors: List[str] = []
    warnings: List[str] = []

    need_id = need.get("need_id")
    if need_id in (None, ""):
        errors.append("need_id is missing.")

    home_id = need.get("home_id")
    if home_id in (None, ""):
        errors.append("home_id is missing.")

    resource_type = _normalize_resource_type(need.get("resource_type"))
    if not resource_type:
        errors.append("resource_type is missing.")

    quantity_requested = _as_float(need.get("quantity_requested"), 0.0)
    quantity_fulfilled = _as_float(need.get("quantity_fulfilled"), 0.0)
    if quantity_requested <= 0:
        errors.append("quantity_requested must be greater than zero.")
    if quantity_fulfilled < 0:
        errors.append("quantity_fulfilled cannot be negative.")

    urgency = need.get("urgency")
    try:
        urgency_score = int(urgency)
    except (TypeError, ValueError):
        urgency_score = None
    if urgency_score is None:
        warnings.append("urgency is missing or invalid; score will be penalized.")

    deadline = need.get("deadline")
    if deadline is None:
        warnings.append("deadline is missing; delivery feasibility may be uncertain.")

    storage_capacity_available = need.get("storage_capacity_available")
    if storage_capacity_available is False:
        warnings.append("storage capacity is not available.")

    outstanding = max(0.0, quantity_requested - quantity_fulfilled)
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "need_id": need_id,
        "home_id": home_id,
        "resource_type": resource_type,
        "quantity_requested": quantity_requested,
        "quantity_fulfilled": quantity_fulfilled,
        "outstanding_quantity": outstanding,
        "urgency": urgency,
        "urgency_score": urgency_score,
        "deadline": deadline,
        "storage_capacity_available": storage_capacity_available,
    }


def validate_offer(offer: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a single resource offer and normalize its fields."""
    if not isinstance(offer, dict):
        return {
            "valid": False,
            "errors": ["Offer must be a dictionary."],
            "warnings": [],
        }

    errors: List[str] = []
    warnings: List[str] = []

    resource_id = offer.get("resource_id")
    if resource_id in (None, ""):
        errors.append("resource_id is missing.")

    resource_type = _normalize_resource_type(offer.get("resource_type"))
    if not resource_type:
        errors.append("resource_type is missing.")

    quantity_available = _as_float(offer.get("quantity_available"), 0.0)
    if quantity_available <= 0:
        errors.append("quantity_available must be greater than zero.")

    unit = _normalize_unit(offer.get("unit"))
    if not unit:
        errors.append("unit is missing.")

    safety_status = str(offer.get("safety_status") or "").strip().lower()
    if safety_status not in {"approved", "safe", "verified", "ok"}:
        errors.append("safety_status is not approved for use.")

    availability_status = str(offer.get("availability_status") or "").strip().lower()
    if availability_status not in {"available", "approved", "ready"}:
        errors.append("availability_status is not available.")

    expiry_date = offer.get("expiry_date")
    available_until = offer.get("available_until")
    expiry_candidates = []
    for field_name in ("expiry_date", "available_until"):
        value = offer.get(field_name)
        if value in (None, ""):
            continue
        parsed = _parse_date(value)
        if parsed is not None:
            expiry_candidates.append(parsed)
        else:
            warnings.append(f"{field_name} is not a valid date and will be ignored.")
    if expiry_candidates and min(expiry_candidates) < date.today():
        errors.append("Offer is expired.")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "resource_id": resource_id,
        "resource_type": resource_type,
        "quantity_available": quantity_available,
        "unit": unit,
        "safety_status": safety_status,
        "availability_status": availability_status,
        "expiry_date": expiry_date,
        "available_until": available_until,
    }


def _parse_date(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        if isinstance(value, str):
            return date.fromisoformat(value)
    except ValueError:
        pass
    return None


def _compatible_units(unit_a: str, unit_b: str) -> bool:
    if not unit_a or not unit_b:
        return False
    if unit_a == unit_b:
        return True
    if {unit_a, unit_b} == {"kg", "g"}:
        return True
    if {unit_a, unit_b} == {"litres", "l"}:
        return True
    return False


def _common_unit(unit_a: str, unit_b: str) -> str:
    if not unit_a and not unit_b:
        return ""
    if unit_a == unit_b:
        return unit_a
    if {unit_a, unit_b} == {"kg", "g"}:
        return "kg"
    if {unit_a, unit_b} == {"litres", "l"}:
        return "litres"
    return unit_a or unit_b


def _convert_to_common_unit(amount: float, from_unit: str, to_unit: str) -> float:
    if not from_unit or not to_unit or from_unit == to_unit:
        return amount
    if {from_unit, to_unit} == {"kg", "g"}:
        return amount / 1000.0 if from_unit == "g" else amount * 1000.0
    return amount


def _amount_to_common_unit(amount: float, unit: str) -> float:
    if unit == "g" and not amount:
        return 0.0
    if unit == "g":
        return amount / 1000.0
    return amount


def _total_allocated_for_home(allocation_history: Iterable[Dict[str, Any]], home_id: Any) -> float:
    total = 0.0
    for allocation in allocation_history or []:
        if not isinstance(allocation, dict):
            continue
        if allocation.get("home_id") == home_id:
            total += _as_float(allocation.get("quantity_allocated"), 0.0)
    return total


def check_eligibility(
    need: Dict[str, Any],
    resource_offer: Dict[str, Any],
    allocation_history: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Return eligibility details and clear reasons why a candidate is excluded."""
    need_result = validate_need(need)
    offer_result = validate_offer(resource_offer)
    warnings: List[str] = []
    reasons: List[str] = []

    if not need_result["valid"]:
        reasons.extend(need_result["errors"])
    if not offer_result["valid"]:
        reasons.extend(offer_result["errors"])

    if not reasons:
        resource_type_match = _normalize_resource_type(need.get("resource_type")) == _normalize_resource_type(resource_offer.get("resource_type"))
        if not resource_type_match:
            reasons.append("Resource type does not match the requested resource.")

        need_unit = _normalize_unit(need.get("unit"))
        offer_unit = _normalize_unit(resource_offer.get("unit"))
        unit_match = _compatible_units(need_unit, offer_unit)
        if not unit_match:
            reasons.append("Units are incompatible.")

        outstanding = max(0.0, _as_float(need.get("quantity_requested"), 0.0) - _as_float(need.get("quantity_fulfilled"), 0.0))
        if outstanding <= 0:
            reasons.append("There is no outstanding need.")

        available = _as_float(resource_offer.get("quantity_available"), 0.0)
        if need_unit and offer_unit and need_unit != offer_unit:
            available = _convert_to_common_unit(available, offer_unit, _common_unit(need_unit, offer_unit))
            outstanding = _convert_to_common_unit(outstanding, need_unit, _common_unit(need_unit, offer_unit))

        already_reserved = 0.0
        for allocation in allocation_history or []:
            if not isinstance(allocation, dict):
                continue
            if allocation.get("resource_id") == resource_offer.get("resource_id"):
                already_reserved += _as_float(allocation.get("quantity_allocated"), 0.0)
        remaining = max(0.0, available - already_reserved)
        if remaining <= 0:
            reasons.append("Resource quantity is already fully reserved.")

        if need.get("verification_status") not in ("verified", "approved"):
            reasons.append("Need is not verified.")

        if need.get("storage_capacity_available") is False:
            reasons.append("Home cannot safely store this resource.")

        if need.get("delivery_feasible") is False:
            reasons.append("Delivery is not feasible for this candidate.")

        if need_result["warnings"]:
            warnings.extend(need_result["warnings"])
        if offer_result["warnings"]:
            warnings.extend(offer_result["warnings"])

    eligible = not reasons
    return {
        "eligible": eligible,
        "reasons": reasons,
        "warnings": warnings,
    }


def _urgency_to_score(urgency: Any) -> float:
    try:
        value = float(urgency)
    except (TypeError, ValueError):
        return 0.0
    if value <= 0:
        return 0.0
    return min(100.0, max(0.0, (value / 5.0) * 100.0))


def _delivery_feasibility_score(need: Dict[str, Any]) -> float:
    if need.get("delivery_feasible") is True:
        return 100.0
    if need.get("delivery_feasible") is False:
        return 0.0
    if need.get("deadline") is None:
        return 40.0
    return 60.0


def _equity_score(need: Dict[str, Any], allocation_history: Optional[Iterable[Dict[str, Any]]] = None) -> float:
    home_id = need.get("home_id")
    recent = _total_allocated_for_home(allocation_history or [], home_id)
    outstanding = max(0.0, _as_float(need.get("quantity_requested"), 0.0) - _as_float(need.get("quantity_fulfilled"), 0.0))
    if outstanding <= 0:
        return 100.0
    penalty = min(100.0, (recent / max(1.0, outstanding)) * 100.0)
    return max(0.0, 100.0 - penalty)


def calculate_priority_score(
    need: Dict[str, Any],
    resource_offer: Dict[str, Any],
    allocation_history: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Compute the explainable weighted score for a single need and offer."""
    eligibility = check_eligibility(need, resource_offer, allocation_history)
    if not eligibility["eligible"]:
        return {
            "eligible": False,
            "score": 0.0,
            "components": {
                "urgency_score": 0.0,
                "unmet_need_score": 0.0,
                "delivery_feasibility_score": 0.0,
                "allocation_equity_score": 0.0,
            },
            "reasons": eligibility["reasons"],
            "warnings": eligibility["warnings"],
        }

    requested = _as_float(need.get("quantity_requested"), 0.0)
    fulfilled = _as_float(need.get("quantity_fulfilled"), 0.0)
    outstanding = max(0.0, requested - fulfilled)
    unmet_score = (outstanding / requested * 100.0) if requested > 0 else 0.0

    need_unit = _normalize_unit(need.get("unit"))
    offer_unit = _normalize_unit(resource_offer.get("unit"))
    if need_unit and offer_unit and need_unit != offer_unit:
        common = _common_unit(need_unit, offer_unit)
        requested = _convert_to_common_unit(requested, need_unit, common)
        outstanding = _convert_to_common_unit(outstanding, need_unit, common)
        if requested > 0:
            unmet_score = (outstanding / requested * 100.0)

    urgency_score = _urgency_to_score(need.get("urgency"))
    delivery_score = _delivery_feasibility_score(need)
    equity_score = _equity_score(need, allocation_history)

    score = (
        0.40 * urgency_score
        + 0.30 * unmet_score
        + 0.20 * delivery_score
        + 0.10 * equity_score
    )

    return {
        "eligible": True,
        "score": round(score, 2),
        "components": {
            "urgency_score": round(urgency_score, 2),
            "unmet_need_score": round(unmet_score, 2),
            "delivery_feasibility_score": round(delivery_score, 2),
            "allocation_equity_score": round(equity_score, 2),
        },
        "reasons": [],
        "warnings": eligibility["warnings"],
    }


def _recommend_quantity(need: Dict[str, Any], remaining_available: float, resource_offer: Optional[Dict[str, Any]] = None) -> float:
    requested = _as_float(need.get("quantity_requested"), 0.0)
    fulfilled = _as_float(need.get("quantity_fulfilled"), 0.0)
    outstanding = max(0.0, requested - fulfilled)

    if resource_offer is not None:
        need_unit = _normalize_unit(need.get("unit"))
        offer_unit = _normalize_unit(resource_offer.get("unit"))
        if need_unit and offer_unit and need_unit != offer_unit:
            common = _common_unit(need_unit, offer_unit)
            outstanding = _convert_to_common_unit(outstanding, need_unit, common)
            remaining_available = _convert_to_common_unit(remaining_available, offer_unit, common)

    return max(0.0, min(outstanding, remaining_available))


def rank_needs(
    needs: Iterable[Dict[str, Any]],
    resource_offer: Dict[str, Any],
    allocation_history: Optional[Iterable[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Rank eligible needs for a single resource offer.

    Returns a list of recommendations with their scores and explanations. Each
    item is JSON-serializable and suitable for a Django service layer.
    """
    ranked: List[Dict[str, Any]] = []
    for need in needs or []:
        score_info = calculate_priority_score(need, resource_offer, allocation_history)
        if not score_info["eligible"]:
            continue

        deadline = need.get("deadline")
        try:
            deadline_value = _parse_date(deadline)
        except TypeError:
            deadline_value = None

        ranked.append(
            {
                "need_id": need.get("need_id"),
                "home_id": need.get("home_id"),
                "resource_type": _normalize_resource_type(need.get("resource_type")),
                "priority_score": score_info["score"],
                "components": score_info["components"],
                "deadline": deadline,
                "deadline_sort": deadline_value.isoformat() if deadline_value else "9999-12-31",
                "warnings": score_info["warnings"],
            }
        )

    ranked.sort(key=lambda item: (-item["priority_score"], item["deadline_sort"], str(item["need_id"])))
    return ranked


def recommend_allocations(
    needs: Iterable[Dict[str, Any]],
    resource_offer: Dict[str, Any],
    allocation_history: Optional[Iterable[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Create recommended allocations without exceeding available supply."""
    ranked = rank_needs(needs, resource_offer, allocation_history)
    available = _as_float(resource_offer.get("quantity_available"), 0.0)
    allocated_total = 0.0
    recommendations: List[Dict[str, Any]] = []

    for result in ranked:
        need_match = next((item for item in needs or [] if item.get("need_id") == result["need_id"]), None)
        if need_match is None:
            continue

        already_reserved = 0.0
        for allocation in allocation_history or []:
            if not isinstance(allocation, dict):
                continue
            if allocation.get("resource_id") == resource_offer.get("resource_id") and allocation.get("need_id") == need_match.get("need_id"):
                already_reserved += _as_float(allocation.get("quantity_allocated"), 0.0)

        remaining_available = max(0.0, available - allocated_total)
        if remaining_available <= 0:
            break

        quantity = _recommend_quantity(need_match, remaining_available, resource_offer)
        quantity = max(0.0, quantity - already_reserved)
        if quantity <= 0:
            continue

        explanation = (
            f"Home {need_match.get('home_id')} has an outstanding need of "
            f"{need_match.get('quantity_requested', 0)} and the allocation uses the "
            f"available stock without exceeding remaining supply."
        )

        recommendations.append(
            {
                "need_id": need_match.get("need_id"),
                "home_id": need_match.get("home_id"),
                "resource_id": resource_offer.get("resource_id"),
                "priority_score": result["priority_score"],
                "recommended_quantity": round(quantity, 2),
                "components": result["components"],
                "eligibility": True,
                "explanation": explanation,
                "warnings": result["warnings"],
            }
        )
        allocated_total += quantity

    return recommendations
