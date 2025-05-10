I have the following python script that triangulates the position of a rover in 3D space however does not account for the following possible situations. Please refactor the code to account for these situations and adjust calculations. Also please find any other situations that may cause error or uncertainty in calculations.

- can't handle certain instances, need to find out why - intersecting spheres, planes, lines, etc...
- might have two drones that are equidistant - might be throwing error.


- Coincident Drone Positions:
If two or more drones are positioned in such a way that they are equidistant or very close to each other, they may generate identical or nearly identical distances to the rover. This can lead to numerical instability in the localization algorithm. Specifically, when the positions of drones are nearly identical, the optimization algorithm (least_squares) may struggle because there is insufficient diversity in the data for accurate triangulation or multilateration.

- Singular or Near-Singular Matrix in Least Squares:
In the case of multilateration (where distances from drones are used to estimate the rover's position), if the drone positions are collinear or too close, the optimization problem becomes nearly degenerate. The Jacobian matrix for the least squares problem may become singular or near-singular, causing the algorithm to fail or return incorrect results. This can happen when drone positions are highly symmetric or aligned in a way that the problem lacks sufficient independent constraints to solve for the rover's position.

- Sphere-Sphere Intersection Issues:
Your sphere_sphere_intersection function attempts to find the intersection between spheres, which assumes that two spheres will intersect at a set of points (often a circle). However, when drone positions are too close to each other or identical, the intersection points may not be well-defined or could overlap significantly. This leads to a problem when trying to determine a valid intersection. As the error message suggests, this happens when no valid intersection is found, and the system falls back to multilateration.


There should be no error as there is no noise in the system, i do not want to add noise into the system so that i can see when there is any error. I want to keep the simulation as simple to the original as possible but simply adjust for the issues to ensure the is no error when calculating the rover position.

Below is the 3D script i want to modify, attatched is the example 2D scripts that work perfectly, of course the script that only has 2 drones is imperfect but it exemplifies the need for 3 or more drones.


make a function named angular_diversity that ensures at least any 4 given drones meet the angular diversity requirements necessary to calculate the rover's position. make  a function to check angular diversity, if not met then start moving drones. in the real world, drones will give feed back saying if they cannot move to a certain place such as being jammed or detecting objects in the way, set this boolean CAN_MOVE= True for all drones. verify CAN_MOVE for a drone every time you need to move after the fact of a random drone movement or random rover movement, Effectively, when the plot is updated and you are calculating the rover's position, check angular diversity requirements between any group of 4 drones, then if none of those combinations of 4 drones match the requirements, then start moving drones to new locations. pick the combination of 4 drones that are the closest to meeting the angular diversity requirements, then find new coordinates that would allow them to meet the angular diversity requirements. then adjust the drones, make a 2 second delay between finding the new positions, printing out the positional change information, and then actually updating the plot to show the new positions and information. 


NEED TO ADD MORE CONSTRAINTS

- IF THE ROVER IS AT THE ORIGIN, THEN THERE EXISTS A PLANE OF WHICH THE DRONES CANNOT EXIST IN RELATIVE TO THE ROVER - THE GROUND
  - this plane could be angled such as if the rover is on a hill. effectively
- IF THE DRONES ARE SET TO HOVER, THEY SHOULD EXIST IN THE SAME PLANE AS EACH WITHIN A CERTAIN TOLERANCE - EXAMPLE +/- 1m OF ALTITUDE

the drones are always above the xy-plane of the rover. OR if the rover is above the xy plane or below it, calculate the angle between the origin of the xy-plane and the rover, then normalize the xy-plane to the rover and make sure no drones spawn in this area. that way if the rover is on a hill, there will be no possibility of a drone being "in the hill" in the simulation. From here as well I would want to have the drones all spawn in the same xy plane with each other.



better yet when randomly placing drones, simply pick a random number between z=0 and z=10, then use that number + or minus DRONE_XY_PLANE_TOLERANCE to then give the drones random xy positions



I want to refactor the following simulation to where the drones all spawn in the same xy plane as each other, basically pick a z value between 1 and 10 and place the drones in that xy plane. I also want to add a constrain't that simulates the rover being on a hill. make a global variable named ROVER_ON_HILL = 10 for a 10 degree slope. basically, the drones in the real world will avoid objects, terrain, etc... and therefore if the rover is on a hill, there cannot exist any drones in that hill. to simulation the hill, when the rover is plotted, make sure the rover never is plotted above the z=5 xy plane. then select a random angle between 0 and 45 degrees. wherever the rover is relative to the origin, plot a rectangle that will represent a plane rotated from a level ground to the rover's position on an incline that is that angle relative to the original xy plane of z=0. Then make sure no drones exist past this plane in the plot, the drones must only exist between the rover and the origin, and then the quadrants where the rover is not, but also cannot be below the new plane.



Warning: Could not place all drones above hill after max attempts. simply take the area that is the hill plane and everything under the hill plane, then use this to select random xy positions for the drones after you select a random z value between 1 and 10 for the xy plane for the drones to be in. what is the full new code



- i want to be able to toggle of the view of the linear paths between the drones and the rover and the spheres of the drones generated using the linear paths as radii of the speheres to be able to see their intersections
- i want to be able to toggle the view of the circles of intersection between every sphere
- i want to have a slider to be able to change the angle of the hill plane between 0 and 90 degrees. but don't update the drone positions based on this slider, simply update the hill plane relative to the rover. then when the user clicks the drones positions button, take the new angle of the hill plane into consideration


ok now the rover should be at the point of most intersections, account for this in the code