# importowanie bibliotek
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import requests 


nowy_katalog = '/Users/katarzynakoszel/Downloads/projektesplo'
try:
    os.chdir(nowy_katalog)
except FileNotFoundError:
    pass 

st.set_page_config(page_title="Różowy raport", layout="wide")

### WCZYTYWANIE DANYCH 

@st.cache_data
def wczytaj_dane(x):
    df = pd.read_csv(x)
    return df

@st.cache_data
def wczytaj_dane_gus(x):
    df = pd.read_csv(x, sep=";")
    return df

def pobierz_mape():
    url = "https://raw.githubusercontent.com/ppatrzyk/polska-geojson/master/wojewodztwa/wojewodztwa-min.geojson"
    return requests.get(url).json()

mammografia_pelna = wczytaj_dane("mammografia_pełna.csv")
zgon_data = wczytaj_dane("nowsutka_czyste.csv")
kobiety = wczytaj_dane_gus("LUDN_2137_CTAB_20260402154610.csv")
mammografia_dluga = wczytaj_dane("mammografia_pełna.csv")
szpitale_czyste = wczytaj_dane("szpitale_czyste.csv")
ludnosc = wczytaj_dane_gus("LUDN_2137_CTAB_20260402192255.csv")
mezczyzni = wczytaj_dane_gus("LUDN_3977_CTAB_20260516114155.csv") # uwaga nowy plik
geojson_polska = pobierz_mape()

## PANEL BOCZNY - WYBÓR ROKU
with st.sidebar:
    st.header("Ustawienia:")
    wybrany_rok = st.selectbox("Wybierz rok do analizy:", [2022, 2023, 2024])
    rok_skrocony = wybrany_rok % 100
    
    lista_wojewodztw = mammografia_pelna[mammografia_pelna["Województwo"] != "RAZEM"]["Województwo"].unique()
    wybrane_woj = st.multiselect("Podświetl województwo na wykresach punktowych:", lista_wojewodztw)

### OBRÓBKA DANYCH 

# dane o liczności kobiet w grupie wiekowej 45 - 74 lata
kobiety_c = kobiety.copy()
kobiety_c.columns = kobiety_c.columns.str.lower()
kobiety_c['nazwa'] = kobiety_c['nazwa'].astype(str).str.lower().str.strip()
kol_wiek = [c for c in kobiety_c.columns if any(w in c.replace('_', '-') for w in ['45-49', '50-54', '55-59', '60-64', '65-69', '70-74'])]
kobiety_c['suma_kobiet'] = kobiety_c[kol_wiek].sum(axis=1)

# filtrujemy mammografie pod wybrany rok
m = mammografia_dluga[(mammografia_dluga["Rok"] == rok_skrocony) & (mammografia_dluga["Województwo"] != "RAZEM")]
m["woj_join"] = m["Województwo"].astype(str).str.lower().str.strip()

# laczenie z liczba kobiet
df_mapa = m.merge(kobiety_c[["nazwa", "suma_kobiet"]], left_on="woj_join", right_on="nazwa", how="left")
df_mapa['wsp_mammo'] = (df_mapa['Całk_liczb_bad'] / df_mapa['suma_kobiet']) * 100

## dane o szpitalach
szpitale = szpitale_czyste.copy()
szpitale['obszar_low'] = szpitale['obszar'].astype(str).str.lower().str.strip()
szpitale['zmiana_lozek'] = szpitale['lozka_2024'] - szpitale['lozka_2022']

ludn_c = ludnosc.copy()
ludn_c.columns = ludn_c.columns.str.lower()
kol_pop_lista = [c for c in ludn_c.columns if 'ogolem' in c or 'ogółem' in c or 'ogół' in c]

kol_pop = kol_pop_lista[0]
ludn_c = ludn_c[['nazwa', kol_pop]].rename(columns={kol_pop: 'populacja'})

ludn_c['nazwa_low'] = ludn_c['nazwa'].astype(str).str.lower().str.strip()

kol_lozka = f"lozka_{wybrany_rok}" if f"lozka_{wybrany_rok}" in szpitale.columns else "lozka_2024"
df_szpitale_mapa = szpitale.merge(ludn_c, left_on='obszar_low', right_on='nazwa_low', how='left')

# Liczymy wskaźnik na 10 tys. mieszkańców dla wybranego roku
df_szpitale_mapa['lozka_10tys'] = (df_szpitale_mapa[kol_lozka] / df_szpitale_mapa['populacja']) * 10000

# dane o mezczyznach - czyszczenie:
mezczyzni = wczytaj_dane_gus("LUDN_3977_CTAB_20260516114155.csv")
kolumny_do_zostawienia = ['Nazwa'] + [col for col in mezczyzni.columns if 'mężczyźni' in col.lower() or 'mezczyzni' in col.lower()]
mezczyzni = mezczyzni[kolumny_do_zostawienia]
mezczyzni_dluga = mezczyzni.melt(
    id_vars = ["Nazwa"],
    value_vars=[col for col in mezczyzni.columns if col != 'Nazwa'],
    var_name="Rok_brzydki",
    value_name="Wartosc"
)
mezczyzni_dluga['Rok'] = mezczyzni_dluga['Rok_brzydki'].str.extract(r'(\d{4})')
mezczyzni = mezczyzni_dluga[["Nazwa", "Wartosc", "Rok"]]
mezczyzni['Wartosc'] = mezczyzni['Wartosc'].astype(str).str.replace(',', '.').astype(float)

# INTERFEJS UŻYTKOWNIKA

st.title("Różowy raport")

# Definicja zakładek
tab1, tab2, tab3 = st.tabs(["Przed diagnozą", "W trakcie diagnozy", "Po diagnozie"])

# ======================================================================================================================
# ZAKŁADKA 1: Przed diagnozą
# ======================================================================================================================
with tab1:
    st.header("Sekcja: Profilaktyka i Zgłaszalność")
    
    ## WYKRES PIERWSZY - mapa zgłaszalności na mammografię

    st.subheader(f"Mapa: Zgłaszalność na badania mammograficzne w roku {wybrany_rok}")

    df_mapa['woj_UPPER'] = df_mapa['Województwo'].str.upper()

    fig_map_mammo = px.choropleth(
        df_mapa, geojson=geojson_polska, locations="woj_join", featureidkey="properties.nazwa",
        color="wsp_mammo", color_continuous_scale="RdPu_r",
        labels={'wsp_mammo': 'Zgłaszalność (%)'}, hover_data=["woj_UPPER"]
    )

    fig_map_mammo.update_traces(
        hovertemplate="<b>%{customdata[0]}</b><br>Zgłaszalność: %{z:.2f}%<extra></extra>"
    )

    if wybrane_woj:

        wybrane_up = [w.strip().upper() for w in wybrane_woj]
        
        df_niewybrane = df_mapa[~df_mapa['woj_UPPER'].isin(wybrane_up)]
        df_zaznaczone = df_mapa[df_mapa['woj_UPPER'].isin(wybrane_up)]


        if not df_niewybrane.empty:
            fig_map_mammo.add_trace(
                go.Choropleth(
                    geojson=geojson_polska,
                    locations=df_niewybrane["woj_join"],
                    featureidkey="properties.nazwa",
                    z=[0] * len(df_niewybrane),
                    colorscale=[[0, 'rgba(30, 30, 30, 0.5)'], [1, 'rgba(30, 30, 30, 0.5)']], 
                    showscale=False,
                    marker=dict(line=dict(width=0.5, color='rgba(120, 120, 120, 0.2)')),
                    hoverinfo="skip"
                )
            )

        if not df_zaznaczone.empty:
            fig_map_mammo.add_trace(
                go.Choropleth(
                    geojson=geojson_polska,
                    locations=df_zaznaczone["woj_join"],
                    featureidkey="properties.nazwa",
                    z=[1] * len(df_zaznaczone),
                    colorscale=[[0, 'rgba(0,0,0,0)'], [1, 'rgba(0,0,0,0)']],
                    showscale=False,
                    marker=dict(line=dict(width=1.0, color="whitesmoke")),
                    hoverinfo="skip"
                )
            )

    fig_map_mammo.update_geos(
        fitbounds="locations", 
        visible=False,
        bgcolor="rgba(0,0,0,0)" 
    )
    
    fig_map_mammo.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        coloraxis_colorbar=dict(thickness=15, len=0.6, y=0.5),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        dragmode=False
    )
    
    st.plotly_chart(fig_map_mammo, use_container_width=True,
                    config={
            'scrollZoom': False,
            'displayModeBar': False,
            'staticPlot': False 
        })


    # WYKRES DRUGI - zgłaszalność vs wykrywalność
    st.divider()
    st.subheader(f"Zależność między zgłaszalnością na mammografię a wykrywalnością nowotworów:")
    d_tab1 = mammografia_pelna[(mammografia_pelna["Województwo"] != "RAZEM") & (mammografia_pelna["Rok"] == rok_skrocony)].copy()
    d_tab1["Zglaszalnosc_proc"] = (d_tab1["Całk_liczb_bad"] / d_tab1["Liczba_kobiet"]) * 100
    d_tab1["Wykryte_10tys"] = (d_tab1["Złośl"] / d_tab1["Liczba_kobiet"]) * 10000

    if not wybrane_woj:
        kolory_tab1 = ["#dd3497"] * len(d_tab1) 
    else:
        kolory_tab1 = ["#ae017e" if woj in wybrane_woj else "#f0f0f0" for woj in d_tab1["Województwo"]]

    wykres2 = px.scatter(
        d_tab1,
        x="Zglaszalnosc_proc",
        y="Wykryte_10tys",
        hover_name="Województwo",
        title=f"Czy częstsze badania to wyższa wykrywalność? (Rok {wybrany_rok})",
        labels={
            "Zglaszalnosc_proc": "Procent przebadanych kobiet (%)",
            "Wykryte_10tys": "Wykryte nowotwory (na 10 tys. kobiet)"
        }
    )
    wykres2.update_traces(
        marker=dict(size=14, color=kolory_tab1, line=dict(width=1, color="DarkSlateGrey")),
        hovertemplate="<b>%{hovertext}</b><br>Przebadane kobiety [%]: %{x:.2f}%<br>Wykryte nowotwory (na 10 tys. kobiet): %{y:.2f}<extra></extra>"
    )
    st.plotly_chart(wykres2, use_container_width=True)


# =========================================================================================================
# ZAKŁADKA 2: W trakcie diagnozy
# =========================================================================================================
with tab2:
    st.header("Sekcja: Wyniki Badań")
    st.subheader(f"Jak skutecznie polskie województwa szukają nowotworów? Dane dla roku {wybrany_rok}")

    # Wykres nr 3 -  wskaźnik skierowań vs precyzja
    st.write("Wykres pokazuje, że zazwyczaj im łatwiej w danym województwie o skierowanie na diagnostykę onkologiczną,\
              tym rzadziej kończy się ona ostatecznym potwierdzeniem nowotworu.")
    d_wyk1 = mammografia_pelna[(mammografia_pelna["Województwo"]!="RAZEM")&(mammografia_pelna["Rok"]==rok_skrocony)].copy()
    
    d_wyk1["precyzja"] = ((d_wyk1["Złośl"] / d_wyk1["Dalsza_diag_onkologiczna"]) * 100).round(2)
    d_wyk1["wskaznik_skierowan"] = ((d_wyk1["Dalsza_diag_onkologiczna"] / d_wyk1["Całk_liczb_bad"]) * 100).round(2)
    
    wykres1 = px.scatter(
        d_wyk1,
        x="wskaznik_skierowan",
        y="precyzja",
        hover_name="Województwo",
        labels={
            "wskaznik_skierowan": "Odsetek skierowań na dalszą diagnostykę onkologiczną (%)",
            "precyzja": "Potwierdzone nowotwory (%)"
        }
    )
    wykres1.update_traces(marker=dict(size=15, color=kolory_tab1, line=dict(width=1, color="DarkSlateGrey")),
                          hovertemplate="<b>%{hovertext}</b><br>Procent skierowań: %{x}%<br>Potwierdzone nowotwory: %{y}%<extra></extra>")
    st.plotly_chart(wykres1, use_container_width=True)

    # Wykres nr 4 - Sunburst: Struktura diagnoz
    st.divider()
    st.subheader(f"Struktura diagnoz mammografii w Polsce w {wybrany_rok} roku")
    st.write("Kliknij w sekcję **'Pozostałe'**, aby zobaczyć szczegółowy podział podejrzanych zmian.")
    dane_wyk4 = mammografia_pelna[(mammografia_pelna["Województwo"]=="RAZEM")&(mammografia_pelna["Rok"]==rok_skrocony)].iloc[0]

    norm = dane_wyk4["Norm"]
    lag = dane_wyk4["Łag"]
    nieokresl = dane_wyk4["Nieokreśl"]
    prawd_lag = dane_wyk4["Prawd_łag"]
    podejrz = dane_wyk4["Podejrz"]
    zlosl = dane_wyk4["Złośl"]

    suma_pozostale = nieokresl + prawd_lag + podejrz + zlosl
    suma_wszystkich = norm + lag + suma_pozostale

    labels = ["Wyniki", "Normalna", "Łagodna", "Pozostałe", "Nieokreślone", "Prawd. łagodne", "Podejrzane", "Złośliwe"]
    parents = ["", "Wyniki", "Wyniki", "Wyniki", "Pozostałe", "Pozostałe", "Pozostałe", "Pozostałe"]
    values = [suma_wszystkich, norm, lag, suma_pozostale, nieokresl, prawd_lag, podejrz, zlosl]
    colors = ["#ffffff", "#feebe2", "#fcc5c0", "#fa9fb5", "#f768a1", "#dd3497", "#ae017e", "#7a0177"]
    
    dodatkowy_opis = [
        "", "", "", "", 
        f"<br>Udział w kategorii Pozostałe: {(nieokresl/suma_pozostale):.2%}", 
        f"<br>Udział w kategorii Pozostałe: {(prawd_lag/suma_pozostale):.2%}", 
        f"<br>Udział w kategorii Pozostałe: {(podejrz/suma_pozostale):.2%}",   
        f"<br>Udział w kategorii Pozostałe: {(zlosl/suma_pozostale):.2%}"      
    ]
    
    wykres4 = go.Figure(go.Sunburst(
        labels=labels, parents=parents, values=values, branchvalues="total",
        marker=dict(colors=colors), customdata=dodatkowy_opis, textinfo="label+percent parent",
        hovertemplate=(
            "<b>%{label}</b><br>Liczba: %{value}<br>Udział w całości badań: %{percentRoot:.2%}<br>%{customdata}<extra></extra>")
    ))
    wykres4.update_layout(margin=dict(t=10, l=10, r=10, b=10), height=500)
    st.plotly_chart(wykres4, use_container_width=True)

    # Wykres nr 5 - Lejek diagnostyczny
    st.divider()
    st.subheader(f"Ścieżka pacjentki: Lejek diagnostyczny (Rok {wybrany_rok})")
    st.write("Wykres pokazuje, jak filtruje się grupa badanych kobiet na kolejnych etapach systemu.")

    dane_lejek = mammografia_pelna[
        (mammografia_pelna["Województwo"] == "RAZEM") & 
        (mammografia_pelna["Rok"] == rok_skrocony)
    ].iloc[0]

    dane_do_lejka = pd.DataFrame({
        "Etap": [
            "Wszystkie wykonane badania", 
            "Dalsza diagnostyka (skierowania ogółem)", 
            "Konsultacja onkologiczna", 
            "Wykryte nowotwory złośliwe"
        ],
        "Liczba": [
            dane_lejek["Całk_liczb_bad"], 
            dane_lejek["Dalsza_diag"], 
            dane_lejek["Dalsza_diag_onkologiczna"], 
            dane_lejek["Złośl"]
        ]
    })

    wykres_lejek = px.funnel(
        dane_do_lejka,
        y="Etap",
        x="Liczba"
    )
    wykres_lejek.update_traces(
        marker=dict(color="#dd3497"),
        texttemplate="%{value}<br>%{percentInitial:.2%}" 
    )
    st.plotly_chart(wykres_lejek, use_container_width=True)
    
    # Wykres 6 - smiertelnosc mezczyzn 
    st.header("Umieralność mężczyzn")
    
    dane_wykres = mezczyzni[mezczyzni['Rok'] == str(wybrany_rok)].copy()

    if not wybrane_woj:
        kolory_kropek = ["#dd3497"] * len(dane_wykres)
    else:
        wybrane_up = [w.strip().upper() for w in wybrane_woj]
        kolory_kropek = [
            "#63005A" if woj.strip().upper() in wybrane_up else "#e0e0e0" 
            for woj in dane_wykres['Nazwa']
        ]

    fig_mezczyzni = px.bar(
        dane_wykres, 
        x="Wartosc", 
        y="Nazwa", 
        orientation="h",
        title=f"Wskaźnik umieralności u mężczyzn (Dane dla roku {wybrany_rok})",
        labels={
            "Wartosc": "Wskaźnik zachorowań",
            "Nazwa": "Województwo"
        },
        hover_name="Nazwa"
    )
    
    fig_mezczyzni.update_traces(
        marker=dict(color=kolory_kropek, line=dict(width=1, color="DarkSlateGrey")),
        hovertemplate="<b>%{hovertext}</b><br>Wskaźnik: %{x}<extra></extra>"
    )
    

    fig_mezczyzni.update_layout(
        xaxis_title="Wskaźnik zachorowań",
        yaxis_title="", 
        yaxis={'categoryorder': 'total ascending'}, 
        height=550 
    )
    st.plotly_chart(fig_mezczyzni, use_container_width=True)
    st.caption("Wskaźnik zgonów oznacza liczbę zgonów na raka sutka w danym województwie podzieloną przez 100 tys. mieszkańców." \
    "Ze względu na rzadkość występowania nowotworu piersi u mężczyzn, roczna liczba przypadków w poszczególnych województwach jest bardzo mała. Różnice między regionami mogą być wynikiem zwykłego odchylenia statystycznego, a nie realnych trendów. " \
    "Niemniej dane pokazują, że zjawisko to jest obecne powszechnie w całym kraju. Jedynym przypadkiem, gdzie nie zanotowano " \
    "zgonu na raka sutka u męzczyzny było województwo opolskie w roku 2022. ")

# ==========================================
# ZAKŁADKA 3: Po diagnozie
# ==========================================
with tab3:
    st.header("Sekcja: System Opieki i Leczenie")
    st.subheader(f"Wpływ profilaktyki na wskaźnik zgonów (Rok {wybrany_rok})")

    # Wykres 6 - Scatter: zaleznosc miedzy profilaktyka a wspolczynnikiem zgonow
    d_zgony = zgon_data[zgon_data["rok"] == wybrany_rok].copy()
    d_zgony["obszar"] = d_zgony["obszar"].str.upper().str.strip()
    d_prof = mammografia_pelna[(mammografia_pelna["Województwo"] != "RAZEM") & (mammografia_pelna["Rok"] == rok_skrocony)].copy()
    
    d_prof["Zglaszalnosc_proc"] = ((d_prof["Całk_liczb_bad"] / d_prof["Liczba_kobiet"]) * 100).round(2)
    d_prof["Woj_Match"] = d_prof["Województwo"].str.upper().str.strip()
    
    df_merged = pd.merge(d_prof, d_zgony, left_on="Woj_Match", right_on="obszar")
    

    df_merged["wspolczynnik"] = df_merged["wspolczynnik"].round(2)
    
    mediana_prof = df_merged["Zglaszalnosc_proc"].median()
    mediana_zgon = df_merged["wspolczynnik"].median()

    if not wybrane_woj:
        kolory_tab3 = ["#dd3497"] * len(df_merged)
    else:
        wybrane_up = [w.strip().upper() for w in wybrane_woj]
        kolory_tab3 = ["#b50082" if woj.strip().upper() in wybrane_up else "#f0f0f0" for woj in df_merged["Województwo"]]

    wykres_zgony = px.scatter(
        df_merged,
        x="Zglaszalnosc_proc",
        y="wspolczynnik",
        hover_name="Województwo",

        title=f"Czy profilaktyka ratuje życie? Zgłaszalność na badania a umieralność (Rok {wybrany_rok})",
        labels={
            "Zglaszalnosc_proc": "Zgłaszalność na mammografię (%)", 
            "wspolczynnik": "Wskaźnik zgonów"
        }
    )
    wykres_zgony.add_vline(x=mediana_prof, line_dash="dash", line_color="lightgray")
    wykres_zgony.add_hline(y=mediana_zgon, line_dash="dash", line_color="lightgray")
    
    wykres_zgony.update_traces(
        marker=dict(size=14, color=kolory_tab3, line=dict(width=1, color="DarkSlateGrey")),
        hovertemplate="<b>%{hovertext}</b><br>Przebadane kobiety: %{x}%<br>Współczynnik zgonów: %{y}<extra></extra>"
    )

    st.plotly_chart(wykres_zgony, use_container_width=True)
    st.caption("Linie przerywane oznaczają medianę krajową dla wybranego roku. Współczynnik zgonów to liczba zgonów na raka piersi na 100 tys. kobiet.")

    # Wykres 7 - Mapa: szpitale onkologiczne
    st.divider()
    st.subheader("Infrastruktura: Łóżka na oddziałach onkologicznych")
    
    df_szpitale_mapa = szpitale.merge(ludn_c[['nazwa_low', 'populacja']], left_on='obszar_low', right_on='nazwa_low', how='left')
    
    kol_lozka = f"lozka_{wybrany_rok}" if f"lozka_{wybrany_rok}" in szpitale.columns else "lozka_2024"
    df_szpitale_mapa['lozka_10tys'] = (df_szpitale_mapa[kol_lozka] / df_szpitale_mapa['populacja']) * 10000
    df_szpitale_mapa['zmiana_procentowa'] = (((df_szpitale_mapa['lozka_2024'] - df_szpitale_mapa['lozka_2022']) / df_szpitale_mapa['lozka_2022'].replace(0, 1)) * 100).astype(float)
    df_szpitale_mapa['zmiana_tekst'] = df_szpitale_mapa['zmiana_procentowa'].apply(
        lambda x: f"+{x:.2f}%" if x > 0 else f"{x:.2f}%"
    )
    df_szpitale_mapa['obszar_UPPER'] = df_szpitale_mapa['obszar'].str.upper()
    
    tryb_mapy = st.radio(
        "Wybierz co wyświetlić na mapie:", 
        [f"Łóżka na 10 tys. mieszkańców (Rok {wybrany_rok})", "Dynamika zmian (2022 -> 2024 w %)"], 
        horizontal=True
    )
    
    if "Dynamika" in tryb_mapy:
        fig_map_szp = px.choropleth(
            df_szpitale_mapa,
            geojson=geojson_polska,
            locations="obszar_low",
            featureidkey="properties.nazwa",
            color="zmiana_procentowa",
            color_continuous_scale="RdPu", 
            color_continuous_midpoint=0,     
            labels={'zmiana_procentowa': 'Zmiana liczby łóżek (%)'},
            hover_data=["obszar_UPPER", "lozka_2022", "lozka_2024", "zmiana_tekst"] 
        )
        fig_map_szp.update_traces(
            hovertemplate="<b>%{customdata[0]}</b><br>Zmiana łóżek: <b>%{customdata[3]}</b><br>Łóżka 2022: %{customdata[1]}<br>Łóżka 2024: %{customdata[2]}<extra></extra>"
        )
    else:
        fig_map_szp = px.choropleth(
            df_szpitale_mapa, 
            geojson=geojson_polska,
            locations="obszar_low",
            featureidkey="properties.nazwa",
            color="lozka_10tys",
            color_continuous_scale="RdPu_r",
            labels={'lozka_10tys': 'Łóżka na 10 tys. mieszkańców'},
            hover_data=["obszar_UPPER", kol_lozka]
        )
        fig_map_szp.update_traces(
            hovertemplate="<b>%{customdata[0]}</b><br>Łóżka na 10 tys. mieszk.: %{z:.2f}<br>Całkowita liczba łóżek: %{customdata[1]}<extra></extra>"
        )

    if wybrane_woj:
        wybrane_up = [w.strip().upper() for w in wybrane_woj]

        df_niewybrane = df_szpitale_mapa[~df_szpitale_mapa['obszar_UPPER'].isin(wybrane_up)]
        df_zaznaczone = df_szpitale_mapa[df_szpitale_mapa['obszar_UPPER'].isin(wybrane_up)]


        if not df_niewybrane.empty:
            fig_map_szp.add_trace(
                go.Choropleth(
                    geojson=geojson_polska,
                    locations=df_niewybrane["obszar_low"],
                    featureidkey="properties.nazwa",
                    z=[0] * len(df_niewybrane),
                    colorscale=[[0, 'rgba(30, 30, 30, 0.5)'], [1, 'rgba(30, 30, 30, 0.5)']], 
                    showscale=False,
                    marker=dict(line=dict(width=0.5, color='rgba(100, 100, 100, 0.3)')),
                    hoverinfo="skip"
                )
            )


        if not df_zaznaczone.empty:
            fig_map_szp.add_trace(
                go.Choropleth(
                    geojson=geojson_polska,
                    locations=df_zaznaczone["obszar_low"],
                    featureidkey="properties.nazwa",
                    z=[1] * len(df_zaznaczone),
                    colorscale=[[0, 'rgba(0,0,0,0)'], [1, 'rgba(0,0,0,0)']],
                    showscale=False,
                    marker=dict(line=dict(width=1.0, color = "whitesmoke")), 
                    hoverinfo="skip"
                )
            )


    fig_map_szp.update_geos(
        fitbounds="locations", 
        visible=False,
        bgcolor="rgba(0,0,0,0)" 
    )
    
    fig_map_szp.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        coloraxis_colorbar=dict(thickness=15, len=0.6, y=0.5),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        dragmode=False
    )
    
    st.plotly_chart(fig_map_szp, use_container_width=True,
                    config={
            'scrollZoom': False,
            'displayModeBar': False,
            'staticPlot': False 
        })