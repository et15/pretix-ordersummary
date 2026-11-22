from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled
from pretix.base.models import Event, Organizer, Team, User


@pytest.fixture
def organizer():
    with scopes_disabled():
        # Bank transfer is a hybrid plugin: it must be active for the organizer too.
        return Organizer.objects.create(
            name="JDAV Hessen", slug="jdavhe", plugins="pretix.plugins.banktransfer"
        )


@pytest.fixture
def event(organizer):
    with scopes_disabled():
        ev = Event.objects.create(
            organizer=organizer,
            name="Kletterkurs",
            slug="kurs",
            date_from=now() + timedelta(days=30),
            plugins="pretix_jdavhe_orderlist,pretix.plugins.banktransfer",
        )
        ev.settings.payment_banktransfer__enabled = True
        return ev


@pytest.fixture
def item(event):
    with scopes_disabled():
        return event.items.create(name="Teilnahme", default_price=Decimal("10.00"))


@pytest.fixture
def addon_item(event):
    with scopes_disabled():
        return event.items.create(name="Leihausrüstung", default_price=Decimal("5.00"))


def _make_user(organizer, event, email, permissions):
    user = User.objects.create_user(email, "dummy-password")
    with scopes_disabled():
        team = Team.objects.create(
            organizer=organizer, name=email, limit_event_permissions=permissions
        )
        team.members.add(user)
        team.limit_events.add(event)
    return user


@pytest.fixture
def admin_client(client, organizer, event):
    user = _make_user(
        organizer, event, "admin@example.org", {"event.orders:read": True}
    )
    client.login(email=user.email, password="dummy-password")
    return client


@pytest.fixture
def unprivileged_client(client, organizer, event):
    user = _make_user(organizer, event, "nobody@example.org", {})
    client.login(email=user.email, password="dummy-password")
    return client


@pytest.fixture
def admin_settings_client(client, organizer, event):
    user = _make_user(
        organizer,
        event,
        "settings@example.org",
        {"event.orders:read": True, "event.settings.general:write": True},
    )
    client.login(email=user.email, password="dummy-password")
    return client
