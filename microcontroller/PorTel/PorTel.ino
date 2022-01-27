/*
 Interface with PorTel Beacon Board
 Nick Belsten
 First Created: 1-25-2022
 Most Recent Update: 1-25-2022
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
float getPeakLaserP();
float getTemp();
void sendMyPacket();

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
#define A_BITS 14
#define PACKET_SIZE 530

const float PD_R2P = 6.25;

const float PDthresh = 6;

unsigned long LastComm;

bool LaserOn=false;
bool Alert=false;


// GUItool: begin automatically generated code
AudioSynthWaveform       driver;      //xy=201.00000190734863,235.00000381469727
AudioInputAnalog         PDadc;           //xy=225.00000381469727,376.0000057220459
AudioSynthWaveformDc     shiftDC;  //xy=233.00000381469727,428.0000071525574
AudioRecordQueue         driverQueue;         //xy=460.00000762939453,276.00000381469727
AudioOutputAnalog        dac1;           //xy=461,236
AudioMixer4              PDmixer;         //xy=469.00000762939453,394.00000381469727
AudioAnalyzeFFT256       PDfft;       //xy=673.0000095367432,412.0000057220459
AudioAnalyzePeak         PDpeak;          //xy=677.0000095367432,370.0000057220459
AudioRecordQueue         PDqueue;         //xy=689.0000095367432,504.00000762939453
AudioAnalyzeToneDetect   toneDetect;          //xy=692.0000095367432,455.0000057220459
AudioConnection          patchCord1(driver, dac1);
AudioConnection          patchCord2(driver, driverQueue);
AudioConnection          patchCord3(PDadc, 0, PDmixer, 0);
AudioConnection          patchCord4(shiftDC, 0, PDmixer, 1);
AudioConnection          patchCord5(PDmixer, PDpeak);
AudioConnection          patchCord6(PDmixer, PDfft);
AudioConnection          patchCord7(PDmixer, toneDetect);
AudioConnection          patchCord8(PDmixer, PDqueue);
// GUItool: end automatically generated code



static PacketSerial myPacketSerial;
DAC myDAC=DAC(10);

/*************** CODE!!!!!!  *********************/
void setup() {
  Serial.begin(115200);
  myPacketSerial.setPacketHandler(&onPacket);
  myPacketSerial.setStream(&Serial);

  analogReadResolution(A_BITS);

  AudioMemory(150);
  
  PDmixer.gain(0,-1);
  PDmixer.gain(1,1);
  shiftDC.amplitude(1);

  LastComm = millis();
  
  driver.begin(0,WAVEFORM_SINE,MOD_F);
  dac1.analogReference(EXTERNAL);
  
}

void loop() {
  myPacketSerial.update();
}

void onPacket(const byte* buffer, size_t size){
  if(size!=14){
    Serial.print("Bad packet length");
    return;
  }
  processPacket(buffer);
  sendMyPacket();
}

//HERE start control functions
void processPacket(const byte* packet){
  memcpy(&LaserOn,&packet[0],1);
  digitalWrite(TECSHDN_P,packet[1]);
  digitalWrite(TECSHDN_P,packet[2]);
  float temp;
  memcpy(&temp,&packet[3],4);
  short val = (short)((temp/70.0)*(2<<12));
  myDAC.write(val);
  float driveAmplitude, driveOffset;
  memcpy(&driveAmplitude,&packet[7],4);
  memcpy(&driveOffset,&packet[11],4);
  driver.amplitude(driveAmplitude);
  driver.offset(driveOffset);
}


//HERE starts packet making functions

//Get peak laser power as measured by photodiode
float getPeakLaserP(){
  return (PDpeak.read()*PD_R2P);  
}

//Get current laser temperature
float getTemp(){
  return ((float)analogRead(TEMPIN_P))*70.0/(2<<A_BITS);
}

void sendMyPacket(){ 
  //Start filling the audio buffers in prep
  PDqueue.begin();
  driverQueue.begin();
  
  float PDPeak = getPeakLaserP();
  bool laserOverpower = (PDPeak>PDthresh);
  bool laserOvercurrent = digitalRead(V2OVC_P);
  bool pbad2V2 = digitalRead(V2PGD_P);
  bool pbadTEC = digitalRead(TECPGD_P);
  bool commLoss = (LaserOn && (millis()-LastComm)>500);
  byte alertStatus = (laserOverpower<<0) | (laserOvercurrent<<1) | (pbad2V2<<2) | (pbadTEC<<3) | (commLoss<<4);
  Alert = alertStatus;
  float temp = getTemp();
  float TECI = (((float)analogRead(TECI_P))/(2<<A_BITS)-0.5)*5.0;
  float TECV = (((float)analogRead(TECV_P))/(2<<A_BITS)-0.5)*5.0;

  //Wait until we get at least on packet in the buffers
  while(driverQueue.available()<1){delay(1);}
  
  byte mypacket[PACKET_SIZE];
  mypacket[0]=(byte)Alert;
  mypacket[1]=(byte)alertStatus;
  memcpy(&mypacket[2],&temp,4);
  memcpy(&mypacket[6],&TECI,4);
  memcpy(&mypacket[10],&TECV,4);
  memcpy(&mypacket[14],&PDPeak,4);
  memcpy(&mypacket[18],PDqueue.readBuffer(),256);
  memcpy(&mypacket[274],driverQueue.readBuffer(),256);
  
  myPacketSerial.send(mypacket,PACKET_SIZE);
}


%Note: can do byte serialization by defining the struct and defining the union of the struct and byte array
%OR can just cast the pointer to the struct as a pointer to a byte array (and use sizeof)
