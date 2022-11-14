"""
Written by Keeya Emmanuel Lubowa
On 24th Aug, 2022
Email ekeeya@oddjobs.tech
"""

from .views import *

urlpatterns = HandlerCRUDL().as_urlpatterns()
