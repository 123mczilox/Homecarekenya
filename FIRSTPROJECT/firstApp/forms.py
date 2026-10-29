from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models import F
from django.utils import timezone
from django.forms import ModelForm

from .models import (
    Allocation,
    BookingRequest,
    ChildrenHome,
    ContributionPledge,
    Donor,
    FoodBridgeListing,
    HomeRegistration,
    HomeNeed,
    Hobby,
    ResourceOffer,
    Student,
    EventSmsSubscriber,
)


class StudentForm(ModelForm):
    class Meta:
        model = Student
        fields = '__all__'


class HobbyForm(ModelForm):
    class Meta:
        model = Hobby
        fields = '__all__'


class ChildrenHomeForm(ModelForm):
    class Meta:
        model = ChildrenHome
        fields = '__all__'


class DonorForm(ModelForm):
    class Meta:
        model = Donor
        fields = '__all__'


class ResourceOfferForm(ModelForm):
    class Meta:
        model = ResourceOffer
        fields = '__all__'


class HomeNeedForm(ModelForm):
    class Meta:
        model = HomeNeed
        fields = '__all__'


class BookingRequestForm(ModelForm):
    visitor_conduct_accepted = forms.BooleanField(required=True)

    class Meta:
        model = BookingRequest
        fields = [
            'home',
            'date',
            'time',
            'visitor_count',
            'visitor_name',
            'email',
            'purpose',
            'notes',
            'visitor_conduct_accepted',
        ]

    def clean_date(self):
        date = self.cleaned_data['date']
        if date < timezone.localdate():
            raise forms.ValidationError('Choose today or a future date.')
        return date


class FoodBridgeListingForm(ModelForm):
    contact_name = forms.CharField(max_length=150)
    contact_email = forms.EmailField()
    food_safety_confirmed = forms.BooleanField(required=True)

    class Meta:
        model = FoodBridgeListing
        fields = [
            'food_name',
            'category',
            'contact_name',
            'contact_email',
            'quantity',
            'unit',
            'location',
            'collection_window',
            'expiry_date',
            'handling',
            'food_safety_confirmed',
        ]

    def clean_expiry_date(self):
        expiry_date = self.cleaned_data['expiry_date']
        if expiry_date < timezone.localdate():
            raise forms.ValidationError('Expired food cannot be offered.')
        return expiry_date


class AllocationForm(ModelForm):
    class Meta:
        model = Allocation
        fields = '__all__'


class HomeRegistrationForm(ModelForm):
    verification_acknowledged = forms.BooleanField(required=True)

    class Meta:
        model = HomeRegistration
        fields = [
            'name',
            'location',
            'email',
            'phone_number',
            'website_url',
            'description',
            'verification_acknowledged',
        ]


class ContributionPledgeForm(ModelForm):
    pledge_acknowledged = forms.BooleanField(required=True)
    phone_number = forms.CharField(
        required=False,
        max_length=16,
        validators=[
            RegexValidator(
                regex=r"^\+[1-9]\d{7,14}$",
                message="Enter a phone number in international format, such as +254712345678.",
            )
        ],
    )
    sms_consent = forms.BooleanField(required=False)
    need = forms.ModelChoiceField(
        queryset=HomeNeed.objects.none(),
        required=False,
        empty_label='Choose a verified need',
    )

    class Meta:
        model = ContributionPledge
        fields = [
            'resource_type',
            'direction',
            'need',
            'description',
            'quantity',
            'donor_name',
            'email',
            'phone_number',
            'sms_consent',
            'pledge_acknowledged',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['need'].queryset = HomeNeed.objects.filter(
            verification_status__in=['verified', 'approved'],
            is_published=True,
            quantity_fulfilled__lt=F('quantity_requested'),
        ).select_related('home')

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('direction') == 'need' and not cleaned_data.get('need'):
            self.add_error('need', 'Choose a verified outstanding need.')
        if cleaned_data.get('direction') == 'fairmatch':
            cleaned_data['need'] = None
        if cleaned_data.get('sms_consent') and not cleaned_data.get('phone_number'):
            self.add_error('phone_number', 'Enter a phone number to receive SMS updates.')
        return cleaned_data


class EventSmsSubscriptionForm(forms.Form):
    phone_number = forms.CharField(
        max_length=16,
        validators=[
            RegexValidator(
                regex=r"^\+[1-9]\d{7,14}$",
                message="Enter a phone number in international format, such as +254712345678.",
            )
        ],
    )
    consent = forms.BooleanField(
        required=True,
        error_messages={"required": "Consent is required to receive event SMS alerts."},
    )

    def save(self):
        phone_number = self.cleaned_data["phone_number"]
        subscriber, _ = EventSmsSubscriber.objects.update_or_create(
            phone_number=phone_number,
            defaults={"is_active": True, "consented_at": timezone.now()},
        )
        return subscriber


class EventSmsUnsubscribeForm(forms.Form):
    phone_number = forms.CharField(
        max_length=16,
        validators=[
            RegexValidator(
                regex=r"^\+[1-9]\d{7,14}$",
                message="Enter a phone number in international format, such as +254712345678.",
            )
        ],
    )


class HomeNeedSubmissionForm(forms.Form):
    home = forms.ModelChoiceField(
        queryset=ChildrenHome.objects.none(),
        empty_label='Choose an organization',
    )
    title = forms.CharField(max_length=120)
    category = forms.ChoiceField(choices=HomeNeed.CATEGORY_CHOICES)
    quantity = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    unit = forms.CharField(max_length=20)
    urgency = forms.TypedChoiceField(
        choices=[(value, f'{value} · {label}') for value, label in [
            (1, 'Routine'),
            (2, 'Soon'),
            (3, 'Important'),
            (4, 'High'),
            (5, 'Critical'),
        ]],
        coerce=int,
    )
    deadline = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    storage_capacity_available = forms.TypedChoiceField(
        choices=(('true', 'Confirm available'), ('false', 'Not available')),
        coerce=lambda value: value == 'true',
    )
    reason = forms.CharField(widget=forms.Textarea, max_length=2000)

    def __init__(self, *args, homes=None, **kwargs):
        super().__init__(*args, **kwargs)
        if homes is not None:
            self.fields['home'].queryset = homes

    def save(self):
        return HomeNeed.objects.create(
            home=self.cleaned_data['home'],
            category=self.cleaned_data['category'],
            resource_type=self.cleaned_data['title'],
            quantity_requested=self.cleaned_data['quantity'],
            urgency=self.cleaned_data['urgency'],
            deadline=self.cleaned_data['deadline'],
            storage_capacity_available=self.cleaned_data['storage_capacity_available'],
            unit=self.cleaned_data['unit'],
            notes=self.cleaned_data['reason'],
            verification_status='pending',
        )