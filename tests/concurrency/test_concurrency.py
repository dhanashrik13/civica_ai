import pytest
import concurrent.futures
from django.db import connection
from accounts.models import User, Department, Location, OfficerProfile
from issues.models import Issue

@pytest.mark.django_db(transaction=True)
class TestIssueConcurrency:
    def setup_method(self):
        self.loc = Location.objects.create(name="Test Loc", type="village")
        self.dept = Department.objects.create(name="Test Dept", level="village")
        self.citizen = User.objects.create_user(username="citizen_c", email="c_c@test.com", role=User.Role.CITIZEN)
        self.officer_user = User.objects.create_user(username="officer_c", email="o_c@test.com", role=User.Role.OFFICER)
        self.officer = OfficerProfile.objects.create(user=self.officer_user, department=self.dept, location=self.loc, level="village")

    def test_concurrent_issue_creation(self):
        # We test that creating multiple issues concurrently works and triggers signals/hooks safely
        # Note: Django's transaction.atomic creates its own locks if configured. We just ensure no crash.
        
        def create_issue(index):
            # Each thread needs its own db connection cleanup in django
            Issue.objects.create(
                title=f"Concurrent Issue {index}",
                description="Testing concurrency",
                category="drainage",
                priority="medium",
                reported_by=self.citizen,
                location=self.loc,
                department=self.dept
            )
            connection.close()

        threads = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            for i in range(10):
                threads.append(executor.submit(create_issue, i))
            
            concurrent.futures.wait(threads)
        
        assert Issue.objects.count() == 10
        # Check that async enrichment task hooks didn't crash
        from accounts.models import PendingTask
        assert PendingTask.objects.filter(task_name="issues.tasks.enrich_issue_context").count() == 10
