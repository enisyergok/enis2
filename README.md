# Üretim Planlama Uygulaması

Bu uygulama, üretim süresi verilerine dayalı olarak üretim planlaması yapmanıza yardımcı olan bir web uygulamasıdır.

## Özellikler

- Excel dosyasındaki veriler analiz edilerek ürün ve proses bilgileri çıkarılır
- Ürün seçimi ve adet girişi yapılabilir
- Vardiya süresi ve çalışma günleri ayarlanabilir
- Toplam üretim süresi otomatik olarak hesaplanır
- Günlük, haftalık ve aylık üretim planı oluşturulur
- Proses bazlı üretim süreleri pasta grafiği ile görselleştirilir

## Kurulum

1. Gerekli bağımlılıkları yükleyin:
   ```
   pip install -r requirements.txt
   ```

2. Uygulamayı çalıştırın:
   ```
   python app.py
   ```

3. Tarayıcınızda `http://localhost:5000` adresine gidin

## Dosya Yapısı

- `app.py`: Ana uygulama dosyası
- `data/`: Veri dosyaları
  - `products_data.json`: Ürün ve proses verileri
- `static/`: Statik dosyalar (CSS, JS)
- `templates/`: HTML şablonları

## Kullanım

1. Ana sayfada ürün(leri) ve adet(leri) seçin
2. İsterseniz vardiya süresi ve çalışma günlerini değiştirin
3. "Üretim Planı Oluştur" butonuna tıklayın
4. Sonuç sayfasında üretim planınızı ve grafiklerinizi görüntüleyin

## Üretim Ortamına Dağıtım

Uygulamayı üretim ortamına dağıtmak için:

1. `debug=False` ayarını kontrol edin
2. Bir WSGI sunucusu kullanın (örn. Gunicorn)
3. Procfile'ı kullanarak dağıtım yapın:
   ```
   web: gunicorn app:app
   ```

## Lisans

Bu uygulama açık kaynak kodludur.
