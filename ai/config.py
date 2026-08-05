# --- SHARED AI CONFIGURATION (Source of Truth) ---

SYSTEM_CATEGORIES = {
    # OFFICIAL DEPARTMENTS
    "pwd": "Public Works Department (PWD)",
    "water_supply": "Water Supply Department",
    "sanitation": "Sanitation Department",
    "electricity": "Electricity Department",
    "road_transport": "Road & Transport Department",
    "drainage_sewerage": "Drainage & Sewerage Department",
    "health": "Health Department",
    "environment": "Environment Department",
    "urban_planning": "Urban Planning Department",
    "disaster_management": "Disaster Management Department",
    "traffic_police": "Traffic Police Department",
    "municipal_engineering": "Municipal Engineering Department",
    "other": "General Administration",
}

SYSTEM_PRIORITIES = ["High", "Medium", "Low"]

# Logical Department Mapping
DEPARTMENT_MAPPING = {
    "pwd": "Public Works Department (PWD)",
    "water_supply": "Water Supply Department",
    "sanitation": "Sanitation Department",
    "electricity": "Electricity Department",
    "road_transport": "Road & Transport Department",
    "drainage_sewerage": "Drainage & Sewerage Department",
    "health": "Health Department",
    "environment": "Environment Department",
    "urban_planning": "Urban Planning Department",
    "disaster_management": "Disaster Management Department",
    "traffic_police": "Traffic Police Department",
    "municipal_engineering": "Municipal Engineering Department",
    "other": "General Administration"
}

# --- SEMANTIC INFRASTRUCTURE KNOWLEDGE GRAPH ---
INFRASTRUCTURE_GRAPH = {
    "electricity": {
        "concepts": ["power", "electricity", "electric", "current", "volt", "voltage", "light", "shock", "spark"],
        "assets": ["Transformer", "Power Line", "Electric Pole", "Substation", "Meter Box"],
        "risks": ["Outage Risk", "Fire Hazard", "Electrocution Risk", "Public Safety Hazard"],
        "cascading_impacts": ["Darkness", "Business Interruption", "Medical Equipment Failure"]
    },
    "water_supply": {
        "concepts": ["water", "pani", "paani", "pipeline", "pipe", "tap", "borewell", "tank", "leak", "supply"],
        "assets": ["Main Pipeline", "Distribution Valve", "Storage Tank", "Water Pump", "Supply Line"],
        "risks": ["Contamination Risk", "Resource Wastage", "Flooding", "Health Hazard"],
        "cascading_impacts": ["Scarcity", "Disease Outbreak", "Road Erosion"]
    },
    "road_transport": {
        "concepts": ["road", "street", "pothole", "highway", "bridge", "divider", "pavement", "rasta", "rastaa"],
        "assets": ["Road Surface", "Bridge Structure", "Footpath", "Stormwater Drain", "Street Furniture"],
        "risks": ["Traffic Risk", "Accident Hazard", "Structural Damage", "Public Hazard"],
        "cascading_impacts": ["Vehicle Damage", "Emergency Vehicle Delay", "Dust Pollution"]
    },
    "sanitation": {
        "concepts": ["garbage", "kachra", "trash", "waste", "cleaning", "smell", "stink", "sweep", "dump"],
        "assets": ["Dustbin", "Collection Vehicle", "Processing Unit", "Dumping Ground"],
        "risks": ["Health Risk", "Pest Infestation", "Environmental Pollution", "Fire Risk"],
        "cascading_impacts": ["Disease Spread", "Drainage Blockage", "Air Quality Degradation"]
    },
    "drainage_sewerage": {
        "concepts": ["drain", "drainage", "gutter", "sewage", "manhole", "overflow", "choke", "blockage"],
        "assets": ["Main Sewer Line", "Manhole Cover", "Gully Trap", "Treatment Plant"],
        "risks": ["Flooding Risk", "Contamination", "Health Hazard", "Structural Risk"],
        "cascading_impacts": ["Property Damage", "Disease Spread", "Road Damage"]
    }
}

def get_rule_based_analysis(description):
    """
    CIVIC INTELLIGENCE CONSISTENCY LAYER v4.0
    Implements Semantic Ontology Inference and Risk Reasoning.
    """
    text = (description or "").lower()
    
    # 1. Semantic Domain Matching (Check Concepts + Assets)
    detected_domains = []
    for domain, graph in INFRASTRUCTURE_GRAPH.items():
        search_terms = graph["concepts"] + [a.lower() for a in graph["assets"]]
        if any(term in text for term in search_terms):
            detected_domains.append(domain)
            
    # Fallback to broad department match if concepts missed (Include Devanagari)
    if not detected_domains:
        if any(w in text for w in ["water", "pani", "paani", "पाणी", "पाण्याची"]): detected_domains.append("water_supply")
        elif any(w in text for w in ["electricity", "power", "bijli", "बिजली", "light"]): detected_domains.append("electricity")
        elif any(w in text for w in ["road", "pothole", "rasta", "रस्ता", "footpath"]): detected_domains.append("road_transport")
        elif any(w in text for w in ["garbage", "kachra", "कचरा", "trash"]): detected_domains.append("sanitation")
        elif any(w in text for w in ["drain", "gutter", "gutter", "गटर"]): detected_domains.append("drainage_sewerage")

    # 2. Ontology Inference
    inferred_assets = []
    inferred_risks = []
    
    # Primary Domain Selection
    primary_domain = detected_domains[0] if detected_domains else "other"
    primary_key = "pwd" if primary_domain == "road_transport" else primary_domain

    for domain in detected_domains:
        graph = INFRASTRUCTURE_GRAPH.get(domain, {})
        if graph:
            # Look for specific asset matches
            found_assets = [a for a in graph["assets"] if a.lower() in text]
            # If no specific asset, infer the primary one
            inferred_assets.extend(found_assets if found_assets else [graph["assets"][0]])
            
            # Look for specific risk matches
            found_risks = [r for r in graph["risks"] if r.lower() in text]
            # If no specific risk, infer the logical ones
            inferred_risks.extend(found_risks if found_risks else graph["risks"][:2])

    # De-duplicate
    inferred_assets = list(set(inferred_assets))
    inferred_risks = list(set(inferred_risks))

    # 3. Intent Detection (Semantic Priority Hierarchy)
    # Higher level intents MUST override shallow keyword matches.
    intent = "issue reporting"
    
    # Priority 1: Emergency & Public Safety (Context-First)
    emergency_markers = ["emergency", "critical", "danger", "hazard", "risk", "hospital", "school", "rainfall", "flood", "spark", "electrocution", "fire"]
    safety_triggers = ["safety", "hazard", "threat", "risk", "harm", "ambulance", "access", "spark", "fire", "shock", "flood"]
    
    if any(w in text for w in emergency_markers) and any(w in text for w in safety_triggers):
        intent = "emergency_risk_analysis"
    elif any(w in text for w in emergency_markers):
        intent = "public_safety_assessment"
    elif any(w in text for w in ["escalate", "escalation", "urgent", "higher authority"]):
        intent = "escalation_analysis"
    
    # Priority 2: Operational Requests (Only if not Emergency)
    if intent == "issue reporting":
        intent_rules = {
            "summarization": ["summarize", "summary", "brief", "overview"],
            "scheme inquiry": ["how to apply", "ration card", "scheme", "mjpjay", "pmay", "yojana", "apply"],
            "status inquiry": ["my status", "complaint status", "my complaint", "what happened to my", "update on"],
            "complaint_filter": ["find", "show me", "list", "filter", "display", "where are", "takraari", "daakhva", "show", "दाखवा"],
            "workload_analysis": ["workload", "backlog", "pending tasks", "officer performance"],
            "ward_analytics": ["ward analytics", "area wise analysis", "district analysis"],
            "duplicate_detection": ["manage duplicates", "find identical", "clean duplicates"] # More specific keywords
        }

        for target_intent, keywords in intent_rules.items():
            if any(w in text for w in keywords):
                # Special check for 'repeated' to avoid false positive duplicate detection
                if target_intent == "duplicate_detection" and not any(w in text for w in ["manage", "find identical", "list same"]):
                    continue
                intent = target_intent
                break

    # 4. Dynamic Risk Scoring
    risk_score = 0
    urgency_tags = []
    
    if primary_domain != "other":
        risk_score += 15 # Base domain weight
        
    # Location Sensitivity
    if any(w in text for w in ["school", "hospital", "market", "station", "kashti"]):
        risk_score += 10
        urgency_tags.append("Sensitive Location Impact")

    # Severity Indicators
    severity_keywords = ["emergency", "fatal", "deadly", "critical", "danger", "hazard", "spark", "immediate", "72 hours"]
    if any(w in text for w in severity_keywords):
        risk_score += 15
        urgency_tags.append("Immediate Safety Triggers Detected")

    # Cascading Risk Weight
    risk_score += (len(inferred_risks) * 3)
    
    priority = "Medium"
    if risk_score > 35: priority = "Emergency"
    elif risk_score > 20: priority = "High"
    elif risk_score < 10: priority = "Low"

    # 5. Build Natural Human Response (Seamless & Direct)
    if primary_domain == "other" and intent == "issue reporting":
        suggestion = "I couldn't quite identify the exact problem from your description.\n\nCould you please let me know if it involves water, electricity, roads, or garbage? I'll be able to help you better with more details."
    else:
        # A. Natural Summary
        domain_label = primary_domain.replace('_', ' ').title()
        
        # Contextual Opening based on Intent but without showing Intent Name
        if intent in ["emergency_risk_analysis", "public_safety_assessment"]:
            situation = f"This situation involves potential hazards in the {domain_label} domain that require urgent attention."
        elif intent == "escalation_analysis":
            situation = f"This request for escalation regarding {domain_label} issues is being evaluated based on priority and impact."
        elif urgency_tags:
            situation = f"There seems to be an urgent {domain_label} issue near a sensitive area."
        else:
            situation = f"There seems to be a possible {domain_label} issue."
        
        # B. Natural Risks/Impact
        impact_intro = "This could potentially lead to:"
        risks_list = "\n".join([f"• {risk.capitalize()}" for risk in inferred_risks])
        infrastructure_note = f"The {', '.join(inferred_assets).lower()} might be affected."
        
        # C. Natural Recommendations
        if priority == "Emergency":
            action = "Recommended next steps:\n• A field team should check this immediately\n• Please secure the area for public safety"
        elif priority == "High":
            action = "Recommended next steps:\n• Schedule an inspection as soon as possible\n• Monitor for any worsening signs"
        else:
            action = "Recommended next steps:\n• A routine check should be scheduled\n• Keep an eye on it during regular maintenance"

        # Construct final seamless response
        suggestion = f"{situation}\n\n{impact_intro}\n{risks_list}\n\n{infrastructure_note}\n\n{action}"

    return {
        "intent": intent, 
        "category": SYSTEM_CATEGORIES.get(primary_key, "Other"),
        "category_key": primary_key,
        "priority": priority,
        "department": DEPARTMENT_MAPPING.get(primary_key, "General Administration"),
        "confidence": 75 if primary_domain != "other" else 30,
        "is_reliable": primary_domain != "other",
        "suggestion": suggestion,
        "entities": {
            "inferred_assets": inferred_assets,
            "inferred_risks": inferred_risks,
            "urgency_tags": urgency_tags
        },
        "analysis": {
            "risk_score": risk_score,
            "explainability": f"Softened natural response generated for {primary_domain}."
        }
    }


def validate_ai_structure(data):
    """
    Shared Validation Layer: Enforces the schema before response.
    """
    if not isinstance(data, dict):
        return None
        
    cat_key = data.get("category_key", "other").lower()
    if cat_key not in SYSTEM_CATEGORIES:
        cat_key = "other"
        
    priority = data.get("priority", "Medium").title()
    if priority not in SYSTEM_PRIORITIES:
        priority = "Medium"
        
    confidence = int(data.get("confidence", 50))
    
    return {
        "category": SYSTEM_CATEGORIES[cat_key],
        "category_key": cat_key,
        "priority": priority,
        "department": DEPARTMENT_MAPPING.get(cat_key, "General Administration"),
        "suggestion": data.get("suggestion", "Analysis complete."),
        "confidence": confidence,
        "is_reliable": confidence >= 50
    }
