import json
import os
import tempfile
import webbrowser
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsProject,
)


def export_qgis_to_webgis(
    output_filepath=None, title="Mapa Interativo - WebGIS QGIS"
):
    """Lê as camadas vetoriais do QGIS e exporta para uma aplicação WebGIS HTML completa."""
    project = QgsProject.instance()
    layers = list(project.mapLayers().values())

    crs_dst = QgsCoordinateReferenceSystem("EPSG:4326")
    web_layers = []

    # Cores padrão caso a camada não tenha cor definida
    default_colors = [
        "#10b981",
        "#3b82f6",
        "#ef4444",
        "#f59e0b",
        "#8b5cf6",
        "#ec4899",
        "#14b8a6",
    ]
    color_idx = 0

    print("🔎 Processando camadas do QGIS...")

    for layer in layers:
        # Apenas camadas vetoriais
        if layer.type() != layer.VectorLayer:
            continue

        layer_name = layer.name()
        crs_src = layer.crs()
        transform = QgsCoordinateTransform(crs_src, crs_dst, project)

        # Capturar cor do renderer
        renderer = layer.renderer()
        layer_color = default_colors[color_idx % len(default_colors)]
        color_idx += 1

        if renderer and hasattr(renderer, "symbol") and renderer.symbol():
            symbol = renderer.symbol()
            if symbol and hasattr(symbol, "color"):
                layer_color = symbol.color().name()

        # Descobrir o tipo de geometria
        geom_type_enum = layer.geometryType()
        geom_type_str = "Polygon"
        if geom_type_enum == 0:
            geom_type_str = "Point"
        elif geom_type_enum == 1:
            geom_type_str = "LineString"

        # Extrair feições em formato GeoJSON
        field_names = [field.name() for field in layer.fields()]
        features_list = []

        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom.isNull() or geom.isEmpty():
                continue

            # Reprojetar para EPSG:4326 se necessário
            if crs_src != crs_dst:
                geom_reproj = QgsGeometry(geom)
                geom_reproj.transform(transform)
            else:
                geom_reproj = geom

            # Converter geometria para JSON
            try:
                geom_json = json.loads(geom_reproj.asJson())
            except Exception:
                continue

            # Dicionário de atributos
            attrs = {}
            for name in field_names:
                val = feat[name]
                if hasattr(val, "toString"):
                    val = val.toString()
                elif val is None or str(val) == "NULL":
                    val = None
                attrs[name] = val

            features_list.append(
                {
                    "type": "Feature",
                    "geometry": geom_json,
                    "properties": attrs,
                }
            )

        geojson_data = {
            "type": "FeatureCollection",
            "features": features_list,
        }

        web_layers.append(
            {
                "id": f"layer_{len(web_layers)}",
                "name": layer_name,
                "color": layer_color,
                "geom_type": geom_type_str,
                "data": geojson_data,
            }
        )
        print(
            f"✅ Camada '{layer_name}' processada ({len(features_list)} feições)."
        )

    if not web_layers:
        print("❌ Nenhuma camada vetorial encontrada no projeto ativo!")
        return

    # Definir caminho do arquivo de saída
    if not output_filepath:
        temp_dir = tempfile.gettempdir()
        output_filepath = os.path.join(temp_dir, "webgis_qgis_export.html")

    # JSON codificado das camadas para inclusão no HTML
    layers_json_str = json.dumps(web_layers, ensure_ascii=False)

    # Template HTML
    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        #map {{ height: calc(100vh - 64px); width: 100%; }}
        .custom-scrollbar::-webkit-scrollbar {{ width: 6px; }}
        .custom-scrollbar::-webkit-scrollbar-thumb {{ background-color: #cbd5e1; border-radius: 3px; }}
    </style>
</head>
<body class="bg-slate-900 font-sans flex flex-col h-screen overflow-hidden">

    <!-- Header -->
    <header class="h-16 bg-slate-800 border-b border-slate-700 px-6 flex items-center justify-between text-white shadow-md z-20">
        <div class="flex items-center gap-3">
            <div class="bg-emerald-600 p-2 rounded-lg"><i class="fa-solid fa-map-location-dot text-xl"></i></div>
            <div>
                <h1 class="font-bold text-lg leading-tight">{title}</h1>
                <p class="text-xs text-slate-400">Exportado automaticamente via PyQGIS</p>
            </div>
        </div>
        <button onclick="downloadAllLayersGeoJSON()" class="bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition flex items-center gap-2 shadow">
            <i class="fa-solid fa-file-arrow-down"></i> Baixar GeoJSON Completo
        </button>
    </header>

    <!-- Content Area -->
    <div class="flex flex-1 relative overflow-hidden">
        <!-- Sidebar -->
        <aside class="w-80 bg-slate-800 border-r border-slate-700 flex flex-col text-slate-200 z-10 shadow-xl">
            <!-- Tabs -->
            <div class="flex border-b border-slate-700 bg-slate-850">
                <button onclick="switchTab('layers')" id="tab-layers" class="flex-1 py-3 text-xs font-semibold uppercase tracking-wider text-emerald-400 border-b-2 border-emerald-500 flex items-center justify-center gap-2">
                    <i class="fa-solid fa-layer-group"></i> Camadas
                </button>
                <button onclick="switchTab('details')" id="tab-details" class="flex-1 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400 border-b-2 border-transparent flex items-center justify-center gap-2">
                    <i class="fa-solid fa-circle-info"></i> Detalhes
                </button>
            </div>

            <!-- Tab Content: Layers -->
            <div id="content-layers" class="flex-1 p-4 overflow-y-auto custom-scrollbar flex flex-col gap-4">
                <div class="text-xs font-bold uppercase text-slate-400 tracking-wider">Camadas Vetoriais</div>
                <div id="layers-list" class="flex flex-col gap-3"></div>
            </div>

            <!-- Tab Content: Details -->
            <div id="content-details" class="flex-1 p-4 overflow-y-auto custom-scrollbar hidden flex flex-col gap-4">
                <div class="text-xs font-bold uppercase text-slate-400 tracking-wider">Atributos da Feição Selecionada</div>
                <div id="feature-info" class="text-sm text-slate-400 italic bg-slate-900/50 p-4 rounded-lg border border-slate-700">
                    Clique em qualquer vetor no mapa para visualizar a tabela de atributos completa.
                </div>
            </div>
        </aside>

        <!-- Map Container -->
        <main class="flex-1 relative">
            <div id="map"></div>
        </main>
    </div>

    <script>
        const layersData = {layers_json_str};
        let map;
        let leafletLayers = {{}};

        function initMap() {{
            map = L.map('map').setView([0, 0], 2);

            const osm = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{b}}/{{x}}/{{y}}.png', {{
                attribution: '&copy; OpenStreetMap contributors'
            }});

            const esriSatellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                attribution: 'Tiles &copy; Esri'
            }}).addTo(map);

            const baseMaps = {{
                "Satélite (ESRI)": esriSatellite,
                "OpenStreetMap": osm
            }};

            L.control.layers(baseMaps, null, {{ position: 'topright' }}).addTo(map);

            const boundsGroup = L.featureGroup();

            layersData.forEach((lData) => {{
                const geojsonLayer = L.geoJSON(lData.data, {{
                    style: function(feature) {{
                        return {{
                            color: lData.color,
                            weight: 2,
                            opacity: 0.9,
                            fillColor: lData.color,
                            fillOpacity: 0.35
                        }};
                    }},
                    onEachFeature: function(feature, layer) {{
                        layer.on('click', function(e) {{
                            showFeatureDetails(feature.properties, lData.name, feature);
                        }});
                    }}
                }}).addTo(map);

                leafletLayers[lData.id] = {{
                    layer: geojsonLayer,
                    data: lData,
                    opacity: 0.35
                }};

                boundsGroup.addLayer(geojsonLayer);
            }});

            if (layersData.length > 0) {{
                map.fitBounds(boundsGroup.getBounds(), {{ padding: [30, 30] }});
            }}

            renderLayerControls();
        }}

        function renderLayerControls() {{
            const container = document.getElementById('layers-list');
            container.innerHTML = '';

            layersData.forEach((lData) => {{
                const card = document.createElement('div');
                card.className = "bg-slate-750 p-3 rounded-lg border border-slate-700 flex flex-col gap-2";
                
                card.innerHTML = `
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <input type="checkbox" checked onchange="toggleLayer('${{lData.id}}', this.checked)" class="w-4 h-4 accent-emerald-500 rounded cursor-pointer">
                            <span class="w-3 h-3 rounded-full inline-block" style="background-color: ${{lData.color}};"></span>
                            <span class="font-medium text-sm text-slate-200">${{lData.name}}</span>
                        </div>
                        <button onclick="downloadSingleLayerGeoJSON('${{lData.id}}')" title="Baixar GeoJSON" class="text-slate-400 hover:text-emerald-400 p-1 transition">
                            <i class="fa-solid fa-download"></i>
                        </button>
                    </div>
                    <div class="flex items-center gap-2 mt-1">
                        <span class="text-xs text-slate-400">Opacidade:</span>
                        <input type="range" min="0" max="1" step="0.05" value="0.35" oninput="changeOpacity('${{lData.id}}', this.value)" class="w-full accent-emerald-500 h-1 bg-slate-700 rounded-lg cursor-pointer">
                    </div>
                `;
                container.appendChild(card);
            }});
        }}

        function toggleLayer(id, visible) {{
            if (visible) {{
                map.addLayer(leafletLayers[id].layer);
            }} else {{
                map.removeLayer(leafletLayers[id].layer);
            }}
        }}

        function changeOpacity(id, value) {{
            leafletLayers[id].opacity = value;
            leafletLayers[id].layer.setStyle({{ fillOpacity: value, opacity: Math.min(1, parseFloat(value) + 0.3) }});
        }}

        function showFeatureDetails(properties, layerName, feature) {{
            switchTab('details');
            const container = document.getElementById('feature-info');
            
            let tableHtml = `<div class="mb-3 text-xs font-semibold text-emerald-400 uppercase tracking-wider">${{layerName}}</div>`;
            tableHtml += `<div class="overflow-x-auto border border-slate-700 rounded-lg"><table class="w-full text-left text-xs border-collapse"><tbody>`;

            for (const [key, val] of Object.entries(properties)) {{
                tableHtml += `
                    <tr class="border-b border-slate-700/50 hover:bg-slate-800">
                        <td class="p-2 font-medium text-slate-400 bg-slate-850/50">${{key}}</td>
                        <td class="p-2 text-slate-200">${{val !== null ? val : '<span class="text-slate-600">-</span>'}}</td>
                    </tr>
                `;
            }}

            tableHtml += `</tbody></table></div>`;
            
            const featureGeoJSON = JSON.stringify({{
                type: "Feature",
                geometry: feature.geometry,
                properties: properties
            }}, null, 2);

            tableHtml += `
                <button onclick="downloadCustomGeoJSON(${{escape(JSON.stringify(featureGeoJSON))}}, 'feicao_selecionada.geojson')" class="mt-3 w-full bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-medium py-2 rounded transition flex items-center justify-center gap-2">
                    <i class="fa-solid fa-download"></i> Baixar GeoJSON desta Feição
                </button>
            `;

            container.innerHTML = tableHtml;
        }}

        function switchTab(tab) {{
            const tabLayers = document.getElementById('tab-layers');
            const tabDetails = document.getElementById('tab-details');
            const contentLayers = document.getElementById('content-layers');
            const contentDetails = document.getElementById('content-details');

            if (tab === 'layers') {{
                tabLayers.className = "flex-1 py-3 text-xs font-semibold uppercase tracking-wider text-emerald-400 border-b-2 border-emerald-500 flex items-center justify-center gap-2";
                tabDetails.className = "flex-1 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400 border-b-2 border-transparent flex items-center justify-center gap-2";
                contentLayers.classList.remove('hidden');
                contentDetails.classList.add('hidden');
            }} else {{
                tabDetails.className = "flex-1 py-3 text-xs font-semibold uppercase tracking-wider text-emerald-400 border-b-2 border-emerald-500 flex items-center justify-center gap-2";
                tabLayers.className = "flex-1 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400 border-b-2 border-transparent flex items-center justify-center gap-2";
                contentDetails.classList.remove('hidden');
                contentLayers.classList.add('hidden');
            }}
        }}

        function downloadCustomGeoJSON(contentStr, filename) {{
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(contentStr);
            const downloadAnchor = document.createElement('a');
            downloadAnchor.setAttribute("href", dataStr);
            downloadAnchor.setAttribute("download", filename);
            document.body.appendChild(downloadAnchor);
            downloadAnchor.click();
            downloadAnchor.remove();
        }}

        function downloadSingleLayerGeoJSON(id) {{
            const lData = leafletLayers[id].data;
            const contentStr = JSON.stringify(lData.data, null, 2);
            downloadCustomGeoJSON(contentStr, `${{lData.name.toLowerCase().replace(/\\s+/g, '_')}}.geojson`);
        }}

        function downloadAllLayersGeoJSON() {{
            const allFeatures = [];
            layersData.forEach(lData => {{
                lData.data.features.forEach(feat => {{
                    const newFeat = JSON.parse(JSON.stringify(feat));
                    newFeat.properties._layer_name = lData.name;
                    allFeatures.push(newFeat);
                }});
            }});

            const fullGeoJSON = {{
                type: "FeatureCollection",
                features: allFeatures
            }};

            downloadCustomGeoJSON(JSON.stringify(fullGeoJSON, null, 2), "todas_as_camadas_qgis.geojson");
        }}

        window.onload = initMap;
    </script>
</body>
</html>
"""

    with open(output_filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"🎉 WebGIS exportado com sucesso!")
    print(f"📁 Salvo em: {output_filepath}")

    webbrowser.open(f"file://{output_filepath}")


# Executar no QGIS
export_qgis_to_webgis(title="SIG Ambiental & Fundiário - Export QGIS")