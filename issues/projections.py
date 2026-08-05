import logging
from django.db import transaction, models
from django.db.models import F
from issues.models import IssueEvent, Issue
from dashboards.models import DistrictDashboardProjection

logger = logging.getLogger(__name__)

def process_issue_event(event_id, is_replay=False):
    """
    Idempotent Event Handler for District Dashboard Projection.
    Updates denormalized counts based on IssueEvent stream.
    """
    try:
        with transaction.atomic():
            # 1. Fetch event and related issue
            # We select_related district/department to avoid N+1 if needed, 
            # though here we use the event payload or issue record.
            event = IssueEvent.objects.select_related('issue', 'issue__department').get(pk=event_id)
            issue = event.issue
            
            if not issue.district or not issue.department:
                return # Can't project without geo/dept context
                
            # 2. IDEMPOTENCY CHECK
            projection, created = DistrictDashboardProjection.objects.select_for_update().get_or_create(
                district=issue.district,
                department=issue.department
            )
            
            if not is_replay and event.id <= projection.last_event_id:
                logger.info(f"[PROJECTION] Skipping duplicate event {event.id} for {projection} (Last: {projection.last_event_id})")
                return
            
            logger.info(f"[PROJECTION] Applying event {event.id} ({event.event_type}) to {projection}")
            # 3. APPLY EVENT TO PROJECTION
            payload = event.payload
            status = payload.get('status')
            priority = payload.get('priority')
            is_new = payload.get('is_new', False)
            
            # Simple Incremental Logic
            # Note: For complex state transitions, we might need more metadata in the event
            # or to query the previous state from a previous event.
            if event.event_type == IssueEvent.Type.CREATED:
                projection.pending_count = F('pending_count') + 1
                if priority == Issue.Priority.HIGH or priority == Issue.Priority.EMERGENCY:
                    projection.high_priority_count = F('high_priority_count') + 1
            
            elif event.event_type == IssueEvent.Type.ASSIGNED:
                # Transition from Pending to Assigned
                projection.pending_count = F('pending_count') - 1
                projection.assigned_count = F('assigned_count') + 1
                
            elif event.event_type == IssueEvent.Type.RESOLVED:
                projection.assigned_count = F('assigned_count') - 1
                projection.resolved_count = F('resolved_count') + 1
            
            # Update checkpoint
            projection.last_event_id = event.id
            projection.save()
            
            if not is_replay:
                logger.info(f"[PROJECTION] Event {event.id} applied to {projection}")

    except IssueEvent.DoesNotExist:
        logger.error(f"[PROJECTION] Event {event_id} not found.")
    except Exception as e:
        logger.error(f"[PROJECTION] Failed to process event {event_id}: {e}")

def rebuild_district_projections():
    """
    Full Replay of the IssueEvent stream to rebuild projections from scratch.
    IMPLEMENTS LIVE REPLAY SAFETY: Rebuilds in memory, then performs an atomic swap.
    """
    logger.info("[REPLAY] Starting live-safe projection rebuild...")
    
    # 1. Determine Checkpoint (Replay Isolation)
    latest_event = IssueEvent.objects.order_by('-id').first()
    if not latest_event:
        return
    checkpoint_id = latest_event.id
    
    # 2. Rebuild in memory (No locks on live traffic)
    shadow_projections = {}
    events = IssueEvent.objects.filter(id__lte=checkpoint_id).select_related('issue').order_by('timestamp', 'id')
    
    for event in events:
        issue = event.issue
        if not issue.district or not issue.department_id:
            continue
            
        key = (issue.district, issue.department_id)
        if key not in shadow_projections:
            shadow_projections[key] = {
                'pending_count': 0, 'assigned_count': 0, 'resolved_count': 0, 
                'high_priority_count': 0, 'last_event_id': 0
            }
        
        p = shadow_projections[key]
        payload = event.payload
        priority = payload.get('priority')
        
        if event.event_type == IssueEvent.Type.CREATED:
            p['pending_count'] += 1
            if priority == Issue.Priority.HIGH or priority == Issue.Priority.EMERGENCY:
                p['high_priority_count'] += 1
        elif event.event_type == IssueEvent.Type.ASSIGNED:
            p['pending_count'] -= 1
            p['assigned_count'] += 1
        elif event.event_type == IssueEvent.Type.RESOLVED:
            p['assigned_count'] -= 1
            p['resolved_count'] += 1
            
        p['last_event_id'] = event.id

    # 3. Atomic Swap (Short lock window)
    with transaction.atomic():
        # Lock existing rows
        existing = DistrictDashboardProjection.objects.select_for_update().all()
        existing_dict = {(proj.district, proj.department_id): proj for proj in existing}
        
        for key, shadow in shadow_projections.items():
            district, dept_id = key
            
            if key in existing_dict:
                live = existing_dict[key]
                # Detect if live traffic advanced while we were building shadow state
                if live.last_event_id > checkpoint_id:
                    logger.info(f"[REPLAY] Live state advanced for {district}. Fast-forwarding missed events.")
                    # Fast-forward is naturally handled because we just overwrite with shadow, 
                    # then re-run process_issue_event for the missed events!
                    live.pending_count = shadow['pending_count']
                    live.assigned_count = shadow['assigned_count']
                    live.resolved_count = shadow['resolved_count']
                    live.high_priority_count = shadow['high_priority_count']
                    live.last_event_id = shadow['last_event_id']
                    live.save()
                    
                    missed_events = IssueEvent.objects.filter(
                        id__gt=checkpoint_id,
                        id__lte=live.last_event_id,
                        issue__district=district,
                        issue__department_id=dept_id
                    ).order_by('id')
                    for e in missed_events:
                        process_issue_event(e.id, is_replay=True)
                else:
                    live.pending_count = shadow['pending_count']
                    live.assigned_count = shadow['assigned_count']
                    live.resolved_count = shadow['resolved_count']
                    live.high_priority_count = shadow['high_priority_count']
                    live.last_event_id = shadow['last_event_id']
                    live.save()
            else:
                DistrictDashboardProjection.objects.create(
                    district=district,
                    department_id=dept_id,
                    pending_count=shadow['pending_count'],
                    assigned_count=shadow['assigned_count'],
                    resolved_count=shadow['resolved_count'],
                    high_priority_count=shadow['high_priority_count'],
                    last_event_id=shadow['last_event_id']
                )
                
    logger.info(f"[REPLAY] Completed rebuild up to checkpoint {checkpoint_id}.")

def is_projection_stale(district, department, max_lag_seconds=30, max_event_gap=10):
    """
    Checks if a projection is too stale to use safely.
    Compares the projection's last_event_id against the global latest event.
    """
    try:
        projection = DistrictDashboardProjection.objects.get(district=district, department=department)
    except DistrictDashboardProjection.DoesNotExist:
        return True # Stale/missing
        
    # Get the latest event ID globally (or for this district/dept if partitioned)
    latest_event = IssueEvent.objects.order_by('-id').first()
    if not latest_event:
        return False # No events at all, so can't be stale
        
    event_gap = latest_event.id - projection.last_event_id
    
    if event_gap == 0:
        return False
        
    if event_gap > max_event_gap:
        logger.warning(f"STALE PROJECTION: {projection} lags by {event_gap} events.")
        return True
        
    # Check if the last processed time is suspiciously old while we know there are new events
    if projection.updated_at < timezone.now() - timezone.timedelta(seconds=max_lag_seconds):
        logger.warning(f"STALE PROJECTION: {projection} updated at {projection.updated_at}, older than {max_lag_seconds}s.")
        return True
        
    return False

def detect_projection_drift():
    """
    Audit utility to compare denormalized projections vs source-of-truth Issue table.
    """
    drifts = []
    projections = DistrictDashboardProjection.objects.all()
    
    for p in projections:
        # Calculate truth from Issue table
        truth = Issue.objects.filter(district=p.district, department=p.department).aggregate(
            pending=models.Count('id', filter=models.Q(status=Issue.Status.PENDING)),
            assigned=models.Count('id', filter=models.Q(status=Issue.Status.ASSIGNED)),
            resolved=models.Count('id', filter=models.Q(status=Issue.Status.RESOLVED))
        )
        
        if (p.pending_count != truth['pending'] or 
            p.assigned_count != truth['assigned'] or 
            p.resolved_count != truth['resolved']):
            
            drifts.append({
                'projection': str(p),
                'drift': {
                    'pending': p.pending_count - truth['pending'],
                    'assigned': p.assigned_count - truth['assigned'],
                    'resolved': p.resolved_count - truth['resolved']
                }
            })
            
    return drifts
