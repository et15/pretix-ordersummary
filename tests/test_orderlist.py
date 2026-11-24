from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled
from pretix.base.models import (
    Customer,
    InvoiceAddress,
    Order,
    OrderPayment,
    Question,
)

URL = "/control/event/jdavhe/kurs/jdavhe-orderlist/"


def _order(event, code, **kwargs):
    defaults = {
        "status": Order.STATUS_PENDING,
        "email": f"{code.lower()}@example.org",
        "datetime": now(),
        "expires": now() + timedelta(days=10),
        "total": Decimal("10.00"),
        "locale": "en",
        "sales_channel": event.organizer.sales_channels.get(identifier="web"),
    }
    defaults.update(kwargs)
    return Order.objects.create(event=event, code=code, **defaults)


def _position(order, item, name, **kwargs):
    return order.all_positions.create(
        item=item,
        price=Decimal("10.00"),
        attendee_name_parts={"full_name": name},
        **kwargs,
    )


@pytest.mark.django_db
def test_requires_permission(unprivileged_client):
    assert unprivileged_client.get(URL).status_code == 403


@pytest.mark.django_db
def test_404_if_plugin_inactive(admin_client, event):
    event.plugins = ""
    event.save()
    assert admin_client.get(URL).status_code == 404


@pytest.mark.django_db
def test_participant_names_instead_of_invoice_name(
    admin_client, event, item, addon_item
):
    with scopes_disabled():
        o = _order(event, "ABC12")
        InvoiceAddress.objects.create(order=o, name_parts={"full_name": "Paula Payer"})
        main = _position(o, item, "Anna Alpin")
        _position(o, item, "Bert Berg")
        _position(o, addon_item, "Addon Person", addon_to=main)
    html = admin_client.get(URL).content.decode()
    assert "Anna Alpin" in html
    assert "Bert Berg" in html
    assert "Addon Person" not in html
    assert "Paula Payer" not in html


@pytest.mark.django_db
def test_fallback_customer_then_invoice(admin_client, organizer, event, item):
    with scopes_disabled():
        customer = Customer.objects.create(
            organizer=organizer,
            email="c@example.org",
            name_parts={"full_name": "Carla Konto"},
        )
        o1 = _order(event, "CUST1", customer=customer)
        InvoiceAddress.objects.create(order=o1, name_parts={"full_name": "Not Shown"})
        _position(o1, item, "")
        o2 = _order(event, "INVO1")
        InvoiceAddress.objects.create(order=o2, name_parts={"full_name": "Ida Invoice"})
        _position(o2, item, "")
        o3 = _order(event, "COMP1")
        InvoiceAddress.objects.create(
            order=o3, company="Sektion Beispiel", is_business=True
        )
    html = admin_client.get(URL).content.decode()
    assert "Carla Konto" in html
    assert "Not Shown" not in html
    assert "Ida Invoice" in html
    assert "Sektion Beispiel" in html
    assert "Name from customer account" in html
    assert "Name from invoice address" in html


@pytest.mark.django_db
def test_canceled_order_keeps_names(admin_client, event, item):
    with scopes_disabled():
        o = _order(event, "CANC1", status=Order.STATUS_CANCELED)
        _position(o, item, "Clara Cancel", canceled=True)
    html = admin_client.get(URL, {"status": "c"}).content.decode()
    assert "Clara Cancel" in html


@pytest.mark.django_db
def test_payment_method(admin_client, event, item):
    with scopes_disabled():
        paid = _order(event, "PAID1", status=Order.STATUS_PAID)
        _position(paid, item, "Paula Paid")
        paid.payments.create(
            provider="banktransfer",
            amount=paid.total,
            state=OrderPayment.PAYMENT_STATE_FAILED,
        )
        paid.payments.create(
            provider="free",
            amount=paid.total,
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
        )
        pending = _order(event, "PEND1")
        _position(pending, item, "Pia Pending")
        pending.payments.create(
            provider="banktransfer",
            amount=pending.total,
            state=OrderPayment.PAYMENT_STATE_CREATED,
        )
    resp = admin_client.get(URL)
    rows = {o.code: o.payment_methods for o in resp.context["orders"]}
    assert rows["PAID1"] == ["Free of charge"]
    assert rows["PEND1"] == ["Bank transfer"]


@pytest.mark.django_db
def test_search_by_participant(admin_client, event, item):
    with scopes_disabled():
        _position(_order(event, "FIND1"), item, "Findable Person")
        _position(_order(event, "HIDE1"), item, "Other Person")
    resp = admin_client.get(URL, {"query": "findable"})
    assert [o.code for o in resp.context["orders"]] == ["FIND1"]


@pytest.mark.django_db
def test_navigation_entry(admin_client, event):
    html = admin_client.get("/control/event/jdavhe/kurs/orders/").content.decode()
    assert URL in html


@pytest.mark.django_db
def test_multiple_tickets_no_fallback_and_no_duplicates(
    admin_client, organizer, event, item
):
    with scopes_disabled():
        customer = Customer.objects.create(
            organizer=organizer,
            email="c@example.org",
            name_parts={"full_name": "Kunde Konto"},
        )
        o = _order(event, "MULT1", customer=customer)
        InvoiceAddress.objects.create(order=o, name_parts={"full_name": "Rech Nung"})
        _position(o, item, "Anna Alpin")
        _position(o, item, "")
        _position(o, item, "Anna Alpin")
        _position(o, item, "Bert Berg")
    resp = admin_client.get(URL)
    row = resp.context["orders"][0]
    assert row.participant_names == ["Anna Alpin", "Bert Berg"]
    assert row.name_source == "attendee"
    html = resp.content.decode()
    assert "Kunde Konto" not in html
    assert "Rech Nung" not in html


def _question(event, item, text, identifier, **kwargs):
    q = event.questions.create(question=text, identifier=identifier, type="S", **kwargs)
    q.items.add(item)
    return q


@pytest.mark.django_db
def test_settings_page_and_question_columns(
    admin_settings_client, event, item, addon_item
):
    with scopes_disabled():
        sektion = _question(event, item, "Sektion", "sektion", position=2)
        shoe = _question(event, addon_item, "Shoe size", "shoe", position=1)
        hidden = _question(event, item, "Not selected", "other", position=3)
        o = _order(event, "QUES1")
        main = _position(o, item, "Anna Alpin")
        second = _position(o, item, "Bert Berg")
        addon = _position(o, addon_item, "", addon_to=main)
        main.answers.create(question=sektion, answer="Frankfurt")
        second.answers.create(question=sektion, answer="Frankfurt")
        main.answers.create(question=hidden, answer="secret")
        addon.answers.create(question=shoe, answer="42")

    settings_url = URL + "settings/"
    html = admin_settings_client.get(settings_url).content.decode()
    assert "Sektion" in html and "Shoe size" in html

    resp = admin_settings_client.post(
        settings_url,
        {"jdavhe_orderlist_question_columns": [str(sektion.pk), str(shoe.pk)]},
    )
    assert resp.status_code == 302

    resp = admin_settings_client.get(URL)
    # Columns follow the position of the questions, not the selection.
    assert [q.pk for q in resp.context["questions"]] == [shoe.pk, sektion.pk]
    row = resp.context["orders"][0]
    assert row.question_values == [["42"], ["Frankfurt"]]
    assert "secret" not in resp.content.decode()


@pytest.mark.django_db
def test_order_level_question(admin_settings_client, event, item):
    with scopes_disabled():
        q = event.questions.create(
            question="Sektion",
            identifier="sektion",
            type="S",
            container_type=Question.ContainerType.ORDER,
        )
        o = _order(event, "ORDQ1")
        _position(o, item, "Anna Alpin")
        o.answers.create(question=q, answer="Kassel")
        event.settings.jdavhe_orderlist_question_columns = [str(q.pk)]
    resp = admin_settings_client.get(URL)
    assert resp.context["orders"][0].question_values == [["Kassel"]]


@pytest.mark.django_db
def test_settings_requires_permission(admin_client):
    assert admin_client.get(URL + "settings/").status_code == 403


def _codes(resp):
    return [o.code for o in resp.context["orders"]]


@pytest.mark.django_db
def test_status_filter(admin_client, event, item):
    with scopes_disabled():
        _position(_order(event, "PEND1"), item, "A")
        _position(_order(event, "PAID1", status=Order.STATUS_PAID), item, "B")
        _position(_order(event, "EXPI1", status=Order.STATUS_EXPIRED), item, "C")
        _position(_order(event, "CANC1", status=Order.STATUS_CANCELED), item, "D")
        # Canceled with paid fee: status stays "paid", all positions canceled.
        fee = _order(event, "FEEC1", status=Order.STATUS_PAID)
        _position(fee, item, "E", canceled=True)

    def codes(status):
        return sorted(_codes(admin_client.get(URL, {"status": status})))

    assert codes("") == ["EXPI1", "PAID1", "PEND1"]
    assert codes("all") == ["CANC1", "EXPI1", "FEEC1", "PAID1", "PEND1"]
    assert codes("n") == ["PEND1"]
    assert codes("p") == ["PAID1"]
    assert codes("e") == ["EXPI1"]
    assert codes("c") == ["CANC1", "FEEC1"]
    assert codes("nonsense") == ["EXPI1", "PAID1", "PEND1"]


@pytest.mark.django_db
def test_sorting(admin_settings_client, organizer, event, item):
    client = admin_settings_client
    with scopes_disabled():
        q = _question(event, item, "Sektion", "sektion")
        event.settings.jdavhe_orderlist_question_columns = [str(q.pk)]
        o1 = _order(event, "AAAA1", datetime=now() - timedelta(days=3))
        p1 = _position(o1, item, "bert Berg")
        p1.answers.create(question=q, answer="Kassel")
        o2 = _order(event, "BBBB2", datetime=now() - timedelta(days=1))
        _position(o2, item, "")
        InvoiceAddress.objects.create(
            order=o2, name_parts={"full_name": "Carla Invoice"}
        )
        o3 = _order(event, "CCCC3", datetime=now() - timedelta(days=2))
        p3 = _position(o3, item, "Anna Alpin")
        p3.answers.create(question=q, answer="Frankfurt")
        o4 = _order(event, "DDDD4", datetime=now())
        _position(o4, item, "")

    def codes(ordering):
        return _codes(client.get(URL, {"ordering": ordering}))

    assert codes("") == ["DDDD4", "BBBB2", "CCCC3", "AAAA1"]  # default: newest first
    assert codes("code") == ["AAAA1", "BBBB2", "CCCC3", "DDDD4"]
    assert codes("-code") == ["DDDD4", "CCCC3", "BBBB2", "AAAA1"]
    assert codes("datetime") == ["AAAA1", "CCCC3", "BBBB2", "DDDD4"]
    # Case-insensitive, fallback names included, orders without a name last.
    assert codes("participant") == ["CCCC3", "AAAA1", "BBBB2", "DDDD4"]
    assert codes("-participant") == ["BBBB2", "AAAA1", "CCCC3", "DDDD4"]
    # Orders without an answer come last (in order of creation).
    assert codes(f"q{q.pk}") == ["CCCC3", "AAAA1", "BBBB2", "DDDD4"]
    assert codes("payment") == codes("")  # not sortable: default order
    html = client.get(URL).content.decode()
    assert f"ordering=-q{q.pk}" in html
    assert "ordering=-participant" in html


@pytest.mark.django_db
def test_live_filter_returns_only_results(admin_client, event, item):
    with scopes_disabled():
        _position(_order(event, "LIVE1"), item, "Lena Live")
        _position(_order(event, "LIVE2", status=Order.STATUS_CANCELED), item, "Carl")
    page = admin_client.get(URL).content.decode()
    assert 'id="jdavhe-orderlist-filter"' in page
    assert "pretix_jdavhe_orderlist/orderlist.js" in page

    resp = admin_client.get(
        URL, {"status": "c"}, headers={"X-Requested-With": "XMLHttpRequest"}
    )
    html = resp.content.decode()
    assert "<html" not in html
    assert 'id="jdavhe-orderlist-filter"' not in html
    assert "LIVE2" in html
    assert "LIVE1" not in html
    # Sort links keep the current filter.
    assert "status=c" in html
