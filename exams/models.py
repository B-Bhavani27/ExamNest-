from django.db import models

from accounts.models import Student


class Exam(models.Model):

    exam_name = models.CharField(max_length=200, unique=True)

    description = models.TextField(blank=True)

    total_questions = models.PositiveIntegerField(default=25)

    total_marks = models.PositiveIntegerField(default=100)

    duration = models.PositiveIntegerField(
        default=60,
        help_text="Duration in Minutes"
    )

    pass_marks = models.PositiveIntegerField(default=40)

    max_attempts = models.PositiveIntegerField(default=2)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.exam_name

class Question(models.Model):

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name="questions"
    )

    question = models.TextField()

    option_a = models.CharField(max_length=255)

    option_b = models.CharField(max_length=255)

    option_c = models.CharField(max_length=255)

    option_d = models.CharField(max_length=255)

    CORRECT_CHOICES = [
        ("A", "Option A"),
        ("B", "Option B"),
        ("C", "Option C"),
        ("D", "Option D"),
    ]

    correct_answer = models.CharField(
        max_length=1,
        choices=CORRECT_CHOICES
    )

    marks = models.PositiveIntegerField(default=4)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.exam.exam_name} - Question {self.id}"

class StudentExamAttempt(models.Model):

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE
    )

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE
    )

    attempt_number = models.PositiveIntegerField(default=1)
    face_verified = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)

    submitted_at = models.DateTimeField(
        null=True,
        blank=True
    )

    score = models.PositiveIntegerField(default=0)

    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    passed = models.BooleanField(default=False)

    warnings = models.PositiveIntegerField(default=0)
    violations = models.PositiveIntegerField(default=0)

    warning_logs = models.JSONField(default=list, blank=True)

    violation_logs = models.JSONField(default=list, blank=True)

    is_submitted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.student.student_id} - {self.exam.exam_name}"



class StudentAnswer(models.Model):

    attempt = models.ForeignKey(
        StudentExamAttempt,
        on_delete=models.CASCADE,
        related_name="answers"
    )

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE
    )

    ANSWER_CHOICES = [
        ("A", "Option A"),
        ("B", "Option B"),
        ("C", "Option C"),
        ("D", "Option D"),
    ]

    selected_answer = models.CharField(
        max_length=1,
        choices=ANSWER_CHOICES
    )

    is_correct = models.BooleanField(default=False)

    marks_obtained = models.PositiveIntegerField(default=0)

    answered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.attempt.student.student_id} - {self.question.id}"




