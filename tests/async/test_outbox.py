import pytest
from django.db import transaction
from django.utils import timezone
from accounts.models import PendingTask
from accounts.utils_async import dispatch_task_transactional, recover_pending_tasks, prune_stale_tasks
from final_proj.celery import app

@pytest.fixture
def patch_celery(mocker):
    # Mock send_task to avoid actually hitting the broker during tests
    return mocker.patch.object(app, 'send_task')

@pytest.mark.django_db(transaction=True)
class TestAsyncOutbox:
    def test_dispatch_creates_pending_task(self, patch_celery):
        # We must use atomic block to test on_commit properly, but django test client
        # might wrap everything. For transactional_db, we can manually trigger or simulate.
        
        with transaction.atomic():
            res = dispatch_task_transactional("issues.tasks.enrich_issue_context", args=[1])
            assert res is True
            # Task should be in PENDING state before commit
            assert PendingTask.objects.count() == 1
            task = PendingTask.objects.first()
            assert task.status == PendingTask.Status.PENDING

        # After atomic block, on_commit should run (simulated or real depending on pytest-django)
        # Note: In pytest-django transaction=True, on_commit fires.
        task.refresh_from_db()
        assert patch_celery.call_count == 1
        assert task.status == PendingTask.Status.DISPATCHED

    def test_outbox_recovery_drains_queue(self, patch_celery):
        PendingTask.objects.create(
            task_name="test_task_1", status=PendingTask.Status.PENDING,
            args=[1], kwargs={}
        )
        PendingTask.objects.create(
            task_name="test_task_2", status=PendingTask.Status.PENDING,
            args=[2], kwargs={}
        )
        
        success_count = recover_pending_tasks()
        assert success_count == 2
        assert patch_celery.call_count == 2
        assert PendingTask.objects.filter(status=PendingTask.Status.PENDING).count() == 0
        assert PendingTask.objects.filter(status=PendingTask.Status.DISPATCHED).count() == 2

    def test_outbox_starvation_behavior(self, patch_celery):
        # Create 105 tasks. Our recover_pending_tasks currently caps at 100
        tasks = [
            PendingTask(task_name=f"task_{i}", status=PendingTask.Status.PENDING, args=[], kwargs={})
            for i in range(105)
        ]
        PendingTask.objects.bulk_create(tasks)
        
        success_count = recover_pending_tasks()
        assert success_count == 100
        assert PendingTask.objects.filter(status=PendingTask.Status.PENDING).count() == 5
        # The remaining 5 are starved until next run. This proves the bug identified in the audit.

    def test_prune_stale_tasks(self):
        old_time = timezone.now() - timezone.timedelta(days=4)
        PendingTask.objects.create(
            task_name="t1", status=PendingTask.Status.DISPATCHED,
            dispatched_at=old_time
        )
        PendingTask.objects.create(
            task_name="t2", status=PendingTask.Status.DISPATCHED,
            dispatched_at=timezone.now()
        )
        # Force the created_at for the failure task
        t3 = PendingTask.objects.create(task_name="t3", status=PendingTask.Status.FAILED)
        PendingTask.objects.filter(pk=t3.pk).update(created_at=timezone.now() - timezone.timedelta(days=15))
        
        pruned = prune_stale_tasks()
        assert pruned == 2
        assert PendingTask.objects.count() == 1
