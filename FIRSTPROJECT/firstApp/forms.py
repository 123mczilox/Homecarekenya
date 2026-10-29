from django.forms import ModelForm

from .models import (
    Allocation,
    BookingRequest,
    ChildrenHome,
    Donor,
    FoodBridgeListing,
    HomeNeed,
    Hobby,
    ResourceOffer,
    Student,
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
        ]


class FoodBridgeListingForm(ModelForm):
    class Meta:
        model = FoodBridgeListing
        fields = [
            'food_name',
            'category',
            'quantity',
            'unit',
            'location',
            'collection_window',
            'expiry_date',
            'handling',
            'food_safety_confirmed',
        ]


class AllocationForm(ModelForm):
    class Meta:
        model = Allocation
        fields = '__all__'