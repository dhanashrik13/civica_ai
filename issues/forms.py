
# ---------------------------
# REPORT GENERATION FORM (OPTIONAL)
# ---------------------------
from django import forms

from accounts.models import Issue, Officer


class ReportForm(forms.ModelForm):
    CATEGORY_CHOICES = [
        ('roads', 'Roads'),
        ('water', 'Water Supply'),
        ('electricity', 'Electricity'),
        ('waste', 'Waste Management'),
        ('public_safety', 'Public Safety'),
        ('other', 'Other'),
    ]

    location = forms.CharField(max_length=255, required=True, help_text="Enter the location of the issue")
    category = forms.ChoiceField(choices=CATEGORY_CHOICES, required=True)
    photo1 = forms.ImageField(required=False)
    photo2 = forms.ImageField(required=False)
    photo3 = forms.ImageField(required=False)

    class Meta:
        model = Issue
        fields = ['title', 'description', 'category', 'location', 'photo1', 'photo2', 'photo3']



# ---------------------------
# ISSUE MANAGEMENT
# ---------------------------
class IssueForm(forms.ModelForm):
    class Meta:
        model = Issue
        fields = ['title', 'description']


class IssueAssignmentForm(forms.Form):
    officer = forms.ModelChoiceField(
        queryset=Officer.objects.all(),
        required=True,
        label="Assign to Officer"
    )


class IssueStatusForm(forms.Form):
    status = forms.ChoiceField(
        choices=Issue.STATUS_CHOICES,
        required=True
    )
