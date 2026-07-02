# -*- coding: utf-8 -*-
"""
utils_v2.py
Utilidades adaptadas a la nueva estructura
"""
import re
from sqlalchemy import text
from config_v2 import engine

def separar_mayusculas(texto):
    """
    Separa palabras en CamelCase añadiendo espacios.
    Ejemplo: 'VoleiGirona' -> 'Volei Girona'
    """
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', texto)

def obtener_apellido_por_id(jugador_id):
    """Obtiene el apellido de un jugador por su ID"""
    with engine.connect() as conn:
        resultado = conn.execute(text("""
        SELECT apellido FROM jugadores WHERE id = :jid
        """), {"jid": jugador_id}).fetchone()
        
        return resultado[0] if resultado else "Desconocido"

def obtener_nombre_completo_jugador(jugador_id):
    """Obtiene el nombre completo de un jugador por su ID"""
    with engine.connect() as conn:
        resultado = conn.execute(text("""
        SELECT apellido, nombre FROM jugadores WHERE id = :jid
        """), {"jid": jugador_id}).fetchone()
        
        if resultado:
            apellido, nombre = resultado
            return f"{nombre} {apellido}" if nombre else apellido
        return "Desconocido"

def obtener_info_partido(partido_id):
    """Obtiene información completa de un partido"""
    with engine.connect() as conn:
        resultado = conn.execute(text("""
        SELECT 
            p.id,
            p.rival,
            p.local,
            e.nombre as equipo,
            e.equipo_letra,
            t.nombre as temporada,
            f.nombre as fase,
            p.fecha,
            p.resultado
        FROM partidos_new p
        JOIN equipos e ON p.equipo_id = e.id
        JOIN temporadas t ON p.temporada_id = t.id
        LEFT JOIN fases f ON p.fase_id = f.id
        WHERE p.id = :pid
        """), {"pid": partido_id}).fetchone()
        
        if resultado:
            return {
                'id': resultado[0],
                'rival': resultado[1],
                'local': resultado[2],
                'equipo': resultado[3],
                'equipo_letra': resultado[4],
                'equipo_completo': f"{resultado[3]} {resultado[4]}" if resultado[4] else resultado[3],
                'temporada': resultado[5],
                'fase': resultado[6],
                'fecha': resultado[7],
                'resultado': resultado[8]
            }
        return None

def listar_jugadores_equipo(equipo_id):
    """Lista todos los jugadores de un equipo"""
    with engine.connect() as conn:
        jugadores = conn.execute(text("""
        SELECT id, apellido, nombre, dorsal, posicion
        FROM jugadores
        WHERE equipo_id = :eid AND activo = true
        ORDER BY apellido
        """), {"eid": equipo_id}).fetchall()
        
        return jugadores

def obtener_partidos_filtrados(equipo_id=None, temporada_id=None, fase_id=None):
    """Obtiene lista de IDs de partidos según filtros"""
    with engine.connect() as conn:
        filtros = []
        params = {}
        
        if equipo_id:
            filtros.append("equipo_id = :equipo_id")
            params['equipo_id'] = equipo_id
        
        if temporada_id:
            filtros.append("temporada_id = :temporada_id")
            params['temporada_id'] = temporada_id
        
        if fase_id:
            filtros.append("fase_id = :fase_id")
            params['fase_id'] = fase_id
        
        where_clause = "WHERE " + " AND ".join(filtros) if filtros else ""
        
        query = text(f"""
        SELECT id 
        FROM partidos_new 
        {where_clause}
        ORDER BY id
        """)
        
        resultados = conn.execute(query, params).fetchall()
        return [r[0] for r in resultados]
