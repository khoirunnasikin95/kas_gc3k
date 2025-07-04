from django.db import models
from django.utils import timezone

STATUS_RUMAH = [
    ('sudah', 'Sudah Ditempati'),
    ('segera', 'Segera Ditempati'),
    ('belum', 'Belum Ditempati'),
]

class Rumah(models.Model):
    blok = models.CharField(max_length=10)
    nama = models.CharField(max_length=100)
    status = models.CharField(max_length=10, choices=STATUS_RUMAH)

    def __str__(self):
        return f"{self.blok} - {self.nama}"


class Pembayaran(models.Model):
    rumah = models.ForeignKey(Rumah, on_delete=models.CASCADE)
    tahun = models.IntegerField()
    bulan = models.CharField(max_length=20)
    iuran_sampah = models.IntegerField(default=0)
    iuran_dansos = models.IntegerField(default=0)

    class Meta:
        unique_together = ['rumah', 'tahun', 'bulan']

    def __str__(self):
        return f"{self.rumah} - {self.bulan} {self.tahun}"
    
class Transaksi(models.Model):
    JENIS_TRANSAKSI = [
        ('masuk', 'Pemasukan'),
        ('keluar', 'Pengeluaran'),
    ]
    jenis = models.CharField(max_length=10, choices=JENIS_TRANSAKSI)
    nominal = models.PositiveIntegerField()
    keterangan = models.CharField(max_length=255)
    tanggal = models.DateField(default=timezone.now, blank=True, null=True)

    def __str__(self):
        return f"{self.get_jenis_display()} - Rp{self.nominal} - {self.keterangan}"

