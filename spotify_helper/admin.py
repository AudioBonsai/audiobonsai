from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from spotify_helper.models import SpotifyUser


class SpotifyUserInline(admin.StackedInline):
    model = SpotifyUser
    can_delete = False


class UserAdmin(BaseUserAdmin):
    inlines = [SpotifyUserInline]


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
