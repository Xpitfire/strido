---
layout: home
hero:
  name: Strido
  text: A 12-DoF quadruped you can print, buy, build and train
  tagline: Mini-Pupper-class robot on proven Yertle legs, with a face display, 360° LiDAR, wide camera, Raspberry Pi 5 + ESP32-S3, ROS 2 and a learned controller. Every part, bolt, pin and joint limit comes from a verified CAD model.
  image:
    src: /images/hero_front.png
    alt: Rendering of the assembled Strido
  actions:
    - theme: brand
      text: Start building
      link: /docs/getting-started
    - theme: alt
      text: Shop the parts
      link: /docs/shop
    - theme: alt
      text: Print kit
      link: /docs/print-kit
    - theme: alt
      text: Learn the engineering
      link: /docs/wiki/
    - theme: alt
      text: 3D viewer
      link: /docs/viewer
features:
  - title: Print
    details: Pick complete robots or single parts and download a ready-to-print package — oriented STLs, ready 220 × 220 mm plates and the PrusaSlicer profile every part was verified with.
    link: /docs/print-kit
    linkText: Open the print kit
  - title: Buy
    details: The complete robot as one cart, priced at real shops with shipping. Choose one of four buying plans or change the shop per part; check out per shop, Amazon in one click.
    link: /docs/shop
    linkText: Open the shop
  - title: Assemble
    details: IKEA-style steps generated from the CAD — each part and fastener appears in exactly one parts box; fasteners drawn at 1:1 in the PDF.
    link: /docs/assembly/
    linkText: Assembly manual
  - title: Wire
    details: Power tree, wiring list, pin map and power budget, checked against the firmware pin header and every fuse and wire rating.
    link: /docs/electronics
    linkText: Electronics
  - title: Program, simulate, train
    details: ESP32-S3 firmware with watchdog and e-stop, ROS 2 Jazzy bringup, MuJoCo and Gazebo models from the CAD, PPO training and an NT-X extension.
    link: /docs/software
    linkText: Software
  - title: Learn
    details: A wiki on the engineering behind the robot — servos, LiPo power, buses, sensors, Linux, Docker, ROS 2, kinematics, reinforcement learning, 3D printing and fasteners.
    link: /docs/wiki/
    linkText: Start learning
---

<div class="vp-doc" style="max-width: 1152px; margin: 0 auto; padding: 0 24px 48px;">

## The robot in 3D

<ClientOnly><AssemblyViewer height="520px" /></ClientOnly>

<div class="yx-specs">
  <div><strong>430&nbsp;×&nbsp;188&nbsp;×&nbsp;264&nbsp;mm</strong><span>standing, LiDAR on top</span></div>
  <div><strong>≈ 3.0 kg</strong><span>CAD mass incl. 2S 5000 mAh battery</span></div>
  <div><strong>12 × 35 kg·cm</strong><span>SPT5435LV servos, linkage-driven knees</span></div>
  <div><strong>Pi&nbsp;5 + ESP32&#8209;S3</strong><span>ROS 2 Jazzy · 200 Hz motion loop</span></div>
  <div><strong>360° LiDAR · camera · LCD</strong><span>RPLIDAR C1, Camera Module 3 Wide, 2" face</span></div>
  <div><strong>0 collisions</strong><span>interference, clearance, fits: see <a href="/docs/verification">Verification</a></span></div>
</div>

## What it takes

<div class="yx-journey">
  <a href="/docs/print-kit"><span>1 · Print</span><strong>≈ 1.0 kg PETG</strong><small>34 parts, 67 pieces, about 100 h on a 220 × 220 mm printer</small></a>
  <a href="/docs/shop"><span>2 · Buy</span><strong>from €979</strong><small>62 items from 8 shops incl. shipping to Austria (plan A)</small></a>
  <a href="/docs/assembly/"><span>3 · Assemble</span><strong>22 steps</strong><small>hex keys, a soldering iron and a crimp tool</small></a>
  <a href="/docs/software"><span>4 · Run</span><strong>flash · calibrate · walk</strong><small>firmware, ROS 2 in Docker, teleop or the learned policy</small></a>
</div>

</div>
