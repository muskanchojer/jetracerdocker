## My notes
run main.py for normal keyboard control only. My first basic working code.
run main3.py for camera, imu and keyboard control all working together simultaneously.
run main2.py for camera, imu and keyboard control all working one-by-one at diff times.

# JetRacer Control System
Basic control system for Waveshare JetRacer on NVIDIA Jetson Orin Nano. 

## Features

- ✅ **Keyboard Control** - WASD control with persistent steering
- 🔄 **Modular Design** - Easy to add LIDAR, camera, autonomous features
- 🐳 **Docker Integration** - Runs ROS 1 Noetic in containerized environment
- 📝 **Logging** - All components log to `logs/` directory
- ⚙️ **Configuration** - Centralized config in `config/robot_config.yaml`

## Quick Start

### Start Docker Container

```bash
~/start_jetracer_docker.sh
```

### Run main file

```bash
python main.py      #or main2.py or main3.py
```

## Configuration

Configuration is stored in `config/robot_config.yaml`. 

## Logging

All components log to `logs/` directory. 

## Challenges
1. The camera doesnt run in the docker container. It runs fine in the host machine. There is a "libbiff.so.1: cannot open shared object file: No such file or directory" error which creates this problem. 
2. IMU logging leaks in the terminal too even though the fix for that is in place. Will try fixing it in the next version.
3. Ros-noetic does not work with jetson's ubuntu 22.04 which is why docker is used to be able to extract data from the waveshare robot hardware itself.
