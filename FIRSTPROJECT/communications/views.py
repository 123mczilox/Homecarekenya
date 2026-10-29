from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt, csrf_protect, ensure_csrf_cookie

from .services import build_ussd_response, send_sms


@ensure_csrf_cookie
def test_sms(request):
    recipients = request.GET.get('to') or '+254700000000'
    message = request.GET.get('message') or "HomeCareKenya: test SMS from Africa's Talking"
    sender_id = request.GET.get('sender') or None

    result = send_sms(recipients, message, sender_id=sender_id)
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


@csrf_exempt
def ussd_callback(request):
    if request.method != 'POST':
        return HttpResponse('END Method not allowed.', content_type='text/plain; charset=utf-8')

    phone_number = request.POST.get('phoneNumber') or request.GET.get('phoneNumber')
    text = request.POST.get('text') or request.GET.get('text') or ''

    response_text = build_ussd_response(text, phone_number)
    return HttpResponse(response_text, content_type='text/plain; charset=utf-8')
