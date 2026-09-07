from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from webapp.forms import RegistrationForm, LoginForm
from webapp.services.auth_service import register_user, authenticate_user

bp = Blueprint('auth', __name__)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        register_user(form.username.data, form.password.data)
        flash('Account created. You can log in now.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html', form=form)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = authenticate_user(form.username.data, form.password.data)
        if user is None:
            flash('Incorrect username or password.', 'error')
            return redirect(url_for('auth.login'))
        login_user(user)
        flash(f'Welcome back, {user.username}.', 'success')
        return redirect(url_for('main.index'))
    return render_template('login.html', form=form)


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'success')
    return redirect(url_for('main.index'))
