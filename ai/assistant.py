import os
import json
import re
import google.generativeai as genai
from django.conf import settings
from django.utils import timezone

class CivicAIAssistant:
    """
    ENTERPRISE-GRADE CIVIC INTELLIGENCE SYSTEM.
    Uses multi-stage NLP pipeline for deep civic understanding.
    Supports English, Marathi, Hindi, and transliterated (Hinglish/Marathish) inputs.
    """

    # 1. Configuration (Enterprise Schema) - Aligned with SYSTEM_CATEGORIES
    from .config import SYSTEM_CATEGORIES, DEPARTMENT_MAPPING
    
    ALLOWED_CATEGORIES = list(SYSTEM_CATEGORIES.values())
    ALLOWED_PRIORITIES = ["Low", "Medium", "High", "Emergency"]
    
    # Map to canonical labels for consistency
    DEPARTMENT_MAP = DEPARTMENT_MAPPING

    INTENTS = [
        "issue reporting", "status inquiry", "policy clarification", 
        "escalation appeal", "governance suggestion", "staffing query",
        "scheme inquiry", "summarization", "complaint_filter", "workload_analysis",
        "duplicate_detection", "trend_analysis", "ward_analytics",
        "emergency_risk_analysis", "public_safety_assessment", "escalation_analysis"
    ]

    def __init__(self):
        self.model = None
        self.api_key = getattr(settings, "GOOGLE_GEMINI_API_KEY", None) or os.getenv("GOOGLE_GEMINI_API_KEY")
        
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                self.embed_model = "models/text-embedding-004"
            except Exception as e:
                print(f"[AI EVOLUTION] Init Failure: {str(e)}")

    def get_embedding(self, text):
        """
        Generates a semantic vector embedding for the given text.
        Used for duplicate detection and semantic search.
        """
        if not self.api_key or not text:
            return None
        
        try:
            result = genai.embed_content(
                model=self.embed_model,
                content=text,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            print(f"[AI EMBEDDING] Failure: {str(e)}")
            return None

    def process_input(self, user_input, user_role="citizen", context=None):
        """
        Main entry point for AI input analysis.
        Coordinates prompt construction, model inference, and validation.
        """
        if not self.model:
            return self._fallback_response(user_input, "Model not initialized (Missing API Key)", user_role)

        try:
            # 1. Knowledge Base Lookup
            from .knowledge import get_relevant_knowledge
            kb_context = get_relevant_knowledge(user_input)
            
            # 2. Build Evolution Prompt with Knowledge
            prompt = self._build_evolution_prompt(user_input, user_role, context, kb_context)
            response = self.model.generate_content(prompt)
            ai_data = self._parse_and_validate(response.text, user_input, user_role)
            
            # 3. Operational Data Enrichment (for Officers/Admins)
            # Prioritize higher-level operational intents
            operational_intents = ["complaint_filter", "workload_analysis", "ward_analytics", "summarization", "emergency_risk_analysis", "public_safety_assessment", "escalation_analysis"]
            if user_role in ["officer", "super_admin", "dept_admin"] and ai_data['intent'] in operational_intents:
                op_data = self._query_operational_data(ai_data, user_role, context)
                if op_data:
                    # Replace technical response with clean operational data
                    ai_data['response'] = op_data
            
            return ai_data
        except Exception as e:
            print(f"[AI EVOLUTION] Inference Failure: {str(e)}")
            return self._fallback_response(user_input, str(e), user_role)

    def _query_operational_data(self, ai_data, role, context):
        """
        Queries the Issue database and generates a natural, conversational report with strict vertical spacing.
        """
        from issues.models import Issue
        from django.db.models import Q, Count
        
        try:
            filters = Q()
            entities = ai_data.get('entities', {})
            
            # Filter by Category/Department
            cat_key = ai_data.get('category_key')
            if cat_key and cat_key != 'other':
                filters &= Q(category=cat_key)
            
            # Filter by Ward
            ward = entities.get('location_hints')
            if ward and 'ward' in str(ward).lower():
                ward_num = re.findall(r'\d+', str(ward))
                if ward_num:
                    filters &= Q(ward__icontains=ward_num[0]) | Q(metadata__description__icontains=f"Ward {ward_num[0]}")

            # Filter by Status
            status_map = {"unresolved": "pending", "pending": "pending", "resolved": "resolved", "in progress": "in_progress"}
            user_status = (entities.get('status_hint') or '').lower()
            if user_status in status_map:
                filters &= Q(status=status_map[user_status])

            # Filter by Age (Days)
            days = entities.get('days_hint')
            if days:
                from datetime import timedelta
                filters &= Q(created_at__gte=timezone.now() - timedelta(days=int(days)))

            # Fetch Data
            total_count = Issue.objects.filter(filters).count()
            if total_count == 0:
                return "I couldn't find any complaints that match your search in the system right now."

            # Get Status Breakdown
            status_counts = Issue.objects.filter(filters).values('status').annotate(total=Count('status'))
            status_labels = dict(Issue.Status.choices)
            
            # Build Natural Conversational Report
            subject = ai_data.get('category', 'General').lower()
            report = f"I found {total_count} {subject}-related complaints.\n\n"
            
            report += "Current status:\n"
            for item in status_counts:
                label = status_labels.get(item['status'], item['status']).lower()
                report += f"• {item['total']} complaints are {label}\n"
            
            # Get Recent Issues (Top 4 for scanability)
            recent_issues = Issue.objects.filter(filters).order_by('-created_at')[:4]
            report += "\nMost reported issues:\n"
            for i in recent_issues:
                report += f"• {i.title}\n"
            
            if total_count > 4:
                report += f"\nI have {total_count - 4} more complaints available if you need them."
                
            return report
        except Exception as e:
            return "I tried to look up the latest data, but I'm having a little trouble connecting to the system right now."

    def process_evidence(self, image_file, issue_context):
        """
        Multi-Modal Analysis of Civic Evidence (Photos).
        Analyzes damage severity, authenticity, and infrastructure type.
        """
        if not self.model: return None
        
        try:
            # 1. Load Image
            from PIL import Image
            img = Image.open(image_file)
            
            # 2. Build Multi-modal Prompt
            prompt = f"""
            TASK: Analyze this civic issue evidence photo.
            ISSUE CONTEXT: {json.dumps(issue_context)}
            
            ANALYSIS GOALS:
            1. Authenticity: Does this look like a real photo of a civic issue? (Spam/Fraud check)
            2. Infrastructure: Identify the affected infrastructure (Road, Pipe, Pole, etc.)
            3. Severity: Estimate damage scale (1-10) based on visual cues.
            4. Objects: Detect specific objects (Potholes, Water burst, Garbage pile).
            
            REQUIRED JSON OUTPUT:
            {{
                "is_authentic": true/false,
                "infrastructure_type": "string",
                "visual_severity": 1-10,
                "detected_objects": ["string"],
                "analysis_trace": "Detailed visual reasoning"
            }}
            """
            
            response = self.model.generate_content([prompt, img])
            json_text = re.sub(r'```json|```', '', response.text).strip()
            return json.loads(json_text)
            
        except Exception as e:
            print(f"[AI MULTI-MODAL] Visual Analysis Failure: {str(e)}")
            return None

    def _build_evolution_prompt(self, user_input, role, context, kb_context=None):
        """
        Deep Semantic & Operational Intelligence Prompt.
        Enforces strict vertical formatting and context-first intent routing.
        """
        context_str = json.dumps(context, indent=2) if context else "No additional context."
        kb_str = json.dumps(kb_context, indent=2) if kb_context else "No specific knowledge base matches."
        
        return f"""
        YOU ARE THE CIVICPULSE OPERATIONAL INTELLIGENCE CORE.
        Your task is deep semantic reasoning and "Context-First" intent routing.
        
        --- INTENT ROUTING HIERARCHY (PRIORITIZE TOP DOWN) ---
        1. EMERGENCY_RISK_ANALYSIS: Triggers if input mentions hospitals, schools, sparks, flooding, or direct life risks.
        2. PUBLIC_SAFETY_ASSESSMENT: Triggers for significant hazards that aren't immediate life-threats.
        3. ESCALATION_ANALYSIS: Triggers when users ask for higher authority or report unresolved critical failures.
        4. OPERATIONAL INTENTS: summarization, complaint_filter, workload_analysis (Only if not Emergency).
        5. ISSUE_REPORTING: Default for simple reporting.
        
        RULE: DO NOT route to "duplicate_detection" just because the word "repeated" is used. Only use "duplicate_detection" if the user specifically wants to manage or identify identical reports.
        
        --- READABILITY RULE: STRICT VERTICAL FORMATTING ---
        You MUST ensure every major point and every bullet point appears on a NEW LINE.
        Use double line breaks (\\n\\n) between sections.
        
        USER ROLE: {role.upper()}
        SYSTEM CONTEXT: {context_str}
        
        --- MULTILINGUAL UNDERSTANDING ---
        You MUST deeply understand English, Marathi, Hindi, and mixed shorthand.
        Respond naturally in the user's primary language.
        
        --- TARGET OUTPUT STYLE (NATURAL & HUMAN) ---
        Generate a JSON response. The 'response' field must be a NATURAL and PRACTICAL operational summary.
        - NEVER expose internal intent labels (e.g., 'EMERGENCY_RISK_ANALYSIS') or pipeline status updates.
        - NO robotic transition phrases like "I'm looking into your request regarding...".
        - Opening: Start DIRECTLY with a natural phrase ("There seems to be a...", "I've identified a possible risk...").
        - Impact: Explain naturally what could happen.
        - Action: Use "Recommended next steps" followed by clear bullet points.
        - STYLE: Immediate, professional, field-oriented, and seamless.
        
        INTENTS: {self.INTENTS}
        ALLOWED CATEGORIES: {self.ALLOWED_CATEGORIES}
        
        USER INPUT: "{user_input}"
        
        REQUIRED JSON SCHEMA:
        {{
            "intent": "Exact intent from list",
            "category": "Canonical name",
            "category_key": "short_key",
            "priority": "Low/Medium/High/Emergency",
            "department": "Department name",
            "entities": {{
                "infrastructure": "Name if found",
                "inferred_assets": ["likely", "assets"],
                "inferred_risks": ["practical", "problems"],
                "urgency_tags": ["risk", "factors"],
                "location_hints": "Ward/Location",
                "status_hint": "unresolved/resolved/pending",
                "days_hint": "age"
            }},
            "analysis": {{
                "severity_score": 1-10,
                "urgency_reason": "Context-first reasoning",
                "explainability": "Reasoning chain"
            }},
            "response": "NATURAL HUMAN SUMMARY (Vertical points, no robotic labels, use \\n for new lines)",
            "confidence": 0-100
        }}
        """

    def _parse_and_validate(self, raw_text, user_input, user_role="citizen"):
        """Advanced validation layer with Hardened Confidence Gates."""
        try:
            # Clean possible markdown noise
            json_text = re.sub(r'```json|```', '', raw_text).strip()
            data = json.loads(json_text)
            
            # Canonical normalization
            category_val = data.get("category", "Other").title()
            # Attempt reverse map if LLM returned display name
            cat_key = "other"
            for k, v in self.SYSTEM_CATEGORIES.items():
                if v.title() == category_val:
                    cat_key = k
                    break
            
            priority = data.get("priority", "Medium").title()
            if priority not in self.ALLOWED_PRIORITIES: priority = "Medium"

            raw_confidence = data.get("confidence", 0)
            
            # 2. CALIBRATION & AMBIGUITY LAYER
            from .calibration import AICalibrationEngine
            ambiguity = AICalibrationEngine.analyze_ambiguity(user_input)
            calibrated_confidence = AICalibrationEngine.get_calibrated_confidence(
                raw_confidence, user_input, cat_key
            )
            
            is_reliable = calibrated_confidence >= 75 and not ambiguity['requires_human_clarification']
            
            return {
                "intent": data.get("intent", "issue reporting"),
                "category": self.SYSTEM_CATEGORIES.get(cat_key, "Other"),
                "category_key": cat_key,
                "priority": priority,
                "department": self.DEPARTMENT_MAP.get(cat_key, "General Administration"),
                "secondary_department": data.get("secondary_department"),
                "entities": data.get("entities", {}),
                "analysis": data.get("analysis", {}),
                "response": data.get("response", "Processing complete."),
                "confidence": calibrated_confidence,
                "raw_confidence": raw_confidence,
                "is_reliable": is_reliable,
                "forensics": {
                    "prompt_version": "4.0-SEMANTIC",
                    "calibration_applied": calibrated_confidence != raw_confidence,
                    "gate_passed": is_reliable
                },
                "timestamp": timezone.now().isoformat()
            }
        except Exception as e:
            print(f"[AI EVOLUTION] Parse Error: {str(e)}")
            return self._fallback_response(user_input, "Intelligence parsing error.", user_role)

    def _fallback_response(self, text, reason, user_role="citizen"):
        """
        Consolidated Fallback Engine.
        Uses the improved weighted scoring system from config.py.
        """
        from .config import get_rule_based_analysis
        rule_res = get_rule_based_analysis(text)
        
        # Operational Data Enrichment for Fallback
        op_data = ""
        if user_role in ["officer", "super_admin", "dept_admin"] and rule_res['intent'] in ["complaint_filter", "workload_analysis", "ward_analytics", "summarization"]:
             op_data = self._query_operational_data(rule_res, user_role, {})
        
        response = f"{rule_res['suggestion']}"
        if op_data:
            # For fallback, replace technical suggestion with clean report
            response = op_data

        return {
            "intent": rule_res.get("intent", "issue reporting"),
            "category": rule_res["category"],
            "category_key": rule_res["category_key"],
            "priority": rule_res["priority"],
            "department": rule_res["department"],
            "secondary_department": rule_res.get("secondary_department"),
            "entities": rule_res.get("entities", {"analysis_mode": "keyword_fallback"}),
            "analysis": rule_res.get("analysis", {}),
            "response": response,
            "confidence": rule_res["confidence"],
            "is_reliable": rule_res["is_reliable"],
            "timestamp": timezone.now().isoformat(),
            "fallback_reason": reason
        }
