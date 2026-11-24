from django.utils.translation import gettext_lazy

from . import __version__

try:
    from pretix.base.plugins import PLUGIN_LEVEL_EVENT, PluginConfig
except ImportError:
    raise RuntimeError(
        "Please use pretix 2026.9.0 or above to run this plugin!",
    ) from None


class PluginApp(PluginConfig):
    default = True
    name = "pretix_ordersummary"
    verbose_name = "Attendee order list"

    class PretixPluginMeta:
        name = gettext_lazy("Attendee order list")
        author = "et15"
        description = gettext_lazy(
            "Order list showing the attendees of each order, with payment method "
            "and selected question answers"
        )
        visible = True
        version = __version__
        category = "FEATURE"
        compatibility = "pretix>=2026.9.0"
        level = PLUGIN_LEVEL_EVENT
        settings_links = [
            (
                (gettext_lazy("Orders"), gettext_lazy("Orders by attendee")),
                "plugins:pretix_ordersummary:settings",
                {},
            ),
        ]
        navigation_links = [
            (
                (gettext_lazy("Orders"), gettext_lazy("Orders by attendee")),
                "plugins:pretix_ordersummary:index",
                {},
            ),
        ]

    def ready(self):
        from . import signals  # NOQA
