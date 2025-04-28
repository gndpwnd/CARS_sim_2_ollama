import asyncio
import httpx
import json
import time

# Configuration
SIM_API_URL = "http://127.0.0.1:5001"
MCP_API_URL = "http://127.0.0.1:5000"

async def test_simulation_api():
    """Run a series of tests on the simulation API"""
    async with httpx.AsyncClient() as client:
        # Test 1: Check if API is running
        print("\n=== Test 1: API Health Check ===")
        try:
            response = await client.get(f"{SIM_API_URL}/")
            print(f"Response: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"Error: {e}")
            return False

        # Test 2: Get simulation status
        print("\n=== Test 2: Get Simulation Status ===")
        try:
            response = await client.get(f"{SIM_API_URL}/status")
            print(f"Status Code: {response.status_code}")
            status_data = response.json()
            print(f"Running: {status_data.get('running')}")
            print(f"Iteration Count: {status_data.get('iteration_count')}")
            
            # Print first agent position as example
            agent_positions = status_data.get('agent_positions', {})
            if agent_positions:
                first_agent = next(iter(agent_positions))
                print(f"Example Agent '{first_agent}' Position: {agent_positions[first_agent]}")
            else:
                print("No agents found in simulation")
        except Exception as e:
            print(f"Error: {e}")

        # Test 3: Get all agents
        print("\n=== Test 3: Get All Agents ===")
        try:
            response = await client.get(f"{SIM_API_URL}/agents")
            agents_data = response.json().get('agents', {})
            print(f"Found {len(agents_data)} agents:")
            for agent_id, data in agents_data.items():
                print(f"  - {agent_id}: Position {data['position']}, Jammed: {data['jammed']}")
        except Exception as e:
            print(f"Error: {e}")

        # Test 4: Get simulation parameters
        print("\n=== Test 4: Get Simulation Parameters ===")
        try:
            response = await client.get(f"{SIM_API_URL}/simulation_params")
            params = response.json()
            print(json.dumps(params, indent=2))
        except Exception as e:
            print(f"Error: {e}")

        # Test 5: Move an agent
        print("\n=== Test 5: Move an Agent ===")
        try:
            # First, get a list of available agents
            response = await client.get(f"{SIM_API_URL}/agents")
            agents_data = response.json().get('agents', {})
            
            if agents_data:
                # Take the first agent as a test subject
                test_agent = next(iter(agents_data.keys()))
                current_pos = agents_data[test_agent]['position']
                
                # Move the agent to a new position (offset by 2 units in x and y)
                new_x = current_pos[0] + 2
                new_y = current_pos[1] + 2
                
                print(f"Moving {test_agent} from {current_pos} to ({new_x}, {new_y})")
                
                response = await client.post(
                    f"{SIM_API_URL}/move_agent",
                    json={"agent": test_agent, "x": new_x, "y": new_y}
                )
                
                print(f"Response: {response.status_code}")
                print(json.dumps(response.json(), indent=2))
                
                # Verify the agent moved by getting its position again
                await asyncio.sleep(1)  # Wait a bit
                response = await client.get(f"{SIM_API_URL}/agents")
                updated_pos = response.json().get('agents', {}).get(test_agent, {}).get('position')
                print(f"New position of {test_agent}: {updated_pos}")
            else:
                print("No agents available to test movement")
        except Exception as e:
            print(f"Error: {e}")

        # Test 6: Pause and continue simulation
        print("\n=== Test 6: Pause and Continue Simulation ===")
        try:
            # Pause the simulation
            response = await client.post(f"{SIM_API_URL}/control/pause")
            print(f"Pause response: {response.status_code} - {response.json()}")
            
            # Wait a bit
            await asyncio.sleep(2)
            
            # Continue the simulation
            response = await client.post(f"{SIM_API_URL}/control/continue")
            print(f"Continue response: {response.status_code} - {response.json()}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test 7: Test MCP integration
        print("\n=== Test 7: Test MCP Command Integration ===")
        try:
            # Test natural language command via MCP
            test_cmd = "Move agent1 to coordinates 5, -5"
            print(f"Sending command: '{test_cmd}'")
            
            response = await client.post(
                f"{MCP_API_URL}/llm_command",
                json={"message": test_cmd}
            )
            
            print(f"Response: {response.status_code}")
            print(json.dumps(response.json(), indent=2))
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    print("===== Simulation API Test Script =====")
    print(f"Connecting to Simulation API at: {SIM_API_URL}")
    print(f"Connecting to MCP API at: {MCP_API_URL}")
    
    # Run the async test function
    asyncio.run(test_simulation_api())
    
    print("\n===== Test Complete =====")