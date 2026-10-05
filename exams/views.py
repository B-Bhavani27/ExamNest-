from django.shortcuts import render, redirect
from .models import Exam, Question, StudentExamAttempt, StudentAnswer
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from deepface import DeepFace
import cv2
import base64
import numpy as np
import tempfile
import traceback
import os
from accounts.models import Student
from django.utils import timezone
import json

# ==========================================================
# YOLO MODEL (loaded once at module import, not per-request)
# ==========================================================
from ultralytics import YOLO

YOLO_MODEL = YOLO("yolov8n.pt")

# COCO class names we care about -> human readable violation text
RESTRICTED_OBJECT_CLASSES = {
    "cell phone": "Mobile Phone Detected",
    "book": "Book Detected",
}

YOLO_CONFIDENCE_THRESHOLD = 0.35


def exam_instructions(request, exam_id):
    exam = Exam.objects.get(id=exam_id)

    return render(
        request,
        "exams/exam_instructions.html",
        {
            "exam": exam
        }
    )


def permissions(request, exam_id):
    exam = Exam.objects.get(id=exam_id)

    return render(
        request,
        "exams/permissions.html",
        {
            "exam": exam
        }
    )


def face_verification(request, exam_id):

    student_id = request.session.get("student_id")

    if not student_id:
        return redirect("student_login")

    student = Student.objects.get(student_id=student_id)
    exam = Exam.objects.get(id=exam_id)

    previous_attempts = StudentExamAttempt.objects.filter(
        student=student,
        exam=exam
    ).count()

    if previous_attempts >= exam.max_attempts:
        return redirect("student_dashboard")

    attempt = StudentExamAttempt.objects.filter(
        student=student,
        exam=exam,
        is_submitted=False
    ).first()

    if not attempt:
        attempt = StudentExamAttempt.objects.create(
            student=student,
            exam=exam,
            attempt_number=previous_attempts + 1
        )

    return render(
        request,
        "exams/face_verification.html",
        {
            "exam": exam,
            "student": student,
            "attempt": attempt,
        }
    )


@csrf_exempt
def verify_face(request, exam_id):

    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "message": "Invalid request."
        })

    student_id = request.session.get("student_id")

    if not student_id:
        return JsonResponse({
            "success": False,
            "message": "Student not logged in."
        })

    student = Student.objects.get(student_id=student_id)

    image_data = request.POST.get("image")

    if not image_data:
        return JsonResponse({
            "success": False,
            "message": "No image received."
        })

    try:

        image_data = image_data.split(",")[1]
        image_bytes = base64.b64decode(image_data)

        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".jpg"
        )

        temp_file.write(image_bytes)
        temp_file.close()

        # -----------------------------------------------------
        # DEEPFAKE / SPOOF CHECK (real vs printed photo/screen)
        # Runs once here, at verification time, not continuously.
        # -----------------------------------------------------
        try:
            spoof_check = DeepFace.extract_faces(
                img_path=temp_file.name,
                detector_backend="opencv",
                enforce_detection=False,
                anti_spoofing=True
            )

            if spoof_check:
                is_real = spoof_check[0].get("is_real", True)

                if not is_real:
                    os.remove(temp_file.name)
                    return JsonResponse({
                        "success": False,
                        "message": "Spoof detected. Please use your live camera, not a photo or screen."
                    })

        except Exception:
            # If the installed deepface version doesn't support
            # anti_spoofing, skip this check rather than blocking login.
            traceback.print_exc()

        result = DeepFace.verify(
            img1_path=student.photo.path,
            img2_path=temp_file.name,
            model_name="Facenet",
            detector_backend="skip",
            enforce_detection=False
        )

        os.remove(temp_file.name)

        if result["verified"]:

            attempt = StudentExamAttempt.objects.filter(
                student=student,
                exam_id=exam_id,
                is_submitted=False
            ).order_by("-id").first()

            if attempt:
                attempt.face_verified = True
                attempt.save()

            return JsonResponse({
                "success": True,
                "message": "Face verified successfully."
            })

        return JsonResponse({
            "success": False,
            "message": "Face does not match."
        })

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({
            "success": False,
            "message": str(e)
        })


def exam_page(request, exam_id):

    student_id = request.session.get("student_id")

    if not student_id:
        return redirect("student_login")

    student = Student.objects.get(student_id=student_id)

    exam = Exam.objects.get(id=exam_id)

    attempt = StudentExamAttempt.objects.filter(
        student=student,
        exam=exam,
        is_submitted=False
    ).first()

    if not attempt:
        return redirect("face_verification", exam_id=exam.id)

    if not attempt.face_verified:
        return redirect("face_verification", exam_id=exam.id)

    questions = Question.objects.filter(
        exam=exam,
        is_active=True
    )

    return render(
        request,
        "exams/exam_page.html",
        {
            "exam": exam,
            "student": student,
            "attempt": attempt,
            "questions": questions,
        }
    )


@csrf_exempt
def save_answer(request):

    if request.method != "POST":
        return JsonResponse({
            "success": False
        })

    student_id = request.session.get("student_id")

    if not student_id:
        return JsonResponse({
            "success": False
        })

    attempt_id = request.POST.get("attempt_id")
    question_id = request.POST.get("question_id")
    answer = request.POST.get("answer")

    attempt = StudentExamAttempt.objects.get(id=attempt_id)

    question = Question.objects.get(id=question_id)

    StudentAnswer.objects.update_or_create(
        attempt=attempt,
        question=question,
        defaults={
            "selected_answer": answer
        }
    )

    return JsonResponse({
        "success": True
    })


def calculate_and_finalize_attempt(attempt):
    """
    Shared scoring logic. Used by both a normal submit and an
    AI-proctoring auto-submit (5+ violations), so a score is
    always calculated no matter how the exam ends.
    """

    answers = StudentAnswer.objects.filter(attempt=attempt)

    total_score = 0

    for answer in answers:

        if answer.selected_answer == answer.question.correct_answer:
            answer.is_correct = True
            answer.marks_obtained = answer.question.marks
        else:
            answer.is_correct = False
            answer.marks_obtained = 0

        total_score += answer.marks_obtained
        answer.save()

    attempt.score = total_score

    if attempt.exam.total_marks > 0:
        attempt.percentage = round(
            (total_score / attempt.exam.total_marks) * 100,
            2
        )
    else:
        attempt.percentage = 0

    attempt.passed = total_score >= attempt.exam.pass_marks
    attempt.is_submitted = True
    attempt.submitted_at = timezone.now()
    attempt.save()

    return attempt


@csrf_exempt
def submit_exam(request, exam_id):

    student_id = request.session.get("student_id")

    if not student_id:
        return redirect("student_login")

    student = Student.objects.get(student_id=student_id)

    try:
        attempt = StudentExamAttempt.objects.get(
            student=student,
            exam_id=exam_id,
            is_submitted=False
        )
    except StudentExamAttempt.DoesNotExist:
        return redirect("student_dashboard")

    calculate_and_finalize_attempt(attempt)

    return redirect(
        "result_page",
        exam_id=exam_id
    )


def result_page(request, exam_id):

    student_id = request.session.get("student_id")

    if not student_id:
        return redirect("student_login")

    student = Student.objects.get(
        student_id=student_id
    )

    attempt = StudentExamAttempt.objects.filter(
        student=student,
        exam_id=exam_id,
        is_submitted=True
    ).order_by("-id").first()

    if not attempt:
        return redirect("student_dashboard")

    answers = attempt.answers.select_related(
        "question"
    )

    correct_count = answers.filter(is_correct=True).count()
    wrong_count = answers.filter(is_correct=False).count()
    answered_count = answers.count()
    unanswered_count = attempt.exam.questions.filter(is_active=True).count() - answered_count

    time_taken = None

    if attempt.started_at and attempt.submitted_at:

        delta = attempt.submitted_at - attempt.started_at
        total_minutes = int(delta.total_seconds() // 60)
        seconds = int(delta.total_seconds() % 60)

        hours = total_minutes // 60
        minutes = total_minutes % 60

        if hours > 0:
            time_taken = f"{hours}h {minutes}m {seconds}s"
        else:
            time_taken = f"{minutes}m {seconds}s"

    context = {
        "student": student,
        "attempt": attempt,
        "exam": attempt.exam,
        "answers": answers,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "answered_count": answered_count,
        "unanswered_count": unanswered_count,
        "time_taken": time_taken,
    }

    return render(
        request,
        "exams/result.html",
        context
    )


@csrf_exempt
def update_proctoring(request):

    if request.method != "POST":
        return JsonResponse({"success": False})

    student_id = request.session.get("student_id")

    if not student_id:
        return JsonResponse({"success": False})

    student = Student.objects.get(
        student_id=student_id
    )

    data = json.loads(request.body)

    attempt_id = data.get("attempt_id")
    event = data.get("event")
    event_type = data.get("type")

    try:
        attempt = StudentExamAttempt.objects.get(
            student=student,
            id=attempt_id,
            is_submitted=False
        )

    except StudentExamAttempt.DoesNotExist:
        return JsonResponse({"success": False})

    current_time = timezone.now().strftime("%H:%M:%S")

    if event_type == "warning":

        logs = attempt.warning_logs
        logs.append({"event": event, "time": current_time})
        attempt.warning_logs = logs
        attempt.warnings += 1

    elif event_type == "violation":

        logs = attempt.violation_logs
        logs.append({"event": event, "time": current_time})
        attempt.violation_logs = logs
        attempt.violations += 1

    auto_submit = False

    if attempt.violations >= 5:
        calculate_and_finalize_attempt(attempt)
        auto_submit = True
    else:
        attempt.save()

    return JsonResponse({
        "success": True,
        "warnings": attempt.warnings,
        "violations": attempt.violations,
        "auto_submit": auto_submit
    })


@csrf_exempt
def detect_objects(request):
    """
    Continuous AI proctoring endpoint, called every few seconds
    from exam_page.html while the exam is in progress.

    Runs:
      - YOLOv8 (COCO) object detection -> mobile phone / book
      - DeepFace face detection -> face count + rough "looking away"
        estimate based on how far the face center is from the frame
        center.
    """

    if request.method != "POST":
        return JsonResponse({"success": False})

    student_id = request.session.get("student_id")

    if not student_id:
        return JsonResponse({"success": False})

    image_data = request.POST.get("image")

    if not image_data:
        return JsonResponse({"success": False})

    try:
        image_data = image_data.split(",")[1]
        image_bytes = base64.b64decode(image_data)

        np_arr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame is None:
            return JsonResponse({"success": False, "message": "Invalid frame."})

        frame_height, frame_width = frame.shape[:2]

        # ---------------- YOLO: phone / book detection ----------------
        detected_objects = []

        yolo_results = YOLO_MODEL(frame, verbose=False)

        for result in yolo_results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                label = YOLO_MODEL.names.get(class_id, "")

                if label in RESTRICTED_OBJECT_CLASSES and confidence >= YOLO_CONFIDENCE_THRESHOLD:
                    detected_objects.append(RESTRICTED_OBJECT_CLASSES[label])

        detected_objects = list(set(detected_objects))

        # ---------------- DeepFace: face count + gaze estimate ----------------
        face_count = 0
        looking_away = False

        try:
            faces = DeepFace.extract_faces(
                img_path=frame,
                detector_backend="mtcnn",
                enforce_detection=False
            )

            valid_faces = [f for f in faces if f.get("confidence", 0) > 0]
            face_count = len(valid_faces)

            if face_count == 1:
                region = valid_faces[0].get("facial_area", {})
                face_center_x = region.get("x", 0) + region.get("w", 0) / 2
                face_center_y = region.get("y", 0) + region.get("h", 0) / 2

                frame_center_x = frame_width / 2
                frame_center_y = frame_height / 2

                x_offset_ratio = abs(face_center_x - frame_center_x) / frame_width
                y_offset_ratio = abs(face_center_y - frame_center_y) / frame_height

                if x_offset_ratio > 0.22 or y_offset_ratio > 0.22:
                    looking_away = True

        except Exception:
            traceback.print_exc()

        return JsonResponse({
            "success": True,
            "detected_objects": detected_objects,
            "face_count": face_count,
            "looking_away": looking_away
        })

    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"success": False, "message": str(e)})