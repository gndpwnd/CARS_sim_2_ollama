# GPS Simulation Refactoring Plan

## Files to Keep and Modify

### Core Files (Keep and Update)
1. **`sat_constellation.py`** - Satellite constellation simulator (GPS/GNSS message generator)
2. **`gps_client_lib.py`** - Client library for vehicles to communicate with constellation
3. **`vehicle_requirements_tracker.py`** - Tracks GPS requirements for each vehicle
4. **`main_gui.py`** - Main simulation GUI with vehicle tracking
5. **`vehicle.py`** - Vehicle simulation class
6. **`utils_gps_sim.py`** - Utility functions
7. **`requirements_config.json`** - Configuration for requirements monitoring
8. **`constellation_config.json`** - Configuration for satellite constellation

### Files to Remove or Consolidate
- **Remove**: `enhanced_notification_gui.py` (redundant)
- **Remove**: `run_sim.py` (standalone, not integrated)
- **Keep**: `notification_gui.py`

## Key Changes Needed

### 1. Simplify Vehicle Requirements Tracker
- Remove complex GPS client creation within the tracker
- Focus only on monitoring requirements, not generating GPS data
- Use constellation data through the client library

### 2. Update Main GUI Integration
- Properly integrate with vehicle_requirements_tracker
- Add vehicle selector dropdown to notification dashboard
- Connect simulation vehicles to constellation server

### 3. Clean Up Notification Dashboard
- Add vehicle dropdown selector above tabs
- Simplify the worker thread approach
- Use requirements_config.json for configuration

### 4. Constellation Server Improvements
- Ensure proper NMEA/RTCM message generation
- Add realistic signal degradation simulation
- Improve error injection capabilities

## Execution Steps

### Step 1: Clean Up Files
Remove redundant files

### Step 2: Update Vehicle Requirements Tracker
Simplify to focus on monitoring, not GPS generation

### Step 3: Fix Main GUI Integration
Connect vehicles to constellation server properly

### Step 4: Improve Requirements Dashboard
Add vehicle selection and clean up UI

### Step 5: Test Integration
Ensure constellation → client → tracker → dashboard flow works

## Architecture Flow
```
Satellite Constellation (sat_constellation.py)
    ↓ (TCP server providing NMEA/RTCM)
GPS Client Library (gps_client_lib.py)
    ↓ (parses messages, callbacks)
Vehicle Requirements Tracker (vehicle_requirements_tracker.py)
    ↓ (monitors requirements)
Requirements Dashboard (requirements_dashboard.py)
    ↓ (displays vehicle status)
Main GUI (main_gui.py)
    ↓ (coordinates everything)
```

## Benefits of This Approach
1. **Modularity**: Each component has a clear, single responsibility
2. **Realistic GPS**: Uses actual NMEA/RTCM protocols via libraries
3. **Scalability**: Easy to add more vehicles or requirements
4. **Maintainability**: Clear separation of concerns
5. **Testability**: Components can be tested independently