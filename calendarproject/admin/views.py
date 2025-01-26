from flask import Blueprint, render_template
from flask_login import login_required, current_user
from calendarproject.models.appointment import Appointment

admin = Blueprint('admin', __name__)


@admin.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_instructor:
        flash('Access denied. You must be an instructor to view this page.', 'error')
        return redirect(url_for('page.home'))

    # Fetch appointments for the current instructor
    appointments = Appointment.query.filter_by(instructor_id=current_user.id).all()

    # Separate booked and available appointments
    booked_appointments = [apt for apt in appointments if not apt.is_available]
    available_appointments = [apt for apt in appointments if apt.is_available]

    return render_template('admin/dashboard.html',
                           booked_appointments=booked_appointments,
                           available_appointments=available_appointments)