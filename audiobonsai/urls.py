"""audiobonsai URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url
from django.contrib import admin
import sausage_grinder.views as sg
import spotify_helper.views as sh

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^spotify/ask_user', sh.spotify_ask_user),
    url(r'^spotify/request_token', sh.spotify_request_token),
    url(r'^spotify/login', sh.spotify_login),
    url(r'^spotify/confirm_access', sh.spotify_confirm_access),
    url(r'^spotify/expire_token', sh.expire_token),
    url(r'^spotify/test_conn', sh.test_conn),
    url(r'^artist', sg.artist),
    url(r'^genre', sg.genre),
    url(r'^release', sg.release),
    url(r'^track', sg.track),
    url(r'^week', sg.week),
    url(r'^', sg.sausage_grinder_index),
]
