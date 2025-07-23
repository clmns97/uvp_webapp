import React, { useState, useRef, useCallback } from 'react'
import Map, { Source, Layer, Marker, Popup } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [clickedPoint, setClickedPoint] = useState(null)
  const [nearestProtectedAreas, setNearestProtectedAreas] = useState(null)
  const [allnationalparke, setAllnationalparke] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showAllnationalparke, setShowAllnationalparke] = useState(false)
  const [showPopup, setShowPopup] = useState(false)
  
  // New state for GeoJSON file handling
  const [uploadedGeoJSON, setUploadedGeoJSON] = useState(null)
  const [isDragging, setIsDragging] = useState(false)
  const [fileName, setFileName] = useState('')
  
  const mapRef = useRef()

  // Helper function to find nearest protected areas for any geometry
  const findNearestProtectedAreas = useCallback(async (geojson) => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(`${API_URL}/api/nearest-protected-areas`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ geojson }),
      })
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const data = await response.json()
      setNearestProtectedAreas(data)
      
    } catch (err) {
      setError(`Error finding nearest protected areas: ${err.message}`)
      console.error('Error:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  const handleMapClick = useCallback(async (event) => {
    const { lngLat } = event
    setClickedPoint(lngLat)
    setShowPopup(true)
    
    // Create a Point GeoJSON from the clicked coordinates
    const pointGeoJSON = {
      type: "Point",
      coordinates: [lngLat.lng, lngLat.lat]
    }
    
    await findNearestProtectedAreas(pointGeoJSON)
  }, [findNearestProtectedAreas])

  // Helper function to calculate bounds for any geometry type
  const calculateBounds = useCallback((geojson) => {
    let bounds = null
    
    const addCoordinateToBounds = (coord) => {
      const [lng, lat] = coord
      if (!bounds) {
        bounds = { minLng: lng, maxLng: lng, minLat: lat, maxLat: lat }
      } else {
        bounds.minLng = Math.min(bounds.minLng, lng)
        bounds.maxLng = Math.max(bounds.maxLng, lng)
        bounds.minLat = Math.min(bounds.minLat, lat)
        bounds.maxLat = Math.max(bounds.maxLat, lat)
      }
    }
    
    const processGeometry = (geometry) => {
      if (!geometry || !geometry.coordinates) return
      
      switch (geometry.type) {
        case 'Point':
          addCoordinateToBounds(geometry.coordinates)
          break
        case 'LineString':
          geometry.coordinates.forEach(addCoordinateToBounds)
          break
        case 'Polygon':
          // For polygons, we only need the outer ring (first array)
          geometry.coordinates[0].forEach(addCoordinateToBounds)
          break
        case 'MultiPoint':
          geometry.coordinates.forEach(addCoordinateToBounds)
          break
        case 'MultiLineString':
          geometry.coordinates.forEach(lineString => {
            lineString.forEach(addCoordinateToBounds)
          })
          break
        case 'MultiPolygon':
          geometry.coordinates.forEach(polygon => {
            // For each polygon, use the outer ring (first array)
            polygon[0].forEach(addCoordinateToBounds)
          })
          break
      }
    }
    
    if (geojson.type === 'FeatureCollection') {
      geojson.features.forEach(feature => {
        if (feature.geometry) {
          processGeometry(feature.geometry)
        }
      })
    } else if (geojson.type === 'Feature') {
      if (geojson.geometry) {
        processGeometry(geojson.geometry)
      }
    } else {
      // Direct geometry object
      processGeometry(geojson)
    }
    
    return bounds
  }, [])

  // Drag and drop handlers
  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback(async (e) => {
    e.preventDefault()
    setIsDragging(false)
    
    const files = Array.from(e.dataTransfer.files)
    const geoJsonFile = files.find(file => 
      file.type === 'application/json' || 
      file.name.toLowerCase().endsWith('.geojson') ||
      file.name.toLowerCase().endsWith('.json')
    )
    
    if (!geoJsonFile) {
      setError('Please drop a valid GeoJSON file (.json or .geojson)')
      return
    }
    
    try {
      const text = await geoJsonFile.text()
      let geojson = JSON.parse(text)
      
      // Validate GeoJSON structure
      if (!geojson.type) {
        throw new Error('Invalid GeoJSON: missing type field')
      }
      
      // Clear previous results
      setClickedPoint(null)
      setShowPopup(false)
      setError(null)
      setLoading(true)
      
      // Check if GeoJSON needs coordinate transformation
      try {
        const transformResponse = await fetch(`${API_URL}/api/transform-geojson`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ geojson }),
        })
        
        if (transformResponse.ok) {
          const transformData = await transformResponse.json()
          
          if (transformData.source_crs !== "EPSG:4326") {
            // Use the transformed GeoJSON
            geojson = transformData.transformed_geojson
            setError(`📍 Transformed from ${transformData.source_crs} to WGS84`)
            // Clear the error after a few seconds to show it as info
            setTimeout(() => {
              setError(null)
            }, 5000)
          }
        } else {
          const errorData = await transformResponse.json()
          throw new Error(errorData.detail || 'CRS transformation failed')
        }
      } catch (transformError) {
        console.warn('CRS transformation failed:', transformError.message)
        setError(`⚠️ CRS check failed: ${transformError.message}. Assuming WGS84.`)
        // Continue with original GeoJSON, assuming it's in WGS84
      }
      
      // Set the uploaded GeoJSON for display
      setUploadedGeoJSON(geojson)
      setFileName(geoJsonFile.name)
      
      // Find nearest protected areas for the uploaded geometry
      await findNearestProtectedAreas(geojson)
      
      // Fit map to bounds of uploaded GeoJSON
      if (mapRef.current) {
        const bounds = calculateBounds(geojson)
        
        if (bounds) {
          // Add some padding to ensure the geometry is fully visible
          const padding = 0.01 // degrees
          mapRef.current.fitBounds([
            [bounds.minLng - padding, bounds.minLat - padding],
            [bounds.maxLng + padding, bounds.maxLat + padding]
          ], { padding: 50 })
        }
      }
      
    } catch (err) {
      setError(`Error processing GeoJSON file: ${err.message}`)
      console.error('Error:', err)
    } finally {
      setLoading(false)
    }
  }, [findNearestProtectedAreas, calculateBounds])

  // File input handler (alternative to drag and drop)
  const handleFileInput = useCallback(async (e) => {
    const file = e.target.files[0]
    if (!file) return
    
    // Create a mock drop event to reuse the same logic
    const mockDropEvent = {
      preventDefault: () => {},
      dataTransfer: { files: [file] }
    }
    
    await handleDrop(mockDropEvent)
    
    // Clear the input so the same file can be selected again
    e.target.value = ''
  }, [handleDrop])

  const loadAllnationalparke = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(`${API_URL}/api/all-nationalparke`)
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const data = await response.json()
      setAllnationalparke(data)
      setShowAllnationalparke(true)
      
    } catch (err) {
      setError(`Error loading nationalparke: ${err.message}`)
      console.error('Error:', err)
    } finally {
      setLoading(false)
    }
  }

  const clearResults = () => {
    setClickedPoint(null)
    setNearestProtectedAreas(null)
    setAllnationalparke(null)
    setShowAllnationalparke(false)
    setShowPopup(false)
    setUploadedGeoJSON(null)
    setFileName('')
    setError(null)
  }

  // Helper function to get color for different protected area types
  const getAreaTypeColor = (areaType) => {
    const colors = {
      'National Parks': '#2ecc71',
      'Nature Parks': '#3498db', 
      'Nature Reserves': '#e67e22',
      'Landscape Protection Areas': '#9b59b6',
      'Biosphere Reserves': '#f39c12',
      'Bird Protection Areas': '#e74c3c',
      'Fauna-Flora-Habitat Areas': '#1abc9c',
      'National Natural Monuments': '#34495e',
      'Biosphere Reserve Zoning': '#f1c40f'
    }
    return colors[areaType] || '#95a5a6'
  }

  // Group areas by type for better display
  const groupedAreas = nearestProtectedAreas ? 
    nearestProtectedAreas.features.reduce((groups, area) => {
      const type = area.properties.area_type
      if (!groups[type]) {
        groups[type] = []
      }
      groups[type].push(area)
      return groups
    }, {}) : {}

  // Layer styles for GeoJSON data
  const nearestProtectedAreasLayerStyle = {
    id: 'nearest-protected-areas',
    type: 'fill',
    paint: {
      'fill-color': [
        'case',
        ['==', ['get', 'area_type'], 'National Parks'], '#2ecc71',
        ['==', ['get', 'area_type'], 'Nature Parks'], '#3498db',
        ['==', ['get', 'area_type'], 'Nature Reserves'], '#e67e22',
        ['==', ['get', 'area_type'], 'Landscape Protection Areas'], '#9b59b6',
        ['==', ['get', 'area_type'], 'Biosphere Reserves'], '#f39c12',
        ['==', ['get', 'area_type'], 'Bird Protection Areas'], '#e74c3c',
        ['==', ['get', 'area_type'], 'Fauna-Flora-Habitat Areas'], '#1abc9c',
        ['==', ['get', 'area_type'], 'National Natural Monuments'], '#34495e',
        ['==', ['get', 'area_type'], 'Biosphere Reserve Zoning'], '#f1c40f',
        '#95a5a6'
      ],
      'fill-opacity': 0.7,
      'fill-outline-color': '#000000'
    }
  }

  const allnationalparkeLayerStyle = {
    id: 'all-nationalparke',
    type: 'fill',
    paint: {
      'fill-color': '#3498db',
      'fill-opacity': 0.5,
      'fill-outline-color': '#2980b9'
    }
  }

  // Updated styles for uploaded GeoJSON - optimized for polygons
  const uploadedGeoJSONFillLayerStyle = {
    id: 'uploaded-geojson-fill',
    type: 'fill',
    paint: {
      'fill-color': '#e74c3c',
      'fill-opacity': 0.4,
      'fill-outline-color': '#c0392b'
    },
    filter: ['in', '$type', 'Polygon']
  }

  const uploadedGeoJSONLineLayerStyle = {
    id: 'uploaded-geojson-line',
    type: 'line',
    paint: {
      'line-color': '#c0392b',
      'line-width': 3,
      'line-opacity': 0.8
    },
    filter: ['in', '$type', 'LineString']
  }

  const uploadedGeoJSONPointLayerStyle = {
    id: 'uploaded-geojson-points',
    type: 'circle',
    paint: {
      'circle-radius': 8,
      'circle-color': '#e74c3c',
      'circle-stroke-color': '#c0392b',
      'circle-stroke-width': 2
    },
    filter: ['==', '$type', 'Point']
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ 
        background: '#2c3e50', 
        color: 'white', 
        padding: '1rem',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
      }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem' }}>GeoJSON Protected Areas Finder</h1>
        <p style={{ margin: '0.5rem 0 0 0', opacity: 0.8 }}>
          Click on the map or drag & drop a GeoJSON file to find nearest protected areas
        </p>
      </div>

      {/* Controls */}
      <div style={{ 
        background: '#ecf0f1', 
        padding: '1rem', 
        borderBottom: '1px solid #bdc3c7',
        display: 'flex',
        gap: '1rem',
        alignItems: 'center',
        flexWrap: 'wrap'
      }}>
        <button 
          onClick={loadAllnationalparke}
          disabled={loading}
          style={{
            background: '#3498db',
            color: 'white',
            border: 'none',
            padding: '0.5rem 1rem',
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1
          }}
        >
          {loading ? 'Loading...' : 'Show All National Parks'}
        </button>
        
        <label style={{
          background: '#9b59b6',
          color: 'white',
          padding: '0.5rem 1rem',
          borderRadius: '4px',
          cursor: 'pointer',
          display: 'inline-block'
        }}>
          Upload GeoJSON
          <input
            type="file"
            accept=".json,.geojson"
            onChange={handleFileInput}
            style={{ display: 'none' }}
          />
        </label>
        
        <button 
          onClick={clearResults}
          style={{
            background: '#e74c3c',
            color: 'white',
            border: 'none',
            padding: '0.5rem 1rem',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Clear Results
        </button>

        {fileName && (
          <div style={{ 
            background: '#27ae60', 
            color: 'white', 
            padding: '0.5rem 1rem',
            borderRadius: '4px',
            fontSize: '0.9rem'
          }}>
            📁 {fileName}
          </div>
        )}

        {error && (
          <div style={{ color: '#e74c3c', fontWeight: 'bold' }}>
            {error}
          </div>
        )}
      </div>

      {/* Map */}
      <div 
        style={{ flex: 1, position: 'relative' }}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* Drag overlay */}
        {isDragging && (
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(52, 152, 219, 0.8)',
            zIndex: 2000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            fontSize: '2rem',
            fontWeight: 'bold',
            pointerEvents: 'none'
          }}>
            Drop GeoJSON file here
          </div>
        )}

        <Map
          ref={mapRef}
          initialViewState={{
            longitude: 51.416667,
            latitude: 9.483333,
            zoom: 10
          }}
          style={{ width: '100%', height: '100%' }}
          mapStyle={{
            version: 8,
            sources: {
              'carto-light': {
                type: 'raster',
                tiles: [
                  'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
                  'https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
                  'https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
                  'https://d.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png'
                ],
                tileSize: 256,
                attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>'
              }
            },
            layers: [
              {
                id: 'carto-light-layer',
                type: 'raster',
                source: 'carto-light',
                minzoom: 0,
                maxzoom: 22
              }
            ]
          }}
          onClick={handleMapClick}
          cursor={loading ? 'wait' : 'auto'}
        >
          {/* All nationalparke layer */}
          {showAllnationalparke && allnationalparke && (
            <Source id="all-nationalparke-source" type="geojson" data={allnationalparke}>
              <Layer {...allnationalparkeLayerStyle} />
            </Source>
          )}

          {/* Uploaded GeoJSON layer */}
          {uploadedGeoJSON && (
            <Source id="uploaded-geojson-source" type="geojson" data={uploadedGeoJSON}>
              <Layer {...uploadedGeoJSONFillLayerStyle} />
              <Layer {...uploadedGeoJSONLineLayerStyle} />
              <Layer {...uploadedGeoJSONPointLayerStyle} />
            </Source>
          )}

          {/* Nearest protected areas layer */}
          {nearestProtectedAreas && (
            <Source id="nearest-protected-areas-source" type="geojson" data={nearestProtectedAreas}>
              <Layer {...nearestProtectedAreasLayerStyle} />
            </Source>
          )}

          {/* Clicked point marker */}
          {clickedPoint && (
            <Marker
              longitude={clickedPoint.lng}
              latitude={clickedPoint.lat}
              color="red"
            />
          )}

          {/* Popup for clicked point */}
          {clickedPoint && showPopup && (
            <Popup
              longitude={clickedPoint.lng}
              latitude={clickedPoint.lat}
              anchor="bottom"
              onClose={() => setShowPopup(false)}
            >
              <div>
                <strong>Clicked Location</strong><br />
                Lat: {clickedPoint.lat.toFixed(6)}<br />
                Lng: {clickedPoint.lng.toFixed(6)}
              </div>
            </Popup>
          )}
        </Map>
        
        {/* Loading overlay */}
        {loading && (
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            background: 'rgba(255, 255, 255, 0.9)',
            padding: '2rem',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            zIndex: 1500,
            display: 'flex',
            alignItems: 'center',
            gap: '1rem'
          }}>
            <div style={{
              width: '24px',
              height: '24px',
              border: '3px solid #e3e3e3',
              borderTop: '3px solid #3498db',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite'
            }}></div>
            <span style={{ fontWeight: 'bold', color: '#2c3e50' }}>
              Finding nearest protected areas...
            </span>
          </div>
        )}
        
        {/* Results panel */}
        {nearestProtectedAreas && (
          <div style={{
            position: 'absolute',
            top: '10px',
            right: '10px',
            background: 'white',
            padding: '1rem',
            borderRadius: '8px',
            boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
            maxWidth: '350px',
            maxHeight: '70vh',
            overflowY: 'auto',
            zIndex: 1000
          }}>
            <h3 style={{ margin: '0 0 0.5rem 0' }}>
              Nearest Protected Areas
              {fileName && <div style={{ fontSize: '0.8rem', color: '#666' }}>for {fileName}</div>}
            </h3>
            {nearestProtectedAreas.features.length === 0 ? (
              <div style={{ color: '#666', fontStyle: 'italic' }}>
                No protected areas found within 50km
              </div>
            ) : (
              Object.entries(groupedAreas).map(([areaType, areas]) => (
                <div key={areaType} style={{ marginBottom: '1rem' }}>
                  <h4 style={{ 
                    margin: '0 0 0.5rem 0', 
                    color: getAreaTypeColor(areaType),
                    borderBottom: `2px solid ${getAreaTypeColor(areaType)}`,
                    paddingBottom: '0.25rem',
                    fontSize: '0.9rem'
                  }}>
                    {areaType} ({areas.length})
                  </h4>
                  {areas.map((area, index) => (
                    <div key={`${area.properties.id}-${index}`} style={{ 
                      marginBottom: '0.5rem',
                      padding: '0.5rem',
                      background: '#f8f9fa',
                      borderRadius: '4px',
                      borderLeft: `4px solid ${getAreaTypeColor(areaType)}`
                    }}>
                      <strong>{area.properties.name}</strong><br />
                      <small style={{ color: '#666' }}>
                        {area.properties.distance_km}km away
                      </small>
                    </div>
                  ))}
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Add CSS for spinner animation */}
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

export default App