from django.shortcuts import render
from django.contrib import messages
from .models import HeroSection, Feature, Testimonial, TrustedCity
from django.contrib.auth import get_user_model
from django.db.models import F, ExpressionWrapper, DurationField, Avg , Count, Q
from issues.models import Issue
from accounts.models import Department
from django.shortcuts import render
from django.contrib.auth import get_user_model
from django.db.models import F, ExpressionWrapper, DurationField, Avg, Count, Q

from issues.models import Issue
from .models import HeroSection, Feature, Testimonial, TrustedCity


def homepage(request):
    User = get_user_model()

    # ---------------- HERO + STATIC CONTENT ----------------
    hero = HeroSection.objects.first()
    features = Feature.objects.all()
    testimonials = Testimonial.objects.all()
    cities = TrustedCity.objects.all()

    # ---------------- STATS (REAL DATA) ----------------
    total_citizens = User.objects.filter(role="citizen").count()
    total_resolved = Issue.objects.filter(status="resolved").count()

    avg_response = Issue.objects.filter(
        status="resolved",
        resolved_at__isnull=False
    ).annotate(
        resolution_time=ExpressionWrapper(
            F("resolved_at") - F("created_at"),
            output_field=DurationField()
        )
    ).aggregate(avg_time=Avg("resolution_time"))["avg_time"]

    avg_hours = int(avg_response.total_seconds() // 3600) if avg_response else 0

    stats = [
        {
            "icon_class": "bi bi-people",
            "value": total_citizens,
            "label": "Active Citizens"
        },
        {
            "icon_class": "bi bi-check2-circle",
            "value": total_resolved,
            "label": "Issues Resolved"
        },
        {
            "icon_class": "bi bi-clock-history",
            "value": f"{avg_hours} Hours",
            "label": "Avg Response"
        },
        {
            "icon_class": "bi bi-graph-up-arrow",
            "value": "95%",  # keep static or replace later with feedback system
            "label": "Satisfaction Rate"
        },
    ]

    # ---------------- DEPARTMENTS (OPTIMIZED QUERY) ----------------
    departments_qs = Department.objects.annotate(
        total=Count("issues"),
        resolved=Count("issues", filter=Q(issues__status="resolved")),
        in_progress=Count("issues", filter=Q(issues__status="in_progress")),
        pending=Count("issues", filter=Q(issues__status="pending")),
    )

    departments = []
    for dept in departments_qs:
        total = dept.total
        resolved = dept.resolved

        completion = int((resolved / total) * 100) if total > 0 else 0

        departments.append({
            "name": dept.name,
            "total": total,
            "resolved": resolved,
            "in_progress": dept.in_progress,
            "pending": dept.pending,
            "completion": completion,
        })

    # ---------------- HOW IT WORKS ----------------
    how_it_works = [
        {"title": "Register / Login", "desc": "Create your account or sign in to get started."},
        {"title": "Report Civic Issues", "desc": "Submit issues with photos, location, and details."},
        {"title": "AI Routes Issue to Department", "desc": "AI automatically forwards your issue to the correct team."},
        {"title": "Track Issue Progress", "desc": "Monitor updates and status in real-time."},
        {"title": "Receive Notifications", "desc": "Get alerts when your issue is updated or resolved."},
    ]

    # ---------------- FAQ ----------------
    faq = [
        {"question": "Is CivicPulse free to use?", "answer": "Yes, the platform is free for citizens."},
        {"question": "How does the AI routing system work?", "answer": "AI analyzes issue type and forwards it to the correct department."},
        {"question": "What types of issues can I report?", "answer": "Roads, water, waste, streetlight, sanitation, and more."},
        {"question": "How long does it take to resolve an issue?", "answer": "Most issues are resolved within 48–72 hours."},
        {"question": "Is my personal information secure?", "answer": "Yes, we use encrypted, government-grade security."},
        {"question": "Can I report issues anonymously?", "answer": "Yes, anonymous reporting is allowed for most issue types."},
    ]

    # ---------------- CONTEXT ----------------
    context = {
        "hero": hero,
        "stats": stats,
        "features": features,
        "testimonials": testimonials,
        "cities": cities,
        "departments": departments,
        "how_it_works": how_it_works,
        "faq": faq,
    }

    return render(request, "landing/home_refactored.html", context)


def about(request):
    return render(request, "landing/about.html")

def feature(request):
    return render(request, "landing/feature.html")


def contact(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        subject = request.POST.get("subject")
        message = request.POST.get("message")
        
        # Log the inquiry
        print(f"Contact Inquiry: {full_name} <{email}> Subject: {subject} Message: {message}")
        
        messages.success(request, "Your message has been sent successfully!")
        
    return render(request, "landing/contact.html")


def documentation(request):
    return render(request, "landing/documentation.html")

def docs_home(request):
    return render(request, "landing/documentation.html")

def quick_start(request):
    return render(request, "landing/quick_start.html")

def videos(request):
    return render(request, "landing/videos.html")

def api_docs(request):
    return render(request, "landing/api_docs.html")

def privacy_policy(request):
    return render(request, "landing/privacy.html")

def terms_of_service(request):
    return render(request, "landing/terms.html")

def help_support(request):
    return render(request, "landing/support.html")

def faq(request):
    return render(request, "landing/faq.html")
