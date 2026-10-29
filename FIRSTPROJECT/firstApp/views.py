import logging
import os
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib import messages
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from communications.services import send_sms
from fairmatch.engine import recommend_allocations

from .backend_api import BackendAPIError, get_public_home, get_public_homes
from .forms import (
    AllocationForm,
    BookingRequestForm,
    ContributionPledgeForm,
    DonorForm,
    EventSmsSubscriptionForm,
    EventSmsUnsubscribeForm,
    FoodBridgeListingForm,
    HomeNeedSubmissionForm,
    HomeRegistrationForm,
    HomeNeedForm,
    HobbyForm,
    ResourceOfferForm,
    StudentForm,
)
from .models import (
    Allocation,
    BookingRequest,
    ChildrenHome,
    CommunityEvent,
    Donor,
    EventSmsSubscriber,
    FoodBridgeListing,
    HomeNeed,
    Hobby,
    ResourceOffer,
    Student,
)

logger = logging.getLogger(__name__)
EVENT_TIME_ZONE = ZoneInfo("Africa/Nairobi")


def backend_unavailable(request):
    return render(request, "firstApp/backend_unavailable.html", status=503)


def home(request):
    if settings.HOMECARE_API_BASE_URL:
        try:
            featured_homes = get_public_homes({"verification": "verified"})[:3]
        except BackendAPIError:
            return backend_unavailable(request)
        return render(request, "main.html", {"featured_homes": featured_homes})

    featured_homes = ChildrenHome.objects.filter(is_verified=True).order_by("-created_at")[:3]
    return render(request, "main.html", {"featured_homes": featured_homes})


def find_homes(request):
    query = request.GET.get("q", "").strip()
    county = request.GET.get("county", "").strip()
    verification = request.GET.get("verification", "").strip()

    if settings.HOMECARE_API_BASE_URL:
        try:
            homes = get_public_homes({"q": query, "county": county, "verification": verification})
        except BackendAPIError:
            return backend_unavailable(request)
        return render(
            request,
            "firstApp/find_homes.html",
            {
                "homes": homes,
                "query": query,
                "selected_county": county,
                "verification": verification,
                "counties": ChildrenHome.COUNTY_CHOICES,
            },
        )

    homes = ChildrenHome.objects.all().order_by("-created_at")
    if query:
        homes = homes.filter(Q(name__icontains=query) | Q(location__icontains=query))
    if county:
        homes = homes.filter(location=county)
    if verification == "verified":
        homes = homes.filter(is_verified=True)
    elif verification == "listed":
        homes = homes.filter(is_verified=False)

    return render(
        request,
        "firstApp/find_homes.html",
        {
            "homes": homes,
            "query": query,
            "selected_county": county,
            "verification": verification,
            "counties": ChildrenHome.COUNTY_CHOICES,
        },
    )


def home_profile(request, slug):
    if settings.HOMECARE_API_BASE_URL:
        try:
            home = get_public_home(slug)
        except BackendAPIError:
            return backend_unavailable(request)
        return render(
            request,
            "firstApp/home_profile.html",
            {"home": home, "needs": None},
        )

    home = get_object_or_404(ChildrenHome, slug=slug)
    needs = home.needs.filter(
        verification_status__in=["verified", "approved"],
        is_published=True,
        quantity_fulfilled__lt=F("quantity_requested"),
    ).order_by("-urgency", "deadline")
    return render(
        request,
        "firstApp/home_profile.html",
        {"home": home, "needs": needs},
    )


def bookings(request):
    if settings.HOMECARE_API_BASE_URL:
        try:
            homes = get_public_homes({"verification": "verified"})
        except BackendAPIError:
            return backend_unavailable(request)
    else:
        homes = ChildrenHome.objects.filter(is_verified=True).order_by("name")

    if request.method == "POST":
        form = BookingRequestForm(request.POST)
        if form.is_valid():
            booking = form.save()
            contact_phone = booking.home.phone_number or os.environ.get("DEFAULT_CONTACT_PHONE")
            if contact_phone:
                send_sms(
                    [contact_phone],
                    f"HomeCare Kenya: New visit request from {booking.visitor_name} for {booking.home.name} on {booking.date}.",
                )
            messages.success(
                request,
                "Your visit request is saved and awaiting the organization’s approval. This is not a confirmed visit.",
            )
            return redirect("Bookings")
        return render(
            request,
            "firstApp/bookings.html",
            {
                "homes": homes,
                "form": form,
            },
        )

    return render(
        request,
        "firstApp/bookings.html",
        {
            "homes": homes,
        },
    )


def events(request):
    subscription_form = EventSmsSubscriptionForm()
    unsubscribe_form = EventSmsUnsubscribeForm()
    if request.method == "POST" and request.POST.get("action") == "unsubscribe":
        unsubscribe_form = EventSmsUnsubscribeForm(request.POST)
        if unsubscribe_form.is_valid():
            updated_count = EventSmsSubscriber.objects.filter(
                phone_number=unsubscribe_form.cleaned_data["phone_number"],
                is_active=True,
            ).update(is_active=False)
            if updated_count:
                result = send_sms(
                    [unsubscribe_form.cleaned_data["phone_number"]],
                    "HomeCare Kenya: You have unsubscribed from event SMS reminders.",
                )
                if result.get("status") == "sent":
                    messages.success(request, "You are unsubscribed from event SMS reminders.")
                else:
                    logger.warning(
                        "Event SMS unsubscription confirmation failed: %s",
                        result.get("error") or result.get("message") or result.get("status"),
                    )
                    messages.warning(
                        request,
                        "You are unsubscribed, but we could not send the confirmation SMS.",
                    )
            else:
                messages.success(request, "If that number was subscribed, it is now unsubscribed.")
            return redirect("events")
    elif request.method == "POST":
        subscription_form = EventSmsSubscriptionForm(request.POST)
        if subscription_form.is_valid():
            subscriber = subscription_form.save()
            result = send_sms(
                [subscriber.phone_number],
                (
                    "HomeCare Kenya: You are subscribed to event SMS reminders. "
                    "We will text you three days before published upcoming events. "
                    "Unsubscribe anytime at homecarekenya.onrender.com/events/."
                ),
            )
            if result.get("status") == "sent":
                messages.success(request, "You are subscribed to upcoming event SMS alerts.")
            else:
                logger.warning(
                    "Event SMS subscription confirmation failed: %s",
                    result.get("error") or result.get("message") or result.get("status"),
                )
                messages.warning(
                    request,
                    "Your subscription is saved, but we could not send a confirmation SMS. "
                    "You remain subscribed to upcoming event reminders.",
                )
            return redirect("events")

    return render(
        request,
        "firstApp/events.html",
        {
            "events": CommunityEvent.objects.filter(
                is_published=True,
                event_date__gte=timezone.localdate(timezone=EVENT_TIME_ZONE),
            ),
            "subscription_form": subscription_form,
            "unsubscribe_form": unsubscribe_form,
        },
    )


def donations(request):
    form_data = request.POST if request.method == "POST" else None
    form = ContributionPledgeForm(form_data)
    if request.method == "POST" and form.is_valid():
        pledge = form.save()
        sms_failures = []
        coordinator_phone = os.environ.get("COORDINATOR_PHONE", "").strip()
        if coordinator_phone:
            coordinator_result = send_sms(
                [coordinator_phone],
                (
                    f"HomeCare Kenya: New {pledge.get_resource_type_display()} pledge "
                    f"from {pledge.donor_name}: {pledge.quantity} "
                    f"{pledge.description}. Review pending pledge in admin."
                ),
            )
            if coordinator_result.get("status") != "sent":
                sms_failures.append("coordinator")
                logger.warning("Donation pledge SMS alert to coordinator failed: %s", coordinator_result)
        else:
            sms_failures.append("coordinator")
            logger.warning("Donation pledge saved, but COORDINATOR_PHONE is not configured.")

        if pledge.phone_number and pledge.sms_consent:
            donor_result = send_sms(
                [pledge.phone_number],
                (
                    f"HomeCare Kenya: Thank you, {pledge.donor_name}. "
                    "Your contribution pledge is saved for coordinator review. "
                    "No payment has been processed."
                ),
            )
            if donor_result.get("status") != "sent":
                sms_failures.append("donor")
                logger.warning("Donation pledge SMS confirmation to donor failed: %s", donor_result)

        success_message = (
            "Your contribution pledge is saved for coordinator review. "
            "No payment has been processed."
        )
        if sms_failures:
            messages.warning(
                request,
                f"{success_message} An SMS notification could not be sent; the coordinator may need to follow up.",
            )
        else:
            messages.success(request, success_message)
        return redirect("Donations")
    return render(
        request,
        "firstApp/donations.html",
        {"form": form},
    )


def homed(request):
    return render(request, "firstApp/homed.html")


def admin_dashboard(request):
    return render(request, "firstApp/admin.html")


def admin(request):
    return admin_dashboard(request)


def needs_management(request):
    homes = ChildrenHome.objects.filter(is_verified=True).order_by("name")
    form_data = request.POST if request.method == "POST" else None
    form = HomeNeedSubmissionForm(form_data, homes=homes)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            "Your need is saved as pending and will not be published or matched until reviewed.",
        )
        return redirect("needs-management")
    return render(
        request,
        "firstApp/needs.html",
        {
            "form": form,
            "needs": HomeNeed.objects.filter(
                verification_status__in=["verified", "approved"],
                is_published=True,
                quantity_fulfilled__lt=F("quantity_requested"),
            ).select_related("home").order_by("-created_at"),
            "homes_available": homes.exists(),
        },
    )


def fairmatch(request):
    sample_need = {
        "need_id": "demo-learning-supplies",
        "home_id": "demo-home-01",
        "resource_type": "exercise books",
        "quantity_requested": 120,
        "quantity_fulfilled": 64,
        "unit": "books",
        "urgency": 4,
        "deadline": "2026-11-15",
        "verification_status": "verified",
        "storage_capacity_available": True,
        "delivery_feasible": True,
    }
    sample_offer = {
        "resource_id": "demo-offer-01",
        "resource_type": "exercise books",
        "quantity_available": 40,
        "unit": "books",
        "safety_status": "approved",
        "availability_status": "available",
    }
    recommendations = recommend_allocations([sample_need], sample_offer)
    return render(
        request,
        "firstApp/fairmatch.html",
        {
            "recommendations": recommendations,
            "recommendation": recommendations[0] if recommendations else None,
            "sample_need": sample_need,
            "sample_offer": sample_offer,
        },
    )


def foodbridge(request):
    form_data = request.POST if request.method == "POST" else None
    form = FoodBridgeListingForm(form_data)
    if request.method == "POST":
        if form.is_valid():
            listing = form.save()
            coordinator_phone = os.environ.get("COORDINATOR_PHONE")
            if coordinator_phone:
                send_sms(
                    [coordinator_phone],
                    f"HomeCare Kenya: New FoodBridge listing received: {listing.food_name} ({listing.quantity} {listing.unit}) for {listing.location}.",
                )
            messages.success(
                request,
                "Your FoodBridge offer is saved for coordinator review. It will not be matched or allocated until approved.",
            )
            return redirect("foodbridge")
        return render(
            request,
            "firstApp/foodbridge.html",
            {
                "form": form,
            },
        )
    return render(
        request,
        "firstApp/foodbridge.html",
        {"form": form},
    )


def home_registration(request):
    form_data = request.POST if request.method == "POST" else None
    form = HomeRegistrationForm(form_data)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            "Your organization details are saved and awaiting review. This submission does not verify the organization.",
        )
        return redirect("home-register")
    return render(
        request,
        "firstApp/home_registration.html",
        {"form": form},
    )


# ---------------- Donor CRUD ----------------
def createDonor(request):
    form = DonorForm()
    if request.method == "POST":
        form = DonorForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("read-donors")
    return render(request, "firstApp/form.html", {"form": form})


def readDonors(request):
    donors = Donor.objects.all().order_by("-created_at")
    return render(request, "firstApp/donors.html", {"donors": donors})


def readDonor(request, pk):
    donor = get_object_or_404(Donor, id=pk)
    return render(request, "firstApp/donor.html", {"donor": donor})


def updateDonor(request, pk):
    donor = get_object_or_404(Donor, id=pk)
    form = DonorForm(instance=donor)
    if request.method == "POST":
        form = DonorForm(request.POST, instance=donor)
        if form.is_valid():
            form.save()
            return redirect("read-donors")
    return render(request, "firstApp/form.html", {"form": form})


def deleteDonor(request, pk):
    donor = Donor.objects.get(id=pk)
    donor.delete()
    return redirect("read-donors")


# ---------------- ResourceOffer CRUD ----------------
def createResourceOffer(request):
    form = ResourceOfferForm()
    if request.method == "POST":
        form = ResourceOfferForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("read-resource-offers")
    return render(request, "firstApp/form.html", {"form": form})


def readResourceOffers(request):
    offers = ResourceOffer.objects.all().order_by("-created_at")
    return render(request, "firstApp/resource_offers.html", {"offers": offers})


def readResourceOffer(request, pk):
    offer = get_object_or_404(ResourceOffer, id=pk)
    return render(request, "firstApp/resource_offer.html", {"offer": offer})


def updateResourceOffer(request, pk):
    offer = get_object_or_404(ResourceOffer, id=pk)
    form = ResourceOfferForm(instance=offer)
    if request.method == "POST":
        form = ResourceOfferForm(request.POST, instance=offer)
        if form.is_valid():
            form.save()
            return redirect("read-resource-offers")
    return render(request, "firstApp/form.html", {"form": form})


def deleteResourceOffer(request, pk):
    offer = ResourceOffer.objects.get(id=pk)
    offer.delete()
    return redirect("read-resource-offers")


# ---------------- HomeNeed CRUD ----------------
def createHomeNeed(request):
    form = HomeNeedForm()
    if request.method == "POST":
        form = HomeNeedForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("read-home-needs")
    return render(request, "firstApp/form.html", {"form": form})


def readHomeNeeds(request):
    needs = HomeNeed.objects.all().order_by("-created_at")
    return render(request, "firstApp/home_needs.html", {"needs": needs})


def readHomeNeed(request, pk):
    need = get_object_or_404(HomeNeed, id=pk)
    return render(request, "firstApp/home_need.html", {"need": need})


def updateHomeNeed(request, pk):
    need = get_object_or_404(HomeNeed, id=pk)
    form = HomeNeedForm(instance=need)
    if request.method == "POST":
        form = HomeNeedForm(request.POST, instance=need)
        if form.is_valid():
            form.save()
            return redirect("read-home-needs")
    return render(request, "firstApp/form.html", {"form": form})


def deleteHomeNeed(request, pk):
    need = HomeNeed.objects.get(id=pk)
    need.delete()
    return redirect("read-home-needs")


# ---------------- Allocation CRUD ----------------
def createAllocation(request):
    form = AllocationForm()
    if request.method == "POST":
        form = AllocationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("read-allocations")
    return render(request, "firstApp/form.html", {"form": form})


def readAllocations(request):
    allocations = Allocation.objects.all().order_by("-allocated_at")
    return render(request, "firstApp/allocations.html", {"allocations": allocations})


def readAllocation(request, pk):
    allocation = get_object_or_404(Allocation, id=pk)
    return render(request, "firstApp/allocation.html", {"allocation": allocation})


def updateAllocation(request, pk):
    allocation = get_object_or_404(Allocation, id=pk)
    form = AllocationForm(instance=allocation)
    if request.method == "POST":
        form = AllocationForm(request.POST, instance=allocation)
        if form.is_valid():
            form.save()
            return redirect("read-allocations")
    return render(request, "firstApp/form.html", {"form": form})


def deleteAllocation(request, pk):
    allocation = Allocation.objects.get(id=pk)
    allocation.delete()
    return redirect("read-allocations")


def match_resource_offer(request, offer_id):
    offer = get_object_or_404(ResourceOffer, id=offer_id)
    needs = HomeNeed.objects.filter(
        verification_status__in=["verified", "approved"],
        is_published=True,
        resource_type__iexact=offer.resource_type,
    ).select_related("home")

    need_dicts = [
        {
            "need_id": need.id,
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
        for need in needs
    ]

    offer_dict = {
        "resource_id": offer.id,
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

    history = []
    for allocation in Allocation.objects.filter(resource_offer_id=offer.id).select_related("need__home"):
        history.append(
            {
                "resource_id": offer.id,
                "need_id": allocation.need_id,
                "home_id": allocation.need.home_id,
                "quantity_allocated": float(allocation.quantity_allocated),
            }
        )

    results = recommend_allocations(need_dicts, offer_dict, history)
    return JsonResponse({"offer_id": offer.id, "recommendations": results})


# ---------------- Student CRUD ----------------
def createStudent(request):
    form = StudentForm()
    if request.method == "POST":
        form = StudentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("read-students")
    return render(request, "firstApp/form.html", {"form": form})


def readStudents(request):
    students = Student.objects.all()
    return render(request, "firstApp/students.html", {"students": students})


def readStudent(request, pk):
    student = get_object_or_404(Student, id=pk)
    return render(request, "firstApp/student.html", {"student": student})


def updateStudent(request, pk):
    student = get_object_or_404(Student, id=pk)
    form = StudentForm(instance=student)
    if request.method == "POST":
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            return redirect("read-students")
    return render(request, "firstApp/form.html", {"form": form})


def deleteStudent(request, pk):
    student = Student.objects.get(id=pk)
    student.delete()
    return redirect("read-students")


# ---------------- HOBBY CRUD ----------------
def createHobby(request):
    form = HobbyForm()
    if request.method == "POST":
        form = HobbyForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("read-hobbies")
    return render(request, "firstApp/form.html", {"form": form})


def readHobbies(request):
    hobbies = Hobby.objects.all()
    return render(request, "firstApp/hobby.html", {"hobbies": hobbies})


def readHobby(request, pk):
    hobby = get_object_or_404(Hobby, id=pk)
    return render(request, "firstApp/hobby.html", {"hobby": hobby})


def updateHobby(request, pk):
    hobby = get_object_or_404(Hobby, id=pk)
    form = HobbyForm(instance=hobby)
    if request.method == "POST":
        form = HobbyForm(request.POST, instance=hobby)
        if form.is_valid():
            form.save()
            return redirect("read-hobbies")
    return render(request, "firstApp/form.html", {"form": form})


def deleteHobby(request, pk):
    hobby = Hobby.objects.get(id=pk)
    hobby.delete()
    return redirect("read-hobbies")
