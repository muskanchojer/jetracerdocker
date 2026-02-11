# VSLAM Mode Setup Guide

Complete guide for setting up and using the Visual-Inertial SLAM (VSLAM) mode on JetRacer with Jetson Orin Nano.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Installing PyCuVSLAM](#installing-pycuvslam)
4. [Installing Dependencies](#installing-dependencies)
5. [Camera-IMU Calibration](#camera-imu-calibration)
6. [Running VSLAM Mode](#running-vslam-mode)
7. [Troubleshooting](#troubleshooting)
8. [Performance Tuning](#performance-tuning)
9. [Advanced Features](#advanced-features)

## Overview

VSLAM mode provides real-time Visual-Inertial Odometry (VIO) using:
- **pycuvslam**: NVIDIA's CUDA-accelerated VSLAM library
- **Monocular camera**: USB webcam (640x480)
- **IMU**: 6-DOF inertial measurement unit
- **Rerun**: 3D visualization of trajectory and features

### Features

- ✅ Real-time 3D localization and mapping
- ✅ IMU + Camera sensor fusion for robust tracking
- ✅ No pre-built map required (online SLAM)
- ✅ Publishes odometry to `/vslam/odom` for navigation
- ✅ 3D visualization with Rerun
- ✅ Trajectory logging and export

## Prerequisites

### Hardware

- **Jetson Orin Nano** with JetPack 5.x or 6.x
- **USB Camera** (640x480, calibrated)
- **IMU** publishing to `/imu` topic in Docker ROS
- **Docker container** running with ROS and sensor drivers

### Software

- Ubuntu 22.04 (on Jetson)
- Python 3.8+
- CUDA 11.4+ (comes with JetPack)
- Docker with ROS Noetic container
- Camera and IMU drivers running in Docker

## Installing PyCuVSLAM

PyCuVSLAM is NVIDIA's CUDA-accelerated Visual SLAM library. It must be installed separately as it's not available via pip.

### Option 1: Pre-built Wheel (Recommended)

If available for your JetPack version:

```bash
# Check NVIDIA Isaac ROS releases or NVIDIA forums for pre-built wheels
# Example (adjust URL for your JetPack version):
pip install pycuvslam-<version>-cp38-cp38-linux_aarch64.whl
```

### Option 2: Build from Source

If no pre-built wheel is available:

```bash
# Install dependencies
sudo apt-get update
sudo apt-get install -y \
    cmake \
    build-essential \
    libeigen3-dev \
    libgflags-dev \
    libgoogle-glog-dev \
    libopencv-dev

# Clone cuVSLAM (if available) or use NVIDIA Isaac ROS
# Follow NVIDIA's official documentation for building cuVSLAM
# Example:
git clone https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_visual_slam.git
cd isaac_ros_visual_slam
# Follow build instructions in the repository
```

### Verify Installation

```bash
python3 -c "import pycuvslam; print('✅ pycuvslam installed')"
```

## Installing Dependencies

Install Python dependencies:

```bash
cd /home/runner/work/jetracerdocker/jetracerdocker

# Install dependencies
pip install -r requirements.txt

# Verify key packages
python3 -c "import rerun as rr; print('✅ Rerun installed')"
python3 -c "import yaml; print('✅ PyYAML installed')"
python3 -c "import scipy; print('✅ SciPy installed')"
```

## Camera-IMU Calibration

Proper calibration is critical for good VSLAM performance.

### Step 1: Camera Intrinsic Calibration

The repository already includes camera calibration from calibDB.net:
- **Camera**: USB2.0 PC CAMERA (640x480)
- **Intrinsics**: Already in `config/vslam_config.yaml`

If you need to recalibrate:

```bash
# Use OpenCV or ROS camera_calibration
rosrun camera_calibration cameracalibrator.py \
    --size 8x6 --square 0.024 \
    image:=/usb_cam/image_raw camera:=/usb_cam
```

### Step 2: IMU Noise Calibration

Calibrate IMU noise parameters for optimal sensor fusion:

```bash
# Keep robot completely stationary!
python3 scripts/calibrate_imu_noise.py --duration 60 --output config/imu_calibration.yaml
```

**Important**: Place robot on a stable surface with no vibrations during calibration.

The script will:
1. Record IMU data for 60 seconds
2. Calculate noise statistics
3. Compute noise density and random walk parameters
4. Save results to `config/imu_calibration.yaml`

Copy the output values to `config/vslam_config.yaml` under the `imu:` section.

### Step 3: Camera-IMU Transform

Measure the physical transformation between camera and IMU:

```bash
python3 scripts/measure_imu_camera.py
```

The script will prompt you to:
1. Measure the physical offset (translation) from IMU to camera
2. Describe the relative orientation (rotation)
3. Optionally update `config/vslam_config.yaml` automatically

**Example measurements**:
- Camera is 5cm forward, 2cm right, 1cm up from IMU: `[0.05, 0.02, 0.01]`
- Camera and IMU aligned (same orientation): `[0, 0, 0]` degrees
- Camera rotated 90° left: `[0, 0, 90]` degrees

## Running VSLAM Mode

### Start Docker Container

Ensure your ROS Docker container is running:

```bash
~/start_jetracer_docker.sh
```

Verify topics are available:

```bash
docker exec jetracer_ros bash -c "source /root/catkin_ws/devel/setup.bash && rostopic list | grep -E '(imu|image)'"
```

Expected output:
```
/imu
/usb_cam/image_raw
```

### Launch VSLAM Mode

#### From Main Menu

```bash
python3 main.py
```

Select option **5. VSLAM Mode (Visual-Inertial SLAM)**.

#### Direct Launch

```bash
python3 main.py --mode vslam --no-check
```

#### Standalone

```bash
python3 scripts/vslam_control.py
```

### What to Expect

When running, you'll see:

```
🚀 VSLAM Mode Running
==============================================================
  Press Ctrl+C to stop and save trajectory
==============================================================

📊 Statistics (runtime: 10.0s)
==============================================================
  Camera: 29.5 fps | IMU: 198.3 Hz
  Tracked frames: 295 | Success rate: 94.2%
  Trajectory points: 295
==============================================================

📍 Position: x=0.234, y=-0.012, z=0.456
```

### Rerun Visualization

If Rerun is enabled (default), a 3D viewer will open showing:
- **Camera pose** (blue coordinate frame)
- **Trajectory** (green line with points)
- **Feature points** (colored dots)
- **IMU data** (time series plots)

Navigate the 3D view with mouse:
- **Left click + drag**: Rotate
- **Right click + drag**: Pan
- **Scroll**: Zoom

### Stop and Save

Press **Ctrl+C** to stop VSLAM mode. The trajectory will be automatically saved to:

```
logs/vslam_trajectory_YYYYMMDD_HHMMSS.txt
```

Format:
```
# timestamp x y z qx qy qz qw
1234567890.123456 0.000000 0.000000 0.000000 0.0 0.0 0.0 1.0
1234567890.156789 0.012000 -0.003000 0.015000 0.0 0.0 0.01 0.9999
...
```

## Troubleshooting

### Issue: "Failed to import pycuvslam"

**Solution**: Install pycuvslam following [Installing PyCuVSLAM](#installing-pycuvslam).

### Issue: "Tracking failed" or low success rate (<80%)

**Causes**:
- Poor lighting conditions
- Fast motion (exceeds max_frame_delta_s)
- Insufficient features (texture-less environment)
- Incorrect calibration

**Solutions**:
1. Improve lighting (brighter, more uniform)
2. Slow down robot motion
3. Add visual features to environment (posters, objects)
4. Recalibrate camera and IMU
5. Adjust `max_features_per_frame` in config

### Issue: Camera FPS too low

**Solutions**:
1. Reduce camera resolution in config
2. Enable frame skipping: `skip_frames: 2`
3. Use compressed image transport (requires ROS setup)
4. Disable Rerun visualization temporarily

### Issue: "No IMU data" or "No camera data"

**Solution**: Check ROS topics are publishing:

```bash
docker exec jetracer_ros bash -c "source /root/catkin_ws/devel/setup.bash && rostopic hz /imu"
docker exec jetracer_ros bash -c "source /root/catkin_ws/devel/setup.bash && rostopic hz /usb_cam/image_raw"
```

If not publishing, check sensor drivers in Docker.

### Issue: High drift over time

**Causes**:
- IMU calibration inaccurate
- Poor camera-IMU synchronization
- Long-term operation without loop closure

**Solutions**:
1. Recalibrate IMU noise parameters
2. Verify camera-IMU transform is correct
3. Reduce `max_frame_delta_s` for stricter sync
4. For long runs, consider implementing loop closure

## Performance Tuning

### Optimize for Speed

Edit `config/vslam_config.yaml`:

```yaml
vslam:
  performance:
    skip_frames: 2  # Process every other frame
    max_features_per_frame: 150  # Reduce features
    
  camera:
    width: 640  # Keep at 640x480 or reduce to 320x240
    height: 480
    fps: 30  # Reduce if camera supports
    
  tracker:
    async_sba: true  # Keep enabled for async bundle adjustment
```

### Optimize for Accuracy

```yaml
vslam:
  performance:
    skip_frames: 1  # Process all frames
    max_features_per_frame: 300  # More features
    
  camera:
    width: 640
    height: 480
    fps: 30
```

### Memory Usage

Rerun visualization uses significant memory. Disable if needed:

```yaml
vslam:
  visualization:
    enable_rerun: false
```

## Advanced Features

### Custom Configuration

Create a custom config file:

```bash
cp config/vslam_config.yaml config/my_vslam_config.yaml
# Edit my_vslam_config.yaml
```

Use it:

```python
from scripts.vslam_control import VSLAMController
controller = VSLAMController(config_path='config/my_vslam_config.yaml')
controller.run()
```

### Publishing to ROS

The controller can publish odometry to ROS topics for use with navigation:

```yaml
vslam:
  ros:
    publish_odom: true
    odom_topic: "/vslam/odom"
    publish_rate: 30
```

To implement publishing, add to `scripts/vslam_control.py`:

```python
# In _on_camera_frame callback:
if result and result.get('success'):
    # Publish to ROS (requires rospy or ros_bridge extension)
    self._publish_odometry(result)
```

### Trajectory Analysis

Analyze saved trajectories:

```bash
python3 -c "
import numpy as np

# Load trajectory
data = np.loadtxt('logs/vslam_trajectory_20240101_120000.txt')
positions = data[:, 1:4]

# Calculate total distance
distances = np.sqrt(np.sum(np.diff(positions, axis=0)**2, axis=1))
total_distance = np.sum(distances)

print(f'Total distance traveled: {total_distance:.2f} meters')
print(f'Start position: {positions[0]}')
print(f'End position: {positions[-1]}')
"
```

### Integration with Navigation

To use VSLAM odometry for goal-based navigation, modify `scripts/goal_based_control.py`:

```python
# Add VSLAM odometry as additional pose source
from scripts.vslam_control import VSLAMController

class GoalBasedController:
    def __init__(self):
        # ... existing code ...
        self.vslam = VSLAMController()
        self.vslam.initialize()
        self.vslam.ros_bridge.start()
    
    def get_current_pose(self):
        # Fuse wheel odometry with VSLAM
        odom_pose = self.ros_bridge.get_odometry()
        vslam_pose = self.vslam.pycuvslam_bridge.last_pose
        
        # Implement sensor fusion logic
        # ...
```

## References

- [NVIDIA cuVSLAM Documentation](https://docs.nvidia.com/isaac/doc/visual_slam.html)
- [Isaac ROS Visual SLAM](https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_visual_slam)
- [Rerun Documentation](https://www.rerun.io/docs)
- [Camera Calibration Tutorial](http://wiki.ros.org/camera_calibration/Tutorials/MonocularCalibration)

## Support

For issues or questions:
1. Check [Troubleshooting](#troubleshooting) section
2. Review logs in `logs/` directory
3. Verify hardware connections and ROS topics
4. Open an issue in the repository with:
   - Error messages
   - Configuration file
   - System info (JetPack version, hardware)

---

**Last Updated**: 2024
**Tested On**: Jetson Orin Nano with JetPack 5.x/6.x
