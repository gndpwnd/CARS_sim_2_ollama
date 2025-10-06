"""
Modified sim.py with GPS constellation integration

This version tracks GPS metrics for each agent and logs them to the RAG store.
"""

# Add these imports at the top of sim.py
import sys
sys.path.append('.')  # Ensure local imports work

try:
    from gps_client_lib import GPSData, AgentGPSManager, parse_nmea_gga
    GPS_ENABLED = True
    print("[GPS] GPS constellation integration enabled")
except ImportError as e:
    print(f"[GPS] Warning: GPS integration disabled - {e}")
    GPS_ENABLED = False

# Add to global variables section
gps_manager = None
gps_data_cache = {}

def initialize_gps_manager():
    """Initialize the GPS manager for agents"""
    global gps_manager
    
    if not GPS_ENABLED:
        print("[GPS] GPS integration is disabled")
        return False
    
    try:
        # Base station location (New York City by default)
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
    """
    Update GPS data for an agent based on their position
    
    Args:
        agent_id: Agent identifier
        position: (x, y) tuple of agent position
    """
    global gps_manager, gps_data_cache
    
    if not GPS_ENABLED or gps_manager is None:
        return None
    
    try:
        # Check if agent is jammed
        is_agent_jammed = jammed_positions.get(agent_id, False)
        
        # Get GPS data from constellation
        gps_data = gps_manager.update_agent_gps(
            agent_id=agent_id,
            position=position,
            jamming_center=jamming_center,
            jamming_radius=jamming_radius,
            gps_denied=is_agent_jammed
        )
        
        if gps_data:
            gps_data_cache[agent_id] = gps_data
            
            # Log GPS metrics to RAG store
            log_gps_metrics(agent_id, gps_data)
            
        return gps_data
        
    except Exception as e:
        print(f"[GPS] Error updating GPS for {agent_id}: {e}")
        return None

def log_gps_metrics(agent_id, gps_data):
    """
    Log GPS metrics to the RAG store for monitoring
    
    Args:
        agent_id: Agent identifier  
        gps_data: GPSData object with NMEA sentences and metrics
    """
    try:
        from rag_store import add_log
        import datetime
        
        # Parse GGA sentence for detailed metrics
        gga_parsed = {}
        for sentence in gps_data.nmea_sentences:
            if 'GGA' in sentence:
                gga_parsed = parse_nmea_gga(sentence)
                break
        
        # Create log entry
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

# Modify update_swarm_data to include GPS updates
def update_swarm_data_with_gps(frame):
    """
    Enhanced version of update_swarm_data that includes GPS tracking
    """
    global iteration_count
    
    # Only update if animation is running
    if not animation_running:
        return
        
    iteration_count += 1
    
    # Track which agents need GPS updates this iteration
    agents_to_update_gps = []
    
    for agent_id in swarm_pos_dict:
        last_position = swarm_pos_dict[agent_id][-1][:2]
        comm_quality = swarm_pos_dict[agent_id][-1][2]
        is_agent_jammed = is_jammed(last_position, jamming_center, jamming_radius)
        
        # Update jammed status
        if is_agent_jammed and not jammed_positions[agent_id]:
            print(f"{agent_id} has entered jamming zone at {last_position}. Communication quality degraded.")
            jammed_positions[agent_id] = True
            swarm_pos_dict[agent_id][-1][2] = low_comm_qual
            
            # Update GPS when entering jamming zone
            agents_to_update_gps.append((agent_id, last_position))
        
        # ... rest of original update_swarm_data logic ...
        # [Include all the existing movement logic here]
        
        # Update GPS periodically (every 5 iterations)
        if iteration_count % 5 == 0:
            agents_to_update_gps.append((agent_id, last_position))
    
    # Update GPS data for flagged agents
    for agent_id, position in agents_to_update_gps:
        update_agent_gps_data(agent_id, position)

# Add GPS status to API endpoints
@app.get("/gps_status")
async def get_gps_status():
    """Get GPS status for all agents"""
    global gps_data_cache
    
    if not GPS_ENABLED:
        return {"error": "GPS integration not enabled"}
    
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
    
    return {"gps_status": gps_status, "gps_enabled": GPS_ENABLED}

# Update main execution
if __name__ == "__main__":
    print(f"Running simulation with {'LLM' if USE_LLM else 'Algorithm'} control")
    
    # Initialize GPS manager
    gps_initialized = initialize_gps_manager()
    if gps_initialized:
        print("[GPS] GPS constellation integration active")
    else:
        print("[GPS] Running without GPS integration")
    
    # Start API server in a separate thread
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    
    # Initialize agents before starting the simulation
    initialize_agents()
    
    # Run the simulation with plots
    run_simulation_with_plots()
    
    # Cleanup on exit
    if gps_manager:
        gps_manager.stop()