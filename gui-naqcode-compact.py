import numpy as np
import pandas as pd
from collections import deque
import random
import tkinter as tk
from tkinter import ttk
from ttkbootstrap import Style, Toplevel, utility
import time
from PIL import Image, ImageTk

# Sensor Imports

from sensors.ESC import cut_throttle, restart_throttle
from sensors.servos import set_servo_angle, toggle_choke
from sensors.temp import read_temp
from sensors.rpm import read_rpm
from sensors.load_cell import read_load_cells
from sensors.flow import read_flow

# --- Mock Sensor Functions ---
'''
def read_sensors():
    """Mocks reading all sensor values."""
    sensor_values = {
        # Temperature between 15°C and 100°C
        "Temperature": round(random.uniform(15, 100), 2),
        # RPM between 0 and 6000 rpm
        "RPM": random.randint(0, 6000),
        # Load cells produce forces, say between -1000 and 1000 N
        "Load Cell 1": load_cell_dict['Load Cell 1 (Raw)'],
        "Load Cell 2": round(random.uniform(-1000, 1000), 2),
        # Flow sensors: 0–2000 g/min and 0–20 L/min
        "grams_per_min": round(random.uniform(0, 2000), 2),
        "liters_per_min": round(random.uniform(0, 20), 2)
    }
    return sensor_values
'''

# Read all sensor values (real implementation)
def read_sensors():
    #temp_dict = read_temp()
    rpm_dict = read_rpm()
    load_cell_dict = read_load_cells()
    #flow_dict = read_flow()

    return {
        "Temperature": round(random.uniform(15, 100), 2),
        "RPM": rpm_dict['rpm'],
        "Load Cell 1": load_cell_dict['Load Cell 1 (Raw)'],
        "Load Cell 2": load_cell_dict['Load Cell 2 (Raw)'],
        "grams_per_min": round(random.uniform(0, 2000), 2),
        "liters_per_min": round(random.uniform(0, 2000), 2)
    }

# --- GUI Implementation ---
class SensorGUI:
    def __init__(self, root):
        # --- Core Setup ---
        self.root = root
        self.style = Style(theme='flatly') 
        root.title("Engine Control Panel Dashboard")
        root.geometry("1000x550")
        
        # Configure custom styles
        self.style.configure('Custom.TFrame', background='white', bordercolor='#003366', relief='flat', borderwidth=2, border_radius=10)
        self.style.configure('Control.TButton', font=('Inter', 11, 'bold'), padding=(12, 5), border_radius=8)
        self.style.configure('Danger.TLabel', foreground='white', background='#dc3545', font=('Inter', 9))
        self.style.configure('Success.TLabel', foreground='white', background='#28a745', font=('Inter', 9))

        # --- Data Storage and Logic Variables ---
        self.sensor_active = True  # True means engine is running/ready to poll (initial state)
        self.choke_state = tk.BooleanVar(value=False) # False means Choke: Closed (initial state)
        self.throttle_var = tk.DoubleVar(value=90.0)
        self.percent_text = tk.StringVar(value=f"{int(self.throttle_var.get())}°")

        self.sensor_data = {
            "Temperature": deque(maxlen=20), "RPM": deque(maxlen=20),
            "Load Cell 1": deque(maxlen=20), "Load Cell 2": deque(maxlen=20),
            'grams_per_min': deque(maxlen=20), 'liters_per_min': deque(maxlen=20)
        }
        self.moving_avg_window = 5
        self.wait_time_after_choke = 5  # cycles to wait after choke engagement
        self.after_delay = 1000  # 1 second poll time
        self.waiting_for_readings = 0
        self._excel_buffer = []

        self.display_widgets = {} 
        self.control_widgets = {}
        
        self.display_widgets['Load Cell 1'] = {
            'current': tk.StringVar(value=f"0"), 'avg': tk.StringVar(value=""), 'unit': "N"
         }

        self.display_widgets['Temperature'] = {
            'current': tk.StringVar(value=f"0"), 'avg': tk.StringVar(value=""), 'unit': "°C"
        }
        self.display_widgets['RPM'] = {
            'current': tk.StringVar(value=f"0"), 'avg': tk.StringVar(value=""), 'unit': "RPM"
        }
        self.display_widgets['Load Cell 2'] = {
            'current': tk.StringVar(value=f"0"), 'avg': tk.StringVar(value=""), 'unit': "N"
        }
        self.display_widgets['liters_per_min'] = {
            'current': tk.StringVar(value=f"0"), 'avg': tk.StringVar(value=""), 'unit': "L/min"
        }

        # --- Build Layout ---
        self.create_layout()
        
        # --- Start Polling ---
        self.root.after(0, self.poll_sensors)
        self.root.protocol("WM_DELETE_WINDOW", self.save_data_and_close)
        
        # Initialize indicator colors (Cut/Restart starts ready/green)
        self.update_cut_restart_indicators() 

    def create_indicator_block(self, parent, data_key, label_text, unit, row, col):
        """Creates one of the four top bordered display blocks with current and avg data."""
        
        key_map = {
            "Temperature": "Temperature", "RPM": "RPM",
            "Torque": "Load Cell 2",
            "Fuel Flow": "liters_per_min"
        }
        key = key_map.get(label_text, data_key)

        BLOCK_WIDTH = 150 
        BLOCK_HEIGHT = 85 

        block_frame = ttk.Frame(parent, padding=3, relief='solid', borderwidth=2, style='Custom.TFrame', 
                                width=BLOCK_WIDTH, height=BLOCK_HEIGHT)
        block_frame.grid(row=row, column=col, padx=15, pady=3, sticky='nsew')
        # Crucial step: stop the frame from shrinking/expanding to its contents
        block_frame.grid_propagate(False) 
        
        current_value_text = self.display_widgets[key]['current']
        
        # FIXED WIDTH for the main value label to prevent overflow, anchor center for safety
        value_label = ttk.Label(
            block_frame, textvariable=current_value_text, font=('Inter', 26, 'bold'),
            padding=(0, 2), foreground='#003366', anchor='center', width=10) # Fixed width 
        value_label.pack(fill='x', expand=True, pady=(3, 0))
        
        avg_value_text = tk.StringVar(value="Avg: 0")
        avg_label = ttk.Label(
            block_frame, textvariable=avg_value_text, font=('Inter', 9, 'normal'),
            padding=(0, 2), foreground='#777', anchor='center')
        avg_label.pack(fill='x', expand=True)

        ttk.Label(
            parent, text=label_text+' ('+unit+')' if unit != 'RPM' else label_text, font=('Inter', 11, 'bold'),
            foreground='#555'
        ).grid(row=row+1, column=col, pady=(0, 5))

        self.display_widgets[key] = {
            'current': current_value_text, 'avg': avg_value_text, 'unit': unit
        }
        return block_frame

    def create_circular_indicator(self, parent, color, tag, initial_state=True):
        """Creates a circular canvas indicator and returns the canvas and the circle item ID."""
        size = 30
        canvas = tk.Canvas(parent, width=size, height=size, highlightthickness=0, bg='white')
        circle_id = canvas.create_oval(2, 2, size - 2, size - 2, fill=color if initial_state else 'gray', outline='#333', width=2, tags=tag)
        return canvas, circle_id

    def setup_control_block(self, parent, title, action_command, button_text_var, tag):
        """Sets up a control block (Choke or Cut/Restart)."""
        block_frame = ttk.Frame(parent, padding=8, relief='solid', borderwidth=2, style='Custom.TFrame')
        block_frame.pack(side='left', padx=25, pady=10, fill='both', expand=True)
        
        ttk.Label(block_frame, text=title, font=('Inter', 12, 'bold'), foreground='#333').pack(pady=(0, 5))
        
        indicator_frame = ttk.Frame(block_frame, style='TFrame')
        indicator_frame.pack(pady=5)
        
        # Indicator setup
        green_canvas, green_id = self.create_circular_indicator(indicator_frame, 'lightgreen', f'{tag}_green', tag != 'choke') # Choke starts gray/closed
        green_canvas.pack(side='left', padx=10)
        
        red_canvas, red_id = self.create_circular_indicator(indicator_frame, 'red', f'{tag}_red', tag == 'choke') # Choke starts red/closed
        red_canvas.pack(side='left', padx=10)
        
        action_button = ttk.Button(
            block_frame, textvariable=button_text_var, command=action_command,
            style='Control.TButton', bootstyle='info'
        )
        action_button.pack(pady=8, fill='x', padx=8)

        return {
            'frame': block_frame, 'green_id': green_id, 'red_id': red_id,
            'green_canvas': green_canvas, 'red_canvas': red_canvas, 'button': action_button
        }

    def create_layout(self):
         # 0. Header Frame
        self.header_frame = ttk.Frame(self.root, padding=(15, 3))
        self.header_frame.pack(fill='x', pady=(3, 5))
        
        try:
            logo_image = Image.open("logo.png")
            logo_image = logo_image.resize((35, 35), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(logo_image)
            
            logo_label = ttk.Label(self.header_frame, image=self.logo_photo)
            logo_label.pack(side='left', padx=(15, 8))
        except Exception as e:
            print(f"Logo error: {e}")
        
        # Title alongside logo
        ttk.Label(self.header_frame, text="Engine Control Panel Dashboard", 
                 font=('Inter', 14, 'bold'), foreground='#003366').pack(side='left')

        # 1. Top Indicators Frame
        self.top_grid_frame = ttk.Frame(self.root, padding=5)
        self.top_grid_frame.pack(pady=5, padx=40, fill='x')
        self.top_grid_frame.columnconfigure((0, 1, 2, 3), weight=1)
        self.top_grid_frame.rowconfigure((0, 1), weight=1)

        sensors_config = [
            ("Temperature", "Temperature", "°C", 0, 0), ("RPM", "RPM", "RPM", 0, 1),
            ("Load Cell 2", "Torque", "N", 0, 2),
            ("liters_per_min", "Fuel Flow", "L/min", 0, 3)
        ]
        
        for key, label, unit, r, c in sensors_config:
            self.create_indicator_block(self.top_grid_frame, key, label, unit, r, c)

        # 2. Center Controls Frame
        self.center_frame = ttk.Frame(self.root, padding=5)
        self.center_frame.pack(pady=5, padx=40, fill='x')
        self.center_frame.columnconfigure(0, weight=1)

        # 2a. Choke Control Block (Starts Closed/Red)
        self.choke_text = tk.StringVar(value="Choke: Closed")
        self.control_widgets['choke'] = self.setup_control_block(
            self.center_frame, "Choke", self.toggle_choke, self.choke_text, 'choke'
        )

        # 2b. Central Thrust Value Display (Load Cell 1)
        THRUST_WIDTH = 180
        THRUST_HEIGHT = 160
        
        self.thrust_frame = ttk.Frame(self.center_frame, padding=10, relief='solid', borderwidth=2, style='Custom.TFrame',
                                      width=THRUST_WIDTH, height=THRUST_HEIGHT) # Fixed Size
        self.thrust_frame.pack(side='left', padx=25, pady=5, fill='both', expand=True)
        self.thrust_frame.pack_propagate(False) # Crucial step for pack geometry

        ttk.Label(self.thrust_frame, text="Thrust (N)", font=('Inter', 12, 'bold'), foreground='#333').pack(pady=(0, 3))
        
        # Use the StringVar created in __init__ for Load Cell 1 
        thrust_text_var = self.display_widgets['Load Cell 1']['current']

        self.thrust_value_label = ttk.Label(
            self.thrust_frame, textvariable=thrust_text_var, font=('Inter', 26, 'bold'), 
            padding=20, foreground='#a50000', anchor='center', width=8 # Fixed width for number
        )
        self.thrust_value_label.pack(expand=True, fill='both')

        # 2c. Cut/Restart Control Block (Starts Active/Green)
        self.cut_restart_text = tk.StringVar(value="State: Cut")
        self.control_widgets['cut_restart'] = self.setup_control_block(
            self.center_frame, "Starter", self.toggle_cut_restart, self.cut_restart_text, 'cut_restart'
        )

        # 3. Status Label
        self.status_label_text = tk.StringVar(value="")
        self.status_label = ttk.Label(
            self.root, textvariable=self.status_label_text, anchor="center", justify="center", style='Success.TLabel')
        self.status_label.pack(fill='x', padx=40, pady=(0, 3))

        # 4. Slider Control Frame
        self.slider_frame = ttk.Frame(self.root, padding=(15, 3))
        self.slider_frame.pack(pady=10, padx=40, fill='x')

        ttk.Button(self.slider_frame, text="➖", command=self.decrement_throttle, bootstyle='dark', width=5).pack(side='left', padx=8, ipady=3)

        self.slider_area_frame = ttk.Frame(self.slider_frame, padding=3, relief='raised', style='Custom.TFrame')
        self.slider_area_frame.pack(side='left', fill='x', expand=True)
        
        # Custom canvas-based slider for better touchscreen interaction
        self.create_custom_slider()
        
        ttk.Label(
            self.slider_area_frame, textvariable=self.percent_text, font=('Inter', 12, 'bold'),
            foreground='#333', background='white'
        ).place(relx=0.5, rely=0.5, anchor='center')

        ttk.Button(self.slider_frame, text="➕", command=self.increment_throttle, bootstyle='dark', width=5).pack(side='left', padx=8, ipady=3)
        
        # 5. Save Button
        ttk.Button(
            self.root, text="Save Data and Exit", command=self.save_data_and_close, 
            style='Control.TButton', bootstyle='light', width=20
        ).pack(pady=(3, 5), ipadx=15, ipady=8)

    def create_custom_slider(self):
        """Creates a custom canvas-based slider with a vertical bar handle for better touchscreen use."""
        # Canvas for the slider with increased height for easier touch interaction
        slider_height = 50
        self.slider_canvas = tk.Canvas(
            self.slider_area_frame, 
            height=slider_height, 
            bg='white', 
            highlightthickness=0
        )
        self.slider_canvas.pack(fill='x', padx=15, pady=8, expand=True)
        
        # Track initialization state
        self.slider_initialized = False
        
        # Bind resize event
        self.slider_canvas.bind('<Configure>', self._on_slider_resize)
        
        # Bind events after a short delay to ensure canvas is rendered
        self.root.after(10, self._init_slider_graphics)
        
    def _init_slider_graphics(self):
        """Initialize slider graphics after canvas is rendered."""
        # Get canvas dimensions
        self.slider_canvas.update_idletasks()
        canvas_width = self.slider_canvas.winfo_width()
        canvas_height = self.slider_canvas.winfo_height()
        
        # Slider track dimensions
        self.slider_padding = 20
        self.track_y = canvas_height / 2
        self.track_start_x = self.slider_padding
        self.track_end_x = canvas_width - self.slider_padding
        self.track_width = self.track_end_x - self.track_start_x
        
        # Draw slider track (thicker for touch)
        track_thickness = 8
        self.slider_canvas.create_rectangle(
            self.track_start_x, self.track_y - track_thickness/2,
            self.track_end_x, self.track_y + track_thickness/2,
            fill='#d0d0d0', outline='#999', width=1, tags='track'
        )
        
        # Draw filled track portion (progress indicator)
        self.filled_track = self.slider_canvas.create_rectangle(
            self.track_start_x, self.track_y - track_thickness/2,
            self.track_start_x, self.track_y + track_thickness/2,
            fill='#17a2b8', outline='', tags='filled'
        )
        
        # Calculate initial handle position
        initial_value = self.throttle_var.get()
        initial_x = self._value_to_x(initial_value)
        
        # Draw vertical bar handle (much easier to grab on touchscreen)
        handle_width = 20  # Thick vertical bar
        handle_height = 40  # Tall enough to touch easily
        self.handle = self.slider_canvas.create_rectangle(
            initial_x - handle_width/2, self.track_y - handle_height/2,
            initial_x + handle_width/2, self.track_y + handle_height/2,
            fill='#0056b3', outline='#003d82', width=2, tags='handle'
        )
        
        # Add subtle gradient effect with inner highlight
        self.handle_highlight = self.slider_canvas.create_rectangle(
            initial_x - handle_width/2 + 2, self.track_y - handle_height/2 + 2,
            initial_x - handle_width/2 + 6, self.track_y + handle_height/2 - 2,
            fill='#4d9fd9', outline='', tags='handle_highlight'
        )
        
        # Bind mouse/touch events
        self.slider_canvas.tag_bind('handle', '<Button-1>', self._on_slider_press)
        self.slider_canvas.tag_bind('handle', '<B1-Motion>', self._on_slider_drag)
        self.slider_canvas.tag_bind('handle_highlight', '<Button-1>', self._on_slider_press)
        self.slider_canvas.tag_bind('handle_highlight', '<B1-Motion>', self._on_slider_drag)
        self.slider_canvas.bind('<Button-1>', self._on_track_click)
        
        # Update filled track to initial position
        self._update_filled_track(initial_x)
        
        # Mark as initialized
        self.slider_initialized = True
        
    def _on_slider_resize(self, event):
        """Handle canvas resize events to redraw slider at correct position."""
        if not self.slider_initialized:
            return
            
        # Get new canvas dimensions
        canvas_width = event.width
        canvas_height = event.height
        
        # Update track dimensions
        self.track_y = canvas_height / 2
        self.track_start_x = self.slider_padding
        self.track_end_x = canvas_width - self.slider_padding
        self.track_width = self.track_end_x - self.track_start_x
        
        # Get current value before redrawing
        current_value = self.throttle_var.get()
        
        # Redraw track
        track_thickness = 8
        coords = self.slider_canvas.coords('track')
        if coords:
            self.slider_canvas.coords(
                'track',
                self.track_start_x, self.track_y - track_thickness/2,
                self.track_end_x, self.track_y + track_thickness/2
            )
        
        # Update handle position based on current value
        new_x = self._value_to_x(current_value)
        self._update_handle_position(new_x)
        
    def _value_to_x(self, value):
        """Convert slider value (40-120) to canvas x coordinate."""
        normalized = (value - 40) / (120 - 40)
        return self.track_start_x + normalized * self.track_width
        
    def _x_to_value(self, x):
        """Convert canvas x coordinate to slider value (40-120)."""
        # Clamp x to track bounds
        x = max(self.track_start_x, min(x, self.track_end_x))
        normalized = (x - self.track_start_x) / self.track_width
        value = 40 + normalized * (120 - 40)
        return max(40, min(120, value))
        
    def _update_handle_position(self, x):
        """Update the position of the slider handle and filled track."""
        # Get handle dimensions
        coords = self.slider_canvas.coords(self.handle)
        handle_width = coords[2] - coords[0]
        handle_height = coords[3] - coords[1]
        
        # Update handle position
        self.slider_canvas.coords(
            self.handle,
            x - handle_width/2, self.track_y - handle_height/2,
            x + handle_width/2, self.track_y + handle_height/2
        )
        
        # Update highlight position
        self.slider_canvas.coords(
            self.handle_highlight,
            x - handle_width/2 + 2, self.track_y - handle_height/2 + 2,
            x - handle_width/2 + 6, self.track_y + handle_height/2 - 2
        )
        
        self._update_filled_track(x)
        
    def _update_filled_track(self, x):
        """Update the filled portion of the track."""
        coords = self.slider_canvas.coords('track')
        self.slider_canvas.coords(
            self.filled_track,
            self.track_start_x, coords[1],
            x, coords[3]
        )
        
    def _on_slider_press(self, event):
        """Handle mouse/touch press on slider handle."""
        self.slider_canvas.config(cursor='hand2')
        
    def _on_slider_drag(self, event):
        """Handle dragging the slider handle."""
        new_value = self._x_to_value(event.x)
        self.throttle_var.set(new_value)
        self._update_handle_position(event.x)
        self.on_throttle_change()
        
    def _on_track_click(self, event):
        """Handle clicking on the track to jump to position."""
        # Only respond if clicking on track, not on handle
        items = self.slider_canvas.find_overlapping(event.x, event.y, event.x, event.y)
        if self.handle not in items and self.handle_highlight not in items:
            new_value = self._x_to_value(event.x)
            self.throttle_var.set(new_value)
            self._update_handle_position(event.x)
            self.on_throttle_change()

    # --- Utility Methods ---
    
    def show_modal(self, title, message, style='info', size=(300, 150), button_text="OK", command=None):
        """Displays a simple modal message."""
        try:
            modal = Toplevel(title=title, parent=self.root, size=size)
            modal.place_window_center()
            ttk.Label(modal, text=message, padding=20, wraplength=size[0] - 40).pack(pady=10)
            
            close_command = command if command else modal.destroy
            ttk.Button(modal, text=button_text, command=close_command, bootstyle=style).pack(pady=10)
            
            modal.protocol("WM_DELETE_WINDOW", close_command)
            self.root.wait_window(modal)
        except tk.TclError:
            # Handle case where main window is already destroyed during saving
            pass
        
    def clear_data(self):
        """Clears all sensor data deques, the Excel buffer, and resets GUI labels."""
        for key in self.sensor_data:
            self.sensor_data[key].clear()
            if key in self.display_widgets:
                widget_data = self.display_widgets[key]
                unit = widget_data['unit']
                widget_data['current'].set(f"0")
                widget_data['avg'].set(f"Avg: 0")
        
    # --- Control Handlers ---

    def on_throttle_change(self, event=None):
        """Updates throttle angle display and clears all accumulated data."""
        throttle_value = int(self.throttle_var.get())
        angle_text = f"{throttle_value}°"
        self.update_servo_angle(throttle_value)
        
        self.percent_text.set(angle_text) 
        
        # LOGIC: As required by the original logic, changing the throttle setting MUST clear the data.
        self.clear_data()
        self.waiting_for_readings = 0
    
    def update_servo_angle(self, angle=None):
        if angle is None:
            angle = int(self.throttle_var.get())

        set_servo_angle(18, angle)

    def increment_throttle(self):
        new_value = min(120, self.throttle_var.get() + 1)
        self.throttle_var.set(new_value)
        if hasattr(self, 'slider_canvas'):
            self._update_handle_position(self._value_to_x(new_value))
        self.on_throttle_change()

    def decrement_throttle(self):
        new_value = max(40, self.throttle_var.get() - 1)
        self.throttle_var.set(new_value)
        if hasattr(self, 'slider_canvas'):
            self._update_handle_position(self._value_to_x(new_value))
        self.on_throttle_change()

    def update_choke_indicators(self):
        """Helper to update the visual state of the Choke block."""
        choke_control = self.control_widgets['choke']
        green_canvas = choke_control['green_canvas']
        red_canvas = choke_control['red_canvas']
        green_id = choke_control['green_id']
        red_id = choke_control['red_id']
        
        is_open = self.choke_state.get()
        green_canvas.itemconfig(green_id, fill='lightgreen' if is_open else 'gray')
        red_canvas.itemconfig(red_id, fill='gray' if is_open else 'red')
        
    def toggle_choke(self):
        """Toggles the choke state and manages the initial delay."""
        current_state = self.choke_state.get()
        self.choke_state.set(not current_state)
        self.update_choke_indicators()

        if self.choke_state.get():
            # Choke is now OPEN (ON) - start delay, set button text to "Choke: Open"
            self.choke_text.set("Choke: Open")
            self.waiting_for_readings = self.wait_time_after_choke
            self.status_label_text.set(f"Choke OPEN. Starting {self.wait_time_after_choke}s delay...")
            self.status_label.config(style='Danger.TLabel')
        else:
            # Choke is now CLOSED (OFF) - clear data, set button text to "Choke: Closed"
            self.choke_text.set("Choke: Closed")
            self.clear_data()
            self.status_label_text.set("Choke CLOSED. Data Cleared.")
            self.status_label.config(style='Success.TLabel')

    def update_cut_restart_indicators(self):
        """Helper to update the visual state of the Cut/Restart block."""
        cut_control = self.control_widgets['cut_restart']
        green_canvas = cut_control['green_canvas']
        red_canvas = cut_control['red_canvas']
        green_id = cut_control['green_id']
        red_id = cut_control['red_id']

        is_active = self.sensor_active
        green_canvas.itemconfig(green_id, fill='lightgreen' if is_active else 'gray')
        red_canvas.itemconfig(red_id, fill='gray' if is_active else 'red')
        
    def toggle_cut_restart(self):
        """Toggles the engine active state, manages polling and data clearing."""
        
        # LOGIC FIX: Invert the state
        self.sensor_active = not self.sensor_active
        self.update_cut_restart_indicators()

        if self.sensor_active:
            # Engine is now ACTIVE (Restarted)
            self.cut_restart_text.set("State: Cut") 
            restart_throttle()
            self.status_label_text.set("Engine Restarted. Sensor Polling Active.")
            self.status_label.config(style='Success.TLabel')
        else:
            # Engine is now INACTIVE (Cut)
            self.cut_restart_text.set("State: Restart") 
            cut_throttle()
            #self.clear_data()
            self.status_label_text.set("Engine Cut. Sensor Polling Paused. Data Cleared.")
            self.status_label.config(style='Danger.TLabel')

    # --- Polling Logic ---

    def poll_sensors(self):
        """Polls sensors, handles choke delay, and updates GUI."""
        if not self.root.winfo_exists():
            return
            
        should_poll = False

        if True:
            if self.choke_state.get():
                # Choke is OPEN: Enforce delay logic
                if self.waiting_for_readings > 0:
                    self.waiting_for_readings -= 1
                    self.status_label_text.set(
                        f"Choke OPEN. Delay: {self.waiting_for_readings} cycles remaining..."
                    )
                    self.status_label.config(style='Danger.TLabel')
                else:
                    # Delay elapsed: Poll sensors
                    should_poll = True
            else:
                # Choke is CLOSED: Poll sensors immediately
                should_poll = False

        if should_poll:
            values = read_sensors()
            if not values or any(v is None for v in values.values()):
                self.status_label_text.set("Sensor missing, skipping cycle...")
                # If a reading fails, re-enforce the delay if the choke is open, 
                # to prevent rapid logging of bad data.
                if self.choke_state.get():
                    self.waiting_for_readings = self.wait_time_after_choke
            else:
                self._process_and_update_values(values)
                self.status_label_text.set(f"Sampling Active.")
                self.status_label.config(style='Success.TLabel')
        #elif not self.sensor_active:
            # Update status if engine is cut
           # self.status_label_text.set("Engine CUT. Polling Paused.")
           # self.status_label.config(style='Danger.TLabel')
        
        # If the status was updated by the choke delay, don't overwrite it here.
        
        self.root.after(self.after_delay, self.poll_sensors)

    def _process_and_update_values(self, sensor_values):
        """Updates internal deques and GUI labels based on new sensor data."""
        timestamp = time.time()
        excel_row = {'Time': timestamp, 'Throttle': int(self.throttle_var.get())}
        
        for key, value in sensor_values.items():
            self.sensor_data[key].append(value)
            excel_row[key] = value

            if key in self.display_widgets:
                widget_data = self.display_widgets[key]
                unit = widget_data['unit']
                
                widget_data['current'].set(f"{value:.2f}")

                latest_readings = list(self.sensor_data[key])
                if len(latest_readings) >= self.moving_avg_window:
                    avg_value = np.mean(latest_readings[-self.moving_avg_window:])
                    widget_data['avg'].set(f"Avg: {avg_value:.2f}")
        
        self._excel_buffer.append(excel_row)

    # --- Exit Logic ---

    def save_data_and_close(self):
        """Attempts to save accumulated data to Excel and then closes the application."""
        if self._excel_buffer:
            try:
                # Update UI to prevent perceived freeze during file write
                self.status_label_text.set("Saving data to Excel...")
                self.status_label.config(style='Warning.TLabel') 
                self.root.update()

                df = pd.DataFrame(self._excel_buffer)
                filename = "sensor_readings.xlsx"
                
                with pd.ExcelWriter(filename, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name="Readings")
                
                # Confirmation modal
                self.show_modal("Save Complete", f"Saved {len(df)} readings to {filename}.", style='success', size=(300, 150))

            except (ImportError, ModuleNotFoundError):
                self.show_modal("Dependency Error", "Cannot save data. Please install 'pandas' and 'openpyxl'.", style='danger', size=(400, 200))
                
            except Exception as e:
                self.show_modal("File Error", f"Failed to save data to Excel. Error: {e}", style='danger', size=(400, 200))
        
        # Close the application cleanly
        self.root.quit()
        self.root.destroy()

# Run Application
if __name__ == "__main__":
    root = tk.Tk()
    app = SensorGUI(root)
    root.mainloop()
