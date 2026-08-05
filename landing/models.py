from django.db import models

class HeroSection(models.Model):
    title = models.CharField(max_length=255)
    subtitle = models.TextField()
    button_text = models.CharField(max_length=50)

    class Meta:
        verbose_name_plural = "Hero Section"

    def __str__(self):
        return self.title

class Stat(models.Model):
    icon_class = models.CharField(max_length=100)
    value = models.CharField(max_length=50)
    label = models.CharField(max_length=100)

    def __str__(self):
        return self.label

class Feature(models.Model):
    icon_class = models.CharField(max_length=100)
    title = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.title

class Testimonial(models.Model):
    message = models.TextField()
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class TrustedCity(models.Model):
    name = models.CharField(max_length=255)

    class Meta:
        verbose_name_plural = "Trusted Cities"

    def __str__(self):
        return self.name

