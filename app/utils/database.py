import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, Any
import logging

# Ensure database directory exists
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "geocoding.db")

def get_connection():
    """Create a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def setup_database():
    """Set up the database with required tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create companies table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create addresses table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS addresses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        street TEXT,
        number TEXT,
        city TEXT,
        latitude REAL,
        longitude REAL,
        status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(street, number, city)
    )
    ''')
    
    # Create persons table with new fields
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS persons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        address_id INTEGER,
        company_id INTEGER,
        arrival_time TEXT,
        departure_time TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (address_id) REFERENCES addresses(id),
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )
    ''')
    
    # Create vehicles table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model TEXT NOT NULL,
        vehicle_number TEXT,
        license_plate TEXT,
        driver TEXT,
        seats INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Check if routes table exists and has the correct schema
    cursor.execute("PRAGMA table_info(routes)")
    columns = cursor.fetchall()
    
    # If table exists but has wrong schema, drop and recreate it
    if columns and not any(col[1] == 'start_address' for col in columns):
        cursor.execute("DROP TABLE IF EXISTS route_stops")
        cursor.execute("DROP TABLE IF EXISTS routes")
        
    # Create routes table with correct schema
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        company_id INTEGER,
        vehicle_id INTEGER,
        is_arrival BOOLEAN NOT NULL,
        start_address TEXT,
        end_address TEXT,
        start_lat REAL,
        start_lon REAL,
        end_lat REAL,
        end_lon REAL,
        created_at TEXT,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
    )
    ''')
    
    # Create route_stops table with correct schema
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS route_stops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        route_id INTEGER,
        stop_order INTEGER,
        person_id INTEGER,
        lat REAL,
        lon REAL,
        FOREIGN KEY (route_id) REFERENCES routes(id),
        FOREIGN KEY (person_id) REFERENCES persons(id)
    )
    ''')
    
    # Create route_api_responses table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS route_api_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        route_id INTEGER NOT NULL,
        response_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE
    )
    ''')
    
    conn.commit()
    conn.close()

def get_or_create_company(name):
    """Insert a company if it doesn't exist, or get its ID if it does."""
    if not name:
        return None
        
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if company already exists
    cursor.execute('SELECT id FROM companies WHERE name=?', (name,))
    result = cursor.fetchone()
    
    if result:
        company_id = result[0]
    else:
        # Insert new company
        cursor.execute('INSERT INTO companies (name) VALUES (?)', (name,))
        company_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return company_id
    
def insert_address(street, number, city, latitude, longitude, status):
    """Insert or get address and return its ID."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if address already exists
    cursor.execute('''
    SELECT id FROM addresses 
    WHERE street=? AND number=? AND city=?
    ''', (street, number, city))
    
    result = cursor.fetchone()
    
    if result:
        address_id = result[0]
    else:
        # Insert new address
        cursor.execute('''
        INSERT INTO addresses (street, number, city, latitude, longitude, status)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (street, number, city, latitude, longitude, status))
        address_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return address_id

def insert_person(name, address_id, company_id=None, arrival_time=None, departure_time=None):
    """Insert a person with reference to their address and schedule."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO persons (name, address_id, company_id, arrival_time, departure_time)
    VALUES (?, ?, ?, ?, ?)
    ''', (name, address_id, company_id, arrival_time, departure_time))
    
    person_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return person_id

def get_all_person_address_data():
    """Get all persons with their addresses, company, and schedule information."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT p.name, a.street, a.number, a.city, a.latitude, a.longitude, a.status,
           c.name as company_name, p.arrival_time, p.departure_time
    FROM persons p
    JOIN addresses a ON p.address_id = a.id
    LEFT JOIN companies c ON p.company_id = c.id
    ORDER BY p.name
    ''')
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return results

def get_all_companies():
    """Get all companies from database."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT name FROM companies ORDER BY name')
    results = [row['name'] for row in cursor.fetchall()]
    
    conn.close()
    return results

def insert_vehicle(model, vehicle_number, license_plate, driver, seats):
    """Insert a vehicle into the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        INSERT INTO vehicles (model, vehicle_number, license_plate, driver, seats)
        VALUES (?, ?, ?, ?, ?)
        ''', (model, vehicle_number, license_plate, driver, seats))
        
        vehicle_id = cursor.lastrowid
        conn.commit()
        
        return vehicle_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_all_vehicles():
    """Get all vehicles from the database."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT id, model, vehicle_number, license_plate, driver, seats
    FROM vehicles
    ORDER BY model, vehicle_number
    ''')
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return results

def check_vehicle_exists(vehicle_number=None, license_plate=None):
    """Check if a vehicle with the given number or license plate exists."""
    if not vehicle_number and not license_plate:
        return False
        
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT id FROM vehicles WHERE "
    params = []
    
    if vehicle_number:
        query += "vehicle_number = ?"
        params.append(vehicle_number)
        
    if license_plate:
        if vehicle_number:
            query += " OR "
        query += "license_plate = ?"
        params.append(license_plate)
    
    cursor.execute(query, params)
    result = cursor.fetchone()
    
    conn.close()
    
    return result is not None

def delete_vehicle(vehicle_id):
    """Delete a vehicle from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_companies_with_persons():
    """Get all companies that have persons assigned to them."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT DISTINCT c.id, c.name
    FROM companies c
    JOIN persons p ON p.company_id = c.id
    ORDER BY c.name
    ''')
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return results

def get_persons_by_company(company_id, arrival=True):
    """
    Get all persons for a specific company with their addresses.
    If arrival=True, get persons who need transportation TO the company (morning).
    If arrival=False, get persons who need transportation FROM the company (evening).
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # For arrival routes, we filter by the arrival time field
    # For departure routes, we filter by the departure time field
    time_field = 'p.arrival_time' if arrival else 'p.departure_time'
    
    cursor.execute(f'''
    SELECT p.id, p.name, a.street, a.number, a.city, a.latitude, a.longitude, 
           {time_field} as scheduled_time
    FROM persons p
    JOIN addresses a ON p.address_id = a.id
    WHERE p.company_id = ? 
    AND {time_field} IS NOT NULL
    AND a.latitude IS NOT NULL 
    AND a.longitude IS NOT NULL
    ORDER BY p.name
    ''', (company_id,))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return results

def get_company_address(company_id):
    """Get the most common address for employees of a company (assumed to be the company location)."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT a.id, a.street, a.number, a.city, a.latitude, a.longitude, COUNT(*) as count
    FROM addresses a
    JOIN persons p ON p.address_id = a.id
    WHERE p.company_id = ?
    GROUP BY a.street, a.number, a.city
    ORDER BY count DESC
    LIMIT 1
    ''', (company_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return dict(result)
    return None

def create_route(name, company_id, vehicle_id, is_arrival, start_address, end_address, 
                start_lat, start_lon, end_lat, end_lon, created_at=None):
    """
    Create a new route in the database
    
    Args:
        name: Route name
        company_id: ID of the company
        vehicle_id: ID of the vehicle assigned to the route
        is_arrival: Boolean indicating if this is an arrival route (True) or departure route (False)
        start_address: Text representation of the starting point
        end_address: Text representation of the ending point
        start_lat: Latitude of the starting point
        start_lon: Longitude of the starting point
        end_lat: Latitude of the ending point
        end_lon: Longitude of the ending point
        created_at: Timestamp when the route was created (defaults to current time)
        
    Returns:
        ID of the newly created route
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if created_at is None:
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO routes (
        name, company_id, vehicle_id, is_arrival, 
        start_address, end_address, 
        start_lat, start_lon, end_lat, end_lon, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, company_id, vehicle_id, is_arrival, 
          start_address, end_address, 
          start_lat, start_lon, end_lat, end_lon, created_at))
    
    route_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return route_id

def add_route_stop(route_id, stop_order, person_id, lat, lon):
    """
    Add a stop to a route
    
    Args:
        route_id: ID of the route
        stop_order: Order of the stop in the route sequence
        person_id: ID of the person at this stop
        lat: Latitude of the stop
        lon: Longitude of the stop
        
    Returns:
        ID of the newly created stop
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO route_stops (route_id, stop_order, person_id, lat, lon)
    VALUES (?, ?, ?, ?, ?)
    ''', (route_id, stop_order, person_id, lat, lon))
    
    stop_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return stop_id

def get_all_routes():
    """
    Get all routes from the database
    
    Returns:
        List of route dictionaries
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT r.id, r.name, r.company_id, c.name as company_name,
           r.vehicle_id, r.is_arrival, r.created_at
    FROM routes r
    LEFT JOIN companies c ON r.company_id = c.id
    ORDER BY r.created_at DESC
    ''')
    
    routes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return routes

def get_route_details(route_id):
    """
    Get detailed information about a route, including all stops
    
    Args:
        route_id: ID of the route to retrieve
        
    Returns:
        Dictionary with route details and list of stops
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get route info - ensure column names match the table schema
    cursor.execute('''
    SELECT r.id, r.name, r.company_id, c.name as company_name,
           r.vehicle_id, v.model as vehicle_model, v.license_plate as vehicle_plate, 
           r.is_arrival, r.start_address, r.end_address,
           r.start_lat, r.start_lon, r.end_lat, r.end_lon, r.created_at
    FROM routes r
    LEFT JOIN companies c ON r.company_id = c.id
    LEFT JOIN vehicles v ON r.vehicle_id = v.id
    WHERE r.id = ?
    ''', (route_id,))
    
    route_result = cursor.fetchone()
    if not route_result:
        conn.close()
        return None
        
    route = dict(route_result)
    
    # Get stops
    cursor.execute('''
    SELECT rs.id, rs.stop_order, rs.person_id, rs.lat, rs.lon,
           p.name as person_name, a.street, a.number, a.city
    FROM route_stops rs
    LEFT JOIN persons p ON rs.person_id = p.id
    LEFT JOIN addresses a ON p.address_id = a.id
    WHERE rs.route_id = ?
    ORDER BY rs.stop_order
    ''', (route_id,))
    
    stops = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {
        'route': route,
        'stops': stops
    }

def save_route_api_response(route_id: int, api_response: dict) -> bool:
    """
    Saves the raw Geoapify API response for a route to the database.
    
    Args:
        route_id: ID of the route in the database
        api_response: Dictionary containing the API response
        
    Returns:
        True if successful, False otherwise
    """
    conn = get_connection()  # Use standard connection method
    cursor = conn.cursor()
    
    try:
        # Serialize the API response to JSON
        response_json = json.dumps(api_response)
        
        # Save the response to the database
        cursor.execute(
            "INSERT INTO route_api_responses (route_id, response_json, created_at) VALUES (?, ?, ?)",
            (route_id, response_json, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Error saving API response: {e}")
        return False
    finally:
        conn.close()

def get_route_api_response(route_id: int) -> Dict[str, Any]:
    """
    Retrieves the saved API response for a route.
    
    Args:
        route_id: ID of the route
        
    Returns:
        Dictionary containing the deserialized API response or None
    """
    conn = get_connection()  # Use standard connection method
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT response_json FROM route_api_responses WHERE route_id = ? ORDER BY created_at DESC LIMIT 1",
            (route_id,)
        )
        result = cursor.fetchone()
        
        if result and result[0]:
            return json.loads(result[0])
        return None
    except Exception as e:
        logging.error(f"Error retrieving API response: {e}")
        return None
    finally:
        conn.close()
