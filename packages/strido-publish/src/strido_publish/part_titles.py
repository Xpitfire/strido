"""Human-readable titles of catalogue parts (manual, book, catalogue, viewer)."""

from strido_cad import fastener_meshes, wiring

WIRING_TYPES = wiring.load()["cable_types"]
FASTENER_TITLES = {
    "iso4762": "socket head screw",
    "iso7380": "button head screw",
    "iso4032": "hex nut",
    "din985": "lock nut (nylon insert)",
    "iso7089": "washer",
    "standoff": "stand-off F-F",
}
PURCHASED_TITLES = {
    "servo_spt5435lv": "Servo SPT5435LV-180W",
    "bearing_625zz": "Ball bearing 625ZZ",
    "bearing_633zz": "Ball bearing 633ZZ",
    "bearing_6805_2rs": "Ball bearing 6805-2RS",
    "sleeve_bearing_3x5x5_pair": "Sleeve bearings 3×5×5 (pair)",
    "servo_disc_horn_25t": "25T aluminium disc horn",
    "servo_arm_horn_25t": "25T aluminium arm horn",
    "raspberry_pi_5": "Raspberry Pi 5 + Active Cooler",
    "adafruit_pca9685": "PCA9685 servo driver",
    "adafruit_lsm6dsox": "LSM6DSOX IMU",
    "adafruit_ina260": "INA260 power monitor",
    "pololu_d36v50f5": "Pololu D36V50F5 5 V regulator",
    "pololu_power_switch_hp": "Pololu #2813 pushbutton switch",
    "fuse_holder_ato": "ATO fuse holder",
    "hobbywing_ubec_10a": "Hobbywing UBEC-10A",
    "lipo_2s_5000_gensace": "LiPo 2S 5000 mAh",
    "seeed_xiao_esp32s3": "Seeed XIAO ESP32-S3",
    "wago_221_415": "WAGO 221-415",
    "waveshare_lcd_2inch": 'Waveshare 2" LCD (ST7789)',
    "rpi_camera_module_3_wide": "Camera Module 3 Wide",
    "rplidar_c1": "RPLIDAR C1",
    "rplidar_usb_adapter": "RPLIDAR USB adapter",
    "pushbutton_12mm": "12 mm push button",
    "xt60h_female": "XT60H female",
    "cable_tie_mount": "Adhesive cable-tie mount 13 × 13 mm",
}
# Cable runs (strido_cad.wiring_geometry): the cable type of hardware/wiring.yaml
CABLE_TITLES = {
    "spiral_wrap": "Spiral wrap",
    "cable_tie": "Cable tie 2.5 × 100 mm",
}


def title(name: str) -> str:
    if name in PURCHASED_TITLES:
        return PURCHASED_TITLES[name]
    if name in CABLE_TITLES:
        return CABLE_TITLES[name]
    if name in WIRING_TYPES:
        kind = WIRING_TYPES[name]
        gauge = f"{kind['gauge']} " if "gauge" in kind else ""
        return f"Cable: {gauge}{name.replace('_', ' ')}"
    if name in fastener_meshes.CATALOGUE["items"]:
        item = fastener_meshes.spec(name)
        label = FASTENER_TITLES[item["standard"]]
        size = f"{item['thread']} × {item['length']:g}" if item["kind"] in ("screw", "standoff") else item["thread"]
        standard = fastener_meshes.CATALOGUE["standards"][item["standard"]]["title"].split(" ")
        norm = " ".join(standard[:2]) if item["standard"] != "standoff" else "brass"
        return f"{size} {label} ({norm})"
    return name.replace("_", " ").capitalize() + " (printed)"
