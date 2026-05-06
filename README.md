# สรุปการเรียนรู้: วันแรกกับ Antigravity 🚀
*วันที่ 4 พฤษภาคม 2569 | โปรเจกต์: PV Load Profile*

---

## 1. Stack ที่ตั้งค่าไปในวันนี้

| เครื่องมือ | หน้าที่ | สถานะ |
|---|---|---|
| **Python 3.9** (venv) | สภาพแวดล้อมแยกต่างหากของโปรเจกต์ | ✅ พร้อมใช้ |
| **Jupyter Notebook** | รันและดูผลลัพธ์แบบ Interactive | ✅ พร้อมใช้ |
| **Jupytext** | Bridge เชื่อม `.py` ↔ `.ipynb` | ✅ พร้อมใช้ |
| **Pandas / NumPy / Matplotlib** | วิเคราะห์และพล็อตกราฟ | ✅ พร้อมใช้ |

---

## 2. Workflow การทำงานร่วมกับ Antigravity

```
คุณบอกโจทย์ → Antigravity แก้ main.py → Jupytext Sync → เปิด/Reload main.ipynb → Run All → ดูผลลัพธ์
```

> [!TIP]
> **กฎสำคัญ:** เมื่อ Antigravity แก้ไขไฟล์ ให้ **ปิดแล้วเปิด `main.ipynb` ใหม่เสมอ** (หรือรอให้ Jupytext Sync เสร็จ) ก่อนกด Run

> [!NOTE]
> หากโค้ดในไฟล์ `.ipynb` ไม่อัปเดต ให้รันคำสั่งนี้ใน Terminal:
> ```bash
> .\venv\Scripts\jupytext.exe --sync main.py
> ```

---

## 3. Python / Pandas ที่ได้เรียนรู้วันนี้

### 📌 การอ่านไฟล์ CSV
```python
df = pd.read_csv('profile_weekday.csv')  # อ่านข้อมูลจากไฟล์
```
**แนวคิด:** แยกข้อมูล (CSV) ออกจากโค้ด (Python) เพื่อให้แก้ไขง่าย ไม่ต้องแตะโค้ดทุกครั้ง

### 📌 การแปลงข้อมูลให้เป็นรูปแบบ DateTime
```python
df['Time'] = pd.to_datetime('2000-01-01 ' + df['Time'], infer_datetime_format=True)
```
**แนวคิด:** Pandas ต้องการ Timestamp เต็มรูปแบบ จึงต้องเติมวันสมมติเข้าไป

### 📌 Linear Interpolation (ประมาณค่าระหว่างจุด)
```python
df.interpolate(method='time')
```
**แนวคิด:** แปลงข้อมูลที่เก็บมาไม่สม่ำเสมอ ให้กลายเป็นข้อมูลรายชั่วโมงสม่ำเสมอ

### 📌 np.where (IF-ELSE สำหรับข้อมูลจำนวนมาก)
```python
np.where(เงื่อนไข, ค่าถ้าจริง, ค่าถ้าเท็จ)
```
**แนวคิด:** เร็วกว่าการใช้ for-loop มากสำหรับข้อมูล 8760+ แถว

### 📌 Monthly Scaling (ปรับสัดส่วนตามเป้าหมาย)
```python
Scaling_Factor = Target_Total / Raw_Total
Adjusted = Raw * Scaling_Factor
```
**แนวคิด:** รูปทรงกราฟคงเดิม แต่สเกลจะขยาย/หดให้ผลรวมตรงเป้า 100%

### 📌 Export CSV แบบ Custom
```python
df['column'].round(4).to_csv('output.csv', index=False, header=False)
```

---

## 4. บทเรียน Data Engineering จากข้อมูลจริง 🔥

> [!IMPORTANT]
> **ปัญหาที่เจอ & วิธีแก้ — สิ่งเหล่านี้คือทักษะ Data Cleaning ที่ใช้จริงในงาน**

| ปัญหาที่เจอ | สาเหตุ | วิธีแก้ |
|---|---|---|
| ค่า `NaN` ใน Interpolation | ข้อมูลไม่เรียงตามเวลา + ขาดจุดยึด 00:00 | `.sort_values()` + เติม Anchor Points |
| ตัวอักษรไทยเป็น □ ในกราฟ | Matplotlib ใช้ฟอนต์ที่ไม่รองรับภาษาไทย | `rcParams['font.family'] = 'Tahoma'` |
| `.ipynb` ไม่อัปเดตหลังแก้ `.py` | ต้องบังคับ Sync ด้วย Jupytext | `jupytext --sync main.py` |

---

## 5. โครงสร้างไฟล์โปรเจกต์ที่สร้างขึ้น

```
PV_loadprofie/
│
├── venv/                    ← Python Environment (ห้ามลบ!)
│
├── main.py                  ← โค้ดหลัก (Antigravity แก้ไขที่นี่)
├── main.ipynb               ← Notebook (Sync กับ main.py อัตโนมัติ)
│
├── profile_weekday.csv      ← INPUT: รูปแบบใช้ไฟวันทำงาน
├── profile_weekend.csv      ← INPUT: รูปแบบใช้ไฟวันหยุด
├── monthly_targets.csv      ← INPUT: เป้าหมายรายเดือน (kWh)
│
└── load_profile_8760.csv    ← OUTPUT: ข้อมูล 8760 ชั่วโมง พร้อมใช้!
```

---

## 6. ขั้นตอนต่อไปที่แนะนำ 🗺️

- [ ] นำ `load_profile_8760.csv` ไปใช้กับซอฟต์แวร์ปลายทาง (เช่น PVSyst, SAM)
- [ ] เพิ่มข้อมูล **PV Generation** เพื่อวิเคราะห์ Self-consumption vs Grid Import/Export
- [ ] เพิ่ม **กราฟรายเดือน** เพื่อดูการกระจายการใช้ไฟตลอดปี
- [ ] ลองใส่ข้อมูลจริงจากไฟล์ CSV ใหม่ และรัน Pipeline นี้ซ้ำ
