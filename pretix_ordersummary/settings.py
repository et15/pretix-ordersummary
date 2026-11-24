"""Settings keys of this plugin, registered with pretix' settings store."""

import json

from pretix.base.settings import settings_hierarkey

#: Optional standard columns that are shown (see ``STANDARD_COLUMNS``).
STANDARD_COLUMNS_KEY = "ordersummary_standard_columns"
COLUMN_DATETIME = "datetime"
COLUMN_PAYMENT = "payment"
#: Shown by default, as before these columns became optional.
STANDARD_COLUMNS_DEFAULT = [COLUMN_DATETIME, COLUMN_PAYMENT]

#: IDs (as strings) of the questions shown as extra columns, in no particular order.
QUESTION_COLUMNS_KEY = "ordersummary_question_columns"

#: Check-in column: "" = hidden, "any" = entries on any check-in list,
#: otherwise the ID of one check-in list.
CHECKIN_COLUMN_KEY = "ordersummary_checkin_column"
CHECKIN_ANY = "any"

#: ID of the date question with the date of birth for the age column, "" = hidden.
AGE_QUESTION_KEY = "ordersummary_age_question"

settings_hierarkey.add_default(
    STANDARD_COLUMNS_KEY, json.dumps(STANDARD_COLUMNS_DEFAULT), list
)
settings_hierarkey.add_default(QUESTION_COLUMNS_KEY, "[]", list)
settings_hierarkey.add_default(CHECKIN_COLUMN_KEY, "", str)
settings_hierarkey.add_default(AGE_QUESTION_KEY, "", str)
