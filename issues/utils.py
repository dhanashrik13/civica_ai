from django.db.models import Count, Q

from django.db import transaction, models
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

def build_location_label(village, taluka, district):
    return ", ".join(part for part in [village, taluka, district] if part)

LOCATION_ALIASES = {
    "pmc": "pune municipal corporation",
    "pune city": "pune",
    "pcmc": "pimpri chinchwad municipal corporation",
    "pimpri chinchwad": "pimpri chinchwad municipal corporation",
    "mumbai city": "mumbai",
    "mumbai suburban": "mumbai",
    "mc": "municipal corporation",
    "ahmednagar": "ahilyanagar",
    "aurangabad": "chhatrapati sambhajinagar",
    "pune municipal corporation": "pmc",
    "pimpri chinchwad municipal corporation": "pcmc",
}

def normalize_name(name):
    """
    Utility to normalize location names for robust matching.
    Preserves internal spaces for better icontains matching.
    """
    if not name: return ""
    import re
    # 1. Lowercase and strip
    name = name.lower().strip()

    # Apply aliases before suffix removal
    for alias, canonical in LOCATION_ALIASES.items():
        if name == alias:
            name = canonical
            break

    # 2. Remove common suffixes
    name = re.sub(r'\s+(district|taluka|village|ward|zone|city|municipal corporation|corporation|mc)$', '', name)

    # 3. Collapse multiple spaces and remove non-alphanumeric (except spaces)
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()

    # Re-apply aliases after cleanup
    for alias, canonical in LOCATION_ALIASES.items():
        if name == alias:
            name = canonical
            break

    return name
def get_name_variants(name):
    """Returns a list of name variants based on aliases."""
    norm = normalize_name(name)
    if not norm: return []
    variants = {norm}
    for alias, canonical in LOCATION_ALIASES.items():
        if norm == alias:
            variants.add(canonical)
        if norm == canonical:
            variants.add(alias)
    return list(variants)

def find_best_officer(issue):
    """
    STRICT HIERARCHY-AWARE ASSIGNMENT ENGINE.
    Prioritizes local officers (L1) -> Taluka/Zone (L2) -> District/City (L3).
    Ensures zero cross-jurisdiction leakage with improved normalization matching.
    """
    from accounts.models import OfficerProfile
    from issues.models import Issue
    from django.db.models import Count, Q
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"FIND_BEST_OFFICER for Issue #{issue.id}")

    if not issue.department_id:
        logger.error(f"Cannot assign Issue #{issue.id}: No department assigned.")
        return None

    # Get variants for all levels to handle aliases like Ahmednagar/Ahilyanagar
    v_village = get_name_variants(issue.village)
    v_ward = get_name_variants(issue.ward)
    v_taluka = get_name_variants(issue.taluka)
    v_zone = get_name_variants(issue.zone)
    v_city = get_name_variants(issue.city)
    v_district = get_name_variants(issue.district)

    logger.info(f"Location Variants: D={v_district}, T={v_taluka}, V={v_village}, C={v_city}, Z={v_zone}, W={v_ward}")

    # Determine if Urban or Rural
    is_urban = bool(issue.city or issue.zone or issue.ward)
    is_rural = not is_urban and bool(issue.district or issue.taluka or issue.village)

    logger.info(f"Issue Type: {'URBAN' if is_urban else 'RURAL'}")

    with transaction.atomic():
        # DO NOT lock all officers. Only filter base candidates.
        base_officers = OfficerProfile.objects.filter(
            department_id=issue.department_id, 
            is_active=True,
            user__is_active=True
        )
        
        logger.info(f"Base officers in Dept {issue.department}: {base_officers.count()}")

        # We will collect a list of candidate IDs first without locking
        candidate_ids = []

        # STAGE 0: CANONICAL LOCATION HIERARCHY MATCH (STRICT)
        if issue.location_id:
            logger.info(f"STAGE 0: Hierarchical Search for Issue #{issue.id} starting from {issue.location.name} ({issue.location.type})")
            
            curr = issue.location
            while curr:
                # Try to find officers at this specific hierarchy level
                found_ids = list(base_officers.filter(location_id=curr.id).values_list('id', flat=True))
                if found_ids:
                    logger.info(f"  - Found {len(found_ids)} candidates at {curr.name} ({curr.type})")
                    candidate_ids = found_ids
                    break
                
                # Move up the hierarchy
                logger.warning(f"  - UNDERSTAFFED: No candidates at {curr.name} ({curr.type}), moving up...")
                curr = curr.parent
            
            # If we found candidates via hierarchy, we skip string matching
            if candidate_ids:
                logger.info(f"STAGE 0 SUCCESS: Found candidates via hierarchy.")
        
        # Helper to build variant Q objects
        def build_q(field, variants, exact=False):
            q = Q()
            for v in variants:
                if exact: q |= Q(**{f"{field}__iexact": v})
                else: q |= Q(**{f"{field}__icontains": v})
            return q

        # STAGE 1: LOCAL PRECISION (L1: Village / Ward) - FALLBACK STRING MATCH
        if not candidate_ids:
            candidates_qs = OfficerProfile.objects.none()
            if is_rural and v_village:
                logger.info(f"STAGE 1 (Rural/Village): Searching for village variants in district variants")
                q_v = build_q('village', v_village, exact=True)
                q_d = build_q('district', v_district)
                candidates_qs = base_officers.filter(level='village').filter(q_v).filter(q_d)
                if not candidates_qs.exists():
                    q_v_ic = build_q('village', v_village)
                    candidates_qs = base_officers.filter(level='village').filter(q_v_ic).filter(q_d)
            elif is_urban and v_ward:
                logger.info(f"STAGE 1 (Urban/Ward): Searching for ward variants in city variants")
                q_w = build_q('ward', v_ward, exact=True)
                q_c = build_q('city', v_city)
                candidates_qs = base_officers.filter(level='ward').filter(q_w).filter(q_c)
                if not candidates_qs.exists():
                    q_w_ic = build_q('ward', v_ward)
                    candidates_qs = base_officers.filter(level='ward').filter(q_w_ic).filter(q_c)
            candidate_ids = list(candidates_qs.values_list('id', flat=True))

        # STAGE 2: SUPERVISORY FALLBACK (L2: Taluka / Zone)
        if not candidate_ids:
            logger.info("STAGE 1 yielded no candidates. Moving to STAGE 2...")
            candidates_qs = OfficerProfile.objects.none()
            if is_rural and v_taluka:
                logger.info(f"STAGE 2 (Rural/Taluka): Searching for taluka variants in district variants")
                q_t = build_q('taluka', v_taluka, exact=True)
                q_d = build_q('district', v_district)
                candidates_qs = base_officers.filter(level='taluka').filter(q_t).filter(q_d)
                if not candidates_qs.exists():
                    q_t_ic = build_q('taluka', v_taluka)
                    candidates_qs = base_officers.filter(level='taluka').filter(q_t_ic).filter(q_d)
            elif is_urban and v_zone:
                logger.info(f"STAGE 2 (Urban/Zone): Searching for zone variants in city variants")
                q_z = build_q('zone', v_zone, exact=True)
                q_c = build_q('city', v_city)
                candidates_qs = base_officers.filter(level='zone').filter(q_z).filter(q_c)
                if not candidates_qs.exists():
                    q_z_ic = build_q('zone', v_zone)
                    candidates_qs = base_officers.filter(level='zone').filter(q_z_ic).filter(q_c)
            candidate_ids = list(candidates_qs.values_list('id', flat=True))

        # STAGE 3: REGIONAL FALLBACK (L3: District / City)
        if not candidate_ids:
            logger.info("STAGE 2 yielded no candidates. Moving to STAGE 3...")
            candidates_qs = OfficerProfile.objects.none()
            if v_district:
                logger.info(f"STAGE 3 (District): Searching for level=district in district variants")
                q_d = build_q('district', v_district, exact=True)
                candidates_qs = base_officers.filter(level='district').filter(q_d)
                if not candidates_qs.exists():
                    q_d_ic = build_q('district', v_district)
                    candidates_qs = base_officers.filter(level='district').filter(q_d_ic)
            elif v_city:
                logger.info(f"STAGE 3 (City): Searching for level=city in city variants")
                q_c = build_q('city', v_city, exact=True)
                candidates_qs = base_officers.filter(level='city').filter(q_c)
                if not candidates_qs.exists():
                    q_c_ic = build_q('city', v_city)
                    candidates_qs = base_officers.filter(level='city').filter(q_c_ic)
            candidate_ids = list(candidates_qs.values_list('id', flat=True))

        if not candidate_ids:
            logger.warning(f"FINAL FAILURE: No officers found at ANY stage for Issue #{issue.id} within jurisdiction constraints. System is UNDERSTAFFED for this location/department.")
            return None

        # --- CONCURRENCY LOCKING PHASE ---
        # Only lock the specific candidates found, skipping already locked rows to prevent deadlocks
        # and allow concurrent assignments to distribute load across multiple officers.
        locked_candidates = OfficerProfile.objects.select_for_update(skip_locked=True).filter(id__in=candidate_ids).annotate(
            cat_expertise=Count('user__resolved_issues', filter=Q(user__resolved_issues__category=issue.category), distinct=True),
            active_workload=Count('assigned_issues', filter=~Q(assigned_issues__status='resolved'), distinct=True),
            total_hist=Count('assigned_issues', distinct=True),
            solved_hist=Count('user__resolved_issues', filter=Q(user__resolved_issues__status='resolved'), distinct=True)
        )

        if not locked_candidates.exists():
            logger.warning(f"All candidates for Issue #{issue.id} are currently locked by other transactions. Retrying later or falling back.")
            return None

        logger.info(f"Found {locked_candidates.count()} candidate officers. Scoring them...")

        scored_list = []
        for off in locked_candidates:
            # 1. BASE GEOGRAPHIC SCORE (Boosted L1/L2)
            geo_score = 0
            if off.level in ['village', 'ward']:
                 geo_score = 150 # Boosted from 100
            elif off.level in ['taluka', 'zone']:
                 geo_score = 100 # Boosted from 70
            elif off.level in ['district', 'city']:
                 geo_score = 40  # District fallback
            
            # 2. OPERATIONAL ADJUSTMENTS (Workload Balancing Phase 5)
            workload_cap = off.workload_capacity or 10
            if off.active_workload >= workload_cap:
                work_score = -100  # Stiffer penalty for overload
            else:
                work_score = (1.0 - (off.active_workload / workload_cap)) * 30 # Boosted from 20
                
            exp_score = min(off.cat_expertise / 5.0, 1.0) * 20  # Boosted from 10
            eff_rate = (off.solved_hist / off.total_hist) if off.total_hist > 0 else 0.5
            eff_score = eff_rate * 20 # Boosted from 10
            
            total_score = geo_score + exp_score + work_score + eff_score
            
            scored_list.append({
                'officer': off,
                'score': total_score,
                'details': f"Geo: {geo_score}, Exp: +{int(exp_score)}, Workload({off.active_workload}/{workload_cap}): {int(work_score)}, Eff: +{int(eff_score)}"
            })

        scored_list.sort(key=lambda x: x['score'], reverse=True)
        best = scored_list[0]
        
        if best['score'] < 0:
            logger.warning(f"SEVERE UNDERSTAFFING / OVERLOAD DETECTED: Best officer {best['officer'].user.username} is severely overloaded or a poor match (Score: {int(best['score'])}).")
        
        logger.info(f"Best officer: {best['officer'].user.username} with score {int(best['score'])}")
        issue.assignment_explanation = f"Precision Match: {best['officer'].user.full_name or best['officer'].user.username} (Score: {int(best['score'])}). Reasoning: {best['details']}"
        return best['officer']


def calculate_adaptive_risk(issue):
    """
    Computes a risk score and prediction confidence.
    """
    from issues.models import CategoryIntelligence, Issue
    
    score = 0
    details = {}
    confidence = 100

    # 1. Category Difficulty
    intel = CategoryIntelligence.objects.filter(category=issue.category).first()
    if not intel or intel.total_resolved < 5:
        confidence -= 30 # Lower confidence on small datasets
    
    diff_factor = intel.difficulty_score if intel else 1.0
    cat_risk = min(diff_factor * 40, 40)
    score += cat_risk
    details['category_risk'] = int(cat_risk)

    # 2. OfficerProfile Backlog
    if issue.assigned_to:
        backlog = issue.assigned_to.assigned_issues.exclude(status='resolved').count()
        backlog_risk = min(backlog * 5, 30)
        score += backlog_risk
        details['officer_backlog_risk'] = backlog_risk
    else:
        confidence -= 20

    # 3. Time Decay
    elapsed = 0
    if issue.created_at:
        elapsed = max(0, (timezone.now() - issue.created_at).days)
    sla_days = max(1, issue.sla_days)
    time_risk = min((elapsed / sla_days) * 30, 30)
    score += time_risk
    details['time_risk'] = int(time_risk)

    issue.risk_score = max(0, min(int(score), 100))
    # Using JSON field to store confidence and details
    details['confidence'] = max(0, confidence)
    issue.intelligence_data = details
    return issue.risk_score

def update_intelligence_after_resolution(issue):
    """
    Learning Loop with Stability and Audit Trail.
    """
    from issues.models import CategoryIntelligence, IntelligenceLog, Issue
    
    if issue.status != Issue.Status.RESOLVED or not issue.resolved_at:
        return

    with transaction.atomic():
        intel, created = CategoryIntelligence.objects.select_for_update().get_or_create(category=issue.category)
        
        # 1. Update Avg Resolution Time with Weighted Smoothing
        duration = max(0.0, (issue.resolved_at - issue.created_at).total_seconds() / 3600.0)
        old_time = intel.avg_resolution_hours
        
        # Weighted average: new = (old * stability) + (new_point * (1-stability))
        alpha = 1.0 - intel.learning_stability
        new_time = (old_time * intel.learning_stability) + (duration * alpha)
        
        # Bounds check to prevent extreme shifts
        new_time = max(1.0, min(new_time, 500.0))
        intel.avg_resolution_hours = new_time
        
        # Audit Log for Avg Time
        IntelligenceLog.objects.create(
            category=issue.category,
            change_type='avg_time',
            old_value=old_time,
            new_value=new_time,
            reason=f"Resolved issue #CN-{issue.id} with duration {int(duration)}h"
        )
        
        # 2. Update Difficulty Score
        old_diff = intel.difficulty_score
        new_diff = max(0.5, min(new_time / 48.0, 2.5))
        intel.difficulty_score = new_diff
        
        if abs(new_diff - old_diff) > 0.01:
            IntelligenceLog.objects.create(
                category=issue.category,
                change_type='difficulty',
                old_value=old_diff,
                new_value=new_diff,
                reason="Re-calculated difficulty based on new average time"
            )
            
        intel.total_resolved += 1
        intel.save()
    
    return intel

def get_priority(category, description):
    category = str(category or "").lower()
    description = str(description or "").lower()

    # EMERGENCY CONDITIONS: Immediate threat to life or safety
    emergency_keywords = [
        "electric shock", "electrocution", "fire", "gas leak", 
        "building collapse", "bridge collapse", "major accident", 
        "poisoning", "toxic leak"
    ]

    for word in emergency_keywords:
        if word in description or word in category:
            return "emergency"

    # HIGH priority conditions: Critical infrastructure failure, health hazards, safety risks
    high_keywords = [
        "overflow", "leakage", "hazard", "sewage", "accident", "danger", 
        "burst", "open drain", "short circuit", "contamination", 
        "emergency", "urgent", "health", "disaster"
    ]

    # MEDIUM priority conditions: Significant service disruption, common infrastructure issues
    medium_keywords = [
        "pothole", "garbage", "blockage", "dark", "street light", "broken", 
        "damaged", "cracked", "stink", "smell", "dump", "cleaning",
        "pwd", "water", "electricity", "sanitation", "drainage"
    ]

    # LOW priority conditions: Minor aesthetic issues, non-urgent requests
    low_keywords = [
        "paint", "minor", "aesthetic", "tree trimming", "dust", "noise",
        "suggestion", "feedback", "slow", "delay", "environment", "planning"
    ]

    # Check HIGH first
    for word in high_keywords:
        if word in category or word in description:
            return "high"

    # Then MEDIUM
    for word in medium_keywords:
        if word in category or word in description:
            return "medium"

    # Then LOW (explicit keywords)
    for word in low_keywords:
        if word in category or word in description:
            return "low"

    # Default logic: 
    # If category is Water or Drainage related, it's at least MEDIUM
    water_drainage_cats = ["water_supply", "drainage_sewerage", "water_leakage", "drainage", "sewage"]
    if any(cat in category for cat in water_drainage_cats):
        return "medium"

    return "low"
