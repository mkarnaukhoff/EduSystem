# =============================================================================
#  app.py — Информационная система образовательной организации «EduSystem»
# =============================================================================

import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, flash, session
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///education.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# =============================================================================
#  МОДЕЛИ БАЗЫ ДАННЫХ
# =============================================================================

class User(db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role          = db.Column(db.String(20),  default='student')
    full_name     = db.Column(db.String(100))
    phone         = db.Column(db.String(20))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    is_active     = db.Column(db.Boolean,  default=True)

    # Связи
    enrollments = db.relationship('Enrollment', backref='student', lazy=True)
    teacher_profile = db.relationship('Teacher', backref='user', uselist=False)
    
    # Для grades явно указываем foreign_keys
    grades_as_student = db.relationship('GradeItem', foreign_keys='GradeItem.student_id', backref='student', lazy=True)
    grades_as_teacher = db.relationship('GradeItem', foreign_keys='GradeItem.graded_by', backref='grader', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Teacher(db.Model):
    __tablename__ = 'teachers'
    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    bio       = db.Column(db.Text)
    email     = db.Column(db.String(120))
    phone     = db.Column(db.String(20))

    courses = db.relationship('Course', backref='teacher', lazy=True)


class Course(db.Model):
    __tablename__ = 'courses'
    id          = db.Column(db.Integer, primary_key=True)
    code        = db.Column(db.String(20),  unique=True, nullable=False)
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    hours       = db.Column(db.Integer, default=36)
    teacher_id  = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    enrollments = db.relationship('Enrollment', backref='course', lazy=True)
    grades      = db.relationship('GradeItem', backref='course', lazy=True)
    schedule    = db.relationship('Schedule', backref='course', lazy=True, cascade='all, delete-orphan')


class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    id              = db.Column(db.Integer, primary_key=True)
    student_id      = db.Column(db.Integer, db.ForeignKey('users.id'),   nullable=False)
    course_id       = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    enrollment_date = db.Column(db.DateTime, default=datetime.utcnow)
    status          = db.Column(db.String(20), default='enrolled')

    __table_args__ = (db.UniqueConstraint('student_id', 'course_id', name='unique_enrollment'),)


class GradeItem(db.Model):
    __tablename__ = 'grade_items'
    id         = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'),   nullable=False)
    course_id  = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title      = db.Column(db.String(200), nullable=False)
    score      = db.Column(db.Float, nullable=False)
    weight     = db.Column(db.Float, default=1.0)
    graded_at  = db.Column(db.DateTime, default=datetime.utcnow)
    graded_by  = db.Column(db.Integer, db.ForeignKey('users.id'))


class Schedule(db.Model):
    __tablename__ = 'schedule'
    id          = db.Column(db.Integer, primary_key=True)
    course_id   = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    day_of_week = db.Column(db.String(20))
    start_time  = db.Column(db.String(10))
    end_time    = db.Column(db.String(10))
    room        = db.Column(db.String(50))


class Announcement(db.Model):
    __tablename__ = 'announcements'
    id           = db.Column(db.Integer, primary_key=True)
    title        = db.Column(db.String(200), nullable=False)
    content      = db.Column(db.Text, nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    created_by   = db.Column(db.Integer, db.ForeignKey('users.id'))
    is_published = db.Column(db.Boolean, default=True)


# =============================================================================
#  ДЕКОРАТОРЫ
# =============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if user.role != 'admin':
            flash('Доступ запрещён', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


# =============================================================================
#  ПУБЛИЧНЫЕ МАРШРУТЫ
# =============================================================================

@app.route('/')
def index():
    courses = Course.query.filter_by(is_active=True).limit(6).all()
    announcements = Announcement.query.filter_by(is_published=True)\
        .order_by(Announcement.created_at.desc()).limit(3).all()
    teachers = Teacher.query.limit(3).all()
    return render_template('index.html', courses=courses,
                           announcements=announcements, teachers=teachers)


@app.route('/courses')
def courses():
    search = request.args.get('search')
    query = Course.query.filter_by(is_active=True)
    if search:
        query = query.filter(Course.name.contains(search) | Course.code.contains(search))
    return render_template('courses.html', courses=query.all())


@app.route('/course/<int:course_id>')
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    is_enrolled = False
    grade_items = []
    final_grade = None
    final_letter = '-'

    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user.role == 'student':
            enrollment = Enrollment.query.filter_by(student_id=user.id, course_id=course_id).first()
            is_enrolled = enrollment is not None and enrollment.status == 'enrolled'
            if is_enrolled:
                grade_items = GradeItem.query.filter_by(student_id=user.id, course_id=course_id).all()
                if grade_items:
                    total_score = sum(i.score * i.weight for i in grade_items)
                    total_weight = sum(i.weight for i in grade_items)
                    final_grade = round(total_score / total_weight, 1) if total_weight > 0 else 0
                    if final_grade >= 90:
                        final_letter = 'Отлично'
                    elif final_grade >= 80:
                        final_letter = 'Хорошо'
                    elif final_grade >= 60:
                        final_letter = 'Удовлетворительно'
                    else:
                        final_letter = 'Неудовлетворительно'

    return render_template('course_detail.html', course=course, is_enrolled=is_enrolled,
                           grade_items=grade_items, final_grade=final_grade, final_letter=final_letter)


@app.route('/schedule')
def schedule():
    schedules = Schedule.query.all()
    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
    return render_template('schedule.html', schedules=schedules, days=days)


@app.route('/teachers')
def teachers():
    return render_template('teachers.html', teachers=Teacher.query.all())


# =============================================================================
#  АУТЕНТИФИКАЦИЯ
# =============================================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        full_name = request.form.get('full_name')

        if not username or not email or not password:
            flash('Заполните все обязательные поля', 'danger')
            return redirect(url_for('register'))

        if len(password) < 8:
            flash('Пароль должен быть минимум 8 символов', 'danger')
            return redirect(url_for('register'))

        if password != confirm:
            flash('Пароли не совпадают', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Имя пользователя занято', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email уже зарегистрирован', 'danger')
            return redirect(url_for('register'))

        user = User(username=username, email=email, full_name=full_name, role='student')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Регистрация успешна! Войдите в систему.', 'success')
        return redirect(url_for('login'))

    return render_template('auth.html', action='register')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash(f'Добро пожаловать, {user.full_name or user.username}!', 'success')
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')

    return render_template('auth.html', action='login')


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


# =============================================================================
#  ЛИЧНЫЙ КАБИНЕТ
# =============================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])

    if user.role == 'student':
        enrollments = Enrollment.query.filter_by(student_id=user.id, status='enrolled').all()
        completed = Enrollment.query.filter_by(student_id=user.id, status='completed').all()
        return render_template('dashboard.html', user=user, enrollments=enrollments, completed=completed)

    elif user.role == 'teacher':
        teacher = Teacher.query.filter_by(user_id=user.id).first()
        courses = Course.query.filter_by(teacher_id=teacher.id).all() if teacher else []
        students_count = Enrollment.query.filter(Enrollment.course_id.in_([c.id for c in courses])).count() if courses else 0
        return render_template('dashboard.html', user=user, teacher=teacher, courses=courses, students_count=students_count)

    return redirect(url_for('admin_dashboard'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        user.full_name = request.form.get('full_name')
        user.phone = request.form.get('phone')

        new_pass = request.form.get('new_password')
        if new_pass:
            if new_pass == request.form.get('confirm_password'):
                user.set_password(new_pass)
                flash('Пароль изменён', 'success')
            else:
                flash('Пароли не совпадают', 'danger')
                return redirect(url_for('profile'))

        db.session.commit()
        flash('Профиль обновлён', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html', user=user)


# =============================================================================
#  СТУДЕНТ
# =============================================================================

@app.route('/enroll/<int:course_id>', methods=['POST'])
@login_required
def enroll(course_id):
    user = User.query.get(session['user_id'])
    course = Course.query.get_or_404(course_id)

    if user.role != 'student':
        flash('Только студенты могут записываться на курсы', 'danger')
        return redirect(url_for('course_detail', course_id=course_id))

    if Enrollment.query.filter_by(student_id=user.id, course_id=course_id).first():
        flash('Вы уже записаны на этот курс', 'warning')
        return redirect(url_for('course_detail', course_id=course_id))

    enrollment = Enrollment(student_id=user.id, course_id=course_id, status='enrolled')
    db.session.add(enrollment)
    db.session.commit()
    flash(f'Вы записаны на курс "{course.name}"', 'success')
    return redirect(url_for('course_detail', course_id=course_id))


@app.route('/my-courses')
@login_required
def my_courses():
    user = User.query.get(session['user_id'])

    if user.role == 'student':
        enrollments = Enrollment.query.filter_by(student_id=user.id).all()
        return render_template('my_courses.html', enrollments=enrollments)

    elif user.role == 'teacher':
        teacher = Teacher.query.filter_by(user_id=user.id).first()
        courses = Course.query.filter_by(teacher_id=teacher.id).all() if teacher else []
        return render_template('my_courses.html', courses=courses, is_teacher=True)

    return redirect(url_for('admin_dashboard'))


@app.route('/grades')
@login_required
def grades():
    user = User.query.get(session['user_id'])
    if user.role != 'student':
        flash('Только для студентов', 'danger')
        return redirect(url_for('dashboard'))

    grade_items = GradeItem.query.filter_by(student_id=user.id).all()
    course_summary = {}

    for item in grade_items:
        if item.course_id not in course_summary:
            course_summary[item.course_id] = {
                'total': 0, 'count': 0, 'course': Course.query.get(item.course_id)
            }
        course_summary[item.course_id]['total'] += item.score
        course_summary[item.course_id]['count'] += 1

    for cid in course_summary:
        avg = course_summary[cid]['total'] / course_summary[cid]['count']
        course_summary[cid]['avg'] = round(avg, 1)
        if avg >= 90:
            course_summary[cid]['letter'] = 'Отлично'
        elif avg >= 80:
            course_summary[cid]['letter'] = 'Хорошо'
        elif avg >= 60:
            course_summary[cid]['letter'] = 'Удовлетворительно'
        else:
            course_summary[cid]['letter'] = 'Неудовлетворительно'

    return render_template('grades.html', grade_items=grade_items, course_summary=course_summary)


# =============================================================================
#  ПРЕПОДАВАТЕЛЬ
# =============================================================================

@app.route('/my_courses_teacher')
@login_required
def my_courses_teacher():
    user = User.query.get(session['user_id'])
    if user.role != 'teacher':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))

    teacher = Teacher.query.filter_by(user_id=user.id).first()
    if not teacher:
        flash('Профиль преподавателя не найден', 'danger')
        return redirect(url_for('dashboard'))

    courses = Course.query.filter_by(teacher_id=teacher.id).all()
    return render_template('my_courses_teacher.html', courses=courses)


@app.route('/course/<int:course_id>/students')
@login_required
def course_students(course_id):
    user = User.query.get(session['user_id'])
    course = Course.query.get_or_404(course_id)

    if user.role != 'teacher':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))

    teacher = Teacher.query.filter_by(user_id=user.id).first()
    if not teacher or course.teacher_id != teacher.id:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))

    enrollments = Enrollment.query.filter_by(course_id=course_id, status='enrolled').all()
    students_with_grades = []

    for enrollment in enrollments:
        student = User.query.get(enrollment.student_id)
        grade_items = GradeItem.query.filter_by(student_id=student.id, course_id=course_id).all()
        avg_grade = round(sum(g.score for g in grade_items) / len(grade_items), 1) if grade_items else None

        students_with_grades.append({
            'student': student,
            'enrollment': enrollment,
            'grade_items': grade_items,
            'avg_grade': avg_grade
        })

    return render_template('course_students.html', course=course, students=students_with_grades)


@app.route('/grade/save', methods=['POST'])
@login_required
def save_grade():
    user = User.query.get(session['user_id'])
    if user.role != 'teacher':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))

    student_id = request.form.get('student_id')
    course_id = request.form.get('course_id')
    title = request.form.get('title')
    score = request.form.get('score')

    teacher = Teacher.query.filter_by(user_id=user.id).first()
    course = Course.query.get_or_404(course_id)

    if course.teacher_id != teacher.id:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))

    try:
        score = float(score)
        if score < 0 or score > 100:
            raise ValueError
    except:
        flash('Оценка должна быть числом от 0 до 100', 'danger')
        return redirect(url_for('course_students', course_id=course_id))

    existing = GradeItem.query.filter_by(student_id=student_id, course_id=course_id, title=title).first()
    if existing:
        existing.score = score
        flash('Оценка обновлена', 'success')
    else:
        new_grade = GradeItem(student_id=student_id, course_id=course_id, title=title, score=score, graded_by=user.id)
        db.session.add(new_grade)
        flash('Оценка выставлена', 'success')

    db.session.commit()
    return redirect(url_for('course_students', course_id=course_id))


@app.route('/grade/delete/<int:grade_id>')
@login_required
def delete_grade(grade_id):
    user = User.query.get(session['user_id'])
    grade = GradeItem.query.get_or_404(grade_id)

    if user.role != 'teacher':
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))

    teacher = Teacher.query.filter_by(user_id=user.id).first()
    course = Course.query.get(grade.course_id)

    if course.teacher_id != teacher.id:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))

    course_id = grade.course_id
    db.session.delete(grade)
    db.session.commit()
    flash('Оценка удалена', 'success')
    return redirect(url_for('course_students', course_id=course_id))


# =============================================================================
#  АДМИНИСТРАТОР
# =============================================================================

@app.route('/admin')
@admin_required
def admin_dashboard():
    section = request.args.get('section', 'dashboard')
    entity_id = request.args.get('id')

    users = User.query.all() if section in ['users', 'edit_user'] else []
    courses = Course.query.all() if section in ['courses', 'edit_course'] else []
    enrollments = Enrollment.query.all() if section == 'enrollments' else []
    teachers = Teacher.query.all() if section in ['teachers', 'edit_teacher'] else []
    announcements = Announcement.query.all() if section in ['announcements', 'edit_announcement'] else []
    schedule = Schedule.query.all() if section in ['schedule', 'edit_schedule'] else []

    edit_item = None
    edit_type = None
    if entity_id:
        if section == 'edit_user':
            edit_item, edit_type = User.query.get(entity_id), 'user'
        elif section == 'edit_course':
            edit_item, edit_type = Course.query.get(entity_id), 'course'
        elif section == 'edit_teacher':
            edit_item, edit_type = Teacher.query.get(entity_id), 'teacher'
        elif section == 'edit_announcement':
            edit_item, edit_type = Announcement.query.get(entity_id), 'announcement'
        elif section == 'edit_schedule':
            edit_item, edit_type = Schedule.query.get(entity_id), 'schedule'

    stats = {
        'total_students': User.query.filter_by(role='student').count(),
        'total_teachers': User.query.filter_by(role='teacher').count(),
        'total_courses': Course.query.count(),
        'total_enrollments': Enrollment.query.count(),
    }

    return render_template('admin.html', section=section, users=users, courses=courses,
                           enrollments=enrollments, teachers=teachers, announcements=announcements,
                           schedule=schedule, edit_item=edit_item, edit_type=edit_type, stats=stats)


@app.route('/admin/<action>/<entity>', methods=['POST'])
@admin_required
def admin_action(action, entity):
    if action == 'add':
        if entity == 'course':
            course = Course(
                code=request.form.get('code'),
                name=request.form.get('name'),
                description=request.form.get('description'),
                hours=int(request.form.get('hours')),
                teacher_id=int(request.form.get('teacher_id')),
                is_active='is_active' in request.form
            )
            db.session.add(course)
            flash('Курс добавлен', 'success')

        elif entity == 'announcement':
            announcement = Announcement(
                title=request.form.get('title'),
                content=request.form.get('content'),
                created_by=session['user_id'],
                is_published='is_published' in request.form
            )
            db.session.add(announcement)
            flash('Объявление добавлено', 'success')

        elif entity == 'schedule':
            schedule = Schedule(
                course_id=int(request.form.get('course_id')),
                day_of_week=request.form.get('day_of_week'),
                start_time=request.form.get('start_time'),
                end_time=request.form.get('end_time'),
                room=request.form.get('room')
            )
            db.session.add(schedule)
            flash('Занятие добавлено', 'success')

        elif entity == 'teacher':
            username = request.form.get('username')
            email = request.form.get('email')
            full_name = request.form.get('full_name')

            if not User.query.filter_by(username=username).first():
                user = User(username=username, email=email, full_name=full_name, role='teacher', is_active=True)
                user.set_password('teacher123')
                db.session.add(user)
                db.session.flush()

                teacher = Teacher(user_id=user.id, full_name=full_name, bio=request.form.get('bio'), email=email)
                db.session.add(teacher)
                flash('Преподаватель добавлен (пароль: teacher123)', 'success')
            else:
                flash('Пользователь с таким логином уже существует', 'danger')
                db.session.rollback()
                return redirect(url_for('admin_dashboard', section='teachers'))

    elif action == 'edit':
        if entity == 'user':
            user = User.query.get(request.form.get('id'))
            user.role = request.form.get('role')
            user.is_active = 'is_active' in request.form
            flash('Пользователь обновлён', 'success')

        elif entity == 'course':
            course = Course.query.get(request.form.get('id'))
            course.code = request.form.get('code')
            course.name = request.form.get('name')
            course.description = request.form.get('description')
            course.hours = int(request.form.get('hours'))
            course.teacher_id = int(request.form.get('teacher_id'))
            course.is_active = 'is_active' in request.form
            flash('Курс обновлён', 'success')

        elif entity == 'teacher':
            teacher = Teacher.query.get(request.form.get('id'))
            teacher.full_name = request.form.get('full_name')
            teacher.bio = request.form.get('bio')
            teacher.email = request.form.get('email')
            teacher.phone = request.form.get('phone')
            if teacher.user:
                teacher.user.full_name = teacher.full_name
                teacher.user.email = teacher.email
            flash('Преподаватель обновлён', 'success')

        elif entity == 'announcement':
            ann = Announcement.query.get(request.form.get('id'))
            ann.title = request.form.get('title')
            ann.content = request.form.get('content')
            ann.is_published = 'is_published' in request.form
            flash('Объявление обновлено', 'success')

        elif entity == 'schedule':
            sched = Schedule.query.get(request.form.get('id'))
            sched.course_id = int(request.form.get('course_id'))
            sched.day_of_week = request.form.get('day_of_week')
            sched.start_time = request.form.get('start_time')
            sched.end_time = request.form.get('end_time')
            sched.room = request.form.get('room')
            flash('Расписание обновлено', 'success')

    elif action == 'delete':
        if entity == 'user':
            user = User.query.get(request.form.get('id'))
            GradeItem.query.filter_by(student_id=user.id).delete()
            Enrollment.query.filter_by(student_id=user.id).delete()
            db.session.delete(user)
            flash('Пользователь удалён', 'success')

        elif entity == 'course':
            course = Course.query.get(request.form.get('id'))
            db.session.delete(course)
            flash('Курс удалён', 'success')

        elif entity == 'teacher':
            teacher = Teacher.query.get(request.form.get('id'))
            if teacher.user:
                db.session.delete(teacher.user)
            db.session.delete(teacher)
            flash('Преподаватель удалён', 'success')

        elif entity == 'announcement':
            ann = Announcement.query.get(request.form.get('id'))
            db.session.delete(ann)
            flash('Объявление удалено', 'success')

        elif entity == 'schedule':
            sched = Schedule.query.get(request.form.get('id'))
            db.session.delete(sched)
            flash('Запись из расписания удалена', 'success')

    elif action == 'update_status' and entity == 'enrollment':
        enrollment = Enrollment.query.get(request.form.get('id'))
        enrollment.status = request.form.get('status')
        flash('Статус записи обновлён', 'success')

    db.session.commit()

    section_map = {
        'user': 'users', 'course': 'courses', 'teacher': 'teachers',
        'announcement': 'announcements', 'schedule': 'schedule', 'enrollment': 'enrollments'
    }
    return redirect(url_for('admin_dashboard', section=section_map.get(entity, 'dashboard')))


# =============================================================================
#  ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
# =============================================================================

def init_db():
    with app.app_context():
        db.create_all()

        if not User.query.filter_by(role='admin').first():
            admin = User(username='admin', email='admin@edu.ru', full_name='Администратор', role='admin', is_active=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Создан администратор: admin / admin123")

        teachers_data = [
            ('ivanov', 'Иванов Иван Иванович', 'ivanov@edu.ru', 'Преподаватель информатики'),
            ('petrova', 'Петрова Мария Сергеевна', 'petrova@edu.ru', 'Преподаватель математики'),
            ('sidorov', 'Сидоров Алексей Владимирович', 'sidorov@edu.ru', 'Преподаватель программирования'),
            ('kozlova', 'Козлова Екатерина Андреевна', 'kozlova@edu.ru', 'Преподаватель баз данных'),
            ('morozov', 'Морозов Дмитрий Петрович', 'morozov@edu.ru', 'Преподаватель ИБ'),
            ('volkova', 'Волкова Анна Игоревна', 'volkova@edu.ru', 'Преподаватель веб-дизайна'),
        ]

        teacher_ids = {}
        for username, full_name, email, bio in teachers_data:
            if not User.query.filter_by(username=username).first():
                user = User(username=username, email=email, full_name=full_name, role='teacher', is_active=True)
                user.set_password('teacher123')
                db.session.add(user)
                db.session.flush()
                teacher = Teacher(user_id=user.id, full_name=full_name, bio=bio, email=email)
                db.session.add(teacher)
                db.session.flush()
                teacher_ids[username] = teacher.id
                print(f"Создан преподаватель: {username} / teacher123")
            else:
                user = User.query.filter_by(username=username).first()
                teacher = Teacher.query.filter_by(user_id=user.id).first()
                if teacher:
                    teacher_ids[username] = teacher.id

        courses_data = [
            ('CS101', 'Основы программирования', 64, 'ivanov', 'Введение в Python'),
            ('CS102', 'ООП', 64, 'ivanov', 'Объектно-ориентированное программирование'),
            ('MA101', 'Высшая математика', 80, 'petrova', 'Математический анализ'),
            ('DB201', 'Базы данных', 48, 'kozlova', 'SQL'),
            ('WEB301', 'Веб-технологии', 64, 'sidorov', 'Flask'),
            ('IS401', 'Инфобезопасность', 48, 'morozov', 'Шифрование'),
            ('WD201', 'Веб-дизайн', 48, 'volkova', 'UX/UI'),
            ('CS202', 'Алгоритмы', 64, 'ivanov', 'Алгоритмы сортировки'),
        ]

        for code, name, hours, teacher_username, desc in courses_data:
            if not Course.query.filter_by(code=code).first():
                course = Course(code=code, name=name, description=desc, hours=hours, teacher_id=teacher_ids.get(teacher_username, 1))
                db.session.add(course)
        db.session.commit()

        cs101 = Course.query.filter_by(code='CS101').first()
        cs102 = Course.query.filter_by(code='CS102').first()
        ma101 = Course.query.filter_by(code='MA101').first()
        db201 = Course.query.filter_by(code='DB201').first()
        web301 = Course.query.filter_by(code='WEB301').first()
        is401 = Course.query.filter_by(code='IS401').first()
        cs202 = Course.query.filter_by(code='CS202').first()

        students_data = [
            ('petrov', 'Петров Пётр Петрович', 'petrov@student.ru', [cs101, cs102, cs202]),
            ('sidorova', 'Сидорова Анна Владимировна', 'sidorova@student.ru', [ma101, web301]),
            ('kozlov', 'Козлов Сергей Андреевич', 'kozlov@student.ru', [db201, is401]),
        ]

        for username, full_name, email, courses_list in students_data:
            if not User.query.filter_by(username=username).first():
                user = User(username=username, email=email, full_name=full_name, role='student', is_active=True)
                user.set_password('student123')
                db.session.add(user)
                db.session.flush()
                for course in courses_list:
                    if course:
                        db.session.add(Enrollment(student_id=user.id, course_id=course.id))
                print(f"Создан студент: {username} / student123")
        db.session.commit()

        petrov = User.query.filter_by(username='petrov').first()
        ivanov_user = User.query.filter_by(username='ivanov').first()
        if petrov and cs101:
            grades_data = [
                (cs101.id, 'Лабораторная №1', 88), (cs101.id, 'Лабораторная №2', 92),
                (cs101.id, 'Контрольная', 85), (cs101.id, 'Экзамен', 90),
                (cs102.id, 'Лабораторная №1', 75), (cs102.id, 'Лабораторная №2', 80),
                (cs102.id, 'Курсовой проект', 78), (cs202.id, 'Лабораторная №1', 68),
                (cs202.id, 'Лабораторная №2', 72), (cs202.id, 'Контрольная', 65),
            ]
            for course_id, title, score in grades_data:
                if not GradeItem.query.filter_by(student_id=petrov.id, course_id=course_id, title=title).first():
                    db.session.add(GradeItem(student_id=petrov.id, course_id=course_id, title=title, score=score, graded_by=ivanov_user.id if ivanov_user else None))
            db.session.commit()

        schedule_data = [
            (cs101, 'Понедельник', '09:00', '10:30', '101'), (ma101, 'Понедельник', '11:00', '12:30', '102'),
            (cs102, 'Вторник', '09:00', '10:30', '103'), (web301, 'Вторник', '11:00', '12:30', '104'),
            (db201, 'Среда', '09:00', '10:30', '101'), (cs101, 'Среда', '11:00', '12:30', '102'),
            (is401, 'Четверг', '09:00', '10:30', '103'), (cs202, 'Пятница', '09:00', '10:30', '101'),
            (ma101, 'Пятница', '11:00', '12:30', '102'),
        ]
        for course, day, start, end, room in schedule_data:
            if course and not Schedule.query.filter_by(course_id=course.id, day_of_week=day).first():
                db.session.add(Schedule(course_id=course.id, day_of_week=day, start_time=start, end_time=end, room=room))
        db.session.commit()

        if Announcement.query.count() == 0:
            admin_user = User.query.filter_by(username='admin').first()
            db.session.add(Announcement(title='Добро пожаловать в EduSystem!', content='Уважаемые студенты и преподаватели!', created_by=admin_user.id if admin_user else 1))
            db.session.add(Announcement(title='График экзаменов', content='Расписание сессии будет опубликовано до 15 июня.', created_by=admin_user.id if admin_user else 1))
            db.session.commit()

        print("\n=== База данных готова! ===")
        print("  Admin:    admin / admin123")
        print("  Teacher:  ivanov / teacher123")
        print("  Student:  petrov / student123")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_db()
    app.run(debug=True)