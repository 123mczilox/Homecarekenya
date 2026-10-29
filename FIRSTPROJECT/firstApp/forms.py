from django.forms import ModelForm

from .models import Allocation, ChildrenHome, Donor, HomeNeed, Hobby, ResourceOffer, Student


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


class AllocationForm(ModelForm):
    class Meta:
        model = Allocation
        fields = '__all__'