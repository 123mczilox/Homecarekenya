from django.urls import path

from .views import africastalking_webhook, test_sms

urlpatterns = [
    path('communications/test-sms/', test_sms, name='test_sms'),
    path('communications/webhook/', africastalking_webhook, name='africastalking_webhook'),
]
