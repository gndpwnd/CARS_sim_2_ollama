---
title: 8 - Comprehensive Variables and Constants
type: docs
prev: gps_denied_rover/7_GPS_specific_cybersecurity
next: gps_denied_rover/9_comprehensive_diagrams.md
sidebar:
  open: true
math: true
---

## Multilateration in 3 Dimensions

### Variables

*   **unknownPosition** $(x, y, z)$ - The coordinates of the point whose location is to be determined.
*   **knownPosition** $(x_i, y_i, z_i)$ - The coordinates of each known reference point (e.g., drone anchor).
*   **measuredDistance** $d_i$ - The measured distance from each known reference point to the unknown position.
*   **intersectionCircleCenter** $\mathbf{p}$ - The center coordinates of a circular intersection formed by two spheres.
*   **intersectionCircleNormalVector** $\mathbf{n}$ - The normal vector of the plane on which an intersection circle lies.
*   **intersectionCircleRadius** $h$ - The radius of an intersection circle formed by two spheres.
*   **leastSquaresMatrixA** $\mathbf{A}$ - A matrix constructed from the normal vectors of intersection planes for solving the system of plane equations.
*   **leastSquaresVectorB** $\mathbf{b}$ - A vector constructed from the dot products of normal vectors and plane centers.
*   **solutionVectorX** $\mathbf{x}$ - The unknown position vector obtained by solving the least squares system.
*   **candidatePoint** $(x_c, y_c)$ - A potential point where intersections occur (used in 2D for maximum intersection finding).
*   **intersectionCount** - The number of circles/spheres that a candidate point lies on within a given tolerance.
*   **error** $i$ - The difference between the calculated distance from a potential rover position to an anchor and the measured ToF distance, used to identify occluded anchors.
*   **epsilonGeo** - Geometric tolerance, typically set to 0.1 m, used for validating intersections and consistency.

### Constants

*   **minReferencePoints3D** - A minimum of **four known locations** is required to uniquely determine an unknown location in three dimensions.
*   **distanceSeparation** - Ideally, no known location should be the same distance from the unknown location as any other known location.
*   **angularSeparation** - Known locations should not be positioned at the same angle from the unknown location.
*   **nonCoplanarPositioning** - The four reference points should not be coplanar to ensure a unique 3D solution.
*   **altitudeConstraints** - Maintaining all drones within the same altitude creates an imaginary XY plane constraint.
*   **epsilon** - A tolerance value used in counting intersections for candidate points.

## Measuring Time-of-Flight using Radio Communication Between Two Devices/Drones

### Variables

*   **distance** $d$ - The distance between two transceivers.
*   **timeOneWay** $t$ - The time for a signal to travel one-way.
*   **roundTripTime** $\Delta t$ - The time for a signal to travel from transmitter to receiver and back.
*   **signalTransmissionTime** $T_1$ - The time when a signal is transmitted.
*   **acknowledgmentReceptionTime** $T_2$ - The time when an acknowledgment signal is received.
*   **roundTripTimeUncertainty** $\sigma_t$ - The uncertainty in round-trip time measurement.
*   **distanceAccuracy** $\Delta d$ or $\sigma_d$ - The error in distance measurement.
*   **positionAccuracy** $\sigma_{\mathrm{position}}$ - The accuracy of the overall position determined by multilateration.
*   **volumeUncertainty** $\sigma_V$ - The uncertainty in the 3D positioning volume.
*   **clockPrecision** $\Delta t$ - The required time resolution for a target distance accuracy.
*   **clockFrequency** $f_{\mathrm{clock}}$ - The required clock frequency for a target time resolution.
*   **signalFrequency** $f_{\mathrm{signal}}$ - The frequency of the radio signal used for ToF measurement.
*   **wavelength** $\lambda$ - The wavelength of the radio signal.
*   **processingDelay** $T_{\mathrm{offset}}$ - The total system delay, including signal detection, acknowledgment generation, transmission preparation, reception processing, and acknowledgment transmission.
*   **knownDistance** $d_{\mathrm{known}}$ - A precisely known distance used during calibration.
*   **measuredDistanceCalibration** $d_{\mathrm{measured}}$ - The distance calculated from raw ToF measurement during calibration.
*   **distanceOffset** $D_{\mathrm{offset}}$ - The difference between known and measured distances during calibration.
*   **actualDistance** $d_{\mathrm{actual}}$ - The distance after applying calibration offset.
*   **measuredTimeCalibration** - The raw measured time during calibration.
*   **universalTime** $t_{\mathrm{universal}}$ - A theoretical universal time reference.
*   **standardClockOffset** $\delta_{\mathrm{standard}}$ - The constant offset of the standard clock.
*   **standardClockError** $\epsilon_{\mathrm{standard}}$ - The drift rate of the standard clock.
*   **precisionClockOffset** $\delta_{\mathrm{precision}}$ - The constant offset of the precision clock.
*   **precisionClockError** $\epsilon_{\mathrm{precision}}$ - The drift rate of the precision clock.
*   **precisionClockActiveTime** $t_{\mathrm{active}}$ - The cumulative active time of the precision clock.
*   **baseStationReceptionTime** $T_{\mathrm{base}}$ - The time at which the base station receives data using its standard clock.
*   **synchronizationWindowTime** $\Delta t_{\mathrm{sync}}$ - The maximum time window for collecting all distance measurements to maintain position accuracy.
*   **maxRoverVelocity** $v_{\max}$ - The maximum velocity of the rover.
*   **stabilizationTime** $T_{\mathrm{stabilization}}$ - Time required for precision clock thermal stabilization.
*   **measurePhaseTime** $T_{\mathrm{measure\_phase}}$ - Time required for ToF measurements.
*   **transmitPhaseTime** $T_{\mathrm{transmit\_phase}}$ - Time required for data transmission.
*   **computeTime** $T_{\mathrm{compute}}$ - Time required for multilateration calculation.
*   **totalCycleTime** $T_{\mathrm{total}}$ - The sum of all times in a complete measurement cycle.
*   **precisionClockDutyCycle** $\mathrm{Duty}_{\mathrm{cycle}}$ - The percentage of time the precision clock is active.
*   **temperatureFrequencyRelationshipAlpha** $\alpha$ - The temperature coefficient for crystal oscillators relating temperature change to frequency change.
*   **residualTemperatureChange** $\Delta T_{\mathrm{residual}}$ - The remaining temperature instability after thermal stabilization.
*   **clockResolution** - The smallest measurable time increment of a clock.
*   **bandwidth** $BW$ - The bandwidth of the signal.
*   **signalToNoiseRatio** $SNR$ - The signal-to-noise ratio.

### Constants

*   **speedOfLightVacuum** $c \approx 2.998 \times 10^8 \ \mathrm{m/s}$ - Speed of light in vacuum.
*   **speedOfLightAir** $c_{\mathrm{air}} \approx 2.997 \times 10^8 \ \mathrm{m/s}$ - Speed of light in air.
*   **refractiveIndexAir** $n_{\mathrm{air}} \approx 1.0003$ - Refractive index of air at standard conditions.
*   **temperatureVariationImpact** $\pm 0.1\%$ - Speed variation per 30°C due to temperature.
*   **humidityImpact** - Negligible for radio frequencies.
*   **atmosphericPressureImpact** - Minimal impact at operational altitudes.
*   **geometricDilutionOfPrecision** GDOP = 1.22 (assumed for 4 agents) - A factor quantifying the effect of satellite/agent geometry on position accuracy.
*   **kGeometry** - A factor typically ranging from 1.2 to 2.5 depending on agent spatial distribution for position accuracy.
*   **targetVolumeAccuracy** $10 \ \mathrm{cm^3}$ - The target volume uncertainty for positioning.
*   **targetPositionalAccuracy** $\sigma_{\mathrm{position}} \approx 0.134 \ \mathrm{m}$ - Required positional accuracy to achieve 10 cm³ volume uncertainty.
*   **requiredDistanceAccuracy** $\sigma_d = 0.22 \ \mathrm{m}$ - Required distance accuracy to achieve 0.134 m positional accuracy.
*   **requiredClockPrecision** $\Delta t = 734 \ \mathrm{ps}$ - Required clock precision for 0.22 m distance accuracy.
*   **requiredClockFrequency** $f_{\mathrm{clock}} \geq 1.4 \ \mathrm{GHz}$ - Required clock frequency for 734 ps resolution.
*   **nyquistSamplingCriterion** - Sampling frequency must be at least twice the signal frequency ($f_{\mathrm{clock}} \geq 2 \times f_{\mathrm{signal}}$).
*   **practicalSafetyMargin** $10\times$ - A recommended safety margin for signal frequency ($f_{\mathrm{signal}} \leq f_{\mathrm{clock}}/2 \times 0.1$).
*   **maxAllowableSignalFrequency** $70 \ \mathrm{MHz}$ - Recommended maximum signal frequency for 1.4 GHz clock.
*   **minimumSeparationDistance** $d_{\mathrm{min}} = 4.28 \ \mathrm{m}$ - Minimum distance between agents to ensure far-field operation.
*   **transmitPower** $1 \ \mathrm{W}$ - Assumed transmitter power (30 dBm) for link budget analysis.
*   **receiverSensitivity** $-100 \ \mathrm{dBm}$ - Assumed receiver sensitivity for link budget analysis.
*   **linkBudget** $130 \ \mathrm{dB}$ - The total allowable path loss.
*   **practicalMaximumRange** $\sim 1 \ \mathrm{km}$ - The estimated maximum line-of-sight range.
*   **calibrationExampleKnownDistance** $10.00 \ \mathrm{m}$ - Example known distance for calibration.
*   **calibrationExampleMeasuredTime** $70.5 \ \mathrm{ns}$ - Example measured time during calibration.
*   **communicationSystemABandwidth** $\sim 1-10 \ \mathrm{kbps}$ - Lower bandwidth requirements for command and control.
*   **standardSystemClockPrecision** $1-100 \ \mathrm{MHz}$ - Typical precision for standard clocks.
*   **precisionClockThermalStabilizationPeriod** $100-500 \ \mathrm{ms}$ - Time needed for precision clock to stabilize.
*   **ToFMeasurementWindow** $1-10 \ \mathrm{ms}$ - Duration of high-precision ToF measurements.
*   **dataTransmissionPhase** $10-50 \ \mathrm{ms}$ - Duration for agents to transmit results.
*   **standardClockResolution** - The resolution of the standard clock, e.g., for a 100 MHz clock, this is 10 ns.
*   **clockActivationJitter** $\approx 100 \ \mathrm{ps}$ - Typical for precision oscillator startup, equivalent to 1.5 cm distance error.
*   **targetTemperatureStability** $\pm 0.1^{\circ} \mathrm{C}$ - Target stability for thermal management.
*   **thermalStabilizationError** $\approx 1.5 \ \mathrm{cm}$ - Error due to residual temperature instability.
*   **processingDelayStability** $\approx \pm 1 \ \mathrm{ns}$ - Typical stability for digital systems.
*   **urbanMultipathError** $\approx 0.1 \times \lambda$ - Estimated multipath error in urban environments.
*   **exampleSNR** $20 \ \mathrm{dB}$ - Example signal-to-noise ratio for error calculation.
*   **estimatedPrecisionClockPower** $5 \ \mathrm{W}$ - Estimated power consumption of a precision clock when active.
*   **estimatedStandardClockPower** $1 \ \mathrm{W}$ - Estimated power consumption of standard clocks.
*   **estimatedRadioSystemPower** $2 \ \mathrm{W}$ - Estimated average power consumption for radio systems.

## Detecting Target Occlusion Using Geometry

### Variables

*   **geometricTolerance** $\epsilon_{\mathrm{geo}}$ - A threshold for determining geometric consistency, set to 0.1m.
*   **anchorPosition2D** $(x_i, y_i)$ - Known 2D coordinates of the drone anchors.
*   **anchorPosition3D** $(x_i, y_i, z_i)$ - Known 3D coordinates of the drone anchors.
*   **ToFDistanceMeasurement** $r_i$ - The Time-of-Flight measured distance from anchor $i$ to the rover.
*   **centerSeparationDistance** $d_{ij}$ - The distance between the centers of two circles/spheres.
*   **circleIntersectionParameterA** $a$ - An intermediate calculation parameter for circle/sphere intersection.
*   **circleIntersectionParameterH** $h$ - An intermediate calculation parameter representing a half-chord length or radius of intersection circle.
*   **midpointIntersection** $(x_m, y_m)$ - Midpoint between two circle intersections.
*   **intersectionPoint1** $(x_{\mathrm{int1}}, y_{\mathrm{int1}})$ - The first intersection point of two circles.
*   **intersectionPoint2** $(x_{\mathrm{int2}}, y_{\mathrm{int2}})$ - The second intersection point of two circles.
*   **candidatePoint2D** $(x_k, y_k)$ - A candidate point for the rover's position in 2D, derived from pairwise circle intersections.
*   **distanceFromCandidateToAnchor** $d_{k,i}$ - The calculated distance from a candidate point to an anchor.
*   **intersectionCountCandidate** - The number of circles that intersect at a specific candidate point within the tolerance.
*   **roverPosition** $(\mathrm{x_{rover}}, \mathrm{y_{rover}})$ or $(\mathrm{x_{rover}}, \mathrm{y_{rover}}, \mathrm{z_{rover}})$ - The determined position of the rover.
*   **maximumIntersectionCount** $\mathrm{count_{max}}$ - The highest number of circles/spheres intersecting at a single point.
*   **distanceFromRoverToAnchor** $d_{\mathrm{rover},i}$ - The calculated distance from the determined rover position to an anchor.
*   **error** $i$ - The absolute difference between the calculated distance from the rover's position to anchor $i$ and the measured ToF distance $r_i$.

### Constants

*   **sampleAccuracyConstraint** $0.1 \ \mathrm{m}$ - The recommended value for geometric tolerance $\epsilon_{\mathrm{geo}}$.
*   **minAnchors2D** - A minimum of **three** known locations is required for 2D multilateration.
*   **minAnchors3D** - A minimum of **four** known locations is required for 3D multilateration.
*   **noOcclusionCondition** - $\mathrm{count_{max}} = n$, where $n$ is the total number of anchors.
*   **singleOcclusionCondition** - $\mathrm{count_{max}} = n-1$.
*   **multipleOcclusionCondition** - $\mathrm{count_{max}} < n-1$.
*   **minimumPositioningRequirements** - Must maintain $\ge 3$ anchors for 2D, $\ge 4$ for 3D during multiple occlusion analysis.

## Detecting Target Occlusion Using Odometry On-Board a Rover

### Variables

*   **odometryTolerance** $\epsilon_{\mathrm{odom}}$ - A threshold for validating odometry consistency, set to 0.05 m.
*   **roverDisplacementVector** $(\Delta x, \Delta y, \Delta z)$ - The displacement of the rover measured by odometry (e.g., wheel encoders, accelerometer).
*   **timeInterval** $\Delta t$ - The time duration over which displacement is measured.
*   **displacementMagnitude** $L$ - The scalar magnitude of the rover's displacement.
*   **apparentVelocity** $v_{\mathrm{apparent}}$ - The calculated velocity of the rover based on odometry.
*   **rangeDifference** $\Delta r_i$ - The change in measured range to anchor $i$ between new and old measurements ($r_{i,new} - r_{i,old}$).
*   **violationFlag** $\mathrm{violation}_i$ - A boolean indicating if anchor $i$ violates the triangle inequality constraint.
*   **roverHeading** $\theta$ - The current heading of the rover.
*   **anchorBearing** $\phi_i$ - The bearing from the rover to anchor $i$.
*   **expectedRange** $r_{i,expected}$ - The range to anchor $i$ predicted by the law of cosines based on previous range, displacement, and bearings.
*   **error** $i$ - The absolute difference between the new measured range and the expected range for anchor $i$.
*   **confidenceWeightGeometric** $w_{\mathrm{geo}}$ - Confidence weight for geometric detection.
*   **confidenceWeightOdometry** $w_{\mathrm{odom}}$ - Confidence weight for odometry detection.
*   **combinedOcclusionProbability** $P(\mathrm{occluded}_i)$ - The combined probability of occlusion for an anchor based on weighted geometric and odometry results.
*   **finalOcclusionStatus** $\mathrm{final\_occluded}_i$ - The final boolean decision for occlusion.

### Constants

*   **sampleAccuracyConstraintOdometry** $0.05 \ \mathrm{m}$ - The recommended value for odometry tolerance $\epsilon_{\mathrm{odom}}$.
*   **safetyFactorOpenField** $2.0$ - Safety factor for position jump detection in open field.
*   **safetyFactorUrbanCanyon** $3.0$ - Safety factor for position jump detection in urban canyon.
*   **safetyFactorForestCanopy** $4.0$ - Safety factor for position jump detection in forest canopy.
*   **safetyFactorMountainousTerrain** $5.0$ - Safety factor for position jump detection in mountainous terrain.
*   **minimumMeasurementsForTemporalFiltering** $N=5$ - Recommended sliding window size for temporal smoothing.
*   **violationPersistenceThreshold** $\ge 60\%$ - Percentage of recent measurements that must show violation for occlusion confirmation.
*   **violationMagnitudeThreshold** $2 \times \epsilon_{\mathrm{odom}}$ - Minimum violation magnitude for high confidence occlusion.
*   **confidenceWeightSum** $w_{\mathrm{geo}} + w_{\mathrm{odom}} = 1.0$ - Weights must sum to unity.
*   **fusionDecisionThreshold** $0.6$ - Threshold for deciding final occlusion status.
*   **disagreementLowerConfidenceThreshold** $0.4$ - Lower threshold for conservative approach during disagreement.
*   **k1_k2** - Factors for setting statistical detection thresholds based on desired false positive rate (e.g., $k=2$ for ~5% FP, $k=3$ for ~0.3% FP, $k=4$ for ~0.006% FP).

## Triggers for Determining that GPS Has Become Unreliable and Need to Switch to the Alternative Positioning System (APS)

### Variables

*   **fixQuality** - GPS receiver lock status (e.g., 3D, 2D, No Fix).
*   **lockDegradationEvents** - Number of times fix quality degrades within a period.
*   **reacquisitionTime** - Time taken for GPS receiver to reacquire lock (cold or warm start).
*   **trackedSatelliteCount** - Number of satellites currently being tracked by the GPS receiver.
*   **carrierToNoiseRatio** C/N₀ - Signal strength per channel.
*   **automaticGainControl** AGC voltage - Receiver's compensation for noise floor.
*   **checksumFailureRate** - Rate of corrupted NMEA/UBX messages.
*   **truncatedSentenceRate** - Rate of incomplete GPS sentences.
*   **parityErrorFrequency** - Frequency of parity errors in GPS data.
*   **horizontalAlertLimit** HAL - RAIM threshold for horizontal error.
*   **verticalAlertLimit** VAL - RAIM threshold for vertical error.
*   **timeToAlert** - Time for RAIM to issue an alert.
*   **positionJumpMagnitude** - Magnitude of sudden, unrealistic position changes.
*   **roverVelocity** - GPS-derived or actual rover speed.
*   **roverAcceleration** - GPS-derived or actual rover acceleration.
*   **rtkFixStatus** - RTK solution quality (RTK-FIX, RTK-FLOAT, DGPS, Single Point).
*   **carrierPhaseCycleSlipCount** - Number of detected cycle slips.
*   **insPosition** - Position predicted by the Inertial Navigation System (INS).
*   **gpsPosition** - Position derived from GPS.
*   **insDriftRate** - Rate at which INS accumulates error.
*   **insUncertainty** $\sigma_{\mathrm{INS}}$ - Uncertainty of the INS.
*   **gpsUncertainty** $\sigma_{\mathrm{GPS}}$ - Uncertainty of the GPS.
*   **combinedUncertainty** $\sqrt{\sigma_{\mathrm{INS}}^2 + \sigma_{\mathrm{GPS}}^2}$ - Combined uncertainty of INS and GPS.
*   **wheelEncoderSpeed** - Speed derived from wheel encoders.
*   **gpsHeadingRate** - Heading rate derived from GPS.
*   **imuYawRate** - Yaw rate from IMU.
*   **headingError** - Error in heading calculation.
*   **UWBdistanceError** - Difference between UWB-derived and GPS-calculated distances to drones.
*   **satelliteElevationAngle** - Angle of satellites above horizon.
*   **positionOscillationMagnitude** - Magnitude of position fluctuations, indicative of multipath.
*   **hdop** - Horizontal Dilution of Precision.
*   **pdop** - Position Dilution of Precision.
*   **gdop** - Geometric Dilution of Precision.
*   **gpsApsScore** - A weighted score indicating GPS reliability, used for APS activation decision.
*   **rmsRangeResiduals** - Root Mean Square error in distance measurements (for APS quality).
*   **solutionConvergenceTime** - Time for APS to achieve target accuracy.
*   **minActiveDrones** - Minimum number of active drones required for positioning.
*   **uwbPacketLoss** - Packet loss rate on UWB communication links.
*   **dronePositionUncertainty** - Uncertainty in known drone positions.
*   **clockFrequencyDrift** - Drift of the precision clock over measurement cycle.
*   **rangingSignalSNR** - Signal-to-noise ratio of ToF ranging signals.
*   **processingLatency** - Time taken for position solution updates.
*   **gpsApsDifference** - Difference between GPS and APS calculated positions during recovery.

### Constants

*   **detectionLatencyTarget** $\le 1 \ \mathrm{second}$ - Target response time for GPS denial detection.
*   **positionUpdateRateTarget** $1 \ \mathrm{Hz}$ - Target position update frequency.
*   **volumeAccuracyConstraintTarget** $10 \ \mathrm{cm^3}$ - Required positioning accuracy when operating.
*   **falsePositiveRateTarget** $< 1\%$ - Acceptable rate of incorrect denial detections.
*   **lockDegradationThreshold** $> 3$ in 10 seconds - Number of lock degradation events to trigger detection.
*   **reacquisitionTimeColdStart** $> 30 \ \mathrm{seconds}$ - Reacquisition time for cold start to trigger detection.
*   **reacquisitionTimeWarmStart** $> 5 \ \mathrm{seconds}$ - Reacquisition time for warm start to trigger detection.
*   **normalSatelliteCountOpenSky** $8-12$ satellites - Expected satellite count in open sky.
*   **satelliteCountWarningThreshold** $< 6$ satellites - Warning level for satellite count.
*   **satelliteCountCriticalThreshold** $< 4$ satellites - Critical level for satellite count.
*   **satelliteCountDropRate** $> 50\%$ drop in $< 5$ seconds - Rate of change to trigger detection.
*   **normalCN0OpenField** $40-50 \ \mathrm{dB-Hz}$ - Expected C/N₀ in open field.
*   **normalCN0LightFoliage** $35-45 \ \mathrm{dB-Hz}$ - Expected C/N₀ in light foliage.
*   **normalCN0UrbanCanyons** $25-40 \ \mathrm{dB-Hz}$ - Expected C/N₀ in urban canyons.
*   **normalCN0HeavyFoliage** $20-35 \ \mathrm{dB-Hz}$ - Expected C/N₀ in heavy foliage.
*   **checksumFailureRateThreshold** $> 5\%$ - Rate to indicate interference.
*   **truncatedSentenceRateThreshold** $> 2\%$ - Rate to indicate signal disruption.
*   **parityErrorFrequencyThreshold** $> 1\%$ - Rate to indicate data corruption.
*   **maxRoverSpeedExpected** $15 \ \mathrm{m/s}$ - Maximum expected speed for a land survey rover.
*   **maxRoverAccelerationLimit** $5 \ \mathrm{m/s^2}$ - Reasonable acceleration limit for terrain navigation.
*   **anomalyVelocityThreshold** $> 20 \ \mathrm{m/s}$ - Velocity exceeding this flags GPS error.
*   **anomalyAccelerationThreshold** $> 8 \ \mathrm{m/s^2}$ - Acceleration exceeding this flags GPS error.
*   **acceptableFixLossDuration** $< 2 \ \mathrm{seconds}$ - Normal GPS fluctuation.
*   **warningFixLossDuration** $2-5 \ \mathrm{seconds}$ - Begin APS preparation.
*   **criticalFixLossDuration** $> 5 \ \mathrm{seconds}$ - Force APS activation.
*   **towAnomalyJumpThreshold** $> 2 \ \mathrm{seconds}$ - TOW jumps to trigger anomaly detection.
*   **staticPositionNormalVariance** $\sigma_{\mathrm{position}} < 2.0 \ \mathrm{meters}$.
*   **staticPositionWarningVariance** $\sigma_{\mathrm{position}} = 2.0-5.0 \ \mathrm{meters}$.
*   **staticPositionCriticalVariance** $\sigma_{\mathrm{position}} > 5.0 \ \mathrm{meters}$.
*   **staticPositionJumpAPSActivation** $> 10 \ \mathrm{meters}$ - Position jump while stationary to trigger APS.
*   **insGpsAcceptableDifference** $|GPS_{position} - INS_{predicted}| < 3 \times \sigma_{\mathrm{uncertainty}}$.
*   **insGpsWarningDifference** $3\sigma \text{ to } 5\sigma$.
*   **insGpsCriticalDifference** $> 5\sigma$ or consistently growing.
*   **insGpsActivationCondition** - When GPS-INS difference exceeds bounds for $> 3$ consecutive measurements.
*   **imuGpsAngularRateConsistency** $|GPS_{heading\_rate} - IMU_{yaw\_rate}| < 10^{\circ}/\mathrm{s}$.
*   **gpsWheelEncoderSpeedConsistency** $|GPS_{speed} - Wheel_{encoder\_speed}| < 2 \ \mathrm{m/s}$.
*   **headingValidationThreshold** $15^{\circ}$ - Heading error to trigger GPS integrity warning.
*   **uwbDistanceConsistencyNormal** $< 0.5 \ \mathrm{meters}$ - Normal operation for UWB cross-validation.
*   **uwbDistanceConsistencyDegradation** $0.5-2.0 \ \mathrm{meters}$ - GPS degradation indication.
*   **uwbDistanceConsistencyFailure** $> 2.0 \ \mathrm{meters}$ consistently - GPS failure indication.
*   **uwbDistanceErrorTrigger** $> 2.0 \ \mathrm{m}$ for $> 3$ measurements - Triggers APS preparation.
*   **urbanCanyonLowerThresholdPercentage** $20\%$ - Lowering thresholds in urban environments.
*   **forestCanopyWarningExtension** $10 \ \mathrm{seconds}$ - Extend warning periods for APS activation.
*   **openFieldJammingResponse** $< 1 \ \mathrm{second}$ - Immediate APS activation.
*   **highPrecisionSurveyingAccuracy** $< 10 \ \mathrm{cm}$ - Required positioning for active surveying.
*   **transitPhaseAccuracy** $< 1 \ \mathrm{meter}$ - Acceptable positioning for transit.
*   **stationaryOperationsDrift** $< 50 \ \mathrm{cm}$ - Position holding requirement.
*   **apsScoreThresholdReliableGPS** $< 0.3$.
*   **apsScoreThresholdDegradedGPS** $0.3-0.6$.
*   **apsScoreThresholdUnreliableGPS** $> 0.6$.
*   **gpsToApsTransitionDelay** $1-5 \ \mathrm{seconds}$ (depending on criticality).
*   **apsToGpsTransitionDelay** $10-15 \ \mathrm{seconds}$ (minimum for GPS stability).
*   **emergencyTransitionDelay** $< 1 \ \mathrm{second}$.
*   **apsPreparationDuration** $2-10 \ \mathrm{seconds}$.
*   **precisionClockStabilizationPreActivation** $200 \ \mathrm{ms}$.
*   **initialApsPositionAccuracy** $< 0.2 \ \mathrm{m}$.
*   **convergedApsPositionAccuracy** $< 0.1 \ \mathrm{m}$.
*   **apsPositionUpdateRate** $1 \ \mathrm{Hz} \pm 50 \ \mathrm{ms}$.
*   **gpsRecoverySignalThreshold** Satellite count $> 6$, C/N₀ $> 35 \ \mathrm{dB-Hz}$ consistently.
*   **gpsRecoveryPositionConsistency** GPS-APS difference $< 0.5 \ \mathrm{m}$ for $> 15 \ \mathrm{seconds}$.
*   **gpsRecoveryStabilityConfirmation** No integrity flags for $> 30 \ \mathrm{seconds}$.
*   **urbanMaskAngleIncrease** from $5^{\circ}$ to $15^{\circ}$.
*   **urbanMultipathDetectionTrigger** position oscillations $> 3 \ \mathrm{m}$.
*   **droneNetworkMinimumActive** $4$ drones (for 3D).
*   **droneNetworkOptimal** $6-8$ drones.
*   **uwbRangingSNRThreshold** $> 20 \ \mathrm{dB}$.
*   **clockStabilityDriftThreshold** $< 0.1 \ \mathrm{ppm}$.
*   **singleDroneLossCapability** - Continue with reduced accuracy (5 drones minimum for 3D).
*   **extendedEnvironmentalCalibrationDuration** $\ge 4$ hours - For establishing baseline measurements.
*   **calibrationThresholdConfidence** $2-3$ sigma - For establishing detection thresholds.
*   **staticAlignmentTime** $15$-minute stationary initialization for INS/GPS.
*   **wheelOdometryKnownDistanceTest** Minimum $100$ meters for calibration.