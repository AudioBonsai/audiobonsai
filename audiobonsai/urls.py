from django.urls import include, path
from django.contrib import admin

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('sausage_grinder.urls')),
    path('spotify', include('spotify_helper.urls')),
]
