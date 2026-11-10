# Strido ROS 2 Jazzy + Gazebo Harmonic workspace (amd64 and arm64, incl. Raspberry Pi 5 and Apple silicon).
#   docker compose -f docker/compose.yaml build ros
#   docker compose -f docker/compose.yaml run --rm sim-smoke
FROM ros:jazzy-ros-base

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-jazzy-ros-gz \
        ros-jazzy-gz-ros2-control \
        ros-jazzy-ros2-controllers \
        ros-jazzy-ros2-control \
        ros-jazzy-xacro \
        ros-jazzy-robot-state-publisher \
        ros-jazzy-tf2-ros \
        ros-jazzy-teleop-twist-keyboard \
        git \
        python3-serial \
        python3-numpy \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ws
# Slamtec LiDAR driver (not packaged for Jazzy): pinned upstream commit
ARG SLLIDAR_COMMIT=34300099fadfc772965962dec837bf436706188f
RUN git clone https://github.com/Slamtec/sllidar_ros2 /ws/src/sllidar_ros2 \
    && git -C /ws/src/sllidar_ros2 checkout ${SLLIDAR_COMMIT}
COPY packages/strido-core /ws/packages/strido-core
RUN pip3 install --no-cache-dir --break-system-packages --no-deps /ws/packages/strido-core
COPY ros2/strido_description /ws/src/strido_description
COPY ros2/strido_bringup /ws/src/strido_bringup
COPY ros2/strido_control /ws/src/strido_control
RUN . /opt/ros/jazzy/setup.sh && colcon build --symlink-install --event-handlers console_direct-

COPY docker/ros2/entrypoint.sh docker/ros2/sim_smoke.sh /
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
