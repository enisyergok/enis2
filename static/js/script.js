// Ürün ekleme, düzenleme ve kaldırma işlemleri
document.addEventListener('DOMContentLoaded', function() {
    // Ürün ekleme butonu
    if (document.getElementById('addProduct')) {
        document.getElementById('addProduct').addEventListener('click', function() {
            const productSelections = document.getElementById('productSelections');
            const productRow = document.querySelector('.product-row').cloneNode(true);
            
            // Yeni satırın değerlerini temizle
            productRow.querySelector('select').selectedIndex = 0;
            productRow.querySelector('input[type="number"]').value = '';
            
            // Silme butonunu aktifleştir
            productRow.querySelector('.remove-product').addEventListener('click', function() {
                this.closest('.product-row').remove();
            });
            
            productSelections.appendChild(productRow);
        });
        
        // İlk satırın silme butonu
        document.querySelector('.remove-product').addEventListener('click', function() {
            if (document.querySelectorAll('.product-row').length > 1) {
                this.closest('.product-row').remove();
            }
        });
    }
    
    // DeepSeek AI soru sorma
    if (document.getElementById('askDeepseek')) {
        document.getElementById('askDeepseek').addEventListener('click', function() {
            const question = document.getElementById('deepseekQuestion').value.trim();
            if (question) {
                // Yükleniyor göstergesi
                document.getElementById('deepseekResponse').innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Yükleniyor...</span></div>';
                
                // AJAX isteği
                fetch('/api/ask_deepseek', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: 'question=' + encodeURIComponent(question)
                })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('deepseekResponse').innerHTML = 'Hata: ' + data.error;
                    } else {
                        document.getElementById('deepseekResponse').innerHTML = data.answer;
                    }
                })
                .catch(error => {
                    document.getElementById('deepseekResponse').innerHTML = 'Bağlantı hatası: ' + error.message;
                });
            }
        });
    }
    
    // Ürün veri doğrulama
    if (document.getElementById('productForm')) {
        document.getElementById('productForm').addEventListener('submit', function(event) {
            const products = document.querySelectorAll('select[name="products[]"]');
            let hasError = false;
            let errorMessage = '';
            
            // Aynı ürünün birden fazla seçilip seçilmediğini kontrol et
            const selectedProducts = [];
            products.forEach(function(select) {
                if (select.value && selectedProducts.includes(select.value)) {
                    hasError = true;
                    errorMessage = 'Aynı ürün birden fazla kez seçilemez. Lütfen farklı ürünler seçin.';
                }
                if (select.value) {
                    selectedProducts.push(select.value);
                }
            });
            
            // En az bir proses seçilip seçilmediğini kontrol et
            const selectedProcesses = document.querySelectorAll('input[name="processes[]"]:checked');
            if (selectedProcesses.length === 0) {
                hasError = true;
                errorMessage = 'Lütfen en az bir proses seçin.';
            }
            
            // Hata varsa formu gönderme
            if (hasError) {
                event.preventDefault();
                alert(errorMessage);
            }
        });
    }
    
    // Yeni ürün ekleme formu doğrulama
    if (document.getElementById('addProductForm')) {
        document.getElementById('addProductForm').addEventListener('submit', function(event) {
            const productName = document.getElementById('product_name').value.trim();
            const processTimes = document.querySelectorAll('input[name^="process_time_"]');
            let hasProcessTime = false;
            
            // Ürün adı kontrolü
            if (!productName) {
                event.preventDefault();
                alert('Lütfen bir ürün adı girin.');
                return;
            }
            
            // En az bir proses süresi girilmiş mi kontrolü
            processTimes.forEach(function(input) {
                if (input.value.trim() !== '') {
                    hasProcessTime = true;
                }
            });
            
            if (!hasProcessTime) {
                event.preventDefault();
                alert('Lütfen en az bir proses için süre girin.');
            }
        });
    }
});
