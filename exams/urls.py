from django.urls import path
from . import views

urlpatterns = [
    path(
        "instructions/<int:exam_id>/",
        views.exam_instructions,
        name="exam_instructions",
    ),

    path(
        "permissions/<int:exam_id>/",
        views.permissions,
        name="permissions",
    ),

    path(
        "face-verification/<int:exam_id>/",
        views.face_verification,
        name="face_verification",
    ),

    path(
        "verify_face/<int:exam_id>/",
        views.verify_face,
        name="verify_face",
    ),

    path(
        "exam/<int:exam_id>/",
        views.exam_page,
        name="exam_page",
    ),

    path(
        "save-answer/",
        views.save_answer,
        name="save_answer",
    ),

    path(
        "submit/<int:exam_id>/",
        views.submit_exam,
        name="submit_exam",
    ),

    path(
        "result/<int:exam_id>/",
        views.result_page,
        name="result_page",
    ),

    path(
        "update-proctoring/",
        views.update_proctoring,
        name="update_proctoring",
    ),

    path(
        "detect-objects/",
        views.detect_objects,
        name="detect_objects",
    ),
]
