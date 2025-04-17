from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, Process, User
import json

processes_bp = Blueprint('processes', __name__)

@processes_bp.route('/processes')
@login_required
def index():
    processes = Process.query.all()
    return render_template('processes/index.html', processes=processes)

@processes_bp.route('/processes/new', methods=['GET', 'POST'])
@login_required
def new_process():
    if request.method == 'POST':
        process_name = request.form['process_name']
        
        # Proses ismi zaten var mı?
        if Process.query.filter_by(name=process_name).first():
            flash('Bu isimde bir proses zaten mevcut.')
            return redirect(url_for('processes.new_process'))
        
        process = Process(name=process_name, user_id=current_user.id)
        db.session.add(process)
        
        # Mevcut ürün veri dosyasını güncelle
        try:
            with open('data/products_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Yeni prosesi processes listesine ekle
            if process_name not in data["processes"]:
                data["processes"].append(process_name)
                
            # process_personnel içine ekle (varsayılan 1 değeriyle)
            if process_name not in data["process_personnel"]:
                data["process_personnel"][process_name] = 1
                
            # Yeni JSON dosyasını kaydet
            with open('data/products_data.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                
            db.session.commit()
            flash('Yeni proses başarıyla eklendi!')
            return redirect(url_for('processes.index'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Proses eklenirken hata oluştu: {str(e)}')
            return redirect(url_for('processes.new_process'))
    
    return render_template('processes/new.html')
