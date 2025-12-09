import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(
    page_title="Corfin Teknik Analiz",
    page_icon="🛡️",
    layout="wide"
)

# --- BAŞLIK VE KURUMSAL KİMLİK ---
col_logo, col_title = st.columns([1, 5])
with col_title:
    st.title("🛡️ Corfin LUBRICATION | Teknik Çözüm Simülatörü")
    st.markdown("**Akoni Kimya A.Ş.** | Mühendislik ve Tasarım Bölümü")
st.markdown("---")

# --- SOL MENÜ: VERİ GİRİŞİ ---
st.sidebar.header("⚙️ Saha ve Ekipman Verileri")

# 1. Rulman Bilgileri
st.sidebar.subheader("1. Rulman Özellikleri")
d_cap = st.sidebar.number_input("Rulman Dış Çapı (D) - mm", value=240, step=10)
b_genislik = st.sidebar.number_input("Rulman Genişliği (B) - mm", value=80, step=5)
rpm = st.sidebar.number_input("Çalışma Devri (RPM)", value=1200, step=50)
rulman_adedi = st.sidebar.number_input("Toplam Rulman Sayısı", value=12, step=1)

# Genel Gres Formülü: G = 0.005 * D * B
teorik_gramaj = 0.005 * d_cap * b_genislik
# "SKF" ibaresi kaldırıldı, genel ifade kullanıldı:
st.sidebar.info(f"Teorik Standart İhtiyaç (Sefer Başı): **{teorik_gramaj:.2f} gr**")

# 2. Çalışma Şartları (Zorluk Derecesi)
st.sidebar.subheader("2. Ortam Zorluk Derecesi")
sicaklik = st.sidebar.slider("Çalışma Sıcaklığı (°C)", 20, 200, 90)
su_durumu = st.sidebar.select_slider("Su ve Nem Maruziyeti", options=["Kuru", "Nemli", "Su İle Yıkanma", "Basınçlı Su/Buhar"])
yuk_durumu = st.sidebar.select_slider("Yük ve Titreşim", options=["Hafif", "Orta", "Ağır Yük", "Şok Yük/Darbe"])

# --- HESAPLAMA MOTORU (Mühendislik Mantığı) ---

# Katsayı Tanımları (Varsayılan Lityum vs Corfin Ca-Sulfonate)
# 1.0 = Kayıp Yok, 0.5 = Yarı Yarıya Performans Kaybı

# Sıcaklık Etkisi
if sicaklik < 80:
    k_temp_rakip, k_temp_corfin = 1.0, 1.0
elif sicaklik < 120:
    k_temp_rakip, k_temp_corfin = 0.6, 0.95 # Lityum bozulmaya başlar
else:
    k_temp_rakip, k_temp_corfin = 0.3, 0.90 # Corfin yüksek sıcaklıkta stabil

# Su Etkisi
su_map_rakip = {"Kuru": 1.0, "Nemli": 0.8, "Su İle Yıkanma": 0.4, "Basınçlı Su/Buhar": 0.1}
su_map_corfin = {"Kuru": 1.0, "Nemli": 1.0, "Su İle Yıkanma": 0.95, "Basınçlı Su/Buhar": 0.85}
k_su_rakip = su_map_rakip[su_durumu]
k_su_corfin = su_map_corfin[su_durumu]

# Yük Etkisi
yuk_map_rakip = {"Hafif": 1.0, "Orta": 0.9, "Ağır Yük": 0.6, "Şok Yük/Darbe": 0.4}
yuk_map_corfin = {"Hafif": 1.0, "Orta": 1.0, "Ağır Yük": 0.95, "Şok Yük/Darbe": 0.90}
k_yuk_rakip = yuk_map_rakip[yuk_durumu]
k_yuk_corfin = yuk_map_corfin[yuk_durumu]

# Toplam Performans Skoru (Basit Çarpım)
perf_rakip = k_temp_rakip * k_su_rakip * k_yuk_rakip
perf_corfin = k_temp_corfin * k_su_corfin * k_yuk_corfin

# Yağlama Sıklığı Hesabı (Referans: 10 gün olsun)
baz_gun = 15 # İdeal şartlarda
gercek_gun_rakip = baz_gun * perf_rakip
gercek_gun_corfin = baz_gun * perf_corfin

# Yıllık Tüketim Hesabı
yil_tuketim_rakip = (360 / max(gercek_gun_rakip, 0.5)) * teorik_gramaj * rulman_adedi / 1000
yil_tuketim_corfin = (360 / max(gercek_gun_corfin, 0.5)) * teorik_gramaj * rulman_adedi / 1000

# --- EKRAN ÇIKTILARI ---

# 1. Üst Özet Kartları
col1, col2, col3 = st.columns(3)
col1.metric("Rakip Ürün Yağlama Aralığı", f"{gercek_gun_rakip:.1f} Gün", f"Yıllık {yil_tuketim_rakip:.1f} kg")
col2.metric("Corfin Yağlama Aralığı", f"{gercek_gun_corfin:.1f} Gün", f"Yıllık {yil_tuketim_corfin:.1f} kg", delta_color="normal")
fark_kg = yil_tuketim_rakip - yil_tuketim_corfin
col3.metric("Kazandıran Tasarruf", f"{fark_kg:.1f} kg/Yıl", "Daha Az Atık", delta_color="inverse")

st.markdown("---")

# 2. Grafik Alanı
c_left, c_right = st.columns([1, 1])

with c_left:
    st.subheader("🔍 Performans Kırılımı (Radar Analizi)")
    categories = ['Sıcaklık Dayanımı', 'Su Direnci', 'Yük/Darbe Dayanımı']
    
    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=[k_temp_rakip*100, k_su_rakip*100, k_yuk_rakip*100],
        theta=categories, fill='toself', name='Standart Gres', line_color='gray'
    ))
    fig_radar.add_trace(go.Scatterpolar(
        r=[k_temp_corfin*100, k_su_corfin*100, k_yuk_corfin*100],
        theta=categories, fill='toself', name='Corfin Kalsiyum Sülfonat', line_color='#E63946' # Corfin Kırmızısı
    ))
    fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=True, height=400)
    st.plotly_chart(fig_radar, use_container_width=True)

with c_right:
    st.subheader("📊 Yıllık Tüketim Projeksiyonu")
    df_chart = pd.DataFrame({
        "Senaryo": ["Mevcut Durum (Rakip)", "Corfin Çözümü"],
        "Tüketim (kg)": [yil_tuketim_rakip, yil_tuketim_corfin],
        "Renk": ["Gray", "#E63946"]
    })
    fig_bar = px.bar(df_chart, x="Senaryo", y="Tüketim (kg)", color="Senaryo", 
                     color_discrete_sequence=["gray", "#E63946"], text_auto='.1f')
    fig_bar.update_layout(height=400)
    st.plotly_chart(fig_bar, use_container_width=True)

# 3. Yorum ve Rapor Alanı
st.success(f"""
**Teknik Değerlendirme:** Sisteme girilen {sicaklik}°C sıcaklık ve '{su_durumu}' ortam şartlarında, standart gres filmi mukavemetini kaybederek 
akıp gitmekte veya bozulmaktadır. Corfin Kalsiyum Sülfonat teknolojisi ise yapısındaki kalsit partikülleri sayesinde 
bu şartlarda dahi yük taşımaya devam eder. Bu sayede yağlama periyodunu **{int(gercek_gun_rakip)} günden {int(gercek_gun_corfin)} güne** çıkarabiliyoruz.
""")