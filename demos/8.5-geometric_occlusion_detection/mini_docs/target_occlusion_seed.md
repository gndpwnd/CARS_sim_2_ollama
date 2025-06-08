When operating in environments with significant terrain features, especially applicable to a GPS-denied land survey rover scenario, the rover may become occluded to the drones/agents that perform distannce measurements using ToF to then enable multilateration. How do you check for target occlusion when you don't use images?

## Geometric Occlusion Detection using ToF measurements and positional accuracy constraint

**TLDR:** Checking if there is a discrepancy in the ToF (distance measurments) between all the Child Drones and the Rover using geometry of anchor/drone positions. 

1. Set a constraint/tolerance - lets say we want to be within 0.1m^2
2. Collect all ToFs of the child drones and their positions
3. Given positions and ToF distances from the Child Drones, determine if target occlusion exists:
   1. Line Segment Convergence
      1. all distances should can be represented as a line segment
      2. starting each line segments at its relative drone/anchor point, the endpoints of the line segments should converge at a given point within the given constraint (0.1m^2)
      3. If the line segments are unable to converge within the constraint, one or more of the distances are off, and therefore the target (Rover) is occluded from one or more anchors (Child Drones)
   2. The calculations for determining occlusion using geometry, are similar to some of the multilateration calculations.
      1. Multilateration calculation similarites can be leveraged when determining line segment convergence.
      2. Use line segments to create circles that inherently intersect
      3. In multilateration, you calculate the point of most intersections
      4. For line segment convergence checking, you need to check to see if a point exists at which the number of intersections of circles matches the number of line segments
         1. Example - if there are 3 line segments coming from anchors/drones, then there should be a point of which 3 intersections occur, not only is this your rover position but this shows that the distance measurements are all guarunteed to be within your accuracy constraint.
         2. Example - if there are 3 line segments coming from anchors/drones, but there is not a point of which 3 intersections occur, then one or more of the line segments is the incorrect size
4. Determine if a single anchor is occluded or if multiple anchors are occluded:
   1. **this is in progress** - determining if just one line segment is the incorrect size based on accuracy constraint and therefore the relative anchor/drone is occluded from the rover
   2. **this is in progress** or if multiple line segments are the incorrect size compared to accuracy constraint then how to find which are incorrect in order to reposition multiple anchors/drones.
6. Recovery state for anchors occluded from target outside of tolerance
   1. move anchor/s using a pathfinding algorithm until not occluded from target
   2. keep track of ToF constraints and multilateration constraints

## Checking ToF measurements against Rover odometry and positional accuracy constraint

**TLDR:** Equipping the Rover to have onboard wheel/track encoders and accelerometer can assist in making multilateration decisions. If the rover has operated past a point of GPS signal loss, accounting for this may help in determining if the rover has become occluded from any anchors/drones that perform ToF measurements. 

1. Set a constraint/tolerance - lets say we want to be within 0.1m^2
2. Collect Rover odometry
   1. Accelerometer in x,y,z
   2. Wheel encoders
      1. identify encoder positions and account for movement operations like forward, backward, and turning
3. Handle timestamp offsets
   1. its very hard to sync clocks, so periodically checking the timestamp of the odometry data and determining a time offset will help a base station or parent drone to create a unified timestamp for all data collected across Rover and Child Drones
4. Identify abonormalities in odometry data
   1. if the wheel encoders convey movement, but the accelerometer does not, the rover is probably stuck
   2. if the accelerometer conveys movement, but the wheel encoders do not, the rover probably slipped, fell, etc.
5. Combine odometry data to make a guess at how far the rover has traveled without GPS location data and create a HEADLESS_POSITION which would contain this guess
6. Factor HEADLESS_POSITION into calculations
   1. **this is in progress**

## References

Amala Arokia Nathan, R. J., Kurmi, I., & Bimber, O. (2023). Drone swarm strategy for the detection and tracking of occluded targets in complex environments. Communications Engineering, 2(1), 55. https://doi.org/10.1038/s44172-023-00104-0
