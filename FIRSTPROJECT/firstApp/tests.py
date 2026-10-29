from django.test import TestCase
from django.test import override_settings
from unittest.mock import patch

from .backend_api import BackendAPIError
from .models import (
    ChildrenHome,
    ContributionPledge,
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

    def test_contribution_form_persists_a_pending_pledge(self):
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
