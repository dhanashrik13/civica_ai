from django.core.management.base import BaseCommand
from accounts.services import (
    analyze_district_coverage, 
    generate_staffing_for_district, 
    simulate_district_rollout, 
    execute_approved_rollout
)
from accounts.models import StaffingRollout

class Command(BaseCommand):
    help = "Safely generate officers with governance rollout controls."

    def add_arguments(self, parser):
        parser.add_argument('--district', type=str, help='District name')
        parser.add_argument('--simulate', action='store_true', help='Simulate rollout and create draft')
        parser.add_argument('--rollout-id', type=int, help='Rollout ID to approve or execute')
        parser.add_argument('--approve', action='store_true', help='Approve a draft rollout')
        parser.add_argument('--execute', action='store_true', help='Execute an approved rollout')
        parser.add_argument('--limit', type=int, default=20, help='Max officers to generate')

    def handle(self, *args, **options):
        district = options['district']
        simulate = options['simulate']
        rollout_id = options['rollout_id']
        approve = options['approve']
        execute = options['execute']
        limit = options['limit']

        if simulate:
            if not district:
                self.stdout.write(self.style.ERROR("Please specify --district for simulation"))
                return
            rollout = simulate_district_rollout(district)
            if rollout:
                self.stdout.write(self.style.SUCCESS(f"Simulated rollout for {district}."))
                self.stdout.write(f"Rollout ID: {rollout.id}")
                self.stdout.write(f"Estimated Officers: {rollout.estimated_officers}")
                self.stdout.write(f"Current Pending Issues: {rollout.policy_snapshot.get('pending_issues')}")
                self.stdout.write(self.style.WARNING(f"Run with --rollout-id {rollout.id} --approve to proceed."))
            return

        if approve:
            if not rollout_id:
                self.stdout.write(self.style.ERROR("Please specify --rollout-id to approve"))
                return
            try:
                rollout = StaffingRollout.objects.get(pk=rollout_id)
                rollout.status = StaffingRollout.Status.APPROVED
                rollout.save()
                self.stdout.write(self.style.SUCCESS(f"Rollout {rollout_id} for {rollout.district.name} APPROVED."))
                self.stdout.write(self.style.WARNING(f"Run with --rollout-id {rollout_id} --execute --limit {limit} to start generation."))
            except StaffingRollout.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Rollout {rollout_id} not found."))
            return

        if execute:
            if not rollout_id:
                self.stdout.write(self.style.ERROR("Please specify --rollout-id to execute"))
                return
            created = execute_approved_rollout(rollout_id, limit=limit, stdout=self.stdout)
            if created > 0:
                self.stdout.write(self.style.SUCCESS(f"Successfully created {created} officers."))
            return

        # Default: Analysis
        if district:
            summary = analyze_district_coverage(district_name=district)
            if summary:
                s = summary[0]
                self.stdout.write(f"District: {s['district']}")
                self.stdout.write(f"Current Staff: {s['current']}")
                self.stdout.write(f"Staffing Gap: {s['gap']}")
                self.stdout.write(f"Readiness Score: {s['readiness']:.1f}%")
                self.stdout.write("\nPolicies Active:")
                for p in s['policies_used']:
                    self.stdout.write(f"  - {p}")
                self.stdout.write(self.style.WARNING(f"\nRun with --district {district} --simulate to create a rollout plan."))
        else:
            self.stdout.write("Use --district <name> to analyze or --rollout-id <id> to manage rollouts.")
