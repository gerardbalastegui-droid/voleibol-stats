# -*- coding: utf-8 -*-
"""
config_v2.py
Configuración para trabajar con la NUEVA ESTRUCTURA de base de datos
(equipos, temporadas, fases, jugadores con IDs)
"""
import os
from sqlalchemy import create_engine, text
import matplotlib
matplotlib.use("Agg")  # backend sense pantalla (per a Railway)
import matplotlib.pyplot as plt
try:
    import seaborn as sns
except Exception:
    sns = None

# -----------------------------
# COLORES DEL CLUB
# -----------------------------
COLOR_ROJO = "#C8102E"
COLOR_BLANCO = "#FFFFFF"
COLOR_NEGRO = "#000000"
COLOR_AMARILLO = "#F4D000"
COLOR_GRIS = "#F2F2F2"
COLOR_VERDE = "#4CAF50"
COLOR_NARANJA = "#FF9800"

# -----------------------------
# CONFIGURACIÓN DE PÁGINA
# -----------------------------
A4_H = (11.69, 8.27)

# -----------------------------
# CARPETA DE INFORMES
# -----------------------------
CARPETA_INFORMES = os.environ.get(
    "CARPETA_INFORMES",
    r"C:\Users\Usuario\Desktop\voleibol_import\Informes"
)
try:
    os.makedirs(CARPETA_INFORMES, exist_ok=True)
except Exception:
    pass

# -----------------------------
# CONFIGURACIÓN DE BASE DE DATOS
# -----------------------------
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:navi6573@localhost:5432/voleibol"
)
engine = create_engine(DB_URL)

# -----------------------------
# CONFIGURACIÓN DE MATPLOTLIB
# -----------------------------
if sns is not None:
    sns.set_style("whitegrid")
plt.rcParams.update({'figure.figsize': A4_H})

# -----------------------------
# NOMBRES DE TABLAS NUEVAS
# -----------------------------
TABLA_EQUIPOS = "equipos"
TABLA_TEMPORADAS = "temporadas"
TABLA_FASES = "fases"
TABLA_JUGADORES = "jugadores"
TABLA_PARTIDOS = "partidos_new"
TABLA_ACCIONES = "acciones_new"

# -----------------------------
# CONSTANTES DE ZONAS
# -----------------------------
ZONAS_TABLA = [
    ["p5", "p4"],
    ["p6", "p3"],
    ["p1", "p2"]
]

ORDEN_ROTACIONES = [
    ["p4", "p3", "p2"],
    ["p5", "p6", "p1"]
]

# -----------------------------
# RENOMBRADO DE COLUMNAS
# -----------------------------
RENOMBRAR_COLUMNAS = {
    "jugador_apellido": "Jugador",
    "total": "Total",
    "eficacia_pct": "Eficacia (%)",
    "eficiencia_pct": "Eficiencia (%)",
}

# -----------------------------
# CONTEXTO GLOBAL (Se establece al inicio)
# -----------------------------
import json

class ContextoGlobal:
    """Mantiene el contexto actual de trabajo (equipo, temporada, fase)"""
    
    ARCHIVO_CONTEXTO = os.path.join(os.path.dirname(__file__), "contexto.json")
    
    def __init__(self):
        self.equipo_id = None
        self.equipo_nombre = None
        self.temporada_id = None
        self.temporada_nombre = None
        self.fase_id = None
        self.fase_nombre = None
        
        # Cargar contexto guardado si existe
        self.cargar_contexto()
    
    def establecer_contexto(self, equipo_id, equipo_nombre, temporada_id, temporada_nombre, fase_id=None, fase_nombre=None):
        """Establece el contexto de trabajo y lo guarda"""
        self.equipo_id = equipo_id
        self.equipo_nombre = equipo_nombre
        self.temporada_id = temporada_id
        self.temporada_nombre = temporada_nombre
        self.fase_id = fase_id
        self.fase_nombre = fase_nombre
        
        # Guardar en archivo
        self.guardar_contexto()
    
    def guardar_contexto(self):
        """Guarda el contexto actual en un archivo JSON"""
        datos = {
            'equipo_id': self.equipo_id,
            'equipo_nombre': self.equipo_nombre,
            'temporada_id': self.temporada_id,
            'temporada_nombre': self.temporada_nombre,
            'fase_id': self.fase_id,
            'fase_nombre': self.fase_nombre
        }
        
        try:
            with open(self.ARCHIVO_CONTEXTO, 'w', encoding='utf-8') as f:
                json.dump(datos, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  No se pudo guardar el contexto: {e}")
    
    def cargar_contexto(self):
        """Carga el contexto desde el archivo JSON"""
        if not os.path.exists(self.ARCHIVO_CONTEXTO):
            return
        
        try:
            with open(self.ARCHIVO_CONTEXTO, 'r', encoding='utf-8') as f:
                datos = json.load(f)
            
            self.equipo_id = datos.get('equipo_id')
            self.equipo_nombre = datos.get('equipo_nombre')
            self.temporada_id = datos.get('temporada_id')
            self.temporada_nombre = datos.get('temporada_nombre')
            self.fase_id = datos.get('fase_id')
            self.fase_nombre = datos.get('fase_nombre')
        except Exception as e:
            print(f"⚠️  No se pudo cargar el contexto: {e}")
    
    def limpiar_contexto(self):
        """Limpia el contexto actual"""
        self.equipo_id = None
        self.equipo_nombre = None
        self.temporada_id = None
        self.temporada_nombre = None
        self.fase_id = None
        self.fase_nombre = None
        
        # Eliminar archivo
        if os.path.exists(self.ARCHIVO_CONTEXTO):
            os.remove(self.ARCHIVO_CONTEXTO)
    
    def obtener_filtro_sql(self):
        """Devuelve el filtro SQL para queries"""
        filtros = []
        params = {}
        
        if self.equipo_id:
            filtros.append("p.equipo_id = :equipo_id")
            params['equipo_id'] = self.equipo_id
        
        if self.temporada_id:
            filtros.append("p.temporada_id = :temporada_id")
            params['temporada_id'] = self.temporada_id
        
        if self.fase_id:
            filtros.append("p.fase_id = :fase_id")
            params['fase_id'] = self.fase_id
        
        return (" AND " + " AND ".join(filtros), params) if filtros else ("", {})
    
    def mostrar_contexto(self):
        """Muestra el contexto actual"""
        print("\n" + "="*60)
        print("   CONTEXT ACTUAL DE TREBALL")
        print("="*60)
        if self.equipo_nombre:
            print(f"📋 Equip: {self.equipo_nombre}")
        else:
            print(f"📋 Equip: (no configurat)")
        
        if self.temporada_nombre:
            print(f"📅 Temporada: {self.temporada_nombre}")
        else:
            print(f"📅 Temporada: (no configurada)")
        
        if self.fase_nombre:
            print(f"🏆 Fase: {self.fase_nombre}")
        else:
            print(f"🏆 Fase: (totes les fases)")
        print("="*60)

# Instancia global del contexto
contexto = ContextoGlobal()

# -----------------------------
# FUNCIONES DE UTILIDAD
# -----------------------------

def obtener_equipo_activo():
    """Devuelve el ID del equipo activo o None"""
    return contexto.equipo_id

def obtener_temporada_activa():
    """Devuelve el ID de la temporada activa"""
    with engine.connect() as conn:
        resultado = conn.execute(text("""
        SELECT id, nombre FROM temporadas WHERE activa = true LIMIT 1
        """)).fetchone()
        
        if resultado:
            return resultado[0], resultado[1]
        return None, None

def obtener_nombre_jugador(jugador_id):
    """Obtiene el apellido de un jugador por su ID"""
    with engine.connect() as conn:
        resultado = conn.execute(text("""
        SELECT apellido, nombre FROM jugadores WHERE id = :jid
        """), {"jid": jugador_id}).fetchone()
        
        if resultado:
            apellido, nombre = resultado
            return f"{apellido} {nombre}" if nombre else apellido
        return "Desconocido"

def listar_partidos_disponibles(equipo_id=None, temporada_id=None, fase_id=None):
    """Lista los partidos disponibles según filtros"""
    with engine.connect() as conn:
        filtros = []
        params = {}
        
        if equipo_id:
            filtros.append("p.equipo_id = :equipo_id")
            params['equipo_id'] = equipo_id
        
        if temporada_id:
            filtros.append("p.temporada_id = :temporada_id")
            params['temporada_id'] = temporada_id
        
        if fase_id:
            filtros.append("p.fase_id = :fase_id")
            params['fase_id'] = fase_id
        
        where_clause = "WHERE " + " AND ".join(filtros) if filtros else ""
        
        query = text(f"""
        SELECT 
            p.id, 
            p.rival, 
            p.local,
            e.nombre as equipo,
            e.equipo_letra,
            t.nombre as temporada,
            f.nombre as fase
        FROM {TABLA_PARTIDOS} p
        JOIN {TABLA_EQUIPOS} e ON p.equipo_id = e.id
        JOIN {TABLA_TEMPORADAS} t ON p.temporada_id = t.id
        LEFT JOIN {TABLA_FASES} f ON p.fase_id = f.id
        {where_clause}
        ORDER BY p.id DESC
        """)
        
        return conn.execute(query, params).fetchall()
