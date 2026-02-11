#!/usr/bin/env python3
"""
Camera-IMU Transform Measurement
Interactive script to help measure and configure the camera-IMU transformation
"""

import sys
import yaml
import numpy as np
from pathlib import Path


def quaternion_from_euler(roll, pitch, yaw):
    """
    Convert Euler angles to quaternion
    
    Args:
        roll, pitch, yaw: Angles in radians
    
    Returns:
        [qx, qy, qz, qw]
    """
    cy = np.cos(yaw * 0.5)
    sy = np.sin(yaw * 0.5)
    cp = np.cos(pitch * 0.5)
    sp = np.sin(pitch * 0.5)
    cr = np.cos(roll * 0.5)
    sr = np.sin(roll * 0.5)
    
    qw = cr * cp * cy + sr * sp * sy
    qx = sr * cp * cy - cr * sp * sy
    qy = cr * sp * cy + sr * cp * sy
    qz = cr * cp * sy - sr * sp * cy
    
    return [qx, qy, qz, qw]


def rotation_matrix_from_euler(roll, pitch, yaw):
    """
    Create rotation matrix from Euler angles (ZYX convention)
    
    Args:
        roll, pitch, yaw: Angles in radians
    
    Returns:
        3x3 rotation matrix
    """
    # Rotation around X (roll)
    Rx = np.array([
        [1, 0, 0],
        [0, np.cos(roll), -np.sin(roll)],
        [0, np.sin(roll), np.cos(roll)]
    ])
    
    # Rotation around Y (pitch)
    Ry = np.array([
        [np.cos(pitch), 0, np.sin(pitch)],
        [0, 1, 0],
        [-np.sin(pitch), 0, np.cos(pitch)]
    ])
    
    # Rotation around Z (yaw)
    Rz = np.array([
        [np.cos(yaw), -np.sin(yaw), 0],
        [np.sin(yaw), np.cos(yaw), 0],
        [0, 0, 1]
    ])
    
    # Combined rotation: R = Rz * Ry * Rx
    R = Rz @ Ry @ Rx
    return R


def measure_transform():
    """
    Interactive measurement of camera-IMU transformation
    """
    print("\n" + "="*70)
    print("📐 Camera-IMU Transformation Measurement")
    print("="*70)
    print("\nThis script helps you configure the transformation from IMU to camera frame.")
    print("\nCoordinate Frame Conventions:")
    print("  - Camera frame: X=right, Y=down, Z=forward")
    print("  - IMU/Body frame: X=forward, Y=left, Z=up")
    print("  - ROS REP-103: X=forward, Y=left, Z=up")
    print("\n" + "="*70 + "\n")
    
    # Ask about sensor mounting
    print("Step 1: Relative Position")
    print("-" * 70)
    print("\nMeasure the distance from IMU to camera center.")
    print("Use a ruler to measure the physical offset.\n")
    
    print("Enter translation (in meters) from IMU to camera:")
    print("  Example: If camera is 5cm forward, 2cm right, 1cm up from IMU")
    print("           Enter: 0.05, 0.02, 0.01\n")
    
    tx, ty, tz = 0.0, 0.0, 0.0
    try:
        tx = float(input("  X offset (forward, in meters): ").strip() or "0.0")
        ty = float(input("  Y offset (left, in meters): ").strip() or "0.0")
        tz = float(input("  Z offset (up, in meters): ").strip() or "0.0")
    except ValueError as e:
        print(f"\n⚠️  Invalid input: {e}, using default: [0, 0, 0]")
        tx, ty, tz = 0.0, 0.0, 0.0
    
    translation = [tx, ty, tz]
    
    print(f"\n✅ Translation: X={tx:.3f}, Y={ty:.3f}, Z={tz:.3f} meters")
    
    # Ask about orientation
    print("\n" + "="*70)
    print("Step 2: Relative Orientation")
    print("-" * 70)
    print("\nDescribe how the camera is rotated relative to the IMU.")
    print("Common cases:")
    print("  1. Camera and IMU aligned (same orientation) - Use [0, 0, 0]")
    print("  2. Camera rotated 90° left - Use [0, 0, 90]")
    print("  3. Camera rotated 180° (facing backward) - Use [0, 0, 180]")
    print("  4. Camera tilted down 30° - Use [30, 0, 0]")
    print("\nEnter Euler angles (in degrees):\n")
    
    roll, pitch, yaw = 0.0, 0.0, 0.0
    try:
        roll = float(input("  Roll (rotation around forward axis, degrees): ").strip() or "0.0")
        pitch = float(input("  Pitch (rotation around left axis, degrees): ").strip() or "0.0")
        yaw = float(input("  Yaw (rotation around up axis, degrees): ").strip() or "0.0")
    except ValueError as e:
        print(f"\n⚠️  Invalid input: {e}, using default: [0, 0, 0]")
        roll, pitch, yaw = 0.0, 0.0, 0.0
    
    # Convert to radians
    roll_rad = np.radians(roll)
    pitch_rad = np.radians(pitch)
    yaw_rad = np.radians(yaw)
    
    print(f"\n✅ Orientation: Roll={roll:.1f}°, Pitch={pitch:.1f}°, Yaw={yaw:.1f}°")
    
    # Calculate rotation matrix
    rotation_matrix = rotation_matrix_from_euler(roll_rad, pitch_rad, yaw_rad)
    
    # Flatten to row-major format for config
    rotation_flat = rotation_matrix.flatten().tolist()
    
    # Create transformation dict
    transform = {
        'rotation': rotation_flat,  # 3x3 matrix as 9-element list
        'translation': translation
    }
    
    # Display results
    print("\n" + "="*70)
    print("📋 Transformation Matrix (Camera from IMU)")
    print("="*70)
    print("\nRotation Matrix:")
    print(rotation_matrix)
    print(f"\nTranslation: {translation}")
    
    print("\n" + "="*70)
    print("📋 Copy these values to config/vslam_config.yaml:")
    print("="*70)
    print("""
  T_cam_imu:
    # Transformation from IMU frame to camera frame
    rotation: [""" + ", ".join([f"{x:.6f}" for x in rotation_flat]) + """]
    translation: [""" + ", ".join([f"{x:.6f}" for x in translation]) + """]
""")
    
    # Ask if user wants to update config
    print("\n" + "="*70)
    update = input("\nUpdate config/vslam_config.yaml automatically? [y/N]: ").strip().lower()
    
    if update == 'y':
        try:
            config_path = Path(__file__).parent.parent / "config" / "vslam_config.yaml"
            
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            config['vslam']['T_cam_imu'] = transform
            
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            print(f"\n✅ Configuration updated: {config_path}")
        
        except Exception as e:
            print(f"\n❌ Failed to update config: {e}")
            return False
    else:
        print("\n💡 Manual update required - copy the values above to your config file")
    
    return True


def main():
    try:
        success = measure_transform()
        return 0 if success else 1
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 1
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
