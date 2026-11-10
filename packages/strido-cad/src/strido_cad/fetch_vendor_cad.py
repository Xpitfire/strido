"""Download the official vendor CAD models used by `strido_cad.vendor` and tessellate them.

The files stay in build/vendor_cad/ (git-ignored): their licences do not allow
redistribution in this repository. Each file is pinned by SHA-256; a changed upstream
file fails loudly instead of silently moving a board. Without these files vendor.py
falls back to datasheet envelopes (marked official=False in the CAD manifest).

    make vendor-cad
"""

import hashlib
import io
import sys
import urllib.request
import zipfile
from dataclasses import dataclass

from .paths import BUILD
from .step_cache import load_step_cache

OUT = BUILD / "vendor_cad"
USER_AGENT = "Mozilla/5.0 (Strido CAD fetch)"


@dataclass(frozen=True)
class Model:
    folder: str
    file: str
    url: str
    sha256: str
    zip_member: str | None = None  # file inside a downloaded zip
    referer: str | None = None
    page: str | None = None  # human download page when the file sits behind a form


MODELS = (
    Model(
        "raspberry_pi_5",
        "rpi-5b_no_graphics.step",
        "https://pip-assets.raspberrypi.com/categories/892-raspberry-pi-5/documents/RP-010083-CA-1-rpi-5%203D%20STEP%20-%20No%20Graphics%20small%20file.zip",
        "78164070c1cc7ab854382950d2e85926c6e35432f1e5a146b733397a7c6afb44",
        zip_member="rpi-5b_no_graphics.step",
    ),
    Model(
        "rpi_camera_module_3",
        "Camera_module_3_wide_model_simple.stp",
        "https://pip-assets.raspberrypi.com/categories/1207-design-files/documents/RP-008154-DS-1-camera-module-3-step.zip",
        "b13715ed4fac37ef8357ffddf824cfafe923e55aa849941c5508986cc625c994",
        zip_member="Camera_module_3_wide_model_simple.stp",
    ),
    Model(
        "adafruit_pca9685_815",
        "815 Servo Driver 16 Channel.step",
        "https://raw.githubusercontent.com/adafruit/Adafruit_CAD_Parts/main/815%20Servo%20Driver%2016%20Channel/815%20Servo%20Driver%2016%20Channel.step",
        "71200cd8d6e03f5cd99293314124ca0f2c97ded824d0acda33f065fa140c3f6a",
    ),
    Model(
        "waveshare_2inch_lcd",
        "2inch_LCD_Module_3D_Drawing.stp",
        "https://files.waveshare.com/wiki/2inch_LCD_Module/2inch_LCD_Module_3D_Drawing.zip",
        "ea3b3c8770fb450881320ad85891e011f4a96d9781928b76fef76416b08de2e5",
        zip_member="2inch_LCD_Module_3D_Drawing.stp",
    ),
    Model(
        "rplidar_c1",
        "C1M1_appearance_V2_20230926.3d_model.stp",
        "https://download-en.slamtec.com/api/download/rplidar-c1-model-3d-stp/1?lang=netural",
        "0c5ec21a35b08a1b2c81cf18ba3ecefc72aedadc655b1108f80a2d5affc34568",
        referer="https://www.slamtec.com/",
    ),
    Model(
        "pololu_d36v50f5",
        "d36v50fx-step-down-voltage-regulator.step",
        "https://www.pololu.com/file/0J1733/d36v50fx-step-down-voltage-regulator.step",
        "cdcc9e55ba1de3adfb59c330732e107a6419216c4c6f5f16396c5423757c5155",
    ),
    Model(
        "pololu_pushbutton_switch_hp_2813",
        "big-pushbutton-power-switch-with-reverse-voltage-protection.step",
        "https://www.pololu.com/file/0J1405/big-pushbutton-power-switch-with-reverse-voltage-protection.step",
        "89dceed662b33acde2cf32cef641e73ba3a7763c03d66824b471639f7bcb5de8",
    ),
    Model(
        "xiao_esp32s3",
        "XIAO-ESP32S3 v2.step",
        "https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res/seeed-studio-xiao-esp32s3-3d_model.zip",
        "870ad45c7af5d92324cec4c6ae65fbf86e3b049d5a97ab9ffd9039ebd73455dd",
        zip_member="XIAO-ESP32S3 v2.step",
    ),
    # form-gated (HTTP 403 for scripts): download in a browser and save as build/vendor_cad/littelfuse_fhac0001zxj/OL-FHAC0001ZXJ.step;
    # without it vendor.py uses a 50 x 32 x 16 mm envelope for the fuse holder body
    Model(
        "littelfuse_fhac0001zxj",
        "OL-FHAC0001ZXJ.step",
        "https://cdn1-originals.webdamdb.com/12956_130036194",
        "493cab98170a1b55690a3c6784056ee3835b8ed2a0bd9b0b032ed6d25b6a9e55",
        page="https://info.littelfuse.com/ato-fhac-series-download",
    ),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(model: Model) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    if model.referer:
        headers["Referer"] = model.referer
    with urllib.request.urlopen(urllib.request.Request(model.url, headers=headers), timeout=120) as response:
        payload = response.read()
    if model.zip_member is None:
        return payload
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        matches = [name for name in archive.namelist() if name.endswith(model.zip_member)]
        assert matches, f"{model.url}: {model.zip_member} not in {archive.namelist()}"
        return archive.read(matches[0])


def main() -> int:
    failures = []
    for model in MODELS:
        target = OUT / model.folder / model.file
        if target.is_file() and sha256(target.read_bytes()) == model.sha256:
            status = "present"
        else:
            try:
                data = download(model)
            except OSError as error:
                failures.append(
                    f"{model.folder}: download failed ({error}); save it manually as {target} from {model.page or model.url}"
                )
                continue
            if sha256(data) != model.sha256:
                failures.append(
                    f"{model.folder}: SHA-256 mismatch (vendor updated the file?) - review and update the pin"
                )
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            status = "downloaded"
        solids = len(load_step_cache(target))
        print(f"{model.folder:34s} {status:10s} {solids} solids")
    for failure in failures:
        print("FAIL", failure)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
