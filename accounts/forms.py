from django import forms
from .models import Citizen, Officer, Admin, Issue, Department


# ---------------------------
# AUTHENTICATION & REGISTRATION
# ---------------------------
class RegisterForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=True)

    def __init__(self, *args, **kwargs):
        role = kwargs.pop('role', None)
        super().__init__(*args, **kwargs)

        # Dynamically add role-specific fields
        if role == 'Citizen':
            self.fields['phone_no'] = forms.CharField(max_length=15, required=True)
            self.fields['address'] = forms.CharField(widget=forms.Textarea, required=True)
        elif role == 'Officer':
            self.fields['region'] = forms.CharField(max_length=100, required=True)
            self.fields['department'] = forms.ModelChoiceField(
                queryset=Department.objects.all(),
                required=True
            )
        elif role == 'Admin':
            self.fields['access_level'] = forms.CharField(
                max_length=50,
                required=False,
                initial='superuser',
                disabled=True
            )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match!")

        return cleaned_data


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)


# ---------------------------
# ADMIN DASHBOARD: USER MANAGEMENT
# ---------------------------
class UserEditForm(forms.Form):
    # Common fields
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    is_active = forms.BooleanField(required=False)
    is_approved = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        role = kwargs.pop('role', None)
        super().__init__(*args, **kwargs)

        if role == 'Citizen':
            self.fields['phone_no'] = forms.CharField(max_length=15, required=True)
            self.fields['address'] = forms.CharField(widget=forms.Textarea, required=True)
        elif role == 'Officer':
            self.fields['region'] = forms.CharField(max_length=100, required=True)
            self.fields['department'] = forms.ModelChoiceField(
                queryset=Department.objects.all(),
                required=True
            )
        # Admin fields skipped as usually fixed



# ---------------------------
# DEPARTMENT MANAGEMENT
# ---------------------------
class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'description']


# ---------------------------
# FEEDBACK MANAGEMENT (OPTIONAL)
# ---------------------------
class FeedbackForm(forms.Form):
    message = forms.CharField(widget=forms.Textarea, required=True)
    rating = forms.IntegerField(min_value=1, max_value=5, required=False)

