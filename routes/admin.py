from flask import Blueprint, request, render_template, redirect, url_for, session, flash
from utils.auth import admin_required, verify_admin_password
from utils.error_handler import handle_errors
import logging

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/login', methods=['GET', 'POST'])
@handle_errors
def login():
    if request.method == 'POST':
        if verify_admin_password(request.form.get('password')):
            session['is_admin'] = True
            return redirect(url_for('admin.dashboard'))
        flash('Invalid password')
    return render_template('admin/login.html')

@admin_bp.route('/admin/dashboard')
@handle_errors
@admin_required
def dashboard():
    return render_template('admin/dashboard.html')

@admin_bp.route('/admin/logout')
def logout():
    session.pop('is_admin', None)
    return redirect(url_for('home'))