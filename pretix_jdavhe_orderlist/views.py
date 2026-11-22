"""Order list for the event backend that shows participant names per order."""

from django.db.models import Exists, OuterRef, Prefetch, Q, prefetch_related_objects
from django.http import Http404
from django.views.generic import ListView
from pretix.base.models import Order, OrderPayment, OrderPosition
from pretix.control.permissions import EventPermissionRequiredMixin
from pretix.control.views import PaginationMixin

PERMISSION = "event.orders:read"

#: Payment states that mean money was received for this payment.
PAID_STATES = (
    OrderPayment.PAYMENT_STATE_CONFIRMED,
    OrderPayment.PAYMENT_STATE_REFUNDED,
)
#: Payment states of a payment that is started but not finished yet.
OPEN_STATES = (
    OrderPayment.PAYMENT_STATE_CREATED,
    OrderPayment.PAYMENT_STATE_PENDING,
)

NAME_SOURCE_ATTENDEE = "attendee"
NAME_SOURCE_CUSTOMER = "customer"
NAME_SOURCE_INVOICE = "invoice"


def _unique(values):
    """Return the non-empty values in their original order, without duplicates."""
    seen = []
    for v in values:
        if v and v not in seen:
            seen.append(v)
    return seen


def participant_names(order):
    """Return ``(names, source)`` to show for an order.

    Expects ``order.main_positions`` (all positions without add-ons, prefetched).
    Order of preference:

    1. Participant names of non-canceled positions; for an order whose positions
       are all canceled, the participant names of the canceled positions.
       Add-on positions are ignored.
    2. Name of the linked customer account.
    3. Name (or, if empty, company) of the invoice address.

    ``source`` is one of the ``NAME_SOURCE_*`` constants, or ``None`` if no name
    was found.
    """
    active = [p for p in order.main_positions if not p.canceled]
    names = _unique(p.attendee_name_cached for p in (active or order.main_positions))
    if names:
        return names, NAME_SOURCE_ATTENDEE

    if order.customer and order.customer.name_cached:
        return [order.customer.name_cached], NAME_SOURCE_CUSTOMER

    try:
        ia = order.invoice_address
    except Order.invoice_address.RelatedObjectDoesNotExist:
        ia = None
    if ia and (ia.name_cached or ia.company):
        return [ia.name_cached or ia.company], NAME_SOURCE_INVOICE

    return [], None


def payment_provider_names(order, providers):
    """Return the display names of the payment methods of an order.

    Expects ``order.payment_list`` (payments, newest first). Uses the methods of
    all paid payments; if there is none, the method of the newest open payment.
    Failed and canceled attempts are ignored. ``providers`` maps the provider
    identifier to the provider instance of the event.
    """
    paid = [p.provider for p in reversed(order.payment_list) if p.state in PAID_STATES]
    if not paid:
        paid = [p.provider for p in order.payment_list if p.state in OPEN_STATES][:1]
    return _unique(
        str(providers[p].verbose_name) if p in providers else p for p in paid
    )


class OrderListView(EventPermissionRequiredMixin, PaginationMixin, ListView):
    """List of the event's orders with participant name and payment method."""

    model = Order
    context_object_name = "orders"
    template_name = "pretix_jdavhe_orderlist/index.html"
    permission = PERMISSION

    def dispatch(self, request, *args, **kwargs):
        # pretix does not check for control URLs whether the plugin is active.
        if "pretix_jdavhe_orderlist" not in request.event.get_plugins():
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = (
            Order.objects.filter(event=self.request.event)
            .select_related("invoice_address", "customer")
            .order_by("-datetime", "-pk")
        )
        query = self.request.GET.get("query", "").strip()
        if query:
            matching_position = OrderPosition.all.filter(
                order=OuterRef("pk"), attendee_name_cached__icontains=query
            )
            qs = qs.filter(
                Q(code__icontains=query)
                | Q(code__icontains=Order.normalize_code(query))
                | Q(email__icontains=query)
                | Q(invoice_address__name_cached__icontains=query)
                | Q(invoice_address__company__icontains=query)
                | Q(customer__name_cached__icontains=query)
                | Exists(matching_position)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        orders = list(ctx["orders"])
        prefetch_related_objects(
            orders,
            Prefetch(
                "all_positions",
                queryset=OrderPosition.all.order_by("positionid"),
                to_attr="position_list",
            ),
            Prefetch(
                "payments",
                queryset=OrderPayment.objects.order_by("-created", "-pk"),
                to_attr="payment_list",
            ),
        )
        providers = self.request.event.get_payment_providers(cached=True)
        for o in orders:
            o.main_positions = [p for p in o.position_list if p.addon_to_id is None]
            # Used by pretix' status label (``count_positions``).
            o.pcnt = sum(1 for p in o.position_list if not p.canceled)
            o.participant_names, o.name_source = participant_names(o)
            o.payment_methods = payment_provider_names(o, providers)
        ctx["orders"] = orders
        ctx["query"] = self.request.GET.get("query", "")
        return ctx
