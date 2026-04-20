# Component Table — Smarter Pet Feeder

| Component          | Type     | Pin(s)              | Purpose                                        |
|--------------------|----------|---------------------|------------------------------------------------|
| IR Obstacle Sensor | Digital  | D2                  | Pet presence detection                         |
| DHT11              | Digital  | D3                  | Temperature & humidity sensing                 |
| HX711 DT           | Digital  | D4                  | Load cell data (bowl weight)                   |
| HX711 SCK          | Digital  | D5                  | Load cell clock                                |
| Servo Motor        | PWM      | D6                  | Food dispensing mechanism                      |
| Relay Module       | Digital  | D7                  | Fan control                                    |
| RFID RST           | Digital  | D9                  | RFID reset                                     |
| RFID SDA (SS)      | Digital  | D10                 | RFID chip select                               |
| RFID MOSI          | SPI      | D11                 | SPI data out                                   |
| RFID MISO          | SPI      | D12                 | SPI data in                                    |
| RFID SCK           | SPI      | D13                 | SPI clock                                      |
| Potentiometer      | Analog   | A5                  | Simulates cat body weight (pressure mat)       |
| 5V DC Fan          | Actuator | Via relay on D7     | Humidity control                               |
| 5kg Load Cell      | Analog   | Via HX711 D4/D5     | Measures food weight in bowl (grams)           |
