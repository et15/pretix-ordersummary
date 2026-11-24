Participant order list
======================

This is a plugin for `pretix`_ by JDAV Hessen.

It adds a page **Orders → Participant orders** to the event backend. Unlike
pretix' own order list, which shows the invoice recipient, it shows the
participants of each order.

Columns
-------

- **Order code**, linked to the order.
- **Participant**: the participant names of all tickets of the order, without
  duplicates and without add-on products. Only if no ticket has a name, the
  name of the linked customer account is used, and after that the name (or
  company) of the invoice address. An icon marks these fallbacks.
- **Order date**.
- **Payment method**: the methods of all paid payments, or, if nothing is paid
  yet, the method of the newest open payment.
- **Extra question columns**, chosen under *Settings → Participant orders*.
  Each cell shows the answers of all tickets of the order (add-ons included),
  without duplicates. Questions asked once per order are supported, too.
- **Status**, as in pretix' order list.

Canceled tickets are only used if all tickets of an order are canceled. The
search box finds orders by order code, email, participant, customer account or
invoice name.

The status filter hides canceled orders by default, including orders canceled
with a paid fee. "Paid" does not include those.

The status filter applies as soon as it changes and the search while typing.
Filter, search, sort arrows and page navigation update only the table, without
reloading the page (``static/pretix_jdavhe_orderlist/orderlist.js``). Sorting
and page changes create browser history entries, so "back" works. Without
JavaScript, everything works as normal links and forms.

All columns except the payment method can be sorted with the arrows next to the
column header. Participant and question columns sort by the first value shown,
ignoring case; orders without a value come last. Answers are sorted as text,
so numbers sort like "10" before "9".

Permissions: viewing the list needs the permission to view orders; the settings
page needs the permission to change the general event settings.

Development setup
-----------------

1. Make sure that you have a working `pretix development setup`_.

2. Clone this repository.

3. Activate the virtual environment you use for pretix development.

4. Execute ``pip install -e .`` within this directory to register this application with pretix's plugin registry.

5. Execute ``make`` within this directory to compile translations.

6. Restart your local pretix server. You can now use the plugin from this repository for your events by enabling it in
   the 'plugins' tab in the settings.

This plugin has CI set up to enforce a few code style rules with `Ruff`_. To
check locally, you need it installed::

    pip install ruff

To check your plugin for rule violations, run::

    ruff format --check .
    ruff check .

You can auto-fix most of these issues by running::

    ruff format .
    ruff check --fix .

To automatically check for these issues before you commit, you can run ``.install-hooks.sh``.

Commits in this repository follow `Conventional Commits`_ and releases are
cut with `Commitizen`_ (``cz bump``), which updates the version in
``pyproject.toml`` and ``pretix_jdavhe_orderlist/__init__.py``, writes
``CHANGELOG.md`` and creates the matching git tag. The version starts at
0.1.0; while it is 0.x, breaking changes bump the minor version.


Quick start without a pretix checkout
-------------------------------------

To run the tests and the style checks you do not need a full pretix development
setup. With `uv`_, a few commands create a throwaway environment that contains
the plugin and pretix from its git master branch::

    uv venv
    source .venv/bin/activate
    uv pip install -e . --group dev --group test
    make
    pytest tests
    ruff check .

``make`` needs GNU gettext (Debian package ``gettext``). To try the plugin in a
running pretix, use the development setup above instead.


License
-------


Copyright 2026 JDAV Hessen

Released under the terms of the Apache License 2.0



.. _pretix: https://github.com/pretix/pretix
.. _pretix development setup: https://docs.pretix.eu/en/latest/development/setup.html
.. _Ruff: https://docs.astral.sh/ruff/
.. _uv: https://docs.astral.sh/uv/
.. _Conventional Commits: https://www.conventionalcommits.org/
.. _Commitizen: https://commitizen-tools.github.io/commitizen/
