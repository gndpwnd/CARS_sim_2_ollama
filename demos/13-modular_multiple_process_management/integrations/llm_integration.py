"""
LLM integration for recovery assistance.
"""
import requests
import re
from typing import Optional, Tuple
from core.config import MCP_API_URL, MAX_MOVEMENT_PER_STEP, X_RANGE, Y_RANGE

def request_llm_recovery_position(agent_id: str, 
                                  current_position: Tuple[float, float]) -> Optional[Tuple[float, float]]:
    """
    Request recovery position from LLM via MCP API.
    
    Args:
        agent_id: Agent identifier
        current_position: Current (x, y) position
    
    Returns:
        Suggested (x, y) position or None if request fails
    """
    try:
        # Build command for LLM
        command = (
            f"Agent {agent_id} is jammed at position ({current_position[0]:.2f}, {current_position[1]:.2f}). "
            f"Suggest a safe recovery position within {MAX_MOVEMENT_PER_STEP:.2f} units that avoids jamming zones. "
            f"Respond with coordinates in format: move to X, Y"
        )
        
        print(f"[MCP] Requesting LLM recovery for {agent_id}...")
        
        # Make HTTP request to MCP chatapp
        response = requests.post(
            f"{MCP_API_URL}/chat",
            json={"message": command},
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            response_text = data.get('response', '')
            
            print(f"[MCP] LLM response: {response_text[:100]}...")
            
            # Parse coordinates from response
            coords = parse_coordinates_from_text(response_text)
            
            if coords:
                x, y = coords
                
                # Validate coordinates are within bounds
                if X_RANGE[0] <= x <= X_RANGE[1] and Y_RANGE[0] <= y <= Y_RANGE[1]:
                    print(f"[MCP] ✓ LLM suggested position: ({x:.2f}, {y:.2f})")
                    return (x, y)
                else:
                    print(f"[MCP] ✗ LLM suggested out-of-bounds position: ({x:.2f}, {y:.2f})")
                    return None
            else:
                print(f"[MCP] ✗ Could not parse coordinates from LLM response")
                return None
        else:
            print(f"[MCP] ✗ HTTP error {response.status_code}")
            return None
        
    except requests.exceptions.Timeout:
        print(f"[MCP] ✗ Request timeout - LLM taking too long")
        return None
    except requests.exceptions.ConnectionError:
        print(f"[MCP] ✗ Connection error - is MCP chatapp running?")
        return None
    except Exception as e:
        print(f"[MCP] ✗ Error requesting LLM help: {e}")
        return None

def parse_coordinates_from_text(text: str) -> Optional[Tuple[float, float]]:
    """
    Parse coordinates from LLM response text.
    
    Args:
        text: Response text from LLM
        
    Returns:
        (x, y) coordinates or None if not found
    """
    # Try different coordinate patterns
    patterns = [
        r'move to\s+(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)',  # "move to X, Y"
        r'\((-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\)',        # "(X, Y)"
        r'x\s*=\s*(-?\d+\.?\d*)\s*,\s*y\s*=\s*(-?\d+\.?\d*)',  # "x=X, y=Y"
        r'position\s+(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)',  # "position X, Y"
        r'coordinates?\s+(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)',  # "coordinate X, Y"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            coords = match.groups()
            try:
                x = float(coords[0])
                y = float(coords[1])
                return (x, y)
            except ValueError:
                continue
    
    return None

def ask_llm_general(prompt: str, timeout: float = 10.0) -> Optional[str]:
    """
    Ask LLM a general question via MCP API.
    
    Args:
        prompt: Question/prompt for LLM
        timeout: Request timeout in seconds
        
    Returns:
        LLM response text or None if failed
    """
    try:
        response = requests.post(
            f"{MCP_API_URL}/chat",
            json={"message": prompt},
            timeout=timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('response', '')
        else:
            print(f"[LLM] Error: HTTP {response.status_code}")
            return None
            
    except Exception as e:
        print(f"[LLM] Error: {e}")
        return None