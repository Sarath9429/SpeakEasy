# 🚗 Vision Guard- ADAS( Realtime Lane Detection )

<p align="center">
    <a href="#"><img alt="Python" src="https://img.shields.io/badge/Python-3.8%2B-14354C.svg?logo=python&logoColor=white"></a>
    <a href="#"><img alt="OpenCV" src="https://img.shields.io/badge/OpenCV-4.x-5C3EE8.svg?logo=opencv&logoColor=white"></a>
    <a href="#"><img alt="CUDA" src="https://img.shields.io/badge/NVIDIA%20CUDA-11.x-76B900.svg?logo=nvidia&logoColor=white"></a>
    <a href="#"><img alt="ONNX" src="https://img.shields.io/badge/ONNX-Inference-005ced.svg?logo=onnx&logoColor=white"></a>
    <a href="#"><img alt="YOLOv8" src="https://img.shields.io/badge/YOLOv8-Detection-00FFFF.svg?logo=ultralytics&logoColor=white"></a>
</p>

A high-performance **Advanced Driver-Assistance System (ADAS)** software pipeline. This project implements high-speed lane detection, vehicle tracking, and safety analysis using the **ONNX Runtime**. It is designed to provide real-time situational awareness by processing various driving conditions including day, night, and rain.

---

# ➤ Contents
1) [Project Showcase](#Project-Showcase)
2) [ADAS Features Explained](#ADAS-Features)
3) [Dataset](#Dataset)
4) [System Architecture](#System-Architecture)
5) [Workflow Methodology](#Core-Methodology)
6) [Model Zoo & Downloads](#Model-Zoo)
7) [Requirements & Setup](#Requirements)
8) [License](#License)

---

<h1 id="Project-Showcase">📸 Project Showcase</h1>

### 🖼️ System Output (Day / Night / Rain)
| **Daylight Conditions** | **Night Conditions** |
| :---: | :---: |
| ![Day Output](demo/dayop.jpeg) | ![Night Output](demo/nightop.jpeg) |
| *Clear lane visibility and object tracking* | *Robust detection in low-light environments* |

| **Rainy / Wet Conditions** | **Bird's Eye View (BEV)** |
| :---: | :---: |
| ![Rainy Output](demo/rainop.jpeg) | ![BEV Panel](demo/BEV.jpeg) |
| *Handling reflections and reduced visibility* | *Top-down view for precise offset math* |

---

<h1 id="ADAS-Features">🛡️ ADAS Features Explained</h1>

This project implements three critical safety systems through a unified computer vision architecture:

### 1. FCWS (Forward Collision Warning System)
The **FCWS** acts as a digital eye monitoring the space ahead. Using **YOLOv8**, the system detects vehicles (cars, trucks, buses) and classifies them in real-time. By analyzing the bounding box scale and position, it estimates the distance to the vehicle in front. If the distance decreases rapidly, the system alerts the driver via a "WARNING" or "PROMPT" overlay to prevent rear-end collisions.

### 2. LDWS (Lane Departure Warning System)
The **LDWS** is designed to prevent accidents caused by lane drifting. Using the **UFLDv2** model, the system identifies the ego-lane boundaries. It monitors the vehicle's position relative to these lines; if the vehicle’s tire approaches or touches the lane markings without a steering intent, the system triggers a "Departure Warning," visually indicating which side the vehicle is drifting toward.

### 3. LKAS (Lane Keeping Assist System)
**LKAS** provides higher-level guidance by calculating the vehicle's exact trajectory. It transforms the front camera view into a **Bird's Eye View (BEV)** to calculate:
* **Lateral Offset:** The distance (in cm) from the vehicle's center to the lane center.
* **Curvature Tracking:** Identifying if the road is curving (Straight, Easy Left/Right, or Hard Left/Right).
This data provides a "Normal" keep-straight guidance to ensure the driver stays centered.

---

<h1 id="Dataset">📊 Dataset</h1>

The models used in this project were tested and validated using a diverse driving dataset to ensure reliability in different environments.

* **Dataset Source:** [Kaggle - Driving Video for Lane Detection (Various Weather)](https://www.kaggle.com/datasets/ashikadnan/driving-video-for-lane-detection-various-weather)
* **Description:** This dataset includes high-quality driving footage captured during daylight, nighttime, and rainy conditions, which was essential for calibrating our LDWS and LKAS logic against glare and reflections.

---

<h1 id="System-Architecture">🏗️ System Architecture</h1>

Below is the high-level block diagram representing the system flow from raw video input to final visual feedback.

<p align="center">
  <img src="demo/block_diagram.jpeg" alt="System Block Diagram" width="900">
</p>



---

<h1 id="Core-Methodology">🧠 Workflow Methodology</h1>

The software operates as a multi-stage computer vision pipeline designed for high-efficiency inference using **ONNX Runtime**.

### Phase 1: Data Ingestion & Preprocessing
Raw video frames are captured and normalized (pixel values scaled 0-1) to match the input tensor requirements of YOLOv8 and UFLDv2. This ensures consistent accuracy across different lighting conditions.

### Phase 2: Parallel AI Inference
Two distinct deep learning models run concurrently to analyze the scene:
* **Vehicle Perception (YOLOv8):** Scans the frame to identify and categorize cars, trucks, and obstacles.
* **Lane Segmentation (UFLDv2):** Treats lane detection as a row-based classification task to rapidly predict the precise location of lane markings (anchors).

### Phase 3: Temporal Tracking & Spatial Mapping
* **Multi-Object Tracking (ByteTrack):** Raw detections are fed into a **Kalman Filter** to predict future positions and maintain persistent IDs for vehicles, even during temporary occlusions.
* **Bird's-Eye View (BEV) Transformation:** An **Inverse Perspective Mapping (IPM)** matrix transforms the skewed camera view into a top-down 2D view. This allows the system to convert pixel distances into real-world metric units (cm) for accurate offset and curvature calculation.

### Phase 4: Safety Logic & Decision Gate
The system calculates the lateral distance from the vehicle center to the detected ego-lane center. If the offset exceeds safety thresholds, specific warnings (LDWS/FCWS) are triggered based on Time-to-Collision (TTC) and lateral drift speed.

### Phase 5: Visualization & Final Output
The system draws dynamic bounding boxes, polygonal lane overlays (colored Green for Safe or Red for Warning), and an ADAS dashboard directly onto the output video stream.

---

<h1 id="Model-Zoo">📂 Model Zoo & Downloads</h1>

All models are used in **.onnx** format. Ensure they are placed in the appropriate project folders.

| Component | Architecture | Model Download Link |
| :--- | :--- | :--- |
| **Lane Model (Day/Night)** | UFLDv2 | [Download CULane ResNet18 ONNX](https://github.com/cfzd/Ultra-Fast-Lane-Detection-v2#model-zoo) |
| **Lane Model (Curves)** | UFLDv2 | [Download CurveLanes ONNX](https://github.com/cfzd/Ultra-Fast-Lane-Detection-v2#model-zoo) |
| **Object Detection** | YOLOv8 | [Download YOLOv8 Large ONNX](https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8l.pt) |

---

<h1 id="Requirements">🛠️ Setup & Installation</h1>

### 1. Requirements
* **Python 3.8+**
* **NVIDIA GPU** (Optional, but highly recommended for ONNX `CUDAExecutionProvider`)
* **ONNX Runtime** (`onnxruntime-gpu` for NVIDIA cards)
### Install all required libraries from the requirements file
```powershell
pip install -r requirements.txt
```

### 2. Environment Setup
```bash
# Create a virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate
```

### 3.1 Download Weights
Download your desired pre-trained models from the links provided in the Model Zoo section. These weights are typically provided in PyTorch format (.pth or .pt).

### 3.2 Convert PyTorch to ONNX
We provide a dedicated script to handle the conversion for the lane detection system.
* Open the file TrafficLaneDetector\convertPytorchToONNX.py.

* Locate the model path variable and pasted the path to your downloaded PyTorch file there.

* Run the conversion script in your terminal:
 ```powershell
 python TrafficLaneDetector\convertPytorchToONNX.py
 ```
### 3.3 Configure main.py
Once the conversion is complete, paste the resulting ONNX model paths into the configuration section of main.py to ensure the program can locate the optimized engines.

### 4 Run Main
```powershell
python main.py
```


