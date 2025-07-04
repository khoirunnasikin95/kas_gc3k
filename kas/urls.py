from django.urls import path
from .views import landing_page, export_excel, export_wa, export_rekap_keseluruhan

urlpatterns = [
    path('', landing_page, name='landing'),
    path('export-excel/', export_excel, name='export_excel'),
    path('export-wa/', export_wa, name='export_wa'),
    path('export-rekap/', export_rekap_keseluruhan, name='export_rekap_keseluruhan'),
]
