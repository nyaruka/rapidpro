from .views import FlowCRUDL, FlowLabelCRUDL, FlowStartCRUDL

urlpatterns = FlowCRUDL().as_urlpatterns()
urlpatterns += FlowLabelCRUDL().as_urlpatterns()
urlpatterns += FlowStartCRUDL().as_urlpatterns()
