from django.contrib import admin
from .models import HeroSection, Stat, Feature, Testimonial, TrustedCity



@admin.register(HeroSection)
class HeroSectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'button_text')


@admin.register(Stat)
class StatAdmin(admin.ModelAdmin):
    list_display = ('label', 'value', 'icon_class')


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ('title', 'icon_class')


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('name', 'role')


@admin.register(TrustedCity)
class TrustedCityAdmin(admin.ModelAdmin):
    list_display = ('name',)