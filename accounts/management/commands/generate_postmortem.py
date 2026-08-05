from django.core.management.base import BaseCommand
from accounts.models import Incident
from django.utils import timezone

class Command(BaseCommand):
    help = 'Generates an automated postmortem for a resolved incident.'

    def add_arguments(self, parser):
        parser.add_argument('incident_id', type=int, help='ID of the incident')

    def handle(self, *args, **options):
        try:
            incident = Incident.objects.get(pk=options['incident_id'])
            
            if not incident.resolved_at:
                incident.resolved_at = timezone.now()
                incident.add_event("Incident marked as RESOLVED by automated postmortem generator.")
                
            postmortem = incident.generate_postmortem_summary()
            
            self.stdout.write(self.style.SUCCESS(f"Postmortem generated for INC-{incident.id}"))
            self.stdout.write("\n" + postmortem)
            
        except Incident.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Incident {options['incident_id']} not found."))
