import json

from django.shortcuts import render, redirect
from django.contrib.auth.hashers import check_password
from django.db.models import Sum, Avg

from .models import Admin
from accounts.models import Student
from exams.models import Exam, StudentExamAttempt
from .utils import export_report


# ==========================================================
# AUTH
# ==========================================================

def admin_login(request):

    if request.method == "POST":

        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        try:
            admin_user = Admin.objects.get(email=email, is_active=True)
        except Admin.DoesNotExist:
            return render(
                request,
                "admin_panel/admin_login.html",
                {"error": "Invalid email or password."}
            )

        if check_password(password, admin_user.password):
            request.session["admin_id"] = admin_user.id
            return redirect("admin_dashboard")

        return render(
            request,
            "admin_panel/admin_login.html",
            {"error": "Invalid email or password."}
        )

    return render(request, "admin_panel/admin_login.html")


def admin_logout(request):
    request.session.flush()
    return redirect("admin_login")


def _get_logged_in_admin(request):
    """Returns the Admin instance for the current session, or None."""

    admin_id = request.session.get("admin_id")

    if not admin_id:
        return None

    try:
        return Admin.objects.get(id=admin_id, is_active=True)
    except Admin.DoesNotExist:
        return None


# ==========================================================
# SHARED DATA HELPERS
# ==========================================================

def _latest_attempts_by_exam(exam):
    """
    One submitted attempt per student for this exam — their most
    recent attempt_number. Returns a dict: {student_id: attempt}.
    """

    attempts = StudentExamAttempt.objects.filter(
        exam=exam, is_submitted=True
    ).select_related("student").order_by("attempt_number")

    latest = {}
    for attempt in attempts:
        latest[attempt.student_id] = attempt

    return latest


def _build_overall_ranking(exams):
    """
    Sums each student's latest score per exam across every exam,
    then ranks students highest-total first.
    """

    totals = {}

    for exam in exams:
        latest = _latest_attempts_by_exam(exam)

        for student_id, attempt in latest.items():

            if student_id not in totals:
                totals[student_id] = {
                    "student": attempt.student,
                    "total_score": 0,
                    "exams_taken": 0,
                }

            totals[student_id]["total_score"] += attempt.score
            totals[student_id]["exams_taken"] += 1

    ranking = sorted(
        totals.values(),
        key=lambda row: row["total_score"],
        reverse=True
    )

    for index, row in enumerate(ranking, start=1):
        row["rank"] = index

    return ranking


def _build_exam_ranking(exam):
    """Ranking of students for a single exam, by their latest score."""

    latest = _latest_attempts_by_exam(exam)

    ranking = sorted(
        latest.values(),
        key=lambda attempt: attempt.score,
        reverse=True
    )

    ranked_rows = []
    for index, attempt in enumerate(ranking, start=1):
        ranked_rows.append({
            "rank": index,
            "student": attempt.student,
            "score": attempt.score,
            "percentage": attempt.percentage,
            "passed": attempt.passed,
        })

    return ranked_rows


# ==========================================================
# DASHBOARD
# ==========================================================

def admin_dashboard(request):

    admin_user = _get_logged_in_admin(request)
    if not admin_user:
        return redirect("admin_login")

    total_students = Student.objects.count()
    exams = Exam.objects.filter(is_active=True)
    total_exams = exams.count()

    all_completed = StudentExamAttempt.objects.filter(is_submitted=True)
    total_attempts = all_completed.count()

    passed_attempts = all_completed.filter(passed=True).count()
    overall_pass_rate = (
        round((passed_attempts / total_attempts) * 100, 1)
        if total_attempts > 0 else 0
    )

    totals = all_completed.aggregate(
        total_warnings=Sum("warnings"),
        total_violations=Sum("violations"),
    )
    total_warnings = totals["total_warnings"] or 0
    total_violations = totals["total_violations"] or 0

    # ---- Chart data: average percentage per exam ----
    exam_names = []
    exam_avg_scores = []

    for exam in exams:
        avg = all_completed.filter(exam=exam).aggregate(a=Avg("percentage"))["a"]
        exam_names.append(exam.exam_name)
        exam_avg_scores.append(round(float(avg), 1) if avg else 0)

    # ---- Chart data: pass vs fail overall ----
    pass_fail_data = [passed_attempts, total_attempts - passed_attempts]

    context = {
        "admin_user": admin_user,
        "total_students": total_students,
        "total_exams": total_exams,
        "total_attempts": total_attempts,
        "overall_pass_rate": overall_pass_rate,
        "total_warnings": total_warnings,
        "total_violations": total_violations,
        "exam_names_json": json.dumps(exam_names),
        "exam_avg_scores_json": json.dumps(exam_avg_scores),
        "pass_fail_json": json.dumps(pass_fail_data),
    }

    return render(request, "admin_panel/admin_dashboard.html", context)


# ==========================================================
# STUDENT REPORTS
# ==========================================================

def admin_students(request):

    admin_user = _get_logged_in_admin(request)
    if not admin_user:
        return redirect("admin_login")

    students = Student.objects.all().order_by("full_name")

    student_rows = []

    for student in students:

        attempts = StudentExamAttempt.objects.filter(
            student=student, is_submitted=True
        ).select_related("exam").order_by("-submitted_at")

        total_attempts = attempts.count()

        agg = attempts.aggregate(
            total_warnings=Sum("warnings"),
            total_violations=Sum("violations"),
            avg_percentage=Avg("percentage"),
        )

        exam_breakdown = []
        for attempt in attempts:
            exam_breakdown.append({
                "exam_name": attempt.exam.exam_name,
                "score": attempt.score,
                "total_marks": attempt.exam.total_marks,
                "percentage": attempt.percentage,
                "passed": attempt.passed,
                "warnings": attempt.warnings,
                "violations": attempt.violations,
                "date": attempt.submitted_at,
            })

        student_rows.append({
            "student_id": student.student_id,
            "full_name": student.full_name,
            "email": student.email,
            "college_name": student.college_name,
            "total_attempts": total_attempts,
            "avg_percentage": round(float(agg["avg_percentage"]), 1) if agg["avg_percentage"] else 0,
            "total_warnings": agg["total_warnings"] or 0,
            "total_violations": agg["total_violations"] or 0,
            "exam_breakdown": exam_breakdown,
        })

    return render(
        request,
        "admin_panel/admin_students.html",
        {
            "admin_user": admin_user,
            "student_rows": student_rows,
        }
    )


# ==========================================================
# RANKINGS
# ==========================================================

def admin_rankings(request):

    admin_user = _get_logged_in_admin(request)
    if not admin_user:
        return redirect("admin_login")

    exams = Exam.objects.filter(is_active=True)

    overall_ranking = _build_overall_ranking(exams)

    exam_rankings = []
    for exam in exams:
        exam_rankings.append({
            "exam": exam,
            "ranking": _build_exam_ranking(exam),
        })

    return render(
        request,
        "admin_panel/admin_rankings.html",
        {
            "admin_user": admin_user,
            "overall_ranking": overall_ranking,
            "exam_rankings": exam_rankings,
        }
    )


# ==========================================================
# EXPORTS
# ==========================================================

def export_students(request):

    if not _get_logged_in_admin(request):
        return redirect("admin_login")

    export_format = request.GET.get("format", "csv")

    students = Student.objects.all().order_by("full_name")

    headers = [
        "Student ID", "Full Name", "Email", "College",
        "Attempts", "Average %", "Total Warnings", "Total Violations"
    ]
    rows = []

    for student in students:
        attempts = StudentExamAttempt.objects.filter(student=student, is_submitted=True)
        agg = attempts.aggregate(
            total_warnings=Sum("warnings"),
            total_violations=Sum("violations"),
            avg_percentage=Avg("percentage"),
        )

        rows.append([
            student.student_id,
            student.full_name,
            student.email,
            student.college_name,
            attempts.count(),
            round(float(agg["avg_percentage"]), 1) if agg["avg_percentage"] else 0,
            agg["total_warnings"] or 0,
            agg["total_violations"] or 0,
        ])

    return export_report(headers, rows, "student_report", export_format, title="ExamNest — Student Report")


def export_overall_ranking(request):

    if not _get_logged_in_admin(request):
        return redirect("admin_login")

    export_format = request.GET.get("format", "csv")

    exams = Exam.objects.filter(is_active=True)
    ranking = _build_overall_ranking(exams)

    headers = ["Rank", "Student ID", "Full Name", "Total Score", "Exams Taken"]
    rows = []

    for row in ranking:
        rows.append([
            row["rank"],
            row["student"].student_id,
            row["student"].full_name,
            row["total_score"],
            row["exams_taken"],
        ])

    return export_report(headers, rows, "overall_ranking", export_format, title="ExamNest — Overall Ranking")


def export_exam_ranking(request, exam_id):

    if not _get_logged_in_admin(request):
        return redirect("admin_login")

    export_format = request.GET.get("format", "csv")

    exam = Exam.objects.get(id=exam_id)
    ranking = _build_exam_ranking(exam)

    headers = ["Rank", "Student ID", "Full Name", "Score", "Percentage", "Result"]
    rows = []

    for row in ranking:
        rows.append([
            row["rank"],
            row["student"].student_id,
            row["student"].full_name,
            row["score"],
            f"{row['percentage']}%",
            "Pass" if row["passed"] else "Fail",
        ])

    return export_report(
        headers, rows, f"{exam.exam_name}_ranking", export_format,
        title=f"ExamNest — {exam.exam_name} Ranking"
    )


def export_dashboard_summary(request):

    if not _get_logged_in_admin(request):
        return redirect("admin_login")

    export_format = request.GET.get("format", "csv")

    exams = Exam.objects.filter(is_active=True)
    all_completed = StudentExamAttempt.objects.filter(is_submitted=True)

    headers = ["Metric", "Value"]
    rows = [
        ["Total Students", Student.objects.count()],
        ["Total Exams", exams.count()],
        ["Total Attempts", all_completed.count()],
        ["Passed Attempts", all_completed.filter(passed=True).count()],
        ["Failed Attempts", all_completed.filter(passed=False).count()],
        ["Total AI Warnings", all_completed.aggregate(w=Sum("warnings"))["w"] or 0],
        ["Total AI Violations", all_completed.aggregate(v=Sum("violations"))["v"] or 0],
    ]

    return export_report(headers, rows, "dashboard_summary", export_format, title="ExamNest — Dashboard Summary")
