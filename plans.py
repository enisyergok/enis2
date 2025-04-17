from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, ProductionPlan
import json
from datetime import datetime

plans_bp = Blueprint('plans', __name__)

@plans_bp.route('/plans')
@login_required
def index():
    plans = ProductionPlan.query.filter_by(user_id=current_user.id).order_by(ProductionPlan.created_at.desc()).all()
    return render_template('plans/index.html', plans=plans)

@plans_bp.route('/plans/<int:id>')
@login_required
def view(id):
    plan = ProductionPlan.query.get_or_404(id)
    
    # Sadece plan sahibi veya admin görebilir
    if plan.user_id != current_user.id and current_user.role != 'admin':
        flash('Bu planı görüntüleme yetkiniz yok.')
        return redirect(url_for('plans.index'))
    
    plan_data = json.loads(plan.plan_data)
    return render_template('plans/view.html', plan=plan, plan_data=plan_data)

@plans_bp.route('/plans/save', methods=['POST'])
@login_required
def save():
    data = request.json
    
    plan_name = data.get('plan_name', f'Plan {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    plan_data = json.dumps(data)
    total_minutes = data.get('total_production_minutes', 0)
    
    plan = ProductionPlan(
        name=plan_name,
        plan_data=plan_data,
        user_id=current_user.id,
        total_production_minutes=total_minutes
    )
    
    db.session.add(plan)
    db.session.commit()
    
    return jsonify({'success': True, 'plan_id': plan.id})

@plans_bp.route('/plans/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    plan = ProductionPlan.query.get_or_404(id)
    
    # Sadece plan sahibi veya admin silebilir
    if plan.user_id != current_user.id and current_user.role != 'admin':
        flash('Bu planı silme yetkiniz yok.')
        return redirect(url_for('plans.index'))
    
    db.session.delete(plan)
    db.session.commit()
    
    flash('Plan başarıyla silindi.')
    return redirect(url_for('plans.index'))

@plans_bp.route('/plans/export/<int:id>')
@login_required
def export(id):
    plan = ProductionPlan.query.get_or_404(id)
    
    if plan.user_id != current_user.id and current_user.role != 'admin':
        flash('Bu planı dışa aktarma yetkiniz yok.')
        return redirect(url_for('plans.index'))
    
    # Plana ait JSON verisini düz dosya olarak indirme
    return jsonify(json.loads(plan.plan_data))
