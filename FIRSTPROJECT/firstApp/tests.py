from datetime import timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.management import call_command, CommandError
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone

from .backend_api import BackendAPIError
from .models import (
    BookingRequest,
    ChildrenHome,
    CommunityEvent,
    ContributionPledge,
    EventSmsSubscriber,
    FoodBridgeListing,
    HomeNeed,
    HomeRegistration,
)


class HomeCarePrototypeTests(TestCase):
    def test_public_pages_render(self):
        pages = [
            "/",
            "/find_homes/",
            "/donations/",
            "/bookings/",
            "/events/",
            "/fairmatch/",
            "/foodbridge/",
            "/register-home/",
            "/homed/",
            "/platform-dashboard/",
            "/needs/",
        ]

        for page in pages:
            with self.subTest(page=page):
                response = self.client.get(page)
                self.assertEqual(response.status_code, 200)

    def test_homepage_labels_demonstration_data(self):
        response = self.client.get("/")

        self.assertContains(response, "Demonstration data")
        self.assertContains(response, "FoodBridge")
        self.assertContains(response, "FairMatch")
        self.assertNotContains(response, "3,870")

    @override_settings(HOMECARE_API_BASE_URL="https://api.example.test")
    def test_api_origin_is_exposed_as_json_configuration(self):
        with patch("firstApp.views.get_public_homes", return_value=[]):
            response = self.client.get("/")

        self.assertContains(
            response,
            '<script id="homecare-api-config" type="application/json">"https://api.example.test"</script>',
            html=True,
        )
        self.assertContains(response, "/static/js/homecare-api.js")

    @override_settings(HOMECARE_API_BASE_URL="https://api.example.test")
    def test_homepage_uses_configured_api_without_local_fallback(self):
        api_homes = [
            {
                "slug": "sample-api-home",
                "name": "Sample API Home",
                "location": "Nairobi",
                "descripttion": "A public sample profile.",
                "is_verified": True,
            }
        ]
        with patch(
            "firstApp.views.get_public_homes", return_value=api_homes
        ) as get_homes:
            response = self.client.get("/")

        self.assertContains(response, "Sample API Home")
        get_homes.assert_called_once_with({"verification": "verified"})

    @override_settings(HOMECARE_API_BASE_URL="https://api.example.test")
    def test_api_failure_returns_service_unavailable(self):
        with patch(
            "firstApp.views.get_public_homes",
            side_effect=BackendAPIError("offline"),
        ):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 503)
        self.assertContains(
            response, "Service temporarily unavailable", status_code=503
        )

    def test_contribution_form_has_versioned_api_endpoint(self):
        response = self.client.get("/donations/")

        self.assertContains(response, 'data-api-endpoint="/api/v1/contributions/"')
        self.assertContains(response, "data-form-feedback")

    def test_directory_filters_saved_homes(self):
        ChildrenHome.objects.create(
            name="Sample Nairobi Home",
            slug="sample-nairobi-home",
            location="Nairobi",
            capacity=30,
            descripttion="A sample organization for directory tests.",
            image="",
            email="sample@example.test",
            is_verified=True,
        )
        ChildrenHome.objects.create(
            name="Sample Nakuru Home",
            slug="sample-nakuru-home",
            location="Nakuru",
            capacity=24,
            descripttion="Another sample organization for directory tests.",
            image="",
            email="nakuru@example.test",
        )

        response = self.client.get(
            "/find_homes/?q=Sample&county=Nairobi&verification=verified"
        )

        self.assertContains(response, "Sample Nairobi Home")
        self.assertNotContains(response, "Sample Nakuru Home")

    def test_registered_home_profile_renders_without_child_records(self):
        home = ChildrenHome.objects.create(
            name="Sample Profile Home",
            slug="sample-profile-home",
            location="Nairobi",
            capacity=20,
            descripttion="A sample organization profile.",
            image="",
            email="profile@example.test",
            is_verified=True,
        )
        HomeNeed.objects.create(
            home=home,
            category="school_supplies",
            resource_type="Exercise books",
            quantity_requested=12,
            unit="books",
            verification_status="verified",
            is_published=True,
        )

        response = self.client.get(f"/homes/{home.slug}/")

        self.assertContains(response, "Sample Profile Home")
        self.assertContains(response, "12.00 books remaining")
        self.assertContains(response, "Exercise books")
        self.assertContains(response, "Children's names, personal histories")
        self.assertNotContains(response, "50 children")

    def test_fairmatch_page_uses_weighted_recommendation(self):
        response = self.client.get("/fairmatch/")

        self.assertContains(response, "76.0")
        self.assertContains(response, "40.0 books")
        self.assertContains(response, "Review required")

    @patch("firstApp.views.send_sms", return_value={"status": "sent"})
    def test_contribution_form_persists_a_pending_pledge(self, _mock_send_sms):
        home = ChildrenHome.objects.create(
            name="Sample Pledge Home",
            slug="sample-pledge-home",
            location="Nairobi",
            capacity=20,
            descripttion="A verified organization for pledge tests.",
            image="",
            email="home@example.test",
            is_verified=True,
        )
        need = HomeNeed.objects.create(
            home=home,
            category="school_supplies",
            resource_type="Exercise books",
            quantity_requested=50,
            unit="books",
            verification_status="verified",
            is_published=True,
        )
        response = self.client.post(
            "/donations/",
            {
                "resource_type": "money",
                "direction": "need",
                "need": str(need.pk),
                "description": "Support school supplies",
                "quantity": "KES 2,000",
                "donor_name": "Amina Wanjiku",
                "email": "amina@example.test",
                "pledge_acknowledged": "true",
            },
        )

        if response.status_code != 302:
            self.fail(f"Contribution form errors: {response.context['form'].errors.as_data()}")
        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "contribution pledge is saved")
        self.assertContains(response, "No payment has been processed")
        pledge = ContributionPledge.objects.get()
        self.assertEqual(pledge.status, "pending_review")
        self.assertEqual(pledge.quantity, "KES 2,000")
        self.assertEqual(pledge.need, need)

    @patch.dict("os.environ", {"COORDINATOR_PHONE": "+254700000002"})
    @patch("firstApp.views.send_sms", return_value={"status": "sent"})
    def test_contribution_pledge_sends_sms_to_coordinator_and_consented_donor(
        self, mock_send_sms
    ):
        response = self.client.post(
            "/donations/",
            {
                "resource_type": "money",
                "direction": "fairmatch",
                "description": "School supplies",
                "quantity": "KES 2,000",
                "donor_name": "Amina Wanjiku",
                "email": "amina@example.test",
                "phone_number": "+254700000001",
                "sms_consent": "true",
                "pledge_acknowledged": "true",
            },
        )

        self.assertEqual(response.status_code, 302)
        pledge = ContributionPledge.objects.get()
        self.assertEqual(pledge.phone_number, "+254700000001")
        self.assertTrue(pledge.sms_consent)
        self.assertEqual(mock_send_sms.call_count, 2)
        self.assertEqual(mock_send_sms.call_args_list[0].args[0], ["+254700000002"])
        self.assertEqual(mock_send_sms.call_args_list[1].args[0], ["+254700000001"])

    @patch.dict("os.environ", {"COORDINATOR_PHONE": "+254700000002"})
    @patch("firstApp.views.send_sms", return_value={"status": "sent"})
    def test_donor_without_sms_consent_only_triggers_coordinator_alert(
        self, mock_send_sms
    ):
        response = self.client.post(
            "/donations/",
            {
                "resource_type": "food",
                "direction": "fairmatch",
                "description": "Rice",
                "quantity": "10 bags",
                "donor_name": "Amina Wanjiku",
                "email": "amina@example.test",
                "phone_number": "+254700000001",
                "pledge_acknowledged": "true",
            },
        )

        self.assertEqual(response.status_code, 302)
        pledge = ContributionPledge.objects.get()
        self.assertFalse(pledge.sms_consent)
        mock_send_sms.assert_called_once()
        self.assertEqual(mock_send_sms.call_args.args[0], ["+254700000002"])

    @patch("firstApp.views.send_sms", return_value={"status": "sent"})
    def test_event_subscriber_requires_consent_and_valid_international_phone(
        self, mock_send_sms
    ):
        response = self.client.post(
            "/events/",
            {"phone_number": "+254700000001"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EventSmsSubscriber.objects.exists())

        response = self.client.post(
            "/events/",
            {"phone_number": "0700000001", "consent": "true"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EventSmsSubscriber.objects.exists())

        response = self.client.post(
            "/events/",
            {
                "action": "subscribe",
                "phone_number": "+254700000001",
                "consent": "true",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(EventSmsSubscriber.objects.get().is_active)
        mock_send_sms.assert_called_once()
        self.assertEqual(mock_send_sms.call_args.args[0], ["+254700000001"])
        self.assertIn("subscribed to event SMS reminders", mock_send_sms.call_args.args[1])

    @patch("firstApp.views.send_sms", return_value={"status": "sent"})
    def test_event_subscriber_can_unsubscribe(self, mock_send_sms):
        EventSmsSubscriber.objects.create(phone_number="+254700000001")

        response = self.client.post(
            "/events/",
            {"action": "unsubscribe", "phone_number": "+254700000001"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(EventSmsSubscriber.objects.get().is_active)
        mock_send_sms.assert_called_once_with(
            ["+254700000001"],
            "HomeCare Kenya: You have unsubscribed from event SMS reminders.",
        )

    @patch("firstApp.views.send_sms", return_value={"status": "sent"})
    def test_unknown_number_unsubscribe_does_not_send_sms(self, mock_send_sms):
        response = self.client.post(
            "/events/",
            {"action": "unsubscribe", "phone_number": "+254700000001"},
        )

        self.assertEqual(response.status_code, 302)
        mock_send_sms.assert_not_called()

    @patch("firstApp.views.send_sms", return_value={"status": "disabled"})
    def test_subscription_saved_when_confirmation_sms_fails(self, _mock_send_sms):
        response = self.client.post(
            "/events/",
            {
                "action": "subscribe",
                "phone_number": "+254700000001",
                "consent": "true",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(EventSmsSubscriber.objects.get().is_active)
        self.assertContains(response, "You remain subscribed")

    def test_event_page_only_displays_published_upcoming_events(self):
        local_event_date = timezone.localdate(timezone=ZoneInfo("Africa/Nairobi"))
        upcoming = CommunityEvent.objects.create(
            title="Upcoming community day",
            details="A public community event.",
            event_date=local_event_date + timedelta(days=4),
            location="Nairobi",
            is_published=True,
        )
        CommunityEvent.objects.create(
            title="Unpublished event",
            details="Not public.",
            event_date=local_event_date + timedelta(days=5),
            location="Nairobi",
        )
        CommunityEvent.objects.create(
            title="Past event",
            details="Already happened.",
            event_date=local_event_date - timedelta(days=1),
            location="Nairobi",
            is_published=True,
        )

        response = self.client.get("/events/")

        self.assertContains(response, upcoming.title)
        self.assertNotContains(response, "Unpublished event")
        self.assertNotContains(response, "Past event")

    def test_ussd_home_menu_offers_events_visits_and_donations(self):
        response = self.client.post("/communications/ussd/", {"text": ""})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.decode().startswith("CON "))
        self.assertContains(response, "1. Upcoming events")
        self.assertContains(response, "2. Book a visit")
        self.assertContains(response, "3. Make a donation")

    def test_ussd_lists_only_published_upcoming_events(self):
        today = timezone.localdate(timezone=ZoneInfo("Africa/Nairobi"))
        CommunityEvent.objects.create(
            title="Upcoming public event",
            details="A public event.",
            event_date=today + timedelta(days=4),
            location="Nairobi",
            is_published=True,
        )
        CommunityEvent.objects.create(
            title="Private unpublished event",
            details="Not public.",
            event_date=today + timedelta(days=5),
            location="Nairobi",
        )

        response = self.client.post("/communications/ussd/", {"text": "1"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.decode().startswith("END "))
        self.assertContains(response, "Upcoming public event")
        self.assertNotContains(response, "Private unpublished event")

    @patch("communications.views.send_sms", return_value={"status": "sent"})
    def test_ussd_books_verified_home_and_notifies_home(self, mock_send_sms):
        home = ChildrenHome.objects.create(
            name="Sample USSD Home",
            slug="sample-ussd-home",
            location="Nairobi",
            capacity=20,
            descripttion="A verified home for USSD tests.",
            image="",
            phone_number="+254700000002",
            email="ussd-home@example.test",
            is_verified=True,
        )
        text = (
            "2*1*Jane Doe*2026-12-01*10:00 am*jane@example.test"
            "*2*Meet the organization*1"
        )

        response = self.client.post(
            "/communications/ussd/",
            {"text": text, "phoneNumber": "254700000001"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.decode().startswith("END "))
        self.assertContains(response, "Visit request saved for review")
        booking = BookingRequest.objects.get()
        self.assertEqual(booking.home, home)
        self.assertEqual(booking.visitor_name, "Jane Doe")
        self.assertEqual(booking.phone_number, "+254700000001")
        self.assertTrue(booking.visitor_conduct_accepted)
        mock_send_sms.assert_called_once()
        self.assertEqual(mock_send_sms.call_args.args[0], ["+254700000002"])

    @patch.dict("os.environ", {"COORDINATOR_PHONE": "+254700000002"})
    @patch("communications.views.send_sms", return_value={"status": "sent"})
    def test_ussd_records_donation_pledge_and_sends_sms_with_opt_in(
        self, mock_send_sms
    ):
        text = (
            "3*1*School supplies*10 boxes*Jane Doe*jane@example.test*1*1"
        )

        response = self.client.post(
            "/communications/ussd/",
            {"text": text, "phoneNumber": "+254700000001"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.decode().startswith("END "))
        self.assertContains(response, "Pledge saved for coordinator review")
        pledge = ContributionPledge.objects.get()
        self.assertEqual(pledge.resource_type, "money")
        self.assertEqual(pledge.description, "School supplies")
        self.assertEqual(pledge.phone_number, "+254700000001")
        self.assertTrue(pledge.sms_consent)
        self.assertEqual(mock_send_sms.call_count, 2)

    def test_ussd_donation_requires_final_confirmation(self):
        response = self.client.post(
            "/communications/ussd/",
            {
                "text": "3*2*Rice*10 bags*Jane Doe*jane@example.test*2*0",
                "phoneNumber": "+254700000001",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Donation pledge cancelled")
        self.assertFalse(ContributionPledge.objects.exists())

    def test_ussd_invalid_booking_consent_does_not_save_request(self):
        response = self.client.post(
            "/communications/ussd/",
            {
                "text": (
                    "2*1*Jane Doe*2026-12-01*10:00 am*jane@example.test"
                    "*2*Meet the organization*maybe"
                ),
                "phoneNumber": "+254700000001",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.decode().startswith("END "))
        self.assertFalse(BookingRequest.objects.exists())

    @patch(
        "firstApp.management.commands.send_event_reminders.send_event_sms",
        return_value={"status": "sent"},
    )
    def test_event_reminder_command_sends_once_three_days_before_event(
        self, mock_send_event_sms
    ):
        EventSmsSubscriber.objects.create(phone_number="+254700000001")
        event = CommunityEvent.objects.create(
            title="Community sports afternoon",
            details="Friendly games and lunch.",
            event_date=timezone.localdate(timezone=ZoneInfo("Africa/Nairobi"))
            + timedelta(days=3),
            event_time="10:00",
            location="Nairobi",
            is_published=True,
        )

        call_command("send_event_reminders")

        mock_send_event_sms.assert_called_once()
        self.assertEqual(
            mock_send_event_sms.call_args.args[0],
            ["+254700000001"],
        )
        event.refresh_from_db()
        self.assertIsNotNone(event.reminder_sent_at)
        call_command("send_event_reminders")
        mock_send_event_sms.assert_called_once()

    @patch(
        "firstApp.management.commands.send_event_reminders.send_event_sms",
        return_value={"status": "sent"},
    )
    def test_event_reminder_command_retries_events_within_three_day_window(
        self, mock_send_event_sms
    ):
        EventSmsSubscriber.objects.create(phone_number="+254700000001")
        event = CommunityEvent.objects.create(
            title="Reminder retry",
            details="A reminder whose scheduled run was missed.",
            event_date=timezone.localdate(timezone=ZoneInfo("Africa/Nairobi"))
            + timedelta(days=2),
            location="Nairobi",
            is_published=True,
        )

        call_command("send_event_reminders")

        mock_send_event_sms.assert_called_once()
        event.refresh_from_db()
        self.assertIsNotNone(event.reminder_sent_at)

    @patch(
        "firstApp.management.commands.send_event_reminders.send_event_sms",
        return_value={"status": "failed", "error": "Provider unavailable"},
    )
    def test_failed_event_reminder_is_reported_and_remains_retryable(
        self, mock_send_event_sms
    ):
        EventSmsSubscriber.objects.create(phone_number="+254700000001")
        event = CommunityEvent.objects.create(
            title="Community sports afternoon",
            details="Friendly games and lunch.",
            event_date=timezone.localdate(timezone=ZoneInfo("Africa/Nairobi"))
            + timedelta(days=3),
            location="Nairobi",
            is_published=True,
        )

        with self.assertRaises(CommandError):
            call_command("send_event_reminders")

        mock_send_event_sms.assert_called_once()
        event.refresh_from_db()
        self.assertIsNone(event.reminder_sent_at)

    def test_unpublished_need_is_not_offered_to_contributors(self):
        home = ChildrenHome.objects.create(
            name="Unpublished Need Home",
            slug="unpublished-need-home",
            location="Nairobi",
            capacity=20,
            descripttion="An unpublished organization need.",
            image="",
            email="home@example.test",
            is_verified=True,
        )
        HomeNeed.objects.create(
            home=home,
            resource_type="Unpublished sample request",
            quantity_requested=10,
            verification_status="verified",
            is_published=False,
        )

        response = self.client.get("/donations/")

        self.assertNotContains(response, "Unpublished sample request")

    def test_invalid_contribution_is_not_saved_and_shows_field_errors(self):
        response = self.client.post(
            "/donations/",
            {
                "resource_type": "money",
                "direction": "fairmatch",
                "description": "Support an outstanding need",
                "quantity": "KES 2,000",
                "donor_name": "Amina Wanjiku",
                "email": "amina@example.test",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pledge_acknowledged")
        self.assertFalse(ContributionPledge.objects.exists())

    def test_registration_form_persists_pending_organization_details(self):
        response = self.client.post(
            "/register-home/",
            {
                "name": "Hope Children's Home",
                "location": "Nairobi",
                "email": "office@example.test",
                "phone_number": "+254700000001",
                "website_url": "https://example.test",
                "description": "Community care and education.",
                "verification_acknowledged": "true",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "organization details are saved")
        registration = HomeRegistration.objects.get()
        self.assertEqual(registration.status, "pending_review")
        self.assertEqual(registration.email, "office@example.test")

    def test_need_submission_is_saved_pending_for_a_verified_home(self):
        home = ChildrenHome.objects.create(
            name="Sample Verified Home",
            slug="sample-verified-home",
            location="Nairobi",
            capacity=20,
            descripttion="A verified organization for need submission tests.",
            image="",
            email="home@example.test",
            is_verified=True,
        )
        response = self.client.post(
            "/needs/",
            {
                "home": str(home.pk),
                "title": "Exercise books",
                "category": "school_supplies",
                "quantity": "50",
                "unit": "books",
                "urgency": "4",
                "deadline": "2026-12-01",
                "storage_capacity_available": "true",
                "reason": "Books are needed for the new school term.",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your need is saved as pending")
        need = HomeNeed.objects.get()
        self.assertEqual(need.home, home)
        self.assertEqual(need.category, "school_supplies")
        self.assertEqual(need.resource_type, "Exercise books")
        self.assertEqual(need.verification_status, "pending")
        self.assertEqual(need.quantity_requested, 50)

    @patch("firstApp.views.send_sms")
    def test_booking_form_saves_to_backend_and_triggers_sms(self, mock_send_sms):
        home = ChildrenHome.objects.create(
            name="Sample Visit Home",
            slug="sample-visit-home",
            location="Nairobi",
            capacity=25,
            descripttion="A sample home for booking tests.",
            image="",
            email="visit@example.test",
            is_verified=True,
        )

        response = self.client.post(
            "/bookings/",
            {
                "home": str(home.pk),
                "date": "2026-12-01",
                "time": "morning",
                "visitor_count": "2",
                "visitor_name": "Jane Doe",
                "email": "jane@example.test",
                "purpose": "Meet the team and review programs.",
                "notes": "Please share a safety briefing.",
                "visitor_conduct_accepted": "true",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "visit request is saved")
        self.assertTrue(home.booking_requests.exists())
        self.assertEqual(home.booking_requests.get().status, "pending_review")
        mock_send_sms.assert_not_called()

    @patch("firstApp.views.send_sms")
    def test_foodbridge_form_saves_to_backend_and_triggers_sms(self, mock_send_sms):
        response = self.client.post(
            "/foodbridge/",
            {
                "food_name": "Fresh produce boxes",
                "category": "fresh_produce",
                "contact_name": "Nia Kamau",
                "contact_email": "nia@example.test",
                "quantity": "18",
                "unit": "boxes",
                "location": "Nairobi central",
                "collection_window": "Tuesday 10:00-12:00",
                "expiry_date": "2026-11-20",
                "handling": "Keep chilled until collection.",
                "food_safety_confirmed": "true",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FoodBridge offer is saved")
        listing = FoodBridgeListing.objects.get()
        self.assertEqual(listing.status, "pending_review")
        self.assertEqual(listing.contact_email, "nia@example.test")
        mock_send_sms.assert_not_called()
