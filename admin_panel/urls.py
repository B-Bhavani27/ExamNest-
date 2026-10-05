from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.admin_login, name="admin_login"),
    path("logout/", views.admin_logout, name="admin_logout"),
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("students/", views.admin_students, name="admin_students"),
    path("rankings/", views.admin_rankings, name="admin_rankings"),

    path("export/students/", views.export_students, name="export_students"),
    path("export/ranking/overall/", views.export_overall_ranking, name="export_overall_ranking"),
    path("export/ranking/exam/<int:exam_id>/", views.export_exam_ranking, name="export_exam_ranking"),
    path("export/dashboard/", views.export_dashboard_summary, name="export_dashboard_summary"),
]
