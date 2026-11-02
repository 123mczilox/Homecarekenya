from datetime import timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.test import RequestFactory, TestCase
from django.test import override_settings
from django.utils import timezone

from .backend_api import BackendAPIError
from .admin import FoodBridgeListingAdmin, HomeRegistrationAdmin
from .models import (
    Allocation,
    BookingRequest,
    ChildrenHome,
    CommunityEvent,
    ContributionPledge,
    EventSmsSubscriber,
    FoodBridgeListing,
    HomeNeed,
    HomecareProfile,
    HomeRegistration,
    ResourceOffer,
)
from .matching import sync_foodbridge_resource_offer
from .registration_workflow import approve_home_registration


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
            "/login/",
            "/needs/",
        ]

        for page in pages:
            with self.subTest(page=page):
                response = self.client.get(page)
                self.assertEqual(response.status_code, 200)

    def test_workspaces_require_a_signed_in_role(self):
        for path in [
            "/homed/",
            "/platform-dashboard/",
            "/donor-dashboard/",
            "/supplier-dashboard/",
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertRedirects(response, f"/login/?next={path}")

    def test_staff_dashboard_uses_live_review_counts(self):
        User = get_user_model()
        staff_user = User.objects.create_user(
            username="operations",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(staff_user)
        HomeRegistration.objects.create(
            name="Pending organization",
            location="Nairobi",
            email="pending@example.test",
            description="Waiting for review.",
            verification_acknowledged=True,
        )
        home = ChildrenHome.objects.create(
            name="Unpublished need home",
            slug="unpublished-need-home",
            location="Nairobi",
            capacity=20,
            descripttion="A verified home with an unpublished need.",
            image="",
            email="home@example.test",
            is_verified=True,
        )
        HomeNeed.objects.create(
            home=home,
            resource_type="Needs publication",
            verification_status="verified",
            is_published=False,
        )

        response = self.client.get("/platform-dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Organization applications")
        self.assertNotContains(response, "/admin/firstApp/homeregistration/")
        self.assertNotContains(response, "Demonstration data")
        self.assertEqual(response.context["pending_registrations"], 1)
        self.assertEqual(response.context["pending_needs"], 1)

    def test_organization_dashboard_and_need_form_are_scoped_to_linked_verified_home(self):
        User = get_user_model()
        own_home = ChildrenHome.objects.create(
            name="Linked Verified Home",
            slug="linked-verified-home",
            location="Nairobi",
            capacity=20,
            descripttion="A verified home.",
            image="",
            email="linked@example.test",
            is_verified=True,
        )
        other_home = ChildrenHome.objects.create(
            name="Other Verified Home",
            slug="other-verified-home",
            location="Kiambu",
            capacity=20,
            descripttion="Another verified home.",
            image="",
            email="other@example.test",
            is_verified=True,
        )
        HomeNeed.objects.create(home=own_home, resource_type="Linked request")
        HomeNeed.objects.create(home=other_home, resource_type="Private other request")
        user = User.objects.create_user(username="home-team", password="test-password")
        HomecareProfile.objects.create(user=user, role="organization", home=own_home)
        self.client.force_login(user)

        dashboard_response = self.client.get("/homed/")
        needs_response = self.client.get("/needs/")

        self.assertContains(dashboard_response, "Linked Verified Home")
        self.assertContains(dashboard_response, "Linked request")
        self.assertNotContains(dashboard_response, "Private other request")
        self.assertContains(needs_response, "Linked Verified Home")
        self.assertNotContains(needs_response, "Other Verified Home")

    def test_organization_profile_cannot_link_unverified_home(self):
        User = get_user_model()
        home = ChildrenHome.objects.create(
            name="Unverified Home",
            slug="unverified-home",
            location="Nairobi",
            capacity=20,
            descripttion="Not yet verified.",
            image="",
            email="unverified@example.test",
        )
        user = User.objects.create_user(username="unverified-team", password="test-password")
        profile = HomecareProfile(user=user, role="organization", home=home)

        with self.assertRaises(ValidationError):
            profile.full_clean()

    @override_settings(HOMECARE_API_BASE_URL="https://api.example.test")
    def test_authenticated_donor_pledges_are_saved_locally_and_scoped(self):
        User = get_user_model()
        donor = User.objects.create_user(username="donor-one", password="test-password")
        other_user = User.objects.create_user(username="donor-two", password="test-password")
        HomecareProfile.objects.create(user=donor, role="donor")
        self.client.force_login(donor)
        with patch("firstApp.views.send_sms", return_value={"status": "sent"}):
            form_response = self.client.get("/donations/")
            post_response = self.client.post(
                "/donations/",
                {
                    "resource_type": "money",
                    "direction": "fairmatch",
                    "description": "My account pledge",
                    "quantity": "KES 500",
                    "donor_name": "Donor One",
                    "email": "donor@example.test",
                    "pledge_acknowledged": "true",
                },
                follow=True,
            )
        ContributionPledge.objects.create(
            resource_type="supplies",
            direction="fairmatch",
            description="Other account pledge",
            quantity="1 box",
            donor_name="Donor Two",
            email="other@example.test",
            pledge_acknowledged=True,
            submitted_by=other_user,
        )
        dashboard_response = self.client.get("/donor-dashboard/")

        self.assertNotContains(form_response, 'data-api-endpoint="/api/v1/contributions/"')
        self.assertContains(post_response, "pledge is saved")
        self.assertEqual(
            ContributionPledge.objects.get(description="My account pledge").submitted_by,
            donor,
        )
        self.assertContains(dashboard_response, "My account pledge")
        self.assertNotContains(dashboard_response, "Other account pledge")

    def test_authenticated_supplier_offers_are_scoped_to_account(self):
        User = get_user_model()
        supplier = User.objects.create_user(username="supplier-one", password="test-password")
        other_user = User.objects.create_user(username="supplier-two", password="test-password")
        HomecareProfile.objects.create(user=supplier, role="supplier")
        self.client.force_login(supplier)
        response = self.client.post(
            "/foodbridge/",
            {
                "food_name": "My account produce",
                "category": "fresh_produce",
                "contact_name": "Supplier One",
                "contact_email": "supplier@example.test",
                "quantity": "12",
                "unit": "boxes",
                "location": "Nairobi",
                "collection_window": "Tomorrow morning",
                "expiry_date": "2026-11-20",
                "handling": "Keep chilled.",
                "food_safety_confirmed": "true",
            },
            follow=True,
        )
        FoodBridgeListing.objects.create(
            food_name="Other account offer",
            category="dry_goods",
            quantity=8,
            unit="bags",
            location="Kiambu",
            collection_window="Tomorrow",
            expiry_date="2026-11-20",
            submitted_by=other_user,
        )
        dashboard_response = self.client.get("/supplier-dashboard/")

        self.assertContains(response, "FoodBridge offer is saved")
        self.assertEqual(
            FoodBridgeListing.objects.get(food_name="My account produce").submitted_by,
            supplier,
        )
        self.assertContains(dashboard_response, "My account produce")
        self.assertNotContains(dashboard_response, "Other account offer")

    def test_role_cannot_open_another_role_dashboard_or_legacy_crud(self):
        User = get_user_model()
        donor = User.objects.create_user(username="role-donor", password="test-password")
        HomecareProfile.objects.create(user=donor, role="donor")
        self.client.force_login(donor)

        self.assertEqual(self.client.get("/platform-dashboard/").status_code, 403)
        self.assertEqual(self.client.get("/read-donors/").status_code, 403)

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

    def test_fairmatch_page_has_no_mock_recommendations(self):
        response = self.client.get("/fairmatch/")

        self.assertContains(response, "No approved offers are currently available.")
        self.assertNotContains(response, "Tumaini Learning Centre")

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

    def test_authenticated_home_registration_is_linked_and_dashboard_approval_creates_workspace(self):
        User = get_user_model()
        applicant = User.objects.create_user(
            username="organization-applicant",
            email="office@example.test",
        )
        staff_user = User.objects.create_superuser(
            username="organization-reviewer",
            email="reviewer@example.test",
            password="test-password",
        )
        self.client.force_login(applicant)
        self.client.post(
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
        )
        registration = HomeRegistration.objects.get()
        self.assertEqual(registration.applicant, applicant)

        self.client.force_login(staff_user)
        response = self.client.post(
            f"/platform-dashboard/organizations/{registration.pk}/approve/",
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        registration.refresh_from_db()
        home = registration.home
        self.assertEqual(registration.status, "approved")
        self.assertTrue(home.is_verified)
        self.assertEqual(home.email, registration.email)
        profile = HomecareProfile.objects.get(user=applicant)
        self.assertEqual(profile.role, "organization")
        self.assertEqual(profile.home, home)

        self.client.force_login(applicant)
        dashboard_response = self.client.get("/homed/")
        self.assertEqual(dashboard_response.context["home"].name, "Hope Children's Home")

    def test_home_registration_admin_approval_creates_workspace_and_is_idempotent(self):
        User = get_user_model()
        applicant = User.objects.create_user(
            username="admin-linked-applicant",
            email="admin-applicant@example.test",
        )
        staff_user = User.objects.create_superuser(
            username="admin-reviewer",
            email="admin-reviewer@example.test",
            password="test-password",
        )
        registration = HomeRegistration.objects.create(
            name="Hope Children's Home",
            location="Nairobi",
            email="admin-applicant@example.test",
            description="Community care and education.",
            verification_acknowledged=True,
            applicant=applicant,
        )
        registration.status = "approved"
        model_admin = HomeRegistrationAdmin(HomeRegistration, admin.site)

        model_admin.save_model(
            RequestFactory().post("/admin/firstApp/homeregistration/"),
            registration,
            form=None,
            change=True,
        )
        first_home_id = registration.home_id
        model_admin.save_model(
            RequestFactory().post("/admin/firstApp/homeregistration/"),
            registration,
            form=None,
            change=True,
        )

        registration.refresh_from_db()
        self.assertEqual(registration.home_id, first_home_id)
        self.assertEqual(ChildrenHome.objects.filter(name="Hope Children's Home").count(), 1)
        self.assertEqual(HomecareProfile.objects.get(user=applicant).home_id, first_home_id)

    def test_home_registration_cannot_be_approved_without_an_assigned_account(self):
        registration = HomeRegistration(
            name="Unlinked Organization",
            location="Nairobi",
            email="unlinked@example.test",
            description="An application without an account.",
            verification_acknowledged=True,
            status="approved",
        )

        with self.assertRaises(ValidationError):
            registration.full_clean()

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


class FairMatchIntegrationTests(TestCase):
    def setUp(self):
        self.home = ChildrenHome.objects.create(
            name="Verified Food Home",
            slug="verified-food-home",
            location="Nairobi",
            capacity=40,
            descripttion="A verified home with current food needs.",
            image="",
            email="home@example.test",
            is_verified=True,
        )

    def make_need(self, **overrides):
        defaults = {
            "home": self.home,
            "category": "food",
            "resource_type": "Maize flour",
            "quantity_requested": 10,
            "quantity_fulfilled": 0,
            "urgency": 5,
            "verification_status": "verified",
            "is_published": True,
            "delivery_feasible": True,
            "storage_capacity_available": True,
            "unit": "kg",
        }
        defaults.update(overrides)
        return HomeNeed.objects.create(**defaults)

    def make_listing(self, **overrides):
        defaults = {
            "food_name": "Maize flour",
            "category": "dry_goods",
            "contact_name": "Supplier",
            "contact_email": "supplier@example.test",
            "quantity": 7,
            "unit": "kg",
            "location": "Nairobi",
            "collection_window": "Tomorrow morning",
            "expiry_date": timezone.localdate() + timedelta(days=5),
            "handling": "Keep sealed and dry.",
            "food_safety_confirmed": True,
        }
        defaults.update(overrides)
        return FoodBridgeListing.objects.create(**defaults)

    def make_staff(self):
        user = get_user_model().objects.create_user(
            username="fairmatch-coordinator",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(user)
        return user

    def test_foodbridge_submission_creates_a_pending_offer_not_visible_to_matching(self):
        response = self.client.post(
            "/foodbridge/",
            {
                "food_name": "Maize flour",
                "category": "dry_goods",
                "contact_name": "Supplier",
                "contact_email": "supplier@example.test",
                "quantity": "7",
                "unit": "kg",
                "location": "Nairobi",
                "collection_window": "Tomorrow morning",
                "expiry_date": (timezone.localdate() + timedelta(days=5)).isoformat(),
                "handling": "Keep sealed and dry.",
                "food_safety_confirmed": "true",
            },
            follow=True,
        )

        listing = FoodBridgeListing.objects.get()
        offer = ResourceOffer.objects.get(foodbridge_listing=listing)
        self.assertContains(response, "saved for coordinator review")
        self.assertEqual(offer.resource_type, "Maize flour")
        self.assertEqual(offer.quantity_available, 7)
        self.assertEqual(offer.safety_status, "pending")
        self.assertEqual(offer.availability_status, "cancelled")
        self.assertNotContains(self.client.get("/fairmatch/"), "Maize flour")

    def test_fairmatch_renders_recommendations_from_approved_database_records(self):
        self.make_need()
        listing = self.make_listing(status="approved")
        offer = sync_foodbridge_resource_offer(listing)

        response = self.client.get("/fairmatch/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maize flour")
        self.assertContains(response, "Verified Food Home")
        self.assertContains(response, "100.0/100")
        self.assertNotContains(response, "Tumaini Learning Centre")
        self.assertEqual(offer.foodbridge_listing, listing)

    def test_confirmed_fairmatch_delivery_updates_need_offer_and_allocation(self):
        need = self.make_need(quantity_requested=10)
        listing = self.make_listing(status="approved")
        offer = sync_foodbridge_resource_offer(listing)
        self.make_staff()

        response = self.client.post(
            f"/fairmatch/allocate/{offer.pk}/{need.pk}/",
            follow=True,
        )

        need.refresh_from_db()
        offer.refresh_from_db()
        allocation = Allocation.objects.get(resource_offer=offer, need=need)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recorded delivery of 7.0 kg")
        self.assertEqual(allocation.status, "delivered")
        self.assertEqual(allocation.quantity_allocated, 7)
        self.assertEqual(need.quantity_fulfilled, 7)
        self.assertEqual(offer.quantity_available, 0)
        self.assertEqual(offer.availability_status, "reserved")

        self.client.post(f"/fairmatch/allocate/{offer.pk}/{need.pk}/")
        self.assertEqual(Allocation.objects.filter(resource_offer=offer, need=need).count(), 1)

    def test_allocation_converts_offer_units_to_need_units(self):
        need = self.make_need(quantity_requested=3000, unit="g")
        listing = self.make_listing(quantity=2, unit="kg", status="approved")
        offer = sync_foodbridge_resource_offer(listing)
        self.make_staff()

        self.client.post(f"/fairmatch/allocate/{offer.pk}/{need.pk}/")

        need.refresh_from_db()
        offer.refresh_from_db()
        allocation = Allocation.objects.get(resource_offer=offer, need=need)
        self.assertEqual(allocation.quantity_allocated, 2)
        self.assertEqual(need.quantity_fulfilled, 2000)
        self.assertEqual(offer.quantity_available, 0)

    def test_admin_approval_makes_confirmed_food_offer_matchable(self):
        listing = self.make_listing()
        offer = sync_foodbridge_resource_offer(listing)
        staff_user = self.make_staff()
        listing.status = "approved"
        request = RequestFactory().post("/admin/firstApp/foodbridgelisting/")
        request.user = staff_user

        FoodBridgeListingAdmin(FoodBridgeListing, admin.site).save_model(
            request,
            listing,
            form=None,
            change=True,
        )

        offer.refresh_from_db()
        self.assertEqual(offer.safety_status, "approved")
        self.assertEqual(offer.availability_status, "available")

    def test_fairmatch_allocation_requires_staff_and_current_eligibility(self):
        need = self.make_need()
        listing = self.make_listing(status="approved")
        offer = sync_foodbridge_resource_offer(listing)
        response = self.client.post(f"/fairmatch/allocate/{offer.pk}/{need.pk}/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Allocation.objects.exists())

        self.make_staff()
        need.is_published = False
        need.save(update_fields=["is_published", "updated_at"])
        response = self.client.post(
            f"/fairmatch/allocate/{offer.pk}/{need.pk}/",
            follow=True,
        )
        self.assertContains(response, "no longer eligible")
        self.assertFalse(Allocation.objects.exists())

    def test_fairmatch_excludes_needs_at_unverified_homes(self):
        self.make_need()
        unverified_home = ChildrenHome.objects.create(
            name="Unverified Home",
            slug="unverified-food-home",
            location="Kiambu",
            capacity=20,
            descripttion="Not yet verified.",
            image="",
            email="unverified@example.test",
            is_verified=False,
        )
        self.make_need(home=unverified_home, resource_type="Maize flour")
        listing = self.make_listing(status="approved")
        sync_foodbridge_resource_offer(listing)

        response = self.client.get("/fairmatch/")

        self.assertContains(response, "Verified Food Home")
        self.assertNotContains(response, "Unverified Home")
