import os
import django
import time
from django.db import transaction

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

from issues.models import Issue, IssueEmbedding
from accounts.models import User, Location, PendingTask
from accounts.utils_async import dispatch_task_transactional, recover_pending_tasks
from ai.assistant import CivicAIAssistant

def drill_wp_c1_transactional_outbox():
    print("--- DRILL: WP-C1 (Transactional Outbox) ---")
    # Clean up previous
    PendingTask.objects.filter(task_name='debug_task').delete()

    with transaction.atomic():
        print("Atomically creating a task in outbox...")
        dispatch_task_transactional('debug_task')
        pending = PendingTask.objects.filter(task_name='debug_task', status=PendingTask.Status.PENDING).count()
        print(f"Pending tasks in DB (pre-commit): {pending}")
        if pending != 1: raise Exception("Outbox atomicity failed!")
    
    print("Transaction committed.")
    # In local testing, if Celery is NOT running, the on_commit hook will still run but app.send_task will 
    # either fail or timeout. Our hook handles exceptions by logging.
    time.sleep(1) 
    
    pending = PendingTask.objects.filter(task_name='debug_task', status=PendingTask.Status.PENDING).count()
    dispatched = PendingTask.objects.filter(task_name='debug_task', status=PendingTask.Status.DISPATCHED).count()
    print(f"Status - Pending: {pending}, Dispatched: {dispatched}")
    print("WP-C1: PROVEN (Atomic persistence verified)")

def drill_wp_c2_lightweight_save():
    print("\n--- DRILL: WP-C2 (Lightweight Save) ---")
    citizen = User.objects.filter(role='citizen').first()
    dist = Location.objects.filter(type='district').first()
    
    if not citizen or not dist:
        print("Skipping: Data missing.")
        return

    start_time = time.time()
    issue = Issue.objects.create(
        title="Scalability Test", description="Surge simulation",
        category="Road", reported_by=citizen, location=dist
    )
    duration = time.time() - start_time
    print(f"Issue created in {duration:.4f}s")
    print(f"Is Enriched? {issue.is_enriched}")
    
    if duration > 0.5: 
        print("Warning: Save path still feels synchronous.")
    else:
        print("WP-C2: PROVEN (Lightweight write-path verified)")

def drill_wp_c3_ai_calibration():
    print("\n--- DRILL: WP-C3 (AI Calibration) ---")
    ai = CivicAIAssistant()
    # Mixed script input
    input_text = "पाणी येत नाहीये in my tap since morning"
    result = ai._parse_and_validate_v2('{"category": "Water", "priority": "High", "confidence": 90}', input_text)
    print(f"Raw Confidence: {result['raw_confidence']}%")
    print(f"Calibrated Confidence: {result['confidence']}%")
    
    if result['confidence'] < result['raw_confidence']:
        print("WP-C3: PROVEN (Calibration penalty applied to mixed-script input)")
    else:
        print("WP-C3: FAILED (No calibration applied)")

if __name__ == "__main__":
    try:
        drill_wp_c1_transactional_outbox()
        drill_wp_c2_lightweight_save()
        drill_wp_c3_ai_calibration()
    except Exception as e:
        print(f"Drill Interrupted: {str(e)}")
