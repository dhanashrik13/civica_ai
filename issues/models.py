from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from accounts.models import Department, OfficerProfile

User = settings.AUTH_USER_MODEL

from .validators import validate_secure_image

from django_softdelete.models import SoftDeleteModel
from simple_history.models import HistoricalRecords

class Issue(SoftDeleteModel, models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ASSIGNED = "assigned", "Assigned"
        RESOLVED = "resolved", "Resolved"

    class Priority(models.TextChoices):
        EMERGENCY = "emergency", "Emergency (Life/Safety)"
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    class Category(models.TextChoices):
        # OFFICIAL GOVERNMENT DEPARTMENTS
        PWD = "pwd", "Public Works Department (PWD)"
        WATER_SUPPLY = "water_supply", "Water Supply Department"
        SANITATION = "sanitation", "Sanitation Department"
        ELECTRICITY = "electricity", "Electricity Department"
        ROAD_TRANSPORT = "road_transport", "Road & Transport Department"
        DRAINAGE_SEWERAGE = "drainage_sewerage", "Drainage & Sewerage Department"
        HEALTH = "health", "Health Department"
        ENVIRONMENT = "environment", "Environment Department"
        URBAN_PLANNING = "urban_planning", "Urban Planning Department"
        DISASTER_MANAGEMENT = "disaster_management", "Disaster Management Department"
        TRAFFIC_POLICE = "traffic_police", "Traffic Police Department"
        MUNICIPAL_ENGINEERING = "municipal_engineering", "Municipal Engineering Department"

        # LEGACY CATEGORIES (Mapped to Departments for compatibility)
        POTHOLE = "pothole", "Public Works Department (PWD) [Legacy]"
        ROAD_DAMAGE = "road_damage", "Public Works Department (PWD) [Legacy]"
        WATER_LEAKAGE = "water_leakage", "Water Supply Department [Legacy]"
        STREET_LIGHT = "street_light", "Electricity Department [Legacy]"
        GARBAGE = "garbage", "Sanitation Department [Legacy]"
        DRAINAGE = "drainage", "Drainage & Sewerage Department [Legacy]"

    class GovernanceScope(models.TextChoices):
        VILLAGE = "village", "Village"
        WARD = "ward", "Ward"
        TALUKA = "taluka", "Taluka"
        CITY = "city", "City"
        DISTRICT = "district", "District"

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=100, choices=Category.choices)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    governance_scope = models.CharField(
        max_length=20, 
        choices=GovernanceScope.choices, 
        default=GovernanceScope.VILLAGE,
        db_index=True
    )
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="issues")
    location = models.ForeignKey("accounts.Location", null=True, blank=True, on_delete=models.SET_NULL)
    location_source = models.CharField(max_length=20, choices=[("gps", "GPS"), ("address", "Address"), ("manual_city", "Manual City")], default="manual_city")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    reported_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="issues_reported")
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="issues_assigned_by")
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="issues_updated_by")
    status_changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="issues_status_changed_by")
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="resolved_issues")
    assigned_to = models.ForeignKey(OfficerProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_issues")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    zone = models.CharField(max_length=100, null=True, blank=True)
    ward = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    village = models.CharField(max_length=100, null=True, blank=True)
    taluka = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    district = models.CharField(max_length=100, null=True, blank=True, db_index=True)

    manual_override = models.BooleanField(default=False, help_text="True if an administrator manually changed the AI's assignment or status")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=['priority', 'status', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['department', 'status']),
            models.Index(fields=['location', 'status']),
            models.Index(fields=['district', 'status']),
            models.Index(fields=['city', 'status']),
            models.Index(fields=['ward', 'status']),
            models.Index(fields=['taluka', 'status']),
            models.Index(fields=['latitude', 'longitude']),
        ]

    # COMPATIBILITY BRIDGES FOR DECOMPOSED COLD FIELDS
    @property
    def description(self): 
        try: return self.metadata.description
        except (IssueMetadata.DoesNotExist, AttributeError): return getattr(self, '_deferred_description', '')
    @description.setter
    def description(self, value): self._deferred_description = value

    @property
    def photo1(self): 
        try: return self.metadata.photo1
        except (IssueMetadata.DoesNotExist, AttributeError): return getattr(self, '_deferred_photo1', None)
    @photo1.setter
    def photo1(self, value): self._deferred_photo1 = value

    @property
    def photo2(self): 
        try: return self.metadata.photo2
        except (IssueMetadata.DoesNotExist, AttributeError): return getattr(self, '_deferred_photo2', None)
    @photo2.setter
    def photo2(self, value): self._deferred_photo2 = value

    @property
    def photo3(self): 
        try: return self.metadata.photo3
        except (IssueMetadata.DoesNotExist, AttributeError): return getattr(self, '_deferred_photo3', None)
    @photo3.setter
    def photo3(self, value): self._deferred_photo3 = value

    @property
    def resolved_photo(self): 
        try: return self.metadata.resolved_photo
        except (IssueMetadata.DoesNotExist, AttributeError): return getattr(self, '_deferred_resolved_photo', None)
    @resolved_photo.setter
    def resolved_photo(self, value): self._deferred_resolved_photo = value

    @property
    def proof_image(self): 
        try: return self.metadata.proof_image
        except (IssueMetadata.DoesNotExist, AttributeError): return getattr(self, '_deferred_proof_image', None)
    @proof_image.setter
    def proof_image(self, value): self._deferred_proof_image = value

    @property
    def resolution_image(self): 
        try: return self.metadata.resolution_image
        except (IssueMetadata.DoesNotExist, AttributeError): return getattr(self, '_deferred_resolution_image', None)
    @resolution_image.setter
    def resolution_image(self, value): self._deferred_resolution_image = value

    @property
    def risk_score(self): 
        try: return self.ai_context.risk_score
        except (IssueAIContext.DoesNotExist, AttributeError): return getattr(self, '_deferred_risk_score', 0)
    @risk_score.setter
    def risk_score(self, value): self._deferred_risk_score = value

    @property
    def intelligence_data(self): 
        try: return self.ai_context.intelligence_data
        except (IssueAIContext.DoesNotExist, AttributeError): return getattr(self, '_deferred_intelligence_data', {})
    @intelligence_data.setter
    def intelligence_data(self, value): self._deferred_intelligence_data = value

    @property
    def assignment_explanation(self): 
        try: return self.ai_context.assignment_explanation
        except (IssueAIContext.DoesNotExist, AttributeError): return getattr(self, '_deferred_assignment_explanation', '')
    @assignment_explanation.setter
    def assignment_explanation(self, value): self._deferred_assignment_explanation = value

    @property
    def idempotency_key(self): 
        try: return self.ai_context.idempotency_key
        except (IssueAIContext.DoesNotExist, AttributeError): return getattr(self, '_deferred_idempotency_key', None)
    @idempotency_key.setter
    def idempotency_key(self, value): self._deferred_idempotency_key = value

    @property
    def is_enriched(self): 
        try: return self.ai_context.is_enriched
        except (IssueAIContext.DoesNotExist, AttributeError): return getattr(self, '_deferred_is_enriched', False)
    @is_enriched.setter
    def is_enriched(self, value): self._deferred_is_enriched = value

    @property
    def sla_multiplier(self): 
        try: return self.ai_context.sla_multiplier
        except (IssueAIContext.DoesNotExist, AttributeError): return getattr(self, '_deferred_sla_multiplier', 1.0)
    @sla_multiplier.setter
    def sla_multiplier(self, value): self._deferred_sla_multiplier = value

    def __init__(self, *args, **kwargs):
        # Intercept cold fields for compatibility
        self._deferred_description = kwargs.pop('description', '')
        self._deferred_photo1 = kwargs.pop('photo1', None)
        self._deferred_photo2 = kwargs.pop('photo2', None)
        self._deferred_photo3 = kwargs.pop('photo3', None)
        self._deferred_resolved_photo = kwargs.pop('resolved_photo', None)
        self._deferred_proof_image = kwargs.pop('proof_image', None)
        self._deferred_resolution_image = kwargs.pop('resolution_image', None)
        
        self._deferred_risk_score = kwargs.pop('risk_score', 0)
        self._deferred_intelligence_data = kwargs.pop('intelligence_data', {})
        self._deferred_assignment_explanation = kwargs.pop('assignment_explanation', '')
        self._deferred_idempotency_key = kwargs.pop('idempotency_key', None)
        self._deferred_is_enriched = kwargs.pop('is_enriched', False)
        self._deferred_sla_multiplier = kwargs.pop('sla_multiplier', 1.0)
        
        super().__init__(*args, **kwargs)
        self._old_assigned_to_id = self.assigned_to_id

    def save(self, *args, **kwargs):
        from accounts.middleware import get_current_user, is_rbac_bypassed
        from django.contrib.auth import get_user_model
        from accounts.utils_async import dispatch_task_transactional
        UserModel = get_user_model()
        
        # 0. GIS SYNC: Ensure string fields match Location object if present
        if self.location_id:
            curr = self.location
            # Reset all hierarchy strings first
            self.district = self.taluka = self.village = self.city = self.ward = self.zone = ""
            while curr:
                if curr.type == 'village': self.village = curr.name
                elif curr.type == 'taluka': self.taluka = curr.name
                elif curr.type == 'district': self.district = curr.name
                elif curr.type == 'city': self.city = curr.name
                elif curr.type == 'zone': self.zone = curr.name
                elif curr.type == 'ward': self.ward = curr.name
                curr = curr.parent

        # 1. LIGHTWEIGHT VALIDATION
        if self.reported_by and self.reported_by.role == UserModel.Role.OFFICER:
            raise ValidationError(f"Officers cannot report issues.")
        
        user = get_current_user()

        # 2. CORE STATE SYNC
        if not self.pk:
            from .utils import get_priority
            self.priority = get_priority(self.category, self.description)
            
            # Automatically assign department based on category
            if not self.department_id:
                from .services import map_category_to_department
                self.department = map_category_to_department(self.category)

        # Integrity Check: Prevent direct assigned_to modification bypassing secure_issue_assignment
        if self.pk and self.assigned_to_id != getattr(self, '_old_assigned_to_id', self.assigned_to_id):
             if getattr(self, '_assigned_via_secure_service', False) is not True:
                 raise ValidationError("Direct assignment modification is prohibited. All assignments must pass through secure_issue_assignment().")


        if self.pk and not is_rbac_bypassed():
            if user and hasattr(user, 'id'):
                self.updated_by = user

        if self.assigned_to_id and self.status == self.Status.PENDING:
            self.status = self.Status.ASSIGNED
        elif not self.assigned_to_id and self.status == self.Status.ASSIGNED:
            self.status = self.Status.PENDING

        if self.status == self.Status.RESOLVED:
            if not self.resolved_at: self.resolved_at = timezone.now()
            if not self.resolved_by and user and hasattr(user, 'id'):
                self.resolved_by = user

        # 3. PERSIST CORE RECORD
        is_new = not self.pk
        super().save(*args, **kwargs)
        
        # 3.5 SYNC DECOMPOSED MODELS (Model Verticalization Layer)
        with transaction.atomic():
            metadata, _ = IssueMetadata.objects.get_or_create(issue=self)
            if hasattr(self, '_deferred_description'): metadata.description = self._deferred_description
            if hasattr(self, '_deferred_photo1'): metadata.photo1 = self._deferred_photo1
            if hasattr(self, '_deferred_photo2'): metadata.photo2 = self._deferred_photo2
            if hasattr(self, '_deferred_photo3'): metadata.photo3 = self._deferred_photo3
            if hasattr(self, '_deferred_resolved_photo'): metadata.resolved_photo = self._deferred_resolved_photo
            if hasattr(self, '_deferred_proof_image'): metadata.proof_image = self._deferred_proof_image
            if hasattr(self, '_deferred_resolution_image'): metadata.resolution_image = self._deferred_resolution_image
            metadata.save()
            
            ai_context, _ = IssueAIContext.objects.get_or_create(issue=self)
            if hasattr(self, '_deferred_risk_score'): ai_context.risk_score = self._deferred_risk_score
            if hasattr(self, '_deferred_intelligence_data'): ai_context.intelligence_data = self._deferred_intelligence_data
            if hasattr(self, '_deferred_assignment_explanation'): ai_context.assignment_explanation = self._deferred_assignment_explanation
            if hasattr(self, '_deferred_idempotency_key'): ai_context.idempotency_key = self._deferred_idempotency_key
            if hasattr(self, '_deferred_is_enriched'): ai_context.is_enriched = self._deferred_is_enriched
            if hasattr(self, '_deferred_sla_multiplier'): ai_context.sla_multiplier = self._deferred_sla_multiplier
            ai_context.save()

        # 4. TRIGGER ASYNC ENRICHMENT (WP-C2)
        if is_new or not self.is_enriched:
            # INFRASTRUCTURE FAILSAFE: 
            # If the outbox is backlogged, we perform a lightweight synchronous assignment
            # so the citizen/officer aren't left in the dark while enrichment catches up.
            from accounts.utils_async import check_async_health
            try:
                health = check_async_health()
                if not health['is_healthy'] and not self.assigned_to_id:
                    from .services import auto_assign_issue
                    import logging
                    logging.getLogger(__name__).warning(f"Async Infrastructure LAGGING (Backlog: {health['outbox_backlog']}). Triggering failsafe sync assignment for Issue #{self.pk}")
                    auto_assign_issue(self)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failsafe Assignment Failed for Issue #{self.pk}: {e}")

            dispatch_task_transactional('issues.tasks.enrich_issue_context', args=[self.pk])

        # 5. HARDENED EVENT EMISSION (Deterministic Replay Boundary)
        from accounts.middleware import is_forensic_mode
        if not is_forensic_mode():
            # Get monotonic sequence number
            seq = IssueEvent.objects.filter(issue=self).count() + 1
            
            event_type = IssueEvent.Type.STATUS_CHANGED
            if is_new:
                event_type = IssueEvent.Type.CREATED
            elif getattr(self, '_old_assigned_to_id', None) != self.assigned_to_id:
                event_type = IssueEvent.Type.ASSIGNED
            elif self.status == self.Status.RESOLVED:
                event_type = IssueEvent.Type.RESOLVED

            try:
                # Correlation ID from middleware context if available
                correlation_id = getattr(user, 'trace_id', f"txn_{self.pk}_{timezone.now().timestamp()}")
                
                event = IssueEvent.objects.create(
                    issue=self,
                    event_type=event_type,
                    actor=user if user and hasattr(user, 'id') else None,
                    sequence_number=seq,
                    correlation_id=correlation_id,
                    payload={
                        "status": self.status,
                        "priority": self.priority,
                        "assigned_to_id": self.assigned_to_id,
                        "is_new": is_new
                    }
                )
                
                # TRIGGER PROJECTION ASYNC (CQRS)
                dispatch_task_transactional('issues.tasks.update_dashboard_projections', args=[event.pk])
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Event Emission Failed for Issue #{self.pk}: {e}")
        
        # Update tracker for next save in same lifecycle
        self._old_assigned_to_id = self.assigned_to_id

    @property
    def created_by(self): return self.reported_by
    @property
    def image(self): return self.photo1
    @property
    def area(self): return self.ward or self.village

    @property
    def sla_days(self):
        """Service Level Agreement days using denormalized multiplier (WP-H1 Fixed)."""
        base_sla = {"emergency": 0.5, "high": 2, "medium": 4, "low": 7}.get(self.priority, 5)
        return base_sla * self.sla_multiplier

    @property
    def is_overdue(self):
        """Returns True if the issue is not resolved and has passed its SLA."""
        if self.status == self.Status.RESOLVED:
            return False
        return (timezone.now() - self.created_at).days > self.sla_days

    @property
    def is_high_risk(self):
        """Identifies issues likely to become overdue (e.g., > 75% of SLA time elapsed)."""
        if self.status == self.Status.RESOLVED or self.is_overdue:
            return False
        elapsed_days = (timezone.now() - self.created_at).days
        return elapsed_days >= (self.sla_days * 0.75)

    @property
    def timeline_events(self):
        """Returns a sorted list of events (assignments, comments, status changes, and system alerts)."""
        events = []
        events.append({'type': 'reported', 'user': self.reported_by, 'time': self.created_at, 'text': 'Issue reported'})
        
        # 1. Forensic: Assignment Reasoning
        if self.assignment_explanation:
            events.append({
                'type': 'ai_governance', 
                'user': type('System', (), {'full_name': 'Governance AI', 'username': 'ai_gov'}), 
                'time': self.created_at, 
                'text': f"Autonomous Assignment: {self.assignment_explanation}",
                'meta': self.intelligence_data
            })

        for log in self.assignment_logs.all():
            events.append({'type': 'assigned', 'user': log.officer.user, 'time': log.assigned_at, 'text': f'Assigned to {log.officer.user.full_name}'})
            
        for comment in self.comments.all():
            events.append({'type': 'comment', 'user': comment.user, 'time': comment.created_at, 'text': comment.text})
            
        # 2. Forensic: Manual Overrides
        if self.manual_override:
            events.append({
                'type': 'human_override', 
                'user': self.updated_by or self.reported_by, 
                'time': self.updated_at, 
                'text': "Manual Administrative Override detected: Assignment/Status changed from AI recommendation."
            })

        if self.status == self.Status.RESOLVED and self.resolved_at:
            events.append({'type': 'resolved', 'user': self.resolved_by, 'time': self.resolved_at, 'text': 'Issue resolved'})
            
        # System-generated predictive events
        if self.is_high_risk:
            # Estimate risk detection time (e.g., 75% of SLA after creation)
            risk_time = self.created_at + timezone.timedelta(days=self.sla_days * 0.75)
            events.append({
                'type': 'system_alert', 
                'user': type('System', (), {'full_name': 'System', 'username': 'system'}), 
                'time': risk_time, 
                'text': f'Delay risk detected based on SLA. Confidence: {self.intelligence_data.get("confidence", "N/A")}%'
            })
            
        if self.is_overdue:
            overdue_time = self.created_at + timezone.timedelta(days=self.sla_days)
            events.append({'type': 'escalation', 'user': type('System', (), {'full_name': 'System', 'username': 'system'}), 'time': overdue_time, 'text': 'Escalation triggered: Issue is overdue.'})
            
        events.sort(key=lambda x: x['time'])
        return events

    def __str__(self): return self.title

class CategoryIntelligence(models.Model):
    category = models.CharField(max_length=100, unique=True, choices=Issue.Category.choices)
    avg_resolution_hours = models.FloatField(default=48.0)
    difficulty_score = models.FloatField(default=1.0) # Multiplier for SLA
    total_resolved = models.IntegerField(default=0)
    learning_stability = models.FloatField(default=0.9) # Smoothing factor
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self): return f"Intel: {self.category}"

class IntelligenceLog(models.Model):
    category = models.CharField(max_length=100)
    change_type = models.CharField(max_length=50) # 'difficulty', 'avg_time', etc.
    old_value = models.FloatField()
    new_value = models.FloatField()
    reason = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self): return f"Log: {self.category} - {self.change_type}"

class Comment(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return f"{self.user} - {self.issue}"

class EscalationAppeal(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        APPROVED = "approved", "Approved (Re-escalated)"
        REJECTED = "rejected", "Rejected"

    issue = models.OneToOneField(Issue, on_delete=models.CASCADE, related_name="appeal")
    citizen = models.ForeignKey(User, on_delete=models.CASCADE, related_name="appeals_filed")
    reason = models.TextField()
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="appeals_reviewed")
    review_comments = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Appeal for Issue #{self.issue.id} ({self.status})"

class IssueEmbedding(models.Model):
    """
    Local Vector Storage for Semantic Governance.
    Enables O(1) lookup of embeddings and local similarity checks.
    """
    issue = models.OneToOneField(Issue, on_delete=models.CASCADE, related_name="embedding")
    vector = models.JSONField(help_text="Semantic vector for clustering and duplicate detection")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['created_at']),
        ]

    def __str__(self): return f"Vector: Issue #{self.issue.id}"

class IssueMetadata(models.Model):
    issue = models.OneToOneField(Issue, on_delete=models.CASCADE, related_name="metadata")
    description = models.TextField(blank=True)
    photo1 = models.ImageField(upload_to="issue_photos/", null=True, blank=True, validators=[validate_secure_image])
    photo2 = models.ImageField(upload_to="issue_photos/", null=True, blank=True, validators=[validate_secure_image])
    photo3 = models.ImageField(upload_to="issue_photos/", null=True, blank=True, validators=[validate_secure_image])
    resolved_photo = models.ImageField(upload_to="resolved_photos/", null=True, blank=True, validators=[validate_secure_image])
    proof_image = models.ImageField(upload_to="proofs/", null=True, blank=True, validators=[validate_secure_image])
    resolution_image = models.ImageField(upload_to="resolutions/", null=True, blank=True, validators=[validate_secure_image])

class IssueAIContext(models.Model):
    issue = models.OneToOneField(Issue, on_delete=models.CASCADE, related_name="ai_context")
    risk_score = models.IntegerField(default=0, db_index=True)
    intelligence_data = models.JSONField(default=dict, blank=True)
    assignment_explanation = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=100, null=True, blank=True, unique=True)
    is_enriched = models.BooleanField(default=False, db_index=True)
    sla_multiplier = models.FloatField(default=1.0)

class IssueEvent(models.Model):
    """
    Append-only Domain Event Stream.
    Hardened for monotonic sequencing, deterministic replay, and schema evolution.
    """
    class Type(models.TextChoices):
        CREATED = "created", "Issue Created"
        ASSIGNED = "assigned", "Officer Assigned"
        ESCALATED = "escalated", "Issue Escalated"
        RESOLVED = "resolved", "Issue Resolved"
        STATUS_CHANGED = "status_changed", "Status Changed"
        PRIORITY_CHANGED = "priority_changed", "Priority Changed"
        METADATA_UPDATED = "metadata_updated", "Metadata Updated"
        OFFICER_OVERLOADED = "officer_overloaded", "Officer Overloaded"

    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="domain_events")
    event_type = models.CharField(max_length=50, choices=Type.choices, db_index=True)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Traceability
    sequence_number = models.PositiveIntegerField(db_index=True, help_text="Monotonic order per issue")
    correlation_id = models.CharField(max_length=100, db_index=True, null=True, blank=True)
    causation_id = models.CharField(max_length=100, null=True, blank=True)
    version = models.IntegerField(default=1)
    
    payload = models.JSONField(default=dict, help_text="Delta of changes or specific event context")

    class Meta:
        ordering = ["issue", "sequence_number"]
        unique_together = [["issue", "sequence_number"]]
        indexes = [
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['correlation_id']),
        ]

    def __str__(self):
        return f"#{self.sequence_number} {self.get_event_type_display()} - Issue #{self.issue_id} @ {self.timestamp}"

class ProjectionCheckpoint(models.Model):
    """
    Tracks the last processed event per projection/subsystem.
    Ensures idempotency and replay safety.
    """
    projection_name = models.CharField(max_length=100, unique=True)
    last_event_id = models.IntegerField(default=0)
    last_processed_at = models.DateTimeField(auto_now=True)

    def __str__(self): return f"Checkpoint: {self.projection_name} @ {self.last_event_id}"


