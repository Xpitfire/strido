# Linux on the Raspberry Pi 5

The Raspberry Pi 5 is Strido's "brain": a small Linux computer that runs ROS 2 inside Docker and talks to the servo controller over USB. This page covers choosing an operating system, flashing it, logging in without a screen, and the handful of Linux skills you need to keep the robot running.

::: tip In Strido
- **Hardware:** Raspberry Pi 5 (4 GB) with the Raspberry Pi Active Cooler and a 64 GB A2 microSD card (SanDisk Extreme), all in `hardware/bom.yaml`. It is fed with 5 V through the GPIO header, not through USB-C.
- **OS:** Ubuntu Server 24.04 (arm64) or Raspberry Pi OS Bookworm 64-bit, plus Docker Engine ([software](../../software.md#raspberry-pi-setup)).
- **Robot software:** runs in the `strido-ros:jazzy` container built from `docker/ros2/Dockerfile`, so the host OS only needs Docker, udev rules and a few firmware settings.
- **Devices:** the XIAO ESP32-S3 (USB CDC) and the RPLIDAR C1 (CP210x USB adapter) appear as `/dev/strido_mcu` and `/dev/rplidar` through `ros2/strido_bringup/config/99-strido.rules`.
:::

## What the Pi does, and what it does not

The Pi runs everything above the servo loop: the gait or policy node, the `mcu_bridge`, the LiDAR driver and (optionally) the camera. It does **not** drive servos or read the IMU itself. Those are on the ESP32-S3, which owns the I²C bus (PCA9685, LSM6DSOX, INA260) and runs a hard 200 Hz loop. The split exists because Linux is not a real-time OS: a busy Pi can pause a process for tens of milliseconds, which is harmless for planning but would make servos twitch. See [firmware](firmware.md).

So the Pi needs only USB serial access, not I²C or SPI. That keeps the Linux setup short.

## Choosing the operating system

| | Ubuntu Server 24.04 (arm64) | Raspberry Pi OS Bookworm 64-bit |
|---|---|---|
| Base | Ubuntu "Noble" | Debian 12 |
| ROS 2 Jazzy natively | Yes: Ubuntu 24.04 is Jazzy's Tier 1 platform (apt packages) | No official binary packages; use Docker |
| Pi 5 camera (libcamera fork) | Must be built yourself | Ships with it (`rpicam-apps`) |
| Tools such as `raspi-config`, `vcgencmd` | Partly | Yes |

Either works because the repo puts ROS 2 in a container (`FROM ros:jazzy-ros-base`, itself built on Ubuntu 24.04). The container brings its own Ubuntu userland; the host only provides the kernel, USB devices and networking. Pick **Raspberry Pi OS** if you want the camera (the Pi 5 camera stack needs the Raspberry Pi libcamera fork, which the Docker image does not include); pick **Ubuntu Server** if you want the option of installing ROS 2 natively later.

Always use the **64-bit** image. The ROS image, NumPy wheels and Docker's arm64 builds all assume `aarch64`.

## Flashing the card with Raspberry Pi Imager

1. Install Raspberry Pi Imager on your laptop and insert the microSD card.
2. Choose device **Raspberry Pi 5**, then the OS (under "Other general-purpose OS → Ubuntu" for Ubuntu Server 24.04, or "Raspberry Pi OS (64-bit)"; the Lite variant has no desktop and is enough for a headless robot).
3. When asked, open **OS customisation** (Edit settings) and set:
   - hostname, for example `strido`;
   - a user name and password (do not keep a default user);
   - Wi-Fi SSID, password and country;
   - on the **Services** tab: enable SSH, ideally with "public-key authentication only" and your public key pasted in.
4. Write, eject, insert the card into the Pi.

::: tip Why customise in the Imager
A walking robot has no keyboard or monitor. Pre-seeding user, Wi-Fi and SSH lets the Pi join your network on first boot so you can reach it from a laptop: this is a *headless* setup.
:::

## First boot and SSH

Power the Pi (logic power only, servo loop key out). After a minute it should be on the network:

```bash
ssh <user>@strido.local          # mDNS name; if it does not resolve, use the IP from your router
```

Use key-based login rather than passwords:

```bash
ssh-keygen -t ed25519             # on the laptop, once
ssh-copy-id <user>@strido.local  # installs the public key on the Pi
```

Then bring the system up to date before installing anything:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

On Raspberry Pi OS, also keep the bootloader EEPROM current (`sudo rpi-eeprom-update`); it holds power settings you will change below.

## Pi-specific configuration for this robot

Two settings from [electronics](../../electronics.md#raspberry-pi-configuration) matter because Strido powers the Pi through the GPIO 5 V pins. That path bypasses USB-C Power Delivery negotiation, so the Pi would otherwise assume a weak supply and limit USB current:

```bash
sudo rpi-eeprom-config --edit        # add:  PSU_MAX_CURRENT=5000
echo "usb_max_current_enable=1" | sudo tee -a /boot/firmware/config.txt
```

`PSU_MAX_CURRENT=5000` tells the bootloader the supply delivers 5 A; `usb_max_current_enable=1` lets the USB ports supply their full current (the LiDAR and ESP32 are USB powered). `config.txt` lives in `/boot/firmware/` on both Bookworm and Ubuntu 24.04.

::: warning
The optional self power-off overlay (`dtoverlay=gpio-poweroff,gpiopin=26`) is marked [UNVERIFIED on Pi 5] in the repo. Test it with the servos disarmed before relying on it.
:::

## Users, groups and device permissions

Linux controls hardware access through files in `/dev` and their owner group:

| Device | Typical name | Default group | Used by Strido? |
|---|---|---|---|
| USB CDC serial (XIAO ESP32-S3) | `/dev/ttyACM0` | `dialout` | Yes: `mcu_bridge`, `strido-cli` |
| USB-UART bridge (CP210x, LiDAR) | `/dev/ttyUSB0` | `dialout` | Yes: `sllidar_ros2` |
| I²C on the GPIO header | `/dev/i2c-1` | `i2c` | No: I²C is on the ESP32 |
| GPIO | `/dev/gpiochip*` | `gpio` | Only the optional power-off overlay |
| Docker daemon socket | `/var/run/docker.sock` | `docker` | Yes |

Two things make this simple here:

- **udev rules.** `99-strido.rules` matches the devices by USB vendor/product ID (Espressif `303a:1001`, Silicon Labs `10c4:ea60`), creates stable symlinks and sets `MODE="0666"`. Without them, the ESP32 and LiDAR could swap between `ttyACM0`/`ttyUSB0` names across reboots, and only `dialout` members could open them.

  ```bash
  sudo cp ros2/strido_bringup/config/99-strido.rules /etc/udev/rules.d/
  sudo udevadm control --reload && sudo udevadm trigger
  ls -l /dev/strido_mcu /dev/rplidar
  ```

- **docker group.** Adding yourself lets you run `docker` without `sudo`:

  ```bash
  sudo usermod -aG docker $USER      # log out and back in afterwards
  ```

  ::: warning
  Membership of `docker` is equivalent to root: anyone in it can start a privileged container. Only add trusted users.
  :::

If you run `strido-cli` or ROS 2 natively (outside Docker) without the udev rule, add yourself to `dialout` instead: `sudo usermod -aG dialout $USER`.

## Installing Docker and building the robot image

Install Docker Engine from Docker's own repository (the Debian or Ubuntu instructions in Further reading), then from a clone of the repository:

```bash
docker compose -f docker/compose.yaml build ros     # ROS 2 Jazzy, Gazebo libs, sllidar_ros2, this repo's packages
docker compose -f docker/compose.yaml run --rm robot
```

The second command starts `ros2 launch strido_bringup robot.launch.py`. Follow the start-up order in [electronics](../../electronics.md#safety-rules): robot lying in the rest pose, loop key in, *then* launch. Details are in [Docker](docker.md) and [ROS 2](ros2.md).

## systemd: services that start at boot

systemd is the process that starts and supervises services on both OSs. Docker itself is a systemd service:

```bash
systemctl status docker          # running? enabled at boot?
sudo systemctl enable --now docker
journalctl -u docker -f          # follow its log
journalctl -b -p warning         # warnings and errors since this boot
```

The repo ships **no** systemd unit for the robot, deliberately: the gait node commands the rest pose and stands up within 3 s of launch, and the safety rules require you to insert the loop key *before* launching. Auto-starting the robot at boot would move servos without a human present. If you add your own unit later (a `Type=simple` service running `docker compose -f docker/compose.yaml run --rm robot`, `After=docker.service`), keep the loop key as the arming step and never leave it inserted unattended.

## Useful commands

| Command | Tells you |
|---|---|
| `hostname -I`, `ip a` | IP addresses |
| `lsusb` | USB devices: look for `303a:1001` (XIAO) and `10c4:ea60` (CP210x) |
| `ls -l /dev/strido_mcu /dev/rplidar` | udev symlinks exist and point at a tty |
| `udevadm info -a -n /dev/ttyACM0` | attributes to match in a udev rule |
| `dmesg -w` | kernel messages live (plug a device in and watch) |
| `vcgencmd get_throttled` | `0x0` is good; bit 0 (`0x1`) = under-voltage now, bit 16 (`0x10000`) = under-voltage happened since boot |
| `vcgencmd measure_temp` | SoC temperature (the Active Cooler keeps it in check under ROS load) |
| `htop`, `free -h`, `df -h` | CPU, memory, disk |
| `docker ps`, `docker logs <id>` | running containers and their output |

`vcgencmd` is part of Raspberry Pi OS; on Ubuntu it may need installing (`libraspberrypi-bin`) or may be unavailable.

## Keeping it maintainable

- Update the host regularly (`apt full-upgrade`); ROS 2 lives in the image, so a host update cannot break ROS.
- Rebuild the image after pulling repo changes: the Dockerfile copies `packages/strido-core` and the three ROS packages at build time.
- Shut down cleanly (`sudo poweroff`) before pulling power: an SD card written to during power loss can corrupt the file system.

## Check yourself

1. Why does the Pi not need I²C enabled in Strido?
2. What do `PSU_MAX_CURRENT=5000` and `usb_max_current_enable=1` fix, and why does this robot need them?
3. Which file gives the ESP32-S3 a stable device name, and what is that name?
4. Why is Raspberry Pi OS the better choice if you want the camera?
5. Why does the repo not start the robot automatically at boot?

<details>
<summary>Answers</summary>

1. All I²C devices (PCA9685, LSM6DSOX, INA260) hang off the ESP32-S3; the Pi talks to the ESP32 over USB serial only.
2. Powering through the GPIO 5 V pins skips USB-C PD negotiation, so the Pi would assume a weak supply and limit USB current. The settings declare a 5 A supply and allow full USB current for the LiDAR and ESP32.
3. `ros2/strido_bringup/config/99-strido.rules`, copied to `/etc/udev/rules.d/`; it creates `/dev/strido_mcu`.
4. The Pi 5 camera stack needs the Raspberry Pi libcamera fork, which Raspberry Pi OS ships and the Docker image does not contain.
5. Launch makes the robot stand up within 3 s; the start-up order requires a person to arm the servos with the loop key just before launching.

</details>

## Further reading

- [Raspberry Pi documentation: getting started and Imager](https://www.raspberrypi.com/documentation/computers/getting-started.html)
- [Raspberry Pi documentation: `config.txt` and EEPROM settings](https://www.raspberrypi.com/documentation/computers/config_txt.html)
- [Docker Engine on Debian](https://docs.docker.com/engine/install/debian/) and [on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [ROS 2 Jazzy installation and supported platforms](https://docs.ros.org/en/jazzy/Installation.html)
- [systemd.service manual](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)
