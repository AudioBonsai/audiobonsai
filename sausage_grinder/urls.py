from django.urls import path

from . import views as sg

urlpatterns = [
    path('artist', sg.artist),
    path('genre', sg.genre),
    path('release', sg.release),
    path('track', sg.track),
    path('', sg.sausage_grinder_index),
]
