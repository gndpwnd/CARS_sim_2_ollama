> https://spire.com/blog/aviation/understanding-multilateration-mlat-for-more-precise-aircraft-positioning-free-from-interference/
> https://adsbx.discourse.group/t/multilateration-mlat-how-it-works-and-why-you-should-care/325
> https://en.wikipedia.org/wiki/Trilateration
> https://en.wikipedia.org/wiki/True-range_multilateration

# README Summary for Drone-Based Multilateration and Trilateration Scripts

## Drone-based Multilateration and Trilateration Simulation

This README explains the theory and implementation of three Python scripts that simulate drone-based localization using distance measurements. The scripts demonstrate multilateration in 2D and 3D, contrasting it with traditional triangulation. In multilateration (or trilateration), known anchor positions (the drones) measure ranges to an unknown target. By intersecting geometric loci (circles or spheres), the target’s location can be determined. In contrast, triangulation uses measured angles with known baselines to find positions ([definitions.net](https://www.definitions.net), [gisgeography.com](https://gisgeography.com)). In modern navigation (e.g. GPS), only distances are used (trilateration) – no angles are involved.

### Key theoretical points:

- **Trilateration vs. Multilateration**: Trilateration uses distances from three (in 2D) or four (in 3D) anchors to locate a point ([definitions.net](https://www.definitions.net), [gisgeography.com](https://gisgeography.com)). When more than the minimum number of distances are used, the term multilateration often applies. For example, GPS (a trilateration system) uses at least four satellite ranges in 3D to fix a receiver’s position. With just two distances in 2D, there are generally two intersection points. A third distance resolves the ambiguity, pinpointing the unique location.

- **Triangulation**: In contrast, triangulation measures angles from two or more known points using instruments like theodolites. With one known baseline, angles to an unknown target can form triangles that determine distances ([mapscaping.com](https://mapscaping.com), [gisgeography.com](https://gisgeography.com)). Surveyors traditionally used triangulation, but GPS and our scripts rely on distance-based trilateration.

- **Circle and Sphere Intersections**: In 2D geometry, each distance constraint defines a circle centered at a drone. Two circles intersect in up to two points ([definitions.net](https://www.definitions.net), [people.csail.mit.edu](https://people.csail.mit.edu)). In 3D, each distance defines a sphere. Three spheres can intersect in two points (a two-way ambiguity). A fourth sphere (or other constraint) is needed to select the unique solution. For example, in a planar setting (all drones and target in one plane), the mirror-image solution persists; having anchors at different altitudes or adding a fourth range resolves this.

Below we describe each script in turn, outlining the mathematical core, assumptions, interactive features, and error estimation logic.

---

## Theoretical Background: Multilateration vs. Trilateration vs. Triangulation

- **Trilateration (Distance-Based)**: Uses measured distances (“ranges”) from an unknown point to three or more known anchors to determine the point’s coordinates ([definitions.net](https://www.definitions.net)). In 2D, three circles (or two circles + altitude info) suffice; in 3D, four spheres are typically needed. With exactly the minimum measurements, solutions may be ambiguous (two possible points). Additional ranges allow a least-squares fit to minimize measurement error ([definitions.net](https://www.definitions.net), [en.wikipedia.org](https://en.wikipedia.org/wiki/Trilateration)).

- **Multilateration**: Essentially trilateration with more distances. When many anchors provide redundant distances, the system is overdetermined. The scripts use nonlinear least squares (e.g. Gauss–Newton) to find the best-fit position that minimizes the squared range errors ([en.wikipedia.org](https://en.wikipedia.org/wiki/Multilateration)).

- **Triangulation (Angle-Based)**: Measures angles from two or more known points to the target. With a known baseline, each angle defines a line of sight. Solving the intersection of these lines locates the target. This approach does not appear in our scripts; it is traditionally used in surveying. Importantly, GPS and distance-based localizations do not use triangulation or any angle information ([gisgeography.com](https://gisgeography.com)).

---

## Summary

All three scripts implement trilateration/multilateration by computing intersections of circles (2D) or spheres (3D). We exploit the fact that each range defines a geometric shape containing the target, and multiple ranges narrow down that location. With more anchors than minimally required, we solve a nonlinear optimization to account for measurement noise and ensure a unique solution.

---

## `1-2_drones.py`: Basic 2D Multilateration (Two Drones)

This script demonstrates the simplest case: two fixed drones in a plane measure their distances to a stationary target (e.g. a ground rover). Each measured distance defines a circle centered on a drone. The target must lie on both circles, so its potential positions are the intersection points of the circles.

- **Mathematical Computation**: Uses the Euclidean distance formula  
  ```math
  d_i = \sqrt{(x - x_i)^2 + (y - y_i)^2}
  ```  
  for each drone *i*. The script solves the two circle equations simultaneously by subtracting one from the other to get a linear equation, then back-substituting.

- **Geometry outcomes**:
  - 0 intersections: circles are too far or fully separate.
  - 1 intersection: circles touch (tangent).
  - 2 intersections: target is ambiguous without more info.

- **Assumptions**: Flat 2D space; distances are ideal or have controllable noise; no angle data.

- **Features**:
  - Interactive Matplotlib: move drones/target, toggle circle visibility.
  - Observe real-time geometric behavior.
  - Simulate noise and see its effect.

- **Error Estimation**:
  - With two drones, location may be ambiguous.
  - Estimated error can be shown (e.g., between intersection and known target).
  - Residuals may be computed:
    ```math
    \sqrt{(x - x_i)^2 + (y - y_i)^2} - d_i
    ```

---

## `2-2D_multilateration.py`: General 2D Multilateration (Multiple Drones)

This script generalizes to **N ≥ 3** drones. Each drone (xᵢ, yᵢ) measures a distance dᵢ. Three or more drones allow unique localization (excluding degenerate cases).

- **Mathematical Computation**:  
  System of nonlinear equations:
  ```math
  (x - x_i)^2 + (y - y_i)^2 = d_i^2, \quad i = 1,\dots,N
  ```  
  Reformulated as a nonlinear least-squares problem:
  ```math
  \min_{x,y} \sum_{i=1}^N \left( \sqrt{(x - x_i)^2 + (y - y_i)^2} - d_i \right)^2
  ```  
  Solved via iterative methods (Gauss–Newton, Levenberg–Marquardt).

- **Assumptions**:
  - 2D environment.
  - Known drone positions.
  - Distances possibly noisy (often modeled with Gaussian noise).
  - At least 3 non-collinear drones required.

- **Features**:
  - Add/remove drones interactively.
  - Adjust noise levels.
  - Show range rings, estimated vs. true positions.
  - Visual feedback as geometry changes.

---

## `3-3D_multilateration.py`: 3D Multilateration (Four or More Drones)

This script extends the problem into **3D space**. Drones are located at known (xᵢ, yᵢ, zᵢ) positions and measure distances dᵢ to an unknown target location (x, y, z). Each distance defines a **sphere**. The intersection of these spheres determines the target’s position.

- **Mathematical Computation**:  
  Each equation is of the form:
  ```math
  (x - x_i)^2 + (y - y_i)^2 + (z - z_i)^2 = d_i^2
  ```  
  With **4 or more** equations (drones), the system is overdetermined and solved via nonlinear least-squares:
  ```math
  \min_{x,y,z} \sum_{i=1}^N \left( \sqrt{(x - x_i)^2 + (y - y_i)^2 + (z - z_i)^2} - d_i \right)^2
  ```

- **Geometry Notes**:
  - With 3 spheres, there may be 0, 1, or 2 intersections.
  - With 4+ spheres, extra information resolves ambiguity.
  - Redundant anchors reduce the effect of measurement noise.

- **Assumptions**:
  - 3D environment (e.g. drones flying at varying altitudes).
  - Measured distances may include noise.
  - At least four non-coplanar drones for a unique solution.

- **Features**:
  - Visualize drone and target positions in 3D (Matplotlib).
  - Add noise to simulate real-world conditions.
  - Display estimated vs. true target position.
  - Optional error statistics:  
    ```math
    \text{RMSE} = \sqrt{ \frac{1}{N} \sum_{i=1}^N ( \hat{d}_i - d_i )^2 }
    ```

---