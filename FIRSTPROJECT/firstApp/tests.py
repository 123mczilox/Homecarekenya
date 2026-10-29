from django.test import TestCase
from django.test import override_settings
from unittest.mock import patch

from .backend_api import BackendAPIError
from .models import ChildrenHome


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

        response = self.client.get(f"/homes/{home.slug}/")

        self.assertContains(response, "Sample Profile Home")
        self.assertContains(response, "Children's names, personal histories")
        self.assertNotContains(response, "50 children")

    def test_fairmatch_page_uses_weighted_recommendation(self):
        response = self.client.get("/fairmatch/")

        self.assertContains(response, "76.0")
        self.assertContains(response, "40.0 books")
        self.assertContains(response, "Review required")

    def test_contribution_preview_does_not_claim_payment(self):
        response = self.client.post("/donations/", {"resource_type": "money"})

        self.assertContains(response, "Nothing was submitted, saved or charged")

    def test_booking_form_saves_to_backend(self):
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
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Request preview created")
        self.assertTrue(home.booking_requests.exists())

    def test_foodbridge_form_saves_to_backend(self):
        response = self.client.post(
            "/foodbridge/",
            {
                "food_name": "Fresh produce boxes",
                "category": "fresh_produce",
                "quantity": "18",
                "unit": "boxes",
                "location": "Nairobi central",
                "collection_window": "Tuesday 10:00-12:00",
                "expiry_date": "2026-11-20",
                "handling": "Keep chilled until collection.",
                "food_safety_confirmed": "true",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Preview only")
