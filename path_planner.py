#!/usr/bin/env python
"""
path_planner.py

GOAL: Move Baxter's arm (left OR right, chosen at startup) through a
planned sequence of steps defined in main().

NEW FEATURES vs move_to_xyz.py:
  1. User picks which arm to use at startup.
  2. Arm movement and gripper actions are separate functions you can
     call in any order.
  3. A plan is just a list of command tuples that execute in order -
     like a simple recipe or script for the robot to follow.

PLAN COMMANDS:
  ('move',  x, y, z)    - move hand to this XYZ position (meters)
  ('open',)             - open the gripper
  ('close',)            - close the gripper
  ('sleep', seconds)    - pause for N seconds before the next step

COORDINATE SYSTEM (meters, from robot base):
  x = forward (+) / backward (-)
  y = left (+) / right (-)
  z = up (+) / down (-)
"""

import rospy
import baxter_interface
from baxter_interface import CHECK_VERSION
from geometry_msgs.msg import PoseStamped, Pose, Point, Quaternion
from std_msgs.msg import Header
from baxter_core_msgs.srv import SolvePositionIK, SolvePositionIKRequest


# ──────────────────────────────────────────────────────────────────────────────
# IK SOLVER  (unchanged from move_to_xyz.py)
# ──────────────────────────────────────────────────────────────────────────────

def get_joint_angles_for_position(limb_name, x, y, z):
    """
    Ask Baxter's IK solver for the joint angles that place the hand at
    (x, y, z) with the gripper pointing straight down.

    Returns a dict of {joint_name: angle} on success, or None if the
    position is unreachable.
    """
    target_pose = PoseStamped(
        header=Header(stamp=rospy.Time.now(), frame_id='base'),
        pose=Pose(
            position=Point(x=x, y=y, z=z),
            orientation=Quaternion(x=0.0, y=1.0, z=0.0, w=0.0)  # gripper down
        ),
    )

    service_name = (
        "ExternalTools/" + limb_name + "/PositionKinematicsNode/IKService"
    )
    ik_service = rospy.ServiceProxy(service_name, SolvePositionIK)

    request = SolvePositionIKRequest()
    request.pose_stamp.append(target_pose)

    rospy.wait_for_service(service_name, 5.0)
    response = ik_service(request)

    if response.isValid[0]:
        return dict(zip(response.joints[0].name, response.joints[0].position))
    else:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# INDIVIDUAL ACTIONS  (call these from your plan, or directly in main)
# ──────────────────────────────────────────────────────────────────────────────

def move_to(arm, limb_name, x, y, z):
    """
    Move the arm's hand to the given XYZ position.

    Returns True if the move succeeded, False if the IK solver could
    not find a solution (position unreachable).
    """
    print("  Moving to (x=%.3f, y=%.3f, z=%.3f)..." % (x, y, z))

    joint_angles = get_joint_angles_for_position(limb_name, x, y, z)

    if joint_angles is None:
        print("  ERROR: No IK solution found. Position may be out of reach.")
        return False

    arm.move_to_joint_positions(joint_angles)
    print("  Reached position.")
    return True


def open_gripper(gripper):
    """Open the gripper fully."""
    print("  Opening gripper...")
    gripper.open()
    rospy.sleep(0.5)   # short pause so the gripper finishes moving


def close_gripper(gripper):
    """Close the gripper to grip an object."""
    print("  Closing gripper...")
    gripper.close()
    rospy.sleep(0.5)   # short pause so the gripper finishes moving


# ──────────────────────────────────────────────────────────────────────────────
# PLAN EXECUTOR
# ──────────────────────────────────────────────────────────────────────────────

def execute_plan(arm, gripper, limb_name, plan):
    """
    Run every step in the plan list, in order.

    If a 'move' step fails (unreachable position), you'll be asked
    whether to skip it and continue or abort the whole plan.
    """
    total = len(plan)

    for step_num, step in enumerate(plan, start=1):
        command = step[0]
        print("\n[Step %d / %d]  %s" % (step_num, total, str(step)))

        if command == 'move':
            _, x, y, z = step
            success = move_to(arm, limb_name, x, y, z)

            if not success:
                answer = input("  Skip this step and continue? (y/n): ").strip().lower()
                if answer != 'y':
                    print("Aborting plan.")
                    return

        elif command == 'open':
            open_gripper(gripper)

        elif command == 'close':
            close_gripper(gripper)

        elif command == 'sleep':
            _, duration = step
            print("  Waiting %.1f second(s)..." % duration)
            rospy.sleep(duration)

        else:
            print("  Unknown command '%s' - skipping." % command)

    print("\n✓ Plan complete!")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN  ─  edit your plan here
# ──────────────────────────────────────────────────────────────────────────────

def main():
    rospy.init_node('path_planner')

    # ── 1. Choose which arm to use ──────────────────────────────────────────
    while True:
        limb_name = input("Which arm? (left / right): ").strip().lower()
        if limb_name in ('left', 'right'):
            break
        print("  Please type 'left' or 'right'.")

    # ── 2. Enable robot and set up arm + gripper ────────────────────────────
    print("\nEnabling robot...")
    rs = baxter_interface.RobotEnable(CHECK_VERSION)
    rs.enable()

    arm     = baxter_interface.Limb(limb_name)
    gripper = baxter_interface.Gripper(limb_name)

    print("Calibrating %s gripper..." % limb_name)
    gripper.calibrate()
    rospy.sleep(1.0)
    gripper.open()

    # ── 3. Define your plan ─────────────────────────────────────────────────
    #
    # Add, remove, or reorder steps freely. The robot will execute them
    # top-to-bottom in the order you list them.
    #
    # Commands:
    #   ('move',  x, y, z)   move hand to this position (meters)
    #   ('open',)             open the gripper
    #   ('close',)            close the gripper
    #   ('sleep', N)          pause N seconds
    #
    plan = [
        # 1. Reach down to pick-up spot
        ('move',  0.65,  0.30,  0.10),

        # 2. Grab the object
        ('close',),
        ('sleep', 1.0),          # wait for grip to settle

        # 3. Lift up
        ('move',  0.65,  0.30,  0.30),

        # 4. Carry across to drop spot
        ('move',  0.65, -0.10,  0.30),

        # 5. Lower down to drop spot
        ('move',  0.65, -0.10,  0.10),

        # 6. Release the object
        ('open',),
        ('sleep', 0.5),

        # 7. Lift back up and clear
        ('move',  0.65, -0.10,  0.30),
    ]

    # ── 4. Run the plan ─────────────────────────────────────────────────────
    execute_plan(arm, gripper, limb_name, plan)

    print("\nFinal %s arm joint angles:" % limb_name)
    print(arm.joint_angles())


if __name__ == '__main__':
    main()