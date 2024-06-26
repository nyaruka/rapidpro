from django.urls import re_path

from .views import Home, MessageHistory, RangeDetails, WorkspaceStats

urlpatterns = [
    re_path(r"^dashboard/home/$", Home.as_view(), {}, "dashboard.dashboard_home"),
    re_path(r"^dashboard/message_history/$", MessageHistory.as_view(), {}, "dashboard.dashboard_message_history"),
    re_path(r"^dashboard/workspace_stats/$", WorkspaceStats.as_view(), {}, "dashboard.dashboard_workspace_stats"),
    re_path(r"^dashboard/range_details/$", RangeDetails.as_view(), {}, "dashboard.dashboard_range_details"),
]
