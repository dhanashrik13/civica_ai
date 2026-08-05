from django.core.management.base import BaseCommand
from accounts.models import HealthSnapshot
from accounts.services import OperationalHealthEngine
from django.utils import timezone

class Command(BaseCommand):
    help = 'Displays the current Operational Health of the Civica AI platform.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("\n" + "="*50))
        self.stdout.write(self.style.NOTICE(" CIVICA AI: REAL-TIME OPERATIONAL HEALTH DASHBOARD"))
        self.stdout.write(self.style.NOTICE("="*50))
        
        snapshot = OperationalHealthEngine.capture_health_snapshot()
        self.stdout.write(f"Snapshot Time: {snapshot.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # 1. GOVERNANCE
        self.stdout.write(self.style.NOTICE(" [GOVERNANCE]"))
        self.stdout.write(f"  - Readiness:     {snapshot.avg_readiness:.1f}%")
        self.stdout.write(f"  - Pending:       {snapshot.pending_issues} issues")
        status_color = self.style.SUCCESS if snapshot.pressure_index < 10 else self.style.WARNING
        self.stdout.write(status_color(f"  - Pressure:      {snapshot.pressure_index:.2f} issues/officer"))
        
        # 2. INFRASTRUCTURE
        self.stdout.write(self.style.NOTICE("\n [INFRASTRUCTURE]"))
        status_color = self.style.SUCCESS if snapshot.outbox_backlog < 50 else self.style.ERROR
        self.stdout.write(status_color(f"  - Outbox:        {snapshot.outbox_backlog} pending tasks"))
        self.stdout.write(f"  - Latency:       {snapshot.system_latency_ms:.2f}ms (Avg write)")
        
        # 3. AI TRUST
        self.stdout.write(self.style.NOTICE("\n [AI TRUST]"))
        self.stdout.write(f"  - Reliability:   {snapshot.avg_ai_confidence:.1f}% average confidence")
        
        # DRIFT & ALERTS
        alerts = OperationalHealthEngine.get_drift_alerts()
        if alerts:
            self.stdout.write(self.style.ERROR("\n !!! CRITICAL OPERATIONAL DRIFT DETECTED !!!"))
            for a in alerts:
                self.stdout.write(self.style.WARNING(f"  - [ALERT] {a}"))
            self.stdout.write(self.style.NOTICE("\n ADVICE: Trigger 'reliability_pipeline' or check Celery worker logs."))
        else:
            self.stdout.write(self.style.SUCCESS("\n STATUS: SYSTEM STABLE (No active drift)"))

        self.stdout.write(self.style.NOTICE("\n" + "="*50))
