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
    name = "pretix_jdavhe_orderlist"
    verbose_name = "JDAV Hessen order list"

    class PretixPluginMeta:
        name = gettext_lazy("JDAV Hessen order list")
        author = "JDAV Hessen"
        description = gettext_lazy("Order list showing participant names instead of the invoice recipient")
        visible = True
        version = __version__
        category = "FEATURE"
        compatibility = "pretix>=2026.9.0"
        level = PLUGIN_LEVEL_EVENT
        settings_links = []
        navigation_links = []

    def ready(self):
        from . import signals  # NOQA
