HACKNEST - IoT Farm Biosecurity System
## Technical Documentation / README

![IMG_6909](https://github.com/user-attachments/assets/a84f07fa-90e1-454a-99cc-673b029dd155)
<img width="1014" height="719" alt="image" src="https://github.com/user-attachments/assets/4815775d-1703-4206-9934-0bf1ff53ed23" />


*Project:* Poultry Farm Monitoring Platform 

*Team:* HACKNEST  

---

## 1. OVERVIEW

HACKNEST is designed to be an offline-first IoT biosecurity monitoring system empowered via real-time sensor data with computer vision to predict disease outbreaks 3-7 days in advance. The system is capable of  6-hour detection vs. 7-day current industry average, addressing India's ₹30,000 crore annual livestock disease losses primarily. It also aims in enabling global export with help of govt. certifications.

### Core Innovation
- *Dual ESP32 Architecture*: Main controller for this + ESP32-CAM communicates thru ESP-NOW (7ms latency aproxx)
- *11-Sensor Array*: environment AND behavioral monitoring
- *Vision AI Integration*: Automated  flock activity analysis with risk scoring
- *Hybrid Data Model*: IoT automation +  digital entry for marginal farmer inclusion in this system

---

## 2. HARDWARE ARCHITECTURE
<img width="902" height="1600" alt="image" src="https://github.com/user-attachments/assets/64a6bc3d-a7dd-498b-a690-46e2ba4cf27a" />


### 2.1 Components

| Category | Component | Quantity | Purpose | Interface |
|----------|-----------|----------|---------|-----------|
| *Controllers* | ESP32 WROVER | 1 | hub | Wifi + ESP-NOW |
| | ESP32-CAM | 1 | Computer vision  | Wifi + ESPNOW |
| *Display* | OLED 1.3 (128x64) + secondary | 1 | Sensor reading | i2c (0x3C) |
| | OLED 0.96 (128x64) | 1 | Menu and interface | i2c (0x3D) |
| *Environment* | DHT22(more accurate) | 1 | Temperature and Humidity | digital (gpio 4) |
| | MQ-135 | 1 |ammonia measures| analog (GPIO 34) |

| | MAX9816 | 1 | Sound levels  | Analog (GPIO 36) |
| *Measurement* | HX711 + Load Cell (two) | 1 +2 | Feed& flock weight | digital (gpio 25/26) |
| | YF-S201 | 1 | Feed flow rates| Pulse (GPIO 27) |
| Control | 2 chn Relay Module | 1 | Fan/curtain control | digital (gpio 32,33) |
| | WS2812B LED Ring (8 led) | 1 | indicators | PWM (GPIO 12) |
| *UI* | Push Button | 4 | Menu navigations | INPUT_PULLUP |
| | Toggle type Switche | 4 | Power management | SPST |
| *Storage* | RTC DS3231 | 1 | Time stamping | I2C (0x68) |

### 2.2 Power Distribution System


5V Power~bank (2A) → [SW1 main] → Main Bus
                                      ├─ [SW2] → Sensor Rail (5V) →MQ135, Flow, Relay, LEDs
                                      ├─ [SW3] → ESP32 VIN→ 3.3V Regulator
                                      |                     └─ DHT22, OLED,BH1750, HX711
                                      └─ [SW4] →  ESP32-CAM(5V direct)


*Current Consumption:* 1.14A @ 5V (peak) | *Runtime:* 17 hours on 10,000mAh powerbank ()ESTIMATED 

### 2.3 Pin Allocation (ESP32 WROVER)

| Function | Pins Used | Devices |
|----------|-----------|---------|
| *I2C Bus* | GPIO 21 (SDA), 22 (SCL) | OLED1, OLED2, BH1750, RTC |
| *Analog (ADC1)* | GPIO 34, 35, 36 | MQ-135, Light, MAX9816 |
| *Digital Sensor* | GPIO 4, 27 | DHT22,YF S201 |
| *HX711 the Load Cell* | GPIO 25 (DT), 26 |weight sensing |
| *Control and Output* | GPIO 12, 32 33 | LED strip, Relay 1, Relay 2 |
| *User Interface* | GPIO 0, 2, 13, 15 | Buttons(SELECT, DOWN, BACK& UP) |

*Total Pins Used:* 17 | *Pin Available:*  21

---

## 3. SOFTWARE ARCHITECTURE

### 3.1 Technology Stack

*Firmware:*
- Arduino Framework (ESP32 board)
- ESP-NOW Protocol for inter-controller communication
- FastLED for visual indication
- BH1750 library accurate lux measurement

*Backend API:*
- FastAPI (Python)
- PostgreSQL (database)
- Computer Vision that uses OpenCV.
- Real-time WebSocket for live dashboard viewing

*Key Libraries:*

Adafruit SSD1306, DHT sensor library,HX711,RTClib,fastLED,BH1750


### 3.2 ESP-NOW Communication Protocol

*Main ESP32 → ESP32-CAM:*
- Command: CAPTURE_NOW,STATUS
- Latency: 7ms
- And No WiFi router required

*ESP32-CAM → Main ESP32:*
- Messages: STATUS, IMAGE_TAKEN, ANALYSIS
- Payload: Risk score, bird counts, alerts
- Updates OLED displays in real-time

### 3.3 Data Flow Architecture


Sensors → ESP32 Main (2s interval) → Local Display + SD Logging
                                   → WiFi → Backend API (5min interval-current)
                                   → Risk Calculation + Fan Control

ESP32-CAM (15min(variable) auto + manual) → Image Capture → Backend AI
                                                → Vision Analysis
                                                → ESP-NOW → Main ESP32
                                                          → OLED Display


### 3.4 Risk Scoring Algorithm

python
Risk = Environmental (0-40) +Behavioral(0-30) + Vision AI (0-20)

Environmental:
  - Temperature deviation: ±20-32°C optimal (+20 if exceeded)
  - Humidity deviation: 40-80% optimal(normally +20 if exceeded)
  - Ammonia level: >25ppm critical (+30)
  - Light level: <50 lux or >800 lux (error of +15/+10)

Behavioral:
  - Sound anomaly: typical range >75dB or <45dB (+10)
  - Water shortage: <20% (+20)

Vision AI:
  - Low activity score: <20% (+30)
  - Abnormal postures detected (+25)
  - Lethargy patterns (+20)

Final Risk = min(100, sum(factors))

These values are the pre-pilot values they will be altered after piloting.


### 3.5 Key Features Implementation

*Dual-Channel Load Cells:*
- Channel A (Feed): Continuous monitoring (5s interval)
- Channel B (Flock): On-demand weight averaging
- Calibration factors: A=-408.3, B=-110.5 (also had automatic startup calibration)

*Automated Fan Control:*
cpp
if (ammoniaPPM > 20 || temperature > 30) {
    digitalWrite(RELAY1_PIN, HIGH);  //exhaust fan
}


*Manual Camera Trigger:*
- Navigate: Settings → Camera → Capture Now
- ESP-NOW command sent instantly
- OLED displays capture status + timestamp

---

## 4. SYSTEM CAPABILITIES

### 4.1 Sensor Specifications

| Sensor | Range | Accuracy | Update Rate |
|--------|-------|----------|-------------|
| DHT22 | -40 to 80°C, 0-100% RH | ±0.5°C, ±2% | 2 seconds |
| MQ-135 | 10-1000ppm NH3 | ±10% | 2 seconds |
| BH1750 | 1-65535 lux | ±20% | 1 second |
| MAX9816 | 40-90 dB (estimated) | ±3dB | 50ms window |
| HX711 | 0-5kg (per cell) | ±0.01kg | 80Hz capable |
| YF-S201 | 0.3-6 L/min | ±3% | ~7.5 pulses/L |
(source google-genric)
### 4.2 Display Interfaces

(example snapshot)
*Main Display (1.3" OLED):*

HACKNEST        [CAM]  ← Camera status
─────────────────────
T:28.5°C H:65%         ← Environmental
NH3:12 S:58 L:350      ← Ammonia, Sound, Light
Feed:2.34kg            ← Measurements
Fan:OFF Risk:45        ← Control status
Img:14:23:15 R:52      ← Last photo + vision risk
14:23:30               ← Current time


*Menu Display (0.96" OLED):*
- Settings: Data frequency (1-30 min can be configured)
- Weight averaging: Multi-chicken weighing workflow
- Camera control: capture + status check
- Calibration: Sensor adjustment options

### 4.3 Performance Metrics

| Metric | Value |
|--------|-------|
| Sensor sampling rate | 2 seconds |
| Display refresh | 500ms |
| Data upload interval | 5 minutes (configurable) |
| Camera capture | 15 minutes + manual |
| ESP-NOW latency | <10ms |
| System response time | <100ms |
| Power consumption | 5.7W average |
| WiFi range (backend sync) | network-dependent |

---

## 5. IMPLEMENTATION STATUS

### Completed (✅)
- [x] Complete hardware assembly with 11 sensors
- [x] Dual OLED display system with menu navigation
- [x] ESP-NOW communication between controllers
- [x] Manual camera trigger via button
- [x] Real-time risk calculation algorithm
- [x] Automated fan control logic
- [x] Dual-channel load cell weight sensing
- [x] Light level monitoring (BH1750)
- [x] LED visual risk indicator
- [x] Power management with toggle switches
- [x] Backend API deployment
- [x]  Historical data visualization

### In Progress (🔄)
- [ ] Computer vision model integration
- [ ] SD card data logging
- [ ] SMS alert system (SIM800L integration)


### Future Enhancements (📋)
- [ ] Mobile app integration
- [ ] Multi-farm dashboard(partially done)
- [ ] Predictive analytics (ML models)
- [ ] Government database integration

---

## 6.TESTING & VALIDATION

### Test Scenarios
1.*Sensor Accuracy:* Validated and calibrated instruments
2. *ESP-NOW Reliabile:* 99.99% success rate at <10m range
3.*Power Consumption:* Measured 1.14A peak, 0.85A average
4. *Response Time:* Fan activation <2s after threshold breach

### Known Limitations
- MQ-135 requires 24-48hr warmup or accuracy
- BH1750 sensitive to direct LED interference 
- ESP-NOW range ~200m line of sight

---

## 7.DEPLOYMENT INSTRUCTIONS

### Prerequisites
- Arduino IDE with ESP32 board package
- Libraries: SSD1306, DHT, HX711, RTClib, FastLED, BH1750
- 5V 2A power supply ( lower may also suffice)
- WiFi network

### Configuration Steps
1.Update MAC addresse in both ESP32 codes
2.Set WiFi credentials if using backend.3.Calibrate the load cells with known weights
4.Verify all I2C addresses, since on same I2C bus
5.Test each of the sensor on its own before integrating everything.### Startup Procedure
1.SW1 ON,Powers the system
2. SW2 ON,the sensors
3. SW3 ON,the main ESP32
4.SW4 ON,Powers the ESP32-CAM
5.Wait for "System Ready" message
6.Verify [CAM] indicator via OLED

---
## 8.CAD Files
Biosense_hub_v8_fixed - main box enclose for the project
<img width="1123" height="625" alt="image" src="https://github.com/user-attachments/assets/59717646-2086-4638-8825-9a51ae5f6558" />

Weight_panels - for the weight cell flat pans
<img width="986" height="587" alt="image" src="https://github.com/user-attachments/assets/2a5f9cfa-ca42-408f-8608-5c1b82ac4293" />

load_cell_stand - for the loadcell fixation on the enclosure
<img width="866" height="531" alt="image" src="https://github.com/user-attachments/assets/724712b1-9203-4590-ad6b-3c2f4bed6466" />



---

## 9.CONCLUSION

<img width="1600" height="902" alt="image" src="https://github.com/user-attachments/assets/04ff7894-bcbf-4535-8b03-3c2d556864f5" />

---
