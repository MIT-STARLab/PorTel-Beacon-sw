/*
 Interface with PorTel Beacon Board
 Nick Belsten
 First Created: 1-25-2022
 Most Recent Update: 2-3-2022
*/
#include <PacketSerial.h>
#include <Audio.h>
#include <Wire.h>
#include <SPI.h>
#include <SerialFlash.h>
#include "dac121.h"


/*************** Prototypes  *********************/
void onPacket(const byte* , size_t);
void processPacket(const byte*);
void fillPDPacket();
void stopLaser();
void getPDSample();
float getPeakLaserP();
float getTemp();
void sendMyPacket();
void watchdog();

/*************** Constants *********************/
//Pin Definitions
#define V2PGD_P 23
#define TECPGD_P 22
#define PD_P 21
#define TEMPIN_P 20
#define TECI_P 19
#define TECV_P 18
#define V2OVC_P 17
#define TECSHDN_P 16

//Constants definitions
#define MOD_F 3000
#define A_BITS 16
#define PACKET_LENGTH 128 //Audio packet

const float PD_R2P = 6.25;
const float DR_R2I = 5.92;
const float PDthresh = 6;
const float TempThresh = 60.0;
const float EPSILON = 0.0001; //Very small amplitude to keep stream running

bool CommLoss=false;

bool LaserOn=false;
bool TECOn=false;
bool Alert=false;

struct SEND_PACKET_STRUCT{
  bool Alert;
  bool LaserOn;
  bool TECOn;
  byte laserStatus;
  byte powerStatus;
  bool commLoss;
  byte dummy1;
  byte dummy2;
  float temp;
  float TECI;
  float TECV;
  float LaserIAVG;
  float LaserIModulation;
  float PDPeak;
  int16_t PDQueue[PACKET_LENGTH];
  int16_t driverQueue[PACKET_LENGTH];
};

struct RECV_PACKET_STRUCT{
  bool laserOn;
  bool TECOn;
  bool dummy1;
  bool dummy2;
  float tempSet;
  float driveAmplitude;
  float driveOffset;
};

// GUItool: begin automatically generated code
AudioSynthWaveform       driver;         //xy=182.00000762939453,208.00000762939453
AudioRecordQueue         driverQueue;    //xy=441.00000762939453,249.00000762939453
AudioOutputAnalog        dac1;           //xy=442.00000762939453,209.00000762939453
AudioConnection          patchCord1(driver, dac1);
AudioConnection          patchCord2(driver, driverQueue);
// GUItool: end automatically generated code

int16_t MyPDQueue[PACKET_LENGTH];

static PacketSerial myPacketSerial;

DAC myDAC=DAC(10);

IntervalTimer AudioTimer;
IntervalTimer WatchdogTimer;
bool Steak;
int AudioPacketFill;

float DriveAmplitude;
float DriveOffset;


/*************** CODE!!!!!!  *********************/
void setup() {
  Serial.begin(115200);
  myPacketSerial.setPacketHandler(&onPacket);
  myPacketSerial.setStream(&Serial);

  analogReadResolution(A_BITS);

  AudioMemory(100);

  driver.frequency(MOD_F);
  driver.amplitude(EPSILON);
  driver.offset(-1);
  driver.begin(WAVEFORM_SINE);

  WatchdogTimer.begin(watchdog,1000000);
  WatchdogTimer.priority(10); //Higher than audio filling
  
  dac1.analogReference(EXTERNAL);

  pinMode(V2PGD_P,INPUT);
  pinMode(TECPGD_P,INPUT);
  pinMode(TEMPIN_P,INPUT);
  pinMode(PD_P,INPUT);
  pinMode(TECI_P,INPUT);
  pinMode(TECV_P,INPUT);
  pinMode(TECPGD_P,INPUT);
  pinMode(V2OVC_P,INPUT);
  pinMode(TECSHDN_P,OUTPUT);
  digitalWrite(TECSHDN_P,LOW);
}

void loop() {
  myPacketSerial.update();
}

void watchdog(){
  if(LaserOn & !Steak){
    CommLoss=true;
    stopLaser();
  }
  Steak=false; //Dog ate steak, now needs a new one
  return;
}

void onPacket(const byte* buffer, size_t size){
  if(size!=sizeof(RECV_PACKET_STRUCT)){
    Serial.print("Bad packet length");
    return;
  }else{
    processPacket((RECV_PACKET_STRUCT*)buffer);
  }
  sendMyPacket();
  Steak=true; //Watchdog gets new steak
}

//HERE start control functions
void processPacket(RECV_PACKET_STRUCT* myRecv){
  LaserOn=myRecv->laserOn;
  if(!LaserOn){stopLaser();}
  
  TECOn=myRecv->TECOn;
  //Serial.print(TECOn);
  digitalWrite(TECSHDN_P,TECOn); //Write high keeps it out of shutdown (inverse logic)

  short shortval = (short)((myRecv->tempSet/70.0)*(1<<12)*2.5/3.3);
  myDAC.write(shortval);
  //Serial.print(shortval);
  DriveAmplitude=myRecv->driveAmplitude;
  DriveOffset=myRecv->driveOffset;

  if(LaserOn){
      if(abs(DriveAmplitude)<EPSILON){driver.amplitude(EPSILON);}
      else{driver.amplitude(DriveAmplitude);}
      driver.offset((DriveOffset*2)-1);
  }
}

//Turns off the laser output
void stopLaser(){
  driver.amplitude(EPSILON);
  driver.offset(-1);
}

//HERE starts packet making functions

void getPDSample(){
  if(AudioPacketFill<PACKET_LENGTH){
    MyPDQueue[AudioPacketFill]=(analogRead(PD_P)*-1)+(1<<A_BITS);
    AudioPacketFill++;
  }else{
    AudioTimer.end();
  }
  return;
}

void fillPDPacket(){
  AudioPacketFill=0;
  AudioTimer.begin(getPDSample,2.267);
  while (AudioPacketFill<PACKET_LENGTH){delay(1);}
  return;
}

//Get peak laser power as measured by photodiode
float getPeakLaserP(){
  int maxVal=0;
   for (int i = 0; i < PACKET_LENGTH; i++) {
      if (MyPDQueue[i] > maxVal) {
         maxVal = MyPDQueue[i];
      }
   }
   return maxVal;
}

//Get current laser temperature
float getTemp(){
  return float(analogRead(TEMPIN_P))*70.0/(float(1<<A_BITS));
}

void sendMyPacket(){ 
  //Start filling the audio buffers in prep
  driverQueue.begin();
  //Wait until we get at least on packet in the buffers

  SEND_PACKET_STRUCT mySend;
  fillPDPacket();

  mySend.temp = getTemp();
  
  mySend.PDPeak = getPeakLaserP();
  bool laserOvertemp = (mySend.temp>TempThresh);
  bool laserOverpower = (mySend.PDPeak>PDthresh);
  bool laserOvercurrent = digitalRead(V2OVC_P);
  bool pbad2V2 = !digitalRead(V2PGD_P);
  bool pbadTEC = !digitalRead(TECPGD_P);
  mySend.laserStatus = (laserOvertemp<<2) | (laserOvercurrent<<1) | (laserOverpower<<0);
  mySend.powerStatus =  (pbadTEC<<1) | (pbad2V2<<0);
  mySend.commLoss = CommLoss;
  mySend.Alert = (mySend.laserStatus || mySend.powerStatus || mySend.commLoss);
  
  mySend.TECI = (float(analogRead(TECI_P)))/(float(1<<A_BITS)-0.5)*5.0;
  mySend.TECV = (float(analogRead(TECV_P)))/(float(1<<A_BITS)-0.5)*5.0;
  mySend.LaserIAVG = DriveOffset*DR_R2I;
  mySend.LaserIModulation = DriveAmplitude*DR_R2I;
  mySend.LaserOn=LaserOn;
  mySend.TECOn=TECOn;

  if(LaserOn){
    while(driverQueue.available()<1){delay(1);}
    //Serial.println(driverQueue.available());
    memcpy(mySend.driverQueue,driverQueue.readBuffer(),sizeof(mySend.driverQueue));
  }else{
    for(int i=0;i<PACKET_LENGTH;i++){
      mySend.driverQueue[i]=0;
    }
  }
  
  memcpy(mySend.PDQueue,MyPDQueue,sizeof(mySend.PDQueue));
  //memcpy(mySend.driverQueue,driverQueue.readBuffer(),sizeof(mySend.driverQueue));

  myPacketSerial.send((byte*)(&mySend),sizeof(SEND_PACKET_STRUCT));
  //delay(500);
}
