#!/usr/bin/env python3
"""
PyCuVSLAM Bridge - Python wrapper for pycuvslam library
Provides easy interface for Visual-Inertial SLAM with mono camera + IMU
"""

import numpy as np
import logging
from typing import Optional, Tuple, Dict
import time


class PyCuVSLAMBridge:
    """
    Bridge to pycuvslam library for Visual-Inertial Odometry (VIO)
    Handles camera configuration, IMU calibration, and pose tracking
    """
    
    def __init__(self, config: dict):
        """
        Initialize pycuvslam tracker
        
        Args:
            config: Configuration dictionary from vslam_config.yaml
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.tracker = None
        self.initialized = False
        
        # Statistics
        self.frame_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.last_pose = None
        self.last_timestamp = None
        
        try:
            import pycuvslam
            self.pycuvslam = pycuvslam
            self.logger.info("✅ pycuvslam module imported successfully")
        except ImportError as e:
            self.logger.error(f"❌ Failed to import pycuvslam: {e}")
            self.logger.error("Install pycuvslam following docs/VSLAM_SETUP.md")
            raise
    
    def initialize_tracker(self) -> bool:
        """
        Initialize pycuvslam tracker with camera and IMU configuration
        
        Returns:
            bool: True if successful
        """
        try:
            camera_config = self.config['vslam']['camera']
            imu_config = self.config['vslam']['imu']
            t_cam_imu_config = self.config['vslam']['T_cam_imu']
            tracker_config = self.config['vslam']['tracker']
            
            # Create camera intrinsics
            intrinsics = self.pycuvslam.CameraIntrinsics()
            intrinsics.image_width = camera_config['width']
            intrinsics.image_height = camera_config['height']
            intrinsics.fx = camera_config['fx']
            intrinsics.fy = camera_config['fy']
            intrinsics.cx = camera_config['cx']
            intrinsics.cy = camera_config['cy']
            
            # Set distortion coefficients (Brown model: k1, k2, p1, p2, k3)
            intrinsics.distortion_coefficients = [
                camera_config['k1'],
                camera_config['k2'],
                camera_config['p1'],
                camera_config['p2'],
                camera_config['k3']
            ]
            
            self.logger.info(f"Camera: {camera_config['width']}x{camera_config['height']}")
            self.logger.info(f"fx={intrinsics.fx:.2f}, fy={intrinsics.fy:.2f}")
            self.logger.info(f"cx={intrinsics.cx:.2f}, cy={intrinsics.cy:.2f}")
            
            # Create IMU calibration
            imu_calib = self.pycuvslam.ImuCalibration()
            imu_calib.gyroscope_noise_density = imu_config['gyroscope_noise_density']
            imu_calib.gyroscope_random_walk = imu_config['gyroscope_random_walk']
            imu_calib.accelerometer_noise_density = imu_config['accelerometer_noise_density']
            imu_calib.accelerometer_random_walk = imu_config['accelerometer_random_walk']
            
            self.logger.info(f"IMU calibration configured:")
            self.logger.info(f"  Gyro noise: {imu_calib.gyroscope_noise_density:.2e} rad/s/√Hz")
            self.logger.info(f"  Accel noise: {imu_calib.accelerometer_noise_density:.2e} m/s²/√Hz")
            
            # Create T_cam_imu transformation
            rotation = np.array(t_cam_imu_config['rotation']).reshape(3, 3)
            translation = np.array(t_cam_imu_config['translation'])
            
            # Create 4x4 transformation matrix
            T_cam_imu = np.eye(4)
            T_cam_imu[:3, :3] = rotation
            T_cam_imu[:3, 3] = translation
            
            self.logger.info(f"T_cam_imu transformation:")
            self.logger.info(f"  Translation: {translation}")
            
            # Create tracker configuration
            tracker_config_obj = self.pycuvslam.Configuration()
            tracker_config_obj.enable_observations_export = tracker_config.get('enable_observations_export', True)
            tracker_config_obj.enable_landmarks_export = tracker_config.get('enable_final_landmarks_export', True)
            
            # Initialize tracker
            self.tracker = self.pycuvslam.Tracker(
                camera_intrinsics=intrinsics,
                imu_calibration=imu_calib,
                T_camera_imu=T_cam_imu,
                configuration=tracker_config_obj
            )
            
            self.logger.info("✅ pycuvslam tracker initialized successfully")
            self.initialized = True
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize tracker: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def register_imu_measurement(self, timestamp: float, 
                                 accel: Tuple[float, float, float],
                                 gyro: Tuple[float, float, float]) -> bool:
        """
        Register an IMU measurement
        
        Args:
            timestamp: Timestamp in seconds
            accel: (ax, ay, az) linear acceleration in m/s²
            gyro: (gx, gy, gz) angular velocity in rad/s
        
        Returns:
            bool: True if successful
        """
        if not self.initialized or self.tracker is None:
            self.logger.warning("Tracker not initialized")
            return False
        
        try:
            self.tracker.register_imu_measurement(
                timestamp_s=timestamp,
                linear_acceleration=list(accel),
                angular_velocity=list(gyro)
            )
            return True
        except Exception as e:
            self.logger.debug(f"Error registering IMU measurement: {e}")
            return False
    
    def track_frame(self, timestamp: float, image: np.ndarray) -> Optional[Dict]:
        """
        Track a camera frame and get pose estimate
        
        Args:
            timestamp: Frame timestamp in seconds
            image: Grayscale image (H, W) or RGB image (H, W, 3)
        
        Returns:
            dict with pose info, or None if tracking failed
            {
                'success': bool,
                'timestamp': float,
                'position': (x, y, z),
                'orientation': (qx, qy, qz, qw),
                'tracking_status': str
            }
        """
        if not self.initialized or self.tracker is None:
            self.logger.warning("Tracker not initialized")
            return None
        
        try:
            # Convert to grayscale if needed
            if len(image.shape) == 3:
                import cv2
                image_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                image_gray = image
            
            # Ensure uint8
            if image_gray.dtype != np.uint8:
                image_gray = (image_gray * 255).astype(np.uint8)
            
            # Track frame
            result = self.tracker.track(
                timestamp_s=timestamp,
                image=image_gray
            )
            
            self.frame_count += 1
            
            if result and result.tracking_status == self.pycuvslam.TrackingStatus.OK:
                self.success_count += 1
                
                # Extract pose
                pose = result.pose
                position = (pose.position.x, pose.position.y, pose.position.z)
                orientation = (pose.orientation.x, pose.orientation.y, 
                             pose.orientation.z, pose.orientation.w)
                
                self.last_pose = {
                    'success': True,
                    'timestamp': timestamp,
                    'position': position,
                    'orientation': orientation,
                    'tracking_status': 'OK',
                    'num_features': getattr(result, 'num_features', 0)
                }
                self.last_timestamp = timestamp
                
                return self.last_pose
            else:
                self.failure_count += 1
                status = result.tracking_status if result else "UNKNOWN"
                self.logger.debug(f"Tracking failed: {status}")
                
                return {
                    'success': False,
                    'timestamp': timestamp,
                    'tracking_status': str(status)
                }
        
        except Exception as e:
            self.logger.error(f"Error tracking frame: {e}")
            self.failure_count += 1
            return None
    
    def get_statistics(self) -> Dict:
        """
        Get tracking statistics
        
        Returns:
            dict: Statistics including success rate, frame count, etc.
        """
        success_rate = (self.success_count / self.frame_count * 100) if self.frame_count > 0 else 0.0
        
        return {
            'total_frames': self.frame_count,
            'successful_tracks': self.success_count,
            'failed_tracks': self.failure_count,
            'success_rate': success_rate,
            'last_pose': self.last_pose,
            'last_timestamp': self.last_timestamp
        }
    
    def reset(self):
        """Reset tracker and statistics"""
        self.frame_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.last_pose = None
        self.last_timestamp = None
        
        if self.tracker:
            try:
                # Reset tracker if method exists
                if hasattr(self.tracker, 'reset'):
                    self.tracker.reset()
                self.logger.info("Tracker reset")
            except Exception as e:
                self.logger.warning(f"Failed to reset tracker: {e}")
    
    def shutdown(self):
        """Shutdown tracker and cleanup"""
        if self.tracker:
            try:
                # Export trajectory if possible
                if hasattr(self.tracker, 'export_trajectory'):
                    trajectory = self.tracker.export_trajectory()
                    self.logger.info(f"Exported {len(trajectory)} poses")
                
                # Cleanup
                self.tracker = None
                self.initialized = False
                self.logger.info("Tracker shutdown complete")
            except Exception as e:
                self.logger.warning(f"Error during shutdown: {e}")


if __name__ == '__main__':
    # Test the bridge
    import yaml
    from pathlib import Path
    
    logging.basicConfig(level=logging.INFO)
    
    # Load config
    config_path = Path(__file__).parent.parent / "config" / "vslam_config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize bridge
    try:
        bridge = PyCuVSLAMBridge(config)
        success = bridge.initialize_tracker()
        
        if success:
            print("✅ Bridge initialized successfully")
            print(f"Statistics: {bridge.get_statistics()}")
        else:
            print("❌ Bridge initialization failed")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
