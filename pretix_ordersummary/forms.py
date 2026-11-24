from django import forms
from django.utils.translation import gettext_lazy as _
from pretix.base.forms import SettingsForm

from .settings import CHECKIN_ANY, CHECKIN_COLUMN_KEY, QUESTION_COLUMNS_KEY


class OrderListSettingsForm(SettingsForm):
    """Choose the optional columns of the order list."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[QUESTION_COLUMNS_KEY] = forms.MultipleChoiceField(
            label=_("Questions as columns"),
            help_text=_(
                "The answers to these questions are shown as additional columns "
                "in the attendee order list, in the order of the questions."
            ),
            required=False,
            widget=forms.CheckboxSelectMultiple,
            choices=[
                (str(q.pk), str(q.question))
                for q in self.obj.questions.order_by("position", "pk")
            ],
        )
        self.fields[CHECKIN_COLUMN_KEY] = forms.ChoiceField(
            label=_("Check-in status"),
            help_text=_(
                "Shows whether the attendees have entered at least once. Exits, "
                "failed scans and add-on products are not taken into account."
            ),
            required=False,
            choices=[
                ("", _("Do not show column")),
                (CHECKIN_ANY, _("All check-in lists")),
                *[
                    (str(cl.pk), str(cl.name))
                    for cl in self.obj.checkin_lists.order_by("name", "pk")
                ],
            ],
        )
