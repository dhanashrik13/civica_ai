import time
import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import User, OfficerProfile, AuditLog, Incident
from issues.models import Issue
from django.utils import timezone
from accounts.services import SecurityAuditEngine

class Command(BaseCommand):
    help = 'Executes security war games to verify RBAC and fraud containment.'

    def add_arguments(self, parser):
        parser.add_argument('--rbac-bypass', action='store_true', help='Simulate RBAC bypass attempt')
        parser.add_argument('--fraud-surge', action='store_true', help='Simulate mass fraud attack')
        parser.add_argument('--privilege-escalation', action='store_true', help='Simulate admin escalation attempt')

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("!!! INITIATING SECURITY WAR GAME !!!"))
        
        if options['rbac_bypass']:
            self._simulate_rbac_bypass()
        elif options['fraud_surge']:
            self._simulate_fraud_surge()
        elif options['privilege_escalation']:
            self._simulate_privilege_escalation()
        else:
            self.stdout.write(self.style.ERROR("No war game flag provided."))

    def _simulate_rbac_bypass(self):
        self.stdout.write("Simulating RBAC Bypass Attempt (Cross-District Assignment)...")
        # Find a Pune officer and a Nagpur issue
        pune_officer = OfficerProfile.objects.filter(district__iexact='Pune').first()
        nagpur_issue = Issue.objects.filter(district__iexact='Nagpur').first()
        
        if not pune_officer or not nagpur_issue:
            self.stdout.write(self.style.ERROR("Incomplete data for drill. Seed Pune/Nagpur first."))
            return

        try:
            nagpur_issue.assigned_to = pune_officer
            nagpur_issue.save()
            self.stdout.write(self.style.ERROR("VULNERABILITY: RBAC Bypass Successful!"))
        except Exception as e:
            self.stdout.write(self.style.SUCCESS(f"CONTAINED: RBAC Enforcement blocked assignment. Error: {str(e)}"))
            AuditLog.objects.create(
                action='security_alert',
                resource_type='Issue',
                resource_id=str(nagpur_issue.id),
                details={"attempt": "Cross-district assignment", "error": str(e)}
            )

    def _simulate_fraud_surge(self):
        self.stdout.write("Simulating Mass Fraud Reporting Surge...")
        citizen = User.objects.filter(role='citizen').first()
        if not citizen: return

        results = SecurityAuditEngine.simulate_report_storm(citizen, "Pune")
        
        if results['contained']:
            self.stdout.write(self.style.SUCCESS(f"CONTAINED: Fraud engine detected and isolated the storm."))
            self.stdout.write(f"Reason: {results['containment_reason']}")
        else:
            self.stdout.write(self.style.ERROR("VULNERABILITY: Fraud storm bypassed filters!"))
            
        Incident.objects.create(
            title="SECURITY WAR GAME: FRAUD SURGE",
            severity="p1",
            incident_type="FRAUD_ATTACK",
            description=f"Simulated attack vectors: {results['attack_vector']}. Result: {results['contained']}"
        )

    def _simulate_privilege_escalation(self):
        self.stdout.write("Simulating Unauthorized Privilege Escalation...")
        citizen = User.objects.filter(role='citizen').first()
        if not citizen: return
        
        # Try to manually change role to super_admin
        original_role = citizen.role
        try:
            citizen.role = User.Role.SUPER_ADMIN
            citizen.save()
            
            # Check if it actually changed (some models have hooks to prevent this)
            citizen.refresh_from_db()
            if citizen.role == User.Role.SUPER_ADMIN:
                self.stdout.write(self.style.ERROR("VULNERABILITY: Privilege Escalation Successful!"))
            else:
                self.stdout.write(self.style.SUCCESS("CONTAINED: Save hooks or logic prevented role change."))
        except Exception as e:
            self.stdout.write(self.style.SUCCESS(f"CONTAINED: System error blocked escalation: {str(e)}"))
        
        # Restore
        citizen.role = original_role
        citizen.save()
