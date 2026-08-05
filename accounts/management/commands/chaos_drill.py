import time
import random
from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db import connection
from accounts.models import Incident, SystemFailureEvent
from django.utils import timezone

class Command(BaseCommand):
    help = 'Executes recurring chaos drills to verify operational resilience.'

    def add_arguments(self, parser):
        parser.add_argument('--redis-fail', action='store_true', help='Simulate Redis outage')
        parser.add_argument('--db-latency', action='store_true', help='Simulate DB latency spike')
        parser.add_argument('--worker-stress', action='store_true', help='Exhaust Celery workers')
        parser.add_argument('--network-partition', action='store_true', help='Simulate network partition')
        parser.add_argument('--duration', type=int, default=30, help='Duration of the chaos event in seconds')

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("!!! INITIATING CHAOS DRILL !!!"))
        
        duration = options['duration']
        
        if options['redis_fail']:
            self._simulate_redis_failure(duration)
        elif options['db_latency']:
            self._simulate_db_latency(duration)
        elif options['worker_stress']:
            self._simulate_worker_stress(duration)
        elif options['network_partition']:
            self._simulate_network_partition(duration)
        else:
            self.stdout.write(self.style.ERROR("No chaos flag provided. Use --help for options."))

    def _simulate_redis_failure(self, duration):
        self.stdout.write(self.style.NOTICE(f"Simulating Redis Failure for {duration}s..."))
        # In a real environment we might stop the service, 
        # but here we'll simulate it by injecting failure into the cache
        SystemFailureEvent.objects.create(
            type='congestion', 
            is_active=True, 
            impact_factor=5.0,
            start_time=timezone.now()
        )
        Incident.objects.create(
            title="SIMULATED REDIS OUTAGE",
            severity="p0",
            incident_type="REDIS_DOWN",
            description="Simulated chaos drill: Redis connection lost."
        )
        
        # We simulate "failure" by making cache operations fail or hang
        # Fallback logic in services should handle this.
        self.stdout.write(self.style.SUCCESS("Chaos Active: Fallback to DB/Memory required."))
        time.sleep(duration)
        
        SystemFailureEvent.objects.filter(is_active=True, type='congestion').update(is_active=False, end_time=timezone.now())
        self.stdout.write(self.style.SUCCESS("Chaos Resolved: Redis simulation ended."))

    def _simulate_db_latency(self, duration):
        self.stdout.write(self.style.NOTICE(f"Simulating DB Latency for {duration}s..."))
        Incident.objects.create(
            title="SIMULATED DB LATENCY",
            severity="p1",
            incident_type="DB_LATENCY",
            description="Simulated chaos drill: database pressure simulation."
        )
        
        with connection.cursor() as cursor:
            if connection.vendor == 'postgresql':
                self.stdout.write("Executing PG_SLEEP(10)...")
                cursor.execute("SELECT pg_sleep(10);")
            elif connection.vendor == 'sqlite':
                self.stdout.write("Executing conceptual SQLite latency drill...")
                # SQLite doesn't have pg_sleep, we simulate by running a heavy query
                # or just doing a local sleep to block this thread's connection
                time.sleep(5)
            else:
                time.sleep(5)
        
        time.sleep(duration)
        self.stdout.write(self.style.SUCCESS("Chaos Resolved: DB latency simulation ended."))

    def _simulate_worker_stress(self, duration):
        self.stdout.write(self.style.NOTICE(f"Simulating Worker Stress for {duration}s..."))
        from accounts.utils_async import dispatch_task_transactional
        
        for i in range(100):
            dispatch_task_transactional('issues.tasks.process_heavy_chaos_load', kwargs={'iterations': 1000000})
            
        self.stdout.write(self.style.SUCCESS(f"Chaos Active: 100 heavy tasks dispatched via Hardened Outbox."))
        time.sleep(duration)
        self.stdout.write(self.style.SUCCESS("Chaos Resolved: Worker stress simulation ended."))

    def _simulate_network_partition(self, duration):
        self.stdout.write(self.style.NOTICE(f"Simulating Network Partition for {duration}s..."))
        SystemFailureEvent.objects.create(
            type='network', 
            is_active=True, 
            impact_factor=10.0,
            start_time=timezone.now()
        )
        time.sleep(duration)
        SystemFailureEvent.objects.filter(is_active=True, type='network').update(is_active=False, end_time=timezone.now())
        self.stdout.write(self.style.SUCCESS("Chaos Resolved: Network partition ended."))
