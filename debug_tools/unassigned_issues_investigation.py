import os
import django
from django.utils import timezone
from django.db.models import Q, Count

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

from issues.models import Issue, IssueAIContext, Department
from accounts.models import OfficerProfile, Location, PendingTask
from issues.utils import normalize_name

def validate_semantics(issue):
    if not issue.department:
        return False, "No department"
    dept_name = issue.department.name.lower()
    content = (issue.title + " " + (issue.description or "")).lower()
    rules = {
        "pothole": ["pwd", "road"],
        "garbage": ["sanitation", "waste", "garbage"],
        "water": ["water supply", "leakage"],
        "electricity": ["electricity", "power", "street light"],
        "traffic": ["traffic", "police", "signal"],
        "drainage": ["drainage", "sewage"],
        "health": ["health", "hospital", "medical"],
    }
    for keyword, matched_depts in rules.items():
        if keyword in content:
            if not any(md in dept_name for md in matched_depts):
                return False, f"Suggested {keyword}, found {dept_name}"
    return True, "Match"

def audit_unassigned():
    unassigned = Issue.objects.filter(Q(assigned_to__isnull=True) | Q(status='pending')).order_by('id')
    all_pending_tasks = list(PendingTask.objects.all())
    
    audit_results = []
    
    for issue in unassigned:
        # Phase 1: Metadata
        ai_context = getattr(issue, 'ai_context', None)
        issue_id_str = str(issue.id)
        issue_tasks = [t for t in all_pending_tasks if issue_id_str in str(t.args)]
        enrich_task = next((t for t in issue_tasks if t.task_name == 'issues.tasks.enrich_issue_context'), None)
        
        # Phase 3: Semantics
        sem_valid, sem_reason = validate_semantics(issue)
        
        # Phase 4/5: Officer Matching
        norm_dist = normalize_name(issue.district)
        norm_taluka = normalize_name(issue.taluka)
        norm_village = normalize_name(issue.village)
        
        base_officers = OfficerProfile.objects.filter(department=issue.department, is_active=True)
        
        village_matches = base_officers.filter(district__icontains=norm_dist, taluka__icontains=norm_taluka, village__icontains=norm_village).count() if norm_village else 0
        taluka_matches = base_officers.filter(district__icontains=norm_dist, taluka__icontains=norm_taluka).count() if norm_taluka else 0
        dist_matches = base_officers.filter(district__icontains=norm_dist).count() if norm_dist else 0
        
        closest_off = base_officers.filter(district__icontains=norm_dist).first()
        
        # Phase 7: Root Cause
        root_cause = "Unknown"
        stage_failed = "Unknown"
        severity = "Medium"
        
        if not issue.department:
            stage_failed = "Dept Mapping"
            root_cause = "No department mapped"
            severity = "High"
        elif not sem_valid:
            stage_failed = "Semantic Validation"
            root_cause = sem_reason
            severity = "High"
        elif dist_matches == 0:
            stage_failed = "Staffing"
            root_cause = "No officer in same district"
            severity = "High"
        elif enrich_task and enrich_task.status != 'completed':
            stage_failed = "Infrastructure"
            root_cause = f"Enrichment {enrich_task.status}"
            severity = "Critical"
        else:
            stage_failed = "Logic Guard"
            root_cause = issue.assignment_explanation or "Assignment engine rejected candidates"
            severity = "Medium"

        audit_results.append({
            'issue': issue,
            'stage_failed': stage_failed,
            'root_cause': root_cause,
            'severity': severity,
            'village_matches': village_matches,
            'taluka_matches': taluka_matches,
            'dist_matches': dist_matches,
            'closest_off': closest_off,
            'enrich_task': enrich_task,
            'sem_valid': sem_valid,
            'sem_reason': sem_reason
        })

    # TABLE 1
    print("\n--- TABLE 1: ALL UNASSIGNED ISSUES ---")
    print("| Issue ID | Title | Department | Location | Status | Pending Duration |")
    print("|---|---|---|---|---|---|")
    for r in audit_results:
        dur = timezone.now() - r['issue'].created_at
        print(f"| {r['issue'].id} | {r['issue'].title[:30]} | {r['issue'].department} | {r['issue'].district} | {r['issue'].status} | {dur.days}d {dur.seconds//3600}h |")

    # TABLE 2
    print("\n--- TABLE 2: EXACT FAILURE REASONS ---")
    print("| Issue ID | Workflow Stage Failed | Exact Root Cause | Severity |")
    print("|---|---|---|---|")
    for r in audit_results:
        print(f"| {r['issue'].id} | {r['stage_failed']} | {r['root_cause']} | {r['severity']} |")

    # TABLE 3
    print("\n--- TABLE 3: OFFICER MATCH ANALYSIS ---")
    print("| Issue ID | Village Matches | Taluka Matches | District Matches | Closest Officer |")
    print("|---|---|---|---|---|")
    for r in audit_results:
        print(f"| {r['issue'].id} | {r['village_matches']} | {r['taluka_matches']} | {r['dist_matches']} | {r['closest_off'].user.username if r['closest_off'] else 'None'} |")

    # TABLE 4
    print("\n--- TABLE 4: ASYNC PIPELINE STATUS ---")
    print("| Issue ID | Celery Status | Outbox Status | Retry Count | Broker Errors |")
    print("|---|---|---|---|---|")
    for r in audit_results:
        t = r['enrich_task']
        print(f"| {r['issue'].id} | {t.status if t else 'N/A'} | {t.status if t else 'N/A'} | {t.retry_count if t else 0} | {t.last_error[:30] if t and t.last_error else 'None'} |")

    # TABLE 5
    print("\n--- TABLE 5: SEMANTIC VALIDATION RESULTS ---")
    print("| Issue ID | AI Department | Semantic Match | Validation Result |")
    print("|---|---|---|---|")
    for r in audit_results:
        print(f"| {r['issue'].id} | {r['issue'].department} | {r['sem_valid']} | {r['sem_reason']} |")

    # TABLE 6
    print("\n--- TABLE 6: ASSIGNMENT POSSIBILITY ---")
    print("| Issue ID | Assignable? | Why Rejected | Should Stay Pending |")
    print("|---|---|---|---|")
    for r in audit_results:
        assignable = "Yes" if r['dist_matches'] > 0 and r['sem_valid'] else "No"
        should_stay = "No" if assignable == "Yes" else "Yes"
        print(f"| {r['issue'].id} | {assignable} | {r['root_cause']} | {should_stay} |")

    # TABLE 7
    summary = {}
    for r in audit_results:
        summary[r['stage_failed']] = summary.get(r['stage_failed'], 0) + 1
    print("\n--- TABLE 7: SYSTEMIC FAILURE SUMMARY ---")
    print("| Failure Type | Count | Impact |")
    print("|---|---|---|")
    for k, v in summary.items():
        print(f"| {k} | {v} | {v} issues unassigned |")

if __name__ == "__main__":
    audit_unassigned()
