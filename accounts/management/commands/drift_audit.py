from django.core.management.base import BaseCommand
from accounts.services import DriftDetectionEngine
from django.utils import timezone

class Command(BaseCommand):
    help = 'Executes a comprehensive Operational Drift Audit for governance stability.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("--- INITIATING OPERATIONAL DRIFT AUDIT ---"))
        
        alerts = DriftDetectionEngine.run_comprehensive_drift_audit()
        
        if not alerts:
            self.stdout.write(self.style.SUCCESS("SYSTEM STABLE: No operational drift detected."))
        else:
            self.stdout.write(self.style.WARNING(f"DRIFT DETECTED: {len(alerts)} alerts found."))
            for alert in alerts:
                self.stdout.write(f"  - [ALERT] {alert}")
        
        self.stdout.write(self.style.NOTICE("--- AUDIT COMPLETE ---"))
