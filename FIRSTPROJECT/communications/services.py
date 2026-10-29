import logging
import os

import africastalking

logger = logging.getLogger(__name__)


def initialize_at():
    username = os.getenv('AT_USERNAME', 'sandbox')
    api_key = os.getenv('AT_API_KEY', '')

    if not api_key or api_key == 'your_africastalking_api_key_here':
        logger.warning("Africa's Talking API key is not set. SMS sending is disabled.")
        return None

    africastalking.initialize(username, api_key)
    return africastalking


def send_sms(phone_number: str, message: str, sender_id: str | None = None) -> dict:
    at = initialize_at()
    if at is None:
        return {
            'status': 'disabled',
            'message': "Africa's Talking is not configured.",
            'provider': 'africastalking',
        }

    sender = sender_id or os.getenv('AT_SENDER_ID', 'HomeCareKenya')
    sms = at.SMS

    try:
        response = sms.send({
            'to': [phone_number],
            'message': message,
            'from': sender,
        })
        logger.info("Africa's Talking SMS sent: %s", response)
        return {
            'status': 'sent',
            'provider': 'africastalking',
            'response': response,
        }
    except Exception as exc:  # pragma: no cover - service integration path
        logger.exception("Failed to send SMS via Africa's Talking")
        return {
            'status': 'failed',
            'provider': 'africastalking',
            'error': str(exc),
        }
