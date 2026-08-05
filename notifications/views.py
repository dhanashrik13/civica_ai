from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Notification

from django.urls import reverse

from django.utils.timesince import timesince
from django.utils import timezone

@login_required
def get_notifications(request):
    notifications = Notification.objects.filter(user=request.user).select_related('related_issue')[:10]
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    
    notif_list = []
    for n in notifications:
        url = "#"
        if n.related_issue:
            if request.user.role == 'citizen':
                url = reverse('citizen:citizen_issue_detail', args=[n.related_issue.id])
            else:
                url = reverse('dashboards:admin_issue_detail', args=[n.related_issue.id])
        
        # Calculate human-readable time
        time_display = timesince(n.created_at, timezone.now()) + " ago"
        if "0 minutes" in time_display:
            time_display = "Just now"

        notif_list.append({
            'id': n.id,
            'message': n.message,
            'is_read': n.is_read,
            'created_at': time_display,
            'type': n.type,
            'severity': n.severity,
            'url': url
        })
    
    return JsonResponse({
        'notifications': notif_list,
        'unread_count': unread_count
    })

from django.views.decorators.http import require_POST

@login_required
@require_POST
def mark_as_read(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'status': 'success'})
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)
