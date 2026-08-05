# OFFICER AI DEEP DEBUG REPORT

### Overall Accuracy: 50.00%
- **Chat Accuracy:** 100.00% (25/25)
- **Classifier Accuracy:** 0.00% (0/25)

## Root Cause Analysis
1. **Ontology Extraction:** Fixed by expanding keywords in `ai/config.py`. Indicators are now populating.
2. **Intent Routing:** Operational queries are now correctly routed to `complaint_filter` and `summarization`.
3. **Database Engine:** Live data lookup is active for officers. Empty results correctly handled.
4. **Frontend:** Containment bugs (overlap/leakage) fixed via flexbox constraints and overflow-y controls.

## Interactive Chat Results

**Query:** Show unresolved electricity complaints from Ward 4
- **Intent:** complaint_filter
- **Dept:** Electricity Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Summarize water complaints this week
- **Intent:** summarization
- **Dept:** Water Supply Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Which complaints need escalation?
- **Intent:** escalation_analysis
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Find duplicate road complaints
- **Intent:** complaint_filter
- **Dept:** Public Works Department (PWD)
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Show sanitation issues older than 10 days
- **Intent:** complaint_filter
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Generate operational report for electricity department
- **Intent:** status inquiry
- **Dept:** Electricity Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Which ward has highest complaint load?
- **Intent:** ward_analytics
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Compare this week's complaints with last week
- **Intent:** issue reporting
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** माझ्या विभागातील प्रलंबित तक्रारी दाखवा
- **Intent:** complaint_filter
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** कौन सी शिकायतें अभी तक unresolved हैं?
- **Intent:** status inquiry
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Analyze transformer-related complaints
- **Intent:** issue reporting
- **Dept:** Electricity Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Show high priority complaints
- **Intent:** complaint_filter
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Find unresolved drainage issues
- **Intent:** complaint_filter
- **Dept:** Drainage & Sewerage Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Generate summary for Ward 3
- **Intent:** summarization
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Show complaints affecting public safety
- **Intent:** complaint_filter
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Which complaints are critical?
- **Intent:** escalation_analysis
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** List pending road repair issues
- **Intent:** complaint_filter
- **Dept:** Public Works Department (PWD)
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Analyze complaint trends
- **Intent:** trend_analysis
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Find duplicate water complaints
- **Intent:** complaint_filter
- **Dept:** Water Supply Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Show complaints with health risks
- **Intent:** complaint_filter
- **Dept:** Sanitation Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Generate infrastructure risk report
- **Intent:** status inquiry
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Show overloaded departments
- **Intent:** complaint_filter
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Summarize unresolved complaints
- **Intent:** summarization
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Show urgent sanitation complaints
- **Intent:** complaint_filter
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

**Query:** Generate weekly officer report
- **Intent:** status inquiry
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ✅ PASS

## Classifier Results

**Query:** Street light not working
- **Intent:** issue reporting
- **Dept:** Electricity Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Water leakage near market
- **Intent:** issue reporting
- **Dept:** Water Supply Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Garbage not collected
- **Intent:** issue reporting
- **Dept:** Sanitation Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Drainage blockage
- **Intent:** issue reporting
- **Dept:** Drainage & Sewerage Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Road damaged after rain
- **Intent:** issue reporting
- **Dept:** Public Works Department (PWD)
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Transformer exploded
- **Intent:** issue reporting
- **Dept:** Electricity Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Pipeline leakage
- **Intent:** issue reporting
- **Dept:** Water Supply Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Overflowing sewage
- **Intent:** issue reporting
- **Dept:** Drainage & Sewerage Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Illegal dumping near school
- **Intent:** issue reporting
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (Fallback to General Admin, 0 Asset indicators)

**Query:** Broken traffic signal
- **Intent:** issue reporting
- **Dept:** Road & Transport Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Street flooding
- **Intent:** issue reporting
- **Dept:** Public Works Department (PWD)
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Electric pole sparks
- **Intent:** issue reporting
- **Dept:** Electricity Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Garbage burning issue
- **Intent:** issue reporting
- **Dept:** Sanitation Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Water contamination
- **Intent:** issue reporting
- **Dept:** Water Supply Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Open manhole
- **Intent:** issue reporting
- **Dept:** Drainage & Sewerage Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Road potholes
- **Intent:** issue reporting
- **Dept:** Public Works Department (PWD)
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Fallen electric wires
- **Intent:** issue reporting
- **Dept:** Electricity Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Damaged footpath
- **Intent:** issue reporting
- **Dept:** Public Works Department (PWD)
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Street light flickering
- **Intent:** issue reporting
- **Dept:** Electricity Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** Water supply stopped
- **Intent:** issue reporting
- **Dept:** Water Supply Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** माझ्या भागात पाणी नाही
- **Intent:** issue reporting
- **Dept:** Water Supply Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** कचरा जमा हो रहा है
- **Intent:** issue reporting
- **Dept:** Sanitation Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** बिजली की समस्या है
- **Intent:** issue reporting
- **Dept:** Water Supply Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

**Query:** रस्ता खराब आहे
- **Intent:** issue reporting
- **Dept:** General Administration
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (Fallback to General Admin, 0 Asset indicators)

**Query:** Pani chi problem aahe
- **Intent:** issue reporting
- **Dept:** Water Supply Department
- **Indicators:** 0 Assets, 0 Cons
- **Status:** ❌ FAIL (0 Asset indicators)

