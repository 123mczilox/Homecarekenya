from decimal import Decimal

from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse

from fairmatch.engine import recommend_allocations

from .forms import (
    AllocationForm,
    DonorForm,
    HomeNeedForm,
    HobbyForm,
    ResourceOfferForm,
    StudentForm,
)
from .models import Allocation, ChildrenHome, Donor, HomeNeed, Hobby, ResourceOffer, Student


def home(request):
    context = {'data': 'Welcome to Galleon Technologies'}
    return render(request, 'main.html', context)


def find_homes(request):
    all_homes = ChildrenHome.objects.all().order_by('-created_at')
    return render(request, 'firstApp/find_homes.html', {'homes': all_homes})


def bookings(request):
    context = {'data': 'Manage your bookings'}
    return render(request, 'firstApp/bookings.html', context)


def events(request):
    context = {'data': 'Explore our events'}
    return render(request, 'firstApp/events.html', context)


def donations(request):
    context = {'data': 'Support our cause'}
    return render(request, 'firstApp/donations.html', context)


def homed(request):
    context = {'data': 'Welcome to your dashboard'}
    return render(request, 'firstApp/homed.html', context)


def admin(request):
    context = {'data': 'Admin panel'}
    return render(request, 'firstApp/admin.html', context)


# ---------------- Donor CRUD ----------------
def createDonor(request):
    form = DonorForm()
    if request.method == 'POST':
        form = DonorForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('read-donors')
    return render(request, 'firstApp/form.html', {'form': form})


def readDonors(request):
    donors = Donor.objects.all().order_by('-created_at')
    return render(request, 'firstApp/donors.html', {'donors': donors})


def readDonor(request, pk):
    donor = get_object_or_404(Donor, id=pk)
    return render(request, 'firstApp/donor.html', {'donor': donor})


def updateDonor(request, pk):
    donor = get_object_or_404(Donor, id=pk)
    form = DonorForm(instance=donor)
    if request.method == 'POST':
        form = DonorForm(request.POST, instance=donor)
        if form.is_valid():
            form.save()
            return redirect('read-donors')
    return render(request, 'firstApp/form.html', {'form': form})


def deleteDonor(request, pk):
    donor = Donor.objects.get(id=pk)
    donor.delete()
    return redirect('read-donors')


# ---------------- ResourceOffer CRUD ----------------
def createResourceOffer(request):
    form = ResourceOfferForm()
    if request.method == 'POST':
        form = ResourceOfferForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('read-resource-offers')
    return render(request, 'firstApp/form.html', {'form': form})


def readResourceOffers(request):
    offers = ResourceOffer.objects.all().order_by('-created_at')
    return render(request, 'firstApp/resource_offers.html', {'offers': offers})


def readResourceOffer(request, pk):
    offer = get_object_or_404(ResourceOffer, id=pk)
    return render(request, 'firstApp/resource_offer.html', {'offer': offer})


def updateResourceOffer(request, pk):
    offer = get_object_or_404(ResourceOffer, id=pk)
    form = ResourceOfferForm(instance=offer)
    if request.method == 'POST':
        form = ResourceOfferForm(request.POST, instance=offer)
        if form.is_valid():
            form.save()
            return redirect('read-resource-offers')
    return render(request, 'firstApp/form.html', {'form': form})


def deleteResourceOffer(request, pk):
    offer = ResourceOffer.objects.get(id=pk)
    offer.delete()
    return redirect('read-resource-offers')


# ---------------- HomeNeed CRUD ----------------
def createHomeNeed(request):
    form = HomeNeedForm()
    if request.method == 'POST':
        form = HomeNeedForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('read-home-needs')
    return render(request, 'firstApp/form.html', {'form': form})


def readHomeNeeds(request):
    needs = HomeNeed.objects.all().order_by('-created_at')
    return render(request, 'firstApp/home_needs.html', {'needs': needs})


def readHomeNeed(request, pk):
    need = get_object_or_404(HomeNeed, id=pk)
    return render(request, 'firstApp/home_need.html', {'need': need})


def updateHomeNeed(request, pk):
    need = get_object_or_404(HomeNeed, id=pk)
    form = HomeNeedForm(instance=need)
    if request.method == 'POST':
        form = HomeNeedForm(request.POST, instance=need)
        if form.is_valid():
            form.save()
            return redirect('read-home-needs')
    return render(request, 'firstApp/form.html', {'form': form})


def deleteHomeNeed(request, pk):
    need = HomeNeed.objects.get(id=pk)
    need.delete()
    return redirect('read-home-needs')


# ---------------- Allocation CRUD ----------------
def createAllocation(request):
    form = AllocationForm()
    if request.method == 'POST':
        form = AllocationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('read-allocations')
    return render(request, 'firstApp/form.html', {'form': form})


def readAllocations(request):
    allocations = Allocation.objects.all().order_by('-allocated_at')
    return render(request, 'firstApp/allocations.html', {'allocations': allocations})


def readAllocation(request, pk):
    allocation = get_object_or_404(Allocation, id=pk)
    return render(request, 'firstApp/allocation.html', {'allocation': allocation})


def updateAllocation(request, pk):
    allocation = get_object_or_404(Allocation, id=pk)
    form = AllocationForm(instance=allocation)
    if request.method == 'POST':
        form = AllocationForm(request.POST, instance=allocation)
        if form.is_valid():
            form.save()
            return redirect('read-allocations')
    return render(request, 'firstApp/form.html', {'form': form})


def deleteAllocation(request, pk):
    allocation = Allocation.objects.get(id=pk)
    allocation.delete()
    return redirect('read-allocations')


def match_resource_offer(request, offer_id):
    offer = get_object_or_404(ResourceOffer, id=offer_id)
    needs = HomeNeed.objects.filter(
        verification_status__in=['verified', 'approved'],
        resource_type__iexact=offer.resource_type,
    ).select_related('home')

    need_dicts = [
        {
            'need_id': need.id,
            'home_id': need.home_id,
            'resource_type': need.resource_type,
            'quantity_requested': float(need.quantity_requested),
            'quantity_fulfilled': float(need.quantity_fulfilled),
            'urgency': need.urgency,
            'deadline': need.deadline.isoformat() if need.deadline else None,
            'verification_status': need.verification_status,
            'delivery_feasible': need.delivery_feasible,
            'storage_capacity_available': need.storage_capacity_available,
            'unit': need.unit,
        }
        for need in needs
    ]

    offer_dict = {
        'resource_id': offer.id,
        'donor_id': offer.donor_id,
        'resource_type': offer.resource_type,
        'quantity_available': float(offer.quantity_available),
        'unit': offer.unit,
        'expiry_date': offer.expiry_date.isoformat() if offer.expiry_date else None,
        'collection_location': offer.collection_location,
        'available_until': offer.available_until.isoformat() if offer.available_until else None,
        'safety_status': offer.safety_status,
        'availability_status': offer.availability_status,
    }

    history = []
    for allocation in Allocation.objects.filter(resource_offer_id=offer.id).select_related('need__home'):
        history.append({
            'resource_id': offer.id,
            'need_id': allocation.need_id,
            'home_id': allocation.need.home_id,
            'quantity_allocated': float(allocation.quantity_allocated),
        })

    results = recommend_allocations(need_dicts, offer_dict, history)
    return JsonResponse({'offer_id': offer.id, 'recommendations': results})


# ---------------- Student CRUD ----------------
def createStudent(request):
    form = StudentForm()
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('read-students')
    return render(request, 'firstApp/form.html', {'form': form})


def readStudents(request):
    students = Student.objects.all()
    return render(request, 'firstApp/students.html', {'students': students})


def readStudent(request, pk):
    student = get_object_or_404(Student, id=pk)
    return render(request, 'firstApp/student.html', {'student': student})


def updateStudent(request, pk):
    student = get_object_or_404(Student, id=pk)
    form = StudentForm(instance=student)
    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            return redirect('read-students')
    return render(request, 'firstApp/form.html', {'form': form})


def deleteStudent(request, pk):
    student = Student.objects.get(id=pk)
    student.delete()
    return redirect('read-students')


# ---------------- HOBBY CRUD ----------------
def createHobby(request):
    form = HobbyForm()
    if request.method == 'POST':
        form = HobbyForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('read-hobbies')
    return render(request, 'firstApp/form.html', {'form': form})


def readHobbies(request):
    hobbies = Hobby.objects.all()
    return render(request, 'firstApp/hobby.html', {'hobbies': hobbies})


def readHobby(request, pk):
    hobby = get_object_or_404(Hobby, id=pk)
    return render(request, 'firstApp/hobby.html', {'hobby': hobby})


def updateHobby(request, pk):
    hobby = get_object_or_404(Hobby, id=pk)
    form = HobbyForm(instance=hobby)
    if request.method == 'POST':
        form = HobbyForm(request.POST, instance=hobby)
        if form.is_valid():
            form.save()
            return redirect('read-hobbies')
    return render(request, 'firstApp/form.html', {'form': form})


def deleteHobby(request, pk):
    hobby = Hobby.objects.get(id=pk)
    hobby.delete()
    return redirect('read-hobbies')