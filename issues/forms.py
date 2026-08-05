from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import escape  # FIXED: For XSS prevention
from accounts.models import OfficerProfile
from issues.models import Issue


# ---------------------------
# REPORT GENERATION FORM
# ---------------------------
class ReportForm(forms.ModelForm):
    # DECOMPOSED COLD FIELDS (Non-model fields in Form)
    description = forms.CharField(widget=forms.Textarea())
    photo1 = forms.ImageField(required=True)
    photo2 = forms.ImageField(required=False)
    photo3 = forms.ImageField(required=False)
    
    district = forms.CharField(required=False, widget=forms.HiddenInput())
    taluka = forms.CharField(required=False, widget=forms.HiddenInput())
    latitude = forms.FloatField(required=False, widget=forms.HiddenInput())
    longitude = forms.FloatField(required=False, widget=forms.HiddenInput())
    village = forms.CharField(required=False, widget=forms.HiddenInput())
    ward = forms.CharField(required=False, widget=forms.HiddenInput())
    city = forms.CharField(required=False, widget=forms.HiddenInput())
    location = forms.CharField(
        required=False, 
        widget=forms.TextInput(attrs={"readonly": "readonly", "class": "form-control"})
    )

    class Meta:
        model = Issue
        fields = [
            "title",
            "category",
            "governance_scope",
            "latitude",
            "longitude",
            "district",
            "taluka",
            "village",
            "ward",
            "city",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show official departments, not legacy labels
        official_categories = [
            "pwd", "water_supply", "sanitation", "electricity", 
            "road_transport", "drainage_sewerage", "health", "environment", 
            "urban_planning", "disaster_management", "traffic_police", "municipal_engineering"
        ]
        self.fields['category'].choices = [
            choice for choice in Issue.Category.choices if choice[0] in official_categories
        ]


    def clean_district(self):
        district = self.cleaned_data.get("district")
        if district:
            from accounts.models import Location
            canonical_districts = list(Location.objects.filter(type='district').values_list('name', flat=True))
            normalized_val = district.strip()
            
            # Simple alias mapping for known variants
            aliases = {
                "Ahmednagar": "Ahilyanagar",
                "Sambhajinagar": "Chhatrapati Sambhajinagar",
                "Aurangabad": "Chhatrapati Sambhajinagar",
                "Dharashiv": "Dharashiv", # Canonical
                "Osmanabad": "Dharashiv"
            }
            
            if normalized_val in aliases:
                normalized_val = aliases[normalized_val]
            
            if normalized_val not in canonical_districts:
                 # Check case-insensitive
                 match = next((d for d in canonical_districts if d.lower() == normalized_val.lower()), None)
                 if match:
                     normalized_val = match
                 else:
                     raise ValidationError(f"Invalid district: '{district}'. Please select a valid jurisdiction.")
            
            return normalized_val
        return district

    def clean_description(self):
        description = self.cleaned_data.get("description")
        if description:
            # FIXED: Prevent XSS
            return escape(description.strip())
        return description

    def clean_location(self):
        location = self.cleaned_data.get("location")
        if location:
            # FIXED: Prevent XSS
            return escape(location.strip())
        return location

    def clean_latitude(self):
        lat = self.cleaned_data.get("latitude")
        if lat is not None:
            # FIXED: Validate latitude range
            if not (-90 <= lat <= 90):
                raise forms.ValidationError("Invalid latitude.")
        return lat

    def clean_longitude(self):
        lng = self.cleaned_data.get("longitude")
        if lng is not None:
            # FIXED: Validate longitude range
            if not (-180 <= lng <= 180):
                raise forms.ValidationError("Invalid longitude.")
        return lng

    def clean(self):
        cleaned_data = super().clean()
        title = cleaned_data.get("title") or ""
        description = cleaned_data.get("description") or ""
        scope = cleaned_data.get("governance_scope")
        district = (cleaned_data.get("district") or "").strip()
        taluka = (cleaned_data.get("taluka") or "").strip()
        village = (cleaned_data.get("village") or "").strip()
        ward = (cleaned_data.get("ward") or "").strip()
        city = (cleaned_data.get("city") or "").strip()

        if len(title) < 5:
            self.add_error("title", "Title must be at least 5 characters long.")

        if len(description) < 10:
            self.add_error("description", "Description must be at least 10 characters long.")

        # GOVERNANCE SCOPE VALIDATION
        if scope == Issue.GovernanceScope.VILLAGE and not village:
            self.add_error("village", "Village is required for Village-level scope.")
        
        if scope == Issue.GovernanceScope.WARD and not ward:
            self.add_error("ward", "Ward/Area selection is required for Ward-level scope.")
            
        if scope == Issue.GovernanceScope.TALUKA and not taluka:
            self.add_error("taluka", "Taluka selection is required for Taluka-level scope.")
            
        if scope == Issue.GovernanceScope.DISTRICT and not district:
            self.add_error("district", "District selection is required for District-level scope.")

        # Maintain backward compatibility for mandatory base fields if scope is Village (default)
        if not scope or scope == Issue.GovernanceScope.VILLAGE:
            if not district:
                self.add_error("district", "Please select a district.")
            if not taluka:
                self.add_error("taluka", "Please select a taluka.")
            if not village:
                self.add_error("village", "Please select a village.")

        if not cleaned_data.get("photo1"):
            self.add_error("photo1", "At least one image is required.")

        for field_name in ("photo1", "photo2", "photo3"):
            image = cleaned_data.get(field_name)
            if image and image.size > 5 * 1024 * 1024:
                self.add_error(field_name, "Each image must be under 5 MB.")

        # Escape remaining hidden fields
        if district: cleaned_data["district"] = escape(district)
        if taluka: cleaned_data["taluka"] = escape(taluka)
        if village: cleaned_data["village"] = escape(village)
        if ward: cleaned_data["ward"] = escape(ward)
        if city: cleaned_data["city"] = escape(city)

        return cleaned_data



class AdminIssueForm(forms.ModelForm):
    description = forms.CharField(widget=forms.Textarea())

    class Meta:
        model = Issue
        fields = [
            "title",
            "category",
            "priority",
            "status",
            "assigned_to",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show official departments, not legacy labels
        official_categories = [
            "pwd", "water_supply", "sanitation", "electricity", 
            "road_transport", "drainage_sewerage", "health", "environment", 
            "urban_planning", "disaster_management", "traffic_police", "municipal_engineering"
        ]
        self.fields['category'].choices = [
            choice for choice in Issue.Category.choices if choice[0] in official_categories
        ]

    def clean_title(self):
        title = self.cleaned_data.get("title")
        if title:
            return escape(title.strip())
        return title

    def clean_description(self):
        description = self.cleaned_data.get("description")
        if description:
            return escape(description.strip())
        return description


# ---------------------------
# ISSUE MANAGEMENT
# ---------------------------
class IssueForm(forms.ModelForm):
    description = forms.CharField(widget=forms.Textarea())

    class Meta:
        model = Issue
        fields = ["title"]

    def clean_title(self):
        title = self.cleaned_data.get("title")
        if title:
            return escape(title.strip())
        return title

    def clean_description(self):
        description = self.cleaned_data.get("description")
        if description:
            return escape(description.strip())
        return description



class IssueAssignmentForm(forms.Form):
    officer = forms.ModelChoiceField(
        queryset=OfficerProfile.objects.filter(
            user__role="officer",
            is_active=True,
        ).select_related("user"),
        required=True,
        label="Assign to OfficerProfile"
    )

class IssueStatusForm(forms.ModelForm):
    class Meta:
        model = Issue
        fields = ["status"]
