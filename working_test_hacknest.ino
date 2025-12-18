/*
 * ════════════════════════════════════════════════════════════
 * HACKNEST v7.2: Automation System (Active HIGH / Transistor)
 * ════════════════════════════════════════════════════════════
 * - FIX: Logic set to Active HIGH (Matches NPN Transistor Driver)
 * > HIGH (3.3V) = ON
 * > LOW (0V)    = OFF
 */

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>
#include <BH1750.h>
#include <Adafruit_NeoPixel.h>
#include <HX711.h>

// ═════════════ PIN DEFINITIONS ═════════════
#define I2C_SDA 21
#define I2C_SCL 22

// Sensors
#define DHT_PIN 4
#define MQ135_PIN 34
#define MIC_PIN 35
#define LED_PIN 18
#define NUM_LEDS 8

// Flow Sensor
#define FLOW_PIN 27 

// Load Cells
#define HX711_DT  25
#define HX711_SCK 26

// RELAYS
#define RELAY1_PIN 32  // EXHAUST
#define RELAY2_PIN 33  // CURTAIN

// --- RELAY LOGIC SETTINGS (UPDATED FOR TRANSISTOR) ---
#define RELAY_ON  HIGH  // HIGH signal turns NPN ON -> Relay ON
#define RELAY_OFF LOW   // LOW signal turns NPN OFF -> Relay OFF

// Buttons
#define BTN_UP 14        
#define BTN_DOWN 0       
#define BTN_SELECT 13     
#define BTN_BACK 15      

// ═════════════ CALIBRATION ═════════════
const float FACTOR_A = 408.3;  
const float FACTOR_B = 110.7;  
long zeroA = 0;
long zeroB = 0;

// ═════════════ HARDWARE OBJECTS ═════════════
Adafruit_SH1106G mainDisplay(128, 64, &Wire, -1);
Adafruit_SSD1306 menuDisplay(128, 64, &Wire, -1);
DHT dht(DHT_PIN, DHT22);
BH1750 lightMeter;
Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);
HX711 scale;

// ═════════════ VARIABLES ═════════════
// Sensor Data
float feedWeightG = 0.0;
float flockWeightG = 0.0;
float flowRate = 0.0; 
int gasRaw = 0;
float lux = 0;

// Relay State
bool relay1State = false;
bool relay2State = false;

// Timing
unsigned long lastScaleBTime = 0;
unsigned long lastDisplayTime = 0;
unsigned long lastFlowTime = 0;

// Menu Logic
enum MenuState { SCREEN_LIVE_DATA, MENU_ROOT, MENU_WEIGHING, MENU_SETTINGS, MENU_INFO };
MenuState currentScreen = SCREEN_LIVE_DATA;
int cursorIndex = 0; 
int numChickens = 0;
float avgChickenWeight = 0;
int dataFreq = 5; 

// Button Debounce
#define DEBOUNCE_DELAY 50 
unsigned long lastDebounce[4] = {0};
bool lastButtonState[4] = {HIGH, HIGH, HIGH, HIGH};
bool buttonPressed[4] = {false};
bool uiNeedsUpdate = true; 

// Flow Interrupt
volatile int flowPulseCount = 0;

// ═════════════ FORWARD DECLARATIONS ═════════════
void updateDisplays();
void handleButton(int btn);
void tareScales();
void controlRelays();

// ═════════════ INTERRUPT ═════════════
void IRAM_ATTR flowPulseCounter() {
  flowPulseCount++;
}

// ═════════════ SETUP ═════════════
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n\n=== HACKNEST v7.2: Active HIGH Logic ===");

  Wire.begin(I2C_SDA, I2C_SCL);

  // Init Displays
  mainDisplay.begin(0x3C, true); mainDisplay.display(); mainDisplay.clearDisplay();
  menuDisplay.begin(SSD1306_SWITCHCAPVCC, 0x3D); menuDisplay.display(); menuDisplay.clearDisplay();

  // Init Buttons
  pinMode(BTN_UP, INPUT_PULLUP);
  pinMode(BTN_DOWN, INPUT_PULLUP);
  pinMode(BTN_SELECT, INPUT_PULLUP);
  pinMode(BTN_BACK, INPUT_PULLUP);

  // --- INIT RELAYS (Start OFF) ---
  pinMode(RELAY1_PIN, OUTPUT); 
  digitalWrite(RELAY1_PIN, RELAY_OFF); // Write LOW to start OFF
  
  pinMode(RELAY2_PIN, OUTPUT); 
  digitalWrite(RELAY2_PIN, RELAY_OFF); // Write LOW to start OFF

  // Init Sensors
  dht.begin();
  lightMeter.begin();
  pinMode(MQ135_PIN, INPUT);
  pinMode(MIC_PIN, INPUT);
  strip.begin(); strip.setBrightness(50); strip.show();

  // Init Flow
  pinMode(FLOW_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(FLOW_PIN), flowPulseCounter, FALLING);

  // Init Scales
  Serial.print("Init Scales... ");
  scale.begin(HX711_DT, HX711_SCK);
  unsigned long timeout = millis();
  while (!scale.is_ready()) {
    if (millis() - timeout > 2000) { Serial.print("."); timeout = millis(); }
  }
  Serial.println(" OK!");

  tareScales(); 
}

void tareScales() {
  Serial.println("[SYSTEM] Taring Scales...");
  menuDisplay.clearDisplay();
  menuDisplay.setCursor(10, 25); menuDisplay.setTextSize(2);
  menuDisplay.println("TARING...");
  menuDisplay.display();

  scale.set_gain(128); delay(50); scale.tare(); zeroA = scale.get_offset();
  scale.set_gain(32); delay(50); scale.tare(); zeroB = scale.get_offset();
  scale.set_gain(128); scale.set_offset(zeroA); scale.set_scale(FACTOR_A);
  
  Serial.println("[SYSTEM] Tare Complete.");
  uiNeedsUpdate = true;
}

void loop() {
  unsigned long now = millis();
  
  // 1. Check Buttons
  readButtons();

  // 2. Read Scales
  if (scale.is_ready()) {
    scale.set_gain(128); scale.set_offset(zeroA); scale.set_scale(FACTOR_A);
    float newWeight = scale.get_units(1);
    if (abs(newWeight - feedWeightG) > 1.0) feedWeightG = newWeight;

    if (currentScreen == MENU_WEIGHING || (now - lastScaleBTime > 5000)) {
      lastScaleBTime = now;
      scale.set_gain(32); scale.set_offset(zeroB); scale.set_scale(FACTOR_B);
      flockWeightG = scale.get_units(1);
    }
  }

  // 3. Read Flow
  if (now - lastFlowTime > 1000) {
    flowRate = (flowPulseCount / 7.5); 
    flowPulseCount = 0; 
    lastFlowTime = now;
  }

  // 4. Read Analog/I2C Sensors
  gasRaw = analogRead(MQ135_PIN);
  lux = lightMeter.readLightLevel();

  // 5. Run Automation Logic
  controlRelays();

  // 6. Update Displays
  if (uiNeedsUpdate || (now - lastDisplayTime > 250)) {
    updateDisplays();
    lastDisplayTime = now;
    uiNeedsUpdate = false; 
  }
  
  // 7. LED Logic
  if (feedWeightG < 50.0) {
    for(int i=0; i<NUM_LEDS; i++) strip.setPixelColor(i, strip.Color(255, 0, 0)); 
  } else {
    for(int i=0; i<NUM_LEDS; i++) strip.setPixelColor(i, strip.Color(0, 255, 0)); 
  }
  strip.show();
  
  delay(10); 
}

// ═════════════ AUTOMATION LOGIC (ACTIVE HIGH) ═════════════
void controlRelays() {
  // RELAY 1: EXHAUST (Gas Logic)
  // If Gas > 4090 -> ON
  if (gasRaw > 4090) {
    if (!relay1State) {
      digitalWrite(RELAY1_PIN, RELAY_ON); // HIGH
      relay1State = true;
      Serial.println("[AUTO] Gas High! Exhaust ON");
    }
  } else {
    if (relay1State) {
      digitalWrite(RELAY1_PIN, RELAY_OFF); // LOW
      relay1State = false;
      Serial.println("[AUTO] Gas Normal. Exhaust OFF");
    }
  }

  // RELAY 2: CURTAIN (Light Logic)
  // If Lux < 20 -> ON
  if (lux < 20) {
    if (!relay2State) {
      digitalWrite(RELAY2_PIN, RELAY_ON); // HIGH
      relay2State = true;
      Serial.println("[AUTO] Dark! Curtain ON");
    }
  } else {
    if (relay2State) {
      digitalWrite(RELAY2_PIN, RELAY_OFF); // LOW
      relay2State = false;
      Serial.println("[AUTO] Bright. Curtain OFF");
    }
  }
}

// ═════════════ BUTTON INPUT SYSTEM ═════════════
void readButtons() {
  int pins[4] = {BTN_UP, BTN_DOWN, BTN_SELECT, BTN_BACK};
  for (int i = 0; i < 4; i++) {
    int reading = digitalRead(pins[i]);
    if (reading != lastButtonState[i]) lastDebounce[i] = millis();
    if ((millis() - lastDebounce[i]) > DEBOUNCE_DELAY) {
      if (reading == LOW && !buttonPressed[i]) {
        buttonPressed[i] = true;
        handleButton(i);
        uiNeedsUpdate = true;
      } else if (reading == HIGH) {
        buttonPressed[i] = false;
      }
    }
    lastButtonState[i] = reading;
  }
}

void handleButton(int btn) {
  Serial.print("[INPUT] "); Serial.println(btn);
  switch (currentScreen) {
    case SCREEN_LIVE_DATA:
      if (btn == 2) { currentScreen = MENU_ROOT; cursorIndex = 0; }
      break;
    case MENU_ROOT:
      if (btn == 0) { cursorIndex--; if (cursorIndex < 0) cursorIndex = 3; } 
      if (btn == 1) { cursorIndex++; if (cursorIndex > 3) cursorIndex = 0; } 
      if (btn == 3) { currentScreen = SCREEN_LIVE_DATA; } 
      if (btn == 2) { 
        if (cursorIndex == 0) currentScreen = MENU_WEIGHING;
        if (cursorIndex == 1) { tareScales(); currentScreen = SCREEN_LIVE_DATA; }
        if (cursorIndex == 2) currentScreen = MENU_SETTINGS;
        if (cursorIndex == 3) currentScreen = MENU_INFO;
      }
      break;
    case MENU_WEIGHING:
      if (btn == 2) { 
        if (flockWeightG > 5.0) {
          numChickens++;
          if (numChickens == 1) avgChickenWeight = flockWeightG;
          else avgChickenWeight = ((avgChickenWeight * (numChickens-1)) + flockWeightG) / numChickens;
          Serial.println("Bird Added");
        }
      }
      if (btn == 3) { currentScreen = MENU_ROOT; }
      break;
    case MENU_SETTINGS:
      if (btn == 0) dataFreq++; 
      if (btn == 1) dataFreq--; 
      if (dataFreq < 1) dataFreq = 1;
      if (btn == 3) currentScreen = MENU_ROOT; 
      if (btn == 2) currentScreen = MENU_ROOT;
      break;
    case MENU_INFO:
      if (btn == 3) currentScreen = MENU_ROOT; 
      break;
  }
}

// ═════════════ DISPLAY RENDERING ═════════════
void updateDisplays() {
  // MAIN DISPLAY (1.3")
  mainDisplay.clearDisplay();
  mainDisplay.setTextSize(1);
  mainDisplay.setTextColor(SH110X_WHITE);
  
  if (currentScreen == MENU_WEIGHING) {
    mainDisplay.setCursor(0,0); mainDisplay.println("--- WEIGH MODE ---");
    mainDisplay.setTextSize(2);
    mainDisplay.setCursor(0,20); mainDisplay.print(flockWeightG, 1); mainDisplay.println("g");
    mainDisplay.setTextSize(1);
    mainDisplay.setCursor(0,50); mainDisplay.println("Place bird on Scale B");
  } else {
    mainDisplay.setCursor(0, 0); mainDisplay.println("--- SENSORS ---");
    mainDisplay.setCursor(0, 15);
    mainDisplay.print("Feed: "); mainDisplay.print(feedWeightG, 1); mainDisplay.println(" g");
    mainDisplay.print("Bird: "); mainDisplay.print(flockWeightG, 1); mainDisplay.println(" g");
    
    // Show Relays status
    mainDisplay.setCursor(0, 35);
    mainDisplay.print("R1:"); mainDisplay.print(relay1State ? "ON " : "OFF");
    mainDisplay.print(" R2:"); mainDisplay.println(relay2State ? "ON " : "OFF");
    
    mainDisplay.print("Gas: "); mainDisplay.print(gasRaw);
    mainDisplay.print(" Lx: "); mainDisplay.println((int)lux);
  }
  mainDisplay.display();

  // MENU DISPLAY (0.96")
  menuDisplay.clearDisplay();
  menuDisplay.setTextSize(1);
  menuDisplay.setTextColor(SSD1306_WHITE);
  menuDisplay.setCursor(0,0);

  if (currentScreen == SCREEN_LIVE_DATA) {
    menuDisplay.setTextSize(2);
    menuDisplay.setCursor(15, 10); menuDisplay.println("SYSTEM");
    menuDisplay.setCursor(20, 30); menuDisplay.println("READY");
    menuDisplay.setTextSize(1);
    menuDisplay.setCursor(0, 55); menuDisplay.println("Press SELECT for Menu");
  } 
  else if (currentScreen == MENU_ROOT) {
    menuDisplay.println("MAIN MENU");
    menuDisplay.drawLine(0, 10, 128, 10, SSD1306_WHITE);
    menuDisplay.setCursor(0, 15);
    if(cursorIndex == 0) menuDisplay.print("> "); else menuDisplay.print("  "); menuDisplay.println("Weighing Mode");
    if(cursorIndex == 1) menuDisplay.print("> "); else menuDisplay.print("  "); menuDisplay.println("Tare Scales");
    if(cursorIndex == 2) menuDisplay.print("> "); else menuDisplay.print("  "); menuDisplay.println("Settings");
    if(cursorIndex == 3) menuDisplay.print("> "); else menuDisplay.print("  "); menuDisplay.println("System Info");
  }
  else if (currentScreen == MENU_WEIGHING) {
    menuDisplay.println("SESSION STATS");
    menuDisplay.drawLine(0, 10, 128, 10, SSD1306_WHITE);
    menuDisplay.setCursor(0, 20);
    menuDisplay.print("Count: "); menuDisplay.println(numChickens);
    menuDisplay.print("Avg:   "); menuDisplay.print(avgChickenWeight, 1); menuDisplay.println("g");
    menuDisplay.setCursor(0, 50); menuDisplay.println("SEL: Add | BACK: Exit");
  }
  else if (currentScreen == MENU_SETTINGS) {
    menuDisplay.println("SETTINGS");
    menuDisplay.print("Data Freq: "); menuDisplay.print(dataFreq); menuDisplay.println("m");
    menuDisplay.println("(UP/DN to change)");
    menuDisplay.println("(SEL to Save)");
  }
  else if (currentScreen == MENU_INFO) {
    menuDisplay.println("INFO");
    menuDisplay.print("Uptime: "); menuDisplay.print(millis()/60000); menuDisplay.println("m");
    menuDisplay.println("Ver: 7.2 Auto");
  }
  menuDisplay.display();
}