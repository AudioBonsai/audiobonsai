from django.urls import path

from . import views as sh

urlpatterns = [
    path('ask_user', sh.spotify_ask_user),
    path('request_token', sh.spotify_request_token),
    path('login', sh.spotify_login),
    path('confirm_access', sh.spotify_confirm_access),
    path('expire_token', sh.expire_token),
    path('test_conn', sh.test_conn),
]
