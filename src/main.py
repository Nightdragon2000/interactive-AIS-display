import cv2
import mediapipe as mp
import numpy as np
import json
import pygame
import rasterio
import psycopg2
import time
import os
from datetime import datetime, timedelta

# =============================================================================
# DATABASE CONFIGURATION - MODIFY THESE VALUES FOR YOUR SETUP
# =============================================================================
DB_HOST = "localhost"
DB_NAME = "Ship_DB"
DB_USER = "postgres"
DB_PASSWORD = "2703"
DB_PORT = 5432  # Default PostgreSQL port
# =============================================================================

# Load camera and projector coordinates
with open('../data/camera_projector_coordinates.json', 'r') as f:
    coordinates = json.load(f)

camera_coords = coordinates["camera"]
camera_top_left = camera_coords["tl_corner"]
camera_bottom_right = camera_coords["br_corner"]

projector_coords = coordinates["projector"]
projector_top_left = projector_coords["tl_corner"]
projector_bottom_right = projector_coords["br_corner"]

# Create polygon for camera region
polygon_points = [
    camera_top_left,
    [camera_bottom_right[0], camera_top_left[1]],
    camera_bottom_right,
    [camera_top_left[0], camera_bottom_right[1]]
]
polygon_array = np.array(polygon_points, np.int32).reshape((-1, 1, 2))

# Image settings
image_x = projector_top_left[0]
image_y = projector_top_left[1]
image_width = projector_bottom_right[0] - projector_top_left[0]
image_height = projector_bottom_right[1] - projector_top_left[1]

# Panel settings
PANEL_WIDTH = 200
PANEL_HEIGHT = 150
PANEL_OFFSET = 50
SHIP_DETECTION_THRESHOLD = 20
HOVER_TIME_REQUIRED = 2.0
DISPLAY_TIME = 15.0

# Gesture settings
THUMB_INDEX_CLOSE_THRESHOLD = 0.05  # Distance threshold for thumb-index touch
GESTURE_HOLD_TIME = 0.5  # Time to hold gesture before triggering close

# Load georeferenced image
def load_map_image():
    image_path = "../data/images/georeferenced_image.tif"
    with rasterio.open(image_path) as src:
        image_data = src.read()
        transform = src.transform
    
    # Handle different image formats
    num_bands = image_data.shape[0]
    if num_bands > 3:
        image_data = image_data[:3, :, :]
    elif num_bands == 1:
        image_data = np.stack([image_data[0]] * 3, axis=0)
    
    # Process image data
    image_data = np.transpose(image_data, (1, 2, 0))
    image_data = np.clip(image_data, 0, 255).astype(np.uint8)
    image_data = np.flipud(image_data)
    image_data = np.rot90(image_data, 3)
    
    return image_data, transform

# Initialize components
def initialize_components():
    # MediaPipe setup
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)
    mp_drawing = mp.solutions.drawing_utils
    
    # Pygame setup
    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    
    # OpenCV setup
    cap = cv2.VideoCapture(0)
    
    return hands, mp_drawing, screen, cap

# Database connection
def connect_database():
    """
    Connect to PostgreSQL database using the configuration variables at the top of the file.
    Modify the DB_* variables at the top of this script to match your database setup.
    """
    try:
        return psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        print("Please check your database configuration variables at the top of the script.")
        raise

# Convert geographic coordinates to pixel coordinates
def geo_to_pixel(lat, lon, transform, src_width, src_height):
    row, col = rasterio.transform.rowcol(transform, lon, lat)
    pixel_x = int(col * image_width / src_width)
    pixel_y = int(row * image_height / src_height)
    return pixel_x, pixel_y

# Check if thumb and index finger are touching
def is_thumb_index_touching(hand_landmarks):
    """
    Check if thumb tip and index finger tip are close enough to be considered touching
    """
    thumb_tip = hand_landmarks.landmark[mp.solutions.hands.HandLandmark.THUMB_TIP]
    index_tip = hand_landmarks.landmark[mp.solutions.hands.HandLandmark.INDEX_FINGER_TIP]
    
    # Calculate distance between thumb and index finger tips
    distance = np.sqrt((thumb_tip.x - index_tip.x)**2 + (thumb_tip.y - index_tip.y)**2)
    
    return distance < THUMB_INDEX_CLOSE_THRESHOLD

# Fetch ship positions from database
def fetch_ship_positions(cursor, transform, src_width, src_height):
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=10)
    
    query = """
        SELECT s.mmsi, s.latitude, s.longitude, s.image_path, s.name, s.destination, s.eta, s.navigation_status
        FROM ships_syros s
        INNER JOIN (
            SELECT mmsi, MAX(timestamp) AS latest_timestamp
            FROM ships_syros
            WHERE timestamp BETWEEN %s AND %s
            GROUP BY mmsi
        ) latest ON s.mmsi = latest.mmsi AND s.timestamp = latest.latest_timestamp
        ORDER BY s.timestamp DESC;
    """
    
    cursor.execute(query, (start_time, end_time))
    records = cursor.fetchall()
    
    ship_positions = []
    for mmsi, lat, lon, img_path, name, dest, eta, status in records:
        pixel_pos = geo_to_pixel(lat, lon, transform, src_width, src_height)
        ship_positions.append((mmsi, pixel_pos, img_path, name, dest, eta, status))
    
    return ship_positions

# Check if point is near a ship
def is_near_ship(ship_pos, x, y, threshold=SHIP_DETECTION_THRESHOLD):
    ship_x, ship_y = ship_pos
    distance = np.hypot(ship_x - x, ship_y - y)
    return distance <= threshold

# Draw ship information panel
def draw_ship_panel(screen, ship_info):
    mmsi, pos, img_path, name, dest, eta, status = ship_info
    
    # Panel position
    panel_x = image_x + image_width - PANEL_WIDTH - PANEL_OFFSET
    panel_y = image_y + 10
    
    # Draw panel background
    pygame.draw.rect(screen, (255, 255, 255), (panel_x, panel_y, PANEL_WIDTH, PANEL_HEIGHT))
    
    # Fonts
    title_font = pygame.font.Font('../data/fonts/DejaVuSans-Bold.ttf', 16)
    text_font = pygame.font.Font('../data/fonts/DejaVuSans.ttf', 10)
    label_font = pygame.font.Font('../data/fonts/DejaVuSans-Bold.ttf', 10)
    
    # Ship name
    name_surface = title_font.render(name, True, (0, 0, 0))
    screen.blit(name_surface, (panel_x + 10, panel_y + 10))
    
    # Ship image
    image_height_panel = PANEL_HEIGHT // 3
    if os.path.exists(img_path):
        ship_image = pygame.image.load(img_path)
        ship_image = pygame.transform.scale(ship_image, (PANEL_WIDTH - 20, image_height_panel))
        screen.blit(ship_image, (panel_x + 10, panel_y + 40))
        actual_img_height = ship_image.get_height()
    else:
        # No image available
        pygame.draw.rect(screen, (200, 200, 200), 
                        (panel_x + 10, panel_y + 40, PANEL_WIDTH - 20, image_height_panel))
        no_img_text = text_font.render("No Image Available", True, (0, 0, 0))
        text_rect = no_img_text.get_rect(center=(panel_x + PANEL_WIDTH // 2, 
                                               panel_y + 40 + image_height_panel // 2))
        screen.blit(no_img_text, text_rect)
        actual_img_height = image_height_panel
    
    # Ship details
    details_y = panel_y + 40 + actual_img_height + 10
    
    if status == "Moored":
        status_label = label_font.render("Status:", True, (0, 0, 0))
        status_value = text_font.render("Moored / Στάσιμο", True, (0, 0, 0))
        screen.blit(status_label, (panel_x + 10, details_y))
        screen.blit(status_value, (panel_x + 10 + status_label.get_width() + 5, details_y))
    else:
        # Destination
        dest_label = label_font.render("Destination:", True, (0, 0, 0))
        dest_value = text_font.render(dest, True, (0, 0, 0))
        screen.blit(dest_label, (panel_x + 10, details_y))
        screen.blit(dest_value, (panel_x + 10 + dest_label.get_width() + 5, details_y))
        
        # ETA
        eta_label = label_font.render("ETA:", True, (0, 0, 0))
        eta_value = text_font.render(eta, True, (0, 0, 0))
        screen.blit(eta_label, (panel_x + 10, details_y + 20))
        screen.blit(eta_value, (panel_x + 10 + eta_label.get_width() + 5, details_y + 20))

# Main application
def main():
    # Load map and initialize components
    image_data, transform = load_map_image()
    hands, mp_drawing, screen, cap = initialize_components()
    conn = connect_database()
    cursor = conn.cursor()
    
    # Get source dimensions for coordinate conversion
    with rasterio.open("../data/images/georeferenced_image.tif") as src:
        src_width, src_height = src.width, src.height
    
    # Create image surface
    image_surface = pygame.surfarray.make_surface(image_data)
    image_surface = pygame.transform.scale(image_surface, (image_width, image_height))
    
    # Initialize variables
    ship_positions = fetch_ship_positions(cursor, transform, src_width, src_height)
    near_ship_start = None
    current_mmsi = None
    selected_mmsi = None
    select_start = None
    
    # Gesture tracking variables
    thumb_index_touching = False
    gesture_start_time = None
    
    # Set refresh timer
    pygame.time.set_timer(pygame.USEREVENT, 60000)  # Refresh every minute
    
    running = True
    while running and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        # Process camera frame
        frame = cv2.flip(frame, 1)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(frame_rgb)
        
        # Draw camera region outline
        cv2.polylines(frame, [polygon_array], True, (255, 0, 0), 2)
        
        # Redraw map
        image_surface = pygame.surfarray.make_surface(image_data)
        image_surface = pygame.transform.scale(image_surface, (image_width, image_height))
        
        # Draw ship positions
        for mmsi, (px, py), _, _, _, _, _ in ship_positions:
            color = (255, 255, 0) if mmsi == selected_mmsi else (255, 0, 0)
            pygame.draw.circle(image_surface, color, (px, py), 5)
        
        # Process hand landmarks
        if result.multi_hand_landmarks:
            for hand_landmarks in result.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp.solutions.hands.HAND_CONNECTIONS)
                
                # Check for thumb-index touching gesture
                is_touching = is_thumb_index_touching(hand_landmarks)
                
                if is_touching and not thumb_index_touching:
                    # Start of gesture
                    thumb_index_touching = True
                    gesture_start_time = time.time()
                    # Visual feedback - draw a circle around the touching fingers
                    thumb_tip = hand_landmarks.landmark[mp.solutions.hands.HandLandmark.THUMB_TIP]
                    thumb_x = int(thumb_tip.x * frame.shape[1])
                    thumb_y = int(thumb_tip.y * frame.shape[0])
                    cv2.circle(frame, (thumb_x, thumb_y), 15, (0, 255, 255), 3)  # Yellow circle
                elif not is_touching:
                    # End of gesture
                    thumb_index_touching = False
                    gesture_start_time = None
                
                # Check if gesture has been held long enough to trigger close
                if (thumb_index_touching and gesture_start_time and 
                    time.time() - gesture_start_time >= GESTURE_HOLD_TIME and 
                    selected_mmsi):
                    selected_mmsi = None  # Close the panel
                    thumb_index_touching = False
                    gesture_start_time = None
                    print("Panel closed by thumb-index gesture")  # Debug output
                
                # Get finger tip position for ship selection
                index_tip = hand_landmarks.landmark[mp.solutions.hands.HandLandmark.INDEX_FINGER_TIP]
                finger_x = int(index_tip.x * frame.shape[1])
                finger_y = int(index_tip.y * frame.shape[0])
                
                # Check if finger is in camera region
                if cv2.pointPolygonTest(polygon_array, (finger_x, finger_y), False) >= 0:
                    cv2.circle(frame, (finger_x, finger_y), 10, (0, 255, 0), -1)
                    
                    # Only process ship selection if not performing close gesture
                    if not thumb_index_touching:
                        # Map to image coordinates (fix horizontal inversion)
                        map_x = int((camera_bottom_right[0] - finger_x) / 
                                  (camera_bottom_right[0] - camera_top_left[0]) * image_width)
                        map_y = int((finger_y - camera_top_left[1]) / 
                                  (camera_bottom_right[1] - camera_top_left[1]) * image_height)
                        
                        pygame.draw.circle(image_surface, (0, 255, 0), (map_x, map_y), 10)
                        
                        # Check if near any ship
                        ship_found = False
                        for mmsi, (ship_x, ship_y), _, _, _, _, _ in ship_positions:
                            if is_near_ship((ship_x, ship_y), map_x, map_y):
                                if current_mmsi != mmsi:
                                    near_ship_start = time.time()
                                    current_mmsi = mmsi
                                elif time.time() - near_ship_start >= HOVER_TIME_REQUIRED:
                                    selected_mmsi = mmsi
                                    select_start = time.time()
                                ship_found = True
                                break
                        
                        if not ship_found:
                            current_mmsi = None
        else:
            # No hands detected - reset gesture state
            thumb_index_touching = False
            gesture_start_time = None
        
        # Display webcam feed
        cv2.imshow('Webcam Feed', frame)
        
        # Display map
        screen.fill((0, 0, 0))
        screen.blit(image_surface, (image_x, image_y))
        
        # Show selected ship panel
        if selected_mmsi:
            selected_ship = next((ship for ship in ship_positions if ship[0] == selected_mmsi), None)
            if selected_ship:
                draw_ship_panel(screen, selected_ship)
                
                # Hide panel after display time (only if not closed by gesture)
                if time.time() - select_start >= DISPLAY_TIME:
                    selected_mmsi = None
        
        pygame.display.flip()
        
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
            elif event.type == pygame.USEREVENT:
                ship_positions = fetch_ship_positions(cursor, transform, src_width, src_height)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            running = False
    
    # Cleanup
    cap.release()
    pygame.quit()
    cv2.destroyAllWindows()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()