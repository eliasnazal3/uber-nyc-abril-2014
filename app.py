import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(page_title="Recogidas de Uber · Nueva York", layout="wide")

ARCHIVO = Path(__file__).parent / "data" / "uber_abril_2014.csv"
if not ARCHIVO.is_file():
    ARCHIVO = ARCHIVO.with_suffix(".csv.gz")
CAMPOS = ["Date/Time", "Lat", "Lon", "Base"]
COLORES = {
    "B02512": "#9D4B45", "B02598": "#466CA6", "B02617": "#9A650A",
    "B02682": "#087970", "B02764": "#785D9D",
}
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
CENTRO = {"lat": 40.73, "lon": -73.97}
SEMILLA = 42
MAX_PUNTOS = 10_000


def entero(numero):
    return f"{numero:,.0f}".replace(",", ".")


def porcentaje(numero):
    return f"{numero:.2f}".replace(".", ",") + " %"


@st.cache_data
def fondo_incluido():
    ruta = ARCHIVO.parent / "fondo_nyc.json"
    return json.loads(ruta.read_text(encoding="utf-8"))


@st.cache_data(show_spinner="Cargando las recogidas de abril…")
def cargar_datos(ruta):
    datos = pd.read_csv(ruta, usecols=CAMPOS)
    datos["Date/Time"] = pd.to_datetime(datos["Date/Time"], format="%m/%d/%Y %H:%M:%S", errors="coerce")
    datos["Lat"] = pd.to_numeric(datos["Lat"], errors="coerce")
    datos["Lon"] = pd.to_numeric(datos["Lon"], errors="coerce")
    datos["Base"] = datos["Base"].astype("string").str.strip().replace("", pd.NA)
    coordenadas_nulas = datos[["Lat", "Lon"]].isna().any(axis=1)
    coordenadas_cero = (datos["Lat"] == 0) | (datos["Lon"] == 0)
    fuera_de_rango = (datos["Lat"].abs() > 90) | (datos["Lon"].abs() > 180)
    coord_invalida = coordenadas_nulas | coordenadas_cero | fuera_de_rango
    en_abril = (datos["Date/Time"] >= "2014-04-01") & (datos["Date/Time"] < "2014-05-01")
    validos = ~coord_invalida & en_abril & datos["Base"].notna()
    calidad = {
        "Filas leídas": len(datos),
        "Coordenadas nulas o ilegibles": int(coordenadas_nulas.sum()),
        "Coordenadas en cero": int(coordenadas_cero.sum()),
        "Coordenadas fuera del rango mundial": int(fuera_de_rango.sum()),
        "Filas con coordenada inválida": int(coord_invalida.sum()),
        "Fechas inválidas o fuera de abril": int((~en_abril).sum()),
        "Bases ausentes": int(datos["Base"].isna().sum()),
        "Filas excluidas en total": int((~validos).sum()),
    }
    datos = datos.loc[validos].copy()
    calidad["Repeticiones exactas adicionales conservadas"] = int(datos.duplicated(CAMPOS).sum())
    datos["Base"] = datos["Base"].astype("category")
    datos["Fecha"] = datos["Date/Time"].dt.normalize()
    datos["Hora"] = datos["Date/Time"].dt.hour
    return datos, calidad


def mostrar(figura, clave, alto):
    figura.update_layout(
        height=alto, template="plotly_white", separators=",.",
        font=dict(family="Arial, sans-serif", size=13, color="#183342"),
        title_font=dict(size=18, color="#183342"),
        paper_bgcolor="white", margin=dict(l=24, r=24, t=54, b=45),
        hoverlabel=dict(font_size=13),
    )
    st.plotly_chart(figura, key=clave, theme=None, use_container_width=True,
                    config={"displaylogo": False, "responsive": True})


st.title("Recogidas de Uber en Nueva York")
st.write("¿Dónde y a qué horas se concentran las recogidas registradas de cada base en abril de 2014?")

datos, calidad = cargar_datos(ARCHIVO)
if datos.empty:
    st.warning("El archivo no contiene registros que cumplan los criterios de abril.")
    st.stop()

todas_bases = sorted(datos["Base"].cat.categories.tolist())
inicio_mes = pd.Timestamp("2014-04-01").date()
fin_mes = pd.Timestamp("2014-04-30").date()

with st.sidebar:
    st.header("Filtros de abril")
    bases = st.multiselect("Bases", todas_bases, default=todas_bases, key="bases")
    fechas = st.date_input("Periodo", value=(inicio_mes, fin_mes), min_value=inicio_mes,
                           max_value=fin_mes, format="DD/MM/YYYY", key="fechas")
    horas = st.slider("Horas de recogida", 0, 23, (0, 23), key="horas",
                      help="Incluye las dos horas indicadas.")
    st.caption("Los filtros se aplican a los indicadores, los gráficos y los mapas.")
    st.divider()
    st.caption("Visualización de la Información · Beta 2.1.0")

if len(fechas) != 2:
    st.info("Completa el periodo seleccionando la fecha final.")
    st.stop()

desde, hasta = fechas
seleccion = datos.loc[
    datos["Base"].isin(bases)
    & datos["Fecha"].between(pd.Timestamp(desde), pd.Timestamp(hasta))
    & datos["Hora"].between(horas[0], horas[1])
]
if seleccion.empty:
    st.warning("La selección contiene 0 registros. Agrega una base o amplía el periodo y las horas.")
    st.stop()

calendario = pd.date_range(desde, hasta, name="Fecha")
diario = seleccion.groupby("Fecha").size().reindex(calendario, fill_value=0).rename("Registros").reset_index()
por_base = seleccion.groupby("Base", observed=True).size().sort_values(ascending=False).rename("Registros").reset_index()
total = len(seleccion)
por_base["Porcentaje"] = por_base["Registros"] / total * 100
pico = diario.loc[diario["Registros"].idxmax()]
diferencia = total - len(datos)
delta = "0 frente a abril" if diferencia == 0 else f"-{entero(abs(diferencia))} frente a abril"

st.caption(f"{desde:%d/%m} a {hasta:%d/%m} de 2014 · {horas[0]:02d}:00 a {horas[1]:02d}:59 · "
           f"{porcentaje(100 * total / len(datos))} de los registros del mes")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Recogidas registradas", entero(total), delta=delta, delta_color="off", border=True, height=130)
k2.metric("Bases con registros", str(len(por_base)), border=True, height=130)
k3.metric("Promedio por fecha", entero(diario["Registros"].mean()), border=True, height=130,
          help="Registros divididos por los días del periodo, incluidos los días con cero.")
k4.metric(f"Máximo diario · {pico['Fecha']:%d/%m}", entero(pico["Registros"]), border=True, height=130,
          help="Si hay empate, se muestra la primera fecha del periodo con ese máximo.")

seccion = st.radio("Sección", ["Actividad", "Mapas", "Datos y método"],
                   horizontal=True, key="seccion", label_visibility="collapsed")

if seccion == "Actividad":
    fig = px.line(diario, x="Fecha", y="Registros", markers=True,
                  title="Recogidas por fecha", labels={"Registros": "Recogidas (n)", "Fecha": "Fecha de abril"},
                  color_discrete_sequence=["#087970"])
    fig.update_traces(line_width=3, marker_size=6,
                      hovertemplate="%{x|%d/%m/%Y}<br>Recogidas: %{y:,.0f}<extra></extra>")
    fig.update_xaxes(tickformat="%d/%m")
    if len(diario) == 1:
        fig.update_xaxes(tickmode="array", tickvals=diario["Fecha"].tolist())
    fig.update_yaxes(rangemode="tozero")
    mostrar(fig, "serie_diaria", 310)

    izquierda, derecha = st.columns([1, 1.6])
    with izquierda:
        fig = px.bar(por_base, x="Registros", y="Base", color="Base", orientation="h",
                     title="Recogidas por base", color_discrete_map=COLORES,
                     labels={"Registros": "Recogidas (n)", "Base": "Código de base"},
                     custom_data=["Porcentaje"])
        fig.update_layout(showlegend=False)
        fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(por_base["Base"].tolist())))
        fig.update_traces(hovertemplate="Base %{y}<br>Recogidas: %{x:,.0f}<br>De la selección: %{customdata[0]:.2f} %<extra></extra>")
        mostrar(fig, "frecuencias_base", 330)
    with derecha:
        conteos = seleccion.groupby(["Fecha", "Hora"]).size().unstack(fill_value=0)
        conteos = conteos.reindex(index=calendario, columns=range(horas[0], horas[1] + 1), fill_value=0)
        perfil = conteos.groupby(conteos.index.dayofweek).mean()
        perfil.index = [DIAS[i] for i in perfil.index]
        fig = px.imshow(perfil, aspect="auto", title="Promedio por día y hora",
                        labels={"x": "Hora de recogida (h)", "y": "Día de la semana", "color": "Recogidas por fecha (n)"},
                        color_continuous_scale=["#F2F5ED", "#BADFD0", "#63B3A6", "#197E77", "#154350"],
                        zmin=0)
        fig.update_xaxes(side="bottom", dtick=2 if horas[1] - horas[0] > 15 else 1)
        fig.update_traces(hovertemplate="%{y}, %{x}:00 h<br>Promedio: %{z:,.1f} recogidas por fecha<extra></extra>")
        fig.update_layout(coloraxis_colorbar=dict(title="Media", thickness=10, len=0.78))
        mostrar(fig, "perfil_semanal", 330)
    principal = por_base.iloc[0]
    st.write(f"La base {principal['Base']} reúne {entero(principal['Registros'])} registros "
             f"({porcentaje(principal['Porcentaje'])} de la selección). "
             f"El {pico['Fecha']:%d/%m} alcanza {entero(pico['Registros'])} recogidas registradas.")

elif seccion == "Mapas":
    vista, cartografia = st.columns(2)
    modo = vista.radio("Vista del mapa", ["Puntos por base", "Densidad"], horizontal=True, key="vista")
    fondo = cartografia.selectbox("Fondo del mapa", ["Distritos y vías principales", "Calles detalladas en línea"])
    estilo = fondo_incluido() if fondo == "Distritos y vías principales" else "streets"
    if total > MAX_PUNTOS:
        muestra = seleccion.sample(n=MAX_PUNTOS, random_state=SEMILLA)
        st.caption(f"Muestra aleatoria de 10.000 de {entero(total)} registros filtrados · Semilla 42")
    else:
        muestra = seleccion
        st.caption(f"Se muestran los {entero(total)} registros filtrados.")
    dentro = muestra["Lat"].between(40.71, 40.80) & muestra["Lon"].between(-74.01, -73.95)
    en_zona = int(dentro.sum())
    fuera = len(muestra) - en_zona
    opciones = dict(lat="Lat", lon="Lon", center=CENTRO, zoom=10, map_style=estilo,
                    hover_name="Base", hover_data={"Date/Time": "|%d/%m/%Y %H:%M", "Lat": ":.4f", "Lon": ":.4f"},
                    labels={"Base": "Base", "Lat": "Latitud (°)", "Lon": "Longitud (°)", "Date/Time": "Recogida"})
    if modo == "Puntos por base":
        fig = px.scatter_map(muestra, color="Base", color_discrete_map=COLORES,
                             category_orders={"Base": todas_bases}, opacity=0.55,
                             title="Ubicación de las recogidas", **opciones)
        fig.update_traces(marker_size=6)
        fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.02))
    else:
        fig = px.density_map(muestra, radius=15, opacity=0.65, title="Concentración espacial",
                             color_continuous_scale=["#293E89", "#6870BA", "#BE7191", "#F29B52", "#FFDC62"],
                             **opciones)
        fig.update_layout(coloraxis_colorbar=dict(title="Intensidad", thickness=13))
    mostrar(fig, "mapa_puntos" if modo == "Puntos por base" else "mapa_densidad", 525)
    if modo == "Puntos por base":
        st.write(f"Cada punto ubica una recogida y su color identifica la base. "
                 f"{entero(en_zona)} de los {entero(len(muestra))} registros dibujados "
                 f"están en la zona de referencia y {entero(fuera)} quedan fuera.")
    else:
        st.write(f"El calor aumenta donde se agrupan puntos cercanos. La zona de referencia contiene "
                 f"{porcentaje(100 * en_zona / len(muestra))} de los registros dibujados. "
                 "Los tonos cálidos indican mayor concentración. El radio y el zoom cambian la intensidad visible.")
    st.caption("Zona de referencia del Certamen 2: latitud 40,71° a 40,80° y longitud −74,01° a −73,95°. "
               "La cobertura del archivo limita lo que podemos inferir sobre la demanda de la ciudad.")
    if fondo == "Distritos y vías principales":
        st.caption("Fondo incluido: NYC Department of City Planning (distritos) y U.S. Census Bureau, TIGER/Line 2014 (vías).")
    else:
        st.caption("Cartografía en línea: CARTO y colaboradores de OpenStreetMap. Si no carga, elige el fondo incluido.")

else:
    st.subheader("Calidad del archivo de abril")
    st.write(f"Se conservaron {entero(len(datos))} registros válidos, incluidas "
             f"{entero(calidad['Repeticiones exactas adicionales conservadas'])} repeticiones adicionales "
             "de los cuatro campos. El archivo carece de identificador único de viaje.")
    st.write(f"Coordenadas inválidas excluidas: {entero(calidad['Filas con coordenada inválida'])}. "
             "La validación comprueba los límites mundiales, los ceros y los valores ausentes.")
    with st.expander("Ver los controles del archivo completo"):
        st.table(pd.DataFrame({"Control": list(calidad), "Filas": [entero(n) for n in calidad.values()]}))
    with st.expander(f"Ver tabla de la selección ({entero(total)} filas)"):
        tamano = 100
        paginas = (total + tamano - 1) // tamano
        pagina = st.number_input("Página de 100 filas", min_value=1, max_value=paginas, value=1, step=1)
        inicio = (pagina - 1) * tamano
        filas = seleccion.iloc[inicio:inicio + tamano][CAMPOS].rename(columns={
            "Date/Time": "Fecha y hora", "Lat": "Latitud (°)", "Lon": "Longitud (°)",
        })
        st.caption(f"Filas {entero(inicio + 1)} a {entero(min(inicio + tamano, total))} de {entero(total)}.")
        st.dataframe(filas, hide_index=True, width="stretch")
    st.caption("Fuente: CSV corregido del Certamen 2. Recogidas de abril de 2014, FiveThirtyEight / NYC TLC.")
