# Baxter Setup Guide — Simulation & Physical Robot

**Stack:** Windows 11 + WSL2 + Docker + ROS Kinetic + Foxglove (TF/joint visualization)

This guide walks through setting up the Rethink Robotics Baxter robot environment from scratch. It covers two workflows that share the same Docker container and scripts:

- **Simulation** — run Baxter in Gazebo inside Docker on your Windows machine, visualize live joint/transform data in Foxglove
- **Physical robot** — connect to a real Baxter over the network and run the same scripts with a single line change

> **Foxglove note:** With this setup, Foxglove shows live transform frames and joint names, but not the solid 3D robot mesh. This is a known limitation of the rosbridge connection type — see [Known Limitation](#known-limitation-no-robot-mesh-in-foxglove) at the bottom for details. For verifying pick-and-place logic, the joint angle readouts and TF tree are functionally sufficient.

---

## Table of Contents

1. [Part 1: One-Time Environment Setup](#part-1-one-time-environment-setup)
2. [Part 2: Create the Docker Container](#part-2-create-the-docker-container)
3. [Part 3: Every Session (Simulation)](#part-3-every-session-simulation)
4. [Part 4: Connect Foxglove](#part-4-connect-foxglove)
5. [Part 5: Run and Verify Your Code](#part-5-run-and-verify-your-code)
6. [Part 5.5: Example Scripts](#part-55-example-scripts)
7. [Physical Robot Setup](#physical-robot-setup)
8. [Resetting the Robot's Position](#resetting-the-robots-position)
9. [Known Limitation: No Robot Mesh in Foxglove](#known-limitation-no-robot-mesh-in-foxglove)

---

## Part 1: One-Time Environment Setup

Do this section once. After it's done, you won't need to repeat it.

### 1.1 Install WSL2

Open PowerShell as Administrator:

```powershell
wsl --install
```

Restart your PC when prompted. Ubuntu will finish setting up automatically and ask you to create a username and password.

### 1.2 Confirm GPU Access in WSL

Open Ubuntu from the Start menu, then run:

```bash
nvidia-smi
```

If this fails, update your NVIDIA driver on Windows (not inside WSL) from [nvidia.com/drivers](https://www.nvidia.com/drivers), then restart and try again.

### 1.3 Install NVIDIA Container Toolkit (inside WSL Ubuntu)

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update && sudo apt install -y nvidia-container-toolkit
```

### 1.4 Install Docker Desktop (on Windows, not WSL)

- Download from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop) and install with default settings
- Open Docker Desktop → gear icon → Resources → WSL Integration → enable integration with your default WSL distro → Apply & Restart

Then back in WSL Ubuntu, configure Docker to use your GPU:

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Verify everything works:

```bash
docker run --rm --gpus all nvidia/cuda:11.0.3-base-ubuntu20.04 nvidia-smi
```

You should see your GPU listed in the output.

### 1.5 Pull the Baxter Docker Image

```bash
docker pull dabaspark/kinetic-baxter:nvidia
```

This is about 1.4 GB and may take a few minutes.

> **Tip:** Docker Desktop keeps running in the background (using RAM) even after you close its window. To fully quit it: right-click the whale icon in your system tray → Quit Docker Desktop. To stop it auto-starting: Docker Desktop → gear icon → General → uncheck "Start Docker Desktop when you log in."

---

## Part 2: Create the Docker Container

Run this **once** to create your working container. We name it `baxter2` because port 9090 (needed for Foxglove) must be mapped at container creation time — it can't be added after the fact.

```bash
# Any WSL terminal
docker run -it \
  --name baxter2 \
  --gpus all \
  -p 9090:9090 \
  --env="DISPLAY" \
  --env="QT_X11_NO_MITSHM=1" \
  --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
  dabaspark/kinetic-baxter:nvidia
```

This drops you inside the container at a `ros@...` prompt. The container persists — use `docker start baxter2` and `docker exec -it baxter2 bash` to return to it. You do **not** need to re-create it.

### 2.1 Install rosbridge (one-time, inside the container)

```bash
source /opt/ros/kinetic/setup.bash
source ~/ros_ws/devel/setup.bash
sudo apt-get update
sudo apt-get install -y --allow-unauthenticated ros-kinetic-rosbridge-server
```

> **Note:** The `--allow-unauthenticated` flag is required because this image's package signing keys are expired (it's a multi-year-old ROS Kinetic snapshot). This is safe for local simulation use.

---

## Physical Robot Setup


### Physical Safety Checklist

<!-- things to verify before enabling the robot each session -->

### Connecting to Baxter's Network

<!-- e.g. how to join Baxter's WiFi/Ethernet, what IP the robot is on, any router/switch config -->

### Configuring the ROS Environment for the Physical Robot

<!-- e.g. ROS_MASTER_URI, ROS_IP, any .bashrc changes needed -->

### Verifying the Connection

<!-- e.g. ping test, rostopic list, checking robot state -->

---

## Part 3: Every Session (Simulation)

Repeat this section each session. You need **three terminal windows** total (two stay running, one is used briefly then can close).

> **Physical robot users:** Skip this entire section. You do not need Docker, Gazebo, or rosbridge to run on the real Baxter. Jump to [Part 5.5](#part-55-example-scripts) and follow the "Run on the physical robot" steps under each script.

### 3.1 Start Docker Desktop

Open Docker Desktop from the Start menu. Wait for "Engine running" in the bottom left.

### 3.2 Terminal 1 — Simulator

```bash
docker start baxter2
docker exec -it baxter2 bash
```

Now inside the container:

```bash
source /opt/ros/kinetic/setup.bash
source ~/ros_ws/devel/setup.bash
./baxter.sh sim
roslaunch baxter_gazebo baxter_world.launch gui:=false
```

Wait 30–60 seconds for messages to stop scrolling. You can ignore the `legacyModeNS` warning — it's harmless. **Leave this terminal open and running.**

### 3.3 Terminal 2 — Rosbridge

Open a new PowerShell window:

```powershell
wsl
docker exec -it baxter2 bash
```

Now inside the container:

```bash
source /opt/ros/kinetic/setup.bash
source ~/ros_ws/devel/setup.bash
roslaunch rosbridge_server rosbridge_websocket.launch
```

Wait for: `"Rosbridge WebSocket server started at ws://0.0.0.0:9090"`. **Leave this terminal open and running.**

### 3.4 Terminal 3 — Get Your WSL IP Address

Open a third PowerShell window:

```powershell
wsl
hostname -I
```

Copy the first IP address printed (e.g. `172.27.91.103`). This can change between WSL restarts — always re-check it. You can close this terminal after copying the IP.

### 3.5 (Optional) Verify the Port Is Reachable from Windows

Open a regular PowerShell window (not WSL):

```powershell
Test-NetConnection -ComputerName <your-wsl-ip> -Port 9090
```

Look for `"TcpTestSucceeded : True"`. If False, double-check the container was created with `-p 9090:9090` (Part 2) and that Terminal 2's rosbridge is actually running.

---

## Part 4: Connect Foxglove

> **Simulation only.** Foxglove is used here to visualize the simulated robot's joint state and TF frames. Skip this section if you're working directly on the physical robot.

1. Go to [foxglove.dev](https://foxglove.dev) (or [app.foxglove.dev](https://app.foxglove.dev)) in your browser — no install needed
2. Click "Open Connection"
3. Select **ROS 1** as the connection type
4. In the URL box enter: `ws://<your-wsl-ip>:9090` (e.g. `ws://172.27.91.103:9090`)
5. Click **Connect**

> **Important:** Make sure the connection type is explicitly set to "Rosbridge" / "ROS 1", **not** the generic "Foxglove WebSocket" option. They use different, incompatible protocols — entering a rosbridge URL under the wrong type will hang on "Waiting for events" with the Connect button greyed out.

### 4.1 Add a 3D Panel

- Click Panel (top left) → add a 3D panel to your layout
- In the Topics tab, you should see live topics like `/tf`, `/tf_static`, `/sim/laserscan/...`, etc.
- Zoom into the cluster of labels in the 3D view to see Baxter's joint/frame names (e.g. `right_torso_itb`, `left_lower_forearm`)

---

## Part 5: Run and Verify Your Code

In a new terminal into the container (simulation) or a terminal on Baxter's network (physical robot):

```bash
docker exec -it baxter2 bash
source /opt/ros/kinetic/setup.bash
source ~/ros_ws/devel/setup.bash
rosrun baxter_tools enable_robot.py -e
```

Then run your script, and verify movement by checking joint angles:

```python
python -c "
import rospy, baxter_interface
rospy.init_node('check')
limb = baxter_interface.Limb('right')
print(limb.joint_angles())
"
```

You can also watch the `/tf` topic update live in Foxglove's 3D panel as your script runs (simulation only).

---

## Part 5.5: Example Scripts

The scripts in this repo all follow the same pattern: get the script onto the container, test it in simulation first, then switch to the real robot by changing only the `baxter.sh` connection line.

### Getting a Script onto the Container

Open a terminal into the container:

```bash
docker exec -it baxter2 bash
source /opt/ros/kinetic/setup.bash
source ~/ros_ws/devel/setup.bash
```

Create the file with nano:

```bash
nano ~/ros_ws/<script_name>.py
```

Paste in the script contents (right-click to paste in most terminals), then save and exit with `Ctrl+O`, `Enter`, `Ctrl+X`.

---
### Script 1: `path_planner.py`

Moves a chosen arm (left or right) to XYZ coordinates in meters, relative to the robot's base, using Baxter's built-in inverse kinematics (IK) solver. Supports a planned sequence of moves and gripper actions defined as a list in `main()`.

**Run in simulation**

Terminals 1 and 2 must already be running. Then:

```bash
docker exec -it baxter2 bash
source /opt/ros/kinetic/setup.bash
source ~/ros_ws/devel/setup.bash
rosrun baxter_tools enable_robot.py -e
python ~/ros_ws/path_planner.py
```
> **Note:** If a target XYZ position is unreachable (too far away, or would pass through the robot's own body), the script prints "No valid IK solution" and stops safely rather than guessing. Adjust the `target_x/y/z` values in the plan if this happens.

**Run on the physical robot**

```bash
docker exec -it baxter2 bash
source /opt/ros/kinetic/setup.bash
source ~/ros_ws/devel/setup.bash
./baxter.sh <baxter_ip_address>
rosrun baxter_tools enable_robot.py -e
python ~/ros_ws/path_planner.py
```
> ⚠️ **Physical robot:** Make sure the space around Baxter's left arm is physically clear before running — unlike simulation, a bad joint angle can cause a real collision.
---

## Resetting the Robot's Position

To return Baxter to a safe, neutral pose at any time — works identically in simulation and on the physical robot:

```bash
rosrun baxter_tools tuck_arms.py -u
```

The `-u` flag means **untuck** — arms move to a relaxed, safe position. The opposite, `-t`, tucks the arms in tight for storage or transport:

```bash
rosrun baxter_tools tuck_arms.py -t
```

---

## Known Limitation: No Robot Mesh in Foxglove

With this setup, Foxglove shows live transform frames and joint names, but not the solid 3D robot body. This is a fundamental limitation of the rosbridge connection type, not a misconfiguration:

- Foxglove only auto-loads the robot mesh (URDF) when connected via a native ROS connection or the Foxglove Bridge — rosbridge doesn't expose ROS parameters the way Foxglove's URDF loader expects
- The Baxter image uses ROS Kinetic, which predates the `ros-$ROS_DISTRO-foxglove-bridge` package that would otherwise solve this
- Workarounds exist (e.g. adding the URDF as a manual Custom Layer in Foxglove, or publishing a `MarkerArray` of meshes) but add significant complexity

For verifying pick-and-place logic, the numeric joint angles and TF tree that already work are functionally sufficient — you don't strictly need the visual mesh to confirm your code moves the arm correctly.
