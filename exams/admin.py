from django.contrib import admin
from .models import Exam, Question, StudentExamAttempt, StudentAnswer


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = (
        "exam_name",
        "total_questions",
        "total_marks",
        "duration",
        "is_active",
    )
    search_fields = ("exam_name",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "exam",
        "correct_answer",
        "marks",
    )
    list_filter = ("exam",)
    search_fields = ("question",)


@admin.register(StudentExamAttempt)
class StudentExamAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "exam",
        "attempt_number",
        "score",
        "warnings",
        "passed",
        "is_submitted",
    )
    list_filter = ("exam", "passed")


@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "attempt",
        "question",
        "selected_answer",
        "is_correct",
    )