from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.decorators.http import require_POST

from . import views

staff_only = views.role_required("staff")

urlpatterns = [
    path("", views.home, name="home"),
    path("home/", views.home, name="home"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="firstApp/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("find_homes/", views.find_homes, name="find_homes"),
    path("homes/<slug:slug>/", views.home_profile, name="home-profile"),
    path("bookings/", views.bookings, name="Bookings"),
    path("events/", views.events, name="events"),
    path("donations/", views.donations, name="Donations"),
    path("homed/", views.homed, name="homed"),
    path("platform-dashboard/", views.admin_dashboard, name="admin-dashboard"),
    path(
        "platform-dashboard/organizations/<int:registration_id>/approve/",
        staff_only(require_POST(views.approve_home_registration_view)),
        name="approve-home-registration",
    ),
    path("donor-dashboard/", views.donor_dashboard, name="donor-dashboard"),
    path("supplier-dashboard/", views.supplier_dashboard, name="supplier-dashboard"),
    path("needs/", views.needs_management, name="needs-management"),
    path("fairmatch/", views.fairmatch, name="fairmatch"),
    path("foodbridge/", views.foodbridge, name="foodbridge"),
    path("register-home/", views.home_registration, name="home-register"),

    # Donor URLs
    path("create-donor/", staff_only(views.createDonor), name="create-donor"),
    path("read-donors/", staff_only(views.readDonors), name="read-donors"),
    path("read-donor/<str:pk>/", staff_only(views.readDonor), name="read-donor"),
    path("update-donor/<str:pk>/", staff_only(views.updateDonor), name="update-donor"),
    path("delete-donor/<str:pk>/", staff_only(require_POST(views.deleteDonor)), name="delete-donor"),

    # Resource offer URLs
    path("create-resource-offer/", staff_only(views.createResourceOffer), name="create-resource-offer"),
    path("read-resource-offers/", staff_only(views.readResourceOffers), name="read-resource-offers"),
    path("read-resource-offer/<str:pk>/", staff_only(views.readResourceOffer), name="read-resource-offer"),
    path("update-resource-offer/<str:pk>/", staff_only(views.updateResourceOffer), name="update-resource-offer"),
    path("delete-resource-offer/<str:pk>/", staff_only(require_POST(views.deleteResourceOffer)), name="delete-resource-offer"),

    # Home need URLs
    path("create-home-need/", staff_only(views.createHomeNeed), name="create-home-need"),
    path("read-home-needs/", staff_only(views.readHomeNeeds), name="read-home-needs"),
    path("read-home-need/<str:pk>/", staff_only(views.readHomeNeed), name="read-home-need"),
    path("update-home-need/<str:pk>/", staff_only(views.updateHomeNeed), name="update-home-need"),
    path("delete-home-need/<str:pk>/", staff_only(require_POST(views.deleteHomeNeed)), name="delete-home-need"),

    # Allocation URLs
    path("create-allocation/", staff_only(views.createAllocation), name="create-allocation"),
    path("read-allocations/", staff_only(views.readAllocations), name="read-allocations"),
    path("read-allocation/<str:pk>/", staff_only(views.readAllocation), name="read-allocation"),
    path("update-allocation/<str:pk>/", staff_only(views.updateAllocation), name="update-allocation"),
    path("delete-allocation/<str:pk>/", staff_only(require_POST(views.deleteAllocation)), name="delete-allocation"),
    path("match-resource-offer/<int:offer_id>/", staff_only(views.match_resource_offer), name="match-resource-offer"),
    path(
        "fairmatch/allocate/<int:offer_id>/<int:need_id>/",
        staff_only(require_POST(views.allocate_fairmatch)),
        name="allocate-fairmatch",
    ),

    # Student URLs
    path("create-student/", staff_only(views.createStudent), name="create-student"),
    path("read-students/", staff_only(views.readStudents), name="read-students"),
    path("read-student/<str:pk>/", staff_only(views.readStudent), name="read-student"),
    path("update-student/<str:pk>/", staff_only(views.updateStudent), name="update-student"),
    path("delete-student/<str:pk>/", staff_only(require_POST(views.deleteStudent)), name="delete-student"),

    # Hobby URLs
    path("create-hobby/", staff_only(views.createHobby), name="create-hobby"),
    path("read-hobbies/", staff_only(views.readHobbies), name="read-hobbies"),
    path("read-hobby/<str:pk>/", staff_only(views.readHobby), name="read-hobby"),
    path("update-hobby/<str:pk>/", staff_only(views.updateHobby), name="update-hobby"),
    path("delete-hobby/<str:pk>/", staff_only(require_POST(views.deleteHobby)), name="delete-hobby"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
