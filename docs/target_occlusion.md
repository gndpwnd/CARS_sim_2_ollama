# Target Occlusion Detection for GPS-Denied Rovers Using Drone Anchors and ToF Measurements

## Geometric Occlusion Detection

Geometric detection checks if the set of distance measurements is self-consistent via geometry. In a clear line-of-sight (LOS) scenario, signals travel directly:contentReference[oaicite:0]{index=0}, so the distance circles/spheres from each anchor should converge at the rover. Obstacles cause non-line-of-sight (NLOS) errors when measured distances become invalid:contentReference[oaicite:1]{index=1}. The steps below test this by intersecting distance boundaries (a process akin to trilateration:contentReference[oaicite:2]{index=2}).

### 2D Occlusion Detection

In 2D, each anchor *i* at *(x_i, y_i)* defines a circle of radius *r_i* (the measured ToF distance). All circles should intersect at the rover if unobstructed:contentReference[oaicite:3]{index=3}. A lack of common intersection indicates one or more occluded (erroneous) measurements.

1. **Define anchor circles:** For each anchor *i* with measured distance *r_i*, form the circle equation:  
    \`\`\`
(x - x_i)^2 + (y - y_i)^2 = r_i^2
    \`\`\`
2. **Pairwise circle intersections:** For each pair of anchors *(i, j)*:  
    - Compute center separation:  
    \`\`\`
d_{ij} = sqrt((x_i - x_j)^2 + (y_i - y_j)^2)
    \`\`\`
    If *d_{ij} > r_i + r_j + tol* or *d_{ij} < |r_i - r_j| - tol*, the circles do not intersect (measurements inconsistent). Otherwise, compute the intersection points:  
    \`\`\`
a = (r_i^2 - r_j^2 + d_{ij}^2) / (2 * d_{ij})
h = sqrt(max(r_i^2 - a^2, 0))
x2 = x_i + a*(x_j - x_i) / d_{ij}
y2 = y_i + a*(y_j - y_i) / d_{ij}
x_int1 = x2 + h*(y_j - y_i)/d_{ij}
y_int1 = y2 - h*(x_j - x_i)/d_{ij}
x_int2 = x2 - h*(y_j - y_i)/d_{ij}
y_int2 = y2 + h*(x_j - x_i)/d_{ij}
    \`\`\`
3. **Check consistent intersection:** Test each candidate intersection *(x_int, y_int)* by computing its distance to every anchor *k*:  
    \`\`\`
error_k = | sqrt((x_int - x_k)^2 + (y_int - y_k)^2) - r_k |
    \`\`\`
   If an intersection yields *error_k ≤ tol* for all anchors, the measurements are consistent (no occlusion). If no common intersection is found within tolerance, one or more distances is invalid:contentReference[oaicite:4]{index=4}.  
4. **Infer occluded anchor(s):** If inconsistencies are found, identify the outliers:  
    - For each anchor *i*, temporarily exclude it and repeat the intersection check with the remaining anchors. If anchors *j, k* (and others) intersect consistently without anchor *i*, then *i*’s measurement is likely occluded.  
    - If exactly one exclusion yields a valid solution, that anchor is occluded. If multiple anchors must be excluded, multiple occlusions exist (further logic **this is in progress**).  
5. **(Recovery placeholder):** *Anchor repositioning logic would follow here (not covered).*

### 3D Occlusion Detection

In 3D, each anchor *i* at *(x_i, y_i, z_i)* defines a sphere of radius *r_i*. All spheres should intersect at the rover if unobstructed. The approach is analogous: intersect spheres pairwise to form circles, then intersect with a third sphere.

1. **Define anchor spheres:** For each anchor *i*, form the sphere equation:  
    \`\`\`
(x - x_i)^2 + (y - y_i)^2 + (z - z_i)^2 = r_i^2
    \`\`\`
2. **Pairwise sphere intersections:** For each pair *(i, j)*:  
    - Compute center distance:  
    \`\`\`
d_{ij} = sqrt((x_i - x_j)^2 + (y_i - y_j)^2 + (z_i - z_j)^2)
    \`\`\`
    - If *d_{ij} > r_i + r_j + tol* or *d_{ij} < |r_i - r_j| - tol*, spheres do not intersect. Otherwise, compute their intersection circle:  
    \`\`\`
a = (r_i^2 - r_j^2 + d_{ij}^2) / (2 * d_{ij})
h = sqrt(max(r_i^2 - a^2, 0))
x2 = x_i + a*(x_j - x_i) / d_{ij}
y2 = y_i + a*(y_j - y_i) / d_{ij}
z2 = z_i + a*(z_j - z_i) / d_{ij}
    \`\`\`
    *(x2,y2,z2)* is the center of the circle of radius *h* formed by spheres *i* and *j*.  
3. **Intersect with third sphere:** With circle center *(x2,y2,z2)* and radius *h*, intersect with sphere *k*:  
    - Compute distance from anchor *k* to the circle center:  
    \`\`\`
d_c = sqrt((x_k - x2)^2 + (y_k - y2)^2 + (z_k - z2)^2)
    \`\`\`
    - If *d_c > r_k + h + tol* or *d_c < |r_k - h| - tol*, no intersection (invalid). Otherwise, solve for intersection points via:  
    \`\`\`
a2 = (h^2 - r_k^2 + d_c^2) / (2 * d_c)
h2 = sqrt(max(h^2 - a2^2, 0))
x_int = x2 + a2*(x_k - x2)/d_c ± h2*(...)
y_int = y2 + a2*(y_k - y2)/d_c ± h2*(...)
z_int = z2 + a2*(z_k - z2)/d_c ± h2*(...)
    \`\`\`  
4. **Check consistent intersection:** As in 2D, verify the candidate point(s):  
    \`\`\`
error_k = | sqrt((x_int - x_k)^2 + (y_int - y_k)^2 + (z_int - z_k)^2) - r_k |
    \`\`\`  
   If a solution yields errors ≤ *tol* for all anchors, distances are consistent. If no common 3D intersection is found, occlusion is indicated.  
5. **Infer occluded anchor(s):** Exclude each anchor in turn and repeat steps 2–4. If excluding anchor *i* restores consistency, then *i* is occluded. (Single vs. multiple occlusions as before.)  
6. **(Recovery placeholder):** *Anchor repositioning logic would follow here (not covered).*

## Odometry-Based Occlusion Detection

Odometry-based detection uses the rover’s known motion to validate range changes:contentReference[oaicite:5]{index=5}. The triangle inequality implies that moving the rover by distance *L* cannot change an anchor range by more than *L* under LOS.

1. **Compute motion:** From odometry, get rover displacement vector *(Δx, Δy, Δz)* and compute its magnitude:  
   \`\`\`
L = sqrt((Δx)^2 + (Δy)^2 + (Δz)^2)
   \`\`\`
2. **Range differences:** For each anchor *i*, compute the range change:  
   \`\`\`
Δr_i = r_{i,new} - r_{i,old}
   \`\`\`
3. **Check consistency:** If the absolute change exceeds *L + tol*, occlusion is likely:  
   \`\`\`
if |Δr_i| > L + tol:
    anchor i is occluded
   \`\`\`
   Otherwise, the measurement is consistent with motion (triangle inequality:contentReference[oaicite:6]{index=6}).  
4. **Optionally using angle:** If the angle *θ* between movement and anchor direction is known, use the law of cosines:  
   \`\`\`
r_{i,new,expected} = sqrt(r_{i,old}^2 + L^2 - 2*r_{i,old}*L*cos(θ))
if |r_{i,new} - r_{i,new,expected}| > tol:
    anchor i is occluded
   \`\`\`
5. **(Recovery placeholder):** *Anchor repositioning logic would follow here (not covered).*  

**Sources:** The above methods are based on geometric trilateration and NLOS detection principles:contentReference[oaicite:7]{index=7}:contentReference[oaicite:8]{index=8}:contentReference[oaicite:9]{index=9}.
