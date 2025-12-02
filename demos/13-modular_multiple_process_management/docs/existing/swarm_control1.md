now this gets into the topic of swarm control. in terms of physical movements, i will want each drone to behave independently depending on various markers, especially in scenarios like GPS denial. but i want the easiest way to move the entire swarm. there is already in place an algorithm that finds the ideal orientation for the swarm, but what about using math like lattices for replicating this optimal pattern across larger swarms?


Swarm Squad
A simulation framework for multi-agent systems.
Swarm Squad is the foundational module of the Swarm Squad project, providing a robust framework for simulating and analyzing multi-agent systems. It implements core functionality for agent modeling, environment simulation, and visualization, serving as the base platform upon which the more specialized Episode I and Episode II modules are built.

The creation of Swarm Squad was motivated by the need for a flexible, customizable, and scalable framework that could simulate the behavior of multiple autonomous agents in various scenarios. Traditional simulation tools often lacked the specific features needed for complex swarm behavior analysis or were too rigid in their implementation to allow for rapid prototyping and experimentation.

Core Capabilities
Swarm Squad addresses these challenges with an architecture designed specifically for multi-agent simulation:

Modular Agent Design: Define agents with customizable properties, behaviors, and capabilities
Physics-Based Simulation: Realistic movement and interaction with accurate physical modeling
Dynamic Environment Creation: Build and modify environments with obstacles, boundaries, and other entities
Configurable Simulation Parameters: Adjust simulation speed, precision, and complexity based on your needs
Comprehensive Data Collection: Gather metrics on agent performance, interaction patterns, and system efficiency
Real-time Visualization: Observe agent behavior as it occurs with intuitive visual representations
Extensible API: Build custom components and integrate with other tools through a well-documented interface
Technical Implementation
The base Swarm Squad module is implemented in Python, leveraging libraries such as NumPy for numerical operations and Dash for visualization. The architecture follows a component-based design that separates concerns between agent behavior, environment modeling, simulation physics, and visualization.

Key components include:

Agent Framework: Flexible base classes for defining agent properties and behaviors
Environment Module: Tools for creating and managing simulation environments
Simulation Engine: Core logic for advancing the simulation state and handling agent interactions
Data Collection System: Infrastructure for gathering and analyzing simulation metrics
Visualization Components: Interactive tools for observing and understanding agent behavior
This modular design allows researchers to focus on the specific aspects of multi-agent systems they're interested in while leveraging pre-built functionality for other aspects of the simulation.

Research Applications
Swarm Squad is designed to support research in various domains, including:

Swarm intelligence and emergent behavior
Distributed decision-making and coordination
Formation control and collective movement
Multi-agent learning and adaptation
Communication-constrained coordination
Robustness to failures and environmental challenges
The framework provides the tools needed to explore these research areas through both structured experiments and open-ended exploration.


Swarm Squad Episode I introduces several key capabilities:

Communication-Aware Formation Control: Maintain formation integrity even in the presence of communication disruption or jamming
Adaptive Behavior Models: Dynamically adjust agent behavior based on environmental conditions and mission objectives
LLM-Guided Decision Making: Leverage large language models to provide strategic guidance for complex mission scenarios
Obstacle Avoidance: Navigate complex environments while maintaining formation and mission progress
Resilience to Communication Failures: Gracefully handle partial or complete communication loss between agents
Performance Metrics: Comprehensive analysis tools for evaluating formation stability, mission success, and resilience


Nice — this is a great place to go next. Lattices are exactly the right kind of math for tiling a formation across many agents: they give you a simple generator (a small set of basis vectors) that you can translate/rotate/scale to replicate an “ideal” local pattern across arbitrarily large swarms. Below I’ll give the concepts, the math, practical control laws, robustness/reconfiguration strategies (including GPS-denial considerations), and a ready-to-use Python sketch you can drop into your Swarm Squad simulation.

I’ll organize this as:

1. Quick intuition / choices of lattices
2. Math: lattice basis, rotation, placement formula
3. Control architecture options (virtual-structure, leader-follower, consensus / graph Laplacian, potential fields)
4. Local control law (simple, practical) + collision avoidance
5. Scaling, hierarchical / recursive tiling, and reconfiguration on failures
6. GPS denial: localization alternatives & bearing/distance-based control
7. Python prototype (generator + local desired-position controller) you can integrate into Swarm Squad

---

# 1) Intuition & lattice choices

Common tilings for planar formations:

* **Hexagonal (triangular) lattice** — densest packing, equal-distance neighbors (good for isotropic sensing/comm). Very common for swarms.
* **Square lattice** — easiest indexing (i, j) but fewer neighbors for the same density.
* **Triangular lattice** — same as hexagonal viewed differently.
  Choose hex if you want uniform nearest-neighbor connectivity and robust local geometry.

Tradeoffs:

* Hex → better connectivity & fault tolerance (each node has 6 neighbors in ideal lattice).
* Square → simpler addressing and indexing (grid-like), easier to map to image-based occupancy.
* Triangular/other lattices → useful if you need anisotropic spacing.

---

# 2) Math: lattice basis, rotation, placement

A 2D lattice is generated by two basis vectors ( \mathbf{a}_1, \mathbf{a}*2 ). Every lattice point is:
[
\mathbf{p}*{i,j} = \mathbf{p}_0 + i\mathbf{a}_1 + j\mathbf{a}_2
]
where (i,j\in\mathbb{Z}) and ( \mathbf{p}_0 ) is an origin/anchor point (e.g., swarm centroid or leader pose).

**Hex lattice basis (spacing (d))**:
[
\mathbf{a}_1 = \begin{bmatrix} d \ 0 \end{bmatrix},\quad
\mathbf{a}_2 = \begin{bmatrix} d/2 \ \tfrac{\sqrt{3}}{2} d \end{bmatrix}
]
This gives neighbor distance (d) between adjacent lattice points.

**Rotation**: if the swarm orientation (from your optimal-orientation algorithm) gives an angle (\theta), rotate each point:
[
\mathbf{p}^{(world)}*{i,j} = \mathbf{p}*{center} + R(\theta),\mathbf{p}_{i,j}
]
with
[
R(\theta) = \begin{bmatrix} \cos\theta & -\sin\theta \ \sin\theta & \cos\theta \end{bmatrix}.
]

**Scaling**: change (d) to scale the lattice spacing.

**Assignment to drones**: map drone IDs to lattice indices ((i,j)) deterministically (round-robin, snake-fill, Hilbert curve for locality, etc.). For dynamic swarms you can use a matching algorithm to assign nearest free lattice points to drones.

---

# 3) Control architectures (how to enact lattice positions)

A few standard patterns:

A) **Virtual Structure (VS)**
Treat the whole lattice as a rigid virtual body. Each drone is assigned a fixed position in the body frame. The virtual body has a pose (translation + orientation) commanded by a higher-level controller. Pros: good coordinated movement and simple assignment. Cons: needs accurate relative localization or communication to maintain per-agent offsets.

B) **Leader-Follower**
One or several leaders follow the global trajectory/orientation; followers maintain relative offsets to leaders or to local neighbors. Simpler, but single-leader failure is a risk (use multi-leader or rotating leaders).

C) **Consensus / Graph Laplacian-based formation**
Use local diffusive control laws driven by graph Laplacian so the swarm converges to the formation shape using only neighbor information. Good for decentralized behavior and robustness.

D) **Behavioral + Potential Fields**
Combine attractive forces to assigned lattice points with repulsive forces for collision avoidance. Simple and works well in practice for many swarms.

---

# 4) A simple, practical local control law

Goal: every drone (i) has a desired lattice point (p^*_i(t)). Use a PD controller on position and velocity plus local collision avoidance.

Let (p_i) be the current world position, (v_i) the current velocity. Desired velocity:
[
v^{des}*i = v*{global} + K_p (p^*_i - p_i) + K_d (v^* - v_i)
]
where (v_{global}) is desired translational velocity from the global controller (virtual structure / leader). If you only have desired pose (no (v^*)), set (v^*=0).

Collision avoidance: add a repulsive term from any neighbor (j) closer than (r_{safe}):
[
F_{rep} = \sum_{j\in\mathcal{N}*i} K*{rep},\phi(|p_i-p_j|),\frac{p_i-p_j}{|p_i-p_j|}
]
where (\phi) is large when distance small (e.g., (\phi(x)=(r_{safe}-x)) for (x<r_{safe}), else 0). Treat as velocity offset:
[
v^{cmd}_i = v^{des}*i + F*{rep}
]

This is simple, local, and reactive.

**Exactness via consensus**: if you want exact relative distances, use gradient-descent on inter-agent distance errors:
[
\dot p_i = -\sum_{j\in\mathcal{N}*i} K*{ij}\left( |p_i - p_j| - d_{ij} \right) \frac{p_i - p_j}{|p_i - p_j|}
]
where (d_{ij}) are target distances (from lattice).

---

# 5) Scaling & hierarchical tiling (formation-of-formations)

For very large swarms:

* **Tile the plane** with the chosen lattice and split the swarm into **cells** (clusters) each managing a local lattice patch.
* Each cell has a **cell leader** that tracks the cell’s virtual pose; internal drones use local controllers.
* This is formation-of-formations: global apply transform ( (p_{cell}, \theta_{cell}) ) to each cell; within cell apply local lattice offsets.

**Recursive / fractal tiling**: you can define a super-lattice of cells whose cell-centers themselves form another lattice (useful for geographic scaling and efficient message routing).

---

# 6) Handling drone failure / reconfiguration (local repair)

When a drone fails (or is lost):

* **Local gap-filling**: neighbors detect missing heartbeat and shift to nearest free lattice index using a *local auction* or *consensus*:

  * Use a small local ID-based leader election for the patch.
  * Each neighbor computes distance cost to candidate vacant lattice points and performs a distributed matching (greedy + tie-breaker by ID).
* **Soft reallocation**: neighbors move slightly to maintain global shape; full reassignment only within a limited radius to limit motion.
* **Multi-scale reconfiguration**: small failures handled locally; large failures trigger cell-level reformation.

Algorithm pattern: detect vacancy → create local candidate set → run distributed greedy assign → move with smoothing.

---

# 7) GPS-denial considerations (localization & control)

If you can’t rely on GPS, you must use relative localization:

* **UWB ranging** + angle-of-arrival (where available) for inter-agent distances.
* **Visual odometry & SLAM** (if drones have cameras) for relative pose to neighbors/landmarks.
* **IMU + inter-agent distance/bearing fusion** with EKF for relative positions.
* **Leader broadcasting relative pose**: leaders with better localization can broadcast offsets.

Control strategies in GPS-denial:

* Use **distance-only formation control** (bearing-less) based on desired inter-agent distances. These are usually gradient-based and converge to shapes up to reflection/rotation unless you anchor orientation with a leader or add angular constraints.
* Use **bearing-based control**: requires relative bearing sensors or cameras.
* Anchor orientation via **magnetometer or relative heading consensus** if absolute heading is unknown.

Important: for lattice replication, you need either a global anchor (one leader with reference) or a distributed orientation consensus (everyone agrees on orientation from noisy local references).

---

# 8) Python prototype for Swarm Squad

Below is a concise code sketch that:

* Generates hex lattice points for an (m\times n) tile around a center.
* Rotates them to the desired orientation.
* Assigns lattice points to agents (simple nearest free).
* A small per-agent control update that computes desired velocity toward assigned lattice point and adds a repulsive collision term.

You can paste this into your Swarm Squad `Agent` update loop or a helper module.

```python
# lattice_utils.py
import numpy as np
from scipy.spatial import cKDTree

def hex_basis(d):
    a1 = np.array([d, 0.0])
    a2 = np.array([d/2.0, (np.sqrt(3)/2.0)*d])
    return a1, a2

def generate_hex_lattice(center, d, radius_cells):
    a1, a2 = hex_basis(d)
    pts = []
    for i in range(-radius_cells, radius_cells+1):
        for j in range(-radius_cells, radius_cells+1):
            p = center + i*a1 + j*a2
            pts.append(p)
    return np.array(pts)  # Nx2

def rotate_points(pts, theta, origin=np.array([0.0, 0.0])):
    R = np.array([[np.cos(theta), -np.sin(theta)],
                  [np.sin(theta),  np.cos(theta)]])
    return (pts - origin) @ R.T + origin

def assign_agents_to_points(agent_positions, lattice_points):
    # greedy nearest assignment (fast); use Hungarian for optimal
    tree = cKDTree(lattice_points)
    dists, idxs = tree.query(agent_positions, k=1)
    assigned = {}
    taken = set()
    for aid, idx in enumerate(idxs):
        # break ties
        if idx in taken:
            # fallback: nearest unused
            dists_k, idxs_k = tree.query(agent_positions[aid], k=10)
            chosen = None
            for cand in idxs_k:
                if cand not in taken:
                    chosen = cand; break
            if chosen is None:
                chosen = idx
            idx = chosen
        assigned[aid] = idx
        taken.add(idx)
    return assigned  # mapping agent_id -> lattice_index

# Local controller
def local_control_step(pos, vel, p_des, neighbors_pos,
                       v_global=np.zeros(2),
                       Kp=1.0, Kd=0.5, r_safe=0.6, Krep=0.7):
    # PD to desired lattice point
    v_des = v_global + Kp*(p_des - pos) - Kd*vel

    # repulsive from neighbors
    rep = np.zeros(2)
    for p_nb in neighbors_pos:
        diff = pos - p_nb
        dist = np.linalg.norm(diff)
        if dist < 1e-6: continue
        if dist < r_safe:
            rep += Krep*(r_safe - dist) * (diff/dist)
    v_cmd = v_des + rep
    # clip speed
    vmax = 2.0
    speed = np.linalg.norm(v_cmd)
    if speed > vmax:
        v_cmd = v_cmd * (vmax / speed)
    return v_cmd
```

Integration notes:

* Call `generate_hex_lattice(center, d, radius)` with center = swarm virtual center, d = lattice spacing, radius large enough to cover #agents.
* `assign_agents_to_points()` gives a quick mapping. Replace with Hungarian or local auction for better global optimality.
* Each agent runs `local_control_step` using local sensed neighbors to compute `neighbors_pos`.

---

# 9) Practical tuning & recommendations

* **Spacing (d)**: choose such that inter-agent sensors / propwash / aerodynamic interactions are safe. (e.g., for small quadcopters maybe (d\ge 1.0) m).
* **Control gains**: tune Kp/Kd in simulation until formation is stable and no oscillation with expected latency/noise.
* **Heartbeat & reassign frequency**: run reassignment auctions slowly (e.g., once per 1–5 s) so agents aren’t constantly switching positions.
* **Collision margin**: set `r_safe` < d/2 to permit control convergence without false positive avoidance.
* **Anchoring orientation**: always keep at least one or a few anchors (leaders) with good absolute pose estimate if you want consistent global orientation across reboots.

---

# 10) Next steps I can do for you (pick any)

* Generate a **Mermaid diagram** that shows lattice tiling + virtual-structure mapping + failure fill algorithm.
* Produce a **detailed simulation example** for Swarm Squad (complete Python module) that demonstrates tiling, assignment, PD control, and local repair after random failures.
* Provide a **proof sketch** for convergence of the consensus/gradient controller (if you want the math formalized).
* Create a **visualization script** using Dash/Matplotlib that animates lattice assignment and local repair.

Which of those should I produce next?



i will want to use HEX. and lattice is just for scalabliility


Perfect — a **hexagonal lattice (HEX)** is an excellent choice for scalable swarm coordination. It’s one of the most efficient spatial distributions for coverage, communication, and collision avoidance. Let’s go over how you can integrate it into your **Swarm Squad** system for real and simulated drones.

---

## 🧮 1. Why a Hexagonal Lattice Works for Swarms

The **hexagonal lattice** gives every drone **six equidistant neighbors**, forming a naturally stable, dense, and scalable structure. It’s mathematically ideal for:

* **Coverage efficiency:** Each drone covers the maximum area with minimal overlap.
* **Robust connectivity:** Six neighbors → redundant paths for communication and navigation.
* **Decentralized scalability:** Adding drones simply extends the lattice pattern without global reconfiguration.
* **Obstacle navigation:** Holes or distortions in the lattice automatically reflow locally.

---

## 🧠 2. Lattice-Based Position Control (Formation Layer)

For each drone ( i ), define its **target position** ( p_i^* ) relative to the swarm centroid ( C ):

[
p_i^* = C + R_i \cdot H(\theta_i)
]

Where:

* ( R_i ) = radial distance from centroid (determined by lattice ring)
* ( \theta_i ) = angular offset within that ring
* ( H(\theta) ) = unit vector function for hex grid direction

The six primary lattice direction vectors (unit hex grid) are:
[
H_k =
\begin{bmatrix}
\cos(k \cdot 60°) \
\sin(k \cdot 60°)
\end{bmatrix}
, \quad k = 0, 1, 2, 3, 4, 5
]

This creates perfect tiling and keeps distance uniform even as swarm grows.

---

## ⚙️ 3. Local Rule for Drone Movement

Each drone computes its **local offset** from the ideal lattice node:
[
u_i = k_p (p_i^* - p_i) + k_n \sum_{j \in N_i} (p_j - p_i)
]

* ( k_p ): global lattice stiffness
* ( k_n ): neighbor coupling gain
* ( N_i ): set of six nearest neighbors

This control law keeps drones at their ideal lattice spacing, even if global GPS is denied — as long as they can sense/communicate with neighbors.

---

## 🔐 4. Integration with Communication Layer

Tie this to your earlier encrypted communication model:

* Each drone broadcasts **position, velocity, and local hex index** in encrypted packets.
* Neighbors use **CMD_ID + drone ID** to prevent stale updates.
* Only neighboring drones (within a hex radius = 1) process these updates.
* If a drone loses contact with one or more neighbors, it uses **local interpolation** to re-establish its cell center until reconnection.

---

## 🔄 5. Handling GPS Denial

In GPS-denied environments:

1. Maintain **relative positioning** via UWB, optical flow, or RSSI.
2. Compute **relative hex node** positions using local distance + direction estimates.
3. Use **swarm centroid estimation** from consensus averaging:
   [
   C_i = \frac{1}{|N_i| + 1}\left(p_i + \sum_{j \in N_i} p_j\right)
   ]
   Each drone converges to the same estimated centroid without needing GPS.

---

## 💻 6. Implementation in *Swarm Squad*

You can integrate the lattice logic as a **FormationController** module:

```python
class HexLatticeFormation:
    def __init__(self, spacing):
        self.spacing = spacing  # meters between neighbors

    def hex_position(self, index):
        ring = int((3*index + 1)**0.5)  # hex ring number
        theta = (index % 6) * np.pi/3
        r = ring * self.spacing
        return np.array([r * np.cos(theta), r * np.sin(theta)])

    def update(self, drone, neighbors):
        target = self.hex_position(drone.lattice_index)
        correction = Kp*(target - drone.position)
        neighbor_term = Kn*sum((n.position - drone.position) for n in neighbors)
        drone.velocity_command = correction + neighbor_term
```

---

## 🗺️ 7. Example Visualization (Mermaid Diagram)

Here’s a conceptual flow of how the **control and communication layers** interact in your swarm:

```mermaid
graph TD
    C[🧠 Swarm Controller] -->|CMD_ID, Target Formation| X[Drone X]
    C --> Y[Drone Y]
    C --> Z[Drone Z]
    
    subgraph HEX-Lattice Formation
        X -->|Neighbor Updates| Y
        Y -->|Neighbor Updates| Z
        Z -->|Neighbor Updates| X
    end

    X -->|Encrypted Position Packet| Y
    Y -->|Encrypted Position Packet| Z
    Z -->|Encrypted Position Packet| X

    X -->|ACK| C
    Y -->|ACK| C
    Z -->|ACK| C

    subgraph Local Control Law
        Xc[(u_i = k_p(p_i*-p_i) + k_nΣ(p_j-p_i))] 
        Yc[(u_i = k_p(p_i*-p_i) + k_nΣ(p_j-p_i))] 
        Zc[(u_i = k_p(p_i*-p_i) + k_nΣ(p_j-p_i))] 
    end

    X --> Xc
    Y --> Yc
    Z --> Zc
```

---

## ⚡ Summary

| Goal                              | Solution                                              |
| --------------------------------- | ----------------------------------------------------- |
| Efficient scalable swarm geometry | Hexagonal lattice spacing                             |
| Easy full-swarm movement          | Offset all lattice nodes by swarm centroid vector     |
| GPS-denied operation              | Local relative positioning + consensus centroid       |
| Security & reliability            | Encrypted neighbor messages with CMD_ID deduplication |
| Robustness to dropout             | Local interpolation and lattice reformation           |

---

Would you like me to generate a **3D version** of the hex-lattice model (like a volumetric hex grid for altitude-separated swarms)? It’s the natural next step if you want your drones to form 3D layers or fly in vertical formations.



how would i make modifications to the controller that exists for the swarm controll


https://raw.githubusercontent.com/Swarm-Squad/Swarm-Squad-Ep1/refs/heads/main/src/swarm_squad_ep1/controllers/behavior_controller.py


"""
Behavior-based controller implementing obstacle avoidance, wall following,
and destination control behaviors.
"""

import numpy as np

import swarm_squad_ep1.config as config
from swarm_squad_ep1.controllers.base_controller import BaseController
from swarm_squad_ep1.models.swarm_state import SwarmState


class BehaviorController(BaseController):
    """
    Controller that implements behavior-based control strategies.

    This controller handles behaviors such as:
    - Obstacle avoidance
    - Wall following
    - Destination reaching
    - Return-to-launch (RTL) behavior for jammed agents
    """

    def __init__(self, swarm_state: SwarmState):
        """
        Initialize the behavior controller.

        Args:
            swarm_state: Reference to the swarm state object
        """
        print("BREAKPOINT: BehaviorController initialized")
        super().__init__(swarm_state)

    def compute_control(self) -> np.ndarray:
        """
        Calculate behavior-based control inputs for all agents.

        Returns:
            A numpy array of shape (swarm_size, 2) containing the control
            inputs for each agent in the swarm.
        """
        # print(
        #     f"BREAKPOINT: BehaviorController.compute_control called at iteration {self.swarm_state.iteration}"
        # )
        # Reset control inputs
        control_inputs = np.zeros((self.swarm_state.swarm_size, 2))

        # Apply behavior-based control for each agent
        for i in range(self.swarm_state.swarm_size):
            # For agents affected by high-power jamming, return to launch
            if not self.swarm_state.agent_status[i]:
                self._add_rtl_behavior(control_inputs, i)
                continue

            # Normal behavior for active agents
            has_obstacle_influence = False

            # Only consider hard obstacles if in hard obstacle mode
            if config.OBSTACLE_MODE == config.ObstacleMode.HARD:
                # Check for obstacle collisions and apply avoidance
                for obstacle in self.swarm_state.obstacles:
                    obstacle_pos = np.array([obstacle[0], obstacle[1]])
                    obstacle_radius = obstacle[2]

                    # Calculate distance to obstacle center
                    dist_to_center = np.linalg.norm(
                        self.swarm_state.swarm_position[i] - obstacle_pos
                    )

                    # Define buffer zones
                    buffer_zone = obstacle_radius + 6.0
                    wall_follow_zone = obstacle_radius + 3.0

                    if dist_to_center < buffer_zone:  # If within buffer zone
                        has_obstacle_influence = True
                        if dist_to_center < wall_follow_zone:
                            # Apply strong avoidance when very close
                            self._add_obstacle_avoidance(
                                control_inputs, i, obstacle_pos, obstacle_radius
                            )
                            # Minimal destination control when very close to obstacle
                            self._add_destination_control(control_inputs, i, weight=0.3)
                        else:
                            # Apply wall following when in outer buffer zone
                            wall_normal = (
                                self.swarm_state.swarm_position[i] - obstacle_pos
                            ) / dist_to_center
                            wall_pos = obstacle_pos + wall_normal * obstacle_radius
                            self._add_wall_following(
                                control_inputs, i, wall_pos, wall_normal
                            )
                            # Reduced destination control during wall following
                            self._add_destination_control(control_inputs, i, weight=0.4)

            # If not influenced by any obstacle, apply normal destination control
            if not has_obstacle_influence:
                self._add_destination_control(control_inputs, i, weight=1.0)

        return control_inputs

    def _add_rtl_behavior(self, control_inputs: np.ndarray, agent_index: int):
        """
        Add return-to-launch control input for an agent affected by jamming.

        Args:
            control_inputs: The array of control inputs to modify
            agent_index: Index of the agent to control
        """
        # RTL parameters
        rtl_magnitude = 0.8  # Slightly slower return speed

        # Calculate vector to initial position
        rtl_vector = (
            self.swarm_state.initial_positions[agent_index]
            - self.swarm_state.swarm_position[agent_index]
        )
        dist_to_home = np.linalg.norm(rtl_vector)

        # If very close to home, stop
        if dist_to_home < 0.5:
            control_inputs[agent_index] = np.zeros(2)
            return

        # Calculate direction and apply speed
        if dist_to_home > 0:  # Avoid division by zero
            rtl_direction = rtl_vector / dist_to_home

            # Scale control input based on distance
            control_param = min(rtl_magnitude, dist_to_home * 0.1)

            # Apply to control input
            control_inputs[agent_index] = rtl_direction * control_param

    def _add_destination_control(
        self, control_inputs: np.ndarray, agent_index: int, weight=1.0
    ):
        """
        Add destination-reaching control input for an agent.

        Args:
            control_inputs: The array of control inputs to modify
            agent_index: Index of the agent to control
            weight: Weight factor for the control input (0.0-1.0)
        """
        # Parameters for destination control
        am = config.DESTINATION_ATTRACTION_MAGNITUDE
        bm = config.DESTINATION_DISTANCE_THRESHOLD

        # Calculate vector to destination
        destination_vector = (
            self.swarm_state.swarm_destination
            - self.swarm_state.swarm_position[agent_index]
        )
        dist_to_dest = np.linalg.norm(destination_vector)

        if dist_to_dest > 0:  # Avoid division by zero
            destination_direction = destination_vector / dist_to_dest

            # Scale control input based on distance
            if dist_to_dest > bm:
                control_param = am
            else:
                control_param = am * (dist_to_dest / bm)

            # Apply weight to control input
            control_update = weight * destination_direction * control_param
            control_inputs[agent_index] += control_update

    def _add_obstacle_avoidance(
        self,
        control_inputs: np.ndarray,
        agent_index: int,
        obstacle_position: np.ndarray,
        obstacle_radius: float,
    ):
        """
        Add obstacle avoidance control input for an agent.

        Args:
            control_inputs: The array of control inputs to modify
            agent_index: Index of the agent to control
            obstacle_position: Position of the obstacle
            obstacle_radius: Radius of the obstacle
        """
        # Avoidance parameters
        ao = config.OBSTACLE_AVOIDANCE_MAGNITUDE
        bo = config.OBSTACLE_INFLUENCE_RANGE

        # Calculate vector away from the obstacle
        obstacle_vector = (
            self.swarm_state.swarm_position[agent_index] - obstacle_position
        )
        dist_to_obstacle = np.linalg.norm(obstacle_vector)

        if dist_to_obstacle < (obstacle_radius + bo):
            avoidance_direction = obstacle_vector / dist_to_obstacle

            # Stronger exponential scaling for more aggressive close-range avoidance
            proximity_factor = np.exp(-0.3 * (dist_to_obstacle - obstacle_radius))
            control_param = (
                ao
                * proximity_factor
                * (1 + 1 / (dist_to_obstacle - obstacle_radius + 0.1))
            )

            # Add to existing control input
            control_inputs[agent_index] += avoidance_direction * control_param

    def _add_wall_following(
        self,
        control_inputs: np.ndarray,
        agent_index: int,
        wall_position: np.ndarray,
        wall_normal: np.ndarray,
    ):
        """
        Add wall-following control input for an agent.

        Args:
            control_inputs: The array of control inputs to modify
            agent_index: Index of the agent to control
            wall_position: Position on the wall closest to the agent
            wall_normal: Normal vector perpendicular to the wall
        """
        # Wall following parameters
        af = config.WALL_FOLLOWING_MAGNITUDE
        df = config.WALL_DISTANCE

        # Calculate perpendicular distance to wall
        agent_position = self.swarm_state.swarm_position[agent_index]
        distance_to_wall = np.dot(agent_position - wall_position, wall_normal)

        # Calculate tangent direction (clockwise around obstacle)
        tangent_direction = np.array([-wall_normal[1], wall_normal[0]])

        # Enhanced wall following behavior
        if abs(distance_to_wall) > df:
            # Stronger correction when too close or too far from wall
            correction = -np.sign(distance_to_wall) * wall_normal
            # Increase correction influence
            control = af * (0.4 * tangent_direction + 0.6 * correction)
        else:
            # Stronger wall following when at good distance
            control = 1.2 * af * tangent_direction

        control_inputs[agent_index] += control


https://raw.githubusercontent.com/Swarm-Squad/Swarm-Squad-Ep1/refs/heads/main/src/swarm_squad_ep1/controllers/formation_controller.py


"""
Communication-aware controller that implements formation control logic.
"""

import numpy as np

import swarm_squad_ep1.config as config
import swarm_squad_ep1.utils as utils
from swarm_squad_ep1.controllers.base_controller import BaseController
from swarm_squad_ep1.models.swarm_state import SwarmState


class FormationController(BaseController):
    """
    Controller that implements communication-aware formation control logic.

    This controller maintains communication quality between agents by adjusting
    their positions to ensure connectivity while keeping a desired formation.
    """

    def __init__(self, swarm_state: SwarmState):
        """
        Initialize the formation controller.

        Args:
            swarm_state: Reference to the swarm state object
        """
        print("BREAKPOINT: FormationController initialized")
        super().__init__(swarm_state)

    def compute_control(self) -> np.ndarray:
        """
        Calculate control inputs for formation control.

        Returns:
            A numpy array of shape (swarm_size, 2) containing the control
            inputs for each agent in the swarm.
        """
        # print(
        #     f"BREAKPOINT: FormationController.compute_control called at iteration {self.swarm_state.iteration}"
        # )
        # Reset control inputs
        control_inputs = np.zeros((self.swarm_state.swarm_size, 2))

        # Formation control - only for active agents
        for i in range(self.swarm_state.swarm_size):
            # Skip agents affected by high-power jamming (returning to launch)
            if not self.swarm_state.agent_status[i]:
                continue

            for j in [
                x
                for x in range(self.swarm_state.swarm_size)
                if x != i and self.swarm_state.agent_status[x]
            ]:
                rij = utils.calculate_distance(
                    self.swarm_state.swarm_position[i],
                    self.swarm_state.swarm_position[j],
                )
                aij = utils.calculate_aij(
                    config.ALPHA, config.DELTA, rij, config.R0, config.V
                )

                # Only apply formation control if communication quality is above threshold
                if aij >= config.PT:
                    rho_ij = utils.calculate_rho_ij(
                        config.BETA, config.V, rij, config.R0
                    )
                else:
                    rho_ij = 0

                qi = self.swarm_state.swarm_position[i, :]
                qj = self.swarm_state.swarm_position[j, :]
                eij = (qi - qj) / np.sqrt(rij)

                # Formation control input
                control_inputs[i] += rho_ij * eij

        return control_inputs

    def update_swarm_state(self):
        """
        Update the swarm state based on agent interactions.

        This method calculates and updates the communication quality,
        distance matrices, and other state information.
        """
        # Update communication matrices
        self.swarm_state.update_matrices()

        # Compute and apply control inputs
        control_inputs = self.compute_control()

        # For agents affected by high-power jamming, get return-to-launch control
        # from the behavior controller
        if config.OBSTACLE_MODE == config.ObstacleMode.HIGH_POWER_JAMMING:
            # Import here to avoid circular imports
            from swarm_squad_ep1.controllers.behavior_controller import (
                BehaviorController,
            )

            rtl_controller = BehaviorController(self.swarm_state)

            for i in range(self.swarm_state.swarm_size):
                if not self.swarm_state.agent_status[i]:
                    # Calculate RTL control for returning agents
                    rtl_inputs = np.zeros((self.swarm_state.swarm_size, 2))
                    rtl_controller._add_rtl_behavior(rtl_inputs, i)
                    control_inputs[i] = rtl_inputs[i]

        self.apply_control(control_inputs)

        # Update performance metrics
        self.swarm_state.update_performance_metrics()

        # Store current positions for trajectory visualization
        self.swarm_state.update_swarm_paths()

        # Increment iteration counter
        self.swarm_state.iteration += 1


https://raw.githubusercontent.com/Swarm-Squad/Swarm-Squad-Ep1/refs/heads/main/src/swarm_squad_ep1/controllers/base_controller.py


"""
Base controller interface defining the common methods for all controllers.
"""

from abc import ABC, abstractmethod

import numpy as np

from swarm_squad_ep1.models.swarm_state import SwarmState


class BaseController(ABC):
    """
    Abstract base class for all controllers.

    Controllers must implement the compute_control method which calculates
    control inputs for each agent in the swarm.
    """

    def __init__(self, swarm_state: SwarmState):
        """
        Initialize the controller with a reference to the swarm state.

        Args:
            swarm_state: Reference to the swarm state object
        """
        self.swarm_state = swarm_state

    @abstractmethod
    def compute_control(self) -> np.ndarray:
        """
        Calculate control inputs for all agents in the swarm.

        Returns:
            A numpy array of shape (swarm_size, 2) containing the control
            inputs for each agent in the swarm.
        """
        pass

    def apply_control(self, control_inputs: np.ndarray = None):
        """
        Apply computed control inputs to update agent positions.

        Args:
            control_inputs: Optional control inputs to apply. If None,
                compute_control() will be called to get control inputs.
        """
        if control_inputs is None:
            control_inputs = self.compute_control()

        # Apply the control inputs to the swarm state
        self.swarm_state.swarm_control_ui = control_inputs
        self.swarm_state.swarm_position += control_inputs

Excellent — you’ve already got a clean modular controller setup in *Swarm Squad*.
Now that you want to integrate **hexagonal lattice formation control** and **decentralized communication-aware movement**, you’ll modify the system by **adding a specialized controller subclass** rather than altering the existing base or formation controllers directly.

This keeps your architecture extensible, backward-compatible, and simulation-friendly.

Let’s go step by step 👇

---

## 🧩 1. Add a New Controller: `HexLatticeController`

You’ll subclass from `BaseController` just like `FormationController`, but the key difference is that you’ll **compute lattice-relative target positions** rather than pairwise attraction/repulsion forces.

Below is a prototype implementation ready to integrate:

```python
"""
Hexagonal lattice-based formation controller.
Maintains scalable, communication-aware swarm geometry.
"""

import numpy as np
from swarm_squad_ep1.controllers.base_controller import BaseController
from swarm_squad_ep1.models.swarm_state import SwarmState

import swarm_squad_ep1.config as config
import swarm_squad_ep1.utils as utils


class HexLatticeController(BaseController):
    """
    Controller implementing a scalable hexagonal-lattice swarm formation.

    Each drone aligns to a virtual lattice node relative to the swarm centroid.
    Drones communicate only with local neighbors for robustness and scalability.
    """

    def __init__(self, swarm_state: SwarmState, spacing: float = 10.0):
        """
        Initialize the hex lattice controller.

        Args:
            swarm_state: SwarmState reference
            spacing: Desired spacing between neighboring drones (m)
        """
        print("BREAKPOINT: HexLatticeController initialized")
        super().__init__(swarm_state)
        self.spacing = spacing

        # Precompute lattice layout indices
        self.lattice_positions = self._generate_hex_lattice(
            swarm_state.swarm_size, spacing
        )

    def _generate_hex_lattice(self, n_agents: int, spacing: float):
        """
        Generate 2D hexagonal lattice positions for the swarm.

        Returns:
            ndarray of shape (n_agents, 2)
        """
        positions = []
        layer = 0
        idx = 0

        while len(positions) < n_agents:
            if layer == 0:
                positions.append([0, 0])
            else:
                for side in range(6):
                    for step in range(layer):
                        if len(positions) >= n_agents:
                            break
                        angle = np.deg2rad(60 * side)
                        x = (layer * np.cos(angle) - step * np.sin(angle)) * spacing
                        y = (layer * np.sin(angle) + step * np.cos(angle)) * spacing
                        positions.append([x, y])
            layer += 1

        return np.array(positions[:n_agents])

    def compute_control(self) -> np.ndarray:
        """
        Compute control inputs based on hex-lattice target positions.
        """
        swarm_positions = self.swarm_state.swarm_position
        swarm_centroid = np.mean(swarm_positions, axis=0)
        control_inputs = np.zeros_like(swarm_positions)

        # Compute each agent’s target lattice position
        for i in range(self.swarm_state.swarm_size):
            target_global = swarm_centroid + self.lattice_positions[i]
            error_vector = target_global - swarm_positions[i]
            control_inputs[i] = config.KP_LATTICE * error_vector

            # Communication-aware adjustment
            for j in range(self.swarm_state.swarm_size):
                if i == j or not self.swarm_state.agent_status[j]:
                    continue

                rij = utils.calculate_distance(
                    swarm_positions[i], swarm_positions[j]
                )

                # Apply communication penalty if signal too weak
                if rij > config.COMMS_RADIUS:
                    control_inputs[i] -= config.KC_COMMS * (swarm_positions[j] - swarm_positions[i])

        return control_inputs

    def update_swarm_state(self):
        """
        Update the swarm state with computed hex-lattice control inputs.
        """
        self.swarm_state.update_matrices()
        control_inputs = self.compute_control()
        self.apply_control(control_inputs)
        self.swarm_state.update_performance_metrics()
        self.swarm_state.update_swarm_paths()
        self.swarm_state.iteration += 1
```

---

## ⚙️ 2. Configuration Parameters to Add in `config.py`

Add these lines to your configuration file to tune the behavior:

```python
# Hex lattice parameters
KP_LATTICE = 0.08       # Position stiffness gain
KC_COMMS = 0.05         # Communication penalty gain
COMMS_RADIUS = 50.0     # Maximum reliable communication distance (m)
```

---

## 🧠 3. How It Works

| Step                               | Description                                                                                                        |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **Lattice Generation**             | `_generate_hex_lattice()` creates the ideal hex grid pattern for the number of drones.                             |
| **Relative Anchoring**             | Each drone’s target is offset from the swarm centroid, so moving the centroid moves the entire formation.          |
| **Local Correction**               | Each drone steers toward its lattice node with proportional control (`KP_LATTICE`).                                |
| **Communication-Aware Adjustment** | If another drone moves beyond communication range, a penalty force maintains connectivity.                         |
| **Compatibility**                  | Can run alongside `BehaviorController` (for obstacle avoidance) or `FormationController` (for fallback formation). |

---

## 🔄 4. Swapping Controllers at Runtime

Since your controllers are all subclasses of `BaseController`, you can easily switch between them:

```python
from swarm_squad_ep1.controllers.hex_lattice_controller import HexLatticeController

swarm_controller = HexLatticeController(swarm_state, spacing=12.0)

while simulation_running:
    swarm_controller.update_swarm_state()
```

If you want to automatically switch between **Formation** and **Hex-Lattice** depending on conditions (e.g., communication loss or scaling), you can add a “ControllerManager” module that selects which control policy to use per iteration.

---

## 🧭 5. Optional Enhancements

* **3D Extension:** Add z-offsets per lattice layer to create stacked hex grids.
* **Neighbor Awareness:** Replace global loops with only nearest-neighbor updates for scalability.
* **Dynamic Scaling:** Adjust lattice spacing dynamically with swarm density or mission radius.
* **Decentralization:** Compute centroid via local consensus to eliminate single-point dependency.

---

Would you like me to show you how to integrate this **HexLatticeController** with the **BehaviorController** (so the drones still avoid obstacles and return to formation automatically)?
That integration pattern is very common in swarm robotics.
