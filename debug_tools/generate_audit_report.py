import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

from dashboards.services import get_officer_performance_stats
from accounts.models import User

def generate_report():
    user = User.objects.filter(role='super_admin').first() or User.objects.filter(is_superuser=True).first()
    stats = get_officer_performance_stats(user)
    
    total_officers = len(stats)
    total_assignments = sum(s["assigned_count"] for s in stats)
    
    sorted_stats = sorted(stats, key=lambda x: x['pending_count'], reverse=True)
    
    print(f"REPORT_TOTAL_OFFICERS: {total_officers}")
    print(f"REPORT_TOTAL_ASSIGNMENTS: {total_assignments}")
    
    print("REPORT_TOP_20_LOADED")
    for s in sorted_stats[:20]:
        risk = "HIGH" if s["pending_count"] > 10 else "MEDIUM"
        print(f"{s['name']}|{s['pending_count']}|{risk}")
        
    print("REPORT_TOP_20_LEAST")
    for s in sorted_stats[-20:]:
        print(f"{s['name']}|{s['pending_count']}")

    # Generate full CSV
    import csv
    with open('full_officer_workload_report.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Name", "Email", "Active", "Department", "Scope", "District", 
            "Assigned Issues", "Resolved Issues", "Pending Issues", 
            "Overdue Issues", "Efficiency %", "Avg Res (Hours)"
        ])
        for s in stats:
            writer.writerow([
                s["name"], s["email"], s["is_active"], s["department"], s["level"], s["district"],
                s["assigned_count"], s["completed_count"], s["pending_count"],
                s["overdue_count"], s["efficiency"], s["avg_resolution_hours"]
            ])
    print(f"CSV_PATH: {os.path.abspath('full_officer_workload_report.csv')}")

if __name__ == "__main__":
    generate_report()
