from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from .models import ChildrenHome, HomeRegistration, HomecareProfile


@transaction.atomic
def approve_home_registration(registration_id):
    registration = HomeRegistration.objects.select_for_update().get(pk=registration_id)
    user = get_user_model().objects.select_for_update().filter(
        pk=registration.applicant_id
    ).first()
    if user is None:
        raise ValidationError(
            {'applicant': 'Select an existing organization account before approval.'}
        )
    if user.is_staff:
        raise ValidationError(
            {'applicant': 'Staff accounts cannot be assigned as organization accounts.'}
        )

    registration.status = 'approved'
    registration.full_clean()
    registration.save(update_fields=['status', 'updated_at'])

    profile = HomecareProfile.objects.select_for_update().filter(user=user).first()
    if profile and (
        profile.role != 'organization'
        or (registration.home_id and profile.home_id != registration.home_id)
    ):
        raise ValidationError(
            {'applicant': 'This account already has a conflicting workspace profile.'}
        )

    if registration.home_id:
        home = ChildrenHome.objects.select_for_update().get(pk=registration.home_id)
        if not home.is_verified:
            home.is_verified = True
            home.save(update_fields=['is_verified', 'updated_at'])
    else:
        base_slug = slugify(registration.name) or 'organization'
        slug = base_slug
        suffix = 2
        while ChildrenHome.objects.filter(slug=slug).exists():
            slug = f'{base_slug}-{suffix}'
            suffix += 1

        home = ChildrenHome.objects.create(
            name=registration.name,
            slug=slug,
            location=registration.location,
            capacity=0,
            descripttion=registration.description,
            image='',
            website_url=registration.website_url or None,
            phone_number=registration.phone_number or None,
            email=registration.email,
            is_verified=True,
        )
        registration.home = home
        registration.save(update_fields=['home', 'updated_at'])

    if profile is None:
        HomecareProfile.objects.create(user=user, role='organization', home=home)
    elif profile.home_id != home.pk:
        profile.home = home
        profile.save(update_fields=['home'])

    return home
