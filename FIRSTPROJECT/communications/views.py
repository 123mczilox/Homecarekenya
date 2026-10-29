import logging
import os
import re
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import DatabaseError
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, csrf_protect, ensure_csrf_cookie
from zoneinfo import ZoneInfo

from .services import send_sms
from firstApp.models import BookingRequest, ChildrenHome, CommunityEvent, ContributionPledge

logger = logging.getLogger(__name__)
EVENT_TIME_ZONE = ZoneInfo("Africa/Nairobi")
E164_PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


@ensure_csrf_cookie
def test_sms(request):
    recipients = request.GET.get('to') or '+254700000000'
    message = request.GET.get('message') or "HomeCareKenya: test SMS from Africa's Talking"
    sender_id = request.GET.get('sender') or None

    result = send_sms(recipients, message, sender_id=sender_id)
    return JsonResponse(result)


@csrf_protect
def africastalking_webhook(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'ignored', 'method': request.method}, status=405)

    payload = request.POST or request.body.decode('utf-8', errors='ignore')
    return JsonResponse({
        'status': 'received',
        'provider': 'africastalking',
        'payload': payload,
    })


@csrf_exempt
def ussd_callback(request):
    if request.method != 'POST':
        return HttpResponse('END Method not allowed.', content_type='text/plain; charset=utf-8')

    phone_number = _normalize_ussd_phone(
        request.POST.get('phoneNumber') or request.GET.get('phoneNumber') or ''
    )
    text = (request.POST.get('text') or request.GET.get('text') or '').strip()
    parts = text.split('*') if text else []
    if any(len(part) > 300 for part in parts):
        return _ussd_response("END One of your answers was too long. Please try again.")

    try:
        response_text = _handle_ussd(parts, phone_number)
    except DatabaseError:
        logger.exception("USSD callback could not access application data")
        response_text = _ussd_response(
            "END The service is temporarily unavailable. Please try again later."
        )
    return HttpResponse(response_text, content_type='text/plain; charset=utf-8')


def _ussd_response(message: str, *, continue_session: bool = False) -> str:
    prefix = "CON" if continue_session else "END"
    return f"{prefix} {message}"


def _normalize_ussd_phone(phone_number: str) -> str:
    cleaned = re.sub(r"[\s()-]", "", phone_number)
    if cleaned.startswith("00"):
        cleaned = f"+{cleaned[2:]}"
    elif cleaned.startswith("254"):
        cleaned = f"+{cleaned}"
    elif cleaned.startswith("0"):
        cleaned = f"+254{cleaned[1:]}"
    if E164_PHONE_PATTERN.fullmatch(cleaned):
        return cleaned
    return ""


def _main_menu() -> str:
    return _ussd_response(
        "HomeCare Kenya\n1. Upcoming events\n2. Book a visit\n3. Make a donation\n0. Exit",
        continue_session=True,
    )


def _handle_ussd(parts: list[str], phone_number: str) -> str:
    if not parts:
        return _main_menu()
    if parts[0] == "0":
        return _ussd_response("Thank you for contacting HomeCare Kenya.")
    if parts[0] == "1":
        return _upcoming_events_response()
    if parts[0] == "2":
        return _booking_response(parts, phone_number)
    if parts[0] == "3":
        return _donation_response(parts, phone_number)
    return _ussd_response("Invalid option. Reply 1, 2, 3 or 0.", continue_session=True)


def _upcoming_events_response() -> str:
    today = timezone.localdate(timezone=EVENT_TIME_ZONE)
    events = CommunityEvent.objects.filter(
        is_published=True,
        event_date__gte=today,
    ).order_by("event_date", "event_time", "title")[:2]
    if not events:
        return _ussd_response("There are no upcoming published events. Please check again later.")

    details = [
        f"{event.event_date:%d %b}: {event.title[:38]} ({event.location[:24]})"
        for event in events
    ]
    return _ussd_response("Upcoming events\n" + "\n".join(details))


def _booking_response(parts: list[str], phone_number: str) -> str:
    if len(parts) == 1:
        homes = list(
            ChildrenHome.objects.filter(is_verified=True).order_by("name")[:3]
        )
        if not homes:
            return _ussd_response("No verified homes are available for visit requests right now.")
        lines = ["Choose a home:"]
        lines.extend(f"{index}. {home.name[:30]}" for index, home in enumerate(homes, 1))
        lines.append("0. Cancel")
        return _ussd_response("\n".join(lines), continue_session=True)

    if parts[1] == "0":
        return _ussd_response("Visit request cancelled.")

    try:
        home_index = int(parts[1])
    except ValueError:
        return _ussd_response("Invalid home choice. Dial again to restart.")
    homes = list(ChildrenHome.objects.filter(is_verified=True).order_by("name")[:3])
    if home_index < 1 or home_index > len(homes):
        return _ussd_response("That home choice is not available. Dial again to restart.")
    home = homes[home_index - 1]

    prompts = [
        "Enter your full name:",
        "Enter visit date as YYYY-MM-DD:",
        "Enter preferred visit time:",
        "Enter your email address:",
        "How many visitors? Enter a number from 1 to 20:",
        "What is the purpose of your visit?",
        "Do you agree to follow the host's visitor conduct and safety rules? 1. Yes 0. Cancel",
    ]
    answer_count = len(parts) - 2
    if answer_count > len(prompts):
        return _ussd_response("Invalid visit request. Dial again to restart.")
    if answer_count < len(prompts):
        return _ussd_response(prompts[answer_count], continue_session=True)

    _, _, visitor_name, visit_date, visit_time, email, visitor_count, purpose, consent = parts
    if consent == "0":
        return _ussd_response("Visit request cancelled.")
    if consent != "1":
        return _ussd_response("Invalid visitor-rules response. Dial again to restart.")
    if not phone_number:
        return _ussd_response("We could not verify your phone number. Please contact the organization.")
    if not visitor_name.strip():
        return _ussd_response("Your name is required. Dial again to restart.")
    try:
        parsed_date = date.fromisoformat(visit_date)
    except ValueError:
        return _ussd_response("Invalid date. Use YYYY-MM-DD and dial again.")
    if parsed_date < timezone.localdate(timezone=EVENT_TIME_ZONE):
        return _ussd_response("Visit date must be today or later. Dial again.")
    try:
        validate_email(email)
    except ValidationError:
        return _ussd_response("Invalid email address. Dial again and enter a valid email.")
    if not visit_time.strip() or len(visit_time) > 40:
        return _ussd_response("Enter a visit time of 40 characters or fewer. Dial again.")
    try:
        number_of_visitors = int(visitor_count)
    except ValueError:
        return _ussd_response("Visitor count must be a number from 1 to 20. Dial again.")
    if not 1 <= number_of_visitors <= 20:
        return _ussd_response("Visitor count must be a number from 1 to 20. Dial again.")
    if not purpose.strip():
        return _ussd_response("A visit purpose is required. Dial again.")

    BookingRequest.objects.create(
        home=home,
        date=parsed_date,
        time=visit_time.strip(),
        visitor_count=number_of_visitors,
        visitor_name=visitor_name.strip()[:150],
        phone_number=phone_number,
        email=email.strip(),
        purpose=purpose.strip(),
        visitor_conduct_accepted=True,
    )
    contact_phone = home.phone_number or os.environ.get("DEFAULT_CONTACT_PHONE", "").strip()
    if contact_phone:
        result = send_sms(
            [contact_phone],
            (
                f"HomeCare Kenya: New USSD visit request from {visitor_name.strip()[:60]} "
                f"for {home.name[:60]} on {parsed_date.isoformat()}. Review it in admin."
            ),
        )
        if result.get("status") != "sent":
            logger.warning(
                "USSD visit request saved, but notification SMS failed: %s",
                result.get("error") or result.get("message") or result.get("status"),
            )
    return _ussd_response("Visit request saved for review. It is not confirmed.")


def _donation_response(parts: list[str], phone_number: str) -> str:
    if len(parts) == 1:
        return _ussd_response(
            "Choose contribution:\n1. Money pledge\n2. Food\n3. Supplies\n0. Cancel",
            continue_session=True,
        )

    resource_types = {"1": "money", "2": "food", "3": "supplies"}
    resource_type = resource_types.get(parts[1])
    if parts[1] == "0":
        return _ussd_response("Donation pledge cancelled.")
    if not resource_type:
        return _ussd_response("Invalid choice. Reply 1, 2, 3 or 0.", continue_session=True)

    prompts = [
        "Describe your contribution:",
        "Enter the amount or quantity:",
        "Enter your full name:",
        "Enter your email address:",
        "Receive pledge SMS updates? 1. Yes 2. No",
        "This records a pledge only; no payment is taken. Submit? 1. Yes 0. Cancel",
    ]
    answer_count = len(parts) - 2
    if answer_count > len(prompts):
        return _ussd_response("Invalid donation pledge. Dial again to restart.")
    if answer_count < len(prompts):
        return _ussd_response(prompts[answer_count], continue_session=True)

    _, _, description, quantity, donor_name, email, sms_choice, confirmation = parts
    if confirmation == "0":
        return _ussd_response("Donation pledge cancelled.")
    if confirmation != "1":
        return _ussd_response("Invalid confirmation. No pledge was saved.")
    if not description.strip() or len(description) > 300:
        return _ussd_response("Contribution description is required. Dial again.")
    if not quantity.strip() or len(quantity) > 100:
        return _ussd_response("Amount or quantity is required. Dial again.")
    if not donor_name.strip():
        return _ussd_response("Your name is required. Dial again.")
    try:
        validate_email(email)
    except ValidationError:
        return _ussd_response("Invalid email address. Dial again and enter a valid email.")
    if sms_choice not in {"1", "2"}:
        return _ussd_response("Reply 1 for SMS updates or 2 to decline. Dial again.")

    pledge = ContributionPledge.objects.create(
        resource_type=resource_type,
        direction="fairmatch",
        description=description.strip(),
        quantity=quantity.strip(),
        donor_name=donor_name.strip()[:150],
        email=email.strip(),
        phone_number=phone_number,
        sms_consent=sms_choice == "1" and bool(phone_number),
        pledge_acknowledged=True,
    )
    notification_failures = []
    coordinator_phone = os.environ.get("COORDINATOR_PHONE", "").strip()
    if coordinator_phone:
        result = send_sms(
            [coordinator_phone],
            (
                f"HomeCare Kenya: New {pledge.get_resource_type_display()} pledge "
                f"from {pledge.donor_name}: {pledge.quantity} {pledge.description}. "
                "Review pending pledge in admin."
            ),
        )
        if result.get("status") != "sent":
            notification_failures.append("coordinator")
            logger.warning(
                "USSD donation pledge saved, but coordinator SMS failed: %s",
                result.get("error") or result.get("message") or result.get("status"),
            )
    else:
        notification_failures.append("coordinator")
        logger.warning("USSD donation pledge saved, but COORDINATOR_PHONE is not configured.")

    if pledge.sms_consent:
        result = send_sms(
            [pledge.phone_number],
            "HomeCare Kenya: Your contribution pledge is saved for coordinator review. No payment has been processed.",
        )
        if result.get("status") != "sent":
            notification_failures.append("donor")
            logger.warning(
                "USSD donation pledge saved, but donor SMS failed: %s",
                result.get("error") or result.get("message") or result.get("status"),
            )

    response = "Pledge saved for coordinator review. No payment was taken."
    if notification_failures:
        response += " SMS confirmation may not have been sent."
    return _ussd_response(response)
