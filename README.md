# Interactive Ship Tracking System

An advanced real-time ship tracking system that combines AIS (Automatic Identification System) data decoding, interactive map projection, and hand gesture recognition to provide an immersive maritime monitoring experience.

## Features

- **Real-time AIS Data Processing**: Decode AIS messages from ships and store vessel information
- **Interactive Map Projection**: Project georeferenced maps with live ship positions
- **Hand Gesture Recognition**: Use hand gestures to interact with ship information
- **Database Integration**: PostgreSQL database for storing ship data and images
- **Ship Information Display**: Fetch and display detailed ship information including images, destinations, and ETA
- **Camera/Projector Calibration**: Precision calibration system for accurate projection mapping

## Prerequisites

### Hardware Requirements
- Webcam (for hand gesture recognition and calibration)
- Projector (for map display)
- AIS receiver connected via serial port (COM port on Windows, USB port on Linux/Mac)

### Software Requirements
- Python 3.8 or higher
- PostgreSQL database server

## Installation

### 1. Clone the Repository
```bash
git clone 
cd ship-tracking-system
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Database Setup

#### Install PostgreSQL
- **Windows**: Download from [postgresql.org](https://www.postgresql.org/downloads/)
- **Linux**: `sudo apt-get install postgresql postgresql-contrib`
- **macOS**: `brew install postgresql`

#### Create Database and Schema
1. Start PostgreSQL service
2. Create a new database:
```sql
CREATE DATABASE Ship_DB;
```

3. Run the schema creation script:
```bash
psql -U postgres -d DATABASE -f data/sql/create_schema.sql
```

### 4. Configuration

#### Update Database Configuration
Edit the database configuration in both `decode_ais.py` and `main.py`:

**In `decode_ais.py`:**
```python
DB_HOST = "localhost"       # Your database host
DB_NAME = "DATABASE"         # Your database name
DB_USER = "postgres"        # Your database username
DB_PASSWORD = "PASSWORD"  # Your database password
DB_PORT = 5432             # Your database port
```

**In `main.py`:**
```python
DB_HOST = "localhost"
DB_NAME = "DATABASE"
DB_USER = "postgres"
DB_PASSWORD = "PASSWORD"
DB_PORT = 5432
```

#### Update Serial Port Configuration
Edit the serial port configuration in `decode_ais.py`:
```python
SERIAL_PORT = "COM5"        # Windows: "COM3", "COM5", etc.
                           # Linux/Mac: "/dev/ttyUSB0", "/dev/ttyACM0", etc.
BAUD_RATE = 4800           # Standard AIS baud rate
```

## 🚀 Quick Start

### First Time Setup

#### 1. Run Calibration (Required for first-time setup)
```bash
cd src
python calibration.py
```

**Calibration Process:**
1. **Camera Calibration**: 
   - Position and resize the rectangle to match your projection area
   - Use mouse to drag corners and move the rectangle
   - Press `ENTER` to save, `ESC` to cancel

2. **Projector Calibration**:
   - Position and scale the map image on your projection surface
   - Use `+`/`-` keys to scale the image
   - Drag the image to position it correctly
   - Press `ESC` to save and exit

### Running the System

#### 2. Start AIS Data Collection
```bash
cd src
python decode_ais.py
```
- Press `s` to start reading from the serial port
- Press `e` to stop and exit
- Keep this running in a separate terminal/command prompt

#### 3. Start Main Application
```bash
python main.py
```