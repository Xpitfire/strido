from setuptools import setup

PACKAGE = "strido_control"

setup(
    name=PACKAGE,
    version="0.1.0",
    packages=[PACKAGE],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{PACKAGE}"]),
        (f"share/{PACKAGE}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Strido maintainers",
    maintainer_email="noreply@example.com",
    description="Strido gait node and MCU bridge",
    license="MIT",
    entry_points={
        "console_scripts": [
            "gait_node = strido_control.gait_node:main",
            "mcu_bridge = strido_control.mcu_bridge:main",
            "policy_node = strido_control.policy_node:main",
            "walk_smoke = strido_control.walk_smoke:main",
        ],
    },
)
