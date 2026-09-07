from flask import Blueprint, redirect, url_for, flash, request, render_template, abort
from flask_login import current_user

from webapp.extensions import db
from webapp.forms import ProblemForm
from webapp.models import Problem, Resource
from webapp.routes.utils import admin_required

bp = Blueprint('problems', __name__)


@bp.route('/problems/<int:problem_id>/go')
def problem_go(problem_id):
    """Jump directly to the resource linked from a problem — the public
    entry point. Same click-through pattern as supplier_go."""
    problem = Problem.query.get_or_404(problem_id)
    return redirect(url_for('kb.resource_detail', resource_id=problem.resource_id))


# ---------------------------------------------------------------------
# Admin management
# ---------------------------------------------------------------------

@bp.route('/admin/problems')
@admin_required
def admin_problems():
    problems = Problem.query.order_by(Problem.sort_order, Problem.name).all()
    return render_template('admin_problems.html', problems=problems)


@bp.route('/admin/problems/new', methods=['GET', 'POST'])
@admin_required
def admin_new_problem():
    form = ProblemForm()
    if form.validate_on_submit():
        problem = Problem(
            name=form.name.data,
            resource_id=form.resource_id.data,
            sort_order=int(form.sort_order.data or 0),
        )
        db.session.add(problem)
        db.session.commit()
        flash(f'Added: {problem.name}', 'success')
        return redirect(url_for('problems.admin_problems'))
    return render_template('admin_problem_form.html', form=form, problem=None)


@bp.route('/admin/problems/<int:problem_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_problem(problem_id):
    problem = Problem.query.get_or_404(problem_id)
    form = ProblemForm(obj=problem)
    if request.method == 'GET':
        form.resource_id.data = problem.resource_id
        form.sort_order.data = str(problem.sort_order)

    if form.validate_on_submit():
        problem.name = form.name.data
        problem.resource_id = form.resource_id.data
        problem.sort_order = int(form.sort_order.data or 0)
        db.session.commit()
        flash(f'Saved: {problem.name}', 'success')
        return redirect(url_for('problems.admin_problems'))
    return render_template('admin_problem_form.html', form=form, problem=problem)


@bp.route('/admin/problems/<int:problem_id>/delete', methods=['POST'])
@admin_required
def admin_delete_problem(problem_id):
    problem = Problem.query.get_or_404(problem_id)
    name = problem.name
    db.session.delete(problem)
    db.session.commit()
    flash(f'Deleted: {name}', 'success')
    return redirect(url_for('problems.admin_problems'))
