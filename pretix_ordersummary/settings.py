"""Settings keys of this plugin, registered with pretix' settings store."""

from pretix.base.settings import settings_hierarkey

#: IDs (as strings) of the questions shown as extra columns, in no particular order.
QUESTION_COLUMNS_KEY = "ordersummary_question_columns"

#: Check-in column: "" = hidden, "any" = entries on any check-in list,
#: otherwise the ID of one check-in list.
CHECKIN_COLUMN_KEY = "ordersummary_checkin_column"
CHECKIN_ANY = "any"

settings_hierarkey.add_default(QUESTION_COLUMNS_KEY, "[]", list)
settings_hierarkey.add_default(CHECKIN_COLUMN_KEY, "", str)
