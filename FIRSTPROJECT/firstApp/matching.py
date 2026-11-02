from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from fairmatch.engine import convert_quantity, recommend_allocations

from .models import Allocation, FoodBridgeListing, HomeNeed, ResourceOffer


class FairMatchError(Exception):
    pass


def sync_foodbridge_resource_offer(listing):
    allocated = Allocation.objects.filter(
        resource_offer__foodbridge_listing=listing,
        status__in=["approved", "delivered"],
    ).aggregate(total=Sum("quantity_allocated"))["total"] or Decimal("0")
    remaining = max(Decimal("0"), Decimal(listing.quantity) - allocated)
    is_approved = listing.status == "approved" and listing.food_safety_confirmed
    if listing.status == "completed":
        availability_status = "delivered"
    elif listing.status == "rejected":
        availability_status = "cancelled"
    elif (
        is_approved
        and listing.expiry_date >= timezone.localdate()
        and remaining > 0
    ):
        availability_status = "available"
    elif is_approved:
        availability_status = "reserved"
    else:
        availability_status = "cancelled"

    return ResourceOffer.objects.update_or_create(
        foodbridge_listing=listing,
        defaults={
            "donor": None,
            "resource_type": listing.food_name[:120],
            "quantity_available": remaining,
            "unit": listing.unit[:20],
            "expiry_date": listing.expiry_date,
            "collection_location": listing.location[:200],
            "available_until": listing.expiry_date,
            "safety_status": "approved" if is_approved else "pending",
            "availability_status": availability_status,
        },
    )[0]


def eligible_needs(*, lock=False):
    needs = HomeNeed.objects.filter(
        home__is_verified=True,
        verification_status__in=["verified", "approved"],
        is_published=True,
        quantity_fulfilled__lt=F("quantity_requested"),
    ).select_related("home").order_by("pk")
    if lock:
        needs = needs.select_for_update()
    return list(needs)


def _need_payload(need):
    return {
        "need_id": need.pk,
        "home_id": need.home_id,
        "resource_type": need.resource_type,
        "quantity_requested": float(need.quantity_requested),
        "quantity_fulfilled": float(need.quantity_fulfilled),
        "urgency": need.urgency,
        "deadline": need.deadline.isoformat() if need.deadline else None,
        "verification_status": need.verification_status,
        "delivery_feasible": need.delivery_feasible,
        "storage_capacity_available": need.storage_capacity_available,
        "unit": need.unit,
    }


def _offer_payload(offer):
    return {
        "resource_id": offer.pk,
        "donor_id": offer.donor_id,
        "resource_type": offer.resource_type,
        "quantity_available": float(offer.quantity_available),
        "unit": offer.unit,
        "expiry_date": offer.expiry_date.isoformat() if offer.expiry_date else None,
        "collection_location": offer.collection_location,
        "available_until": offer.available_until.isoformat() if offer.available_until else None,
        "safety_status": offer.safety_status,
        "availability_status": offer.availability_status,
    }


def offer_recommendations(offer, needs=None, allocations=None):
    if offer.foodbridge_listing_id and (
        offer.foodbridge_listing.status != "approved"
        or not offer.foodbridge_listing.food_safety_confirmed
    ):
        return []
    needs = eligible_needs() if needs is None else list(needs)
    allocations = (
        list(
            Allocation.objects.filter(
                resource_offer=offer,
                status__in=["approved", "delivered"],
            ).select_related("need__home")
        )
        if allocations is None
        else list(allocations)
    )
    history = [
        {
            "resource_id": offer.pk,
            "need_id": allocation.need_id,
            "home_id": allocation.need.home_id,
            "quantity_allocated": float(allocation.quantity_allocated),
        }
        for allocation in allocations
    ]
    need_by_id = {need.pk: need for need in needs}
    recommendations = recommend_allocations(
        [_need_payload(need) for need in needs],
        _offer_payload(offer),
        history,
    )
    for recommendation in recommendations:
        recommendation["need"] = need_by_id[recommendation["need_id"]]
    return recommendations


def fairmatch_board():
    offers = ResourceOffer.objects.filter(
        safety_status__in=["approved", "safe", "verified"],
        availability_status="available",
        quantity_available__gt=0,
    ).filter(
        Q(foodbridge_listing__isnull=True)
        | Q(
            foodbridge_listing__status="approved",
            foodbridge_listing__food_safety_confirmed=True,
        )
    ).select_related("foodbridge_listing").order_by("-created_at", "pk")
    needs = eligible_needs()
    allocations_by_offer = defaultdict(list)
    for allocation in Allocation.objects.filter(
        status__in=["approved", "delivered"],
        resource_offer__in=offers,
    ).select_related("need__home"):
        allocations_by_offer[allocation.resource_offer_id].append(allocation)

    matches = [
        {
            "offer": offer,
            "recommendations": offer_recommendations(
                offer,
                needs,
                allocations_by_offer[offer.pk],
            ),
        }
        for offer in offers
    ]
    return matches, len(needs)


@transaction.atomic
def allocate_fairmatch_recommendation(offer_id, need_id):
    try:
        offer_reference = ResourceOffer.objects.only(
            "pk",
            "foodbridge_listing_id",
        ).get(pk=offer_id)
    except ResourceOffer.DoesNotExist as error:
        raise FairMatchError("This offer no longer exists.") from error

    listing = None
    if offer_reference.foodbridge_listing_id:
        listing = FoodBridgeListing.objects.select_for_update().get(
            pk=offer_reference.foodbridge_listing_id
        )
    offer = ResourceOffer.objects.select_for_update().get(pk=offer_id)
    if listing is not None:
        offer.foodbridge_listing = listing

    if listing and (
        listing.status != "approved"
        or not listing.food_safety_confirmed
    ):
        raise FairMatchError("This FoodBridge offer must be approved before allocation.")

    needs = eligible_needs(lock=True)
    recommendations = offer_recommendations(offer, needs)
    recommendation = next(
        (
            item
            for item in recommendations
            if item["need_id"] == need_id
        ),
        None,
    )
    if recommendation is None:
        raise FairMatchError(
            "This match is no longer eligible. Refresh FairMatch and review the current recommendations."
        )

    need = recommendation["need"]
    offer_quantity = Decimal(str(recommendation["recommended_quantity"]))
    need_quantity = Decimal(
        str(convert_quantity(offer_quantity, offer.unit, need.unit))
    )
    if (
        offer_quantity <= 0
        or offer_quantity > offer.quantity_available
        or need.quantity_fulfilled + need_quantity > need.quantity_requested
    ):
        raise FairMatchError(
            "The available quantities changed. Refresh FairMatch before allocating."
        )

    allocation = Allocation.objects.create(
        resource_offer=offer,
        need=need,
        quantity_allocated=offer_quantity,
        status="delivered",
        notes=(
            "FairMatch recommendation confirmed by a coordinator; receipt recorded. "
            f"{offer_quantity} {offer.unit} allocated as {need_quantity} {need.unit}."
        ),
    )
    need.quantity_fulfilled += need_quantity
    need.save(update_fields=["quantity_fulfilled", "updated_at"])
    offer.quantity_available -= offer_quantity
    if offer.quantity_available <= 0:
        offer.availability_status = "reserved"
    offer.save(update_fields=["quantity_available", "availability_status", "updated_at"])
    return allocation
