from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from dateutil import parser
import pytz
from sqlalchemy.orm import joinedload
from datetime import time
from datetime import datetime, timedelta, timezone
from calendarproject.models.appointment import Appointment
from calendarproject.extensions import db
from sqlalchemy import cast, DateTime, func
from datetime import datetime, timedelta
import json

from calendarproject.models.notification import Notification

instructor = Blueprint('instructor', __name__)


@instructor.route('/instructor/calendar')
@login_required
def calendar():
    if not current_user.is_instructor:
        flash('Dostęp zabroniony. Musisz być instruktorem, aby wyświetlić tę stronę.', 'error')
        return redirect(url_for('page.home'))
    return render_template('instructor/calendar.html')


@instructor.route('/instructor/get_appointments', methods=['GET'])
@login_required
def get_appointments():
    if not current_user.is_instructor:
        return jsonify([])

    # Pobierz parametry zapytania
    start_str = request.args.get('start', type=str)
    end_str = request.args.get('end', type=str)
    tz_str = request.args.get('timeZone', type=str, default='UTC')

    try:
        # Parsowanie strefy czasowej
        try:
            tz = pytz.timezone(tz_str)
        except pytz.UnknownTimeZoneError:
            return jsonify({'status': 'error', 'message': 'Nieznana strefa czasowa'}), 400

        # Parsowanie start i end
        start = parser.isoparse(start_str)
        end = parser.isoparse(end_str)

        # Lokalizacja dat, jeśli są "naiwne"
        if start.tzinfo is None:
            start = tz.localize(start)
        else:
            start = start.astimezone(tz)

        if end.tzinfo is None:
            end = tz.localize(end)
        else:
            end = end.astimezone(tz)

        # Konwersja na UTC, zakładając, że baza danych przechowuje czasy w UTC
        start_utc = start.astimezone(pytz.UTC)
        end_utc = end.astimezone(pytz.UTC)

        # Filtrowanie terminów z joinedload dla studenta
        appointments = Appointment.query.options(joinedload(Appointment.student)).filter(
            Appointment.instructor_id == current_user.id,
            Appointment.start_time >= start_utc,
            Appointment.start_time <= end_utc
        ).all()

        # Przygotowanie wydarzeń do zwrócenia
        events = []
        for appointment in appointments:
            student_name = f"{appointment.student.first_name} {appointment.student.last_name}" if appointment.student else ""
            events.append({
                'id': appointment.id,
                'title': 'Dostępny' if appointment.is_available else f'Temat konsultacji: {appointment.topic}',
                'student': student_name,
                'is_available': appointment.is_available,
                'start': appointment.start_time.isoformat(),
                'end': appointment.end_time.isoformat(),
                'color': 'green' if appointment.is_available else 'blue',
                'status': appointment.status
            })

        return jsonify(events)

    except Exception as e:
        print(f"Błąd w get_appointments: {e}")
        return jsonify({'status': 'error', 'message': 'Nieprawidłowe żądanie'}), 400


@instructor.route('/instructor/add_appointment', methods=['POST'])
@login_required
def add_appointment():
    if not current_user.is_instructor:
        return jsonify({'status': 'error', 'message': 'Odmowa dostępu'}), 403

    try:
        data = json.loads(request.data)
        start_time = datetime.fromisoformat(data['start'])
        end_time = datetime.fromisoformat(data['end'])

        # Upewnij się, że daty zawierają informację o strefie czasowej
        if start_time.tzinfo is None or end_time.tzinfo is None:
            return jsonify(
                {'status': 'error', 'message': 'Nieprawidłowy format daty. Brak informacji o strefie czasowej.'}), 400

        # Oblicz aktualny czas w tej samej strefie czasowej co start_time
        now = datetime.now(timezone.utc).astimezone(start_time.tzinfo)

        # Sprawdź czy start_time jest co najmniej godzinę w przyszłości
        if start_time < now + timedelta(hours=1):
            return jsonify(
                {'status': 'error', 'message': 'Termin musi być co najmniej godzinę do przodu od obecnego czasu.'}), 400

        # Sprawdź czy end_time jest po start_time
        if end_time <= start_time:
            return jsonify({'status': 'error', 'message': 'Czas zakończenia musi być po czasie rozpoczęcia.'}), 400

        # Sprawdź czy to termin całodniowy
        is_full_day = start_time.time() == time(0, 0) and end_time.time() == time(23, 59, 59)

        if is_full_day:
            # Sprawdź, czy istnieją już terminy na ten dzień
            existing_appointments = Appointment.query.filter(
                Appointment.instructor_id == current_user.id,
                func.date(Appointment.start_time) == start_time.date()
            ).first()

            if existing_appointments:
                return jsonify({'status': 'error',
                                'message': 'Nie można dodać całodniowego terminu, ponieważ istnieją już terminy w tym dniu.'}), 400

        new_appointment = Appointment(
            instructor_id=current_user.id,
            start_time=start_time,
            end_time=end_time,
            is_available=True
        )
        db.session.add(new_appointment)
        db.session.commit()
        return jsonify({'status': 'success', 'id': new_appointment.id}), 201

    except json.JSONDecodeError:
        return jsonify({'status': 'error', 'message': 'Nieprawidłowe dane JSON.'}), 400
    except KeyError as e:
        return jsonify({'status': 'error', 'message': f'Brakujący klucz: {e.args[0]}'}), 400
    except ValueError as e:
        return jsonify({'status': 'error', 'message': f'Nieprawidłowy format daty: {str(e)}'}), 400
    except Exception as e:
        # Zaloguj wyjątek jeśli to konieczne
        return jsonify({'status': 'error', 'message': 'Wystąpił nieoczekiwany błąd.'}), 500


@instructor.route('/instructor/delete_appointment', methods=['POST'])
@login_required
def delete_appointment():
    if not current_user.is_instructor:
        return jsonify({'status': 'error', 'message': 'Odmowa dostępu'}), 403
    data = json.loads(request.data)
    appointment_id = data['id']
    appointment = Appointment.query.get(appointment_id)
    if appointment and appointment.instructor_id == current_user.id and appointment.is_available:
        db.session.delete(appointment)
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Termin nie został znaleziony lub nie jest dostępny'}), 404


@instructor.route('/instructor/confirm_appointment/<int:appointment_id>', methods=['POST'])
@login_required
def confirm_appointment(appointment_id):
    if not current_user.is_instructor:
        return jsonify({'status': 'error', 'message': 'Brak autoryzacji'}), 403

    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.instructor_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Brak autoryzacji'}), 403
    if appointment.status != 'pending':
        return jsonify({'status': 'error', 'message': 'Wizyta została już zaakceptowana'}), 403
    appointment.status = 'confirmed'
    db.session.commit()
    notification = Notification(
        user_id=appointment.student_id,
        message=f'Twoja wizyta na {appointment.start_time.strftime("%Y-%m-%d %H:%M")} została zaakceptowana.',
        type="appointment",
        related_id=appointment.id
    )
    db.session.add(notification)
    db.session.commit()
    return jsonify({'status': 'success'})


@instructor.route('/instructor/cancel_appointment/<int:appointment_id>', methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    if not current_user.is_instructor:
        return jsonify({'status': 'error', 'message': 'Brak autoryzacji'}), 403

    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.instructor_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Brak autoryzacji'}), 403
    if appointment.status != 'confirmed':
        return jsonify({'status': 'error', 'message': 'Wizyta została już zcancelowana'}), 403
    appointment.status = 'pending'
    appointment.student = None
    appointment.topic = None;
    appointment.is_available = True;
    db.session.commit()
    notification = Notification(
        user_id=appointment.student_id,
        message=f'Twoja wizyta na {appointment.start_time.strftime("%Y-%m-%d %H:%M")} została anulowana.',
        type="appointment",
        related_id=appointment.id
    )
    db.session.add(notification)
    db.session.commit()
    return jsonify({'status': 'success'})

@instructor.route('/instructor/reject_appointment/<int:appointment_id>', methods=['POST'])
@login_required
def reject_appointment(appointment_id):
    if not current_user.is_instructor:
        return jsonify({'status': 'error', 'message': 'Brak autoryzacji'}), 403

    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.instructor_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Brak autoryzacji'}), 403
    # Tworzenie notyfikacji dla studenta
    notification = Notification(
        user_id=appointment.student_id,
        message=f'Twoja wizyta na {appointment.start_time.strftime("%Y-%m-%d %H:%M")} została odrzucona.',
        type="appointment",
        related_id=appointment.id
    )
    appointment.status = 'rejected'
    appointment.is_available = True
    appointment.student_id = None
    appointment.topic = None
    db.session.commit()

    db.session.add(notification)
    db.session.commit()
    return jsonify({'status': 'success'})
