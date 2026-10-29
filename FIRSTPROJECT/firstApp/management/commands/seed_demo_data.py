from django.core.management.base import BaseCommand

from firstApp.models import ChildrenHome, Donor, HomeNeed, ResourceOffer


class Command(BaseCommand):
    help = "Seed a small demo dataset for the pitch prototype"

    def handle(self, *args, **options):
        donor, _ = Donor.objects.get_or_create(
            email="donor@example.com",
            defaults={
                "full_name": "Grace Wanjiru",
                "phone_number": "+254700123456",
                "organization_name": "Community Care Collective",
                "location": "Nairobi",
            },
        )

        home_1, _ = ChildrenHome.objects.get_or_create(
            slug="tumaini-learning-centre",
            defaults={
                "name": "Tumaini Learning Centre",
                "location": "Nakuru",
                "capacity": 40,
                "descripttion": "A nurturing learning home supporting children through safety, education and mentorship.",
                "image": "",
                "email": "info@tumaini.example",
                "is_verified": True,
                "is_urgent": True,
            },
        )

        home_2, _ = ChildrenHome.objects.get_or_create(
            slug="upendo-children-centre",
            defaults={
                "name": "Upendo Children's Centre",
                "location": "Kiambu",
                "capacity": 35,
                "descripttion": "A community-led home connecting children to care, nutrition and school readiness.",
                "image": "",
                "email": "hello@upendo.example",
                "is_verified": True,
                "is_urgent": False,
            },
        )

        HomeNeed.objects.update_or_create(
            home=home_1,
            resource_type="exercise books",
            defaults={
                "quantity_requested": 120,
                "quantity_fulfilled": 64,
                "urgency": 4,
                "deadline": "2026-11-15",
                "verification_status": "verified",
                "delivery_feasible": True,
                "storage_capacity_available": True,
                "unit": "books",
                "notes": "Learning materials for the school term.",
            },
        )

        HomeNeed.objects.update_or_create(
            home=home_2,
            resource_type="food staples",
            defaults={
                "quantity_requested": 40,
                "quantity_fulfilled": 18,
                "urgency": 3,
                "deadline": "2026-11-05",
                "verification_status": "verified",
                "delivery_feasible": True,
                "storage_capacity_available": True,
                "unit": "bags",
                "notes": "Dry food staples for the kitchen and meal plan.",
            },
        )

        ResourceOffer.objects.update_or_create(
            donor=donor,
            resource_type="exercise books",
            defaults={
                "quantity_available": 50,
                "unit": "books",
                "expiry_date": None,
                "collection_location": "Nairobi CBD",
                "available_until": None,
                "safety_status": "approved",
                "availability_status": "available",
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))
