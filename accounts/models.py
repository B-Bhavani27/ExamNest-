from django.db import models
import uuid
from django.db import models
import uuid
from django.utils import timezone

class Student(models.Model):

    student_id = models.CharField(max_length=20, unique=True, blank=True)

    full_name = models.CharField(max_length=200)

    email = models.EmailField(unique=True)

    dob = models.DateField()

    college_name = models.CharField(max_length=255)

    study_level = models.CharField(max_length=20)

    degree = models.CharField(max_length=100)

    department = models.CharField(max_length=100)

    house_no = models.CharField(max_length=50)

    street_area = models.CharField(max_length=255)

    city = models.CharField(max_length=100)

    district = models.CharField(max_length=100)

    state = models.CharField(max_length=100)

    pincode = models.CharField(max_length=20)

    country = models.CharField(max_length=100)

    photo = models.ImageField(upload_to="student_photos/")

    is_active = models.BooleanField(default=False)

    activation_token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True
    )

    password = models.CharField(
        max_length=255,
        blank=True
    )

    otp = models.CharField(
    max_length=6,
    blank=True,
    null=True
    )

    otp_created_at = models.DateTimeField(
    blank=True,
    null=True
    )

    otp_verified = models.BooleanField(
        default=False
    )


    

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):

        if not self.student_id:

            last_student = Student.objects.order_by("-id").first()

            if last_student:
                last_id = int(last_student.student_id.replace("EXN", ""))
                self.student_id = f"EXN{last_id + 1:04d}"
            else:
                self.student_id = "EXN0001"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student_id} - {self.full_name}"