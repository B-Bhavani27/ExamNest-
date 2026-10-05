from django.urls import path 
from . import views 
urlpatterns = [
    path('', views.index, name='index'),

    path(
        'student-login/',
        views.student_login,
        name='student_login'
    ),
    path(
    'forgot-password/',
    views.forgot_password,
    name='forgot_password'
    ),
    path(
    'verify-otp/<str:student_id>/',
    views.verify_otp,
    name='verify_otp'
    ),
    path(
    'reset-password/<str:student_id>/',
    views.reset_password,
    name='reset_password'
),
    path(
    'resend-otp/<str:student_id>/',
    views.resend_otp,
    name='resend_otp'
),


    path(
        'student-register/',
        views.student_register,
        name='student_register'
    ),
    path(
        'activation/<uuid:token>/',
        views.activation,
        name='activation'
    ),
    path(
        'student-dashboard/',
        views.student_dashboard,
        name='student_dashboard'
    ),


    path(
    'logout/',
    views.logout,
    name='logout'
),

    ]