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
from spotify_helper.views import spotify_login, spotify_request_token, spotify_ask_user, spotify_confirm_access

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^spotify/ask_user', spotify_ask_user),
    url(r'^spotify/request_token', spotify_request_token),
    url(r'^spotify/login', spotify_login),
    url(r'^spotify/confirm_access', spotify_confirm_access),
]
