from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


international_phone_validator = RegexValidator(
    regex=r"^\+[1-9]\d{7,14}$",
    message="Enter a phone number in international format, such as +254712345678.",
)


class ChildrenHome(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, help_text="used for the URLs")
    COUNTY_CHOICES = [
        ('Nairobi', 'Nairobi'),
        ('Nyandarua', 'Nyandarua'),
        ('Nyeri', 'Nyeri'),
        ('Kirinyaga', 'Kirinyaga'),
        ('Kiambu', 'Kiambu'),
        ('Mombasa', 'Mombasa'),
    ]
    location = models.CharField(max_length=100, choices=COUNTY_CHOICES)
    capacity = models.IntegerField()
    descripttion = models.TextField()
    image = models.ImageField(upload_to='children_homes/')
    website_url = models.URLField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField()
    is_verified = models.BooleanField(default=False)
    is_urgent = models.BooleanField(default=False, help_text="Check this to show on 'Urgent Needs' section")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Donor(models.Model):
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    organization_name = models.CharField(max_length=150, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name or self.organization_name or 'Donor'


class ResourceOffer(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('reserved', 'Reserved'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    SAFETY_CHOICES = [
        ('approved', 'Approved'),
        ('safe', 'Safe'),
        ('verified', 'Verified'),
        ('pending', 'Pending'),
    ]
    donor = models.ForeignKey(Donor, on_delete=models.CASCADE, related_name='resource_offers')
    resource_type = models.CharField(max_length=120)
    quantity_available = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit = models.CharField(max_length=20, default='kg')
    expiry_date = models.DateField(blank=True, null=True)
    collection_location = models.CharField(max_length=200, blank=True, null=True)
    available_until = models.DateField(blank=True, null=True)
    safety_status = models.CharField(max_length=20, choices=SAFETY_CHOICES, default='approved')
    availability_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.resource_type} ({self.quantity_available} {self.unit})'


class BookingRequest(models.Model):
    STATUS_CHOICES = [
        ('pending_review', 'Pending review'),
        ('approved', 'Approved'),
        ('declined', 'Declined'),
        ('completed', 'Completed'),
    ]
    home = models.ForeignKey(ChildrenHome, on_delete=models.CASCADE, related_name='booking_requests')
    date = models.DateField()
    time = models.CharField(max_length=40)
    visitor_count = models.PositiveIntegerField(default=1)
    visitor_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=16, blank=True)
    email = models.EmailField()
    purpose = models.TextField()
    notes = models.TextField(blank=True, default='')
    visitor_conduct_accepted = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_review')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.visitor_name} for {self.home.name} on {self.date}'


class FoodBridgeListing(models.Model):
    STATUS_CHOICES = [
        ('pending_review', 'Pending review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]
    CATEGORY_CHOICES = [
        ('fresh_produce', 'Fresh produce'),
        ('dry_goods', 'Dry goods'),
        ('dairy', 'Dairy'),
        ('prepared_food', 'Prepared food'),
        ('other', 'Other'),
    ]
    food_name = models.CharField(max_length=200)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    contact_name = models.CharField(max_length=150, blank=True)
    contact_email = models.EmailField(blank=True)
    quantity = models.PositiveIntegerField()
    unit = models.CharField(max_length=30)
    location = models.CharField(max_length=200)
    collection_window = models.CharField(max_length=200)
    expiry_date = models.DateField()
    handling = models.TextField(blank=True, default='')
    food_safety_confirmed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_review')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.food_name} ({self.quantity} {self.unit})'


class HomeNeed(models.Model):
    CATEGORY_CHOICES = [
        ('food', 'Food'),
        ('clothing', 'Clothing'),
        ('school_supplies', 'School supplies'),
        ('hygiene', 'Hygiene'),
        ('bedding', 'Bedding'),
        ('other', 'Other essential goods'),
    ]
    VERIFICATION_CHOICES = [
        ('verified', 'Verified'),
        ('approved', 'Approved'),
        ('pending', 'Pending'),
    ]
    home = models.ForeignKey(ChildrenHome, on_delete=models.CASCADE, related_name='needs')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='other')
    resource_type = models.CharField(max_length=120)
    quantity_requested = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity_fulfilled = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    urgency = models.PositiveIntegerField(default=1)
    deadline = models.DateField(blank=True, null=True)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_CHOICES, default='pending')
    is_published = models.BooleanField(default=False)
    delivery_feasible = models.BooleanField(default=True)
    storage_capacity_available = models.BooleanField(default=True)
    unit = models.CharField(max_length=20, default='kg')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def outstanding_quantity(self):
        return max(0, self.quantity_requested - self.quantity_fulfilled)

    def __str__(self):
        return f'{self.home.name}: {self.resource_type}'


class Allocation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    resource_offer = models.ForeignKey(ResourceOffer, on_delete=models.CASCADE, related_name='allocations')
    need = models.ForeignKey(HomeNeed, on_delete=models.CASCADE, related_name='allocations')
    quantity_allocated = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    allocated_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'{self.need.home.name} <- {self.quantity_allocated} {self.resource_offer.unit}'


class Student(models.Model):
    name = models.CharField(max_length=100)
    dob = models.DateField()
    age = models.IntegerField()
    course = models.CharField(max_length=100)
    height = models.FloatField()
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Hobby(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    requirements = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class HomeRegistration(models.Model):
    STATUS_CHOICES = [
        ('pending_review', 'Pending review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100, choices=ChildrenHome.COUNTY_CHOICES)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True)
    website_url = models.URLField(blank=True)
    description = models.TextField()
    verification_acknowledged = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_review')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} ({self.get_status_display()})'


class ContributionPledge(models.Model):
    RESOURCE_CHOICES = [
        ('money', 'Money'),
        ('food', 'Food'),
        ('supplies', 'Essential supplies'),
    ]
    DIRECTION_CHOICES = [
        ('need', 'Specific need'),
        ('fairmatch', 'FairMatch recommendation'),
    ]
    STATUS_CHOICES = [
        ('pending_review', 'Pending review'),
        ('accepted', 'Accepted'),
        ('fulfilled', 'Fulfilled'),
        ('withdrawn', 'Withdrawn'),
    ]
    resource_type = models.CharField(max_length=20, choices=RESOURCE_CHOICES)
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    need = models.ForeignKey(
        HomeNeed,
        on_delete=models.SET_NULL,
        related_name='pledges',
        blank=True,
        null=True,
    )
    description = models.CharField(max_length=300)
    quantity = models.CharField(max_length=100)
    donor_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone_number = models.CharField(
        max_length=16,
        blank=True,
        validators=[international_phone_validator],
    )
    sms_consent = models.BooleanField(
        default=False,
        help_text="The donor agrees to receive SMS updates about this pledge.",
    )
    pledge_acknowledged = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_review')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.get_resource_type_display()} pledge from {self.donor_name}'


class CommunityEvent(models.Model):
    title = models.CharField(max_length=160)
    details = models.TextField()
    event_date = models.DateField()
    event_time = models.TimeField(blank=True, null=True)
    location = models.CharField(max_length=200)
    is_published = models.BooleanField(default=False)
    reminder_sent_at = models.DateTimeField(blank=True, null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["event_date", "event_time", "title"]

    def __str__(self):
        return f"{self.title} ({self.event_date})"


class EventSmsSubscriber(models.Model):
    phone_number = models.CharField(
        max_length=16,
        unique=True,
        validators=[international_phone_validator],
    )
    is_active = models.BooleanField(default=True)
    consented_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["phone_number"]

    def __str__(self):
        return self.phone_number