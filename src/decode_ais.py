import serial
import keyboard
from pyais import decode
from datetime import datetime
import psycopg2
import requests
from bs4 import BeautifulSoup
import os

# =============================================================================
# CONFIGURATION - MODIFY THESE VALUES FOR YOUR SETUP
# =============================================================================

# Serial Port Configuration
SERIAL_PORT = "COM5"        # Change this to your serial port (e.g., "COM3", "/dev/ttyUSB0")
BAUD_RATE = 4800           # AIS standard baud rate
SERIAL_TIMEOUT = 2         # Serial read timeout in seconds

# Database Configuration
DB_HOST = "localhost"       # Database server address
DB_NAME = "DATABASE"        # Database name
DB_USER = "postgres"       # Database username
DB_PASSWORD = "PASSWORD"       # Database password
DB_PORT = 5432             # Database port (default PostgreSQL port)

# File System Configuration
IMAGE_DIRECTORY = '../images/Ships_MMSI'  # Directory to save ship images

# =============================================================================

# HTTP headers for web scraping
HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    'Referer': 'https://www.google.com/',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}

def setup_serial_connection():
    """Initialize serial connection"""
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=SERIAL_TIMEOUT)
        print(f"Serial connection established on {SERIAL_PORT}")
        return ser
    except Exception as e:
        print(f"Failed to connect to serial port {SERIAL_PORT}: {e}")
        print("Please check your SERIAL_PORT configuration at the top of the script.")
        return None

def connect_database():
    """Connect to PostgreSQL database using configuration variables"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = conn.cursor()
        print(f"Connected to PostgreSQL database '{DB_NAME}' on {DB_HOST}:{DB_PORT}")
        return conn, cursor
    except psycopg2.Error as e:
        print(f"Database connection failed: {e}")
        print("Please check your database configuration variables at the top of the script:")
        print(f"  DB_HOST: {DB_HOST}")
        print(f"  DB_NAME: {DB_NAME}")
        print(f"  DB_USER: {DB_USER}")
        print(f"  DB_PORT: {DB_PORT}")
        return None, None

def fetch_ship_details(mmsi):
    """Fetch ship details from vesselfinder.com"""
    url = f'https://www.vesselfinder.com/vessels/details/{mmsi}'
    
    try:
        response = requests.get(url, headers=HTTP_HEADERS)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        ship_details = {
            'name': None,
            'image_url': None,
            'destination': None,
            'eta': None
        }
        
        # Extract ship name and image
        ship_details['name'], ship_details['image_url'] = extract_ship_basic_info(soup)
        

        
        # Extract destination and ETA
        ship_details['destination'], ship_details['eta'] = extract_destination_eta(soup)
        
        return ship_details
        
    except Exception as e:
        print(f"Error fetching ship details for MMSI {mmsi}: {e}")
        return None

def extract_ship_basic_info(soup):
    """Extract ship name and image URL from soup"""
    ship_name = None
    ship_image_url = None
    
    ship_info_div = soup.find('div', class_='col vfix-top npr')
    if ship_info_div:
        img_tag = ship_info_div.find('img', class_='main-photo')
        if img_tag:
            ship_name = img_tag.get('title', '').strip()
            ship_image_url = img_tag.get('src', '')
    
    return ship_name, ship_image_url


def extract_destination_eta(soup):
    """Extract destination and ETA from soup"""
    destination = None
    eta = None
    
    vi_r1_div = soup.find('div', class_='vi__r1 vi__sbt')
    if vi_r1_div:
        # Extract destination
        a_tag = vi_r1_div.find('a', class_='_npNa')
        if a_tag:
            destination = a_tag.text.split(',')[0].strip()
        
        # Extract ETA
        value_div = vi_r1_div.find('div', class_='_value')
        if value_div:
            span_tag = value_div.find('span')
            if span_tag:
                eta = span_tag.text.strip().split(':', 1)[-1].strip()
    
    return destination, eta

def download_ship_image(image_url, mmsi):
    """Download ship image and save to local directory"""
    if not image_url:
        return None
    
    try:
        image_response = requests.get(image_url, stream=True)
        if image_response.status_code == 200:
            os.makedirs(IMAGE_DIRECTORY, exist_ok=True)
            image_path = os.path.join(IMAGE_DIRECTORY, f'{mmsi}.jpg')
            
            with open(image_path, 'wb') as image_file:
                for chunk in image_response.iter_content(1024):
                    image_file.write(chunk)
            
            print(f"Image saved to {image_path}")
            return image_path
        else:
            print(f"Failed to download image: HTTP {image_response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error downloading image: {e}")
        return None

def save_ship_data(cursor, conn, timestamp, mmsi, lat, lon, ship_details, image_path):
    """Save ship data to database"""
    try:
        cursor.execute(
            """
            INSERT INTO ships (timestamp, mmsi, latitude, longitude, name, image_path, destination, eta) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (timestamp, mmsi, lat, lon, ship_details['name'], image_path, 
              ship_details['destination'], ship_details['eta'])
        )
        conn.commit()
        print("Data saved to database successfully")
        
    except Exception as e:
        print(f"Database error: {e}")
        conn.rollback()

def process_ais_message(line, cursor, conn):
    """Process a single AIS message"""
    try:
        # Decode the AIS message
        ais_message = decode(line)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Extract basic AIS data
        mmsi = ais_message.mmsi
        lat = ais_message.lat
        lon = ais_message.lon
        
        print(f"Decoded AIS message:")
        print(f"  MMSI: {mmsi}")
        print(f"  Position: {lat}, {lon}")
        print(f"  Timestamp: {timestamp}")
        
        # Fetch additional ship details
        print("Fetching ship details...")
        ship_details = fetch_ship_details(mmsi)
        
        if ship_details:
            print(f"Ship Details:")
            print(f"  Name: {ship_details['name']}")
            print(f"  Destination: {ship_details['destination']}")
            print(f"  ETA: {ship_details['eta']}")
            
            # Download ship image
            image_path = download_ship_image(ship_details['image_url'], mmsi)
            
            # Save to database
            save_ship_data(cursor, conn, timestamp, mmsi, lat, lon, ship_details, image_path)
        else:
            print("Could not fetch ship details")
            
        print("-" * 50)
        
    except Exception as e:
        print(f"Failed to process AIS message: {line}")
        print(f"Error: {e}")

def wait_for_start():
    """Wait for user to press 's' to start"""
    print("Press 's' to start reading from the serial port.")
    print("Press 'e' to stop reading from the serial port and exit the script.")
    
    while True:
        if keyboard.is_pressed("s"):
            print("Starting AIS data collection...")
            break

def main():
    """Main application function"""
    print("AIS Data Decoder - Configuration:")
    print(f"  Serial Port: {SERIAL_PORT}")
    print(f"  Database: {DB_NAME} on {DB_HOST}:{DB_PORT}")
    print(f"  Image Directory: {IMAGE_DIRECTORY}")
    print("-" * 50)
    
    ser = None
    conn = None
    cursor = None
    
    try:
        # Setup connections
        ser = setup_serial_connection()
        if not ser:
            return
        
        conn, cursor = connect_database()
        if not conn or not cursor:
            return
        
        # Wait for user to start
        wait_for_start()
        
        # Main data collection loop
        print("Reading AIS data... Press 'e' to exit.")
        
        while True:
            if keyboard.is_pressed("e"):
                print("Stopping AIS data collection...")
                break
            
            # Read from serial port
            line = ser.readline().decode("ascii", errors="replace").strip()
            
            if line:
                process_ais_message(line, cursor, conn)
    
    except KeyboardInterrupt:
        print("Script interrupted by user.")
    
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    finally:
        # Cleanup
        if ser:
            ser.close()
            print("Serial port closed.")
        
        if cursor:
            cursor.close()
        
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    main()