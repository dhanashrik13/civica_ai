from django.contrib import admin
from accounts import models
# Register your models here.

admin.site.register(models.Admin)
admin.site.register(models.Citizen)
admin.site.register(models.Officer)

