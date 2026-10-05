from django.contrib import admin
from django.contrib.auth.hashers import make_password
from .models import Admin


@admin.register(Admin)
class AdminModelAdmin(admin.ModelAdmin):

    list_display = ("full_name", "email", "is_active", "created_at")
    search_fields = ("full_name", "email")

    def save_model(self, request, obj, form, change):
        """
        Lets the super admin type a plain password in the Django admin
        form. It gets hashed automatically here before saving, the same
        way Django's own UserAdmin handles it — so nobody ever needs to
        pre-hash a password by hand.
        """

        if "password" in form.changed_data:
            obj.password = make_password(obj.password)

        super().save_model(request, obj, form, change)
