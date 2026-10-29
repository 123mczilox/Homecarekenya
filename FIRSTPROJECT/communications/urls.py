from django.urls import path

from .views import africastalking_webhook, test_sms, ussd_callback

urlpatterns = [
    path('test-sms/', test_sms, name='test_sms'),
    path('webhook/', africastalking_webhook, name='africastalking_webhook'),
    path('ussd/', ussd_callback, name='africastalking_ussd'),
]
