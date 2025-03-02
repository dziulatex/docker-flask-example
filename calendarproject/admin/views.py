from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from calendarproject.models.appointment import Appointment
from calendarproject.models.user import User
from calendarproject.extensions import db
from calendarproject.forms.forms import CreateInstructorForm

admin = Blueprint('admin', __name__)


@admin.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin:
        flash('Access denied. You must be an admin to view this page.', 'error')
        return redirect(url_for('page.home'))

    # Fetch appointments for the current instructor
    appointments = Appointment.query.filter_by(instructor_id=current_user.id).all()

    # Separate booked and available appointments
    booked_appointments = [apt for apt in appointments if not apt.is_available]
    available_appointments = [apt for apt in appointments if apt.is_available]

    # Get instructors for the instructor list
    instructors = User.query.filter_by(is_instructor=True).all()

    # Form for adding a new instructor
    form = CreateInstructorForm()

    return render_template('admin/dashboard.html',
                           booked_appointments=booked_appointments,
                           available_appointments=available_appointments,
                           instructors=instructors,
                           form=form)


@admin.route('/create_instructor', methods=['POST'])
@login_required
def create_instructor():
    if not current_user.is_admin:
        flash('Access denied. You must be an admin to perform this action.', 'error')
        return redirect(url_for('page.home'))

    form = CreateInstructorForm()

    if form.validate_on_submit():
        # Check if username already exists
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('Nazwa użytkownika już istnieje. Proszę wybrać inną.', 'error')
            return redirect(url_for('admin.dashboard'))

        # Check if email already exists
        existing_email = User.query.filter_by(email=form.email.data).first()
        if existing_email:
            flash('Adres email jest już używany. Proszę użyć innego adresu.', 'error')
            return redirect(url_for('admin.dashboard'))

        # Create new instructor
        new_instructor = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            is_instructor=True  # Set as instructor
        )
        new_instructor.set_password(form.password.data)

        try:
            db.session.add(new_instructor)
            db.session.commit()
            flash(f'Instruktor {new_instructor.username} został pomyślnie utworzony.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Wystąpił błąd podczas tworzenia instruktora: {str(e)}', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field.capitalize()}: {error}", 'error')

    return redirect(url_for('admin.dashboard'))