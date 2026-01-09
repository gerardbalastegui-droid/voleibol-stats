# 🏐 Voleibol Stats - Aplicación Web

Sistema de estadísticas de voleibol con interfaz web interactiva usando Streamlit.

## 📋 Características

- **📊 Informes de Partido**: Estadísticas completas con gráficos interactivos
- **👤 Análisis de Jugador**: Perfil individual con radar y métricas
- **📈 Comparativas**: Compara el rendimiento entre partidos
- **🏆 Rankings**: Top anotadores con visualización de podio

## 🚀 Instalación

### 1. Requisitos previos
- Python 3.9+
- PostgreSQL con tu base de datos de voleibol

### 2. Instalar dependencias

```bash
cd voleibol_app
pip install -r requirements.txt
```

### 3. Configurar base de datos

Edita la conexión en `app.py` (línea ~60):

```python
return create_engine(
    "postgresql+psycopg2://usuario:contraseña@localhost:5432/voleibol"
)
```

### 4. Ejecutar la aplicación

```bash
streamlit run app.py
```

La app se abrirá automáticamente en `http://localhost:8501`

## 📱 Uso

1. **Selecciona el contexto** en el menú lateral:
   - Equipo
   - Temporada
   - Fase (opcional)

2. **Navega** entre las secciones:
   - 🏠 Inicio: Resumen general
   - 📊 Partit: Análisis de un partido específico
   - 👤 Jugador: Estadísticas individuales
   - 📈 Comparativa: Compara dos partidos

## 🛠️ Estructura del Proyecto

```
voleibol_app/
├── app.py              # Aplicación principal
├── requirements.txt    # Dependencias
└── README.md          # Este archivo
```

## 🔧 Personalización

### Colores del club
Edita las variables al inicio de `app.py`:

```python
COLOR_ROJO = "#C8102E"
COLOR_AMARILLO = "#F4D000"
# etc.
```

### Añadir nuevas páginas
1. Crea una función `pagina_nueva()` siguiendo el patrón existente
2. Añádela al routing en `main()`
3. Añade la opción en `sidebar_contexto()`

## 📊 Base de Datos Esperada

La app espera estas tablas:
- `equipos`: id, nombre, equipo_letra
- `temporadas`: id, nombre, activa
- `fases`: id, nombre, temporada_id
- `jugadores`: id, apellido, nombre, dorsal, posicion, equipo_id, activo
- `partidos_new`: id, rival, local, fecha, resultado, equipo_id, temporada_id, fase_id
- `acciones_new`: id, partido_id, jugador_id, tipo_accion, marca, zona, rotacion

## 🌐 Despliegue

### Opción 1: Streamlit Cloud (Gratuito)
1. Sube el código a GitHub
2. Ve a [share.streamlit.io](https://share.streamlit.io)
3. Conecta tu repo
4. Configura los secrets para la BD

### Opción 2: Servidor propio
```bash
streamlit run app.py --server.port 80 --server.address 0.0.0.0
```

## 📝 Notas

- Los datos se cachean 5 minutos para mejor rendimiento
- Compatible con móvil (diseño responsive)
- Gráficos interactivos con Plotly (zoom, pan, export)

---

Desarrollado para el club 🏐
