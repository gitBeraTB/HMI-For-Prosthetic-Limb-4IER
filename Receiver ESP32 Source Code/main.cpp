#include <Arduino.h>
#include <esp_now.h>
#include <WiFi.h>

// Verici ile aynı olması için "timestamp" ekledik
typedef struct struct_message {
    int gestureID;      
    float confidence;   
    int batteryLevel;
    uint32_t timestamp; // Gidiş-dönüş süresi (Ping) için
} struct_message;

struct_message incomingData;

// Terminali yavaşlatmak için
unsigned long lastPrintTime = 0;
const unsigned long printInterval = 500; 

// Havadan veri geldiği an otomatik çalışan fonksiyon
void OnDataRecv(const uint8_t * mac, const uint8_t *incomingDataPtr, int len) {
    // 1. Gelen byte'ları struct içine kopyala
    memcpy(&incomingData, incomingDataPtr, sizeof(incomingData));
    
    // ================================================================
    //  2. STM32'YE UART İLE ANINDA GÖNDERİM (Senin İstediğin Kısım)
    // ================================================================
    uint8_t packet[3];
    packet[0] = 0xAA;                                 // Başlangıç Baytı
    packet[1] = (uint8_t)incomingData.gestureID;      // Sınıflandırma sonucu (0, 1, 2 vb.)
    packet[2] = 0x55;                                 // Bitiş Baytı
    
    // TX pininden (GPIO 17) STM32'ye fırlat
    Serial1.write(packet, 3);

    // ================================================================
    //  3. EKO (PING-PONG) İŞLEMİ: Gelen veriyi anında geri yolla!
    // ================================================================
    if (!esp_now_is_peer_exist(mac)) {
        esp_now_peer_info_t peerInfo = {};
        memcpy(peerInfo.peer_addr, mac, 6);
        peerInfo.channel = 0;
        peerInfo.encrypt = false;
        esp_now_add_peer(&peerInfo);
    }
    // Paketi geldiği gibi (içindeki zaman damgasıyla) Göndericiye geri şutla
    esp_now_send(mac, (uint8_t *) &incomingData, sizeof(incomingData));

    // ================================================================
    //  4. EKRANA YAZDIRMA (Saniyede 2 kez çalışır, işlemciyi yormaz)
    // ================================================================
    unsigned long now = millis();
    if (now - lastPrintTime >= printInterval) {
        Serial.print("\n>>> PAKET YAKALANDI <<<");
        Serial.printf("\nSTM32'ye Iletilen Hareket ID: %d", incomingData.gestureID);
       // Serial.printf("\nZaman Damgasi (us): %lu", incomingData.timestamp);
        Serial.println("\n[Bilgi] Paket STM32'ye basildi ve Vericiye geri sektirildi.");
        Serial.println("=======================================\n");
        lastPrintTime = now;
    }
}

void setup() {
    delay(3000); 
    // Bilgisayar ile debug ekranı
    Serial.begin(115200);
    
    // STM32 ile haberlesme (Baud: 115200, RX=GPIO18, TX=GPIO17)
    // Eğer senin kartında pinler farklıysa burayı güncellemeyi unutma!
    Serial1.begin(115200, SERIAL_8N1, 18, 17);

    Serial.println("\n--- ALICI (EKO + UART MODU) BASLADI ---");

    WiFi.mode(WIFI_STA); 
    WiFi.disconnect();

    if (esp_now_init() != ESP_OK) {
        Serial.println("HATA: ESP-NOW Baslatilamadi!");
        return;
    }

    esp_now_register_recv_cb(OnDataRecv);
    Serial.println("Havayi dinliyorum, paketler STM32'ye basilecek ve geri sektirilecek...");
}

void loop() {
    delay(1000);
}
