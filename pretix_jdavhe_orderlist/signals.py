from django.dispatch import receiver
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _
from pretix.control.signals import nav_event, nav_event_settings

from .views import PERMISSION, SETTINGS_PERMISSION


def _url_kwargs(request):
    return {"organizer": request.organizer.slug, "event": request.event.slug}


@receiver(nav_event, dispatch_uid="jdavhe_orderlist_nav")
def navbar_entry(sender, request, **kwargs):
    """Add the order list as a sub-item of the built-in "Orders" menu."""
    if not request.user.has_event_permission(
        request.organizer, request.event, PERMISSION, request=request
    ):
        return []
    url = resolve(request.path_info)
    return [
        {
            "label": _("Participant orders"),
            "url": reverse(
                "plugins:pretix_jdavhe_orderlist:index", kwargs=_url_kwargs(request)
            ),
            "parent": reverse("control:event.orders", kwargs=_url_kwargs(request)),
            "active": url.namespace == "plugins:pretix_jdavhe_orderlist"
            and url.url_name == "index",
        }
    ]


@receiver(nav_event_settings, dispatch_uid="jdavhe_orderlist_nav_settings")
def navbar_settings_entry(sender, request, **kwargs):
    """Add the settings page to the event settings menu."""
    if not request.user.has_event_permission(
        request.organizer, request.event, SETTINGS_PERMISSION, request=request
    ):
        return []
    url = resolve(request.path_info)
    return [
        {
            "label": _("Participant orders"),
            "url": reverse(
                "plugins:pretix_jdavhe_orderlist:settings", kwargs=_url_kwargs(request)
            ),
            "active": url.namespace == "plugins:pretix_jdavhe_orderlist"
            and url.url_name == "settings",
        }
    ]
