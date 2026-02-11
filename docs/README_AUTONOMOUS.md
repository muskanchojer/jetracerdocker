# JetRacer Autonomous Control System

A hybrid control system for the Waveshare JetRacer combining manual keyboard control with AI-powered autonomous navigation using YOLOv8 and a learned policy network.

## My notes
use pip install -e ./tinygrad command to install tinygrad
copy .safetensors file from laptop project
only sends straight command when tinygradinference tag is false in config file.

## 🌟 Features

- **Dual Control Modes:**
  - 🎮 **Manual Mode** - Direct keyboard control (WASD)
  - 🤖 **Autonomous Mode** - AI-powered navigation using vision and learned policy

- **Vision Processing:**
  - YOLOv8 foundation model for visual feature extraction
  - Supports both PyTorch (ultralytics) and tinygrad backends
  - Real-time camera processing at configurable FPS

- **Policy Network:**
  - TinyNet neural network for action prediction
  - Outputs: left, straight, right, reverse
  - Confidence-based action filtering
  - Prediction smoothing for stable control

- **Safety Features:**
  - Configurable confidence thresholds
  - Maximum execution time limits
  - Emergency stop capability
  - Comprehensive logging

- **Docker Integration:**
  - ROS Noetic in containerized environment
  - Hardware access via device passthrough
  - Isolated and reproducible environment

## 📁 Project Structure

```
jetracer_controlv1.1/
├── main.py                       # Unified entry point (NEW!)
├── main_old.py                   # Original keyboard control
├── config/
│   ├── robot_config.yaml         # Robot hardware configuration
│   └── autonomous_config.yaml    # AI/autonomous settings (NEW!)
├── scripts/
│   ├── keyboard_control.py       # Keyboard control module
│   ├── camera.py                 # Camera utilities
│   ├── imu_monitor.py            # IMU sensor monitoring
│   └── autonomous_control.py     # Autonomous control script (NEW!)
├── auto/                          # Autonomous driving modules (NEW!)
│   ├── vision.py                 # YOLOv8 vision processing
│   ├── policy.py                 # TinyNet policy network
│   └── control_adapter.py        # Maps AI -> robot commands
├── models/                        # AI model weights (NEW!)
│   ├── yolov8n.pt                # YOLOv8 PyTorch weights
│   └── yolov8n.safetensors       # YOLOv8 tinygrad weights (optional)
├── commabot/dollop-main/         # Original dollop code
│   └── tinynet.safetensors       # Trained policy weights
├── data/trajectories/            # Training data (NEW!)
├── logs/                         # System logs
├── requirements.txt              # Python dependencies (NEW!)
└── setup.sh                      # Setup script (NEW!)
```

## 🚀 Quick Start

### 1. Setup

Run the setup script to install dependencies and configure the system:

```bash
cd /home/msil/Desktop/muskan/jetracer_controlv1.1
chmod +x setup.sh
./setup.sh
```

This will:
- Install system dependencies (OpenCV, FFmpeg, etc.)
- Install Python packages (ultralytics, PyTorch, etc.)
- Download YOLOv8 model weights
- Optionally install tinygrad for lightweight inference
- Create necessary directories

### 2. Start Docker Container

```bash
~/start_jetracer_docker.sh
```

### 3. Run the System

**Interactive mode selection:**
```bash
python3 main.py
```

**Direct mode selection:**
```bash
# Manual keyboard control
python3 main.py --mode manual

# Autonomous AI navigation
python3 main.py --mode autonomous
```

## 🎮 Manual Mode (Keyboard Control)

Controls:
- `W` - Move forward
- `A` - Turn left
- `S` - Move backward
- `D` - Turn right
- `Space` - Stop
- `Q` - Quit

Features:
- Direct motor control via ROS topics
- Real-time command execution
- Persistent steering while turning

## 🤖 Autonomous Mode (AI Navigation)

The autonomous mode uses:
1. **YOLOv8** for visual feature extraction
2. **TinyNet policy** for action prediction
3. **Control adapter** to execute commands on the robot

### Configuration

Edit `config/autonomous_config.yaml` to customize:

```yaml
# Control speed and turning rates
control_mapping:
  left:
    linear: 0.25
    angular: 0.6
  straight:
    linear: 0.35
    angular: 0.0
  # ... etc

# Safety settings
safety:
  confidence_threshold: 0.3  # Minimum confidence to act
  max_execution_time: 300    # Auto-stop after 5 minutes
```

### Backend Options

**Option 1: PyTorch (Default, Recommended)**
- Easier to use, better compatibility
- Uses ultralytics YOLOv8
- Set `use_tinygrad: false` in config

**Option 2: Tinygrad (Lightweight)**
- Smaller memory footprint
- Better for embedded systems
- Requires manual installation
- Set `use_tinygrad: true` in config

### Training Your Own Policy

To train a custom policy for your environment:

```bash
cd commabot/dollop-main

# 1. Collect training data (drive manually and record)
# 2. Label the data (left, straight, right, reverse)
# 3. Preprocess the data
./preprocess.py

# 4. Train the policy
./train.py

# Model saved as tinynet.safetensors
```

## 📝 Configuration Files

### `robot_config.yaml`
Hardware and robot parameters:
- Serial ports and camera devices
- Motor speed limits
- PID control parameters
- Feature flags

### `autonomous_config.yaml` (NEW)
AI and autonomous settings:
- Model paths
- Vision processing settings
- Control velocity mappings
- Safety parameters
- Inference configuration

## 🔧 Dependencies

### System Packages (Ubuntu 22.04)
```bash
sudo apt-get install -y \
    python3-pip \
    python3-opencv \
    libopencv-dev \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    v4l-utils
```

### Python Packages
```bash
pip install -r requirements.txt
```

Main packages:
- `ultralytics` - YOLOv8 implementation
- `torch` / `torchvision` - PyTorch backend
- `opencv-python` - Computer vision
- `numpy` - Numerical computing
- `pyyaml` - Configuration files
- `av` - Video processing

Optional:
- `tinygrad` - Lightweight ML framework (install from source)

## 🐳 Docker Setup

The system uses a Docker container running ROS Noetic:

**Container:** `jetracer_ros`  
**Base Image:** `arm64v8/ros:noetic-robot`

The container provides:
- ROS 1 Noetic environment
- Access to robot hardware (`/dev/ttyACM0`)
- Camera access (`/dev/video0`)
- GPU acceleration via NVIDIA runtime

## 📊 Logging

All operations are logged to `logs/` directory:

- `jetracer_YYYYMMDD_HHMMSS.log` - Manual mode logs
- `autonomous_YYYYMMDD_HHMMSS.log` - Autonomous mode logs

Logs include:
- System initialization
- Hardware checks
- Command execution
- Error messages
- Performance statistics

## ⚠️ Safety

**Important Safety Notes:**

1. **Always test in a safe, open area** first
2. **Keep emergency stop ready** (Space key or Ctrl+C)
3. **Start with low speeds** in autonomous mode
4. **Monitor confidence levels** - low confidence = uncertain
5. **Maximum execution time** prevents runaway behavior
6. **Camera must work properly** - autonomous mode depends on vision

## 🐛 Troubleshooting

### Camera doesn't work in Docker
- Known issue with `libbiff.so.1` library
- Run camera processing on host if needed
- See `scripts/camera.py` for workarounds

### Docker container not running
```bash
~/start_jetracer_docker.sh
docker ps  # Check if running
```

### Robot not responding
1. Check hardware connection: `ls -l /dev/ttyACM0`
2. Check Docker container: `docker ps`
3. Check ROS topics: `docker exec jetracer_ros rostopic list`

### Low autonomous performance
1. Lower `fps_target` in config (reduce to 5-10 Hz)
2. Use tinygrad backend for lighter inference
3. Check confidence threshold settings
4. Verify YOLOv8 model is loaded correctly

### Import errors
```bash
# Reinstall dependencies
pip install -r requirements.txt

# Check Python path
python3 -c "import sys; print('\n'.join(sys.path))"
```

## 🎯 Next Steps

1. **Test Manual Mode** - Verify basic robot control works
2. **Test Autonomous with Default Policy** - See how it behaves
3. **Collect Training Data** - Drive manually in your environment
4. **Train Custom Policy** - Learn from your driving data
5. **Tune Parameters** - Adjust speeds, confidence thresholds
6. **Add Features** - IMU integration, obstacle avoidance, etc.

## 📚 References

- **Dollop Project:** [github.com/muskanchojer/dollop](https://github.com/muskanchojer/dollop)
- **YOLOv8:** [docs.ultralytics.com](https://docs.ultralytics.com/)
- **tinygrad:** [github.com/tinygrad/tinygrad](https://github.com/tinygrad/tinygrad)
- **ROS Noetic:** [wiki.ros.org/noetic](http://wiki.ros.org/noetic)

## 📄 License

See individual component licenses:
- Dollop code: Check commabot/dollop-main/LICENSE
- Your robot control code: Your license
- Dependencies: Their respective licenses

## 🤝 Contributing

To improve the autonomous system:
1. Collect diverse training data
2. Experiment with model architectures
3. Add new sensors (LIDAR, ultrasonic, etc.)
4. Implement advanced features (path planning, SLAM, etc.)

---

**Happy autonomous driving! 🚗🤖**
