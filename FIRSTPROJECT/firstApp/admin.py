from django.contrib import admin

from .models import (
    Allocation,
    BookingRequest,
    ChildrenHome,
    CommunityEvent,
    ContributionPledge,
    Donor,
    EventSmsSubscriber,
    FoodBridgeListing,
    HomeNeed,
    HomeRegistration,
    Hobby,
    ResourceOffer,
    Student,
)


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = ('visitor_name', 'phone_number', 'home', 'date', 'status', 'created_at')
    list_filter = ('status', 'date')
    search_fields = ('visitor_name', 'phone_number', 'email', 'home__name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FoodBridgeListing)
class FoodBridgeListingAdmin(admin.ModelAdmin):
    list_display = ('food_name', 'contact_name', 'quantity', 'unit', 'status', 'expiry_date')
    list_filter = ('status', 'category', 'expiry_date')
    search_fields = ('food_name', 'contact_name', 'contact_email', 'location')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(HomeRegistration)
class HomeRegistrationAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'email', 'status', 'created_at')
    list_filter = ('status', 'location')
    search_fields = ('name', 'email', 'phone_number')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ContributionPledge)
class ContributionPledgeAdmin(admin.ModelAdmin):
    list_display = (
        'donor_name',
        'phone_number',
        'sms_consent',
        'resource_type',
        'quantity',
        'direction',
        'need',
        'status',
        'created_at',
    )
    list_filter = ('status', 'resource_type', 'direction')
    search_fields = ('donor_name', 'email', 'phone_number', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CommunityEvent)
class CommunityEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'event_date', 'event_time', 'location', 'is_published', 'reminder_sent_at')
    list_filter = ('is_published', 'event_date')
    search_fields = ('title', 'details', 'location')
    readonly_fields = ('reminder_sent_at', 'created_at', 'updated_at')


@admin.register(EventSmsSubscriber)
class EventSmsSubscriberAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'is_active', 'consented_at')
    list_filter = ('is_active',)
    search_fields = ('phone_number',)
    readonly_fields = ('created_at', 'consented_at')


@admin.register(HomeNeed)
class HomeNeedAdmin(admin.ModelAdmin):
    list_display = (
        'resource_type',
        'home',
        'verification_status',
        'is_published',
        'urgency',
        'quantity_requested',
        'quantity_fulfilled',
    )
    list_filter = ('verification_status', 'is_published', 'category', 'urgency')
    search_fields = ('resource_type', 'home__name')


admin.site.register(Student)
admin.site.register(Hobby)
admin.site.register(ChildrenHome)
admin.site.register(Donor)
admin.site.register(ResourceOffer)
admin.site.register(Allocation)
