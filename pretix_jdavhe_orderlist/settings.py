"""Settings keys of this plugin, registered with pretix' settings store."""

from pretix.base.settings import settings_hierarkey

#: IDs (as strings) of the questions shown as extra columns, in no particular order.
QUESTION_COLUMNS_KEY = "jdavhe_orderlist_question_columns"

settings_hierarkey.add_default(QUESTION_COLUMNS_KEY, "[]", list)
