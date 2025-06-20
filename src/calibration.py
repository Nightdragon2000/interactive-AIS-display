import cv2
import numpy as np
import json
import os
import pygame
import rasterio
from rasterio.transform import from_gcps
from rasterio.control import GroundControlPoint
from rasterio.crs import CRS

# Configuration constants
CAMERA_PROJECTOR_JSON_PATH = '../data/camera_projector_coordinates.json'
SOURCE_IMAGE_PATH = '../data/images/digital_map.png'
GEOREFERENCED_IMAGE_PATH = '../data/images/georeferenced_image.tif'


# Calibration constants
INITIAL_RECTANGLE_SIZE = (200, 200)
INITIAL_RECTANGLE_POSITION = (100, 100)
CORNER_DETECTION_THRESHOLD = 10
SCALE_STEP = 0.01
MIN_SCALE = 0.1
MAX_SCALE = 5.0

# Ground control points for georeferencing
IMAGE_COORDINATES = [(55, 343), (474, 37), (558, 201), (696, 264)]
REAL_COORDINATES = [(37.362463, 24.876547), (37.529289, 25.163953), 
                   (37.440502, 25.220772), (37.405848, 25.317049)]

def create_georeferenced_image():
    """Create georeferenced image from digital map using ground control points"""
    try:
        # Create ground control points
        gcps = []
        for image_point, real_point in zip(IMAGE_COORDINATES, REAL_COORDINATES):
            gcp = GroundControlPoint(
                row=image_point[1], 
                col=image_point[0], 
                x=real_point[1], 
                y=real_point[0]
            )
            gcps.append(gcp)
        
        # Create transformation from GCPs
        transform = from_gcps(gcps)
        
        # Read source image
        with rasterio.open(SOURCE_IMAGE_PATH) as src:
            image_data = src.read()
            image_data = image_data.transpose(1, 2, 0)
            metadata = src.meta.copy()
        
        # Update metadata with georeference information
        metadata.update({
            'transform': transform,
            'crs': CRS.from_string('WGS84'),
            'count': image_data.shape[2],
        })
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(GEOREFERENCED_IMAGE_PATH), exist_ok=True)
        
        # Save georeferenced image
        with rasterio.open(GEOREFERENCED_IMAGE_PATH, 'w', **metadata) as dst:
            for band in range(image_data.shape[2]):
                dst.write(image_data[:, :, band], band + 1)
        
        print(f"Georeferenced image saved at {GEOREFERENCED_IMAGE_PATH}")
        return True
        
    except Exception as e:
        print(f"Error creating georeferenced image: {e}")
        return False

def load_existing_coordinates():
    """Load existing coordinates from JSON file"""
    if os.path.exists(CAMERA_PROJECTOR_JSON_PATH):
        try:
            with open(CAMERA_PROJECTOR_JSON_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading coordinates: {e}")
    return {}

def save_coordinates(camera_coords=None, projector_coords=None):
    """Save coordinates to JSON file"""
    try:
        # Load existing data
        data = load_existing_coordinates()
        
        # Update with new coordinates
        if camera_coords:
            data['camera'] = camera_coords
        
        if projector_coords:
            data['projector'] = projector_coords
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(CAMERA_PROJECTOR_JSON_PATH), exist_ok=True)
        
        # Save to file
        with open(CAMERA_PROJECTOR_JSON_PATH, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Coordinates saved to {CAMERA_PROJECTOR_JSON_PATH}")
        return True
        
    except Exception as e:
        print(f"Error saving coordinates: {e}")
        return False

class RectangleSelector:
    """Class to handle rectangle selection for camera calibration"""
    
    def __init__(self):
        self.top_left = INITIAL_RECTANGLE_POSITION
        self.bottom_right = (
            INITIAL_RECTANGLE_POSITION[0] + INITIAL_RECTANGLE_SIZE[0],
            INITIAL_RECTANGLE_POSITION[1] + INITIAL_RECTANGLE_SIZE[1]
        )
        self.dragging_mode = None
        self.drag_offset = (0, 0)
    
    def handle_mouse_event(self, event, x, y, flags, param):
        """Handle mouse events for rectangle selection"""
        if event == cv2.EVENT_LBUTTONDOWN:
            self._handle_mouse_down(x, y)
        elif event == cv2.EVENT_MOUSEMOVE:
            self._handle_mouse_move(x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            self._handle_mouse_up()
    
    def _handle_mouse_down(self, x, y):
        """Handle mouse button down event"""
        # Check if clicking on top-left corner
        if self._is_near_point(self.top_left, x, y):
            self.dragging_mode = 'top_left'
        # Check if clicking on bottom-right corner
        elif self._is_near_point(self.bottom_right, x, y):
            self.dragging_mode = 'bottom_right'
        # Check if clicking inside rectangle
        elif self._is_inside_rectangle(x, y):
            self.dragging_mode = 'move'
            self.drag_offset = (x - self.top_left[0], y - self.top_left[1])
        else:
            self.dragging_mode = None
    
    def _handle_mouse_move(self, x, y):
        """Handle mouse move event"""
        if self.dragging_mode == 'top_left':
            self.top_left = (x, y)
        elif self.dragging_mode == 'bottom_right':
            self.bottom_right = (x, y)
        elif self.dragging_mode == 'move':
            width = self.bottom_right[0] - self.top_left[0]
            height = self.bottom_right[1] - self.top_left[1]
            self.top_left = (x - self.drag_offset[0], y - self.drag_offset[1])
            self.bottom_right = (self.top_left[0] + width, self.top_left[1] + height)
    
    def _handle_mouse_up(self):
        """Handle mouse button up event"""
        self.dragging_mode = None
    
    def _is_near_point(self, point, x, y):
        """Check if coordinates are near a specific point"""
        return (abs(point[0] - x) < CORNER_DETECTION_THRESHOLD and 
                abs(point[1] - y) < CORNER_DETECTION_THRESHOLD)
    
    def _is_inside_rectangle(self, x, y):
        """Check if coordinates are inside rectangle"""
        return (self.top_left[0] < x < self.bottom_right[0] and 
                self.top_left[1] < y < self.bottom_right[1])
    
    def draw_on_frame(self, frame):
        """Draw rectangle and corner points on frame"""
        # Draw rectangle
        cv2.rectangle(frame, self.top_left, self.bottom_right, (255, 0, 0), 2)
        
        # Draw corner points
        cv2.circle(frame, self.top_left, 5, (0, 0, 255), -1)
        cv2.circle(frame, self.bottom_right, 5, (0, 0, 255), -1)
    
    def get_coordinates(self):
        """Get current rectangle coordinates"""
        return {
            "tl_corner": self.top_left,
            "br_corner": self.bottom_right
        }

def calibrate_camera():
    """Calibrate camera by selecting rectangle region"""
    print("Camera Calibration:")
    print("- Drag corners to resize rectangle")
    print("- Drag inside rectangle to move it")
    print("- Press ENTER to save coordinates")
    print("- Press ESC to cancel")
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera")
        return False
    
    # Create rectangle selector
    selector = RectangleSelector()
    
    # Set up window and mouse callback
    window_name = "Camera Calibration - Select Rectangle"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, selector.handle_mouse_event)
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: Could not read from camera")
                break
            
            # Flip frame horizontally for mirror effect
            frame = cv2.flip(frame, 1)
            
            # Draw rectangle and corners
            selector.draw_on_frame(frame)
            
            # Display frame
            cv2.imshow(window_name, frame)
            
            # Handle key presses
            key = cv2.waitKey(1) & 0xFF
            if key == 13:  # Enter key
                camera_coords = selector.get_coordinates()
                if save_coordinates(camera_coords=camera_coords):
                    print("Camera calibration completed successfully")
                    return True
                else:
                    print("Error saving camera coordinates")
                    return False
            elif key == 27:  # Escape key
                print("Camera calibration cancelled")
                return False
    
    finally:
        cap.release()
        cv2.destroyAllWindows()

class ImageProjector:
    """Class to handle image projection and positioning"""
    
    def __init__(self, image_data):
        self.original_image = image_data
        self.position = (0, 0)
        self.scale = 1.0
        self.dragging = False
        self.drag_offset = (0, 0)
        self.current_surface = None
        self._update_surface()
    
    def _update_surface(self):
        """Update pygame surface with current scale"""
        self.current_surface = pygame.surfarray.make_surface(self.original_image)
        if self.scale != 1.0:
            new_width = int(self.current_surface.get_width() * self.scale)
            new_height = int(self.current_surface.get_height() * self.scale)
            self.current_surface = pygame.transform.scale(self.current_surface, (new_width, new_height))
    
    def handle_mouse_down(self, mouse_pos):
        """Handle mouse button down for dragging"""
        self.dragging = True
        mouse_x, mouse_y = mouse_pos
        self.drag_offset = (self.position[0] - mouse_x, self.position[1] - mouse_y)
    
    def handle_mouse_up(self):
        """Handle mouse button up"""
        self.dragging = False
    
    def handle_mouse_move(self, mouse_pos):
        """Handle mouse movement for dragging"""
        if self.dragging:
            mouse_x, mouse_y = mouse_pos
            self.position = (mouse_x + self.drag_offset[0], mouse_y + self.drag_offset[1])
    
    def handle_scale_up(self):
        """Increase image scale"""
        self.scale = min(self.scale + SCALE_STEP, MAX_SCALE)
        self._update_surface()
    
    def handle_scale_down(self):
        """Decrease image scale"""
        self.scale = max(self.scale - SCALE_STEP, MIN_SCALE)
        self._update_surface()
    
    def draw(self, screen):
        """Draw image on screen"""
        screen.fill((0, 0, 0))
        screen.blit(self.current_surface, self.position)
    
    def get_coordinates(self):
        """Get current image coordinates"""
        return {
            "tl_corner": self.position,
            "br_corner": (
                self.position[0] + self.current_surface.get_width(),
                self.position[1] + self.current_surface.get_height()
            )
        }

def load_image_for_projection():
    """Load and prepare image for projection"""
    try:
        with rasterio.open(GEOREFERENCED_IMAGE_PATH) as src:
            image_data = src.read()
        
        # Process image data
        image_data = np.transpose(image_data[:3, :, :], (1, 2, 0)).astype(np.uint8)
        image_data = np.flipud(np.rot90(image_data, 3))
        image_data = np.fliplr(image_data)
        image_data = np.flipud(image_data)
        
        return image_data
        
    except Exception as e:
        print(f"Error loading image for projection: {e}")
        return None

def calibrate_projector():
    """Calibrate projector by positioning image"""
    print("Projector Calibration:")
    print("- Drag image to position it")
    print("- Use + and - keys to scale")
    print("- Press ESC to save and exit")
    
    # Load image
    image_data = load_image_for_projection()
    if image_data is None:
        return False
    
    # Initialize pygame
    pygame.init()
    
    try:
        # Create fullscreen display
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.display.set_caption("Projector Calibration")
        
        # Create image projector
        projector = ImageProjector(image_data)
        
        # Main calibration loop
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        # Save coordinates and exit
                        projector_coords = projector.get_coordinates()
                        if save_coordinates(projector_coords=projector_coords):
                            print("Projector calibration completed successfully")
                            return True
                        else:
                            print("Error saving projector coordinates")
                            return False
                    
                    elif event.key in [pygame.K_PLUS, pygame.K_EQUALS]:
                        projector.handle_scale_up()
                    
                    elif event.key == pygame.K_MINUS:
                        projector.handle_scale_down()
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left mouse button
                        projector.handle_mouse_down(event.pos)
                
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:  # Left mouse button
                        projector.handle_mouse_up()
                
                elif event.type == pygame.MOUSEMOTION:
                    projector.handle_mouse_move(event.pos)
            
            # Draw everything
            projector.draw(screen)
            pygame.display.flip()
    
    finally:
        pygame.quit()

def main():
    """Main calibration workflow"""
    print("Starting Camera and Projector Calibration System")
    print("=" * 50)
    
    # Step 1: Create georeferenced image
    print("Step 1: Creating georeferenced image...")
    if not create_georeferenced_image():
        print("Failed to create georeferenced image. Exiting.")
        return
    
    # Step 2: Camera calibration
    print("\nStep 2: Camera calibration...")
    if not calibrate_camera():
        print("Camera calibration failed or cancelled. Exiting.")
        return
    
    # Step 3: Projector calibration
    print("\nStep 3: Projector calibration...")
    if not calibrate_projector():
        print("Projector calibration failed or cancelled. Exiting.")
        return
    
    print("\nCalibration completed successfully!")
    print("All coordinates have been saved to:", CAMERA_PROJECTOR_JSON_PATH)

if __name__ == "__main__":
    main()