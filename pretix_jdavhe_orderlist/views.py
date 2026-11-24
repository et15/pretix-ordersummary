"""Order list for the event backend that shows participant names per order."""

from django.db.models import (
    Exists,
    F,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Value,
    prefetch_related_objects,
)
from django.db.models.functions import Coalesce, Lower, NullIf
from django.http import Http404
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView
from pretix.base.models import (
    Order,
    OrderPayment,
    OrderPosition,
    QuestionAnswer,
)
from pretix.control.permissions import EventPermissionRequiredMixin
from pretix.control.views import PaginationMixin
from pretix.control.views.event import EventSettingsFormView, EventSettingsViewMixin

from .forms import OrderListSettingsForm
from .settings import QUESTION_COLUMNS_KEY

PLUGIN_MODULE = "pretix_jdavhe_orderlist"
PERMISSION = "event.orders:read"
SETTINGS_PERMISSION = "event.settings.general:write"

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


def question_values(order, questions):
    """Return one list of answer strings per question, in the order of ``questions``.

    Expects ``order.position_list`` (with ``answer_list`` per position) and
    ``order.order_answer_list`` (answers to questions asked once per order).
    Answers of all positions count, add-ons included, because a question may be
    asked for an add-on product only. As for names, canceled positions are only
    used if all positions of the order are canceled. Duplicates are removed.
    """
    positions = [
        p for p in order.position_list if not p.canceled
    ] or order.position_list
    answers = list(order.order_answer_list)
    for p in positions:
        answers.extend(p.answer_list)
    return [
        _unique(str(a) for a in answers if a.question_id == q.pk) for q in questions
    ]


def selected_questions(event):
    """Return the questions configured as extra columns, in the order of the questions.

    Questions deleted after they were selected are skipped.
    """
    ids = event.settings.get(QUESTION_COLUMNS_KEY, as_type=list) or []
    return list(event.questions.filter(pk__in=ids).order_by("position", "pk"))


#: Status filter: value -> label. The empty value is the default.
STATUS_ALL = "all"
STATUS_CHOICES = (
    ("", _("All except canceled")),
    (STATUS_ALL, _("All orders")),
    (Order.STATUS_PENDING, _("Pending")),
    (Order.STATUS_PAID, _("Paid")),
    (Order.STATUS_EXPIRED, _("Expired")),
    (Order.STATUS_CANCELED, _("Canceled (fully or with paid fee)")),
)


def filter_status(qs, status):
    """Filter orders by the status filter value (see ``STATUS_CHOICES``).

    "Canceled" includes orders canceled with a paid fee. pretix keeps those in
    status "paid", but without any non-canceled position.
    """
    has_active = Exists(OrderPosition.objects.filter(order=OuterRef("pk")))
    canceled = Q(status=Order.STATUS_CANCELED) | (
        Q(status=Order.STATUS_PAID) & ~has_active
    )
    if status == STATUS_ALL:
        return qs
    if status == Order.STATUS_CANCELED:
        return qs.filter(canceled)
    if status == Order.STATUS_PAID:
        return qs.filter(Q(status=Order.STATUS_PAID) & has_active)
    if status in (Order.STATUS_PENDING, Order.STATUS_EXPIRED):
        return qs.filter(status=status)
    return qs.exclude(canceled)


def participant_sort_expression():
    """Database expression for the first name shown in the participant column.

    Mirrors ``participant_names``: participant name of the first main position
    (canceled positions only if no main position is active), then the customer
    account, then the invoice address.
    """
    order_has_active_main = Exists(
        OrderPosition.objects.filter(order=OuterRef("order"), addon_to__isnull=True)
    )
    first_name = (
        OrderPosition.all.filter(order=OuterRef("pk"), addon_to__isnull=True)
        .exclude(attendee_name_cached__isnull=True)
        .exclude(attendee_name_cached="")
        .filter(Q(canceled=False) | ~order_has_active_main)
        .order_by("positionid")
        .values("attendee_name_cached")[:1]
    )
    return Coalesce(
        Subquery(first_name),
        NullIf("customer__name_cached", Value("")),
        NullIf("invoice_address__name_cached", Value("")),
        NullIf("invoice_address__company", Value("")),
    )


def answer_sort_expression(question):
    """Database expression for the first answer to ``question`` of an order.

    Sorts by the stored answer text, so numbers sort as text ("10" before "9").
    """
    order_answer = QuestionAnswer.objects.filter(
        order=OuterRef("pk"), orderposition__isnull=True, question=question
    ).values("answer")[:1]
    position_answer = (
        QuestionAnswer.objects.filter(
            orderposition__order=OuterRef("pk"),
            orderposition__canceled=False,
            question=question,
        )
        .order_by("orderposition__positionid")
        .values("answer")[:1]
    )
    return Coalesce(Subquery(order_answer), Subquery(position_answer))


class PluginActiveMixin:
    """Return 404 if the plugin is not active for the event.

    pretix does not check this for plugin URLs in the backend.
    """

    def dispatch(self, request, *args, **kwargs):
        if PLUGIN_MODULE not in request.event.get_plugins():
            raise Http404()
        return super().dispatch(request, *args, **kwargs)


class OrderListView(
    PluginActiveMixin, EventPermissionRequiredMixin, PaginationMixin, ListView
):
    """List of the event's orders with participant name and payment method."""

    model = Order
    context_object_name = "orders"
    template_name = "pretix_jdavhe_orderlist/index.html"
    permission = PERMISSION

    #: Sort keys of the fixed columns; question columns use ``q<question id>``.
    SORT_FIELDS = ("code", "participant", "datetime", "status")
    DEFAULT_ORDERING = "-datetime"

    def get_template_names(self):
        # The live filter (static/.../orderlist.js) only needs the result table.
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return ["pretix_jdavhe_orderlist/fragment_results.html"]
        return [self.template_name]

    @cached_property
    def questions(self):
        questions = selected_questions(self.request.event)
        for q in questions:
            q.sort_key = f"q{q.pk}"
        return questions

    @cached_property
    def ordering(self):
        """The requested sort key (with optional "-"), or the default."""
        value = self.request.GET.get("ordering", "")
        key = value.removeprefix("-")
        allowed = set(self.SORT_FIELDS) | {q.sort_key for q in self.questions}
        return value if key in allowed else self.DEFAULT_ORDERING

    def _apply_ordering(self, qs):
        descending = self.ordering.startswith("-")
        key = self.ordering.removeprefix("-")
        if key == "participant":
            qs = qs.annotate(_sort=Lower(participant_sort_expression()))
            expr = "_sort"
        elif key.startswith("q"):
            question = next(q for q in self.questions if q.sort_key == key)
            qs = qs.annotate(_sort=Lower(answer_sort_expression(question)))
            expr = "_sort"
        else:
            expr = key
        field = (
            F(expr).desc(nulls_last=True)
            if descending
            else F(expr).asc(nulls_last=True)
        )
        tie = "-pk" if descending else "pk"
        return qs.order_by(field, tie)

    def get_queryset(self):
        qs = Order.objects.filter(event=self.request.event).select_related(
            "invoice_address", "customer"
        )
        qs = filter_status(qs, self.request.GET.get("status", ""))
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
        return self._apply_ordering(qs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        orders = list(ctx["orders"])
        questions = self.questions
        answer_qs = QuestionAnswer.objects.filter(
            question__in=questions
        ).select_related("question")
        prefetch_related_objects(
            orders,
            Prefetch(
                "all_positions",
                queryset=OrderPosition.all.order_by("positionid"),
                to_attr="position_list",
            ),
            Prefetch(
                "position_list__answers", queryset=answer_qs, to_attr="answer_list"
            ),
            Prefetch(
                "answers",
                queryset=answer_qs.filter(orderposition__isnull=True),
                to_attr="order_answer_list",
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
            o.question_values = question_values(o, questions)
        ctx["orders"] = orders
        ctx["questions"] = questions
        ctx["query"] = self.request.GET.get("query", "")
        ctx["status"] = self.request.GET.get("status", "")
        ctx["status_choices"] = STATUS_CHOICES
        ctx["filtered"] = bool(ctx["query"] or ctx["status"])
        return ctx


class OrderListSettingsView(
    PluginActiveMixin, EventSettingsViewMixin, EventSettingsFormView
):
    """Event settings page to choose the questions shown as extra columns."""

    form_class = OrderListSettingsForm
    template_name = "pretix_jdavhe_orderlist/settings.html"
    permission = SETTINGS_PERMISSION

    def get_success_url(self):
        return reverse(
            "plugins:pretix_jdavhe_orderlist:settings",
            kwargs={
                "organizer": self.request.organizer.slug,
                "event": self.request.event.slug,
            },
        )
