from django.db import models


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


class HomeNeed(models.Model):
    VERIFICATION_CHOICES = [
        ('verified', 'Verified'),
        ('approved', 'Approved'),
        ('pending', 'Pending'),
    ]
    home = models.ForeignKey(ChildrenHome, on_delete=models.CASCADE, related_name='needs')
    resource_type = models.CharField(max_length=120)
    quantity_requested = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity_fulfilled = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    urgency = models.PositiveIntegerField(default=1)
    deadline = models.DateField(blank=True, null=True)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_CHOICES, default='pending')
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