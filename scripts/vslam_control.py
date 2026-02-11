#!/usr/bin/env python3
"""
VSLAM Controller - Main entry point for Visual-Inertial SLAM mode
Integrates pycuvslam with ROS camera and IMU data for real-time localization
"""

import sys
import time
import logging
import signal
import yaml
from pathlib import Path
from datetime import datetime
import numpy as np


class VSLAMController:
    """
    Main controller for VSLAM mode
    Coordinates camera, IMU, and pycuvslam tracker
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize VSLAM controller
        
        Args:
            config_path: Path to vslam_config.yaml
        """
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "vslam_config.yaml"
        
        self.logger.info(f"Loading config from: {config_path}")
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize components
        self.ros_bridge = None
        self.pycuvslam_bridge = None
        self.rerun_recorder = None
        
        # State
        self.running = False
        self.start_time = None
        self.frame_count = 0
        self.imu_count = 0
        
        # Statistics
        self.last_stats_time = time.time()
        self.stats_interval = self.config['vslam']['logging'].get('statistics_interval', 10)
        
        # Trajectory storage
        self.trajectory = []
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("VSLAM Controller initialized")
    
    def _signal_handler(self, sig, frame):
        """Handle shutdown signals"""
        self.logger.info("\n🛑 Shutdown signal received")
        self.running = False
    
    def initialize(self) -> bool:
        """
        Initialize all components
        
        Returns:
            bool: True if successful
        """
        try:
            # Initialize pycuvslam bridge
            self.logger.info("Initializing pycuvslam bridge...")
            from auto.pycuvslam_bridge import PyCuVSLAMBridge
            
            self.pycuvslam_bridge = PyCuVSLAMBridge(self.config)
            if not self.pycuvslam_bridge.initialize_tracker():
                self.logger.error("Failed to initialize pycuvslam tracker")
                return False
            
            # Initialize ROS bridge
            self.logger.info("Initializing ROS bridge...")
            from auto.vslam_ros_bridge import VSLAMROSBridge
            
            self.ros_bridge = VSLAMROSBridge()
            
            # Set callbacks
            self.ros_bridge.set_camera_callback(self._on_camera_frame)
            self.ros_bridge.set_imu_callback(self._on_imu_data)
            
            # Initialize Rerun visualization if enabled
            if self.config['vslam']['visualization'].get('enable_rerun', False):
                self.logger.info("Initializing Rerun visualization...")
                self._initialize_rerun()
            
            self.logger.info("✅ All components initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _initialize_rerun(self):
        """Initialize Rerun for visualization"""
        try:
            import rerun as rr
            
            app_id = self.config['vslam']['visualization']['rerun_app_id']
            rr.init(app_id, spawn=True)
            
            # Log configuration
            rr.log("config/camera", rr.TextLog(str(self.config['vslam']['camera'])))
            rr.log("config/imu", rr.TextLog(str(self.config['vslam']['imu'])))
            
            self.rerun_recorder = rr
            self.logger.info("✅ Rerun visualization initialized")
            
        except ImportError:
            self.logger.warning("⚠️  Rerun not available, visualization disabled")
            self.rerun_recorder = None
        except Exception as e:
            self.logger.warning(f"⚠️  Failed to initialize Rerun: {e}")
            self.rerun_recorder = None
    
    def _on_imu_data(self, timestamp: float, accel: tuple, gyro: tuple):
        """
        Callback for IMU data
        
        Args:
            timestamp: IMU timestamp
            accel: (ax, ay, az) acceleration in m/s²
            gyro: (gx, gy, gz) angular velocity in rad/s
        """
        self.imu_count += 1
        
        # Register with pycuvslam
        if self.pycuvslam_bridge:
            self.pycuvslam_bridge.register_imu_measurement(timestamp, accel, gyro)
        
        # Log to Rerun occasionally
        if self.rerun_recorder and self.imu_count % 20 == 0:
            try:
                self.rerun_recorder.log("imu/accel", self.rerun_recorder.TimeSeriesScalar(accel[0]))
                self.rerun_recorder.log("imu/gyro", self.rerun_recorder.TimeSeriesScalar(gyro[2]))
            except:
                pass
    
    def _on_camera_frame(self, timestamp: float, image: np.ndarray):
        """
        Callback for camera frames
        
        Args:
            timestamp: Frame timestamp
            image: Camera image
        """
        self.frame_count += 1
        
        # Apply frame skip if configured
        skip_frames = self.config['vslam']['performance'].get('skip_frames', 1)
        if self.frame_count % skip_frames != 0:
            return
        
        # Track frame with pycuvslam
        if self.pycuvslam_bridge:
            result = self.pycuvslam_bridge.track_frame(timestamp, image)
            
            if result and result.get('success'):
                # Store pose in trajectory
                pose_data = {
                    'timestamp': timestamp,
                    'position': result['position'],
                    'orientation': result['orientation']
                }
                self.trajectory.append(pose_data)
                
                # Visualize in Rerun
                if self.rerun_recorder:
                    self._visualize_pose(result)
                
                # Log occasionally
                if self.frame_count % 30 == 0:
                    pos = result['position']
                    self.logger.info(f"📍 Position: x={pos[0]:.3f}, y={pos[1]:.3f}, z={pos[2]:.3f}")
    
    def _visualize_pose(self, result: dict):
        """Visualize pose in Rerun"""
        if not self.rerun_recorder:
            return
        
        try:
            pos = result['position']
            quat = result['orientation']
            
            # Log camera pose
            self.rerun_recorder.log(
                "world/camera",
                self.rerun_recorder.Transform3D(
                    translation=pos,
                    rotation=self.rerun_recorder.Quaternion(xyzw=quat)
                )
            )
            
            # Log trajectory point
            self.rerun_recorder.log(
                "world/trajectory",
                self.rerun_recorder.Points3D([pos], colors=[0, 255, 0])
            )
            
        except Exception as e:
            self.logger.debug(f"Rerun visualization error: {e}")
    
    def run(self) -> bool:
        """
        Main run loop
        
        Returns:
            bool: True if successful
        """
        # Initialize
        if not self.initialize():
            return False
        
        # Start ROS bridge
        self.logger.info("Starting ROS bridge...")
        self.ros_bridge.start()
        
        # Wait for data
        self.logger.info("Waiting for camera and IMU data...")
        time.sleep(2.0)
        
        # Main loop
        self.running = True
        self.start_time = time.time()
        
        self.logger.info("\n" + "="*60)
        self.logger.info("🚀 VSLAM Mode Running")
        self.logger.info("="*60)
        self.logger.info("  Press Ctrl+C to stop and save trajectory")
        self.logger.info("="*60 + "\n")
        
        try:
            while self.running:
                # Print statistics periodically
                now = time.time()
                if now - self.last_stats_time >= self.stats_interval:
                    self._print_statistics()
                    self.last_stats_time = now
                
                # Sleep to avoid busy loop
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            self.logger.info("\n🛑 Interrupted by user")
        
        finally:
            self.shutdown()
        
        return True
    
    def _print_statistics(self):
        """Print current statistics"""
        if not self.start_time:
            return
        
        runtime = time.time() - self.start_time
        
        # Get tracking stats
        if self.pycuvslam_bridge:
            stats = self.pycuvslam_bridge.get_statistics()
            success_rate = stats['success_rate']
            total_frames = stats['total_frames']
        else:
            success_rate = 0.0
            total_frames = 0
        
        # Get streaming stats
        if self.ros_bridge:
            stream_stats = self.ros_bridge.get_statistics()
            camera_fps = stream_stats['camera_fps']
            imu_rate = stream_stats['imu_rate']
        else:
            camera_fps = 0.0
            imu_rate = 0.0
        
        self.logger.info("\n" + "="*60)
        self.logger.info(f"📊 Statistics (runtime: {runtime:.1f}s)")
        self.logger.info("="*60)
        self.logger.info(f"  Camera: {camera_fps:.1f} fps | IMU: {imu_rate:.1f} Hz")
        self.logger.info(f"  Tracked frames: {total_frames} | Success rate: {success_rate:.1f}%")
        self.logger.info(f"  Trajectory points: {len(self.trajectory)}")
        self.logger.info("="*60 + "\n")
    
    def save_trajectory(self):
        """Save trajectory to file"""
        if not self.trajectory:
            self.logger.info("No trajectory to save")
            return
        
        try:
            # Create logs directory if needed
            log_dir = Path(__file__).parent.parent / "logs"
            log_dir.mkdir(exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = log_dir / f"vslam_trajectory_{timestamp}.txt"
            
            # Write trajectory
            with open(filename, 'w') as f:
                f.write("# VSLAM Trajectory\n")
                f.write("# timestamp x y z qx qy qz qw\n")
                
                for pose in self.trajectory:
                    ts = pose['timestamp']
                    pos = pose['position']
                    quat = pose['orientation']
                    
                    f.write(f"{ts:.6f} {pos[0]:.6f} {pos[1]:.6f} {pos[2]:.6f} ")
                    f.write(f"{quat[0]:.6f} {quat[1]:.6f} {quat[2]:.6f} {quat[3]:.6f}\n")
            
            self.logger.info(f"✅ Trajectory saved: {filename}")
            self.logger.info(f"   {len(self.trajectory)} poses written")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to save trajectory: {e}")
    
    def shutdown(self):
        """Shutdown all components"""
        self.logger.info("\n🛑 Shutting down VSLAM controller...")
        
        # Stop ROS bridge
        if self.ros_bridge:
            self.ros_bridge.stop()
        
        # Save trajectory
        if self.config['vslam']['logging'].get('save_trajectory', True):
            self.save_trajectory()
        
        # Shutdown pycuvslam
        if self.pycuvslam_bridge:
            self.pycuvslam_bridge.shutdown()
        
        # Final statistics
        self._print_statistics()
        
        self.logger.info("✅ Shutdown complete")


def main():
    """Main entry point for standalone execution"""
    print("\n" + "="*60)
    print("🗺️  VSLAM Mode - Visual-Inertial SLAM")
    print("="*60 + "\n")
    
    controller = VSLAMController()
    success = controller.run()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
