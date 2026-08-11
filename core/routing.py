from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path('ws/negociation/<int:negociation_id>/', consumers.negociation_consumer),
]

