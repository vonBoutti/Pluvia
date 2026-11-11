/*
 * Pluvia - Estação de monitoramento de córrego (ESP32)
 * Simulável no Wokwi: abra iot/estacao_pluvia/ no wokwi.com (diagram.json incluso).
 *
 * Sensores:
 *   1. HC-SR04 (ultrassônico)  -> nível da água no córrego (sensor preso na ponte)
 *   2. Pluviômetro de báscula   -> botão: cada "báscula" = 0,2 mm de chuva
 *      (no Wokwi, clique no botão verde para simular chuva)
 *   3. DHT22                   -> temperatura e umidade do ar
 * Atuadores:
 *   LED verde/amarelo/vermelho e buzzer -> alarme LOCAL, funciona mesmo sem internet
 *
 * A cada ciclo a estação envia JSON para POST /api/leituras com cabeçalho X-API-Key.
 * Sem Wi-Fi, guarda até 24 leituras em buffer e reenvia quando a conexão volta.
 */
#include <WiFi.h>
#include <HTTPClient.h>
#include "DHTesp.h"

// ---------- configuração ----------
const char* WIFI_SSID   = "Wokwi-GUEST";
const char* WIFI_SENHA  = "";
const char* API_URL     = "http://SEU_IP:8000/api/leituras";  // troque pelo IP da máquina com a API
const char* API_KEY     = "dev-device-key-troque";           // igual a DEVICE_API_KEY do .env
const char* ESTACAO     = "AC-01";                            // Jardim Helena (Jardim Pantanal)
const float ALTURA_SENSOR_CM = 400.0;  // distância do sensor ao fundo do córrego
const float COTA_CM          = 180.0;  // nível de transbordamento deste ponto
const unsigned long CICLO_MS = 10000;  // demo: 10 s representam 1 h de leitura consolidada

// ---------- pinos ----------
const int PIN_TRIG = 5, PIN_ECHO = 18, PIN_PLUVIO = 4, PIN_DHT = 15;
const int LED_VERDE = 25, LED_AMARELO = 26, LED_VERMELHO = 27, PIN_BUZZER = 14;

DHTesp dht;
volatile unsigned int basculas = 0;
volatile unsigned long ultimoPulso = 0;
unsigned long ultimoEnvio = 0;

struct LeituraBuf { float chuva, nivel, temp; };
LeituraBuf buffer[24];
int nBuffer = 0;

void IRAM_ATTR contarBascula() {
  unsigned long agora = millis();
  if (agora - ultimoPulso > 150) {  // debounce
    basculas++;
    ultimoPulso = agora;
  }
}

float medirNivelCm() {
  // mediana de 5 medições para filtrar ruído do ultrassônico
  float v[5];
  for (int i = 0; i < 5; i++) {
    digitalWrite(PIN_TRIG, LOW);  delayMicroseconds(2);
    digitalWrite(PIN_TRIG, HIGH); delayMicroseconds(10);
    digitalWrite(PIN_TRIG, LOW);
    long dur = pulseIn(PIN_ECHO, HIGH, 30000);
    v[i] = dur * 0.0343 / 2.0;  // distância em cm
    delay(20);
  }
  for (int i = 0; i < 4; i++) for (int j = i + 1; j < 5; j++) if (v[j] < v[i]) { float t = v[i]; v[i] = v[j]; v[j] = t; }
  float nivel = ALTURA_SENSOR_CM - v[2];
  return nivel < 0 ? 0 : nivel;
}

void alarmeLocal(float nivel) {
  float pct = nivel / COTA_CM;
  digitalWrite(LED_VERDE, pct < 0.6);
  digitalWrite(LED_AMARELO, pct >= 0.6 && pct < 0.8);
  digitalWrite(LED_VERMELHO, pct >= 0.8);
  if (pct >= 0.8) tone(PIN_BUZZER, 2000, 400); else noTone(PIN_BUZZER);
}

bool enviar(const LeituraBuf& l) {
  if (WiFi.status() != WL_CONNECTED) return false;
  HTTPClient http;
  http.begin(API_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", API_KEY);
  String json = String("{\"estacao\":\"") + ESTACAO + "\",\"chuva_mm\":" + String(l.chuva, 1) +
                ",\"nivel_cm\":" + String(l.nivel, 1) + ",\"temp_c\":" + String(l.temp, 1) + "}";
  int code = http.POST(json);
  Serial.printf("POST %s -> %d\n", json.c_str(), code);
  if (code == 201) Serial.println(http.getString());
  http.end();
  return code == 201;
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_TRIG, OUTPUT); pinMode(PIN_ECHO, INPUT);
  pinMode(PIN_PLUVIO, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_PLUVIO), contarBascula, FALLING);
  pinMode(LED_VERDE, OUTPUT); pinMode(LED_AMARELO, OUTPUT); pinMode(LED_VERMELHO, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  dht.setup(PIN_DHT, DHTesp::DHT22);
  WiFi.begin(WIFI_SSID, WIFI_SENHA);
  Serial.print("Conectando Wi-Fi");
  for (int i = 0; i < 20 && WiFi.status() != WL_CONNECTED; i++) { delay(250); Serial.print("."); }
  Serial.println(WiFi.status() == WL_CONNECTED ? " ok" : " sem rede (modo offline)");
}

void loop() {
  float nivel = medirNivelCm();
  alarmeLocal(nivel);  // reage em tempo real, independente da nuvem

  if (millis() - ultimoEnvio >= CICLO_MS) {
    ultimoEnvio = millis();
    noInterrupts(); unsigned int b = basculas; basculas = 0; interrupts();
    TempAndHumidity th = dht.getTempAndHumidity();
    LeituraBuf l = { b * 0.2f, nivel, isnan(th.temperature) ? 0 : th.temperature };
    Serial.printf("[%s] chuva=%.1fmm nivel=%.1fcm (%.0f%% da cota) temp=%.1fC\n",
                  ESTACAO, l.chuva, l.nivel, 100 * l.nivel / COTA_CM, l.temp);

    // reenvia o que ficou no buffer, depois a leitura atual
    while (nBuffer > 0 && enviar(buffer[0])) {
      for (int i = 1; i < nBuffer; i++) buffer[i - 1] = buffer[i];
      nBuffer--;
    }
    if (!enviar(l)) {
      if (nBuffer == 24) { for (int i = 1; i < 24; i++) buffer[i - 1] = buffer[i]; nBuffer--; }
      buffer[nBuffer++] = l;
      Serial.printf("sem conexão: leitura guardada (%d no buffer)\n", nBuffer);
    }
  }
  delay(200);
}
