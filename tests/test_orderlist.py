from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled
from pretix.base.models import Customer, InvoiceAddress, Order, OrderPayment

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
    html = admin_client.get(URL).content.decode()
    assert "Clara Cancel" in html


@pytest.mark.django_db
def test_payment_method(admin_client, event, item):
    with scopes_disabled():
        paid = _order(event, "PAID1", status=Order.STATUS_PAID)
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
