from django.dispatch import receiver
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _
from pretix.control.signals import nav_event

from .views import PERMISSION


@receiver(nav_event, dispatch_uid="jdavhe_orderlist_nav")
def navbar_entry(sender, request, **kwargs):
    """Add the order list as a sub-item of the built-in "Orders" menu."""
    if not request.user.has_event_permission(
        request.organizer, request.event, PERMISSION, request=request
    ):
        return []
    url = resolve(request.path_info)
    kw = {"organizer": request.organizer.slug, "event": request.event.slug}
    return [
        {
            "label": _("Participant orders"),
            "url": reverse("plugins:pretix_jdavhe_orderlist:index", kwargs=kw),
            "parent": reverse("control:event.orders", kwargs=kw),
            "active": url.namespace == "plugins:pretix_jdavhe_orderlist",
        }
    ]
