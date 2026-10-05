from django.db import models


class Admin(models.Model):

    full_name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)

    # Stored hashed via make_password — see admin.py save_model override,
    # so the super admin can just type a plain password in Django's /admin/.
    password = models.CharField(max_length=255)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} ({self.email})"
