#!/usr/bin/env python3
"""
Multi-Agent GPS Simulation with Jamming Detection
Now includes PyQt5 Requirements Dashboard integration
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button
import numpy as np
import random
import math
import sys
import threading
import time
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

# Import helper functions
from sim_helper_funcs import (
    is_jammed, linear_path, limit_movement, 
    algorithm_make_move, llm_make_move,
    log_batch_of_data, get_last_safe_position,
    convert_numpy_coords
)

# Import LLM config
from llm_config import get_ollama_client, get_model_name

# Import GPS integration
try:
    from gps_client_lib import GPSData, AgentGPSManager, parse_nmea_gga
    GPS_ENABLED = True
    print("[GPS] GPS constellation integration enabled")
except ImportError as e:
    print(f"[GPS] Warning: GPS integration disabled - {e}")
    GPS_ENABLED = False

# Import requirements tracking
try:
    from sim_reqs_tracker import create_requirements_monitor, get_requirements_summary
    REQUIREMENTS_ENABLED = True
    print("[REQUIREMENTS] Requirements tracking enabled")
except ImportError as e:
    print(f"[REQUIREMENTS] Warning: Requirements tracking disabled - {e}")
    REQUIREMENTS_ENABLED = False

# Import RAG store
try:
    from rag_store import add_log
    RAG_ENABLED = True
    print("[RAG] RAG logging enabled")
except ImportError as e:
    print(f"[RAG] Warning: RAG logging disabled - {e}")
    RAG_ENABLED = False
    def add_log(text, metadata, log_id=None):
        pass

# Import PyQt5 notification dashboard
try:
    from notification_dashboard import GPSRequirementsNotificationGUI
    from PyQt5.QtWidgets import QApplication
    PYQT5_ENABLED = True
    print("[PYQT5] Notification dashboard available")
except ImportError as e:
    print(f"[PYQT5] Warning: Notification dashboard disabled - {e}")
    PYQT5_ENABLED = False

# =============================================================================
# SIMULATION CONFIGURATION
# =============================================================================

USE_LLM = False
if USE_LLM:
    ollama = get_ollama_client()
    LLM_MODEL = get_model_name()
    MAX_CHARS_PER_AGENT = 25
    MAX_RETRIES = 3

# Simulation parameters
update_freq = 2.5
max_movement_per_step = 1.41
num_history_segments = 5

# Environment setup
x_range, y_range = (-10, 10), (-10, 10)
mission_end = (10, 10)
jamming_center = (0, 0)
jamming_radius = 5

# Agent configuration
num_agents = 5
agents = [f"agent{i+1}" for i in range(num_agents)]

# Communication quality levels
high_comm_qual = 1.0
low_comm_qual = 0.2

# =============================================================================
# GLOBAL STATE
# =============================================================================

swarm_pos_dict = {}
jammed_positions = {}
last_safe_position = {}
agent_paths = {}
agent_targets = {}

gps_manager = None
gps_data_cache = {}

requirements_monitor = None

animation_running = True
iteration_count = 0

# PyQt5 dashboard state
notification_gui = None
qt_app = None

# FastAPI app
app = FastAPI()

# =============================================================================
# GPS INTEGRATION FUNCTIONS
# =============================================================================

def initialize_gps_manager():
    global gps_manager
    
    if not GPS_ENABLED:
        print("[GPS] GPS integration is disabled")
        return False
    
    try:
        gps_manager = AgentGPSManager(
            constellation_host="localhost",
            constellation_port=12345,
            base_latitude=40.7128,
            base_longitude=-74.0060
        )
        gps_manager.start()
        print("[GPS] GPS manager initialized successfully")
        return True
    except Exception as e:
        print(f"[GPS] Failed to initialize GPS manager: {e}")
        return False

def update_agent_gps_data(agent_id, position):
    global gps_manager, gps_data_cache
    
    if not GPS_ENABLED or gps_manager is None:
        return None
    
    try:
        is_agent_jammed = jammed_positions.get(agent_id, False)
        
        gps_data = gps_manager.update_agent_gps(
            agent_id=agent_id,
            position=position,
            jamming_center=jamming_center,
            jamming_radius=jamming_radius,
            gps_denied=is_agent_jammed
        )
        
        if gps_data:
            gps_data_cache[agent_id] = gps_data
            log_gps_metrics(agent_id, gps_data)
            
            if REQUIREMENTS_ENABLED and requirements_monitor:
                requirements_monitor.update_from_gps_data(agent_id, gps_data)
                jamming_level = gps_manager.calculate_jamming_level(
                    position, jamming_center, jamming_radius
                )
                requirements_monitor.update_from_simulation_state(
                    agent_id, position, is_agent_jammed, jamming_level
                )
            
        return gps_data
        
    except Exception as e:
        print(f"[GPS] Error updating GPS for {agent_id}: {e}")
        return None

def log_gps_metrics(agent_id, gps_data):
    if not RAG_ENABLED:
        return
        
    try:
        import datetime
        
        gga_parsed = {}
        for sentence in gps_data.nmea_sentences:
            if 'GGA' in sentence:
                gga_parsed = parse_nmea_gga(sentence)
                break
        
        timestamp = datetime.datetime.now().isoformat()
        
        log_text = (
            f"GPS metrics for {agent_id}: "
            f"Fix Quality={gps_data.fix_quality}, "
            f"Satellites={gps_data.satellite_count}, "
            f"Signal Quality={gps_data.signal_quality:.2f} dB-Hz"
        )
        
        if gga_parsed.get('valid'):
            log_text += f", HDOP={gga_parsed.get('hdop', 99.9):.1f}"
        
        metadata = {
            'timestamp': timestamp,
            'agent_id': agent_id,
            'gps_fix_quality': gps_data.fix_quality,
            'gps_satellites': gps_data.satellite_count,
            'gps_signal_quality': gps_data.signal_quality,
            'gps_hdop': gga_parsed.get('hdop', 99.9) if gga_parsed.get('valid') else 99.9,
            'nmea_sentence_count': len(gps_data.nmea_sentences),
            'rtcm_message_count': len(gps_data.rtcm_messages),
            'role': 'system',
            'source': 'gps',
            'message_type': 'gps_metrics'
        }
        
        add_log(log_text, metadata)
        
    except Exception as e:
        print(f"[GPS] Error logging GPS metrics: {e}")

# =============================================================================
# AGENT INITIALIZATION
# =============================================================================

def initialize_agents():
    global swarm_pos_dict, jammed_positions, last_safe_position, agent_paths, agent_targets
    
    print(f"[INIT] Initializing {num_agents} agents...")
    
    for agent_id in agents:
        start_pos = (
            random.uniform(x_range[0], x_range[1]),
            random.uniform(y_range[0], y_range[1])
        )
        
        swarm_pos_dict[agent_id] = [list(start_pos) + [high_comm_qual]]
        jammed_positions[agent_id] = False
        last_safe_position[agent_id] = start_pos
        agent_paths[agent_id] = []
        agent_targets[agent_id] = None
        
        print(f"[INIT] {agent_id} starting at {start_pos}")
        
        if GPS_ENABLED and gps_manager:
            update_agent_gps_data(agent_id, start_pos)
        
        if REQUIREMENTS_ENABLED and requirements_monitor:
            requirements_monitor.add_agent(agent_id)

# =============================================================================
# SIMULATION UPDATE LOGIC
# =============================================================================

def update_swarm_data(frame):
    global iteration_count, animation_running
    
    if not animation_running:
        return
        
    iteration_count += 1
    
    for agent_id in swarm_pos_dict:
        last_position = swarm_pos_dict[agent_id][-1][:2]
        comm_quality = swarm_pos_dict[agent_id][-1][2]
        is_agent_jammed = is_jammed(last_position, jamming_center, jamming_radius)
        
        if is_agent_jammed and not jammed_positions[agent_id]:
            print(f"{agent_id} entered jamming zone at {last_position}")
            jammed_positions[agent_id] = True
            swarm_pos_dict[agent_id][-1][2] = low_comm_qual
            
            if GPS_ENABLED:
                update_agent_gps_data(agent_id, last_position)
        
        elif not is_agent_jammed and jammed_positions[agent_id]:
            print(f"{agent_id} left jamming zone at {last_position}")
            jammed_positions[agent_id] = False
            swarm_pos_dict[agent_id][-1][2] = high_comm_qual
            
            if GPS_ENABLED:
                update_agent_gps_data(agent_id, last_position)
        
        if not agent_paths[agent_id] or len(agent_paths[agent_id]) == 0:
            if jammed_positions[agent_id]:
                if USE_LLM:
                    next_pos = llm_make_move(
                        agent_id, swarm_pos_dict, num_history_segments,
                        ollama, LLM_MODEL, MAX_CHARS_PER_AGENT, MAX_RETRIES,
                        jamming_center, jamming_radius, max_movement_per_step,
                        x_range, y_range
                    )
                else:
                    next_pos = algorithm_make_move(
                        agent_id, last_position, jamming_center, jamming_radius,
                        max_movement_per_step, x_range, y_range
                    )
                
                agent_paths[agent_id] = linear_path(
                    last_position, next_pos, max_movement_per_step
                )
            
            elif agent_targets[agent_id]:
                target = agent_targets[agent_id]
                agent_paths[agent_id] = linear_path(
                    last_position, target, max_movement_per_step
                )
                
                dist_to_target = math.sqrt(
                    (last_position[0] - target[0])**2 + 
                    (last_position[1] - target[1])**2
                )
                if dist_to_target < max_movement_per_step:
                    agent_targets[agent_id] = None
                    print(f"{agent_id} reached target {target}")
        
        if agent_paths[agent_id] and len(agent_paths[agent_id]) > 0:
            next_pos = agent_paths[agent_id].pop(0)
            limited_pos = limit_movement(last_position, next_pos, max_movement_per_step)
            
            swarm_pos_dict[agent_id].append([
                limited_pos[0], 
                limited_pos[1], 
                low_comm_qual if jammed_positions[agent_id] else high_comm_qual
            ])
            
            if not jammed_positions[agent_id]:
                last_safe_position[agent_id] = limited_pos
        
        if GPS_ENABLED and iteration_count % 5 == 0:
            update_agent_gps_data(agent_id, swarm_pos_dict[agent_id][-1][:2])
    
    if RAG_ENABLED and iteration_count % 10 == 0:
        agent_histories = {}
        for agent_id in swarm_pos_dict:
            last_data = swarm_pos_dict[agent_id][-1]
            agent_histories[agent_id] = [{
                'position': tuple(last_data[:2]),
                'communication_quality': last_data[2],
                'jammed': jammed_positions[agent_id]
            }]
        
        log_batch_of_data(agent_histories, add_log, f"iter{iteration_count}")
    
    update_plot()

# =============================================================================
# VISUALIZATION
# =============================================================================

fig, ax = plt.subplots(figsize=(12, 10))

def update_plot():
    ax.clear()
    
    ax.set_xlim(x_range)
    ax.set_ylim(y_range)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    
    jamming_circle = patches.Circle(
        jamming_center, jamming_radius, 
        color='red', alpha=0.2, label='Jamming Zone'
    )
    ax.add_patch(jamming_circle)
    
    ax.plot(mission_end[0], mission_end[1], 'g*', markersize=20, label='Mission End')
    
    for agent_id in swarm_pos_dict:
        positions = swarm_pos_dict[agent_id]
        
        xs = [pos[0] for pos in positions]
        ys = [pos[1] for pos in positions]
        ax.plot(xs, ys, 'b-', alpha=0.3, linewidth=1)
        
        current = positions[-1]
        color = 'red' if jammed_positions[agent_id] else 'blue'
        ax.plot(current[0], current[1], 'o', color=color, markersize=10)
        
        label_text = f"{agent_id}\nComm: {current[2]:.1f}"
        if GPS_ENABLED and agent_id in gps_data_cache:
            gps = gps_data_cache[agent_id]
            label_text += f"\nSats: {gps.satellite_count}"
        
        ax.text(current[0], current[1] + 0.5, label_text, 
                fontsize=8, ha='center')
    
    ax.legend(loc='upper left')
    ax.set_title(f'Multi-Agent GPS Simulation - Iteration {iteration_count}')
    plt.draw()

# =============================================================================
# PYQT5 NOTIFICATION DASHBOARD
# =============================================================================

def toggle_notification_dashboard(event):
    """Toggle the PyQt5 notification dashboard"""
    global notification_gui, qt_app
    
    if not PYQT5_ENABLED:
        print("[PYQT5] Notification dashboard not available")
        return
    
    if qt_app is None:
        qt_app = QApplication.instance()
        if qt_app is None:
            qt_app = QApplication(sys.argv)
    
    if notification_gui is None or not notification_gui.isVisible():
        notification_gui = GPSRequirementsNotificationGUI(requirements_monitor)
        notification_gui.show()
        print("[PYQT5] Notification dashboard opened")
    else:
        notification_gui.close()
        notification_gui = None
        print("[PYQT5] Notification dashboard closed")

# Add button to matplotlib figure
ax_button = plt.axes([0.81, 0.01, 0.18, 0.05])
btn_dashboard = Button(ax_button, 'Show Dashboard', color='lightblue', hovercolor='skyblue')
btn_dashboard.on_clicked(toggle_notification_dashboard)

# =============================================================================
# FASTAPI CONTROL INTERFACE
# =============================================================================

@app.get("/")
async def root():
    return {"status": "Simulation API running"}

@app.get("/status")
async def get_status():
    agent_positions = {}
    for agent_id in swarm_pos_dict:
        last_pos = swarm_pos_dict[agent_id][-1]
        agent_positions[agent_id] = {
            'x': float(last_pos[0]),
            'y': float(last_pos[1]),
            'communication_quality': float(last_pos[2]),
            'jammed': jammed_positions[agent_id],
            'target': agent_targets.get(agent_id)
        }
    
    return {
        "running": animation_running,
        "iteration_count": iteration_count,
        "agent_positions": agent_positions
    }

@app.post("/move_agent")
async def move_agent(request: dict):
    agent = request.get("agent")
    x = float(request.get("x"))
    y = float(request.get("y"))
    
    if agent not in agents:
        return {"success": False, "message": f"Unknown agent: {agent}"}
    
    agent_targets[agent] = (x, y)
    current_pos = swarm_pos_dict[agent][-1][:2]
    
    return {
        "success": True,
        "message": f"Moving {agent} to ({x}, {y})",
        "current_position": current_pos,
        "jammed": jammed_positions[agent],
        "communication_quality": swarm_pos_dict[agent][-1][2]
    }

@app.get("/gps_status")
async def get_gps_status():
    if not GPS_ENABLED:
        return {"gps_enabled": False, "message": "GPS integration disabled"}
    
    gps_status = {}
    for agent_id, gps_data in gps_data_cache.items():
        gps_status[agent_id] = {
            "fix_quality": gps_data.fix_quality,
            "satellites": gps_data.satellite_count,
            "signal_quality": gps_data.signal_quality,
            "timestamp": gps_data.timestamp,
            "nmea_count": len(gps_data.nmea_sentences),
            "rtcm_count": len(gps_data.rtcm_messages)
        }
    
    return {"gps_enabled": True, "gps_status": gps_status}

@app.get("/agents")
async def get_agents():
    agent_info = {}
    for agent_id in agents:
        last_pos = swarm_pos_dict[agent_id][-1]
        agent_info[agent_id] = {
            'position': (float(last_pos[0]), float(last_pos[1])),
            'jammed': jammed_positions[agent_id]
        }
    return {"agents": agent_info}

@app.post("/control/pause")
async def pause_simulation():
    global animation_running
    animation_running = False
    return {"status": "paused"}

@app.post("/control/continue")
async def continue_simulation():
    global animation_running
    animation_running = True
    return {"status": "running"}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

def run_api_server():
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="warning")

def run_simulation_with_plots():
    ani = FuncAnimation(
        fig, update_swarm_data, 
        interval=int(update_freq * 1000),
        cache_frame_data=False
    )
    plt.show()

def main():
    """
    Main entry point for the simulation with proper GUI handling.
    This function should be called from startup.py or run directly.
    """
    print(f"[SIM] Running simulation with {'LLM' if USE_LLM else 'Algorithm'} control")
    
    # Initialize GPS Manager
    gps_initialized = initialize_gps_manager()
    if gps_initialized:
        print("[GPS] GPS constellation integration active")
    else:
        print("[GPS] Running without GPS integration")
    
    # Initialize Requirements Monitor
    global requirements_monitor
    if REQUIREMENTS_ENABLED:
        requirements_monitor = create_requirements_monitor()
        if requirements_monitor:
            requirements_monitor.start_monitoring()
            print("[REQUIREMENTS] Requirements monitoring active")
    
    # Start FastAPI server in background thread
    import threading
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    print("[API] FastAPI server started on http://0.0.0.0:5001")
    
    # Give API time to start
    time.sleep(2)
    
    # Initialize agents
    initialize_agents()
    
    # Setup matplotlib GUI
    print("[SIM] Starting visualization...")
    print("[SIM] Click 'Show Dashboard' button to open Requirements Dashboard")
    print("[SIM] Close this window to shutdown the simulation")
    
    # Create animation
    ani = FuncAnimation(
        fig, update_swarm_data, 
        interval=int(update_freq * 1000),
        cache_frame_data=False
    )
    
    # This will block until the matplotlib window is closed
    try:
        plt.show()
    except KeyboardInterrupt:
        print("\n[SIM] Caught interrupt signal")
    finally:
        print("[SIM] Shutting down...")
        
        # Cleanup
        if gps_manager:
            gps_manager.stop()
            print("[GPS] GPS manager stopped")
        
        if requirements_monitor:
            requirements_monitor.stop_monitoring()
            print("[REQUIREMENTS] Requirements monitor stopped")
        
        # Close PyQt5 dashboard if open
        global notification_gui
        if notification_gui is not None:
            try:
                notification_gui.close()
            except:
                pass
        
        print("[SIM] Cleanup complete")


if __name__ == "__main__":
    # When run directly (not from startup.py), start API server too
    import threading
    
    print("="*60)
    print("DIRECT SIMULATION START")
    print("Note: For full system, use startup.py instead")
    print("="*60)
    
    main()