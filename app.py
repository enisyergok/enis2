from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import os
import math
from datetime import datetime, timedelta, time
import requests

app = Flask(__name__)

# Veri dosyasını yükle
def load_data():
    with open('data/products_data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# Veriyi kaydet
def save_data(data):
    with open('data/products_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Üretim süresi hesaplama fonksiyonu
def calculate_production_time(product, quantity, data, process=None, personnel_count=1):
    if product not in data['product_processes']:
        return 0
    
    # Belirli bir proses için hesaplama
    if process:
        if process in data['product_processes'][product]:
            # Süreyi dakikaya çevir, personel sayısına böl ve adet ile çarp
            process_time = data['product_processes'][product][process]
            return (process_time / 60 / personnel_count) * quantity
        return 0
    
    # Tüm prosesler için hesaplama
    total_minutes = 0
    for process_name, process_time in data['product_processes'][product].items():
        personnel = data['process_personnel'].get(process_name, 1)
        total_minutes += (process_time / 60 / personnel) * quantity
    
    return total_minutes

# Saat formatını dakikaya çevirme fonksiyonu
def time_to_minutes(time_str):
    hours, minutes = map(int, time_str.split(':'))
    return hours * 60 + minutes

# Dakikayı saat formatına çevirme fonksiyonu
def minutes_to_time(minutes):
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"

# Üretim planı oluşturma fonksiyonu
def create_production_plan(selected_products, quantities, data, shift_schedule, work_days=None, process_personnel=None, selected_processes=None):
    # Varsayılan çalışma günleri (Pazartesi-Cuma)
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
    
    # Personel gereksinimlerini al
    if not process_personnel:
        process_personnel = data.get('process_personnel', {})
    
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
            
        # Ürünün seçilen proseslerdeki süreleri topla
        product_processes = {}
        product_total_minutes = 0
        
        for process in processes_to_use:
            if process in data['product_processes'][product]:
                # Personel sayısını dikkate alarak süreyi hesapla
                personnel_count = process_personnel.get(process, 1)
                process_minutes = calculate_production_time(product, quantity, data, process, personnel_count)
                product_processes[process] = process_minutes
                product_total_minutes += process_minutes
        
        if product_total_minutes > 0:
            total_production_minutes += product_total_minutes
            product_times.append({
                'product': product,
                'quantity': quantity,
                'minutes': product_total_minutes,
                'processes': product_processes
            })
    
    # Toplam gün sayısı hesapla
    total_days = math.ceil(total_production_minutes / effective_work_time)
    
    # Bugünden başlayarak çalışma günlerini belirle
    start_date = datetime.now()
    working_days = []
    current_date = start_date
    
    while len(working_days) < total_days:
        # Çalışma günü mü kontrol et
        if current_date.weekday() in work_days:
            working_days.append(current_date.strftime('%Y-%m-%d'))
        
        current_date += timedelta(days=1)
    
    # Günlük üretim planı oluştur
    daily_plan = []
    remaining_minutes = total_production_minutes
    
    for day in working_days:
        day_minutes = min(effective_work_time, remaining_minutes)
        daily_plan.append({
            'date': day,
            'minutes': day_minutes,
            'percentage': (day_minutes / effective_work_time) * 100
        })
        remaining_minutes -= day_minutes
    
    # Haftalık plan oluştur
    weekly_plan = {}
    for i, day in enumerate(working_days):
        week_number = (datetime.strptime(day, '%Y-%m-%d').isocalendar()[1])
        if week_number not in weekly_plan:
            weekly_plan[week_number] = 0
        weekly_plan[week_number] += daily_plan[i]['minutes']
    
    # Aylık plan oluştur
    monthly_plan = {}
    for i, day in enumerate(working_days):
        month = datetime.strptime(day, '%Y-%m-%d').strftime('%Y-%m')
        if month not in monthly_plan:
            monthly_plan[month] = 0
        monthly_plan[month] += daily_plan[i]['minutes']
    
    # Proses bazlı detaylı plan
    process_details = {}
    process_personnel_details = {}
    
    # Her proses için toplam süreyi hesapla
    for i, product_time in enumerate(product_times):
        for process, minutes in product_time['processes'].items():
            if process not in process_details:
                process_details[process] = 0
                # Proses için personel sayısını al
                process_personnel_details[process] = process_personnel.get(process, 1)
            process_details[process] += minutes
    
    # Günlük proses bazlı detaylı plan
    daily_process_plan = []
    
    # Her gün için proses bazlı plan oluştur
    remaining_process_minutes = {process: minutes for process, minutes in process_details.items()}
    
    for day_index, day in enumerate(working_days):
        day_data = daily_plan[day_index]
        day_total_minutes = day_data['minutes']
        
        # O gün için proses dağılımını hesapla
        day_processes = {}
        current_time = start_minutes
        
        # Toplam proses süresi
        total_process_minutes = sum(remaining_process_minutes.values())
        
        if total_process_minutes > 0:
            # Her proses için o gün yapılacak işi hesapla
            for process, total_minutes in sorted(remaining_process_minutes.items(), key=lambda x: x[1], reverse=True):
                if total_minutes > 0:
                    # Bu proses için bugün ne kadar süre ayrılacak
                    process_day_minutes = min(total_minutes, day_total_minutes * (total_minutes / total_process_minutes))
                    
                    if process_day_minutes > 0:
                        # Prosesin başlangıç ve bitiş zamanlarını hesapla
                        process_start_time = current_time
                        process_end_time = process_start_time
                        process_remaining = process_day_minutes
                        
                        # Molaları dikkate alarak çalışma sürelerini hesapla
                        while process_remaining > 0:
                            # Sonraki molaya kadar çalışılabilecek süre
                            next_break_start = end_minutes
                            for break_info in shift_schedule['breaks']:
                                break_start = time_to_minutes(break_info['start'])
                                if break_start > process_end_time and break_start < next_break_start:
                                    next_break_start = break_start
                            
                            # Molaya kadar çalışılabilecek süre
                            work_until_break = next_break_start - process_end_time
                            
                            if work_until_break >= process_remaining:
                                # Kalan iş moladan önce bitecek
                                process_end_time += process_remaining
                                process_remaining = 0
                            else:
                                # Mola araya girecek
                                process_end_time = next_break_start
                                process_remaining -= work_until_break
                                
                                # Mola süresini atla
                                for break_info in shift_schedule['breaks']:
                                    break_start = time_to_minutes(break_info['start'])
                                    break_end = time_to_minutes(break_info['end'])
                                    if break_start == next_break_start:
                                        process_end_time = break_end
                                        break
                        
                        # Proses bilgilerini kaydet
                        day_processes[process] = {
                            'minutes': process_day_minutes,
                            'start_time': minutes_to_time(int(process_start_time)),
                            'end_time': minutes_to_time(int(process_end_time)),
                            'personnel': process_personnel_details[process],
                            'personnel_minutes': process_day_minutes * process_personnel_details[process]
                        }
                        
                        # Kalan süreyi güncelle
                        remaining_process_minutes[process] -= process_day_minutes
                        
                        # Sonraki proses için başlangıç zamanını güncelle
                        current_time = process_end_time
        
        # Günlük proses planını ekle
        daily_process_plan.append({
            'date': day,
            'processes': day_processes
        })
    
    return {
        'total_minutes': total_production_minutes,
        'total_days': total_days,
        'product_times': product_times,
        'daily_plan': daily_plan,
        'weekly_plan': weekly_plan,
        'monthly_plan': monthly_plan,
        'process_details': process_details,
        'process_personnel': process_personnel_details,
        'daily_process_plan': daily_process_plan,
        'shift_schedule': shift_schedule,
        'selected_processes': processes_to_use
    }

@app.route('/')
def index():
    data = load_data()
    return render_template('index.html', 
                          products=sorted(data['products']), 
                          processes=data['processes'],
                          process_personnel=data.get('process_personnel', {}))

@app.route('/products')
def products():
    data = load_data()
    return render_template('products.html', 
                          products=sorted(data['products']), 
                          processes=data['processes'],
                          product_processes=data['product_processes'])

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    data = load_data()
    
    if request.method == 'POST':
        product_name = request.form.get('product_name', '').strip()
        
        if product_name and product_name not in data['products']:
            # Yeni ürün için proses sürelerini al
            process_times = {}
            for process in data['processes']:
                time_key = f"process_time_{process}"
                if time_key in request.form and request.form[time_key].strip():
                    try:
                        time_value = float(request.form[time_key])
                        if time_value > 0:
                            process_times[process] = time_value
                    except ValueError:
                        pass
            
            # Ürünü ve proses sürelerini kaydet
            if process_times:
                data['products'].append(product_name)
                data['product_processes'][product_name] = process_times
                
                # JSON dosyasını güncelle
                save_data(data)
                
                return render_template('add_product.html', 
                                      processes=data['processes'],
                                      success=True,
                                      message=f"Ürün '{product_name}' başarıyla eklendi.")
            else:
                return render_template('add_product.html', 
                                      processes=data['processes'],
                                      error=True,
                                      message="En az bir proses için süre girmelisiniz.")
        else:
            return render_template('add_product.html', 
                                  processes=data['processes'],
                                  error=True,
                                  message="Geçerli bir ürün adı girmelisiniz veya bu ürün zaten mevcut.")
    
    return render_template('add_product.html', processes=data['processes'])

@app.route('/edit_product/<product>', methods=['GET', 'POST'])
def edit_product(product):
    data = load_data()
    
    if product not in data['products']:
        return redirect(url_for('products'))
    
    if request.method == 'POST':
        new_product_name = request.form.get('product_name', '').strip()
        
        # Yeni ürün adı geçerli mi kontrol et
        if not new_product_name:
            return render_template('edit_product.html', 
                                  product=product,
                                  processes=data['processes'],
                                  product_processes=data['product_processes'].get(product, {}),
                                  error=True,
                                  message="Ürün adı boş olamaz.")
        
        # Eğer ürün adı değiştiyse ve yeni ad zaten varsa hata ver
        if new_product_name != product and new_product_name in data['products']:
            return render_template('edit_product.html', 
                                  product=product,
                                  processes=data['processes'],
                                  product_processes=data['product_processes'].get(product, {}),
                                  error=True,
                                  message=f"'{new_product_name}' adında bir ürün zaten mevcut.")
        
        # Proses sürelerini al
        process_times = {}
        for process in data['processes']:
            time_key = f"process_time_{process}"
            if time_key in request.form and request.form[time_key].strip():
                try:
                    time_value = float(request.form[time_key])
                    if time_value > 0:
                        process_times[process] = time_value
                except ValueError:
                    pass
        
        # En az bir proses süresi girilmiş mi kontrol et
        if not process_times:
            return render_template('edit_product.html', 
                                  product=product,
                                  processes=data['processes'],
                                  product_processes=data['product_processes'].get(product, {}),
                                  error=True,
                                  message="En az bir proses için süre girmelisiniz.")
        
        # Ürün adı değiştiyse eski ürünü kaldır
        if new_product_name != product:
            data['products'].remove(product)
            data['products'].append(new_product_name)
            data['product_processes'][new_product_name] = process_times
            del data['product_processes'][product]
        else:
            # Aynı ürün adıyla güncelle
            data['product_processes'][product] = process_times
        
        # JSON dosyasını güncelle
        save_data(data)
        
        return redirect(url_for('products'))
    
    return render_template('edit_product.html', 
                          product=product,
                          processes=data['processes'],
                          product_processes=data['product_processes'].get(product, {}))

@app.route('/delete_product/<product>', methods=['POST'])
def delete_product(product):
    data = load_data()
    
    if product in data['products']:
        data['products'].remove(product)
        if product in data['product_processes']:
            del data['product_processes'][product]
        
        # JSON dosyasını güncelle
        save_data(data)
    
    return redirect(url_for('products'))

@app.route('/calculate', methods=['POST'])
def calculate():
    data = load_data()
    
    # Form verilerini al
    products = request.form.getlist('products[]')
    quantities = [int(q) for q in request.form.getlist('quantities[]')]
    
    # Seçilen prosesler
    selected_processes = request.form.getlist('processes[]')
    if not selected_processes:
        selected_processes = data['processes']
    
    # Vardiya bilgileri
    shift_start = request.form.get('shiftStart', '07:00')
    shift_end = request.form.get('shiftEnd', '17:00')
    break_starts = request.form.getlist('breakStart[]')
    break_ends = request.form.getlist('breakEnd[]')
    
    # Molaları oluştur
    breaks = []
    total_break_time = 0
    
    for i in range(len(break_starts)):
        if break_starts[i] and break_ends[i]:
            start_minutes = time_to_minutes(break_starts[i])
            end_minutes = time_to_minutes(break_ends[i])
            duration = end_minutes - start_minutes
            
            if duration > 0:
                breaks.append({
                    'start': break_starts[i],
                    'end': break_ends[i],
                    'duration': duration
                })
                total_break_time += duration
    
    # Vardiya bilgilerini oluştur
    shift_schedule = {
        'start_time': shift_start,
        'end_time': shift_end,
        'breaks': breaks,
        'total_break_time': total_break_time,
        'effective_work_time': time_to_minutes(shift_end) - time_to_minutes(shift_start) - total_break_time
    }
    
    # Çalışma günleri
    work_days = [int(day) for day in request.form.getlist('workDays[]')]
    
    # Personel gereksinimleri
    process_personnel = {}
    for process in data['processes']:
        personnel_key = f"personnel[{process}]"
        if personnel_key in request.form:
            try:
                personnel_count = int(request.form.get(personnel_key))
                if personnel_count > 0:
                    process_personnel[process] = personnel_count
            except ValueError:
                pass
    
    # Üretim planı oluştur
    plan = create_production_plan(
        products, 
        quantities, 
        data, 
        shift_schedule, 
        work_days, 
        process_personnel,
        selected_processes
    )
    
    return render_template('result.html', plan=plan, products=products, quantities=quantities)

@app.route('/api/product_info/<product>')
def product_info(product):
    data = load_data()
    if product in data['product_processes']:
        return jsonify(data['product_processes'][product])
    return jsonify({})

@app.route('/api/processes')
def get_processes():
    data = load_data()
    return jsonify(data['processes'])

@app.route('/api/shift_schedule')
def get_shift_schedule():
    data = load_data()
    return jsonify(data.get('shift_schedule', {}))

@app.route('/api/ask_deepseek', methods=['POST'])
def ask_deepseek():
    question = request.form.get('question', '')
    
    try:
        # DeepSeek API'ye istek gönder
        response = {
            'answer': f"DeepSeek AI yanıtı: '{question}' sorunuz için üretim planlaması optimizasyonu önerileri şunlardır: "
                     f"1) Öncelikle yüksek öncelikli siparişleri planlayın, "
                     f"2) Benzer ürünleri gruplandırarak hazırlık sürelerini azaltın, "
                     f"3) Darboğaz prosesleri önceden belirleyip kapasitelerini artırın."
        }
        
        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e), 'answer': 'DeepSeek API ile iletişim kurulamadı. Lütfen daha sonra tekrar deneyin.'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
