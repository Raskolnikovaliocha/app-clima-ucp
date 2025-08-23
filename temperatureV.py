import math

import json
import gspread
import streamlit as st
import requests
from datetime import datetime
from datetime import date
from datetime import  timezone
from zoneinfo import ZoneInfo
import pandas as pd
import os
import plotly.express as px
import sys

# A linha 'import pandas as pd' já deve estar no topo do seu arquivo

# --- Configurações ---
CREDS_FILE = 'google_credentials.json'# Nome do credentials google api
# Certifique-se que o nome da planilha que FUNCIONOU no teste está aqui
SHEET_NAME = 'dadosclimaticos2'# Nome da planilha online de dados brutos

# --- Funções ---
# NOVA FUNÇÃO (para colar no lugar da antiga)
import json # Garanta que 'import json' está no topo do seu script

@st.cache_resource
def connect_to_sheet():
    """Conecta-se usando o segredo de linha única ou arquivo local."""
    try:
        # Tenta ler o segredo de linha única do Streamlit Cloud
        creds_json_str = st.secrets["gspread"]["service_account_info"]
        creds_dict = json.loads(creds_json_str)
        gc = gspread.service_account_from_dict(creds_dict)
        return gc
    except (KeyError, FileNotFoundError):
        # Se falhar, tenta usar o arquivo local (para rodar no seu PC)
        try: 
            gc = gspread.service_account(filename=CREDS_FILE)
            return gc
        except Exception as e:
            st.error(f"Falha na conexão local: {e}")
            return None

# Adicionamos um _ (underline) no gc para evitar conflito com variáveis globais
# E cacheamos os dados por 60 segundos para evitar múltiplas leituras
@st.cache_data(ttl=60)
def load_data_from_sheet(_gc, sheet_name):
    """Carrega todos os dados da planilha para um DataFrame."""
    try:
        worksheet = _gc.open(sheet_name).sheet1
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        if 'horario' in df.columns and not df.empty:
            df['horario'] = pd.to_datetime(df['horario'])
        return df
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Planilha '{sheet_name}' não encontrada. Verifique nome e permissões.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao ler dados: {e}")
        return pd.DataFrame()

def append_row_to_sheet(gc, sheet_name, df_row):
    """Adiciona uma linha de um DataFrame à planilha."""
    try:
        worksheet = gc.open(sheet_name).sheet1
        # Convertendo todos os valores para string para garantir compatibilidade
        row_values = [str(val) for val in df_row.values.tolist()[0]]
        worksheet.append_row(row_values, value_input_option='USER_ENTERED')
    except Exception as e:
        st.error(f"Erro ao salvar dados na planilha: {e}")

# ==============================================================================
# FIM DO NOVO BLOCO
# ==============================================================================


# Aqui começa o processo de pegar os dados no weather api
#st.write("Python em uso:", sys.executable)
st.header('Aplicativo para analisar o clima da UCP')
api_key = 'ba581aa976ee412a432b40f8e4cbab62'#Criei um api no site
url = 'https://api.openweathermap.org/data/2.5/weather?lat=-20.7573491&lon=-42.8728688&appid=ba581aa976ee412a432b40f8e4cbab62&units=metric&lang=pt_br'# API com latitude e longitude de Viçosa
#site + lat+ long
tab1, tab2 = st.tabs(['Análise diária', 'resumo dos dias'])

with tab1:
    # Novo bloco de conexão para a tab1

    gc = connect_to_sheet()
    if gc is None:
        st.stop()  # Se a conexão falhar, para o app

    resposta = requests.get(url) #

    if resposta.status_code == 200:
        dados = resposta.json()
        #st.write(dados)
        temperatura = dados["main"]["temp"]
        umidade = dados["main"]["humidity"]
        minT = dados["main"]["temp_min"]

        maxT = dados["main"]["temp_max"]
        #nascer e pôr do sol
        sunrise_utc = dados["sys"]["sunrise"]
        sunset_utc = dados["sys"]["sunset"]
        nuvens = dados["weather"][0]["description"]
        timezone_offset = dados["timezone"]
        paisBR= dados["sys"]['country']
        cidade = dados["name"]
        coordenada = dados["coord"]["lon"]
        coordenada2 = dados["coord"]["lat"]
        # --- NOVO BLOCO DE CÓDIGO PARA HORA CORRETA ---
        agora_utc = datetime.now(timezone.utc)
        fuso_horario_brasil = ZoneInfo("America/Sao_Paulo")
        agora_brasil = agora_utc.astimezone(fuso_horario_brasil)
        horario = agora_brasil.strftime("%Y-%m-%d %H:%M:%S")
        # --- FIM DO NOVO BLOCO ---

        # Conversão para horário local
        sunrise_local = datetime.utcfromtimestamp(sunrise_utc + timezone_offset).strftime("%H:%M:%S")
        sunset_local = datetime.utcfromtimestamp(sunset_utc + timezone_offset).strftime("%H:%M:%S")

        # fotoperíodo
        # Cálculo do fotoperíodo
        fotoperiodo_segundos = sunset_utc - sunrise_utc
        horas = fotoperiodo_segundos // 3600
        minutos = (fotoperiodo_segundos % 3600) // 60
        fotoperiodo_str = f"{horas}h {minutos}min"

        # Exibir no Streamlit

        st.subheader("Condições climáticas Hoje")
        st.write(f"🌅 Nascer do sol: {sunrise_local}")
        st.write(f"🌇 Pôr do sol: {sunset_local}")
        st.write(f'🕒Fotoperíodo: {fotoperiodo_str}')
        st.write(f'☁️ Nuvens: {nuvens}')
        st.write(f'📍Latitude: {coordenada}')
        st.write(f'🧭 Longitude: {coordenada2}')
        st.write(f'📍 País: {paisBR}')
        st.write(f'📍Cidade: {cidade}')



        #st.write(dados)

        registro = {"horario": [horario], "temperatura": [temperatura], "umidade": [umidade], 'sunrise':[sunrise_local], 'sunset':[sunset_local], 'fotoperiodo':[fotoperiodo_str] }
        df = pd.DataFrame(registro)
        dfv = df.copy()
        #st.write(dfv)
        #calculo do DPV
        dfv['es'] = 0.6108*math.exp((17.27*temperatura)/(temperatura+273.15))
        #st.write(dfv)
        dfv['ea'] = (umidade/100)*dfv['es']
        dfv['dpv'] = dfv['es'] - dfv['ea']

        #st.write(dfv)

        #armazenar em csv:
        append_row_to_sheet(gc, SHEET_NAME, dfv)
        #st.success("✅ Dados coletados automaticamente")
        #st.dataframe(dfv)


        #st.write(f"Temperatura atual: {temperatura} °C")
        #st.write(f'DATA: {horario}')
        #st.write(f"Umidade atual: {umidade}%")
    else:
        st.write(f'Erro na aquisição {resposta.status_code}')



# Exibir gráfico com histórico
    df_hist = load_data_from_sheet(gc, SHEET_NAME)# Conexão
    if not df_hist.empty:
        # --- BLOCO DE CONVERSÃO ---
        colunas_numericas = ['temperatura', 'umidade', 'es', 'ea', 'dpv']
        for col in colunas_numericas:
            df_hist[col] = pd.to_numeric(df_hist[col], errors='coerce')
        # --- FIM DO BLOCO ---
        df_hist["horario"] = pd.to_datetime(df_hist["horario"])
        df_hist = df_hist.sort_values(by="horario")
        #st.dataframe(df_hist)
        #Gráfico de temperatura
        st.subheader('Gráfico de temperatura 📈')
        fig1 = px.line(df_hist, x = 'horario', y = ['temperatura'], title = 'Temperatura')
        fig1.update_layout( yaxis_title = 'Temperatura (°C)', xaxis_title_text = 'Tempo (horas)',  legend_title_text='Variáveis')
        st.plotly_chart(fig1)
        #st.line_chart(df_hist.set_index("horário")[["temperatura"]])
        #Gráfico umidade
        st.subheader('Gráfico de umidade 💧')
        fig2 = px.line(df_hist, x='horario', y='umidade', title='Umidade')
        fig2.update_layout(yaxis_title = 'UR (%)', xaxis_title_text = 'Tempo (horas)')
        st.plotly_chart(fig2)


        st.subheader('Gráfico de DPV')
        fig13 = px.line(df_hist, x='horario', y='dpv', title='DPV')
        fig13.update_layout(yaxis_title = 'DPV (kPa)', xaxis_title_text = 'Tempo (horas)')

        st.plotly_chart(fig13)


        st.subheader('Gráfico de T, UR e DPV')
        fig4 = px.line(df_hist, x = 'horario', y = ['temperatura', 'umidade', 'dpv' ], title='intersecção')
        fig4.update_layout(
            yaxis_title='Valores',
            xaxis_title_text='Horário',
            legend_title_text='Variáveis'
        )
        st.plotly_chart(fig4)
        st.subheader('Análise diária de variáveis: Temperatura, UR, DPV e Fotoperíodo')


        #st.line_chart(df_hist.set_index('horário')['umidade'])
        st.dataframe(df_hist)




#Essa segunda parte é para que haja a leitura dos dados brutos da primeira parte
with tab2:
    # Passo 1: Conectar ao Google Sheets (exatamente como na tab1)
    gc = connect_to_sheet()
    if gc is None:
        st.stop()

    # Passo 2: Ler os dados brutos da planilha (A única grande mudança!)
    dfv3 = load_data_from_sheet(gc, SHEET_NAME)

    if not dfv3.empty:
        # --- BLOCO DE CONVERSÃO ---
        colunas_numericas = ['temperatura', 'umidade', 'es', 'ea', 'dpv']
        for col in colunas_numericas:
            dfv3[col] = pd.to_numeric(dfv3[col], errors='coerce')
        # --- FIM DO BLOCO --


        dfv2 = dfv3.copy()#crítico
        dfv2['horario'] = pd.to_datetime(dfv2['horario'])
        dfv2['data'] = dfv2["horario"].dt.date #vou deletar o horário

        # Novo sistema de agreagação:


        st.subheader('Parâmetros após fechamento dos dias')
        grupo_por_data = dfv2.groupby('data')
        #1.1Temperatura média
        temperatura_media = grupo_por_data['temperatura'].mean()
        #st.write(temperatura_media)
        #1.2Temperatura Mínima
        temperatura_minima = grupo_por_data['temperatura'].min()
        #st.write(temperatura_minina)
        #1.3Temperatura máxima
        temperatura_maxima = grupo_por_data['temperatura'].max()
        amplitude_termica = temperatura_maxima - temperatura_minima
        #st.write(amplitude_termica)
        #2.1: Umidade média
        umidade_media = grupo_por_data['umidade'].mean()
        #st.write(umidade_media)
        #2.2: Umidade mínima:
        umidade_minima = grupo_por_data['umidade'].min()
        umidade_maxima = grupo_por_data['umidade'].max()

        #3.1 DPV:
        dpv_medio = grupo_por_data['dpv'].mean()
        dpv_minimo = grupo_por_data['dpv'].min()
        dpv_maxima = grupo_por_data['dpv'].max()
        #4.0 amplitude

        #Nascer do sol:
        sunset = grupo_por_data['sunset'].first()#1 unidade
        #st.write(sunset)
        sunrise = grupo_por_data['sunrise'].first()
        fotoperiodo = grupo_por_data['fotoperiodo'].first()
        data = grupo_por_data['data'].first()
        #st.write(fotoperiodo)
        #Está tudo em dicionário, vou passar para o Dataframe o dicionário:
        resumo_final = pd.DataFrame({ 'temperatura_media':temperatura_media,'temperatura_maxima' :temperatura_maxima,
                                    'temperatura_minima': temperatura_minima, 'amplitude_termica': amplitude_termica,
                                     'umidade_media':umidade_media, 'umidade_minima':umidade_minima,'umidade_maxima':umidade_maxima,
                                     'dpv_medio':dpv_medio,'dpv_maxima':dpv_maxima,'dpv_minimo':dpv_minimo, 'sunset':sunset,'sunrise':sunrise, 'fotoperiodo':fotoperiodo}).reset_index()# fa com que a data que era índice vire coluna



        st.write(resumo_final)

        #Essa parte é a  análise descritiva resumidas em gráfico

        fig_resumoT = px.line(resumo_final, x='data', y=['temperatura_media', 'temperatura_maxima','temperatura_minima', 'amplitude_termica' ], title='Temperatura média por data')
        fig_resumoT.update_layout(
            yaxis_title='Temperatura média (°C)',
            xaxis_title_text='Tempo (dias)',
            legend_title_text='Variáveis'
        )
        st.plotly_chart(fig_resumoT)
        #2. média de umidade:

        #st.write(media_por_dataU)
        fig_resumo2 = px.line(resumo_final, x='data', y='umidade_media', title='UR  média por data')

        fig_resumo2.update_layout(
            yaxis_title='UR média  (%)',
            xaxis_title_text='Tempo (dias)',
            legend_title_text='Variáveis'
        )
        st.plotly_chart(fig_resumo2)

        #3 Média de de DPV:

        # st.write(media_por_dataU)
        fig_resumo3 = px.line(resumo_final, x='data', y='dpv_medio', title='DPV média por data')

        fig_resumo3.update_layout(
            yaxis_title= 'DPV (kPa)',
            xaxis_title_text='Tempo (dias)',
            legend_title_text='Variáveis'
        )
        st.plotly_chart(fig_resumo3)
        #4. Média do DPV


        fig_resumo4 = px.line(resumo_final, x='data', y='fotoperiodo', title='Fotoperíodo ao longo dos dias')
        fig_resumo4.update_layout(
            yaxis_title='Fotoperíodo (Horas)',
            xaxis_title_text='Tempo (data)',
            legend_title_text='Variáveis'
        )
        st.plotly_chart(fig_resumo4)
        #5# gráfico de umidade relativa, temperatura e DPV


        #st.write(media_por_data4)

        #Fazendo o gráfico completo
        fig5 = px.line(resumo_final, x='data', y=[ 'temperatura_media','umidade_media', 'dpv_medio', 'amplitude_termica'], title='T X UR X DPV')
        fig5.update_layout(
            yaxis_title='Valores',
            xaxis_title_text='Tempo (data)',
            legend_title_text='Variáveis'
        )
        st.plotly_chart(fig5)


# Pegando os dados de radiação solar no API da NASA==================================================================================
#==================Dados pego da NASA

#Coordanada de viçosa:
latitude = -20.7573491
longitude = -42.8728688

intervaloR = st.date_input('Selecione o intervalo de datas', value =(date.today(), date.today()), min_value=date(2024, 1,1), max_value= date.today())
#st.write(intervaloR)
start_str = intervaloR[0].strftime("%Y%m%d")# Transformo da data aceita pelo API = YYYMMMDD
end_str = intervaloR[1].strftime("%Y%m%d")
api_key2 = url = f"https://power.larc.nasa.gov/api/temporal/daily/point?parameters=ALLSKY_SFC_SW_DWN&community=AG&longitude={longitude}&latitude={latitude}&start={start_str}&end={end_str}&format=JSON&api_key={'e5V2DHHi2CGVqC4AaQBauERidB5oGvf6lrBhH8Qj'}"

response2 = requests.get(url=api_key2)

if response2.status_code == 200:# Se não der erro na aquisição dos dados, então (implicação material)
    data2 = response2.json()# vai ser transformado em dicionário
    #st.write(data2)
    #
    valores2 = data2["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]# Radiaçaõ solar global diária
    #precip = data2["properties"]["parameter"]["PRECTOT"]


    #st.write(valores2)
    dfR = pd.DataFrame(valores2, index = [0])
    df2R = pd.DataFrame(list(valores2.items()), columns=["Data","ALLSKY_SFC_SW_DWN" ])# Como é um dicionário, então os valores 2 pegam esses ítens
    #Trandformar o Data para o padrão brasileiro
    df2R['Data'] = pd.to_datetime(df2R['Data'], format = '%Y%m%d')# Conversão em formato de data
    #Conversão para o braseileiro:
    df2R['Data'] = df2R['Data'].dt.strftime('%d/%m/%Y')


    #Vai salvar os dados climáticos
    dfvR12 = df2R.to_csv("dados_climaticosRadiação.csv")
    #Vai exibir o que foi salvo em Data Frame
    df_histR = pd.read_csv("dados_climaticosRadiação.csv")

    st.subheader('Tabela histórica da Radiação global diária')
    st.write(df_histR)
    #vai mostrar o DataFrame em gráfico
    fig5R = px.line(df_histR, x='Data', y='ALLSKY_SFC_SW_DWN', title='Radiação global diária')#MJ m⁻² dia⁻¹
    fig5R.update_layout(
        yaxis_title='Radiação global diária (MJ m⁻² dia⁻¹)',
        xaxis_title_text='Tempo (data)',
        legend_title_text='Variáveis'
    )
    st.plotly_chart(fig5R)
else:
    st.write('Erro na aquisição')

#Quero pegar dados de precipitação agora: Utilzando do mesmo api da NASA===========================================================================
#Coordanada de viçosa:
latitude = -20.7573491
longitude = -42.8728688

st.subheader('Dados de precipitação histórica em  mm(dia)')

intervaloP = st.date_input('Selecione o intervalo de datas', value =(date.today(), date.today()), min_value=date(2020, 1,1), max_value= date.today(), key = 'ppt_1')

#st.write(intervaloR)
start_str2 = intervaloP[0].strftime("%Y%m%d")# Transformo da data aceita pelo API = YYYMMMDD
end_str2 = intervaloP[1].strftime("%Y%m%d")
api_key3 = url = f"https://power.larc.nasa.gov/api/temporal/daily/point?parameters=PRECTOTCORR&community=AG&longitude={longitude}&latitude={latitude}&start={start_str2}&end={end_str2}&format=JSON&api_key={'e5V2DHHi2CGVqC4AaQBauERidB5oGvf6lrBhH8Qj'}"

response3 = requests.get(url=api_key3)
if response3.status_code == 200:
    precip = response3.json()
    #st.write(precip)
    valores3 = precip['properties']['parameter']["PRECTOTCORR"]
    #st.write(valores3)
    # st.write(valores2)
    #dfR = pd.DataFrame(valores2, index=[0])
    #df2R = pd.DataFrame(list(valores2.items()), columns=["Data","ALLSKY_SFC_SW_DWN"])  # Como é um dicionário, então os valores 2 pegam esses ítens
    #dfP = pd.DataFrame(valores3, index = [0])
    #st.write(dfP)
    dfP2 = pd.DataFrame(list(valores3.items()), columns=["Data","Precipitação"])
    #st.write(dfP2)
    #conversão para dattatime
    dfP2['Data'] = pd.to_datetime(dfP2['Data'], format='%Y%m%d')  # Conversão em formato de data
    # Conversão para o brasileiro:
    dfP2['Data'] = dfP2['Data'].dt.strftime('%d/%m/%Y')
    #Consertando a data para as datas atuais que nos importa:
    st.write(dfP2)
    #gráfico  de precipitação:
    st.subheader('Gráfico de PPT')
    fig19 = px.line(dfP2, x='Data', y='Precipitação', title='Gráfico de precipitação (mm/dia), Dados Nasa')
    fig19.update_layout(yaxis_title='Precipitação (mm/dia)', xaxis_title_text='Tempo (dias)')

    st.plotly_chart(fig19)
















        # st.dataframe(dfv)


