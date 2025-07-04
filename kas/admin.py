from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse
import pandas as pd
from django.utils import timezone

from .models import Rumah, Pembayaran, Transaksi


# ========= RUMAH ADMIN ==========
@admin.register(Rumah)
class RumahAdmin(admin.ModelAdmin):
    list_display = ['blok', 'nama', 'status']
    search_fields = ['blok', 'nama']
    list_filter = ['status']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-excel/', self.upload_excel_view, name='upload_excel_rumah'),
            path('export-excel/', self.export_excel_view, name='export_excel_rumah'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        if extra_context is None:
            extra_context = {}
        extra_context['upload_excel_url'] = 'admin:upload_excel_rumah'
        extra_context['export_excel_url'] = 'admin:export_excel_rumah'
        return super().changelist_view(request, extra_context=extra_context)

    def upload_excel_view(self, request):
        if request.method == "POST":
            excel_file = request.FILES["excel_file"]
            df = pd.read_excel(excel_file)

            # Ubah semua kolom jadi lowercase tanpa spasi
            df.columns = [col.strip().lower() for col in df.columns]

            # Mapping nama kolom
            kolom_blok = next((col for col in df.columns if 'blok' in col), None)
            kolom_nama = next((col for col in df.columns if 'nama' in col), None)
            kolom_status = next((col for col in df.columns if 'status' in col), None)

            if not (kolom_blok and kolom_nama and kolom_status):
                self.message_user(request, "Kolom tidak lengkap atau salah format. Harus ada Blok, Nama, dan Status.", level=messages.ERROR)
                return redirect("..")

            jumlah_berhasil = 0
            for _, row in df.iterrows():
                blok = str(row[kolom_blok]).strip()
                nama = str(row[kolom_nama]).strip()
                status = str(row[kolom_status]).strip().lower()

                if blok and nama and status in ['sudah', 'segera']:
                    Rumah.objects.create(
                        blok=blok,
                        nama=nama,
                        status=status
                    )
                    jumlah_berhasil += 1

            self.message_user(request, f"{jumlah_berhasil} data Rumah berhasil diunggah", level=messages.SUCCESS)
            return redirect("..")

        return render(request, "admin/upload_excel.html", {
            "title": "Upload Data Rumah dari Excel"
        })


    def export_excel_view(self, request):
        queryset = Rumah.objects.all()
        data = []
        for obj in queryset:
            data.append({
                'Blok': obj.blok,
                'Nama': obj.nama,
                'Status': obj.status,
            })
        df = pd.DataFrame(data)
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=rumah_export.xlsx'
        df.to_excel(response, index=False)
        return response


# ========= PEMBAYARAN ADMIN ==========
@admin.register(Pembayaran)
class PembayaranAdmin(admin.ModelAdmin):
    list_display = ['rumah', 'bulan', 'tahun', 'iuran_sampah', 'iuran_dansos']
    list_filter = ['bulan', 'tahun']
    search_fields = ['rumah__blok', 'rumah__nama']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-excel/', self.upload_excel_view, name='upload_excel_pembayaran'),
            path('export-excel/', self.export_excel_view, name='export_excel_pembayaran'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        if extra_context is None:
            extra_context = {}
        extra_context['upload_excel_url'] = 'admin:upload_excel_pembayaran'
        extra_context['export_excel_url'] = 'admin:export_excel_pembayaran'
        return super().changelist_view(request, extra_context=extra_context)

    def upload_excel_view(self, request):
        if request.method == "POST":
            excel_file = request.FILES["excel_file"]
            df = pd.read_excel(excel_file)

            # Bersihkan nama kolom Excel (header)
            df.columns = df.columns.str.strip().str.title()

            total_diproses = 0
            total_dilewati = 0

            for index, row in df.iterrows():
                blok_value = str(row.get("Blok", "")).strip()
                bulan = str(row.get("Bulan", "")).strip().capitalize()
                tahun = row.get("Tahun", 0)

                # Lewatkan jika blok/bulan/tahun kosong
                if not (blok_value and bulan and tahun):
                    total_dilewati += 1
                    continue

                try:
                    tahun = int(tahun)
                except (ValueError, TypeError):
                    total_dilewati += 1
                    continue

                # Baca kolom Sampah dan Dansos dengan aman
                sampah_raw = row.get("Sampah", 0)
                dansos_raw = row.get("Dansos", 0)

                iuran_sampah = int(sampah_raw) if not pd.isna(sampah_raw) else 0
                iuran_dansos = int(dansos_raw) if not pd.isna(dansos_raw) else 0

                # Cari rumah berdasarkan blok
                rumah_qs = Rumah.objects.filter(blok=blok_value)
                if rumah_qs.exists():
                    rumah = rumah_qs.first()

                    # Cegah duplikat data untuk bulan & tahun sama
                    if Pembayaran.objects.filter(rumah=rumah, bulan=bulan, tahun=tahun).exists():
                        total_dilewati += 1
                        continue

                    try:
                        Pembayaran.objects.create(
                            rumah=rumah,
                            bulan=bulan,
                            tahun=tahun,
                            iuran_sampah=iuran_sampah,
                            iuran_dansos=iuran_dansos
                        )
                        total_diproses += 1
                    except Exception as e:
                        print(f"Gagal menyimpan baris {index + 2}: {e}")
                        total_dilewati += 1
                else:
                    print(f"Blok '{blok_value}' tidak ditemukan.")
                    total_dilewati += 1

            self.message_user(
                request,
                f"✅ {total_diproses} data berhasil diunggah. ❌ {total_dilewati} baris dilewati.",
                level=messages.SUCCESS
            )
            return redirect("..")

        return render(request, "admin/upload_excel.html", {
            "title": "Upload Data Pembayaran dari Excel"
        })

    def export_excel_view(self, request):
        queryset = Pembayaran.objects.all()
        data = []
        for obj in queryset:
            data.append({
                'Blok': obj.rumah.blok,
                'Nama': obj.rumah.nama,
                'Bulan': obj.bulan,
                'Tahun': obj.tahun,
                'Sampah': obj.iuran_sampah,
                'Dansos': obj.iuran_dansos,
            })
        df = pd.DataFrame(data)
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=pembayaran_export.xlsx'
        df.to_excel(response, index=False)
        return response


# ========= TRANSAKSI ADMIN ==========
@admin.register(Transaksi)
class TransaksiAdmin(admin.ModelAdmin):
    list_display = ['jenis', 'nominal', 'keterangan', 'tanggal']
    list_filter = ['jenis', 'tanggal']
    search_fields = ['keterangan']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-excel/', self.upload_excel_view, name='upload_excel_transaksi'),
            path('export-excel/', self.export_excel_view, name='export_excel_transaksi'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        if extra_context is None:
            extra_context = {}
        extra_context['upload_excel_url'] = 'admin:upload_excel_transaksi'
        extra_context['export_excel_url'] = 'admin:export_excel_transaksi'
        return super().changelist_view(request, extra_context=extra_context)

    def upload_excel_view(self, request):
        if request.method == "POST":
            excel_file = request.FILES["excel_file"]
            df = pd.read_excel(excel_file)

            # Bikin kolom lowercase semua agar tidak masalah case
            df.columns = [str(col).strip().lower() for col in df.columns]

            for _, row in df.iterrows():
                jenis = row.get("jenis", "").strip().lower()
                nominal = int(row.get("nominal", 0))
                keterangan = row.get("keterangan", "")

                # Ambil tanggal jika ada, jika tidak gunakan sekarang
                if "tanggal" in df.columns:
                    tanggal = pd.to_datetime(row.get("tanggal"), errors='coerce')
                    if pd.isna(tanggal):
                        tanggal = timezone.now().date()
                    else:
                        tanggal = tanggal.date()
                else:
                    tanggal = timezone.now().date()

                Transaksi.objects.create(
                    jenis=jenis,
                    nominal=nominal,
                    keterangan=keterangan,
                    tanggal=tanggal
                )

            self.message_user(request, "Data Transaksi berhasil diunggah", level=messages.SUCCESS)
            return redirect("..")

        return render(request, "admin/upload_excel.html", {
            "title": "Upload Data Transaksi dari Excel"
        })

    def export_excel_view(self, request):
        queryset = Transaksi.objects.all()
        data = []
        for obj in queryset:
            data.append({
                'Jenis': obj.jenis,
                'Nominal': obj.nominal,
                'Keterangan': obj.keterangan,
                'Tanggal': obj.tanggal.strftime('%Y-%m-%d'),
            })
        df = pd.DataFrame(data)
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=transaksi_export.xlsx'
        df.to_excel(response, index=False)
        return response
