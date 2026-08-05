import json
import logging
from django.test import TestCase
from django.contrib.auth import get_user_model
from issues.models import Issue
from accounts.models import OfficerProfile, Department, Location
from ai.assistant import CivicAIAssistant

User = get_user_model()
logger = logging.getLogger(__name__)

class MassiveAIValidationSuite(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.assistant = CivicAIAssistant()
        
        # Create users for each role
        cls.citizen = User.objects.create_user(username="test_citizen_mass", password="pwd", role=User.Role.CITIZEN, email="cit_mass@test.com")
        
        # Officer setup
        cls.dept = Department.objects.create(name="Water Supply Department")
        cls.loc = Location.objects.create(name="Pune", type=Location.Type.DISTRICT)
        cls.officer_user = User.objects.create_user(username="test_officer_mass", password="pwd", role=User.Role.OFFICER, email="off_mass@test.com")
        OfficerProfile.objects.create(user=cls.officer_user, department=cls.dept, location=cls.loc)
        
        # Admin setup
        cls.admin_user = User.objects.create_superuser(username="test_admin_mass", password="pwd", email="admin_mass@test.com", role=User.Role.SUPER_ADMIN)
        
        # Seed some issues for context
        Issue.objects.create(title="Water leakage in pipeline", description="Major leak in main pipe.", reported_by=cls.citizen, status=Issue.Status.PENDING, category="water_supply")
        Issue.objects.create(title="Streetlight broken", description="No light on main road.", reported_by=cls.citizen, status=Issue.Status.PENDING, category="electricity")

    def run_query(self, query, user, expected_intent, expected_dept=None):
        role = getattr(user, 'role', 'citizen')
        context = {"test_mode": True, "page_context": f"{role} Dashboard"}
        
        res = self.assistant.process_input(query, user_role=role, context=context)
        
        passed = True
        reasons = []
        
        if res.get('intent') != expected_intent:
            passed = False
            reasons.append(f"Intent Mismatch (Expected: {expected_intent}, Got: {res.get('intent')})")
            
        if expected_dept:
            act_dept = res.get('department', '').lower()
            if expected_dept.lower() not in act_dept:
                passed = False
                reasons.append(f"Department Mismatch (Expected: {expected_dept}, Got: {act_dept})")
                
        return {
            "query": query,
            "passed": passed,
            "actual_intent": res.get('intent'),
            "actual_dept": res.get('department'),
            "reasons": reasons
        }

    def generate_citizen_queries(self):
        # 100 queries: 40 Complaint, 20 Status, 15 Scheme, 15 Multilingual, 5 Summarization, 5 Invalid
        queries = []
        # Complaints (Water)
        for i in range(5): queries.append((f"Water is leaking from the main pipe in ward {i}", "issue reporting", "Water"))
        for i in range(5): queries.append((f"No water supply since {i} days in my area", "issue reporting", "Water"))
        # Complaints (Road)
        for i in range(5): queries.append((f"Big pothole on the main road near shop {i}", "issue reporting", "Public Works"))
        for i in range(5): queries.append((f"Road is completely broken at cross section {i}", "issue reporting", "Public Works"))
        # Complaints (Garbage)
        for i in range(5): queries.append((f"Garbage pile is smelling bad near park {i}", "issue reporting", "Sanitation"))
        for i in range(5): queries.append((f"Dustbin is overflowing since {i} days", "issue reporting", "Sanitation"))
        # Complaints (Electricity)
        for i in range(5): queries.append((f"Street light is not working in street {i}", "issue reporting", "Electricity"))
        for i in range(5): queries.append((f"Live wire fallen on ground near school {i}", "issue reporting", "Electricity"))
        
        # Status
        for i in range(10): queries.append((f"What is the status of my complaint ID {i}?", "status inquiry", None))
        for i in range(10): queries.append((f"Has my issue {i} been resolved yet?", "status inquiry", None))
        
        # Schemes
        for i in range(7): queries.append((f"How do I apply for a ration card online {i}?", "scheme inquiry", None))
        for i in range(8): queries.append((f"What are the benefits of MJPJAY scheme {i}?", "scheme inquiry", None))
        
        # Multilingual
        for i in range(5): queries.append((f"Pani chi problem aahe {i}", "issue reporting", "Water"))
        for i in range(5): queries.append((f"Kachra padla aahe {i}", "issue reporting", "Sanitation"))
        for i in range(5): queries.append((f"Road kharab hai yaha {i}", "issue reporting", "Public Works"))
        
        # Summarization
        for i in range(5): queries.append((f"Summarize the issue with ID {i}", "summarization", None))
        
        # Invalid
        for i in range(5): queries.append((f"Hello how are you {i}", "issue reporting", "General Administration"))
        
        return queries

    def generate_officer_queries(self):
        # 100 queries: Analysis, Summarization, Priority
        queries = []
        for i in range(25): queries.append((f"Show me all pending complaints in ward {i}", "status inquiry", None))
        for i in range(25): queries.append((f"Summarize the issues assigned to me today {i}", "summarization", None))
        for i in range(25): queries.append((f"Which complaints are marked as high priority {i}?", "status inquiry", None))
        for i in range(15): queries.append((f"Are there duplicate reports for water leakage {i}?", "status inquiry", None))
        for i in range(10): queries.append((f"मला प्रलंबित तक्रारी दाखवा {i}", "status inquiry", None)) # Marathi status
        return queries

    def generate_admin_queries(self):
        # 100 queries: Analytics, System, Performance
        queries = []
        for i in range(30): queries.append((f"Which department has the most unresolved complaints {i}?", "status inquiry", None))
        for i in range(30): queries.append((f"Show the performance report for Pune district {i}", "status inquiry", None))
        for i in range(20): queries.append((f"Generate a summary of all escalated issues {i}", "summarization", None))
        for i in range(20): queries.append((f"What is the system health and load {i}?", "status inquiry", None))
        return queries

    def execute_suite(self, name, user, queries):
        passed = 0
        failed_cases = []
        
        for q, expected_intent, expected_dept in queries:
            res = self.run_query(q, user, expected_intent, expected_dept)
            if res['passed']:
                passed += 1
            else:
                failed_cases.append(res)
                
        total = len(queries)
        acc = (passed / total) * 100 if total > 0 else 0
        return acc, failed_cases

    def test_massive_validation(self):
        print("\n=== STARTING MASSIVE AI VALIDATION ===")
        
        # 1. Citizen
        cit_queries = self.generate_citizen_queries()
        cit_acc, cit_fails = self.execute_suite("Citizen", self.citizen, cit_queries)
        print(f"Citizen Accuracy: {cit_acc:.2f}%")
        
        # 2. Officer
        off_queries = self.generate_officer_queries()
        off_acc, off_fails = self.execute_suite("Officer", self.officer_user, off_queries)
        print(f"Officer Accuracy: {off_acc:.2f}%")
        
        # 3. Admin
        adm_queries = self.generate_admin_queries()
        adm_acc, adm_fails = self.execute_suite("Admin", self.admin_user, adm_queries)
        print(f"Admin Accuracy: {adm_acc:.2f}%")
        
        overall_acc = (cit_acc + off_acc + adm_acc) / 3
        
        # Report Generation
        report = f"""# AI FULL VALIDATION REPORT

## Overall Accuracy: {overall_acc:.2f}%

| Assistant | Test Cases | Accuracy |
| :--- | :--- | :--- |
| Citizen | {len(cit_queries)} | {cit_acc:.2f}% |
| Officer | {len(off_queries)} | {off_acc:.2f}% |
| Admin | {len(adm_queries)} | {adm_acc:.2f}% |

"""
        all_fails = cit_fails + off_fails + adm_fails
        if all_fails:
            report += "## Failed Cases\n"
            for f in all_fails[:20]: # Show top 20 failures
                report += f"- Query: '{f['query']}'\n  Reasons: {', '.join(f['reasons'])}\n  Actual Intent: {f['actual_intent']}, Dept: {f['actual_dept']}\n\n"

        with open("AI_FULL_VALIDATION_REPORT.md", "w", encoding="utf-8") as f:
            f.write(report)
            
        with open("ai_validation_logs.json", "w", encoding="utf-8") as f:
            json.write_log = {
                "overall_accuracy": overall_acc,
                "citizen": {"accuracy": cit_acc, "failed": cit_fails},
                "officer": {"accuracy": off_acc, "failed": off_fails},
                "admin": {"accuracy": adm_acc, "failed": adm_fails}
            }
            json.dump(json.write_log, f, indent=2)

        self.assertGreaterEqual(cit_acc, 90.0, "Citizen AI failed threshold")
        self.assertGreaterEqual(off_acc, 90.0, "Officer AI failed threshold")
        self.assertGreaterEqual(adm_acc, 90.0, "Admin AI failed threshold")

    def test_regression_safety(self):
        """Ensure core dashboards load 200 OK after tests."""
        from django.urls import reverse
        
        self.client.force_login(self.citizen)
        self.assertEqual(self.client.get(reverse('dashboards:citizen_dashboard')).status_code, 200)
        
        self.client.force_login(self.officer_user)
        self.assertEqual(self.client.get(reverse('dashboards:officer_dashboard')).status_code, 200)
        
        self.client.force_login(self.admin_user)
        self.assertEqual(self.client.get(reverse('dashboards:admin_dashboard')).status_code, 200)
