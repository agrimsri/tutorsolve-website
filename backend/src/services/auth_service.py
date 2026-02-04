from src.db.database import db
from src.models.user import User, UserRole, UserStatus
from src.models.student import Student
from src.models.expert import Expert
from src.models.employee import Employee
from src.models.super_admin import SuperAdmin
from src.core.security import hash_password, verify_password


class AuthServiceError(Exception):
    pass


class AuthService:

    @staticmethod
    def signup_student(email, password, country, degree=None):
        if country in ("IN", "PK"):
            raise AuthServiceError("Students from this country are not allowed")

        if User.query.filter_by(email=email).first():
            raise AuthServiceError("Email already registered")

        user = User(
            email=email,
            password_hash=hash_password(password),
            role=UserRole.STUDENT,
            status=UserStatus.ACTIVE
        )

        db.session.add(user)
        db.session.flush()  # get user.id

        student = Student(
            user_id=user.id,
            country=country,
            degree=degree
        )

        db.session.add(student)
        db.session.commit()

        return user

    @staticmethod
    def signup_expert(email, password, domain):
        if User.query.filter_by(email=email).first():
            raise AuthServiceError("Email already registered")

        user = User(
            email=email,
            password_hash=hash_password(password),
            role=UserRole.EXPERT,
            status=UserStatus.PENDING  # requires approval
        )

        db.session.add(user)
        db.session.flush()

        expert = Expert(
            user_id=user.id,
            domain=domain
        )

        db.session.add(expert)
        db.session.commit()

        return user

    @staticmethod
    def login(email, password):
        user = User.query.filter_by(email=email).first()

        if not user:
            raise AuthServiceError("Invalid credentials")

        if user.status != UserStatus.ACTIVE:
            raise AuthServiceError("User not active")

        if not verify_password(password, user.password_hash):
            raise AuthServiceError("Invalid credentials")

        return user