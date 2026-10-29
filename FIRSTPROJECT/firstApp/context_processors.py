from django.conf import settings


def homecare_config(request):
    return {
        "HOMECARE_API_BASE_URL": getattr(settings, "HOMECARE_API_BASE_URL", ""),
    }