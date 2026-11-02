from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('firstApp', '0010_bookingrequest_phone_number'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HomecareProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('organization', 'Organization'), ('donor', 'Donor'), ('supplier', 'Supplier')], max_length=20)),
                ('donor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='workspace_profiles', to='firstApp.donor')),
                ('home', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='workspace_profiles', to='firstApp.childrenhome')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='homecare_profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='contributionpledge',
            name='submitted_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contribution_pledges', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='foodbridgelisting',
            name='submitted_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='foodbridge_listings', to=settings.AUTH_USER_MODEL),
        ),
    ]
