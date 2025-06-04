import React, { useState, useRef } from 'react'
import { MapContainer, TileLayer, Marker, Popup, GeoJSON, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// Fix for default markers in react-leaflet
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
})

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Custom hook for handling map clicks
function MapClickHandler({ onMapClick }) {
  useMapEvents({
    click(e) {
      onMapClick(e.latlng)
    },
  })
  return null
}

function App() {
  const [clickedPoint, setClickedPoint] = useState(null)
  const [nearestParks, setNearestParks] = useState(null)
  const [allParks, setAllParks] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showAllParks, setShowAllParks] = useState(false)
  const mapRef = useRef()

  const handleMapClick = async (latlng) => {
    setClickedPoint(latlng)
    setLoading(true)
    setError(null)
    
    try {
      // Create a Point GeoJSON from the clicked coordinates
      const pointGeoJSON = {
        type: "Point",
        coordinates: [latlng.lng, latlng.lat]
      }

      const response = await fetch(`${API_URL}/api/nearest-parks`, {
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
      setNearestParks(data)
      
    } catch (err) {
      setError(`Error finding nearest parks: ${err.message}`)
      console.error('Error:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadAllParks = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(`${API_URL}/api/all-parks`)
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      setAllParks(data)
      setShowAllParks(true)
      
    } catch (err) {
      setError(`Error loading parks: ${err.message}`)
      console.error('Error:', err)
    } finally {
      setLoading(false)
    }
  }

  const clearResults = () => {
    setClickedPoint(null)
    setNearestParks(null)
    setAllParks(null)
    setShowAllParks(false)
    setError(null)
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
        <h1 style={{ margin: 0, fontSize: '1.5rem' }}>GeoJSON Parks Finder</h1>
        <p style={{ margin: '0.5rem 0 0 0', opacity: 0.8 }}>
          Click on the map to find the 5 nearest parks
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
          onClick={loadAllParks}
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
          {loading ? 'Loading...' : 'Show All Parks'}
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
        <MapContainer
          center={[40.7589, -73.9851]} // New York City
          zoom={10}
          style={{ height: '100%', width: '100%' }}
          ref={mapRef}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          
          <MapClickHandler onMapClick={handleMapClick} />
          
          {/* Clicked point marker */}
          {clickedPoint && (
            <Marker position={[clickedPoint.lat, clickedPoint.lng]}>
              <Popup>
                <div>
                  <strong>Clicked Location</strong><br />
                  Lat: {clickedPoint.lat.toFixed(6)}<br />
                  Lng: {clickedPoint.lng.toFixed(6)}
                </div>
              </Popup>
            </Marker>
          )}
          
          {/* Nearest parks */}
          {nearestParks && (
            <GeoJSON 
              data={nearestParks}
              style={{
                fillColor: '#2ecc71',
                weight: 2,
                opacity: 1,
                color: '#27ae60',
                fillOpacity: 0.7
              }}
              onEachFeature={(feature, layer) => {
                layer.bindPopup(`
                  <div>
                    <strong>${feature.properties.name}</strong><br />
                    Distance: ${feature.properties.distance_meters}m
                  </div>
                `)
              }}
            />
          )}
          
          {/* All parks */}
          {showAllParks && allParks && (
            <GeoJSON 
              data={allParks}
              style={{
                fillColor: '#3498db',
                weight: 2,
                opacity: 1,
                color: '#2980b9',
                fillOpacity: 0.5
              }}
              onEachFeature={(feature, layer) => {
                layer.bindPopup(`
                  <div>
                    <strong>${feature.properties.name}</strong>
                  </div>
                `)
              }}
            />
          )}
        </MapContainer>
        
        {/* Results panel */}
        {nearestParks && (
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
            <h3 style={{ margin: '0 0 0.5rem 0' }}>Nearest Parks</h3>
            {nearestParks.features.map((park, index) => (
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