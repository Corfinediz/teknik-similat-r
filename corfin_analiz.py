import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import os
import requests
import base64
import xml.etree.ElementTree as ET
from datetime import date

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Corfin Triboloji Simülatörü", page_icon="🛡️", layout="wide")

# PDF Modülü Kontrolü
try:
    from fpdf import FPDF
    import tempfile
    pdf_aktif = True
except ImportError:
    pdf_aktif = False

# ==========================================
# 🏦 KUR VE ARKA PLAN
# ==========================================
@st.cache_data(ttl=3600)
def get_tcmb_rates():
    kurlar = {"TRY": 1.0, "USD": 35.5, "EUR": 37.5}
    try:
        url = "https://www.tcmb.gov.tr/kurlar/today.xml"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            for curr in root.findall('Currency'):
                code = curr.get('Kod')
                if code in ["USD", "EUR"]:
                    kurlar[code] = float(curr.find('ForexSelling').text)
            return kurlar, True
    except: pass
    return kurlar, False

rates, online_durum = get_tcmb_rates()

def to_report_currency(amount, currency, target_currency):
    if currency == target_currency: return amount
    return (amount * rates[currency]) / rates[target_currency]

def viskozite_kontrol(ndm, secilen_vis):
    if ndm <= 0: return "Veri Bekleniyor...", "secondary"
    if ndm < 50000 and secilen_vis < 150: return "⚠️ Düşük Viskozite Riski", "warning"
    if ndm > 200000 and secilen_vis > 220: return "⚠️ Yüksek Viskozite Riski", "warning"
    return "✅ Viskozite Uygun", "success"

def get_base64_image(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return None

# ==========================================
# 🎛️ ÜST BAŞLIK (HTML/CSS - Pantone 123C)
# ==========================================
logo_dosyasi = "logo.png"
img_base64 = get_base64_image(logo_dosyasi)

if img_base64:
    logo_html = f'<img src="data:image/png;base64,{img_base64}" style="height: 80px; margin-right: 20px; vertical-align: middle;">'
else:
    logo_html = ""

# Renk Kodu: #FFC72C (Pantone 123C benzeri)
st.markdown(f"""
    <div style="display: flex; justify-content: flex-start; align-items: center; margin-bottom: 20px; background-color: #0e1117; padding: 10px; border-radius: 10px;">
        {logo_html}
        <h1 style="color: #FFC72C; margin: 0; padding: 0; font-size: 34px; display: inline-block; vertical-align: middle; font-family: sans-serif; font-weight: bold;">
            Corfin LUBRICATION | Triboloji Simülatörü
        </h1>
    </div>
    """, unsafe_allow_html=True)

if online_durum: 
    st.caption(f"📡 Canlı Kur: 1 EUR = {rates['EUR']:.2f} TL | 1 USD = {rates['USD']:.2f} TL")

st.markdown("---")

# ==========================================
# ⚙️ SOL MENÜ: GİRİŞLER
# ==========================================

sabun_tipleri = ["Lityum", "Lityum Kompleks", "Kalsiyum Sülfonat", "Alüminyum Kompleks", "Poliüre", "Bentonit (Kil)", "Diğer"]

# 1. ANALİZ TÜRÜ
st.sidebar.header("1. Analiz Ayarları")
uygulama_tipi = st.sidebar.selectbox("Uygulama", ["Genel Proses (Dişli, Zincir vb.)", "Rulman (Bearing)"])
rapor_curr = st.sidebar.selectbox("Rapor Para Birimi", ["EUR", "USD", "TRY"], index=0)

r_gramaj = 0
d_ic, d_dis, b_gen, rpm, ndm = 0,0,0,0,0

if uygulama_tipi == "Rulman (Bearing)":
    with st.sidebar.expander("⚙️ Rulman Verileri", expanded=True):
        d_ic = st.number_input("İç Çap (mm)", 0.0, 2000.0, 0.0)
        d_dis = st.number_input("Dış Çap (mm)", 0.0, 2500.0, 0.0)
        b_gen = st.number_input("Genişlik (mm)", 0.0, 800.0, 0.0)
        rpm = st.number_input("Devir (RPM)", 0.0, 15000.0, 0.0)
        
        if d_ic > 0 and d_dis > 0 and rpm > 0:
            ndm = rpm * ((d_ic+d_dis)/2)
            r_gramaj = 0.005 * d_dis * b_gen
        else:
            ndm = 0
            r_gramaj = 0

st.sidebar.markdown("---")

# 2. RAKİP (MEVCUT DURUM)
st.sidebar.header("2. Mevcut Durum (Rakip)")
with st.sidebar.expander("🔴 Rakip Verileri", expanded=True):
    r_ad = st.text_input("Rakip Marka", "Mevcut Ürün")
    r_sabun = st.selectbox("Sabun Tipi", sabun_tipleri, index=0, key="rsabun")
    
    r_fiyat_biliniyor = st.checkbox("Rakip Fiyatı Gir", value=True)
    
    if r_fiyat_biliniyor:
        c1, c2 = st.columns(2)
        r_fiyat = c1.number_input("Birim Fiyat", 0.0, 10000.0, 0.0, key="rf")
        r_curr = c2.selectbox("Para Birimi", ["EUR", "USD", "TRY"], index=0, key="rc")
    else:
        r_fiyat = 0.0; r_curr = "EUR"

    if uygulama_tipi == "Rulman (Bearing)":
        r_vis = st.number_input("Viskozite (cSt)", 0.0, 5000.0, 0.0, key="rv")
        if ndm > 0 and r_vis > 0:
            durum_msg, durum_renk = viskozite_kontrol(ndm, r_vis)
            st.markdown(f":{durum_renk}[{durum_msg}]")

    st.markdown("---")
    st.markdown("**⏳ Yağlama Sıklığı:**")
    c_p1, c_p2 = st.columns(2)
    # HATA DUZELTİLDİ: min_value=0.0 yapıldı
    r_periyot_val = c_p1.number_input("Sıklık Değeri", 0.0, 10000.0, 0.0, key="rpv")
    r_birim = c_p2.selectbox("Birim", ["Dakika", "Saat", "Gün", "Hafta"], index=2, key="rb")
    
    mevcut_tuketim_val = 0
    if uygulama_tipi != "Rulman (Bearing)":
        aylik_tuketim_val = st.number_input("Tüketim Miktarı (kg/Ay)", 0.0, 100000.0, 0.0)
        mevcut_tuketim_val = aylik_tuketim_val * 12

# 3. CORFIN (HEDEF)
st.sidebar.header("3. Corfin Çözümü")
with st.sidebar.expander("🟢 Corfin Hedefleri", expanded=True):
    c_ad = st.text_input("Corfin Marka", "CORFIN STILEX PM")
    c_sabun = st.selectbox("Sabun Tipi", sabun_tipleri, index=2, key="csabun")

    c_fiyat_biliniyor = st.checkbox("Corfin Fiyatı Gir", value=True)
    
    if c_fiyat_biliniyor:
        c3, c4 = st.columns(2)
        c_fiyat = c3.number_input("Birim Fiyat", 0.0, 10000.0, 0.0, key="cf")
        c_curr = c4.selectbox("Para Birimi", ["EUR", "USD", "TRY"], index=0, key="cc")
    else:
        c_fiyat = 0.0; c_curr = "EUR"
    
    if uygulama_tipi == "Rulman (Bearing)":
        c_vis = st.number_input("Viskozite (cSt)", 0.0, 5000.0, 0.0, key="cv")

    st.markdown("---")
    st.markdown("**🎯 Hedef Sıklık:**")
    cc_p1, cc_p2 = st.columns(2)
    # HATA DUZELTİLDİ: min_value=0.0 yapıldı
    c_periyot_val = cc_p1.number_input("Yeni Sıklık", 0.0, 10000.0, 0.0, key="cpv")
    c_birim = cc_p2.selectbox("Birim", ["Dakika", "Saat", "Gün", "Hafta"], index=2, key="cb")

# ==========================================
# ⚙️ HESAPLAMA MOTORU
# ==========================================

veri_girisi_var = False
# Sıfırdan büyük mü kontrolü burada yapılıyor
if r_periyot_val > 0 and c_periyot_val > 0:
    if uygulama_tipi == "Rulman (Bearing)":
        if r_gramaj > 0: veri_girisi_var = True
    else:
        if mevcut_tuketim_val > 0: veri_girisi_var = True

def to_hours(val, unit):
    if unit == "Dakika": return val / 60.0
    if unit == "Saat": return val
    if unit == "Gün": return val * 8 
    if unit == "Hafta": return val * 48
    return val

if veri_girisi_var:
    r_hours = to_hours(r_periyot_val, r_birim)
    c_hours = to_hours(c_periyot_val, c_birim)
    
    if r_hours > 0:
        kat_farki = c_hours / r_hours
        tuketim_azalis_orani = 1 / kat_farki
    else:
        kat_farki = 1
        tuketim_azalis_orani = 1

    if uygulama_tipi == "Rulman (Bearing)":
        yillik_saat = 2400 
        r_yillik_kg = (yillik_saat / r_hours) * r_gramaj / 1000
        c_yillik_kg = r_yillik_kg * tuketim_azalis_orani
    else:
        r_yillik_kg = mevcut_tuketim_val
        c_yillik_kg = r_yillik_kg * tuketim_azalis_orani

    miktar_kazanc = r_yillik_kg - c_yillik_kg
    kazanc_yuzdesi = (miktar_kazanc / r_yillik_kg) * 100 if r_yillik_kg > 0 else 0

    hesaplanabilir = r_fiyat_biliniyor and c_fiyat_biliniyor and (r_fiyat > 0 and c_fiyat > 0)
    net_kazanc = 0
    r_yillik_mal = 0
    c_yillik_mal = 0

    if hesaplanabilir:
        r_fiyat_son = to_report_currency(r_fiyat, r_curr, rapor_curr)
        c_fiyat_son = to_report_currency(c_fiyat, c_curr, rapor_curr)
        r_yillik_mal = r_yillik_kg * r_fiyat_son
        c_yillik_mal = c_yillik_kg * c_fiyat_son
        net_kazanc = r_yillik_mal - c_yillik_mal

    # EKRAN ÇIKTILARI
    col_k1, col_k2 = st.columns(2)

    with col_k1:
        st.subheader("📉 Tüketim & Verimlilik")
        st.metric("Tüketim Azalışı (KG)", f"{miktar_kazanc:.1f} kg", f"%{kazanc_yuzdesi:.0f} Daha Az Tüketim")
        st.info(f"Mevcut **{int(r_yillik_kg)} kg** yıllık tüketim, **{int(c_yillik_kg)} kg** seviyesine inecektir.")

    main_fig = None 

    with col_k2:
        if hesaplanabilir:
            st.subheader(f"💰 Finansal Kazanç ({rapor_curr})")
            st.metric("Yıllık Nakit Kazancı", f"{net_kazanc:,.2f}", f"%{net_kazanc/r_yillik_mal*100:.0f} Kar")
            main_fig = go.Figure(data=[
                go.Bar(name='Mevcut Gider', x=['TCO'], y=[r_yillik_mal], marker_color='#e74c3c'),
                go.Bar(name='Corfin Gider', x=['TCO'], y=[c_yillik_mal], marker_color='#2ecc71')
            ])
            main_fig.update_layout(height=250, margin=dict(t=10, b=10))
            st.plotly_chart(main_fig, use_container_width=True)
        else:
            st.subheader("⚠️ Finansal Durum")
            st.warning("Fiyat bilgisi eksik olduğu için sadece MİKTAR analizi yapılmaktadır.")
            main_fig = go.Figure(data=[go.Pie(labels=['Kullanılacak', 'Tasarruf'], values=[c_yillik_kg, miktar_kazanc], hole=.5, marker_colors=['#2ecc71', '#95a5a6'])])
            main_fig.update_layout(height=250, margin=dict(t=10, b=10), showlegend=False, annotations=[dict(text=f'%{kazanc_yuzdesi:.0f}\nKAZANÇ', x=0.5, y=0.5, font_size=20, showarrow=False)])
            st.plotly_chart(main_fig, use_container_width=True)

    st.markdown("---")

    # TABLO
    st.subheader("📋 Karşılaştırma Tablosu")

    parametreler = ["Sabun Tipi", "Yağlama Sıklığı", "YILLIK TÜKETİM (KG)", "Operasyonel Verimlilik"]
    rakip_vals = [r_sabun, f"{r_periyot_val} {r_birim}", f"{r_yillik_kg:.1f} kg", "Standart"]
    corfin_vals = [c_sabun, f"{c_periyot_val} {c_birim}", f"**{c_yillik_kg:.1f} kg**", f"**{kat_farki:.1f} Kat Ömür**"]

    if hesaplanabilir:
        parametreler.append("YILLIK MALİYET")
        rakip_vals.append(f"{r_yillik_mal:,.2f} {rapor_curr}")
        corfin_vals.append(f"**{c_yillik_mal:,.2f} {rapor_curr}**")

    table_data = {
        "Parametre": parametreler,
        f"🔴 {r_ad}": rakip_vals,
        f"🟢 {c_ad}": corfin_vals
    }
    df = pd.DataFrame(table_data)
    st.table(df.set_index("Parametre"))

    # PDF RAPOR
    if pdf_aktif:
        class PDF(FPDF):
            def header(self):
                if os.path.exists("logo.png"): self.image('logo.png', 10, 8, 33)
                try:
                    self.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
                    self.add_font('DejaVu', 'B', 'DejaVuSans.ttf', uni=True)
                    self.set_font('DejaVu', 'B', 14)
                except: self.set_font('Arial', 'B', 14)
                title = 'FINANSAL FAYDA RAPORU' if hesaplanabilir else 'TEKNIK VERIMLILIK RAPORU'
                self.cell(80); self.cell(30, 10, title, 0, 1, 'C'); self.ln(15)

        def create_pdf():
            pdf = PDF()
            pdf.add_page()
            font = "Arial"
            try:
                pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
                pdf.add_font('DejaVu', 'B', 'DejaVuSans.ttf', uni=True)
                font = "DejaVu"
            except: pass

            pdf.set_font(font, 'B', 11); pdf.set_fill_color(230, 230, 230)
            pdf.cell(0, 8, "1. ANALIZ OZETI", 1, 1, 'L', 1)
            pdf.set_font(font, '', 10)
            pdf.cell(0, 6, f"Uygulama: {uygulama_tipi}", ln=True)
            pdf.cell(0, 6, f"Mevcut Urun: {r_ad} ({r_sabun})", ln=True)
            pdf.cell(0, 6, f"Onerilen Urun: {c_ad} ({c_sabun})", ln=True)
            pdf.ln(5)

            pdf.set_font(font, 'B', 11)
            pdf.cell(0, 8, "2. SONUC TABLOSU", 1, 1, 'L', 1)
            pdf.set_font(font, '', 10)
            
            col_w = [50, 50, 50, 40]
            headers = ["PARAMETRE", "MEVCUT", "CORFIN", "FARK"]
            pdf.set_font(font, 'B', 9)
            for i, h in enumerate(headers): pdf.cell(col_w[i], 7, h, 1, 0, 'C', 1)
            pdf.ln()
            
            pdf.set_font(font, '', 9)
            
            pdf.cell(col_w[0], 7, "YILLIK TUKETIM", 1)
            pdf.cell(col_w[1], 7, f"{r_yillik_kg:.1f} kg", 1)
            pdf.cell(col_w[2], 7, f"{c_yillik_kg:.1f} kg", 1)
            pdf.cell(col_w[3], 7, f"-{miktar_kazanc:.1f} kg", 1, 1)
            
            if hesaplanabilir:
                pdf.cell(col_w[0], 7, f"TOPLAM MALIYET ({rapor_curr})", 1)
                pdf.cell(col_w[1], 7, f"{r_yillik_mal:,.0f}", 1)
                pdf.cell(col_w[2], 7, f"{c_yillik_mal:,.0f}", 1)
                pdf.set_font(font, 'B', 9)
                pdf.cell(col_w[3], 7, f"{net_kazanc:,.0f} KAZANC", 1, 1)
                pdf.set_font(font, '', 9)

            pdf.ln(5)
            
            if main_fig:
                try:
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as t1:
                        main_fig.write_image(t1.name)
                        pdf.image(t1.name, x=30, y=pdf.get_y(), w=150)
                        pdf.ln(100)
                except Exception as e:
                    pdf.cell(0, 10, f"[Grafik Hatasi: {str(e)}]", ln=True)

            pdf.set_font(font, 'B', 12)
            bg_col = (220, 255, 220) if hesaplanabilir else (255, 255, 200)
            pdf.set_fill_color(*bg_col)
            
            sonuc_txt = f"SONUC: Yillik {miktar_kazanc:.1f} kg gres tasarrufu saglanacaktir."
            if hesaplanabilir:
                sonuc_txt += f" Nakit Kazanc: {net_kazanc:,.2f} {rapor_curr}"
                
            pdf.multi_cell(0, 10, sonuc_txt, 1, 'C', 1)

            return pdf.output(dest='S').encode('latin-1')

        if st.button("📄 Raporu İndir (PDF)"):
            try:
                pdf_data = create_pdf()
                st.download_button("Dosyayı Kaydet", pdf_data, "Corfin_Raporu.pdf", "application/pdf")
                st.success("Rapor başarıyla oluşturuldu!")
            except Exception as e: st.error(f"PDF Hatası: {str(e)}")

else:
    st.info("👈 Lütfen sol menüden değerleri giriniz (0'dan büyük değerler).")
