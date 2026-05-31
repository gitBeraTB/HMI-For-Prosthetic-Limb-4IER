import sys
import serial
import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, Qt
import time
import csv

# ==========================================
# 1. AYARLAR
# ==========================================
SERIAL_PORT = '/dev/cu.usbmodem1101'
BAUD_RATE = 921600
MAX_POINTS = 5000
OUTPUT_FILE = 'emg_kayit_3ch.csv'

# Etiket eslemesi (Kullanicinin istedigi 6 sinif)
LABELS = {'1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6}
LABEL_NAMES = {
    0: 'IDLE (Kayit Yok)', 
    1: 'BICEPS REST', 
    2: 'BICEPS', 
    3: 'BILEK REST', 
    4: 'BILEK', 
    5: 'TUTMA', 
    6: 'BIRAKMA'
}
LABEL_COLORS = {
    0: '#94a3b8', 
    1: '#22c55e', 
    2: '#ef4444', 
    3: '#3b82f6', 
    4: '#eab308', 
    5: '#a855f7', 
    6: '#f97316'
}

current_label = 0   
active_keys = set()


# ==========================================
# 2. SERIAL + CSV
# ==========================================
print(f"🔄 {SERIAL_PORT} portuna bağlanılıyor...")
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01)
    print("✅ Bağlantı OK!")
except Exception as e:
    print(f"❌ Hata: {e}")
    sys.exit()

try:
    csv_file = open(OUTPUT_FILE, mode='w', newline='')
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(['Zaman (sn)', 'CH1 (V)', 'CH2 (V)', 'CH3 (V)', 'Label'])
    print(f"📁 Kayit: '{OUTPUT_FILE}'")
except Exception as e:
    print(f"❌ Dosya hatasi: {e}")
    ser.close()
    sys.exit()

print("-" * 50)
print("ETIKETLEME (PLOT PENCERESI ODAKTA OLMALI):")
print("  Tus yok -> Kayit yok (idle)")
for k, v in LABELS.items():
    print(f"  '{k}' basili tut -> {LABEL_NAMES[v]}")
print("-" * 50)

start_time = time.time()

# ==========================================
# 3. GUI - Qt klavye event'leri
# ==========================================
class PlotWindow(pg.GraphicsLayoutWidget):
    def keyPressEvent(self, event):
        global current_label
        if event.isAutoRepeat():
            return
        ch = event.text()
        if ch in LABELS:
            active_keys.add(ch)
            current_label = LABELS[ch]
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        global current_label
        if event.isAutoRepeat():
            return
        ch = event.text()
        if ch in active_keys:
            active_keys.discard(ch)
            current_label = LABELS[next(iter(active_keys))] if active_keys else 0
        else:
            super().keyReleaseEvent(event)

app = QApplication(sys.argv)
pg.setConfigOptions(antialias=False) # Antialiasing cok CPU yoruyor, kapatiyoruz

win = PlotWindow(show=True, title="EMG 3 CH + Etiketleme")
win.resize(1200, 800)
win.setBackground('#0f172a')
win.setFocusPolicy(Qt.StrongFocus)
win.setFocus()

# Plot 1
p1 = win.addPlot(title="CH1 (GPIO 4)")
p1.setYRange(0, 4095, padding=0) # Auto-range CPU dondurur, sabitledik
p1.showGrid(x=True, y=True, alpha=0.3)
curve1 = p1.plot(pen=pg.mkPen('#ef4444', width=2))
win.nextRow()

# Plot 2
p2 = win.addPlot(title="CH2 (GPIO 5)")
p2.setYRange(0, 4095, padding=0)
p2.showGrid(x=True, y=True, alpha=0.3)
curve2 = p2.plot(pen=pg.mkPen('#3b82f6', width=2))
win.nextRow()

# Plot 3
p3 = win.addPlot(title="CH3 (GPIO 6)")
p3.setYRange(0, 4095, padding=0)
p3.showGrid(x=True, y=True, alpha=0.3)
curve3 = p3.plot(pen=pg.mkPen('#22c55e', width=2))

label_text = pg.TextItem(text='IDLE', color=LABEL_COLORS[0], anchor=(0, 0))
label_text.setPos(50, 4000)
font = pg.QtGui.QFont()
font.setPointSize(20)
font.setBold(True)
label_text.setFont(font)
p1.addItem(label_text)

data_buffer1 = np.zeros(MAX_POINTS)
data_buffer2 = np.zeros(MAX_POINTS)
data_buffer3 = np.zeros(MAX_POINTS)
counts = {k: 0 for k in LABELS.values()}
last_drawn_label = -1

# ==========================================
# 4. UPDATE
# ==========================================
def update():
    global data_buffer1, data_buffer2, data_buffer3, last_drawn_label
    has_new_data = False
    lines_read = 0

    new_p1, new_p2, new_p3 = [], [], []
    
    while ser.in_waiting > 0 and lines_read < 1000:
        try:
            line_str = ser.readline().decode('utf-8', errors='ignore').strip()
            if line_str:
                parts = line_str.split(',')
                if len(parts) == 3:
                    try:
                        r1 = float(parts[0])
                        r2 = float(parts[1])
                        r3 = float(parts[2])
                        
                        v1 = (r1 / 4095.0) * 3.3
                        v2 = (r2 / 4095.0) * 3.3
                        v3 = (r3 / 4095.0) * 3.3
                        
                        t = time.time() - start_time
                        if current_label > 0:
                            csv_writer.writerow([f"{t:.4f}", f"{v1:.4f}", f"{v2:.4f}", f"{v3:.4f}", current_label])
                            counts[current_label] += 1
                            
                        new_p1.append(r1)
                        new_p2.append(r2)
                        new_p3.append(r3)
                        has_new_data = True
                    except ValueError:
                        pass
        except Exception:
            pass
        lines_read += 1
        
    if has_new_data and new_p1:
        n = len(new_p1)
        data_buffer1 = np.roll(data_buffer1, -n)
        data_buffer1[-n:] = new_p1
        
        data_buffer2 = np.roll(data_buffer2, -n)
        data_buffer2[-n:] = new_p2
        
        data_buffer3 = np.roll(data_buffer3, -n)
        data_buffer3[-n:] = new_p3

    if has_new_data:
        curve1.setData(data_buffer1)
        curve2.setData(data_buffer2)
        curve3.setData(data_buffer3)
        
        if current_label != last_drawn_label:
            label_text.setText(LABEL_NAMES[current_label])
            label_text.setColor(LABEL_COLORS[current_label])
            # Renkleri degistirelim arka plan vs
            last_drawn_label = current_label

timer = QTimer()
timer.timeout.connect(update)
timer.start(30) # Saniyede 1000 kere yerine ~30 kere ekran guncellenecek (kasmayi engeller)

# ==========================================
# 5. CALISTIR
# ==========================================
if __name__ == '__main__':
    try:
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        print("\nDurduruldu.")
    finally:
        ser.close()
        csv_file.close()
        print("-" * 50)
        print("KAYIT OZETI:")
        for k, v in LABELS.items():
            print(f"  {LABEL_NAMES[v]} = {counts[v]} ornek")
        print(f"Kaydedildi: {OUTPUT_FILE}")