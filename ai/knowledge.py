# --- GOVERNMENT SCHEMES & FAQ KNOWLEDGE BASE ---

GOVERNMENT_SCHEMES = [
    {
        "name": "Ration Card (Maharashtra)",
        "description": "A document issued by the State Government for the purchase of essential commodities from Fair Price Shops.",
        "application_process": [
            "Visit the official Aaple Sarkar portal or the local Tahsildar office.",
            "Fill out Form No. 1 for new ration card.",
            "Submit identity proof, address proof, and income certificate.",
            "Verification by the Food and Civil Supplies Department.",
            "Issuance within 15-30 days."
        ],
        "eligibility": "Residents of Maharashtra based on income categories (BPL, APL, Antyodaya).",
        "keywords": ["ration card", "food grains", "fair price shop", "aaple sarkar", "tahsildar"]
    },
    {
        "name": "Mahatma Jyotirao Phule Jan Arogya Yojana (MJPJAY)",
        "description": "Health insurance scheme for citizens of Maharashtra providing free medical treatment for major illnesses.",
        "application_process": [
            "Visit an empanelled hospital with Ration Card and Identity Proof.",
            "Meet the Arogyamitra at the hospital for registration.",
            "Pre-authorization request is sent to the insurance company.",
            "Cashless treatment is provided if approved."
        ],
        "eligibility": "Ration card holders (Yellow, Orange), farmers from suicide-prone districts.",
        "keywords": ["health insurance", "hospital", "medical treatment", "free operation", "mjpjay"]
    },
    {
        "name": "Pradhan Mantri Awas Yojana (PMAY) - Urban",
        "description": "Scheme to provide affordable housing to the urban poor.",
        "application_process": [
            "Apply online through the PMAY portal or at Common Service Centers (CSC).",
            "Fill in Aadhaar details and category (EWS, LIG, MIG).",
            "Submit income details and property information.",
            "Wait for list publication and verification."
        ],
        "eligibility": "Families without a pucca house in India, within specific income limits.",
        "keywords": ["house", "housing scheme", "pmay", "affordable home", "flat"]
    },
    {
        "name": "Sanjay Gandhi Niradhar Anudan Yojana",
        "description": "Financial assistance to destitute persons, blind, disabled, orphans, and persons suffering from major illnesses.",
        "application_process": [
            "Apply at the Tahsildar office with the prescribed form.",
            "Provide age proof, residence proof, and disability/medical certificate.",
            "Verification by the local committee.",
            "Monthly pension credited to the bank account."
        ],
        "eligibility": "Destitute persons below 65 years, disabled persons (40% and above), orphans.",
        "keywords": ["pension", "destitute", "disabled", "financial help", "niradhar"]
    }
]

GENERAL_FAQS = [
    {
        "question": "How do I report a new civic issue?",
        "answer": "You can report a new issue by going to the 'Report Issue' page on your dashboard, filling in the details like title, description, category, and uploading a photo of the issue.",
        "keywords": ["report", "new issue", "how to submit", "complaint"]
    },
    {
        "question": "How can I track my complaint status?",
        "answer": "Go to the 'My Reports' section on your dashboard. You will see a list of all your reported issues with their current status (Pending, Assigned, In Progress, Resolved).",
        "keywords": ["status", "track", "my complaints", "follow up"]
    },
    {
        "question": "What happens after I report an issue?",
        "answer": "Our AI automatically routes your issue to the relevant department. An officer is then assigned to investigate and resolve it. You will receive notifications at each stage.",
        "keywords": ["process", "after reporting", "routing", "who will fix"]
    }
]

def get_relevant_knowledge(user_input):
    """
    Returns relevant knowledge snippets based on user input.
    """
    text = user_input.lower()
    results = []
    
    # Check Schemes
    for scheme in GOVERNMENT_SCHEMES:
        if any(kw in text for kw in scheme["keywords"]):
            results.append({
                "type": "Government Scheme",
                "title": scheme["name"],
                "info": f"{scheme['description']} Process: {' -> '.join(scheme['application_process'])}"
            })
            
    # Check FAQs
    for faq in GENERAL_FAQS:
        if any(kw in text for kw in faq["keywords"]):
            results.append({
                "type": "FAQ",
                "title": faq["question"],
                "info": faq["answer"]
            })
            
    return results
