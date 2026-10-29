from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from communications.services import send_event_sms
from firstApp.models import CommunityEvent, EventSmsSubscriber

EVENT_TIME_ZONE = ZoneInfo("Africa/Nairobi")


class Command(BaseCommand):
    help = "Send SMS reminders for published events in the next three days."

    def handle(self, *args, **options):
        today = timezone.localdate(timezone=EVENT_TIME_ZONE)
        subscribers = list(
            EventSmsSubscriber.objects.filter(is_active=True).values_list(
                "phone_number", flat=True
            )
        )
        events = CommunityEvent.objects.filter(
            event_date__gt=today,
            event_date__lte=today + timedelta(days=3),
            is_published=True,
            reminder_sent_at__isnull=True,
        )

        if not events.exists():
            self.stdout.write("No published events are due for a reminder.")
            return
        if not subscribers:
            raise CommandError(
                "Events are due for reminders, but there are no active SMS subscribers."
            )

        failures = []
        for event in events:
            result = send_event_sms(
                subscribers,
                event.title,
                f"{event.details} Location: {event.location}.",
                event.event_date.isoformat(),
            )
            if result.get("status") != "sent":
                failures.append(event.title)
                self.stderr.write(
                    self.style.ERROR(
                        f"SMS reminder failed for {event.title}: "
                        f"{result.get('error') or result.get('message') or result}"
                    )
                )
                continue

            event.reminder_sent_at = timezone.now()
            event.save(update_fields=["reminder_sent_at", "updated_at"])
            self.stdout.write(self.style.SUCCESS(f"Reminder sent for {event.title}."))

        if failures:
            raise CommandError(
                f"Failed to send reminders for {len(failures)} event(s)."
            )
