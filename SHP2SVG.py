import geopandas as gpd
import svgwrite
import pandas as pd

# Estados que terão municípios detalhados
estados_detalhados = ["RS", "SC", "PR", "SP", "RJ", "ES", "MS", "MG", "GO"]

# --- 1. Carregar shapefile dos municípios do Brasil ---
gdf = gpd.read_file(r"C:\\Users\\Cassia\\Documents\\Georreferenciamento\\BR_Municipios_2024\\BR_Municipios_2024.shp")
gdf = gdf.to_crs(epsg=3857)

# Separar municípios detalhados e os demais
gdf_detalhados = gdf[gdf["SIGLA_UF"].isin(estados_detalhados)]
gdf_simplificados = gdf[~gdf["SIGLA_UF"].isin(estados_detalhados)]

# Dissolver os municípios dos estados simplificados em um polígono por estado
gdf_estados = gdf_simplificados.dissolve(by="SIGLA_UF").reset_index()
gdf_estados["CD_MUN"] = "UF_" + gdf_estados["SIGLA_UF"]

# Unir municípios detalhados + estados simplificados
gdf_final = gpd.GeoDataFrame(pd.concat([gdf_detalhados, gdf_estados], ignore_index=True), crs=gdf.crs)
gdf_final["PAI_SG"] = "BR"  # marca todos como Brasil

# Simplificar geometrias
gdf_final["geometry"] = gdf_final["geometry"].simplify(tolerance=2000, preserve_topology=True)

# --- 2. Carregar shapefile da América do Sul ---
america_do_sul = gpd.read_file(r"C:\\Users\\Cassia\\Documents\\Georreferenciamento\\GEOFT_PAIS\\GEOFT_PAIS\\GEOFT_PAIS.shp")
america_do_sul = america_do_sul.to_crs(epsg=3857)

# Filtrar apenas países ≠ Brasil (inclui Chile, Equador, Suriname etc.)
paises_vizinhos_raw = america_do_sul[~america_do_sul["PAI_SG"].isin(["BR", None, ""])].copy()
paises_vizinhos = paises_vizinhos_raw.dissolve(by="PAI_SG").reset_index()
paises_vizinhos["CD_MUN"] = "PAIS_" + paises_vizinhos["PAI_SG"]

# Simplificar geometrias
paises_vizinhos["geometry"] = paises_vizinhos["geometry"].simplify(tolerance=2000, preserve_topology=True)

# --- 3. Unir Brasil + países vizinhos ---
gdf_total = pd.concat([gdf_final, paises_vizinhos], ignore_index=True)
gdf_total = gpd.GeoDataFrame(gdf_total, crs=gdf_final.crs)

# Atualizar limites para normalização
minx, miny, maxx, maxy = gdf_total.total_bounds
width = 1000 
aspect_ratio = (maxy - miny) / (maxx - minx) 
height = int(width * aspect_ratio)

def transform_coords(x, y):
    sx = (x - minx) / (maxx - minx) * width
    sy = height - (y - miny) / (maxy - miny) * height
    return (sx, sy)

# --- 4. Criar SVG final ---
dwg = svgwrite.Drawing("C:\\Users\\Cassia\\Documents\\Georreferenciamento\\Mapa_Final.svg", size=(width, height))
dwg.add(dwg.rect(insert=(0, 0), size=(width, height), fill='lightblue'))  # oceano azul

for _, row in gdf_total.iterrows():
    geom = row.geometry
    id_svg = str(row["CD_MUN"])
    pais = row.get("PAI_SG", "")

    if geom.is_empty:
        continue

    # Estilo por tipo
    if pais and pais != "BR":  # países vizinhos
        fill_color = "#F0F0F0"
        stroke_width = 1.0
    elif id_svg.startswith("UF_"):  # estados simplificados
        fill_color = "#DDDDDD"
        stroke_width = 1.0
    else:  # municípios detalhados
        fill_color = "white"
        stroke_width = 0.26

    # Desenhar polígonos
    if geom.geom_type == "Polygon":
        coords = [transform_coords(x, y) for x, y in geom.exterior.coords]
        dwg.add(dwg.polygon(points=coords, id=id_svg, fill=fill_color, stroke="black", stroke_width=stroke_width))
    elif geom.geom_type == "MultiPolygon":
        for poly in geom.geoms:
            coords = [transform_coords(x, y) for x, y in poly.exterior.coords]
            dwg.add(dwg.polygon(points=coords, id=id_svg, fill=fill_color, stroke="black", stroke_width=stroke_width))

# --- 5. Desenhar limites estaduais sobrepostos (contorno grosso) ---
gdf_limites_estados = gdf.dissolve(by="SIGLA_UF").reset_index()
gdf_limites_estados = gdf_limites_estados.to_crs(epsg=3857)
gdf_limites_estados["geometry"] = gdf_limites_estados["geometry"].simplify(tolerance=2000, preserve_topology=True)

for _, row in gdf_limites_estados.iterrows():
    geom = row.geometry
    id_svg = "LIMITE_" + row["SIGLA_UF"]

    if geom.is_empty:
        continue

    if geom.geom_type == "Polygon":
        coords = [transform_coords(x, y) for x, y in geom.exterior.coords]
        dwg.add(dwg.polygon(points=coords, id=id_svg, fill="none", stroke="black", stroke_width=1.0))
    elif geom.geom_type == "MultiPolygon":
        for poly in geom.geoms:
            coords = [transform_coords(x, y) for x, y in poly.exterior.coords]
            dwg.add(dwg.polygon(points=coords, id=id_svg, fill="none", stroke="black", stroke_width=1.0))

dwg.save()
