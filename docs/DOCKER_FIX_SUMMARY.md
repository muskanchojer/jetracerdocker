# Docker ROS Connection Fix

## Problem

When running `python main.py --mode manual`, you got the error:
```
Unable to register with master node [http://localhost:11311]: master may not be running yet.
```

## Root Cause

The issue was that `main.py` was calling `robot.run_keyboard_control()` directly, which tried to communicate with ROS **without starting roscore first**.

## What Was Fixed

### 1. **Added `start_keyboard_control()` method** in `main_old.py`
- New method that properly starts ROS infrastructure before keyboard control
- Starts `roscore` and `robot_base` nodes first
- Then starts keyboard control

### 2. **Updated `main.py`** to call the correct method
- Changed from: `robot.run_keyboard_control()` (direct keyboard, no ROS)
- Changed to: `robot.start_keyboard_control()` (starts ROS first, then keyboard)

### 3. **Fixed Docker exec commands** in `control_adapter.py`
- Added `-i` flag for interactive mode: `docker exec -i`
- Ensures proper ROS environment sourcing

### 4. **Added ROS startup** for autonomous mode
- `autonomous_control.py` now starts roscore if not running
- Checks ROS master status before proceeding

### 5. **Improved Docker checks**
- Now verifies both Docker container AND ROS master are running
- Better error messages

## The Correct Startup Sequence

### Manual Mode:
```
1. Check Docker running          ✓
2. Check hardware connected       ✓
3. Sync scripts                   ✓
4. Start roscore                  ✓ (NEW!)
5. Start robot_base               ✓ (NEW!)
6. Start keyboard control         ✓
```

### Autonomous Mode:
```
1. Check Docker running           ✓
2. Start roscore if needed        ✓ (NEW!)
3. Start robot_base if needed     ✓ (NEW!)
4. Check camera                   ✓
5. Start autonomous loop          ✓
```

## Docker Command Structure

All ROS commands now use this pattern:
```bash
docker exec -i jetracer_ros bash -c \
  "source /root/catkin_ws/devel/setup.bash && <ros_command>"
```

Key points:
- `-i` flag for interactive mode
- Always source ROS environment: `source /root/catkin_ws/devel/setup.bash`
- Full path to catkin workspace: `/root/catkin_ws/`

## Testing

### Test Manual Mode:
```bash
source activate.sh  # or: source .venv/bin/activate
python main.py --mode manual
```

Expected output:
```
✅ Docker container 'jetracer_ros' is running
✅ Robot connected
✅ Synced 4 scripts

  Starting ROS core...
  Starting robot base...

============================================================
  ✅ ROS SYSTEMS READY
============================================================

🎮 Keyboard control active
Controls: W=forward, A=left, S=backward, D=right, Space=stop, Q=quit
```

### Test Autonomous Mode:
```bash
source activate.sh
python main.py --mode autonomous
```

Expected output:
```
✅ Docker container running
  Starting ROS core...
  Starting robot base...
✅ ROS infrastructure started
✅ Camera found
✅ Robot connected

🤖 Autonomous mode active!
```

## Common Issues & Solutions

### Issue: "Unable to register with master"
**Solution:** ROS master not started. The fix ensures roscore starts automatically.

### Issue: "Docker container not running"
**Solution:** Start Docker first:
```bash
~/start_jetracer_docker.sh
```

### Issue: "source: not found" in Docker
**Solution:** Commands now use `bash -c` to ensure bash shell is used.

### Issue: Command hangs or times out
**Solution:** Added `-i` flag for non-interactive commands.

## What Changed in Code

### `main_old.py`:
```python
# NEW METHOD
def start_keyboard_control(self):
    """Start keyboard control only (for main.py integration)"""
    # Starts roscore and robot_base first
    self.start_roscore()
    self.start_robot_base()
    # Then keyboard control
    kb_proc = self.run_keyboard_control()
    kb_proc.wait()
```

### `main.py`:
```python
# BEFORE:
robot.run_keyboard_control()  # ❌ No ROS startup

# AFTER:
robot.start_keyboard_control()  # ✅ Starts ROS first
```

### `control_adapter.py`:
```python
# BEFORE:
["docker", "exec", "jetracer_ros", "bash", "-c", ...]

# AFTER:
["docker", "exec", "-i", "jetracer_ros", "bash", "-c", ...]
#                    ^^^ Added -i flag
```

### `autonomous_control.py`:
```python
# NEW METHOD
def start_ros_infrastructure(self):
    """Start roscore and robot_base if not already running"""
    # Checks if already running, starts if needed
    # Called during check_prerequisites()
```

## Summary

✅ All Docker paths verified and fixed
✅ ROS master now starts automatically  
✅ Proper command sequencing implemented  
✅ Better error messages and checks  
✅ Works for both manual and autonomous modes  

The system now properly manages ROS infrastructure startup!
