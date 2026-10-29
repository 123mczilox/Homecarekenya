from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('home/', views.home, name='home'),
    path('find_homes/', views.find_homes, name='find_homes'),
    path('bookings/', views.bookings, name='Bookings'),
    path('events/', views.events, name='events'),
    path('donations/', views.donations, name='Donations'),
    path('homed/', views.homed, name='homed'),
    path('admin-panel/', views.admin, name='admin-panel'),

    # Donor URLs
    path('create-donor/', views.createDonor, name='create-donor'),
    path('read-donors/', views.readDonors, name='read-donors'),
    path('read-donor/<str:pk>/', views.readDonor, name='read-donor'),
    path('update-donor/<str:pk>/', views.updateDonor, name='update-donor'),
    path('delete-donor/<str:pk>/', views.deleteDonor, name='delete-donor'),

    # Resource offer URLs
    path('create-resource-offer/', views.createResourceOffer, name='create-resource-offer'),
    path('read-resource-offers/', views.readResourceOffers, name='read-resource-offers'),
    path('read-resource-offer/<str:pk>/', views.readResourceOffer, name='read-resource-offer'),
    path('update-resource-offer/<str:pk>/', views.updateResourceOffer, name='update-resource-offer'),
    path('delete-resource-offer/<str:pk>/', views.deleteResourceOffer, name='delete-resource-offer'),

    # Home need URLs
    path('create-home-need/', views.createHomeNeed, name='create-home-need'),
    path('read-home-needs/', views.readHomeNeeds, name='read-home-needs'),
    path('read-home-need/<str:pk>/', views.readHomeNeed, name='read-home-need'),
    path('update-home-need/<str:pk>/', views.updateHomeNeed, name='update-home-need'),
    path('delete-home-need/<str:pk>/', views.deleteHomeNeed, name='delete-home-need'),

    # Allocation URLs
    path('create-allocation/', views.createAllocation, name='create-allocation'),
    path('read-allocations/', views.readAllocations, name='read-allocations'),
    path('read-allocation/<str:pk>/', views.readAllocation, name='read-allocation'),
    path('update-allocation/<str:pk>/', views.updateAllocation, name='update-allocation'),
    path('delete-allocation/<str:pk>/', views.deleteAllocation, name='delete-allocation'),
    path('match-resource-offer/<int:offer_id>/', views.match_resource_offer, name='match-resource-offer'),

    # Student URLs
    path('create-student/', views.createStudent, name='create-student'),
    path('read-students/', views.readStudents, name='read-students'),
    path('read-student/<str:pk>/', views.readStudent, name='read-student'),
    path('update-student/<str:pk>/', views.updateStudent, name='update-student'),
    path('delete-student/<str:pk>/', views.deleteStudent, name='delete-student'),

    # Hobby URLs
    path('create-hobby/', views.createHobby, name='create-hobby'),
    path('read-hobbies/', views.readHobbies, name='read-hobbies'),
    path('read-hobby/<str:pk>/', views.readHobby, name='read-hobby'),
    path('update-hobby/<str:pk>/', views.updateHobby, name='update-hobby'),
    path('delete-hobby/<str:pk>/', views.deleteHobby, name='delete-hobby'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)