from django.urls import re_path

from . import views

urlpatterns = [
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/jdavhe-orderlist/$",
        views.OrderListView.as_view(),
        name="index",
    ),
]
