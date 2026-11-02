from datetime import date

from django.db import migrations, models
import django.db.models.deletion


def link_existing_foodbridge_listings(apps, schema_editor):
    FoodBridgeListing = apps.get_model("firstApp", "FoodBridgeListing")
    ResourceOffer = apps.get_model("firstApp", "ResourceOffer")
    database = schema_editor.connection.alias

    for listing in FoodBridgeListing.objects.using(database).all().iterator():
        approved = listing.status == "approved" and listing.food_safety_confirmed
        available = approved and listing.expiry_date >= date.today()
        ResourceOffer.objects.using(database).create(
            donor=None,
            foodbridge_listing_id=listing.pk,
            resource_type=listing.food_name[:120],
            quantity_available=listing.quantity,
            unit=listing.unit[:20],
            expiry_date=listing.expiry_date,
            collection_location=listing.location[:200],
            available_until=listing.expiry_date,
            safety_status="approved" if approved else "pending",
            availability_status=(
                "available"
                if available
                else "delivered"
                if listing.status == "completed"
                else "cancelled"
            ),
        )


def unlink_foodbridge_listings(apps, schema_editor):
    ResourceOffer = apps.get_model("firstApp", "ResourceOffer")
    ResourceOffer.objects.using(schema_editor.connection.alias).filter(
        foodbridge_listing__isnull=False
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("firstApp", "0011_homecareprofile_submission_ownership"),
    ]

    operations = [
        migrations.AlterField(
            model_name="resourceoffer",
            name="donor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="resource_offers",
                to="firstApp.donor",
            ),
        ),
        migrations.AddField(
            model_name="resourceoffer",
            name="foodbridge_listing",
            field=models.OneToOneField(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="resource_offer",
                to="firstApp.foodbridgelisting",
            ),
        ),
        migrations.RunPython(
            link_existing_foodbridge_listings,
            unlink_foodbridge_listings,
        ),
    ]
