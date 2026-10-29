from django.contrib import admin

from .models import Allocation, ChildrenHome, Donor, HomeNeed, Hobby, ResourceOffer, Student


admin.site.register(Student)
admin.site.register(Hobby)
admin.site.register(ChildrenHome)
admin.site.register(Donor)
admin.site.register(ResourceOffer)
admin.site.register(HomeNeed)
admin.site.register(Allocation)
