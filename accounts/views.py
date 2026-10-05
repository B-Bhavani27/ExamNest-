from django.shortcuts import render, redirect, get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.db.models import Sum
import random
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.hashers import check_password, make_password

from .models import Student


# Home Page
def index(request):

    from exams.models import Exam, StudentExamAttempt

    total_students = Student.objects.count()

    completed_students = StudentExamAttempt.objects.filter(
        is_submitted=True
    ).values("student_id").distinct().count()

    exams = Exam.objects.filter(is_active=True)

    # ---- Top 3 overall rankers: sum of each student's latest score per exam ----
    totals = {}

    for exam in exams:

        exam_attempts = StudentExamAttempt.objects.filter(
            exam=exam, is_submitted=True
        ).select_related("student").order_by("attempt_number")

        latest_by_student = {}
        for attempt in exam_attempts:
            latest_by_student[attempt.student_id] = attempt

        for student_id, attempt in latest_by_student.items():

            if student_id not in totals:
                totals[student_id] = {
                    "student_id": attempt.student.student_id,
                    "full_name": attempt.student.full_name,
                    "total_score": 0,
                }

            totals[student_id]["total_score"] += attempt.score

    top_rankers = sorted(
        totals.values(),
        key=lambda row: row["total_score"],
        reverse=True
    )[:3]

    return render(
        request,
        "index.html",
        {
            "total_students": total_students,
            "completed_students": completed_students,
            "exams": exams,
            "top_rankers": top_rankers,
        }
    )


# Student Login Page


def student_login(request):

    if request.method == "POST":

        login_id = request.POST["login_id"]
        password = request.POST["password"]

        try:

            if "@" in login_id:
                student = Student.objects.get(email=login_id)
            else:
                student = Student.objects.get(student_id=login_id)

        except Student.DoesNotExist:

            return render(
                request,
                "accounts/student_login.html",
                {
                    "error": "Invalid Student ID / Email."
                }
            )

        if not student.is_active:

            return render(
                request,
                "accounts/student_login.html",
                {
                    "error": "Please activate your account first."
                }
            )

        if check_password(password, student.password):

            request.session["student_id"] = student.student_id

            return redirect("student_dashboard")

        return render(
            request,
            "accounts/student_login.html",
            {
                "error": "Incorrect password."
            }
        )

    return render(request, "accounts/student_login.html")

from exams.models import Exam, StudentExamAttempt


def student_dashboard(request):

    student_id = request.session.get("student_id")

    if not student_id:
        return redirect("student_login")

    student = Student.objects.get(student_id=student_id)

    exams = list(Exam.objects.filter(is_active=True))

    all_attempts = StudentExamAttempt.objects.filter(
        student=student
    )

    completed_attempts = all_attempts.filter(
        is_submitted=True
    ).order_by("-submitted_at")

    # ---------------- Grand totals across every exam ever taken ----------------
    totals = completed_attempts.aggregate(
        total_warnings=Sum("warnings"),
        total_violations=Sum("violations"),
    )

    total_warnings = totals["total_warnings"] or 0
    total_violations = totals["total_violations"] or 0

    # ---------------- Per-exam status for "Available Exams" cards + progress ----------------
    passed_count = 0

    for exam in exams:

        exam_attempts = all_attempts.filter(exam=exam)
        attempts_used = exam_attempts.count()

        latest_completed_for_status = exam_attempts.filter(
            is_submitted=True
        ).order_by("-attempt_number").first()

        if latest_completed_for_status and latest_completed_for_status.passed:
            exam.exam_status = "completed"
            passed_count += 1
        elif attempts_used >= exam.max_attempts:
            exam.exam_status = "unavailable"
        else:
            exam.exam_status = "attend"

        exam.attempts_used = attempts_used
        exam.attempts_left = max(exam.max_attempts - attempts_used, 0)

    total_exam_count = len(exams)

    progress_percentage = (
        round((passed_count / total_exam_count) * 100)
        if total_exam_count > 0 else 0
    )
    progress_completed = progress_percentage >= 100

    # ---------------- Per-exam result rows (latest attempt per exam) ----------------
    results = []

    attempted_exam_count = 0
    percentage_sum = 0

    for exam in exams:

        latest_attempt = completed_attempts.filter(exam=exam).first()

        if not latest_attempt:
            continue

        attempted_exam_count += 1
        percentage_sum += float(latest_attempt.percentage)

        row_status = "completed" if latest_attempt.passed else (
            "incomplete" if exam.attempts_used >= exam.max_attempts else "completed"
        )

        results.append({
            "exam_id": exam.id,
            "exam_name": exam.exam_name,
            "warnings": latest_attempt.warnings,
            "violations": latest_attempt.violations,
            "attempts_used": exam.attempts_used,
            "score": latest_attempt.score,
            "is_pass": latest_attempt.passed,
            "status": row_status,
            "date": latest_attempt.submitted_at,
            "warning_logs": latest_attempt.warning_logs,
            "violation_logs": latest_attempt.violation_logs,
        })

    # ---------------- Warning / Violation feeds (separate cards) ----------------
    warning_notifications = []
    violation_notifications = []

    for attempt in completed_attempts:

        for log in attempt.warning_logs:
            warning_notifications.append({
                "icon": "triangle-exclamation",
                "message": log.get("event", "Warning"),
                "exam_name": attempt.exam.exam_name,
                "timestamp": log.get("time", ""),
                "date": attempt.submitted_at,
            })

        for log in attempt.violation_logs:
            violation_notifications.append({
                "icon": "ban",
                "message": log.get("event", "Violation"),
                "exam_name": attempt.exam.exam_name,
                "timestamp": log.get("time", ""),
                "date": attempt.submitted_at,
            })

    warning_notifications.sort(key=lambda n: (n["date"], n["timestamp"]), reverse=True)
    violation_notifications.sort(key=lambda n: (n["date"], n["timestamp"]), reverse=True)

    warning_notifications = warning_notifications[:15]
    violation_notifications = violation_notifications[:15]

    average_score = (
        round(percentage_sum / attempted_exam_count, 1)
        if attempted_exam_count > 0 else 0
    )

    stats = {
        "available_exams": total_exam_count,
        "completed_exams": passed_count,
        "average_score": average_score,
        "ai_warnings": total_warnings,
        "violations": total_violations,
    }

    return render(
        request,
        "accounts/student_dashboard.html",
        {
            "student": student,
            "exams": exams,
            "stats": stats,
            "results": results,
            "warning_notifications": warning_notifications,
            "violation_notifications": violation_notifications,
            "progress_percentage": progress_percentage,
            "progress_completed": progress_completed,
        }
    )

def logout(request):

    request.session.flush()

    return redirect("student_login")



# Student Registration
def student_register(request):

    if request.method == "POST":

        student = Student.objects.create(

            full_name=request.POST["full_name"],
            email=request.POST["email"],
            dob=request.POST["dob"],
            college_name=request.POST["college_name"],
            study_level=request.POST["study_level"],
            degree=request.POST["degree"],
            department=request.POST["department"],
            house_no=request.POST["house_no"],
            street_area=request.POST["street_area"],
            city=request.POST["city"],
            district=request.POST["district"],
            state=request.POST["state"],
            pincode=request.POST["pincode"],
            country=request.POST["country"],
            photo=request.FILES["photo"],
        )

        activation_link = request.build_absolute_uri(
            reverse(
                "activation",
                kwargs={"token": student.activation_token}
            )
        )

        message = f"""
Hello {student.full_name},

Welcome to ExamNest.

Your Student ID is:

{student.student_id}

Click the link below to activate your account and create your password.

{activation_link}

Regards,
ExamNest Team
"""

        send_mail(
            subject="Activate Your ExamNest Account",
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[student.email],
            fail_silently=False,
        )

        return render(request, "accounts/email_sent.html")

    return render(request, "accounts/student_register.html")




def activation(request, token):

    student = get_object_or_404(
        Student,
        activation_token=token
    )

    if request.method == "POST":

        password = request.POST["password"]
        confirm_password = request.POST["confirm_password"]

        if password == confirm_password:

            student.password = make_password(password)
            student.is_active = True
            student.save()

            return redirect("student_login")

    return render(
        request,
        "accounts/activation.html",
        {
            "student": student
        }
    )



def forgot_password(request):

    if request.method == "POST":

        login_id = request.POST["login_id"]

        try:

            if "@" in login_id:
                student = Student.objects.get(email=login_id)
            else:
                student = Student.objects.get(student_id=login_id)

        except Student.DoesNotExist:

            return render(
                request,
                "accounts/forgot_password.html",
                {
                    "error": "Student not found."
                }
            )

        otp = str(random.randint(100000, 999999))

        student.otp = otp
        student.otp_created_at = timezone.now()
        student.save()

        message = f"""
Hello {student.full_name},

Your ExamNest Password Reset OTP is:

{otp}

This OTP is valid for 5 minutes.

Do not share this OTP with anyone.

Regards,
ExamNest Team
"""

        send_mail(
            subject="ExamNest Password Reset OTP",
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[student.email],
            fail_silently=False,
        )

        return redirect("verify_otp", student_id=student.student_id)

    return render(request, "accounts/forgot_password.html")



def verify_otp(request, student_id):

    student = get_object_or_404(
        Student,
        student_id=student_id
    )

    if request.method == "POST":

        entered_otp = request.POST["otp"]

        # Check OTP Expiry (5 Minutes)
        if timezone.now() > student.otp_created_at + timedelta(minutes=5):

            return render(
                request,
                "accounts/verify_otp.html",
                {
                    "student": student,
                    "error": "OTP has expired. Please resend OTP."
                }
            )

        # Check OTP
        if entered_otp == student.otp:

            student.otp_verified = True
            student.save()

            return redirect(
                "reset_password",
                student_id=student.student_id
            )

        return render(
            request,
            "accounts/verify_otp.html",
            {
                "student": student,
                "error": "Invalid OTP."
            }
        )

    return render(
        request,
        "accounts/verify_otp.html",
        {
            "student": student
        }
    )

def reset_password(request, student_id):

    student = get_object_or_404(
        Student,
        student_id=student_id
    )

    # Prevent direct access
    if not student.otp_verified:
        return redirect("forgot_password")

    if request.method == "POST":

        password = request.POST["password"]
        confirm_password = request.POST["confirm_password"]

        if password != confirm_password:

            return render(
                request,
                "accounts/reset_password.html",
                {
                    "student": student,
                    "error": "Passwords do not match."
                }
            )

        student.password = make_password(password)

        # Clear OTP data
        student.otp = None
        student.otp_created_at = None
        student.otp_verified = False

        student.save()

        return redirect("student_login")

    return render(
        request,
        "accounts/reset_password.html",
        {
            "student": student
        }
    )



def resend_otp(request, student_id):

    student = get_object_or_404(
        Student,
        student_id=student_id
    )

    otp = str(random.randint(100000, 999999))

    student.otp = otp
    student.otp_created_at = timezone.now()
    student.otp_verified = False
    student.save()

    send_mail(
        subject="ExamNest Password Reset OTP",
        message=f"""
Hello {student.full_name},

Your new OTP is:

{otp}

This OTP is valid for 5 minutes.

Regards,
ExamNest Team
""",
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[student.email],
        fail_silently=False,
    )

    return redirect(
        "verify_otp",
        student_id=student.student_id
    )