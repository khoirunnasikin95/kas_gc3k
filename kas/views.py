from django.shortcuts import render
from .models import Rumah, Pembayaran, Transaksi
from datetime import datetime
import pandas as pd
from django.http import HttpResponse
from django.utils.timezone import now
from django.utils import timezone
from django.db.models import Sum
from io import BytesIO
from pandas import ExcelWriter

def landing_page(request):
    # Mapping bulan Inggris → Indonesia
    bulan_mapping = {
        'January': 'Januari', 'February': 'Februari', 'March': 'Maret',
        'April': 'April', 'May': 'Mei', 'June': 'Juni',
        'July': 'Juli', 'August': 'Agustus', 'September': 'September',
        'October': 'Oktober', 'November': 'November', 'December': 'Desember'
    }

    # Ambil bulan dan tahun dari query string, fallback ke default
    now_time = timezone.now()
    bulan_default_en = now_time.strftime('%B')
    bulan_default = bulan_mapping.get(bulan_default_en, 'Januari')
    tahun_default = now_time.year

    bulan = request.GET.get('bulan', bulan_default).capitalize()
    tahun = int(request.GET.get('tahun', tahun_default))

    # List pilihan bulan dan tahun
    bulan_list = list(bulan_mapping.values())
    tahun_list = range(2024, 2031)

    # Konversi bulan ke angka
    daftar_bulan = {b: i + 1 for i, b in enumerate(bulan_list)}
    bulan_angka = daftar_bulan.get(bulan, now_time.month)

    # Transaksi bulan ini
    transaksi_bulan = Transaksi.objects.filter(tanggal__month=bulan_angka, tanggal__year=tahun)
    total_masuk = transaksi_bulan.filter(jenis='masuk').aggregate(Sum('nominal'))['nominal__sum'] or 0
    total_keluar = transaksi_bulan.filter(jenis='keluar').aggregate(Sum('nominal'))['nominal__sum'] or 0

    # Transaksi semua waktu
    total_masuk_all = Transaksi.objects.filter(jenis='masuk').aggregate(Sum('nominal'))['nominal__sum'] or 0
    total_keluar_all = Transaksi.objects.filter(jenis='keluar').aggregate(Sum('nominal'))['nominal__sum'] or 0

    # Iuran semua waktu
    iuran_total = Pembayaran.objects.aggregate(
        total_sampah=Sum('iuran_sampah'),
        total_dansos=Sum('iuran_dansos')
    )
    jumlah_iuran_all = (iuran_total['total_sampah'] or 0) + (iuran_total['total_dansos'] or 0)

    # Saldo seluruh waktu
    saldo_all = total_masuk_all + jumlah_iuran_all
    sisa_saldo_all = saldo_all - total_keluar_all
    
    # Pembayaran bulan ini
    pembayaran = Pembayaran.objects.filter(bulan__iexact=bulan, tahun=tahun)
    total_saldo = sum(p.iuran_sampah + p.iuran_dansos for p in pembayaran)

    total_iuran_sampah = pembayaran.aggregate(Sum('iuran_sampah'))['iuran_sampah__sum'] or 0
    total_iuran_dansos = pembayaran.aggregate(Sum('iuran_dansos'))['iuran_dansos__sum'] or 0

    rumah_sudah = Rumah.objects.filter(status='sudah').count()
    rumah_segera = Rumah.objects.filter(status='segera').count()

    context = {
        'pembayaran': pembayaran,
        'bulan': bulan,
        'tahun': tahun,
        'bulan_list': bulan_list,
        'tahun_list': tahun_list,
        'rumah_sudah': rumah_sudah,
        'rumah_segera': rumah_segera,
        'saldo': total_saldo,
        'total_iuran_sampah': total_iuran_sampah,
        'total_iuran_dansos': total_iuran_dansos,
        'jumlah_iuran_all': jumlah_iuran_all,

        # Transaksi bulan ini
        'transaksi': transaksi_bulan,
        'total_masuk': total_masuk,
        'total_keluar': total_keluar,

        # Transaksi semua waktu
        'total_masuk_all': total_masuk_all,
        'total_keluar_all': total_keluar_all,
        'saldo_all': saldo_all,
        'sisa_saldo_all': sisa_saldo_all,
    }

    return render(request, 'landing.html', context)



def export_excel(request):
    bulan = request.GET.get('bulan')
    tahun = request.GET.get('tahun')

    # Filter pembayaran dan transaksi sesuai bulan/tahun
    pembayaran = Pembayaran.objects.filter(bulan__iexact=bulan, tahun=tahun)
    bulan_dict = {b: i + 1 for i, b in enumerate([
        "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember"
    ])}
    bulan_angka = bulan_dict.get(bulan, 1)
    transaksi = Transaksi.objects.filter(tanggal__month=bulan_angka, tanggal__year=int(tahun))

    # Sheet 1: Pembayaran
    pembayaran_data = [{
        'Blok': p.rumah.blok,
        'Nama': p.rumah.nama,
        'Status': p.rumah.get_status_display(),
        'Bulan': p.bulan,
        'Tahun': p.tahun,
        'Iuran Sampah': p.iuran_sampah,
        'Iuran Dansos': p.iuran_dansos,
    } for p in pembayaran]
    df_pembayaran = pd.DataFrame(pembayaran_data)

    # Sheet 2: Transaksi
    transaksi_data = [{
        'Jenis': t.jenis.title(),
        'Nominal': t.nominal,
        'Keterangan': t.keterangan,
        'Tanggal': t.tanggal.strftime('%d-%m-%Y'),
    } for t in transaksi]
    df_transaksi = pd.DataFrame(transaksi_data)

    # Simpan ke Excel
    with pd.ExcelWriter("export.xlsx", engine='openpyxl') as writer:
        df_pembayaran.to_excel(writer, sheet_name='Iuran', index=False)
        df_transaksi.to_excel(writer, sheet_name='Transaksi', index=False)

    with open("export.xlsx", "rb") as f:
        response = HttpResponse(f.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        filename = f"Iuran_dan_Transaksi_{bulan}_{tahun}.xlsx"
        response['Content-Disposition'] = f'attachment; filename={filename}'
        return response



def export_rekap_keseluruhan(request):
    # Semua data pembayaran
    pembayaran = Pembayaran.objects.all()
    transaksi = Transaksi.objects.all()

    # Sheet 1: Pembayaran
    pembayaran_data = [{
        'Blok': p.rumah.blok,
        'Nama': p.rumah.nama,
        'Status': p.rumah.get_status_display(),
        'Bulan': p.bulan,
        'Tahun': p.tahun,
        'Iuran Sampah': p.iuran_sampah,
        'Iuran Dansos': p.iuran_dansos,
    } for p in pembayaran]
    df_pembayaran = pd.DataFrame(pembayaran_data)

    # Sheet 2: Transaksi
    transaksi_data = [{
        'Jenis': t.jenis.title(),
        'Nominal': t.nominal,
        'Keterangan': t.keterangan,
        'Tanggal': t.tanggal.strftime('%d-%m-%Y'),
    } for t in transaksi]
    df_transaksi = pd.DataFrame(transaksi_data)

    # Simpan ke Excel
    with pd.ExcelWriter("rekap_keseluruhan.xlsx", engine='openpyxl') as writer:
        df_pembayaran.to_excel(writer, sheet_name='Iuran', index=False)
        df_transaksi.to_excel(writer, sheet_name='Transaksi', index=False)

    with open("rekap_keseluruhan.xlsx", "rb") as f:
        response = HttpResponse(f.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=Rekap_Keseluruhan.xlsx'
        return response


def export_wa(request):
    from django.utils.timezone import now

    bulan = request.GET.get('bulan')
    tahun = request.GET.get('tahun')

    semua_rumah = Rumah.objects.all()
    pembayaran_dict = {
        (p.rumah_id): p for p in Pembayaran.objects.filter(bulan__iexact=bulan, tahun=tahun)
    }

    # Lokalisasi tanggal
    bulan_dict = {
        'January': 'Januari', 'February': 'Februari', 'March': 'Maret', 'April': 'April',
        'May': 'Mei', 'June': 'Juni', 'July': 'Juli', 'August': 'Agustus',
        'September': 'September', 'October': 'Oktober', 'November': 'November', 'December': 'Desember'
    }
    tgl = now()
    bulan_ina = bulan_dict.get(tgl.strftime('%B'), tgl.strftime('%B'))
    tanggal = tgl.strftime(f'%d {bulan_ina} %Y')

    # Ubah ini sesuai domain dari Render kamu
    base_url = "https://kas-gc3k.onrender.com"

    baris = []
    baris.append(f"Laporan ini dibuat otomatis di website *Kas Warga Graha Citra 3 Kedanyang*.")
    baris.append(f"Untuk detail silakan kunjungi link ini: {base_url}")
    baris.append("")
    baris.append(f"*Update per : {tanggal}*\n")
    baris.append(f"Pembayaran bulan *{bulan.upper()}* status rumah *Sudah Ditempati*:\n")

    for rumah in semua_rumah.filter(status='sudah'):
        p = pembayaran_dict.get(rumah.id)
        status = "✅" if p and (p.iuran_sampah > 0 or p.iuran_dansos > 0) else "❌"
        baris.append(f"{rumah.blok} | {rumah.nama} | {status}")

    baris.append(f"\nPembayaran bulan *{bulan.upper()}* status rumah *Belum Ditempati*:\n")

    for rumah in semua_rumah.filter(status='segera'):
        p = pembayaran_dict.get(rumah.id)
        status = "✅" if p and p.iuran_dansos > 0 else "❌"
        baris.append(f"{rumah.blok} | {rumah.nama} | {status}")

    baris.append("\nBiaya Sampah Rp. 20.000 dan Bansos Rp. 10.000")
    baris.append("Pengambilan sampah 3x (senin, rabu, sabtu)")
    baris.append("Pembayaran di No Rekenig Mandiri *1400013740692 a.n M. KHOIRUN NASIKIN*")

    pesan = "\n".join(baris)

    return HttpResponse(f"""
        <pre id='wa-text'>{pesan}</pre>
        <script>
        navigator.clipboard.writeText(document.getElementById('wa-text').innerText)
            .then(() => alert("📋 Laporan berhasil disalin ke clipboard"))
            .catch(err => alert("Gagal menyalin teks: " + err));
        </script>
    """)
