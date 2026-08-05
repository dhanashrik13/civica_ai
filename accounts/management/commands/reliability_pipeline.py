import time
from django.core.management.base import BaseCommand
from django.core.management import call_command
from accounts.services import GovernanceIntegrityAuditor, DriftDetectionEngine, TrustMetricsEngine
from django.utils import timezone

class Command(BaseCommand):
    help = 'Automates the continuous reliability pipeline: Drills -> Audits -> Scoring.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== INITIATING CONTINUOUS RELIABILITY PIPELINE ==="))
        start_time = time.time()

        # 1. INTEGRITY SCAN
        self.stdout.write("Step 1: Running Governance Integrity Scan...")
        integrity = GovernanceIntegrityAuditor.run_full_integrity_scan()
        self.stdout.write(f"Result: {integrity['orphans']} orphans, {integrity['invalid_assignments']} invalid assignments.")

        # 2. RELIABILITY DRILLS (WP-C1, WP-C2)
        self.stdout.write("\nStep 2: Executing Reliability Drills...")
        call_command('shell', command="from reliability_drill import drill_wp_c1_transactional_outbox, drill_wp_c2_lightweight_save; drill_wp_c1_transactional_outbox(); drill_wp_c2_lightweight_save()")

        # 3. CHAOS SIMULATION (Safe subset)
        self.stdout.write("\nStep 3: Running Chaos Resilience Check (DB Latency)...")
        call_command('chaos_drill', '--db-latency', '--duration', '5')

        # 4. DRIFT AUDIT
        self.stdout.write("\nStep 4: Performing Operational Drift Audit...")
        alerts = DriftDetectionEngine.run_comprehensive_drift_audit()
        if alerts:
            for a in alerts: self.stdout.write(self.style.WARNING(f"  [ALERT] {a}"))
        else:
            self.stdout.write(self.style.SUCCESS("  System Stable (No Drift)"))

        # 5. FINAL SCORING & REPORT
        self.stdout.write("\nStep 5: Synthesizing Final Hardening Metrics...")
        call_command('generate_hardening_score')

        duration = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(f"\n=== PIPELINE COMPLETE (Duration: {duration:.2f}s) ==="))
