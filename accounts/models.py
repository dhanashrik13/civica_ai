from django.db import models


# Abstract base class for all users
class User(models.Model):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(max_length=254, unique=True)
    password = models.CharField(max_length=128)  # Store hashed passwords
    role = models.CharField(max_length=30)
    is_active = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.role} | {self.username}"

    class Meta:
        abstract = True


# Department model for issue assignment
class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


# Citizen model
class Citizen(User):
    phone_no = models.CharField(max_length=15)
    address = models.CharField(max_length=200)


# Officer model
class Officer(User):
    region = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name='officers')


# Admin model
class Admin(User):
    access_level = models.CharField(max_length=50, default="superuser")


# Issue model to be reported by citizens
class Issue(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=100)
    location = models.CharField(max_length=255)
    photo1 = models.ImageField(upload_to='issue_photos/', null=True, blank=True)
    photo2 = models.ImageField(upload_to='issue_photos/', null=True, blank=True)
    photo3 = models.ImageField(upload_to='issue_photos/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reported_by = models.ForeignKey('Citizen', on_delete=models.CASCADE, related_name='issues_reported')
    assigned_to = models.ForeignKey('Officer', on_delete=models.SET_NULL, null=True, blank=True, related_name='issues_assigned')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title
