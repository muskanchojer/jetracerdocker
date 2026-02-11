#!/usr/bin/env python3
"""
IMU Noise Calibration Script
Records static IMU data and calculates noise parameters for VSLAM
"""

import sys
import time
import argparse
import numpy as np
import yaml
from pathlib import Path
import logging


def calibrate_imu_noise(duration=60, output_file=None):
    """
    Calibrate IMU noise parameters
    
    Args:
        duration: Recording duration in seconds
        output_file: Output YAML file path
    
    Returns:
        dict: Calibration parameters
    """
    print("\n" + "="*60)
    print("📡 IMU Noise Calibration")
    print("="*60)
    print("\n⚠️  IMPORTANT: Keep the robot completely stationary!")
    print("   Place it on a stable surface with no vibrations")
    print(f"   Recording for {duration} seconds...\n")
    
    # Import ROS bridge
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from auto.ros_bridge import ROSTopicBridge
    
    # Start collecting IMU data
    bridge = ROSTopicBridge()
    bridge.start()
    
    print("Waiting for IMU data...")
    time.sleep(2.0)
    
    # Collect data
    accel_data = []
    gyro_data = []
    
    start_time = time.time()
    last_print_time = start_time
    
    print("\n🔴 Recording started... Keep robot stationary!")
    print(f"Duration: {duration}s\n")
    
    while time.time() - start_time < duration:
        imu_data = bridge.get_imu_data()
        
        if imu_data['timestamp'] > 0:
            accel = imu_data['accel']
            gyro = imu_data['gyro']
            
            accel_data.append(accel)
            gyro_data.append(gyro)
        
        # Progress update
        elapsed = time.time() - start_time
        if time.time() - last_print_time >= 5.0:
            remaining = duration - elapsed
            samples = len(accel_data)
            rate = samples / elapsed if elapsed > 0 else 0
            print(f"⏱️  {elapsed:.1f}s / {duration}s | Samples: {samples} | Rate: {rate:.1f} Hz | Remaining: {remaining:.1f}s")
            last_print_time = time.time()
        
        time.sleep(0.005)  # 200Hz max
    
    bridge.stop()
    
    print(f"\n✅ Recording complete! Collected {len(accel_data)} samples")
    
    # Convert to numpy arrays
    accel_data = np.array(accel_data)
    gyro_data = np.array(gyro_data)
    
    # Calculate statistics
    print("\n" + "="*60)
    print("📊 Analyzing data...")
    print("="*60 + "\n")
    
    # Accelerometer statistics
    accel_mean = np.mean(accel_data, axis=0)
    accel_std = np.std(accel_data, axis=0)
    
    print("Accelerometer:")
    print(f"  Mean:   X={accel_mean[0]:8.4f}, Y={accel_mean[1]:8.4f}, Z={accel_mean[2]:8.4f} m/s²")
    print(f"  StdDev: X={accel_std[0]:8.4f}, Y={accel_std[1]:8.4f}, Z={accel_std[2]:8.4f} m/s²")
    
    # Gyroscope statistics
    gyro_mean = np.mean(gyro_data, axis=0)
    gyro_std = np.std(gyro_data, axis=0)
    
    print("\nGyroscope:")
    print(f"  Mean:   X={gyro_mean[0]:8.4f}, Y={gyro_mean[1]:8.4f}, Z={gyro_mean[2]:8.4f} rad/s")
    print(f"  StdDev: X={gyro_std[0]:8.4f}, Y={gyro_std[1]:8.4f}, Z={gyro_std[2]:8.4f} rad/s")
    
    # Calculate noise parameters
    # Noise density = std_dev / sqrt(sampling_rate)
    sampling_rate = len(accel_data) / duration
    sqrt_rate = np.sqrt(sampling_rate)
    
    accel_noise_density = np.mean(accel_std) / sqrt_rate
    gyro_noise_density = np.mean(gyro_std) / sqrt_rate
    
    # Random walk is approximated from Allan variance
    # For quick calibration, use std_dev * sqrt(sampling_rate)
    accel_random_walk = np.mean(accel_std) * np.sqrt(sampling_rate) / 100.0  # Approximation
    gyro_random_walk = np.mean(gyro_std) * np.sqrt(sampling_rate) / 100.0    # Approximation
    
    print("\n" + "="*60)
    print("📝 Calibration Results")
    print("="*60)
    print(f"\nSampling rate: {sampling_rate:.1f} Hz")
    print(f"\nAccelerometer:")
    print(f"  noise_density:  {accel_noise_density:.4e} m/s²/√Hz")
    print(f"  random_walk:    {accel_random_walk:.4e} m/s³/√Hz")
    print(f"\nGyroscope:")
    print(f"  noise_density:  {gyro_noise_density:.4e} rad/s/√Hz")
    print(f"  random_walk:    {gyro_random_walk:.4e} rad/s²/√Hz")
    
    # Create calibration dict
    calibration = {
        'imu_calibration': {
            'sampling_rate_hz': float(sampling_rate),
            'samples_collected': len(accel_data),
            'duration_seconds': duration,
            'accelerometer': {
                'noise_density': float(accel_noise_density),
                'random_walk': float(accel_random_walk),
                'mean': [float(x) for x in accel_mean],
                'std': [float(x) for x in accel_std]
            },
            'gyroscope': {
                'noise_density': float(gyro_noise_density),
                'random_walk': float(gyro_random_walk),
                'mean': [float(x) for x in gyro_mean],
                'std': [float(x) for x in gyro_std]
            }
        }
    }
    
    # Save to file
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            yaml.dump(calibration, f, default_flow_style=False, sort_keys=False)
        
        print(f"\n✅ Calibration saved to: {output_path}")
    
    print("\n" + "="*60)
    print("📋 Copy these values to config/vslam_config.yaml:")
    print("="*60)
    print(f"""
  imu:
    frequency: {int(sampling_rate)}
    topic: "/imu"
    
    # Calibrated noise parameters
    gyroscope_noise_density: {gyro_noise_density:.4e}
    gyroscope_random_walk: {gyro_random_walk:.4e}
    accelerometer_noise_density: {accel_noise_density:.4e}
    accelerometer_random_walk: {accel_random_walk:.4e}
""")
    
    return calibration


def main():
    parser = argparse.ArgumentParser(
        description='Calibrate IMU noise parameters for VSLAM'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=60,
        help='Recording duration in seconds (default: 60)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='config/imu_calibration.yaml',
        help='Output file path (default: config/imu_calibration.yaml)'
    )
    
    args = parser.parse_args()
    
    try:
        calibration = calibrate_imu_noise(
            duration=args.duration,
            output_file=args.output
        )
        return 0
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Calibration interrupted by user")
        return 1
    
    except Exception as e:
        print(f"\n❌ Calibration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
