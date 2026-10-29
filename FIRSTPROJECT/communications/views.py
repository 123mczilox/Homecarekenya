from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie

from .services import send_sms


@ensure_csrf_cookie
def test_sms(request):
    phone_number = request.GET.get('to') or '+254700000000'
    message = request.GET.get('message') or "HomeCareKenya: test SMS from Africa's Talking"

    result = send_sms(phone_number, message)
    return JsonResponse(result)


@csrf_protect
def africastalking_webhook(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'ignored', 'method': request.method}, status=405)

    payload = request.POST or request.body.decode('utf-8', errors='ignore')
    return JsonResponse({
        'status': 'received',
        'provider': 'africastalking',
        'payload': payload,
    })
