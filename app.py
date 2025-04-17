from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, current_user, login_required
from datetime import datetime, timedelta
import json
import math
import os

from config import Config
from models import db, User, ProductionPlan, Process
from auth import auth_bp
from processes import processes_bp
from plans import plans_bp

app = Flask(__name__)
app.config.from_object(Config)

# Veritabanı kurulumu
db.init_app(app)

# Flask-Login kurulumu
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Bu sayfayı görüntülemek için giriş yapmalısınız.'

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

# Blueprint'leri kaydet
app.register_blueprint(auth_bp)
app.register_blueprint(processes_bp)
app.register_blueprint(plans_bp)

# Veri dosyasını yükle
def load_data():
    with open('data/products_data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# Veriyi kaydet
def save_data(data):
    with open('data/products_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Üretim süresi hesaplama fonksiyonu
def calculate_production_time(product, quantity, data, process_name, personnel_count=1):
    if product not in data['product_processes']:
        return 0
    
    if process_name in data['product_processes'][product]:
        # Süreyi dakikada çevir, personel sayısına böl ve ürün ile çarp
        process_time = data['product_processes'][product][process_name]
        return (process_time / 60 / personnel_count) * quantity
    
    return 0

# Tüm prosesler için hesaplama
def total_minutes_calculation(products, quantities, data, process_personnel_counts, selected_processes=None):
    total_minutes = 0
    for process_name, process_time in data['product_processes'][products[0]].items():
        if selected_processes and process_name not in selected_processes:
            continue
        
        personnel = data['process_personnel'].get(process_name, 1)
        if process_personnel_counts and process_name in process_personnel_counts:
            personnel = process_personnel_counts.get(process_name, 1)
        
        process_minutes = calculate_production_time(products[0], quantities[0], data, process_name, personnel)
        total_minutes += process_minutes
    
    return total_minutes

# Saat formatını dakikaya çevirme fonksiyonu
def time_to_minutes(time_str):
    hours, minutes = map(int, time_str.split(':'))
    return hours * 60 + minutes

# Dakikayı saat:dakika formatına çevirme
def minutes_to_time(minutes):
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"

# Üretim planı oluşturma fonksiyonu
def create_production_plan(selected_products, quantities, data, shift_schedule, work_days=None, process_personnel=None, selected_processes=None):
    if work_days is None:
        work_days = [0, 1, 2, 3, 4]  # 0=Pazartesi, 6=Pazar
    
    # Vardiya bilgilerini al
    if not shift_schedule:
        shift_schedule = data.get('shift_schedule', {
            'start_time': '07:00',
            'end_time': '17:00',
            'breaks': [
                {'start': '09:00', 'end': '09:15', 'duration': 15},
                {'start': '12:00', 'end': '12:30', 'duration': 30},
                {'start': '15:00', 'end': '15:15', 'duration': 15}
            ],
            'total_break_time': 60,
            'effective_work_time': 540
        })
    
    # Vardiya süresi (dakika)
    start_minutes = time_to_minutes(shift_schedule['start_time'])
    end_minutes = time_to_minutes(shift_schedule['end_time'])
    shift_duration_minutes = end_minutes - start_minutes
    effective_work_time = shift_duration_minutes - shift_schedule['total_break_time']
    
    # Eğer belirli prosesler seçildiyse, sadece onları kullan
    processes_to_use = selected_processes if selected_processes else data['processes']
    
    # Toplam üretim süresi hesapla
    total_production_minutes = 0
    product_times = []
    
    for i, product in enumerate(selected_products):
        quantity = quantities[i]
        
        # Ürün verisi var mı kontrol et
        if product not in data['product_processes']:
            continue
        
        # Her proses için süreleri topla
        for process in processes_to_use:
            if process in data['product_processes'][product]:
                personnel_count = process_personnel.get(process, 1) if process_personnel else data['process_personnel'].get(process, 1)
                process_minutes = calculate_production_time(product, quantity, data, process, personnel_count)
                product_times.append({
                    'product': product,
                    'process': process,
                    'minutes': process_minutes,
                    'quantity': quantity,
                    'personnel': personnel_count
                })
                total_production_minutes += process_minutes
    
    # Günlük, haftalık ve aylık plan oluştur
    daily_work_minutes = effective_work_time
    
    days_needed = math.ceil(total_production_minutes / daily_work_minutes)
    weeks_needed = math.ceil(days_needed / len(work_days)) if work_days else 0
    
    current_date = datetime.now()
    current_weekday = current_date.weekday()
    
    # İlk çalışma gününe ilerle
    days_to_add = 0
    while current_weekday not in work_days and work_days:
        days_to_add += 1
        current_weekday = (current_weekday + 1) % 7
    
    start_date = current_date + timedelta(days=days_to_add)
    
    # Günlük plan
    daily_plan = []
    current_day = start_date
    remaining_minutes = total_production_minutes
    
    day_counter = 0
    while remaining_minutes > 0:
        # Bugün çalışma günü mü?
        if current_day.weekday() in work_days:
            minutes_today = min(daily_work_minutes, remaining_minutes)
            
            # İş başlangıç ve bitiş zamanları
            day_start = datetime.combine(current_day.date(), datetime.strptime(shift_schedule['start_time'], '%H:%M').time())
            
            # Molalar dahil toplam süreyi hesapla
            estimated_end_minutes = start_minutes + (minutes_today * shift_duration_minutes / effective_work_time)
            day_end_time = minutes_to_time(min(int(estimated_end_minutes), end_minutes))
            
            day_end = datetime.combine(current_day.date(), datetime.strptime(day_end_time, '%H:%M').time())
            
            # Bugün tamamlanan işleri hesapla
            day_processes = []
            day_process_minutes = 0
            
            for pt in product_times:
                if pt['minutes'] > 0:
                    mins_for_today = min(pt['minutes'], minutes_today - day_process_minutes)
                    if mins_for_today <= 0:
                        continue
                    
                    completion_percentage = mins_for_today / pt['minutes'] * 100 if pt['minutes'] > 0 else 0
                    
                    day_processes.append({
                        'product': pt['product'],
                        'process': pt['process'],
                        'minutes': mins_for_today,
                        'completion': min(100, completion_percentage)
                    })
                    
                    # Kalan süreyi güncelle
                    pt['minutes'] -= mins_for_today
                    day_process_minutes += mins_for_today
                    
                    if day_process_minutes >= minutes_today:
                        break
            
            daily_plan.append({
                'date': current_day.strftime('%Y-%m-%d'),
                'day_name': ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar'][current_day.weekday()],
                'start_time': shift_schedule['start_time'],
                'end_time': day_end_time,
                'minutes': minutes_today,
                'processes': day_processes
            })
            
            remaining_minutes -= minutes_today
            day_counter += 1
        
        current_day += timedelta(days=1)
        
        # Sonsuz döngüyü önlemek için
        if day_counter > 365:  # 1 yıldan fazla sürmeyecek bir üretim planı varsayalım
            break
    
    # Haftalık ve aylık planları oluştur
    weekly_plan = {}
    monthly_plan = {}
    
    for day in daily_plan:
        date_obj = datetime.strptime(day['date'], '%Y-%m-%d')
        
        # Haftalık plan
        week_number = date_obj.strftime('%Y-W%U')
        if week_number not in weekly_plan:
            weekly_plan[week_number] = {
                'start_date': date_obj.strftime('%Y-%m-%d'),
                'end_date': date_obj.strftime('%Y-%m-%d'),
                'minutes': 0,
                'processes': {}
            }
        
        weekly_plan[week_number]['minutes'] += day['minutes']
        weekly_plan[week_number]['end_date'] = date_obj.strftime('%Y-%m-%d')
        
        # Prosesleri güncelle
        for process in day['processes']:
            if process['process'] not in weekly_plan[week_number]['processes']:
                weekly_plan[week_number]['processes'][process['process']] = 0
            weekly_plan[week_number]['processes'][process['process']] += process['minutes']
        
        # Aylık plan
        month_key = date_obj.strftime('%Y-%m')
        if month_key not in monthly_plan:
            monthly_plan[month_key] = {
                'month_name': date_obj.strftime('%B %Y'),
                'minutes': 0,
                'processes': {}
            }
        
        monthly_plan[month_key]['minutes'] += day['minutes']
        
        # Prosesleri güncelle
        for process in day['processes']:
            if process['process'] not in monthly_plan[month_key]['processes']:
                monthly_plan[month_key]['processes'][process['process']] = 0
            monthly_plan[month_key]['processes'][process['process']] += process['minutes']
    
    # Dönüşüm için list'e çevir
    weekly_plan_list = [{'week': k, **v} for k, v in weekly_plan.items()]
    monthly_plan_list = [{'month': k, **v} for k, v in monthly_plan.items()]
    
    # Tüm proses sürelerini topla
    process_times = {}
    for pt in product_times:
        if pt['process'] not in process_times:
            process_times[pt['process']] = 0
        process_times[pt['process']] += pt['minutes']
    
    # Sonuçları döndür
    return {
        'total_production_minutes': total_production_minutes,
        'days_needed': days_needed,
        'weeks_needed': weeks_needed,
        'daily_plan': daily_plan,
        'weekly_plan': weekly_plan_list,
        'monthly_plan': monthly_plan_list,
        'process_times': process_times,
        'product_times': product_times,
        'effective_work_time': effective_work_time
    }

@app.route('/')
def index():
    try:
        data = load_data()
        products = data['products']
        return render_template('index.html', products=products)
    except Exception as e:
        flash(f'Veri yüklenirken hata oluştu: {str(e)}')
        return render_template('error.html', error=str(e))

@app.route('/products')
def products():
    data = load_data()
    return jsonify(data['products'])

@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        product_name = request.form['product_name']
        processes = request.form.getlist('processes[]')
        times = request.form.getlist('times[]')
        
        data = load_data()
        
        # Ürün zaten var mı kontrol et
        if product_name in data['product_processes']:
            flash('Bu isimde bir ürün zaten mevcut.')
            return render_template('add_product.html', processes=data['processes'])
        
        # Yeni ürünü ekle
        data['products'].append(product_name)
        data['product_processes'][product_name] = {}
        
        # Proses sürelerini ekle
        for i, process in enumerate(processes):
            if i < len(times) and times[i]:
                data['product_processes'][product_name][process] = float(times[i])
        
        # Veriyi kaydet
        save_data(data)
        flash('Yeni ürün başarıyla eklendi!')
        return redirect(url_for('index'))
    
    data = load_data()
    return render_template('add_product.html', processes=data['processes'])

@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        data = load_data()
        request_data = request.json
        
        selected_products = request_data.get('selected_products', [])
        quantities = request_data.get('quantities', [])
        shift_schedule = request_data.get('shift_schedule')
        work_days = request_data.get('work_days')
        process_personnel = request_data.get('process_personnel')
        selected_processes = request_data.get('selected_processes')
        
        if not selected_products or not quantities:
            return jsonify({'error': 'Ürün ve adet bilgisi gereklidir.'}), 400
        
        result = create_production_plan(
            selected_products, 
            quantities, 
            data, 
            shift_schedule, 
            work_days, 
            process_personnel,
            selected_processes
        )
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/edit_product/<product>', methods=['GET', 'POST'])
@login_required
def edit_product(product):
    data = load_data()
    
    if product not in data['product_processes']:
        flash('Ürün bulunamadı.')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        processes = request.form.getlist('processes[]')
        times = request.form.getlist('times[]')
        
        # Ürün proseslerini güncelle
        data['product_processes'][product] = {}
        
        for i, process in enumerate(processes):
            if i < len(times) and times[i]:
                data['product_processes'][product][process] = float(times[i])
        
        # Veriyi kaydet
        save_data(data)
        flash('Ürün başarıyla güncellendi!')
        return redirect(url_for('index'))
    
    product_processes = data['product_processes'][product]
    return render_template('edit_product.html', 
                          product=product, 
                          processes=data['processes'], 
                          product_processes=product_processes)

@app.route('/result', methods=['POST'])
def result():
    try:
        data = load_data()
        
        selected_products = request.form.getlist('products[]')
        quantities = [int(q) for q in request.form.getlist('quantities[]')]
        
        # Vardiya bilgileri
        shift_start = request.form.get('shiftStart', '07:00')
        shift_end = request.form.get('shiftEnd', '17:00')
        
        # Mola bilgileri
        break_starts = request.form.getlist('breakStart[]')
        break_ends = request.form.getlist('breakEnd[]')
        break_durations = [int(d) for d in request.form.getlist('breakDuration[]')]
        
        breaks = []
        total_break_time = 0
        
        for i in range(len(break_starts)):
            if i < len(break_ends) and i < len(break_durations):
                breaks.append({
                    'start': break_starts[i],
                    'end': break_ends[i],
                    'duration': break_durations[i]
                })
                total_break_time += break_durations[i]
        
        # Çalışma günleri
        work_days = [int(day) for day in request.form.getlist('workDays
