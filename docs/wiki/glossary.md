# Glossary

Terms used on the Strido site and in this wiki, A–Z. Each entry says what the term means and, where it matters, how it applies to this robot; follow the link for the wiki page that explains it in depth.

## A

### Abduction
Sideways swing of a leg away from or towards the body's centre line. On Strido it is the hip joint, driven by the servo in the body; see [kinematics and gaits](software/kinematics-and-gaits.md).

### Accepted deviation
A hole that misses a verification band but is deliberately kept, recorded in `accepted_deviations` of `hardware/verification/tolerances.yaml` with an ADR and a builder action. The only one is ADR-009, the servo-mount M3 pilots; see [fasteners](making/fasteners.md).

### ADR (architecture decision record)
A short record of a design decision: context, options, decision, consequences and when to reconsider. Strido keeps them in [decisions.md](../decisions.md).

### Arachne
PrusaSlicer's variable-width perimeter generator, enabled in the kit profile, which fills thin walls instead of leaving gaps; see [3D printing](making/3d-printing.md).

### Arming port
The XT60H jack in the back shell (`arming_port_bezel`): W02 from the main fuse on one contact, W03 to the UBECs on the other. It connects the servo power branch only when the loop key is inserted; see [safety](making/safety.md).

### AWG (American Wire Gauge)
Wire size scale where a smaller number means a thicker wire. Strido uses 14 AWG for the battery trunk, 18 AWG for UBEC outputs, bus jumpers and the logic branch, 22 AWG for the servo leads, signals and the Pi 5 V feed; see [power](hardware/power.md).

## B

### Balance charger
A LiPo charger that monitors and equalises each cell through the pack's balance lead. The BOM includes a B6AC-class charger; see [batteries](hardware/batteries.md).

### Bed adhesion
How firmly the first layer sticks to the print bed. Too little and the part detaches; with PETG on smooth PEI, too much can damage the sheet; see [3D printing](making/3d-printing.md).

### Bearing seat
A printed bore into which a ball bearing or sleeve is pressed. The fit gate accepts a seat from 0.15 mm under to 0.30 mm over the bearing's outer diameter; see [mechanics](hardware/mechanics.md).

### BEC / UBEC
(Universal) battery eliminator circuit: a switching regulator from RC models that turns pack voltage into servo voltage. Strido uses two Hobbywing UBEC-10A at 6.0 V, each feeding two legs; see [power](hardware/power.md).

### BOM (bill of materials)
The list of everything to buy, with quantities and offers. Source: `hardware/bom.yaml`; published as the [BOM page](../bom/README.md).

### Brim
Extra lines around a part's first layer that increase bed contact. In the kit: 5 mm brim on parts taller than 40 mm; see [3D printing](making/3d-printing.md).

### Buck regulator (step-down)
A switching converter that lowers a voltage efficiently. The Pololu D36V50F5 makes the 5 V logic rail from the 2S pack; see [power](hardware/power.md).

### Build kit
The downloadable ZIP with everything needed to print and build a robot; see [downloads](../downloads.md).

## C

### C rating
A LiPo's maximum discharge current as a multiple of its capacity, $I = C \cdot Q / 1\,\mathrm{h}$ (e.g. $60 \times 5\,\mathrm{A} = 300\,\mathrm{A}$ continuous for the 5 Ah Strido pack, 100C burst). See [batteries](hardware/batteries.md).

### CadQuery
A Python library for parametric CAD. All new and modified Strido parts are CadQuery booleans on the upstream geometry; see [CAD as code](software/cad-as-code.md).

### Catalogue
The browsable list of all 76 part types (printed, purchased and fasteners) with images, sizes and assembly steps; see the [catalogue](../catalog.md).

### Clearance hole
A hole a screw passes through freely. ISO 273 sizes for M3 are 3.2 mm (fine) and 3.4 mm (medium); printed holes are chased with these drills; see [fasteners](making/fasteners.md).

### COBS
Consistent Overhead Byte Stuffing: an encoding that removes zero bytes from a message so `0x00` can mark the end of each frame. Used on the USB link between the Pi and the XIAO; see [firmware](software/firmware.md).

### CRC16
A 16-bit checksum appended to every protocol frame (CRC16-CCITT-FALSE) so corrupted frames are rejected; see [firmware](software/firmware.md).

### CSI
Camera Serial Interface: the ribbon-cable camera connector on the Raspberry Pi 5, used by the Camera Module 3 Wide via a 22→15-pin cable; see [sensors](hardware/sensors.md).

### Cut list
The table in the [wiring check](../verification/wiring.md) that gives every wire's routed length and the length to cut: routed length + a termination allowance per end (WAGO strip 11 mm, solder 6 mm, crimp 3 mm, screw terminal 7 mm) + slack of 8 %, at least 10 mm. Builders cut every wire from it; see [cable management](making/cable-management.md).

## D

### Docker
A tool that runs software in containers with all its dependencies. The ROS 2 Jazzy image for the Pi and for Gazebo is built from `docker/compose.yaml`; see [Docker](software/docker.md).

### Domain randomisation
Varying simulation parameters (friction, servo stiffness, mass, IMU noise) during training so a learned policy copes with the real robot; see [simulation and RL](software/simulation-and-rl.md).

### Dupont connector
A 2.54 mm pitch crimp contact and housing that plugs onto header pins and holds by friction. Used for the Pi 5 V feed (W12), W17/W20 at the PCA9685 and the twelve servo signal wires (re-crimped into 1-pin housings); see [tools and workshop](making/tools-and-workshop.md).

## E

### E-stop (emergency stop)
A latched stop. On Strido, `/strido/estop` makes the firmware pull PCA9685 OE high and stop all pulses; the physical servo kill is the loop key. See [safety](making/safety.md).

### Elephant foot
The flared bottom edge of a print caused by the squashed first layer; it tightens bottom-facing holes; see [3D printing](making/3d-printing.md).

### Engagement length
The length of a screw that actually forms or engages thread. The fit gate wants at least 1.5 d in printed pilots (4.5 mm for M3); see [fasteners](making/fasteners.md).

### ESD (electrostatic discharge)
A static spark that can damage chips. Handle the Pi, XIAO and sensor boards by their edges after touching grounded metal; see [safety](making/safety.md).

### ESP32-S3
Espressif's dual-core microcontroller with USB, used on the Seeed XIAO ESP32-S3 motion controller; see [microcontrollers](hardware/microcontrollers.md).

## F

### FDM (fused deposition modelling)
3D printing by extruding molten plastic line by line and layer by layer; see [3D printing](making/3d-printing.md).

### Femur
The thigh link of a leg, between the leg servo module and the knee; four are printed (`femur`).

### FFC (flat flexible cable)
The flat ribbon cable that connects the camera to the Pi's CSI port (300 mm in Strido).

### Firmware
The program running on the microcontroller. Strido's firmware (`firmware/strido_esp32s3`, PlatformIO) runs the 200 Hz control loop and the safety logic; see [firmware](software/firmware.md).

### Fit gate
The verification step `python -m strido_verify.fits` that measures every screw hole and bearing seat in the CAD against the bands in `tolerances.yaml`; see [fasteners](making/fasteners.md).

### Four-bar linkage
Four links joined in a loop by four pivots. Strido's knee uses a parallelogram and a four-bar to drive the tibia from the knee crank; see [mechanics](hardware/mechanics.md).

### Fuse
A wire link that melts above its rated current and so protects the wire after it. Strido uses a 25 A main and a 7.5 A logic ATO blade fuse; see [safety](making/safety.md).

## G

### Gait
The pattern in which legs move. Strido's default is a trot (diagonal leg pairs together) in `packages/strido-core`; see [kinematics and gaits](software/kinematics-and-gaits.md).

### Gate
An executable check that must pass before a change is accepted (interference, ROM, fits, clearance, printability, electronics, wiring, BOM). See the [verification](../verification.md) page.

### Gazebo Harmonic
A robot simulator that runs the ROS 2 stack unchanged against a simulated Strido; see [simulation and RL](software/simulation-and-rl.md).

### Go2 convention
Joint names, signs, frames and topics copied from the Unitree Go2's ROS 2 interface, so code written for a Go2 can drive Strido; see [ROS 2](software/ros2.md).

### Ground star
The single point where all grounds join. On Strido it is a heat-shrunk splice beside the battery input, from which W04 runs to both UBEC inputs (14 AWG) and the switch ground (18 AWG); one point keeps the servo return currents out of the logic grounds; see [power](hardware/power.md).

### Gyroid
A wavy, self-supporting infill pattern that is strong in all directions; the kit uses 30 % gyroid; see [3D printing](making/3d-printing.md).

## H

### Heat shrink
Tubing that shrinks when heated to insulate and strain-relieve a soldered joint; see [tools and workshop](making/tools-and-workshop.md).

### High-side shunt
A current-measuring resistor placed in the positive supply line. The INA260 measures the logic branch this way (VIN+ in, VIN− out); see [sensors](hardware/sensors.md).

### Hole compensation
A slicer setting that shrinks or grows printed holes. The print list asks for X-Y hole compensation −0.15 mm on the servo mounts (ADR-009); see [3D printing](making/3d-printing.md).

### Horn
The arm or disc that fits on a servo's splined output shaft and transmits its torque. Strido uses 25-tooth (25T) aluminium disc and clamping arm horns; see [servos](hardware/servos.md).

## I

### I²C
A two-wire bus (SDA data, SCL clock) where each device has an address. On Strido: PCA9685 0x40, LSM6DSOX 0x6A, INA260 0x41 at 400 kHz; see [buses](hardware/buses.md).

### IMU (inertial measurement unit)
A sensor measuring acceleration and rotation rate. The LSM6DSOX gives the robot its orientation (Mahony filter on the XIAO); see [sensors](hardware/sensors.md).

### INA260
Texas Instruments' current/voltage/power monitor with an integrated shunt (Adafruit 4226). It reports pack voltage for the low-battery cut-off; the firmware will not drive without it; see [sensors](hardware/sensors.md).

### Infill
The internal fill of a printed part, given as a density and a pattern (kit: 30 % gyroid); see [3D printing](making/3d-printing.md).

### Interference check
The gate that tests the assembled CAD for parts that overlap in space; report in [verification/interference.md](../verification/interference.md).

### ISO 4762 / DIN 912
The standard for socket head cap screws, the only screw head type in Strido; see [fasteners](making/fasteners.md).

## J

### Joint limits
The safe range of each joint, from a collision sweep of the full assembly (e.g. calf −150…−45°), shared by firmware, gait and simulation; see [kinematics and gaits](software/kinematics-and-gaits.md).

## K

### Kinematics
The geometry that relates joint angles to foot positions (forward) and foot positions to joint angles (inverse); see [kinematics and gaits](software/kinematics-and-gaits.md).

### Knee crank
The arm on the knee servo that drives the knee linkage; its angle maps non-linearly to the calf angle; see [mechanics](hardware/mechanics.md).

## L

### Layer height
The thickness of each printed layer; 0.2 mm in the kit, half the 0.4 mm nozzle; see [3D printing](making/3d-printing.md).

### LiDAR
A sensor that measures distances with a rotating laser. The Slamtec RPLIDAR C1 publishes `/scan` at 10 Hz from the top pedestal; see [sensors](hardware/sensors.md).

### LiPo (lithium polymer)
The rechargeable battery chemistry of the robot's 2S 5000 mAh pack: high power, but dangerous if shorted, overcharged or over-discharged; see [batteries](hardware/batteries.md).

### Lock nut (DIN 985)
A nut with a nylon insert that grips the thread, used at moving joints so they can turn freely without the nut backing off; see [fasteners](making/fasteners.md).

### Loop key
A shorted XT60 plug that arms the servo branch when inserted in the arming port; pulling it is the servo kill; see [safety](making/safety.md).

## M

### mAh (milliampere-hour)
Battery capacity: 5000 mAh can supply 5 A for one hour. With 7.4 V nominal it stores about 37 Wh; see [batteries](hardware/batteries.md).

### Mahony filter
A lightweight algorithm that fuses gyroscope and accelerometer data into an orientation estimate; runs on the XIAO for `/imu/data`; see [sensors](hardware/sensors.md).

### Manifold (closed)
A mesh with no holes or loose faces, so it has a well-defined inside; every kit STL is checked to be closed; see [CAD as code](software/cad-as-code.md).

### Microcontroller (MCU)
A small single-chip computer for real-time tasks. The XIAO ESP32-S3 is Strido's MCU; see [microcontrollers](hardware/microcontrollers.md).

### MJCF
MuJoCo's XML model format; `models/mujoco/strido.xml` is generated from the CAD; see [simulation and RL](software/simulation-and-rl.md).

### MuJoCo
A fast physics simulator used for the walking demo and reinforcement learning; see [simulation and RL](software/simulation-and-rl.md).

## N

### Nav2
The ROS 2 navigation stack. It talks to the robot through `/cmd_vel` and `/scan`, so it runs unchanged on Strido; see [ROS 2](software/ros2.md).

### NT-X
The robotics platform Strido integrates with through the `strido-ntx` extension; see [NT-X integration](../ntx-integration.md).

### N·m and kg·cm
Units of torque. Servo makers quote kg·cm; $1\,\mathrm{kg\,cm} = 9.81\,\mathrm{N} \times 0.01\,\mathrm{m} \approx 0.098\,\mathrm{N\,m}$, so $35\,\mathrm{kg\,cm} \approx 3.43\,\mathrm{N\,m}$; see [servos](hardware/servos.md).

## O

### OE (output enable)
The PCA9685 pin that switches all 16 outputs off when high. The XIAO holds it high until armed, and a 2.2 kΩ pull-up keeps it high during resets; see [safety](making/safety.md).

### Overhang
A surface printed over empty space. Beyond about 45° from vertical it usually needs supports; the print list gives each part's overhang share; see [3D printing](making/3d-printing.md).

## P

### PCA9685
A 16-channel, 12-bit PWM driver on I²C. It generates the 12 servo signals at 200 Hz but carries none of the servo current; see [buses](hardware/buses.md).

### Perimeter
An outline line of a printed layer; the kit prints 3 perimeters (≈ 1.2 mm wall); see [3D printing](making/3d-printing.md).

### PETG
Polyethylene terephthalate glycol: a tough, heat-resistant filament and the kit profile's material; PLA+ is the alternative; see [3D printing](making/3d-printing.md).

### Pilot hole
A hole smaller than the screw, into which a thread-forming screw cuts its thread (about 0.8 d after printing); see [fasteners](making/fasteners.md).

### PlatformIO
The build system for the firmware: `pio run` to compile and upload, `pio test -e native` for host unit tests; see [firmware](software/firmware.md).

### PLA+
A tougher variant of PLA filament allowed by the print list as an alternative to PETG; see [3D printing](making/3d-printing.md).

### Plate
A ready-arranged 220 × 220 mm build plate (3MF file); the kit has 10 graphite and 3 lime plates; see [3D printing](making/3d-printing.md).

### Policy
A learned controller that maps observations (IMU, command, previous action, gait clock) to joint actions; stored as `policy.npz` and run with numpy; see [simulation and RL](software/simulation-and-rl.md).

### PPO (proximal policy optimisation)
The reinforcement-learning algorithm used to train Strido's walking policy in MuJoCo; see [simulation and RL](software/simulation-and-rl.md).

### Print kit
The package of oriented STLs, slicer profile, parts sheet and plates; build one on the [print kit](../print-kit.md) page.

### Printability gate
The check that slices every part and plate with PrusaSlicer and scans wall thickness; report in [verification/printability.md](../verification/printability.md); see [3D printing](making/3d-printing.md).

### Pull-up resistor
A resistor that holds a signal at a defined high level when nothing drives it, like the 2.2 kΩ on PCA9685 OE; see [buses](hardware/buses.md).

### PWM (pulse-width modulation)
A signal whose pulse length carries information. Hobby servos read the position from the pulse width: 500–2500 µs for 180° on the SPT5435LV, 1500 µs being the centre; see [servos](hardware/servos.md).

## R

### Range of motion (ROM)
How far each joint can move without collisions; the ROM sweep produces the joint limits; see [kinematics and gaits](software/kinematics-and-gaits.md).

### Raspberry Pi 5
The robot's main computer (4 GB) running Linux and ROS 2; see [Linux on the Pi](software/linux-on-the-pi.md).

### REP-103
The ROS convention for units and frames: x forward, y left, z up, SI units; see [ROS 2](software/ros2.md).

### Reinforcement learning (RL)
Training a controller by trial and error in simulation, rewarding good behaviour; see [simulation and RL](software/simulation-and-rl.md).

### ROS 2
Robot Operating System 2: a middleware where nodes exchange messages on topics. Strido runs ROS 2 Jazzy; see [ROS 2](software/ros2.md).

### ros2_control
The ROS 2 framework for controllers and hardware interfaces; in Gazebo it consumes `/leg_controller/commands`; see [ROS 2](software/ros2.md).

## S

### Service loop
A deliberate length of free cable between two ties that lets a cable cross a moving joint without pulling on its terminations. Strido's thigh and knee servo leads cross the hip joint with 36 mm and 40 mm loops, at least 1.2 × the largest tie-to-tie distance over the hip range; see [cable management](making/cable-management.md).

### Servo (hobby servo)
A motor, gearbox, position sensor and controller in one case that moves to the angle given by a PWM pulse. Strido uses twelve SPT5435LV-180W, without position feedback to the controller; see [servos](hardware/servos.md).

### Slew limit
The maximum speed at which the firmware lets a commanded joint angle change (6 rad/s), to avoid violent jumps; see [firmware](software/firmware.md).

### Slicer
Software that turns a 3D model into printer instructions (G-code) layer by layer, e.g. PrusaSlicer; see [3D printing](making/3d-printing.md).

### SLAM
Simultaneous localisation and mapping: building a map while tracking the robot's position in it, here from `/scan`; see [ROS 2](software/ros2.md).

### Smoke test
The first power-up with the loop key out: check boot, `/battery_state`, `/diagnostics` and the OE voltage before any servo can move; see [safety](making/safety.md).

### Snug
Tightening a screw only until the head seats and the parts stop moving, the rule for screws into printed parts; see [fasteners](making/fasteners.md).

### SPI
A fast synchronous bus with clock, data and chip-select lines. The XIAO drives the ST7789 LCD over SPI, with an extra DC (data/command) line; see [buses](hardware/buses.md).

### Spiral wrap
A plastic spiral wound around a bundle of cables that holds and protects it while letting single cables branch out anywhere. Strido puts it on every bundle of three or more cables (`spiral_wrap`); see [cable management](making/cable-management.md).

### Stall torque / stall current
The torque a motor produces and the current it draws when blocked. SPT5435LV: about 3.43 N·m and 3.5 A at 6 V; see [servos](hardware/servos.md).

### Stand-off
A threaded spacer that lifts a circuit board off the deck (M2.5 × 6 mm and M2 × 8 mm brass, female-female); see [fasteners](making/fasteners.md).

### STEMMA QT
Adafruit's 4-pin JST-SH I²C connector system. Two STEMMA QT → female-socket cables connect the IMU to the PCA9685 (W18; the IMU sits too close under the Pi for Dupont housings) and to the INA260 (W19); see [buses](hardware/buses.md).

### STEP, STL and 3MF
STEP: exact CAD solids (the upstream Yertle assembly). STL: triangle meshes for printing. 3MF: a package of meshes plus arrangement, used for the plates; see [CAD as code](software/cad-as-code.md).

### Strain relief
Anything that keeps pull and bending away from a wire's termination: the insulation grip of a crimp, heat-shrink over a solder joint, a cable tie close to a connector. It matters most where solder has wicked into the strands and made them stiff; see [cable management](making/cable-management.md).

### Supports
Temporary printed structures under overhangs, removed after printing; the kit uses snug supports on listed parts; see [3D printing](making/3d-printing.md).

## T

### TF
The ROS 2 transform system that tracks coordinate frames (`odom`, `base_link`, `imu_link`, `lidar_link`); see [ROS 2](software/ros2.md).

### Thread-forming screw
A screw that cuts or forms its own thread in a plain pilot hole. 78 of Strido's screws do this in printed parts; see [fasteners](making/fasteners.md).

### Threadlocker
An anaerobic adhesive that stops screws from loosening. Medium (blue) strength is used on screws into metal horns; see [fasteners](making/fasteners.md).

### Tibia
The lower leg link (calf). Each leg has an `inner_tibia` and `outer_tibia` printed half with a 633ZZ bearing each; see [mechanics](hardware/mechanics.md).

### Topic
A named ROS 2 message channel, such as `/cmd_vel`, `/joint_states` or `/battery_state`; see [ROS 2](software/ros2.md).

### Trot
A gait in which diagonal leg pairs (front-left with rear-right, front-right with rear-left) move together; see [kinematics and gaits](software/kinematics-and-gaits.md).

## U

### udev rule
A Linux rule that gives a device a stable name when it is plugged in; `99-strido.rules` names the XIAO and LiDAR; see [Linux on the Pi](software/linux-on-the-pi.md).

### Upstream (Yertle)
The original open-source Yertle robot whose STEP and STL files Strido builds on, kept unchanged in `upstream/yertle/`; see [design](../design.md).

### URDF / xacro
The ROS robot description format (URDF) and its macro language (xacro); `strido.urdf.xacro` is generated from the CAD; see [simulation and RL](software/simulation-and-rl.md).

### USB CDC
USB's communication device class: the XIAO appears as a serial port to the Pi, carrying the COBS-framed protocol; see [firmware](software/firmware.md).

### uv
A Python package and workspace manager; Strido's Python packages are a uv workspace; see [CAD as code](software/cad-as-code.md).

## V

### VitePress
The static site generator that builds this documentation site.

## W

### WAGO 221-415
A five-way lever connector (32 A, 0.2–4 mm², strip 11 mm) used to build the servo power bus in the front and rear cavities; see [cable management](making/cable-management.md).

### Watchdog
A timer that triggers a safe action if no command arrives: no joint command for 200 ms → hold, 2 s more → relax; see [firmware](software/firmware.md).

## X

### XIAO ESP32-S3
Seeed's thumb-sized ESP32-S3 board: the robot's motion controller, talking USB to the Pi and I²C/SPI to the PCA9685, sensors and LCD; see [microcontrollers](hardware/microcontrollers.md).

### XT60
A two-pole power connector (Amass XT series) rated 30 A continuous, used for the battery input (under the deck), the arming port and the loop key; describe halves by pins or sockets, not male/female; see [power](hardware/power.md).
