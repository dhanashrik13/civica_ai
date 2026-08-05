import json
import logging
from django.test import TestCase
from django.contrib.auth import get_user_model
from issues.models import Issue
from ai.assistant import CivicAIAssistant
from assistant.services import build_chat_reply

User = get_user_model()
logger = logging.getLogger(__name__)

class AIValidationSuite(TestCase):
    def setUp(self):
        self.assistant = CivicAIAssistant()
        self.user = User.objects.create_user(username="test_qa_user", password="password", role=User.Role.CITIZEN, email="qa@test.com")
        # Seed an issue for status/summarization context
        self.issue = Issue.objects.create(
            title="Broken street light",
            description="The street light in front of my house is blinking and not working properly.",
            reported_by=self.user,
            status=Issue.Status.PENDING,
            category="electricity"
        )

    def run_validation(self, query, expected_intent, expected_dept=None, expected_lang=None):
        """Helper to run a single validation test case."""
        # Use build_chat_reply to get the response as the system would provide it
        # This also tests the context enrichment (e.g. for status/summarization)
        result = build_chat_reply(self.user, query, context="Test Dashboard")
        
        # We also call CivicAIAssistant.process_input directly to get structured data for validation
        # Since build_chat_reply only returns the string 'reply'
        enriched_context = {"user_issues": [
            {"id": self.issue.id, "title": self.issue.title, "status": "Pending", "description": self.issue.description}
        ]}
        ai_data = self.assistant.process_input(query, user_role="citizen", context=enriched_context)
        
        passed = True
        reasons = []

        # 1. Intent Validation
        if ai_data.get('intent') != expected_intent:
            passed = False
            reasons.append(f"Intent Mismatch: Expected {expected_intent}, got {ai_data.get('intent')}")

        # 2. Department Validation
        if expected_dept:
            actual_dept = ai_data.get('department')
            # Check if expected_dept is a substring or exact match
            if expected_dept.lower() not in actual_dept.lower():
                passed = False
                reasons.append(f"Department Mismatch: Expected {expected_dept}, got {actual_dept}")

        # 3. Response Relevance
        if not ai_data.get('response') or len(ai_data.get('response')) < 5:
            passed = False
            reasons.append("Empty or too short response")

        return {
            "query": query,
            "passed": passed,
            "actual_intent": ai_data.get('intent'),
            "actual_dept": ai_data.get('department'),
            "response": ai_data.get('response'),
            "reasons": reasons
        }

    def test_ai_accuracy_pipeline(self):
        test_cases = [
            ("Water leakage near my house", "issue reporting", "Water Supply"),
            ("Street light is not working", "issue reporting", "Electricity"),
            ("Garbage not collected from our area", "issue reporting", "Sanitation"),
            ("Show my complaint status", "status inquiry", None),
            ("How to apply for ration card?", "scheme inquiry", None),
            ("Pani chi problem aahe", "issue reporting", "Water Supply"),
            ("Road kharab hai", "issue reporting", "Public Works Department"),
            ("Drainage blockage in ward 3", "issue reporting", "Drainage & Sewerage"),
            ("माझ्या भागात पाण्याची समस्या आहे", "issue reporting", "Water Supply"),
            ("Summarize this civic issue", "summarization", None),
        ]

        results = []
        passed_count = 0

        print("\n--- STARTING AI VALIDATION ---")
        for query, intent, dept in test_cases:
            print(f"Testing: '{query}'...")
            res = self.run_validation(query, intent, dept)
            results.append(res)
            if res["passed"]:
                passed_count += 1
                print("  [PASSED]")
            else:
                print(f"  [FAILED] {', '.join(res['reasons'])}")

        total = len(test_cases)
        accuracy = (passed_count / total) * 100

        # Generate Report
        report = f"""
## AI VALIDATION REPORT

Total Tests: {total}
Passed: {passed_count}
Failed: {total - passed_count}
Accuracy: {accuracy:.1f}%

"""
        if total - passed_count > 0:
            report += "### Failed Cases:\n"
            for res in results:
                if not res["passed"]:
                    report += f"""
Query: "{res['query']}"
Expected: {res['actual_intent']} (Intent), {res['actual_dept']} (Dept)
Actual Error: {', '.join(res['reasons'])}
Response: {res['response']}
--------------------------------
"""

        print(report)
        
        with open("AI_VALIDATION_REPORT.md", "w", encoding="utf-8") as f:
            f.write(report)

        self.assertGreaterEqual(accuracy, 90.0, f"AI Accuracy too low: {accuracy:.1f}%")

    def test_regression_dashboards(self):
        """Verify that dashboard views still work."""
        from django.urls import reverse
        
        # 1. Citizen Dashboard
        self.client.force_login(self.user)
        response = self.client.get(reverse('dashboards:citizen_dashboard'))
        self.assertEqual(response.status_code, 200)
        
        # 2. Officer Dashboard
        from accounts.models import OfficerProfile, Department, Location
        district = Location.objects.create(name="Test District", type=Location.Type.DISTRICT)
        officer_user = User.objects.create_user(username="test_officer", password="password", role=User.Role.OFFICER, email="officer@test.com")
        dept = Department.objects.create(name="Test Dept")
        OfficerProfile.objects.create(user=officer_user, department=dept, location=district)
        
        self.client.force_login(officer_user)
        response = self.client.get(reverse('dashboards:officer_dashboard'))
        self.assertEqual(response.status_code, 200)

        # 3. Admin Dashboard
        admin_user = User.objects.create_superuser(username="test_admin", password="password", email="admin@test.com")
        self.client.force_login(admin_user)
        response = self.client.get(reverse('dashboards:admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        
        # 4. AI Assistant Page
        response = self.client.get(reverse('assistant:ai_assistant'))
        self.assertEqual(response.status_code, 200)

        # 5. Redirect View
        response = self.client.get(reverse('redirect_dashboard'))
        self.assertEqual(response.status_code, 302)
