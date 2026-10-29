from django.conf import settings
from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Q
from .models import Student, Hobby, ChildrenHome
from .forms import StudentForm, HobbyForm
from .backend_api import BackendAPIError, get_public_home, get_public_homes
from fairmatch import recommend_allocations


def backend_unavailable(request):
    return render(request, "firstApp/backend_unavailable.html", status=503)


def home(request):
    if settings.HOMECARE_API_BASE_URL:
        try:
            featured_homes = get_public_homes({"verification": "verified"})[:3]
        except BackendAPIError:
            return backend_unavailable(request)
        return render(request, "main.html", {"featured_homes": featured_homes})

    featured_homes = ChildrenHome.objects.filter(is_verified=True).order_by(
        "-created_at"
    )[:3]
    return render(request, "main.html", {"featured_homes": featured_homes})


def find_homes(request):
    query = request.GET.get("q", "").strip()
    county = request.GET.get("county", "").strip()
    verification = request.GET.get("verification", "").strip()

    if settings.HOMECARE_API_BASE_URL:
        try:
            homes = get_public_homes(
                {
                    "q": query,
                    "county": county,
                    "verification": verification,
                }
            )
        except BackendAPIError:
            return backend_unavailable(request)
        return render(
            request,
            "firstApp/find_homes.html",
            {
                "homes": homes,
                "query": query,
                "selected_county": county,
                "verification": verification,
                "counties": ChildrenHome.COUNTY_CHOICES,
            },
        )

    homes = ChildrenHome.objects.all().order_by("-created_at")
    if query:
        homes = homes.filter(Q(name__icontains=query) | Q(location__icontains=query))
    if county:
        homes = homes.filter(location=county)
    if verification == "verified":
        homes = homes.filter(is_verified=True)
    elif verification == "listed":
        homes = homes.filter(is_verified=False)
    return render(
        request,
        "firstApp/find_homes.html",
        {
            "homes": homes,
            "query": query,
            "selected_county": county,
            "verification": verification,
            "counties": ChildrenHome.COUNTY_CHOICES,
        },
    )


def home_profile(request, slug):
    if settings.HOMECARE_API_BASE_URL:
        try:
            home = get_public_home(slug)
        except BackendAPIError:
            return backend_unavailable(request)
        return render(request, "firstApp/home_profile.html", {"home": home})

    home = get_object_or_404(ChildrenHome, slug=slug)
    return render(request, "firstApp/home_profile.html", {"home": home})


def bookings(request):
    if settings.HOMECARE_API_BASE_URL:
        try:
            homes = get_public_homes({"verification": "verified"})
        except BackendAPIError:
            return backend_unavailable(request)
    else:
        homes = ChildrenHome.objects.filter(is_verified=True).order_by("name")
    return render(
        request,
        "firstApp/bookings.html",
        {
            "submitted": request.method == "POST",
            "homes": homes,
        },
    )


def events(request):
    return render(request, "firstApp/events.html")


def donations(request):
    return render(
        request, "firstApp/donations.html", {"submitted": request.method == "POST"}
    )


def homed(request):
    return render(request, "firstApp/homed.html")


def admin_dashboard(request):
    return render(request, "firstApp/admin.html")


def needs_management(request):
    return render(
        request, "firstApp/needs.html", {"submitted": request.method == "POST"}
    )


def fairmatch(request):
    sample_need = {
        "need_id": "demo-learning-supplies",
        "home_id": "demo-home-01",
        "resource_type": "exercise books",
        "quantity_requested": 120,
        "quantity_fulfilled": 64,
        "unit": "books",
        "urgency": 4,
        "deadline": "2026-11-15",
        "verification_status": "verified",
        "storage_capacity_available": True,
        "delivery_feasible": True,
    }
    sample_offer = {
        "resource_id": "demo-offer-01",
        "resource_type": "exercise books",
        "quantity_available": 40,
        "unit": "books",
        "safety_status": "approved",
        "availability_status": "available",
    }
    recommendations = recommend_allocations([sample_need], sample_offer)
    return render(
        request,
        "firstApp/fairmatch.html",
        {
            "recommendations": recommendations,
            "recommendation": recommendations[0] if recommendations else None,
            "sample_need": sample_need,
            "sample_offer": sample_offer,
        },
    )


def foodbridge(request):
    return render(
        request, "firstApp/foodbridge.html", {"submitted": request.method == "POST"}
    )


def home_registration(request):
    return render(
        request,
        "firstApp/home_registration.html",
        {
            "submitted": request.method == "POST",
            "counties": ChildrenHome.COUNTY_CHOICES,
        },
    )


def createStudent(request):
    form = StudentForm()

    if request.method == "POST":
        form = StudentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("read-students")

    context = {"form": form}
    return render(request, "firstApp/form.html", context)


def readStudents(request):
    students = Student.objects.all()
    context = {"students": students}
    return render(request, "firstApp/students.html", context)


def readStudent(request, pk):
    student = Student.objects.get(id=pk)
    context = {"student": student}
    return render(request, "firstApp/student.html", context)


def updateStudent(request, pk):
    student = Student.objects.get(id=pk)
    form = StudentForm(instance=student)

    if request.method == "POST":
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            return redirect("read-students")

    context = {"form": form}
    return render(request, "firstApp/form.html", context)


def deleteStudent(request, pk):
    student = Student.objects.get(id=pk)
    student.delete()
    return redirect("read-students")


# ---------------- HOBBY CRUD ----------------


def createHobby(request):
    form = HobbyForm()

    if request.method == "POST":
        form = HobbyForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("read-hobbies")

    context = {"form": form}
    return render(request, "firstApp/form.html", context)


def readHobbies(request):
    hobbies = Hobby.objects.all()
    context = {"hobbies": hobbies}
    return render(request, "firstApp/hobby.html", context)


def readHobby(request, pk):
    hobby = Hobby.objects.get(id=pk)
    context = {"hobby": hobby}
    return render(request, "firstApp/hobby.html", context)


def updateHobby(request, pk):
    hobby = Hobby.objects.get(id=pk)
    form = HobbyForm(instance=hobby)

    if request.method == "POST":
        form = HobbyForm(request.POST, instance=hobby)
        if form.is_valid():
            form.save()
            return redirect("read-hobbies")

    context = {"form": form}
    return render(request, "firstApp/form.html", context)


def deleteHobby(request, pk):
    hobby = Hobby.objects.get(id=pk)
    hobby.delete()
    return redirect("read-hobbies")
