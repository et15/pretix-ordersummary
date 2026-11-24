from django.urls import re_path

from . import views

_PREFIX = r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/ordersummary/"

urlpatterns = [
    re_path(_PREFIX + r"$", views.OrderListView.as_view(), name="index"),
    re_path(
        _PREFIX + r"settings/$", views.OrderListSettingsView.as_view(), name="settings"
    ),
]
