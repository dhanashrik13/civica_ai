import json
from django.core.management.base import BaseCommand
from accounts.services import ReplayEngine

class Command(BaseCommand):
    help = 'Reconstructs a deterministic forensic timeline for a specific governance incident (issue).'

    def add_arguments(self, parser):
        parser.add_argument('issue_id', type=int, help='ID of the issue/incident to investigate')
        parser.add_argument('--json', action='store_true', help='Output in raw JSON format')

    def handle(self, *args, **options):
        issue_id = options['issue_id']
        
        try:
            timeline = ReplayEngine.reconstruct_issue_lifecycle(issue_id)
            
            if options['json']:
                self.stdout.write(json.dumps(timeline, indent=2))
                return

            self.stdout.write(self.style.NOTICE("\n" + "="*80))
            self.stdout.write(self.style.NOTICE(f" FORENSIC INVESTIGATION: ISSUE #CN-{issue_id}"))
            self.stdout.write(self.style.NOTICE("="*80))
            
            for event in timeline:
                timestamp = event['timestamp']
                action = event['action']
                actor = event['actor']
                details = event['details']
                
                # Action Coloring
                if "CREATED" in action: color = self.style.SUCCESS
                elif "RESOLVED" in action: color = self.style.MIGRATE
                elif "ERROR" in action or "FAILURE" in action: color = self.style.ERROR
                else: color = self.style.WARNING
                
                self.stdout.write(f"[{timestamp}] " + color(f"{action:20}") + f" by {actor}")
                self.stdout.write(f"    - Details:  {details}")
                
                if 'snapshot' in event and event['snapshot']:
                    self.stdout.write(self.style.NOTICE(f"    - Snapshot: {json.dumps(event['snapshot'], indent=8)}"))
                
                self.stdout.write("-" * 80)
                
            self.stdout.write(self.style.SUCCESS("\n STATUS: FORENSIC RECONSTRUCTION COMPLETE"))
            self.stdout.write(self.style.NOTICE("="*80 + "\n"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during investigation: {str(e)}"))
