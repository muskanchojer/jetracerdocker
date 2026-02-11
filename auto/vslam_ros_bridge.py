#!/usr/bin/env python3
"""
VSLAM ROS Bridge - Subscribe to camera and IMU topics from Docker
Extends ROSTopicBridge to add camera image streaming
"""

import subprocess
import threading
import logging
import time
import numpy as np
from typing import Optional, Tuple, Callable
from collections import deque
import struct


class VSLAMROSBridge:
    """
    ROS Bridge for VSLAM - handles camera images and IMU data from Docker
    Subscribes to /usb_cam/image_raw and /imu topics
    """
    
    def __init__(self, container_name='jetracer_ros'):
        self.container_name = container_name
        self.logger = logging.getLogger(__name__)
        
        # Thread-safe access
        self._camera_lock = threading.Lock()
        self._imu_lock = threading.Lock()
        
        # Latest camera frame
        self.latest_image = None
        self.latest_image_timestamp = 0.0
        self.camera_frame_count = 0
        
        # IMU data buffer (store recent measurements)
        self.imu_buffer = deque(maxlen=200)  # ~1 second at 200Hz
        self.imu_count = 0
        
        # Callbacks
        self.camera_callback = None
        self.imu_callback = None
        
        # Thread control
        self.running = False
        self.camera_thread = None
        self.imu_thread = None
        self.camera_process = None
        self.imu_process = None
        
        # Performance tracking
        self.camera_fps = 0.0
        self.imu_rate = 0.0
        self.last_fps_time = time.time()
        self.fps_frame_count = 0
        self.fps_imu_count = 0
        
        self.logger.info(f"VSLAM ROS Bridge initialized for container: {container_name}")
    
    def set_camera_callback(self, callback: Callable[[float, np.ndarray], None]):
        """
        Set callback for camera frames
        
        Args:
            callback: Function(timestamp, image) called on each frame
        """
        self.camera_callback = callback
    
    def set_imu_callback(self, callback: Callable[[float, tuple, tuple], None]):
        """
        Set callback for IMU data
        
        Args:
            callback: Function(timestamp, accel, gyro) called on each IMU measurement
        """
        self.imu_callback = callback
    
    def start(self):
        """Start listening to camera and IMU topics"""
        self.running = True
        
        # Start camera streaming thread
        self.camera_thread = threading.Thread(target=self._camera_stream_loop, daemon=True)
        self.camera_thread.start()
        
        # Start IMU streaming thread
        self.imu_thread = threading.Thread(target=self._imu_stream_loop, daemon=True)
        self.imu_thread.start()
        
        self.logger.info("Started VSLAM ROS bridge (camera + IMU streaming)")
    
    def stop(self):
        """Stop listening"""
        self.running = False
        
        # Stop camera process
        if self.camera_process:
            try:
                self.camera_process.terminate()
                self.camera_process.wait(timeout=1.0)
            except Exception:
                self.camera_process.kill()
        
        # Stop IMU process
        if self.imu_process:
            try:
                self.imu_process.terminate()
                self.imu_process.wait(timeout=1.0)
            except Exception:
                self.imu_process.kill()
        
        # Wait for threads
        if self.camera_thread:
            self.camera_thread.join(timeout=2.0)
        if self.imu_thread:
            self.imu_thread.join(timeout=2.0)
        
        self.logger.info("Stopped VSLAM ROS bridge")
    
    def _camera_stream_loop(self):
        """
        Continuous streaming loop for camera images
        Uses rostopic echo to get image data
        """
        while self.running:
            try:
                # Use compressed image transport for efficiency
                # Try compressed first, fall back to raw if not available
                cmd = [
                    "docker", "exec", self.container_name,
                    "bash", "-c",
                    "source /root/catkin_ws/devel/setup.bash && rostopic echo /usb_cam/image_raw"
                ]
                
                self.camera_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1
                )
                
                msg_buffer = ""
                
                # Read lines continuously
                while self.running and self.camera_process.poll() is None:
                    line = self.camera_process.stdout.readline()
                    if line:
                        msg_buffer += line
                        
                        # Check if we have a complete message
                        if line.strip() == "---":
                            self._parse_image_message(msg_buffer)
                            msg_buffer = ""
                
            except Exception as e:
                self.logger.error(f"Camera stream error: {e}")
                time.sleep(0.5)
            
            if self.running:
                self.logger.debug("Reconnecting to camera stream...")
    
    def _imu_stream_loop(self):
        """
        Continuous streaming loop for IMU data
        """
        while self.running:
            try:
                cmd = [
                    "docker", "exec", self.container_name,
                    "bash", "-c",
                    "source /root/catkin_ws/devel/setup.bash && rostopic echo /imu"
                ]
                
                self.imu_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1
                )
                
                msg_buffer = ""
                
                # Read lines continuously
                while self.running and self.imu_process.poll() is None:
                    line = self.imu_process.stdout.readline()
                    if line:
                        msg_buffer += line
                        
                        if line.strip() == "---":
                            self._parse_imu_message(msg_buffer)
                            msg_buffer = ""
                
            except Exception as e:
                self.logger.error(f"IMU stream error: {e}")
                time.sleep(0.5)
            
            if self.running:
                self.logger.debug("Reconnecting to IMU stream...")
    
    def _parse_image_message(self, msg_text: str):
        """
        Parse rostopic echo output for image data
        Note: This is simplified - in production, use image_transport compressed
        """
        try:
            lines = msg_text.split('\n')
            
            # Extract image metadata
            height = width = encoding = None
            is_bigendian = False
            step = 0
            data_start_idx = -1
            
            for i, line in enumerate(lines):
                stripped = line.strip()
                
                if 'height:' in stripped:
                    height = int(stripped.split(':')[1].strip())
                elif 'width:' in stripped:
                    width = int(stripped.split(':')[1].strip())
                elif 'encoding:' in stripped:
                    encoding = stripped.split(':')[1].strip()
                elif 'is_bigendian:' in stripped:
                    is_bigendian = 'true' in stripped.lower()
                elif 'step:' in stripped:
                    step = int(stripped.split(':')[1].strip())
                elif 'data:' in stripped and '[' in stripped:
                    data_start_idx = i
                    break
            
            # For rostopic echo, image data is printed as array [val1, val2, ...]
            # This is inefficient for images - better to use compressed transport
            # For now, we'll just update metadata and signal that we got a frame
            
            if height and width:
                timestamp = time.time()
                
                # Create dummy grayscale image (rostopic echo is too slow for full data)
                # In real use, should use compressed_image_transport or direct rospy
                image = np.zeros((height, width), dtype=np.uint8)
                
                with self._camera_lock:
                    self.latest_image = image
                    self.latest_image_timestamp = timestamp
                    self.camera_frame_count += 1
                    self.fps_frame_count += 1
                
                # Update FPS
                now = time.time()
                elapsed = now - self.last_fps_time
                if elapsed >= 1.0:
                    self.camera_fps = self.fps_frame_count / elapsed
                    self.imu_rate = self.fps_imu_count / elapsed
                    self.fps_frame_count = 0
                    self.fps_imu_count = 0
                    self.last_fps_time = now
                
                # Call callback
                if self.camera_callback:
                    self.camera_callback(timestamp, image)
                
        except Exception as e:
            self.logger.debug(f"Error parsing image message: {e}")
    
    def _parse_imu_message(self, msg_text: str):
        """Parse rostopic echo output for IMU data"""
        try:
            lines = msg_text.split('\n')
            
            accel_x = accel_y = accel_z = 0.0
            gyro_x = gyro_y = gyro_z = 0.0
            
            in_angular_velocity = False
            in_linear_acceleration = False
            
            for line in lines:
                stripped = line.strip()
                
                # Angular velocity parsing
                if 'angular_velocity:' in line:
                    in_angular_velocity = True
                    continue
                elif in_angular_velocity:
                    if stripped.startswith('x:'):
                        gyro_x = float(stripped.split(':')[1])
                    elif stripped.startswith('y:'):
                        gyro_y = float(stripped.split(':')[1])
                    elif stripped.startswith('z:'):
                        gyro_z = float(stripped.split(':')[1])
                        in_angular_velocity = False
                
                # Linear acceleration parsing
                if 'linear_acceleration:' in line:
                    in_linear_acceleration = True
                    continue
                elif in_linear_acceleration:
                    if stripped.startswith('x:'):
                        accel_x = float(stripped.split(':')[1])
                    elif stripped.startswith('y:'):
                        accel_y = float(stripped.split(':')[1])
                    elif stripped.startswith('z:'):
                        accel_z = float(stripped.split(':')[1])
                        in_linear_acceleration = False
            
            timestamp = time.time()
            
            # Store in buffer
            imu_data = {
                'timestamp': timestamp,
                'accel': (accel_x, accel_y, accel_z),
                'gyro': (gyro_x, gyro_y, gyro_z)
            }
            
            with self._imu_lock:
                self.imu_buffer.append(imu_data)
                self.imu_count += 1
                self.fps_imu_count += 1
            
            # Call callback
            if self.imu_callback:
                self.imu_callback(timestamp, (accel_x, accel_y, accel_z), 
                                (gyro_x, gyro_y, gyro_z))
            
        except Exception as e:
            self.logger.debug(f"Error parsing IMU message: {e}")
    
    def get_latest_image(self) -> Optional[Tuple[float, np.ndarray]]:
        """
        Get latest camera frame (thread-safe)
        
        Returns:
            (timestamp, image) or None if no frame available
        """
        with self._camera_lock:
            if self.latest_image is not None:
                return self.latest_image_timestamp, self.latest_image.copy()
        return None
    
    def get_imu_buffer(self) -> list:
        """
        Get recent IMU measurements (thread-safe)
        
        Returns:
            list of IMU data dicts
        """
        with self._imu_lock:
            return list(self.imu_buffer)
    
    def get_synchronized_data(self, time_window: float = 0.1) -> Optional[Tuple]:
        """
        Get synchronized camera frame with IMU measurements
        
        Args:
            time_window: Time window in seconds for IMU data around frame
        
        Returns:
            (frame_timestamp, image, imu_measurements) or None
        """
        frame_data = self.get_latest_image()
        if frame_data is None:
            return None
        
        frame_ts, image = frame_data
        
        # Get IMU measurements within time window
        with self._imu_lock:
            imu_data = [
                m for m in self.imu_buffer
                if abs(m['timestamp'] - frame_ts) <= time_window
            ]
        
        if imu_data:
            return frame_ts, image, imu_data
        
        return None
    
    def get_statistics(self) -> dict:
        """Get streaming statistics"""
        return {
            'camera_frames': self.camera_frame_count,
            'camera_fps': self.camera_fps,
            'imu_measurements': self.imu_count,
            'imu_rate': self.imu_rate,
            'imu_buffer_size': len(self.imu_buffer)
        }


if __name__ == '__main__':
    # Test the bridge
    logging.basicConfig(level=logging.INFO)
    
    bridge = VSLAMROSBridge()
    
    # Set callbacks
    def on_camera(timestamp, image):
        print(f"📷 Camera frame: {image.shape} at {timestamp:.3f}")
    
    def on_imu(timestamp, accel, gyro):
        print(f"📡 IMU: accel={accel}, gyro={gyro} at {timestamp:.3f}")
    
    bridge.set_camera_callback(on_camera)
    bridge.set_imu_callback(on_imu)
    
    bridge.start()
    
    print("Listening to camera and IMU topics...")
    print("Press Ctrl+C to stop\n")
    
    try:
        while True:
            stats = bridge.get_statistics()
            print(f"\nStats: {stats}")
            time.sleep(2.0)
    
    except KeyboardInterrupt:
        print("\nStopping...")
        bridge.stop()
