import React, { useState, useRef, useCallback } from 'react'
import Map, { Source, Layer, Marker, Popup } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [clickedPoint, setClickedPoint] = useState(null)
  const [nearestnationalparke, setNearestnationalparke] = useState(null)
  const [allnationalparke, setAllnationalparke] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showAllnationalparke, setShowAllnationalparke] = useState(false)
  const [showPopup, setShowPopup] = useState(false)
  const mapRef = useRef()

  const handleMapClick = useCallback(async (event) => {
    const { lngLat } = event
    setClickedPoint(lngLat)
    setLoading(true)
    setError(null)
    setShowPopup(true)
    
    try {
      // Create a Point GeoJSON from the clicked coordinates
      const pointGeoJSON = {
        type: "Point",
        coordinates: [lngLat.lng, lngLat.lat]
      }
      
      const response = await fetch(`${API_URL}/api/nearest-nationalparke`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          geojson: pointGeoJSON
        }),
      })
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const data = await response.json()
      setNearestnationalparke(data)
      
    } catch (err) {
      setError(`Error finding nearest nationalparke: ${err.message}`)
      console.error('Error:', err)
    } finally {
      setLoading(false)
    }
  }, [])

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
    setNearestnationalparke(null)
    setAllnationalparke(null)
    setShowAllnationalparke(false)
    setShowPopup(false)
    setError(null)
  }

  // Layer styles for GeoJSON data
  const nearestnationalparkeLayerStyle = {
    id: 'nearest-nationalparke',
    type: 'fill',
    paint: {
      'fill-color': '#2ecc71',
      'fill-opacity': 0.7,
      'fill-outline-color': '#27ae60'
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

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ 
        background: '#2c3e50', 
        color: 'white', 
        padding: '1rem',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
      }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem' }}>GeoJSON nationalparke Finder</h1>
        <p style={{ margin: '0.5rem 0 0 0', opacity: 0.8 }}>
          Click on the map to find the 5 nearest nationalparke
        </p>
      </div>

      {/* Controls */}
      <div style={{ 
        background: '#ecf0f1', 
        padding: '1rem', 
        borderBottom: '1px solid #bdc3c7',
        display: 'flex',
        gap: '1rem',
        alignItems: 'center'
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
          {loading ? 'Loading...' : 'Show All nationalparke'}
        </button>
        
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

        {error && (
          <div style={{ color: '#e74c3c', fontWeight: 'bold' }}>
            {error}
          </div>
        )}
      </div>

      {/* Map */}
      <div style={{ flex: 1, position: 'relative' }}>
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
        >
          {/* All nationalparke layer */}
          {showAllnationalparke && allnationalparke && (
            <Source id="all-nationalparke-source" type="geojson" data={allnationalparke}>
              <Layer {...allnationalparkeLayerStyle} />
            </Source>
          )}

          {/* Nearest nationalparke layer */}
          {nearestnationalparke && (
            <Source id="nearest-nationalparke-source" type="geojson" data={nearestnationalparke}>
              <Layer {...nearestnationalparkeLayerStyle} />
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
        
        {/* Results panel */}
        {nearestnationalparke && (
          <div style={{
            position: 'absolute',
            top: '10px',
            right: '10px',
            background: 'white',
            padding: '1rem',
            borderRadius: '8px',
            boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
            maxWidth: '300px',
            zIndex: 1000
          }}>
            <h3 style={{ margin: '0 0 0.5rem 0' }}>Nearest nationalparke</h3>
            {nearestnationalparke.features.map((park, index) => (
              <div key={park.properties.id} style={{ 
                marginBottom: '0.5rem',
                padding: '0.5rem',
                background: '#f8f9fa',
                borderRadius: '4px'
              }}>
                <strong>{park.properties.name}</strong><br />
                <small>{park.properties.distance_meters}m away</small>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default App