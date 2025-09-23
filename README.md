<p align="center">
  <img src="static/img/favicon.svg" alt="GlichFlow Logo" width="96" height="96" />
</p>

# GlichFlow

Takımınız için basit ve hızlı proje/görev yönetimi.

- Canlı: [glichflow.glitchidea.com](http://glichflow.glitchidea.com/)
- Dokümantasyon: [glichflow.glitchidea.com/docs.html](http://glichflow.glitchidea.com/docs.html)
- Kaynak kodu: [github.com/glitchidea/GlichFlow](https://github.com/glitchidea/GlichFlow)

## Neler Sunar?

- Projeler ve Görevler (atama, durum, dosya)
- Ekipler ve Yetkiler
- Mesajlaşma ve Bildirimler
- Takvim görünümü
- Raporlar, GitHub entegrasyonu, AI asistan

## Hızlı Başlangıç

```bash
git clone https://github.com/glitchidea/GlichFlow.git
cd glichflow
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
# http://127.0.0.1:8000
```

Prod ve ileri seviye kurulumlar için dokümantasyonu ziyaret edin.


## Lisans

AGPL-3.0 — ayrıntılar için `LICENSE`.
