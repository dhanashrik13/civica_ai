import re
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.html import escape  # FIXED: For XSS prevention
from .models import Department

User = get_user_model()


# ---------------------------
# AUTHENTICATION & REGISTRATION
# ---------------------------
class RegisterForm(forms.Form):
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=True)

    # Common optional fields
    full_name = forms.CharField(max_length=150, required=True)
    phone_no = forms.CharField(max_length=15, required=False)
    address = forms.CharField(widget=forms.Textarea, required=False)
    region = forms.CharField(max_length=100, required=False)
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False
    )

    # Geolocation fields
    latitude = forms.DecimalField(max_digits=9, decimal_places=6, required=False)
    longitude = forms.DecimalField(max_digits=9, decimal_places=6, required=False)
    allow_location = forms.BooleanField(required=False)
    accept_terms = forms.BooleanField(required=True)

    def __init__(self, *args, **kwargs):
        self.role = kwargs.pop("role", None)
        super().__init__(*args, **kwargs)

        # Clean up fields based on role
        if self.role == User.Role.CITIZEN:
            self.fields["phone_no"].required = True
            self.fields["address"].required = True
            if "region" in self.fields: self.fields.pop("region")
            if "department" in self.fields: self.fields.pop("department")

        elif self.role == User.Role.OFFICER:
            self.fields["region"].required = True
            self.fields["department"].required = True
            if "phone_no" in self.fields: self.fields.pop("phone_no")
            if "address" in self.fields: self.fields.pop("address")
            if "allow_location" in self.fields: self.fields.pop("allow_location")
            if "latitude" in self.fields: self.fields.pop("latitude")
            if "longitude" in self.fields: self.fields.pop("longitude")

        elif self.role == User.Role.DEPT_ADMIN:
            self.fields["department"].required = True
            if "phone_no" in self.fields: self.fields.pop("phone_no")
            if "address" in self.fields: self.fields.pop("address")
            if "region" in self.fields: self.fields.pop("region")
            if "allow_location" in self.fields: self.fields.pop("allow_location")
            if "latitude" in self.fields: self.fields.pop("latitude")
            if "longitude" in self.fields: self.fields.pop("longitude")

        elif self.role == User.Role.SUPER_ADMIN:
            # Super Admin usually created by management command or other super admin
            if "phone_no" in self.fields: self.fields.pop("phone_no")
            if "address" in self.fields: self.fields.pop("address")
            if "region" in self.fields: self.fields.pop("region")
            if "department" in self.fields: self.fields.pop("department")
            if "allow_location" in self.fields: self.fields.pop("allow_location")
            if "latitude" in self.fields: self.fields.pop("latitude")
            if "longitude" in self.fields: self.fields.pop("longitude")

    def clean_phone_no(self):
        phone_no = self.cleaned_data.get("phone_no")
        if phone_no:
            # FIXED: Validate exactly 10 digits starting with 6-9 and prevent all same digits (like 0000000000)
            if not re.match(r'^[6-9]\d{9}$', phone_no):
                raise ValidationError("Phone number must be 10 digits and start with 6-9.")
            if len(set(phone_no)) == 1:
                raise ValidationError("Invalid phone number format.")
        return phone_no

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if password:
            # FIXED: Password strength enforcement (length, upper, lower, digit, special)
            if len(password) < 8:
                raise ValidationError("Password must be at least 8 characters long.")
            if not any(c.isupper() for c in password):
                raise ValidationError("Password must contain at least one uppercase letter.")
            if not any(c.islower() for c in password):
                raise ValidationError("Password must contain at least one lowercase letter.")
            if not any(c.isdigit() for c in password):
                raise ValidationError("Password must contain at least one digit.")
            if not any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?/" for c in password):
                raise ValidationError("Password must contain at least one special character.")
        return password

    def clean_address(self):
        address = self.cleaned_data.get("address")
        if address:
            # FIXED: Prevent XSS by escaping user input
            return escape(address)
        return address

    def clean_full_name(self):
        full_name = self.cleaned_data.get("full_name")
        if full_name:
            # FIXED: Prevent XSS by escaping user input
            return escape(full_name)
        return full_name

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        # FIXED: Confirm password validation on backend (must match)
        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")

        # Geolocation logic
        allow_location = cleaned_data.get("allow_location")
        latitude = cleaned_data.get("latitude")
        longitude = cleaned_data.get("longitude")

        if not allow_location:
            # FIXED: Privacy compliance - remove location data if consent not given
            cleaned_data["latitude"] = None
            cleaned_data["longitude"] = None
        elif latitude is not None and longitude is not None:
            # FIXED: Secure handling of latitude/longitude (validate range)
            if not (-90 <= latitude <= 90):
                self.add_error("latitude", "Latitude must be between -90 and 90.")
            if not (-180 <= longitude <= 180):
                self.add_error("longitude", "Longitude must be between -180 and 180.")

        return cleaned_data


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)


# ---------------------------
# ADMIN DASHBOARD: USER MANAGEMENT
# ---------------------------
class UserEditForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(
        choices=User.Role.choices
    )
    is_active = forms.BooleanField(required=False)
    is_approved = forms.BooleanField(required=False)

    phone_no = forms.CharField(max_length=15, required=False)
    address = forms.CharField(widget=forms.Textarea, required=False)
    region = forms.CharField(max_length=100, required=False)
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

    def clean_role(self):
        role = self.cleaned_data.get("role")
        if self.request and self.request.user.role == User.Role.DEPT_ADMIN:
            if role in [User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN]:
                raise forms.ValidationError("You do not have permission to assign this role.")
        return role

    def clean_department(self):
        department = self.cleaned_data.get("department")
        if self.request and self.request.user.role == User.Role.DEPT_ADMIN:
            if department and department != self.request.user.department:
                raise forms.ValidationError("You can only assign users to your own department.")
        return department

    def clean_phone_no(self):
        phone_no = self.cleaned_data.get("phone_no")
        if phone_no:
            # FIXED: Validate exactly 10 digits starting with 6-9 and prevent fake numbers
            if not re.match(r'^[6-9]\d{9}$', phone_no):
                raise ValidationError("Phone number must be 10 digits and start with 6-9.")
            if len(set(phone_no)) == 1:
                raise ValidationError("Invalid phone number format.")
        return phone_no

    def clean_address(self):
        address = self.cleaned_data.get("address")
        if address:
            # FIXED: Prevent XSS by escaping user input
            return escape(address)
        return address

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if username:
            # FIXED: Prevent XSS by escaping user input
            return escape(username)
        return username

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")

        if role == User.Role.CITIZEN:
            if not cleaned_data.get("phone_no") or not cleaned_data.get("address"):
                raise forms.ValidationError("Citizen requires phone number and address.")

        if role == User.Role.OFFICER:
            if not cleaned_data.get("region") or not cleaned_data.get("department"):
                raise forms.ValidationError("OfficerProfile requires region and department.")

        return cleaned_data


class UserProfileForm(forms.ModelForm):
    full_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    phone_no = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    address = forms.CharField(max_length=200, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    city = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    state = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['email']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['email'].disabled = True
            self.fields['full_name'].initial = self.instance.full_name
            self.fields['phone_no'].initial = self.instance.phone_no
            self.fields['address'].initial = self.instance.address
            self.fields['city'].initial = self.instance.city
            self.fields['state'].initial = self.instance.state

    def save(self, commit=True):
        user = super().save(commit=False)
        user.full_name = self.cleaned_data.get('full_name', '')
        user.phone_no = self.cleaned_data.get('phone_no', '')
        user.address = self.cleaned_data.get('address', '')
        user.city = self.cleaned_data.get('city', '')
        user.state = self.cleaned_data.get('state', '')
        if commit:
            user.save()
            if hasattr(user, 'citizen_profile'):
                user.citizen_profile.full_name = user.full_name
                user.citizen_profile.phone = user.phone_no
                user.citizen_profile.address = user.address
                user.citizen_profile.save()
            if hasattr(user, 'officer'):
                user.officer.full_name = user.full_name
                user.officer.phone = user.phone_no
                user.officer.address = user.address
                user.officer.city = user.city
                user.officer.save()
            if hasattr(user, 'admin_profile'):
                user.admin_profile.full_name = user.full_name
                user.admin_profile.phone_no = user.phone_no
                user.admin_profile.save()
        return user

    def clean_email(self):
        # Always return the original email from the instance
        return self.instance.email

    def clean_phone_no(self):
        phone_no = self.cleaned_data.get("phone_no")
        if phone_no:
            if not re.match(r'^[6-9]\d{9}$', phone_no):
                raise ValidationError("Phone number must be 10 digits and start with 6-9.")
        return phone_no

from django.contrib.auth.hashers import make_password, check_password, identify_hasher
import secrets
import string

# ... (rest of imports)

class ProfilePasswordChangeForm(forms.ModelForm):
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'New Password'}),
        required=False,
        help_text="Leave blank to keep current password."
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm New Password'}),
        required=False
    )
    generate_temp_password = forms.BooleanField(
        required=False,
        label="Generate Temporary Password",
        help_text="If checked, a secure random password will be generated and applied."
    )

    class Meta:
        abstract = True # This doesn't work for ModelForm Meta, but I'll use subclasses

    def clean_new_password(self):
        password = self.cleaned_data.get("new_password")
        if password:
            if len(password) < 8:
                raise ValidationError("Password must be at least 8 characters long.")
            if not any(c.isupper() for c in password):
                raise ValidationError("Password must contain at least one uppercase letter.")
            if not any(c.islower() for c in password):
                raise ValidationError("Password must contain at least one lowercase letter.")
            if not any(c.isdigit() for c in password):
                raise ValidationError("Password must contain at least one digit.")
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")
        generate_temp = cleaned_data.get("generate_temp_password")

        if generate_temp:
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            temp_pw = ''.join(secrets.choice(alphabet) for i in range(12))
            cleaned_data["new_password"] = temp_pw
        elif password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")
        
        return cleaned_data

    def save(self, commit=True):
        profile = super().save(commit=False)
        new_pw = self.cleaned_data.get("new_password")
        
        if new_pw:
            hashed_pw = make_password(new_pw)
            profile.password_hash = hashed_pw
            if hasattr(profile, 'user'):
                profile.user.password = hashed_pw
                profile.user.save()
        if commit:
            profile.save()
        return profile

from .models import CitizenProfile, OfficerProfile, AdminProfile

class CitizenPasswordChangeForm(ProfilePasswordChangeForm):
    class Meta:
        model = CitizenProfile
        fields = ['username', 'email', 'is_active']

class OfficerPasswordChangeForm(ProfilePasswordChangeForm):
    class Meta:
        model = OfficerProfile
        fields = ['username', 'email', 'is_active']

class AdminPasswordChangeForm(ProfilePasswordChangeForm):
    class Meta:
        model = AdminProfile
        fields = ['username', 'email', 'is_active']
