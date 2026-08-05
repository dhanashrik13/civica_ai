import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

from ai.config import get_rule_based_analysis

def verify_semantic_classification():
    test_cases = [
        {
            "id": "CASE 1",
            "text": "Large pothole on main road causing accident risk",
            "expected_primary": "Public Works Department (PWD)",
        },
        {
            "id": "CASE 2",
            "text": "Traffic signal not working causing congestion and traffic jam",
            "expected_primary": "Traffic Police Department",
        },
        {
            "id": "CASE 3",
            "text": "Illegal parking blocking ambulance near hospital",
            "expected_primary": "Traffic Police Department",
        },
        {
            "id": "CASE 4",
            "text": "Road collapsed after heavy rainfall yesterday",
            "expected_primary": "Public Works Department (PWD)",
        }
    ]

    print("--- SEMANTIC INTENT HIERARCHY TEST ---")
    for case in test_cases:
        res = get_rule_based_analysis(case["text"])
        primary = res["department"]
        secondary = res.get("secondary_department")
        
        print(f"[{case['id']}] Input: {case['text']}")
        print(f"Result -> PRIMARY: {primary} | SECONDARY: {secondary}")
        
        # We need to handle the case where "road_transport" maps to "Public Works Department (PWD)" in legacy or display
        match = False
        if case["expected_primary"] in primary:
             match = True
        elif primary == "Road & Transport Department" and case["expected_primary"] == "Public Works Department (PWD)":
             match = True # Both are acceptable for road infrastructure in this context

        if match:
            print("VERDICT: PASS")
        else:
            print(f"VERDICT: FAIL (Expected: {case['expected_primary']})")
        print("-" * 30)

if __name__ == "__main__":
    verify_semantic_classification()
