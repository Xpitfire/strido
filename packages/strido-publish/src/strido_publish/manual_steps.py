"""Content model of the assembly manual: which instances each step fits, step text, part titles.

Every instance of the full assembly (printed part, purchased part, fastener, cable) is assigned to
exactly one step (`assign` asserts it), so the parts boxes add up to the complete robot.
Selectors: `strido_publish.manual_select`; rendering and Markdown: `strido_publish.manual`;
the A4 book: `strido_publish.book`.
"""

from .manual_select import (
    LEG_MOUNT,
    SHELL_NUTS,
    Step,
    base,
    body_part,
    both,
    cables,
    dressing,
    either,
    excluding,
    joints,
    label,
    runs,
    servo_leads,
    types,
)

STEPS = [
    Step(
        "Prepare the electronics deck",
        base(
            either(
                types("electronics_deck", "adafruit_lsm6dsox", "standoff_m2_5_ff_6", "standoff_m2_ff_8"),
                joints(
                    "stand-off -> deck (from below)",
                    "stand-off -> deck (from below, head in pocket)",
                    "IMU -> deck",
                    "IMU nut under the deck",
                ),
            )
        ),
        [
            "Press the LSM6DSOX IMU into its pocket (chip side up, STEMMA connectors towards the rear) and fix it with two M2.5 × 6 screws from the top and M2.5 nuts underneath.",
            "Fix the stand-offs from below with M2.5 × 5 screws: 8 stand-offs M2.5, 6 mm long (Raspberry Pi 5 and PCA9685) and 2 more for the INA260.",
            "Fix 3 stand-offs M2, 8 mm long, for the 5 V regulator with M2 × 5 screws from below.",
            "The screw heads sit in the counterbores under the deck. Do not over-tighten: the deck is 3 mm thick in the centre.",
        ],
        view=(-60.0, -35.0),
        explode=(0, 0, 25),
        scope="bench",
    ),
    Step(
        "Chassis frame",
        base(either(types("inner_shoulder_frame", "side_body_beam"), joints("chassis_side"))),
        [
            "Slide the prepared deck into the grooves of both side body beams.",
            "Close the frame with the two inner shoulder frames: 8 × M3 × 10 screws with hex nuts (nut side inside the bay).",
            "Check that the frame sits flat on the table and the deck cannot move.",
        ],
        radial="y",
    ),
    Step(
        "Hip servos",
        base(either(types("servo_spt5435lv"), joints("hip_servo_ears"))),
        [
            "Centre all twelve servos before mounting any horn or servo (see Step 0).",
            "Insert the four hip servos through the inner shoulder frames from the bay side; output shafts point outwards (front pair to the front, rear pair to the rear).",
            "Fix each servo with 4 × M3 × 10 screws and hex nuts through the servo ears (16 in total).",
            "Route the servo leads into the bay, they will run to the front and rear cavities later.",
        ],
        radial="-y",
    ),
    Step(
        "Hip bearings and shoulder frames",
        either(
            base(
                either(
                    types(
                        "bearing_625zz",
                        "outer_shoulder_frame",
                        "upper_shoulder_frame",
                        "lower_shoulder_frame_front",
                        "lower_shoulder_frame_rear",
                    ),
                    joints("shoulder_frames", "captive nut in upper shoulder frame (upstream pocket)"),
                )
            ),
            SHELL_NUTS,
        ),
        [
            "Press two 625ZZ bearings into each outer shoulder frame (4 in total).",
            "Assemble outer, upper and lower shoulder frames front and rear with 16 × M3 × 10 screws and hex nuts.",
            "Use the Strido lower shoulder frames: `lower_shoulder_frame_front` and `_rear` have the extra pilot hole for the servo-bus holder.",
            "Push M3 nuts into the nut pockets now, while they are reachable: 6 on top of the upper shoulder frames and 8 under the lower shoulder frames for the shell screws (Steps 21 and 22), and 2 more on top of the front upper shoulder frame for the camera base (Step 18).",
        ],
        radial="y",
    ),
    Step(
        "Servo power bus and motion controller",
        base(
            either(
                types("servo_bus_holder_front", "servo_bus_holder_rear", "wago_221_415", "seeed_xiao_esp32s3"),
                joints("bus holder -> lower shoulder frame (self-tapping)"),
            )
        ),
        [
            "Clip four WAGO 221-415 connectors into each servo-bus holder.",
            "Screw each holder to its lower shoulder frame with one M3 × 12 screw (self-tapping into the printed pilot hole).",
            "Place the XIAO ESP32-S3 in the front cavity, USB-C towards the bay (foam tape).",
        ],
        explode=(0, 0, 30),
    ),
    Step(
        "Servo UBECs",
        base(types("hobbywing_ubec_10a")),
        [
            "Leave both UBEC output jumpers open (6.0 V). Measure 6.0 V before any servo is connected.",
            "Foam-tape one UBEC into each side pocket next to the battery bay, standing on its long edge, leads towards the deck.",
        ],
        view=(-45.0, -30.0),
        explode=(0, 0, -30),
    ),
    Step(
        "Boards on the deck",
        base(
            either(
                types(
                    "raspberry_pi_5",
                    "adafruit_pca9685",
                    "adafruit_ina260",
                    "pololu_d36v50f5",
                    "pololu_power_switch_hp",
                ),
                joints("board -> stand-off", "INA260 -> stand-off", "regulator -> stand-off"),
            )
        ),
        [
            "Raspberry Pi 5 with Active Cooler: ports to the front, 4 × M2.5 × 5 screws.",
            "PCA9685: first solder the 2.2 kΩ OE pull-up (OE to VCC on the header, wiring W20), then mount it with the servo headers towards the right side, 4 × M2.5 × 5 screws. Leave its V+ terminal unconnected.",
            "INA260 (bridge A0 first, address 0x41): 2 × M2.5 × 5 screws. Pololu D36V50F5: 3 × M2 × 5 screws.",
            "Pololu pushbutton switch on foam tape in the right side strip, its two 5 mm terminal blocks soldered on (VIN/GND and VOUT/GND).",
        ],
        explode=(0, 0, 25),
        view=(-35.0, 45.0),
    ),
    Step(
        "Leg servo module",
        excluding(body_part("hip"), LEG_MOUNT, joints("knee_drive_centre_screw")),
        [
            "Build one leg at a time; the drawing shows the front-left leg. Front-left and rear-right legs use the *left* servo mount, front-right and rear-left the *right* one. The front legs use the Strido variants `left_servo_mount_fl` / `right_servo_mount_fr` (extra hip-pivot pilot).",
            "Mount the thigh servo and the knee servo in the servo mount with 8 × M3 × 10 screws through the servo ears, then close it with the top bracket: 2 × M3 × 20 screws.",
            "Press the hip bearing pin into the mount; the hip disc horn is fitted in Step 13.",
        ],
        per_leg=True,
        scope="leg",
        view=(-20.0, 20.0),
        explode=(40, 0, 0),
        anchor=("left_servo_mount", "right_servo_mount", "left_servo_mount_fl", "right_servo_mount_fr"),
    ),
    Step(
        "Thigh",
        body_part("thigh"),
        [
            "Fix the femur and the femur servo connector to a 25T aluminium disc horn with 4 × M3 × 20 screws.",
            "With the thigh servo centred, push the horn on the spline with the femur pointing 45° backwards (assembly reference) and fix it with the M3 × 8 centre screw.",
        ],
        per_leg=True,
        scope="leg",
        view=(-20.0, 20.0),
        explode=(30, 0, 0),
        anchor=("femur",),
    ),
    Step(
        "Knee drive crank",
        either(excluding(body_part("crank", "arm"), joints("crank_pins")), joints("knee_drive_centre_screw")),
        [
            "Press the 6805-2RS bearing into the shoulder crank (left or right version per leg) and fit it over the femur servo connector: it turns freely about the thigh axis.",
            "With the knee servo centred, push the 25T aluminium arm horn on its spline at 35° (assembly reference) and fix it with the M3 × 8 centre screw.",
        ],
        per_leg=True,
        scope="leg",
        view=(-20.0, 20.0),
        explode=(30, 0, 0),
        anchor=("left_shoulder", "right_shoulder"),
    ),
    Step(
        "Lower leg",
        excluding(body_part("calf"), joints("tibia_link_pin")),
        [
            "Press two 633ZZ bearings into the tibia halves.",
            "Join inner and outer tibia with 2 × M3 × 12 screws and lock nuts; clamp the foot spacer with the M3 × 20 screw and lock nut.",
            "Fit the knee axle: 2 × M3 × 10 screws with washers from both sides through the femur.",
        ],
        per_leg=True,
        scope="leg",
        view=(-20.0, 20.0),
        explode=(30, 0, 0),
        anchor=("outer_tibia",),
    ),
    Step(
        "Knee linkage",
        either(body_part("long_link", "short_link"), joints("tibia_link_pin", "crank_pins")),
        [
            "Press two 3 × 5 × 5 sleeve bearings into every link eye (8 per leg).",
            "Connect the links as drawn: 2 × M3 × 25 crank pins through the shoulder crank, the M3 × 16 screw with washer at the arm horn, and 1 × M3 × 25 with a lock nut at the tibia.",
            "Tighten the lock nuts only until the joint is free of play: the links must swing under their own weight.",
        ],
        per_leg=True,
        scope="leg",
        view=(-20.0, 20.0),
        explode=(30, 0, 0),
        anchor=("long_link",),
    ),
    Step(
        "Mount the legs",
        LEG_MOUNT,
        [
            "Fix a disc horn to each leg module with 2 × M3 × 8 screws.",
            "With the hip servo centred, push the leg on the hip servo spline (leg vertical) and fix it with the M3 × 8 centre screw.",
            "Insert the hip pivot screw (M3 × 10 with washer) through the 625 bearing into the hip bearing pin.",
        ],
        radial="x",
        zoom=0.8,
    ),
    Step(
        "Power entry",
        either(
            both(types("xt60h_female"), label("battery input")),
            both(types("fuse_holder_ato"), label("25 A main")),
            cables("W01", "W03", "W04", "W09"),
            runs("W02", "W02/arming"),
        ),
        [
            "Cut every wire to its length in the cut list ([wiring check](../verification/wiring.md#cut-list)); strip, tin and heat-shrink every solder joint.",
            "Battery input: solder W01 (14 AWG red) and W04 (14 AWG black) to an XT60H with sockets (check the contact rule in [electronics](../electronics.md#xt60-contact-rule-the-loop-key-must-never-fit-the-battery)) and lay it in the pocket beside the battery under the deck, hood towards the rear. Slide spiral wrap over W01 (it is unfused).",
            "Ground star beside it: splice W04 to the black inputs of both UBECs (14 AWG) and to the logic ground (18 AWG black, on to the switch GND).",
            "Main fuse: trim both leads of a 25 A in-line holder to 20 mm, splice W01 to one and W02 to the other, lay the holder on the rear WAGO bus with its leads out through the inner and outer frame openings and tie it to the upper shoulder frame. No fuse yet.",
            "W02 and W03 (to both UBEC red inputs, spliced under the deck) end behind the rear outer frame: they are soldered to the arming jack in Step 19. W09 (18 AWG red, logic feed) runs from there through the rear cavity and over the deck to the switch VIN; its other end waits for the logic fuse holder (Step 19).",
        ],
        view=(-45.0, -30.0),
    ),
    Step(
        "Servo leads and servo bus",
        either(servo_leads, cables("W05", "W06", "W07", "W08")),
        [
            "Thigh and knee servo leads: tie each to its servo mount plate at the marked point (close to the hip axis), leave the free loop (front: 30 mm thigh, 32 mm knee; rear: 22 mm; it takes up the hip motion) and tie it again at the shoulder frame (thigh) or the bus holder (knee).",
            "Unclip each WAGO pair from its holder before clamping (the XIAO platform blocks the levers in bay 0). At the tie peel the red and brown wires off the lead, cut them to the cut-list length, strip 11 mm and clamp them into the leg's WAGO pair: red into the upper (V+) connector, brown into the lower (GND), ports hip 1, thigh 2, knee 3; refit the pair. Hip servo leads split at the inner frame opening.",
            "Cut the orange signal wire to its cut-list length (measured from the tie), crimp a female Dupont contact, push it into a 1-pin housing and plug it onto the PWM pin of its PCA9685 channel (channel map in [electronics](../electronics.md#pin-maps)).",
            "UBEC outputs (W05 front, W06 rear): extend with 18 AWG into port 0 of bay 0. Jumpers W07/W08: 18 AWG from port 4 of bay 0 to port 0 of bay 1, V+ and GND separately along the WAGO faces.",
        ],
        view=(-30.0, 35.0),
    ),
    Step(
        "Logic and signal wiring",
        cables("W10", "W11", "W24", "W12", "W14", "W17", "W18", "W19", "W20", "W22"),
        [
            "18 AWG: switch VOUT to INA260 VIN+ (W10, red), INA260 VIN- to the regulator VIN (W11, red), switch GND to the regulator GND (W24, black; the INA260 terminal block takes only VIN+ and VIN-).",
            "W12: four 22 AWG wires from the regulator VOUT/GND, Dupont crimps at the Pi end. Leave them unplugged: they go onto the Pi header only after the supply check in Step 20.",
            "I²C: W17 (3V3, GND, SDA, SCL) and W20 (D3 to OE) are 22 AWG wires soldered to the XIAO pins and crimped (Dupont) for the PCA9685 left header. STEMMA QT cables: PCA9685 right header to the IMU (W18), IMU to the INA260 header (W19).",
            "USB: Pi lower port to the XIAO (W14, fold the spare length and tie it in the front cavity). Optional W22: Pi GPIO 26 to the switch OFF pad (22 AWG, Dupont crimp at the Pi, soldered at the switch).",
        ],
        view=(-35.0, 45.0),
    ),
    Step(
        "Front display",
        either(
            base(
                either(
                    types("front_shell_display", "waveshare_lcd_2inch", "display_bracket"),
                    joints("bracket -> LCD hex studs", "bracket -> front shell boss (self-tapping)"),
                )
            ),
            cables("W21"),
        ),
        [
            "Put the 2-inch LCD into the front shell window from the inside, screen outwards, header pins down.",
            "Fix the bracket to the LCD hex studs with 4 × M2 × 5 screws, then to the shell bosses with 2 × M3 × 10 (self-tapping).",
            "Plug the display cable (W21, supplied with the LCD) into the display, run it through the outer shoulder frame opening and solder its 8 wires to the XIAO pins (no room for Dupont housings under the upper shoulder frame); fold the spare length (cut list) and tie it at the opening.",
        ],
        scope="bench",
        view=(-150.0, 20.0),
        explode=(0, 25, 0),
    ),
    Step(
        "Front camera",
        either(
            cables("W16"),
            base(
                either(
                    types("camera_mount_base", "camera_tilt_plate", "rpi_camera_module_3_wide"),
                    joints(
                        "camera PCB -> tilt plate bosses",
                        "M2 nut behind tilt plate",
                        "camera tilt pivot",
                        "pivot nyloc (friction)",
                        "camera base + front shell -> upper shoulder frame nut (replaces upstream M3x8)",
                    ),
                )
            ),
        ),
        [
            "Fix the Camera Module 3 Wide to the tilt plate: 4 × M2 × 10 screws, M2 nuts behind the plate.",
            "Hang the tilt plate between the base cheeks with the M3 × 40 pivot screw and a lock nut; tighten until the camera holds its angle (15° down is the reference).",
            "Plug the 300 mm camera ribbon (W16) into CAM/DISP 0 of the Pi, run it through both shoulder frame openings and up through the front-shell slot to the camera; fold the spare length flat (no creases). Then put the front shell on and screw the camera base and shell to the upper shoulder frame with 2 × M3 × 12.",
        ],
        explode=(0, 0, 30),
    ),
    Step(
        "Rear panel",
        either(
            base(
                either(
                    types("back_shell_button", "pushbutton_12mm", "arming_port_bezel", "arming_port_ring"),
                    both(types("xt60h_female"), label("arming jack")),
                    both(types("fuse_holder_ato"), label("7.5 A logic")),
                    joints("clamp ring -> bezel through the D20 hole"),
                )
            ),
            cables("W13"),
            runs("W02/logic"),
        ),
        [
            "Mount the 12 mm power button in the small hole of the back shell and solder W13 (22 AWG pair, routed to the switch A/B pads).",
            "Insert the XT60 arming port into the printed bezel from outside, clamp it with the ring from inside: 2 × M2.5 × 6.",
            "Solder W02 and W03 to the two contacts of the arming jack. Logic fuse: trim the input lead of a second in-line holder to its cut length and splice it to W02 (heat-shrink); trim its output lead to 20 mm and splice W09 to it. Lay the holder in the shell between the jack and the button. No fuse yet.",
            "Put the back shell on. The loop key stays out until first power-up (final step).",
        ],
        view=(135.0, 20.0),
        explode=(0, 30, 0),
    ),
    Step(
        "Dress the harness and check the logic supply",
        dressing,
        [
            "Supply check before the Pi is connected: plug a charged pack into the battery input (W00) for a moment, insert both fuses, loop key out, press the button and measure 4.8–5.2 V at the W12 Dupont ends (D36V50F5: 5 V ± 4 %). Press again, pull the fuses, unplug the pack. Then plug W12 onto Pi pins 2/4 (5 V) and 6/14 (GND).",
            "Spiral-wrap every bundle of three or more cables and W01 where the drawing shows a sleeve; it protects the leads where they pass frames and moving parts.",
            "Tie at every marked point (2.5 × 100 mm ties, cut flush); two adhesive tie mounts on the deck carry the bundles in the side strips.",
            "Move every leg through its full range by hand: no cable may be pulled tight, pinched or touch a horn or link ([wiring check](../verification/wiring.md)).",
        ],
        view=(-30.0, 35.0),
    ),
    Step(
        "Top shell and LiDAR",
        either(
            cables("W15", "W23"),
            excluding(
                base(
                    either(
                        types("top_shell_sensor", "lidar_pedestal", "rplidar_c1", "rplidar_usb_adapter"),
                        joints(
                            "pedestal -> top shell (from below, self-tapping)",
                            "LiDAR -> pedestal",
                            "shell_to_shoulder_top",
                        ),
                    )
                ),
                SHELL_NUTS,
            ),
        ),
        [
            "Screw the LiDAR pedestal to the top shell from below: 4 × M3 × 12 (self-tapping).",
            "Put the LiDAR USB adapter into the pedestal, behind the cable slot, USB end towards the slot (foam tape). Lead the LiDAR's own cable (W23) through the notch at the pedestal front into the adapter, then fix the RPLIDAR C1 with 4 × M2.5 × 6 (max. 4 mm into the LiDAR).",
            "Plug the second USB cable (W15, from the Pi's upper USB port, routed over the Pi beside the cooler fan) into the adapter through the top-shell slot, then close the top shell over the front and back shells: 6 × M3 × 8 into the nuts inserted in Step 4.",
        ],
        explode=(0, 0, 35),
    ),
    Step(
        "Battery and bottom shell",
        either(
            cables("W00"),
            excluding(
                base(either(types("lipo_2s_5000_gensace", "bottom_shell"), joints("shell_to_shoulder_bottom"))),
                SHELL_NUTS,
            ),
        ),
        [
            "Strap the 2S LiPo under the deck (hook-and-loop strap), lead end to the rear.",
            "Plug the pack's own lead (W00) into the battery input XT60H in the pocket beside the battery (the lead turns forward along the left side under the rear hip servo). Keep the loop key out.",
            "Close the bottom shell: 8 × M3 × 8 screws into the nuts inserted in Step 4.",
        ],
        view=(-45.0, -30.0),
        explode=(0, 0, -35),
    ),
]


def assign(instances) -> list[list]:
    groups = [[] for _ in STEPS]
    for instance in instances:
        if instance.kind == "reference":
            continue
        hits = [index for index, step in enumerate(STEPS) if step.select(instance)]
        assert len(hits) == 1, (
            f"{instance.id} ({instance.part}, body {instance.body}, joint {instance.meta.get('joint')}) matches steps {hits}"
        )
        groups[hits[0]].append(instance)
    return groups
