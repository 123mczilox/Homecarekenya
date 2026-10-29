import logging
import os

import africastalking

logger = logging.getLogger(__name__)


def initialize_at():
    username = os.getenv('AT_USERNAME')
    api_key = os.getenv('AT_API_KEY', '')

    if not api_key or api_key == 'your_africastalking_api_key_here':
        logger.warning("Africa's Talking API key is not set. SMS sending is disabled.")
        return None

    africastalking.initialize(username, api_key)
    return africastalking


def _normalize_recipients(recipients) -> list[str]:
    if recipients is None:
        return []
    if isinstance(recipients, str):
        return [item.strip() for item in recipients.replace(' ', '').split(',') if item.strip()]
    if isinstance(recipients, (list, tuple, set)):
        values = []
        for item in recipients:
            if item is None:
                continue
            values.extend(_normalize_recipients(str(item)))
        return values
    return [str(recipients).strip()]


def send_sms(recipients, message: str, sender_id: str | None = None) -> dict:
    at = initialize_at()
    if at is None:
        return {
            'status': 'disabled',
            'message': "Africa's Talking is not configured.",
            'provider': 'africastalking',
        }

    recipient_list = _normalize_recipients(recipients)
    if not recipient_list:
        return {
            'status': 'failed',
            'provider': 'africastalking',
            'error': 'No recipients were provided.',
        }

    sender = sender_id or os.getenv('AT_SENDER_ID', 'HomeCareKenya')
    sms_service = at.SMS

    try:
        response = sms_service.send(message, recipient_list, sender)
        logger.info("Africa's Talking SMS sent: %s", response)
        return {
            'status': 'sent',
            'provider': 'africastalking',
            'response': response,
            'recipients': recipient_list,
        }
    except Exception as exc:  # pragma: no cover - service integration path
        logger.exception("Failed to send SMS via Africa's Talking")
        return {
            'status': 'failed',
            'provider': 'africastalking',
            'error': str(exc),
            'recipients': recipient_list,
        }


def send_event_sms(recipients, event_title: str, event_details: str, event_date: str | None = None) -> dict:
    date_line = f" Date: {event_date}." if event_date else ""
    message = (
        f"HomeCare Kenya: {event_title}.{date_line} "
        f"More info: {event_details}"
    )
    return send_sms(recipients, message)


def send_donation_sms(recipients, donation_message: str) -> dict:
    message = f"HomeCare Kenya: {donation_message}"
    return send_sms(recipients, message)


def send_general_announcement(recipients, announcement: str) -> dict:
    message = f"HomeCare Kenya: {announcement}"
    return send_sms(recipients, message)
