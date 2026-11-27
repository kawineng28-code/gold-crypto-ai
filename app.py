import { useEffect, useMemo, useRef, useState } from 'react'
import { supabase, hasSupabase } from './supabaseClient.js'
import * as XLSX from 'xlsx'

const todayISO = () => new Date().toISOString().slice(0,10)
const uid = () => Math.random().toString(36).slice(2,10)
const OK = ['ปกติ','ไม่มี','อัดจาระบีเพิ่ม']

const SYSTEMS = [
  {key:'air', no:'1', name:'Cooling Tower', kind:'cooling', desc:'แบบฟอร์ม Liang Chi'},
  {key:'cold', no:'2', name:'COLD WATER PUMP', kind:'pump', desc:'ปั๊มน้ำเย็น'},
  {key:'wastewater', no:'3', name:'PUMP น้ำเสีย', kind:'pump', desc:'ปั๊มน้ำเสีย'},
  {key:'booster', no:'4', name:'BOOSTER PUMP', kind:'pump', desc:'ปั๊มเพิ่มแรงดัน'},
  {key:'sump', no:'5', name:'บ่อ SUMP', kind:'pump', desc:'ปั๊มบ่อสูบ'},
  {key:'sanitary', no:'5', name:'PUMP น้ำท่า', kind:'pump', desc:'ปั๊มน้ำท่า'},
  {key:'fan', no:'6', name:'พัดลมดูดอากาศ / อัดอากาศ', kind:'fan', desc:'พัดลม KEF / MAF'},
  {key:'cdp', no:'7', name:'PUMP CDP, PCHP, SCHP', kind:'pump', desc:'ปั๊มระบบทำความเย็น'},
  {key:'fire', no:'8', name:'ตู้ FHC และ ถังดับเพลิง', kind:'fire', desc:'ตาราง 98 จุด / = ปกติ, x = ไม่ปกติ'},
]

const PUMP_PRESETS = {
  cold: [
    {machineNo:'CWP-01', model:'CR45-5', location:'ห้องปั๊มชั้น G', kw:'', note:'160L-242FF300-G1'},
    {machineNo:'CWP-02', model:'CR45-5', location:'ห้องปั๊มชั้น G', kw:'', note:'160L-242FF300-G1'},
  ],
  wastewater: [
    {machineNo:'SSP-1', model:'TOS80C21.5', location:'Topo Room', kw:'1.5'},
    {machineNo:'SSP-2', model:'TOS80C21.5', location:'Topo Room', kw:'1.5'},
    {machineNo:'SSP-3', model:'TOS80C21.5', location:'ชั้นในห้อง AHU', kw:'1.5'},
    {machineNo:'SSP-4', model:'TOS80C21.5', location:'ชั้นในห้อง AHU', kw:'1.5'},
    {machineNo:'SSP-5', model:'TOS80C21.5', location:'ลานจอด G5', kw:'1.5'},
    {machineNo:'SEP-3-6', model:'TOS80C21.5', location:'ลานจอด G5', kw:'1.5'},
  ],
  booster: [
    {machineNo:'BP-01', model:'T-DA90LA', location:'ห้องปั๊มชั้น 18', kw:'1.5'},
    {machineNo:'BP-02', model:'T-DA90LA', location:'ห้องปั๊มชั้น 18', kw:'1.5'},
  ],
  sump: [
    {machineNo:'SDP-1', model:'TOS5082.75', location:'Pump Room', kw:'0.75'},
    {machineNo:'SDP-2', model:'TOS5082.75', location:'Pump Room', kw:'0.75'},
    {machineNo:'SDP-3', model:'TOS5082.75', location:'ลานจอดชั้น UG', kw:'0.75'},
    {machineNo:'SDP-4', model:'TOS5082.75', location:'ลานจอดชั้น UG', kw:'0.75'},
    {machineNo:'SDP-5', model:'TOS5082.75', location:'ลานจอดชั้น UG', kw:'0.75'},
    {machineNo:'SDP-6', model:'TOS5082.75', location:'ลานจอดชั้น UG', kw:'0.75'},
    {machineNo:'SDP-7', model:'TOS5082.75', location:'ลานจอดชั้น UG 5', kw:'0.75'},
    {machineNo:'SDP-8', model:'TOS5082.75', location:'ลานจอดชั้น UG 5', kw:'0.75'},
    {machineNo:'SDP-9', model:'TOS5082.75', location:'ชั้นใต้ดิน', kw:'0.75'},
    {machineNo:'SDP-10', model:'TOS5082.75', location:'ชั้นใต้ดิน', kw:'0.75'},
  ],
  sanitary: [
    {machineNo:'CRP-2', model:'REF 38773', location:'ห้องปั๊มน้ำท่า'},
    {machineNo:'CRP-3', model:'REF 38773', location:'ห้องปั๊มน้ำท่า'},
    {machineNo:'CRP-4', model:'REF 38773', location:'ห้องปั๊มน้ำท่า'},
    {machineNo:'CRP-5', model:'REF 38773', location:'ห้องปั๊มน้ำท่า'},
  ],
  fan: [
    {machineNo:'KEF-004', location:'ลานจอด ชั้น 4'}, {machineNo:'KEF-007', location:'ชั้น 4'},
    {machineNo:'KEF-009', location:'ลานจอดรถชั้น 4'}, {machineNo:'KEF-011', location:'ลานจอดรถชั้น 4'},
    {machineNo:'KEF-013', location:'ลานจอดรถชั้น 4'}, {machineNo:'KEF-015', location:'ลานจอดรถชั้น 4'},
    {machineNo:'KEF-017', location:'ลานจอดรถชั้น 4'}, {machineNo:'KEF-019', location:''},
    {machineNo:'KEF-021', location:''}, {machineNo:'KEF-023', location:''},
    {machineNo:'MAF-005', location:''}, {machineNo:'MAF-006', location:''}, {machineNo:'MAF-008', location:''},
    {machineNo:'MAF-010', location:''}, {machineNo:'MAF-012', location:''}, {machineNo:'MAF-014', location:''},
    {machineNo:'MAF-016', location:''}, {machineNo:'MAF-018', location:''}, {machineNo:'MAF-020', location:''}, {machineNo:'MAF-022', location:''},
  ],
  cdp: [
    {machineNo:'SCHP-01', model:'411,6x8x15', location:'ชั้น 5'}, {machineNo:'SCHP-02', model:'411,6x8x15', location:'ชั้น 5'},
    {machineNo:'SCHP-03', model:'411,6x8x15', location:'ชั้น 5'}, {machineNo:'SCHP-04', model:'3344,4x5x12', location:'ชั้น 5'},
    {machineNo:'PCHP-01', model:'411,8x10x12', location:'ชั้น 5'}, {machineNo:'PCHP-02', model:'411,8x10x12', location:'ชั้น 5'},
    {machineNo:'PCHP-03', model:'411,8x10x12', location:'ชั้น 5'}, {machineNo:'PCHP-04', model:'3344,4x5x9.5', location:'ชั้น 5'},
    {machineNo:'CDP-01', model:'4118x 10x15', location:'ชั้น 5'}, {machineNo:'CDP-02', model:'4118x 10x15', location:'ชั้น 5'},
    {machineNo:'CDP-03', model:'4118x 10x15', location:'ชั้น 5'}, {machineNo:'CDP-04', model:'3344,4x5x11', location:'ชั้น 5'},
  ],
}

const FIRE_RAW = `1|FHC|G01|PLAZA FL G|หน้าลิฟท์ S1
2|FHC|G02|PLAZA FL G|ข้างร้าน SE-ED
3|FHC|G03|PLAZA FL G|ใน Topsuper
4|FHC|G04|PLAZA FL G|หน้า Take home 4
5|FHC|G05|PLAZA FL G|หน้าลิฟท์ S1
6|FHC|101|PLAZA FL 1|ประตู Drop off
7|FHC|102|PLAZA FL 1|ข้างร้าน Macdonal
8|FHC|103|PLAZA FL 1|หน้าร้านสเวนเซ่น
9|FHC|104|PLAZA FL 1|หน้าห้องน้ำชั้น 1
10|FHC|105|PLAZA FL 1|หน้าลิฟท์ S1
11|FHC|201|PLAZA FL 2|ข้างร้านราชเทวี
12|FHC|202|PLAZA FL 2|ข้างร้านโมเดิร์นแอร์
13|FHC|203|PLAZA FL 2|ข้างร้านคลีเอท
14|FHC|204|PLAZA FL 2|หน้าลิฟท์ S1
15|FHC|301|PLAZA FL 3|ข้างร้านเสียง
16|FHC|302|PLAZA FL 3|หน้าร้าน Black Canyon
17|FHC|303|PLAZA FL 3|ข้างร้านโคลน
18|FHC|304|PLAZA FL 3|หน้าลิฟท์ S1
19|FHC|401|PLAZA FL 4|หน้าประตู ST1
20|FHC|402|PLAZA FL 4|ทางเข้าห้องน้ำชั้น 4
21|FHC|403|PLAZA FL 4|ในโรงหนังเมเจอร์
22|FHC|404|PLAZA FL 4|หน้าลิฟท์ S1
23|FHC|501|TOWER FL 5|หน้าลิฟท์ S1
24|FHC|601|TOWER FL 6|หน้าลิฟท์ S1
25|FHC|701|TOWER FL 7|หน้าลิฟท์ S1
26|FHC|801|TOWER FL 8|หน้าลิฟท์ S1
27|FHC|901|TOWER FL 9|หน้าลิฟท์ S1
28|FHC|1001|TOWER FL 10|หน้าลิฟท์ S1
29|FHC|1101|TOWER FL 11|หน้าลิฟท์ S1
30|FHC|1201|TOWER FL 12|หน้าลิฟท์ S1
31|FHC|1401|TOWER FL 14|หน้าลิฟท์ S1
32|FHC|1501|TOWER FL 15|หน้าลิฟท์ S1
33|FHC|1601|TOWER FL 16|หน้าลิฟท์ S1
34|FHC|1701|TOWER FL 17|หน้าลิฟท์ S1
35|FHC|1801|TOWER FL 18|หน้าลิฟท์ S1
36|FHC|CP01|CARPARK จขบ.|ลานจอดจักรยานยนต์
37|FHC|CP02|CARPARK G|ลานจอดชั้น G
38|FHC|CP03|CARPARK G.5|ลานจอดชั้น G.5
39|FHC|CP04|CARPARK 1.5 บน|ลานจอดชั้น 1.5 บน
40|FHC|CP05|CARPARK 1.5 ล่าง|ลานจอดชั้น 1.5 ล่าง
41|FHC|CP06|CARPARK 2|ลานจอดชั้น 2
42|FHC|CP07|CARPARK 2|ลานจอดชั้น 2
43|FHC|CP08|CARPARK 2.5 บน|ลานจอดชั้น 2.5 บน
44|FHC|CP09|CARPARK 2.5 บน|ลานจอดชั้น 2.5 บน
45|FHC|CP010|CARPARK 2.5 ล่าง|ลานจอดชั้น 2.5 ล่าง
46|FHC|CP011|CARPARK 2.5 ล่าง|ลานจอดชั้น 2.5 ล่าง
47|FHC|CP012|CARPARK 3|ลานจอดชั้น 3
48|FHC|CP013|CARPARK 3|ลานจอดชั้น 3
49|FHC|CP014|CARPARK 3.5 บน|ลานจอดชั้น 3.5 บน
50|FHC|CP015|CARPARK 3.5 บน|ลานจอดชั้น 3.5 บน
51|FHC|CP016|CARPARK 3.5 ล่าง|ลานจอดชั้น 3.5 ล่าง
52|FHC|CP017|CARPARK 3.5 ล่าง|ลานจอดชั้น 3.5 ล่าง
53|FHC|CP018|CARPARK 3.75|ลานจอดชั้น 3.75
54|FE|FE G01|PLAZA FL G|ในประตูหนีไฟ ST1
55|FE|FE G02|PLAZA FL G|ในประตูหนีไฟ ST1
56|FE|FE G03|PLAZA FL G|ในประตูหนีไฟ ST1
57|FE|FE G04|PLAZA FL G|Take home 2
58|FE|FE G05|PLAZA FL G|Take home 3
59|FE|FE G06|PLAZA FL G|Take home 4
60|FE|EF 101|PLAZA FL 1|ในประตูหนีไฟ ST1
61|FE|EF 102|PLAZA FL 1|ในประตูหนีไฟ ST1
62|FE|EF 103|PLAZA FL 1|ในประตูหนีไฟ ST1
63|FE|EF 201|PLAZA FL 2|ในประตูหนีไฟ ST1
64|FE|EF 202|PLAZA FL 2|ในประตูหนีไฟ ST1
65|FE|EF 203|PLAZA FL 2|ในประตูหนีไฟ ST1
66|FE|EF 301|PLAZA FL 3|ในประตูหนีไฟ ST1
67|FE|EF 302|PLAZA FL 3|ในประตูหนีไฟ ST1
68|FE|EF 303|PLAZA FL 3|ในประตูหนีไฟ ST1
69|FE|EF 401|PLAZA FL 4|ในประตูหนีไฟ ST1
70|FE|EF 402|PLAZA FL 4|ในประตูหนีไฟ ST1
71|FE|EF 403|PLAZA FL 4|ในประตูหนีไฟ ST1
72|FE|EF 601|TOWER FL 6|MDB
73|FE|EF 602|TOWER FL 6|หน้าห้อง CO2
74|FE|EF 603|TOWER FL 6|หน้าห้อง AHU NO.2
75|FE|EF 701|TOWER FL 7|หน้าห้อง AHU NO.1
76|FE|EF 702|TOWER FL 7|หน้าห้อง AHU NO.1
77|FE|EF 703|TOWER FL 7|หน้าห้อง AHU NO.3
78|FE|EF 704|TOWER FL 7|หน้าห้อง AHU NO.3
79|FE|EF 801|TOWER FL 8|หน้าห้อง AHU NO.1
80|FE|EF 802|TOWER FL 8|หน้าห้อง AHU NO.1
81|FE|EF 803|TOWER FL 8|หน้าห้อง AHU NO.3
82|FE|EF 804|TOWER FL 8|หน้าห้อง AHU NO.3
83|FE|EF 901|TOWER FL 9|หน้าห้อง AHU NO.1
84|FE|EF 902|TOWER FL 9|หน้าห้อง AHU NO.1
85|FE|EF 903|TOWER FL 9|หน้าห้อง AHU NO.3
86|FE|EF 904|TOWER FL 9|หน้าห้อง AHU NO.3
87|FE|EF 1001|TOWER FL 10|หน้าห้อง AHU NO.1
88|FE|EF 1002|TOWER FL 10|หน้าห้อง AHU NO.1
89|FE|EF 1003|TOWER FL 10|หน้าห้อง AHU NO.3
90|FE|EF 1004|TOWER FL 10|หน้าห้อง AHU NO.3
91|FE|EF 1101|TOWER FL 11|หน้าห้อง AHU NO.1
92|FE|EF 1102|TOWER FL 11|หน้าห้อง AHU NO.1
93|FE|EF 1103|TOWER FL 11|หน้าห้อง AHU NO.3
94|FE|EF 1104|TOWER FL 11|หน้าห้อง AHU NO.3
95|FE|EF 1201|TOWER FL 12|หน้าห้อง AHU NO.1
96|FE|EF 1202|TOWER FL 12|หน้าห้อง AHU NO.1
97|FE|EF 1203|TOWER FL 12|หน้าห้อง AHU NO.3
98|FE|EF 1204|TOWER FL 12|หน้าห้อง AHU NO.3`
const FIRE_PRESETS = FIRE_RAW.split('\n').map(l=>{const parts=l.split('|'); return {no:+parts[0], description:(parts[1]||'').trim(), code:(parts[2]||'').trim().toUpperCase(), location:(parts[3]||'').trim(), room:(parts[4]||'').trim()}}).filter(p=>p.code)

const COOLING_GROUPS = [
  {group:'โครงสร้าง', items:[
    {label:'โครงสร้างภายใน', options:['มีการผุกร่อน','เริ่มมีการผุกร่อน','ปกติ']},
    {label:'ทางเดินด้านใน', options:['มีการผุกร่อน','เริ่มมีการผุกร่อน','ปกติ']},
    {label:'Bolts & Nuts', options:['ชำรุด','เริ่มเป็นสนิม','ปกติ']},
    {label:'Float Valve', options:['ชำรุด','ระดับน้ำมีปัญหา','ปกติ']},
    {label:'Ladder', options:['ชำรุด','เริ่มเป็นสนิม','ปกติ']},
    {label:'Fan Deck', options:['ชำรุด','เริ่มเป็นสนิม','ปกติ']},
    {label:'Out Let Pipe', options:['มีการอุดตัน','เริ่มมีสิ่งอุดตัน','ปกติ']},
  ]},
  {group:'ระบบจ่ายน้ำ', items:[
    {label:'อ่างน้ำร้อน', options:['อุดตัน','เริ่มอุดตัน','ปกติ']},
    {label:'Nozzle', options:['ชำรุด','อุดตัน','ปกติ']},
    {label:'Flow Control Valve', options:['ชำรุด','อุดตัน','ปกติ']},
  ]},
  {group:'ถ่ายเทความร้อน', items:[
    {label:'Filling', options:['อุดตันมาก','เริ่มอุดตัน','ปกติ']},
    {label:'Inlet Louver', options:['ชำรุด','จำนวนไม่ครบ','ปกติ']},
  ]},
  {group:'ใบพัด', items:[
    {label:'U-BOLT', options:['ชำรุด','เริ่มชำรุด','ปกติ']},
    {label:'สั่นสะเทือน', options:['มาก','สั่นบ้างเล็กน้อย','ปกติ']},
    {label:'มีเสียงดัง', options:['มี','ไม่มี']},
  ]},
  {group:'มอเตอร์', items:[
    {label:'สั่นสะเทือน', options:['มาก','สั่นเล็กน้อย','ปกติ']},
    {label:'ความร้อน', options:['สูงผิดปกติ','ปกติ']},
    {label:'มีเสียงดัง', options:['มี','ไม่มี']},
  ]},
]

function compressImage(file){
  return new Promise((resolve,reject)=>{
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = ()=>{
      const max = 1024
      let w = img.naturalWidth, h = img.naturalHeight
      if(w>max || h>max){ const r = Math.min(max/w, max/h); w=Math.round(w*r); h=Math.round(h*r) }
      const c = document.createElement('canvas'); c.width=w; c.height=h
      c.getContext('2d').drawImage(img,0,0,w,h)
      c.toBlob(b=>{ URL.revokeObjectURL(url); resolve(new File([b], file.name.replace(/\\.[^.]+$/,'')+'.jpg',{type:'image/jpeg'})) }, 'image/jpeg', 0.82)
    }
    img.onerror = reject
    img.src = url
  })
}

function PhotoBox({photos, setPhotos}){
  const fileRef = useRef(null)
  const videoRef = useRef(null)
  const [camOn,setCamOn] = useState(false)
  const [camErr,setCamErr] = useState('')
  const [stream,setStream] = useState(null)
  const photoKey = (f)=> (f.name||'')+'|'+(f.size||0)+'|'+(f.lastModified||0)
  const addFiles = async (list)=>{
    const arr = Array.from(list||[])
    if(!arr.length) return
    if(photos.length>=1){ alert('แนบได้ 1 รูปต่อเครื่องเท่านั้น - ถ้าจะเปลี่ยนรูป ให้กดลบรูปเดิมก่อน'); return }
    if(arr.length>1){ alert('แนบได้ 1 รูปต่อเครื่องเท่านั้น - เลือกมาแค่รูปเดียวครับ'); return }
    const f = arr[0]
    const key = photoKey(f)
    if(photos.some(p=>p.key===key)){ alert('รูปนี้แนบไปแล้วครับ - ห้ามใช้รูปเดียวกันซ้ำ'); return }
    try{ const small = f.type.startsWith('image/') ? await compressImage(f) : f
      const preview = URL.createObjectURL(small)
      setPhotos(prev=>[...prev, {file:small, preview, name:small.name, key}])
    }catch{ setPhotos(prev=>[...prev,{file:f, preview:URL.createObjectURL(f), name:f.name, key}]) }
  }
  const startCam = async ()=>{
    setCamErr('')
    try{
      const s = await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'}, audio:false})
      setStream(s); setCamOn(true)
      setTimeout(()=>{ if(videoRef.current){ videoRef.current.srcObject=s; videoRef.current.play().catch(()=>{}) } },80)
    }catch(e){ setCamErr('เปิดกล้องไม่ได้: '+ (e?.message||e) + ' — ลองใช้ปุ่มเลือกจากไฟล์รูปแทน หรือตรวจว่าอนุญาตกล้องในเบราว์เซอร์แล้ว') }
  }
  const stopCam = ()=>{ stream?.getTracks().forEach(t=>t.stop()); setStream(null); setCamOn(false) }
  const snap = ()=>{
    const v = videoRef.current; if(!v) return
    const c = document.createElement('canvas'); c.width=v.videoWidth||1280; c.height=v.videoHeight||720
    c.getContext('2d').drawImage(v,0,0,c.width,c.height)
    c.toBlob(async b=>{
      if(photos.length>=1){ alert('แนบได้ 1 รูปต่อเครื่องเท่านั้น - ถ้าจะเปลี่ยนรูป ให้กดลบรูปเดิมก่อน'); stopCam(); return }
      const f = new File([b],'camera.jpg',{type:'image/jpeg'})
      const small = await compressImage(f)
      setPhotos(prev=>[...prev,{file:small, preview:URL.createObjectURL(small), name:'camera.jpg', key:'camera|'+Date.now()}])
      stopCam()
    },'image/jpeg',0.85)
  }
  useEffect(()=>()=>{ stream?.getTracks().forEach(t=>t.stop()) },[stream])
  return <div className="card">
    <b>แนบรูปถ่าย - ได้ 1 รูปต่อเครื่อง ห้ามใช้รูปเดียวกันซ้ำ (ใช้ได้จริงบนเว็บ https)</b>
    <p className="small">แนบได้แค่ 1 รูปต่อเครื่องเท่านั้น ถ้าเลือกรูปซ้ำกับรูปเดิมจะถูกบล็อก ถ้าจะเปลี่ยนรูปให้กดลบรูปเดิมก่อน แล้วค่อยแนบรูปใหม่ รูปจะถูกอัปโหลดขึ้น Supabase Storage ตอนกดบันทึก</p>
    <div className="row">
      <button type="button" className="btn btn-red" onClick={()=>fileRef.current?.click()}>เลือกจากไฟล์รูป</button>
      <button type="button" className="btn btn-ghost" onClick={camOn?stopCam:startCam}>{camOn?'ปิดกล้อง':'ถ่ายรูปจากกล้อง'}</button>
    </div>
    <input ref={fileRef} type="file" accept="image/*" style={{display:'none'}} onChange={e=>{addFiles(e.target.files); e.target.value=''}} />
    {/* ปุ่มนี้คือตัวที่ทำให้มือถือเด้งไปแอปกล้องโดยตรง เสถียรสุด */}
    <label className="btn btn-line" style={{display:'block',textAlign:'center',marginTop:8,cursor:'pointer'}}>📷 เปิดแอปกล้องของเครื่อง (แนะนำบนมือถือ)
      <input type="file" accept="image/*" capture="environment" style={{display:'none'}} onChange={e=>{addFiles(e.target.files); e.target.value=''}} />
    </label>
    {camErr && <div className="err">{camErr}</div>}
    {camOn && <div style={{marginTop:10}}><video ref={videoRef} playsInline muted style={{width:'100%',borderRadius:12,background:'#000'}} /><button type="button" className="btn btn-red" style={{marginTop:8,width:'100%'}} onClick={snap}>กดถ่ายภาพนี้</button></div>}
    {photos.length>0 && <div className="photo-grid" style={{marginTop:12}}>{photos.map((p,i)=><div key={i} style={{position:'relative'}}><img src={p.preview} alt="" /><button type="button" onClick={()=>setPhotos(prev=>prev.filter((_,j)=>j!==i))} style={{position:'absolute',top:6,right:6,background:'#c8102e',color:'#fff',border:0,borderRadius:999,padding:'4px 8px'}}>ลบ</button><div className="small">{p.name}</div></div>)}</div>}
  </div>
}

function SigPad({value, onChange, label}){
  const ref = useRef(null); const drawing = useRef(false); const pts = useRef([])
  useEffect(()=>{ if(value && ref.current){ const ctx=ref.current.getContext('2d'); ctx.clearRect(0,0,720,260); const img=new Image(); img.onload=()=>ctx.drawImage(img,0,0,720,260); img.src=value } },[value])
  const pos = (e)=>{ const r=ref.current.getBoundingClientRect(); const t=e.touches?.[0]||e; return {x:(t.clientX-r.left)/r.width*720, y:(t.clientY-r.top)/r.height*260} }
  const start=(e)=>{ e.preventDefault(); drawing.current=true; pts.current=[pos(e)] }
  const move=(e)=>{ if(!drawing.current) return; e.preventDefault(); const p=pos(e); const ctx=ref.current.getContext('2d'); ctx.strokeStyle='#0f172a'; ctx.lineWidth=3; ctx.lineCap='round'; const prev=pts.current[pts.current.length-1]; ctx.beginPath(); ctx.moveTo(prev.x,prev.y); ctx.lineTo(p.x,p.y); ctx.stroke(); pts.current.push(p) }
  const end=()=>{ if(!drawing.current) return; drawing.current=false; onChange(ref.current.toDataURL('image/png')) }
  return <div className="field"><label>{label}</label><canvas ref={ref} width={720} height={260} style={{width:'100%',height:110,border:'1px solid #e2e8f0',borderRadius:10,background:'#fff',touchAction:'none'}} onPointerDown={start} onPointerMove={move} onPointerUp={end} onPointerLeave={end} /><button type="button" className="btn btn-ghost" style={{marginTop:6}} onClick={()=>{ const c=ref.current; c.getContext('2d').clearRect(0,0,720,260); onChange('') }}>ล้างลายเซ็น</button></div>
}

export default function App(){
  const [user,setUser] = useState(null)
  const [view,setView] = useState('login') // login | dashboard | form | history
  const [authMode,setAuthMode] = useState('login')
  const [authEmail,setAuthEmail] = useState('')
  const [authPass,setAuthPass] = useState('')
  const [authName,setAuthName] = useState('')
  const [authErr,setAuthErr] = useState('')
  const [authMsg,setAuthMsg] = useState('')
  const [records,setRecords] = useState([])
  const [systemKey,setSystemKey] = useState('')
  const [search,setSearch] = useState('')
  const [filterSys,setFilterSys] = useState('all')
  const [filterResult,setFilterResult] = useState('all')
  const [detail,setDetail] = useState(null)
  const [msg,setMsg] = useState('')
  const [saveErr,setSaveErr] = useState('')

  // form state
  const [date,setDate] = useState(todayISO())
  const [month,setMonth] = useState('')
  const [inspector,setInspector] = useState('')
  const [checker,setChecker] = useState('')
  const [project,setProject] = useState('อาคารสุพรีม')
  const [location,setLocation] = useState('')
  const [model,setModel] = useState('')
  const [ctCount,setCtCount] = useState('')
  const [design,setDesign] = useState({flow:'',hot:'',cold:'',wet:''})
  const [reducer,setReducer] = useState('')
  const [belt,setBelt] = useState({type:'',model:'',ratio:'',check:'',pulley:'',grease:'',noise:''})
  const [gear,setGear] = useState({model:'',ratio:'',level:'',oil:'',noise:''})
  const [fanInfo,setFanInfo] = useState({model:'',blades:'',angle:''})
  const [coolingRes,setCoolingRes] = useState({})
  const [note,setNote] = useState('')
  const [photos,setPhotos] = useState([])
  const [sig1,setSig1] = useState('')
  const [sig2,setSig2] = useState('')
  const [pumpRows,setPumpRows] = useState([{}])
  const [fireRows,setFireRows] = useState([{}])
  const [fireAddCode,setFireAddCode] = useState('')
  const [pumpAddNo,setPumpAddNo] = useState('')
  // --- รูปประจำแถว: 1 เครื่อง = 1 รูป ห้ามซ้ำ ---
  const rowPhotoKey = (f)=> (f.name||'')+'|'+(f.size||0)+'|'+(f.lastModified||0)
  const canAddRow = (rows)=>{ const last=rows[rows.length-1]; if(last && !last.photo && !last.photo_url){ alert('แถวที่ '+rows.length+' ยังไม่มีรูป - แนบรูปแถวนี้ก่อนถึงจะเพิ่มแถวที่ '+(rows.length+1)+' ได้'); return false } return true }
  const onRowPhoto = async (rows,setRows,idx,file)=>{ if(!file) return; const key=rowPhotoKey(file); if(rows.some((x,i)=>i!==idx && x.photo && x.photo.key===key)){ alert('รูปนี้ใช้กับเครื่องอื่นไปแล้วครับ - ห้ามใช้รูปเดียวกันซ้ำ'); return } try{ const small = file.type.startsWith('image/') ? await compressImage(file) : file; const preview=URL.createObjectURL(small); setRows(prev=>prev.map((x,i)=>i===idx?{...x, photo:{file:small, preview, name:small.name, key}}:x)) }catch{ setRows(prev=>prev.map((x,i)=>i===idx?{...x, photo:{file, preview:URL.createObjectURL(file), name:file.name, key}}:x)) } }
  const stripRowPhoto = (rows)=> (rows||[]).map(({photo, ...rest})=>({...rest, photo_name: photo?.name||rest.photo_name||'', photo_url: rest.photo_url||''}))
  const uploadRowPhotos = async (rows)=>{ const out=[]; for(const r of rows){ let url=r.photo_url||''; if(r.photo?.file){ if(!hasSupabase){ url=r.photo.preview } else { try{ const name=`${Date.now()}-${uid()}-${r.photo.name||'photo.jpg'}`; const {error}=await supabase.storage.from('photos').upload(name, r.photo.file); if(error) throw error; const {data}=supabase.storage.from('photos').getPublicUrl(name); url=data.publicUrl }catch{ url=r.photo.preview } } } out.push({...r, photo_url:url}) } return out }

  const sys = SYSTEMS.find(s=>s.key===systemKey)

  useEffect(()=>{
    const sp = new URLSearchParams(window.location.search)
    const q = sp.get('system')
    if(q && SYSTEMS.some(s=>s.key===q)) setSystemKey(q)
    if(hasSupabase){
      supabase.auth.getSession().then(({data})=>{ if(data.session?.user) setUser({email:data.session.user.email, name:data.session.user.email}) })
      supabase.auth.onAuthStateChange((_e, sess)=>{ if(sess?.user) setUser({email:sess.user.email, name:sess.user.email}) })
    }
    loadRecords()
  },[])

  async function loadRecords(){
    let local=[]
    try{ local = JSON.parse(localStorage.getItem('supreme_records')||'[]') }catch{ local=[] }
    if(!hasSupabase){ setRecords(local); return }
    try{
      const {data} = await supabase.from('inspections').select('*').order('created_at',{ascending:false}).limit(500)
      if(data && data.length){
        const cloud = data.map(r=>({id:r.id, ...r.data, photo_urls:r.photo_urls||[], created_at:r.created_at, system_key:r.system_key, system_name:r.system_name}))
        const ids = new Set(cloud.map(x=>x.id))
        setRecords([...cloud, ...local.filter(x=>!ids.has(x.id))])
      } else setRecords(local)
    }catch{ setRecords(local) }
  }

  function startSystem(key){
    const s = SYSTEMS.find(x=>x.key===key); setSystemKey(key); setDate(todayISO()); setMonth(''); setInspector(user?.name||''); setChecker(''); setProject('อาคารสุพรีม'); setLocation(''); setModel(''); setCtCount(''); setDesign({flow:'',hot:'',cold:'',wet:''}); setReducer(''); setBelt({type:'',model:'',ratio:'',check:'',pulley:'',grease:'',noise:''}); setGear({model:'',ratio:'',level:'',oil:'',noise:''}); setFanInfo({model:'',blades:'',angle:''}); setCoolingRes({}); setNote(''); setPhotos([]); setSig1(''); setSig2(''); setSaveErr(''); setMsg('')
    if(s.kind==='pump'||s.kind==='fan') setPumpRows([{id:uid()}])
    if(s.kind==='fire') setFireRows([{id:uid()}])
    setView('form'); window.scrollTo({top:0})
  }

  async function handleAuth(e){
    e.preventDefault(); setAuthErr(''); setAuthMsg('')
    if(authMode==='demo'){
      if(authEmail.trim()==='admin' && authPass==='1234'){ setUser({email:'admin', name:'ผู้ดูแลระบบ'}); setInspector('ผู้ดูแลระบบ'); setView('dashboard'); return }
      setAuthErr('บัญชีทดลองคือ admin / 1234'); return
    }
    if(!hasSupabase){ setAuthErr('ยังไม่ได้ตั้งค่า Supabase — ใช้โหมดทดลอง admin / 1234 ก่อน หรือใส่ VITE_SUPABASE_URL ใน .env แล้ว Deploy ใหม่'); return }
    if(authMode==='signup'){
      const {error} = await supabase.auth.signUp({email:authEmail, password:authPass})
      if(error) setAuthErr(error.message); else { setAuthMsg('สมัครสำเร็จแล้ว ลองเข้าสู่ระบบได้เลย'); setAuthMode('login') }
      return
    }
    const {data, error} = await supabase.auth.signInWithPassword({email:authEmail, password:authPass})
    if(error) setAuthErr(error.message); else { setUser({email:data.user.email, name:data.user.email}); setInspector(data.user.email); setView('dashboard') }
  }

  async function uploadPhotos(){
    if(!photos.length) return []
    if(!hasSupabase){
      // โหมดทดลอง: เก็บ preview ไว้เฉยๆ (ไม่คงทน) แต่ยังแสดงในประวัติของเครื่องนั้นได้
      return photos.map(p=>p.preview)
    }
    const urls=[]
    for(const p of photos){
      try{
        const name = `${Date.now()}-${uid()}-${p.name||'photo.jpg'}`
        const {error} = await supabase.storage.from('photos').upload(name, p.file)
        if(error) throw error
        const {data} = supabase.storage.from('photos').getPublicUrl(name)
        urls.push(data.publicUrl)
      }catch{ urls.push(p.preview) }
    }
    return urls
  }

  function countResults(payload){
    let ok=0, bad=0
    if(payload.kind==='cooling'){ Object.values(payload.coolingRes||{}).forEach(v=>{ if(OK.includes(v)) ok++; else if(v) bad++ }) }
    if(payload.kind==='pump'||payload.kind==='fan'){ (payload.rows||[]).forEach(r=>{ ['control','heat','vibration','belt','filter'].forEach(k=>{ const v=r[k]; if(!v) return; if(v==='ปกติ') ok++; else bad++ }) }) }
    if(payload.kind==='fire'){ (payload.rows||[]).forEach(r=>{ if(r.result==='ปกติ') ok++; else if(r.result==='ไม่ปกติ') bad++ }) }
    return {ok, bad}
  }

  async function saveForm(){
    setSaveErr(''); setMsg('')
    // validation
    if(!date) return setSaveErr('กรุณาเลือกวันที่ตรวจ')
    if(!inspector) return setSaveErr('กรุณากรอกชื่อผู้ตรวจ')
    if(sys.kind==='cooling'){
      if(!project||!location||!model||!ctCount) return setSaveErr('กรุณากรอก โครงการ / สถานที่ติดตั้ง / รุ่น / จำนวน C/T ให้ครบ')
      if(!design.flow||!design.hot||!design.cold||!design.wet) return setSaveErr('กรุณากรอก DESIGN CONDITION ให้ครบทั้ง 4 ช่อง')
      if(!reducer) return setSaveErr('กรุณาเลือก Speed Reducer (Direct / Belt / Gear)')
      if(reducer==='Belt' && (!belt.type||!belt.model||!belt.ratio)) return setSaveErr('กรุณากรอก Belt Type / Model / Ratio')
      if(reducer==='Gear' && (!gear.model||!gear.ratio)) return setSaveErr('กรุณากรอก Gear Model / Ratio')
      if(!fanInfo.model||!fanInfo.blades||!fanInfo.angle) return setSaveErr('กรุณากรอก Fan Model / จำนวนใบ / องศา')
      const allItems = [...COOLING_GROUPS.flatMap(g=>g.items)]
      const missing = allItems.filter(it=>!coolingRes[it.label])
      if(missing.length) return setSaveErr('ยังเลือกผลตรวจไม่ครบ: '+missing.map(m=>m.label).join(', '))
      if(reducer==='Belt' && (!belt.check||!belt.pulley||!belt.grease||!belt.noise)) return setSaveErr('กรุณาเลือกผลตรวจ Belt ให้ครบ')
      if(reducer==='Gear' && (!gear.level||!gear.oil||!gear.noise)) return setSaveErr('กรุณาเลือกผลตรวจ Gear ให้ครบ')
    }
    if(sys.kind==='pump'||sys.kind==='fan'){
      if(pumpRows.some(r=>!r.machineNo)) return setSaveErr('กรุณาเลือกเบอร์เครื่องให้ครบทุกแถว')
      if(pumpRows.some(r=>!r.control||!r.heat||!r.vibration)) return setSaveErr('กรุณาเลือก ชุดคอนโทรล / ความร้อน / สั่นสะเทือน ให้ครบทุกแถว')
      if(sys.kind==='fan' && pumpRows.some(r=>!r.belt||!r.filter)) return setSaveErr('กรุณาเลือก สายพาน / ฟิลเตอร์ ให้ครบทุกแถว')
      if(pumpRows.some(r=>!r.photo && !r.photo_url)) return setSaveErr('ทุกเครื่องต้องมีรูป 1 รูป - แนบรูปให้ครบทุกแถวก่อนบันทึก')
    }
    if(sys.kind==='fire'){
      if(!month) return setSaveErr('กรุณาเลือกประจำเดือน')
      if(fireRows.some(r=>!r.code)) return setSaveErr('กรุณาเลือก Code ให้ครบทุกแถว')
      if(fireRows.some(r=>!r.result)) return setSaveErr('กรุณาเลือกผล / หรือ x ให้ครบทุกแถว')
      if(fireRows.some(r=>!r.photo && !r.photo_url)) return setSaveErr('ทุกจุดต้องมีรูป 1 รูป - แนบรูปให้ครบทุกแถวก่อนบันทึก')
    }
    let photo_urls=[]; let cleanPump=pumpRows, cleanFire=fireRows
    try{
      if(sys.kind==='pump'||sys.kind==='fan'){ cleanPump = await uploadRowPhotos(pumpRows); photo_urls = cleanPump.map(r=>r.photo_url||'').filter(Boolean) }
      else if(sys.kind==='fire'){ cleanFire = await uploadRowPhotos(fireRows); photo_urls = cleanFire.map(r=>r.photo_url||'').filter(Boolean) }
      else { photo_urls = await uploadPhotos() }
    }catch(err){ return setSaveErr(err.message) }
    const rowsForSave = sys.kind==='fire'?stripRowPhoto(cleanFire):(sys.kind==='cooling'?pumpRows:stripRowPhoto(cleanPump))
    const payload = {kind:sys.kind, date, month, inspector, checker, project, location, model, ctCount, design, reducer, belt, gear, fanInfo, coolingRes, rows: rowsForSave, note, sig1, sig2, photo_urls}
    const {ok,bad} = countResults(payload)
    const rec = {id:uid(), system_key:sys.key, system_name:sys.name, date, month, inspector, checker, data:payload, photo_urls, ok_count:ok, bad_count:bad, created_at:new Date().toISOString()}
    let cloudOk = false
    if(hasSupabase){
      try{
        const {error} = await supabase.from('inspections').insert({user_email:user?.email||'', inspector, system_key:sys.key, system_name:sys.name, date, month, data:payload, photo_urls, ok_count:ok, bad_count:bad})
        if(!error) cloudOk = true
      }catch{ cloudOk = false }
    }
    // สำคัญ: ถ้า Cloud ต่อไม่ติด (Failed to fetch) ให้เก็บไว้ในเครื่องก่อน งานไม่หาย แล้วค่อยซิงก์ทีหลัง
    try{
      const all = JSON.parse(localStorage.getItem('supreme_records')||'[]'); all.unshift(rec); localStorage.setItem('supreme_records', JSON.stringify(all))
    }catch{}
    setMsg(cloudOk ? 'บันทึกสำเร็จแล้ว' : 'บันทึกสำเร็จแล้ว (เก็บไว้ในเครื่อง เพราะ Cloud ต่อไม่ติด - เปิดประวัติได้เลย ข้อมูลไม่หาย)'); await loadRecords(); setView('history'); window.scrollTo({top:0})
  }

  function exportExcel(){
    const filtered = filteredRecords()
    if(!filtered.length) return alert('ไม่มีข้อมูลให้ส่งออก')
    const wb = XLSX.utils.book_new()
    const bySys = {}
    filtered.forEach(r=>{ (bySys[r.system_key]=bySys[r.system_key]||[]).push(r) })
    const sheetNames = {air:'Cooling Tower', cold:'COLD WATER PUMP', wastewater:'PUMP น้ำเสีย', booster:'BOOSTER PUMP', sump:'บ่อ SUMP', sanitary:'PUMP น้ำท่า', fan:'พัดลมดูดอากาศ', cdp:'CDP PCHP SCHP', fire:'FHC และ ถังดับเพลิง'}
    const keys = filterSys==='all' ? Object.keys(bySys) : [filterSys]
    keys.forEach(k=>{
      const rows=[]
      ;(bySys[k]||[]).forEach(r=>{
        const d=r.data||{}
        if(d.kind==='cooling'){
          rows.push({วันที่:r.date, โครงการ:d.project, สถานที่:d.location, รุ่น:d.model, 'จำนวน C/T':d.ctCount, 'Water Flow':d.design?.flow, 'Hot':d.design?.hot, 'Cold':d.design?.cold, 'Wet Bulb':d.design?.wet, Reducer:d.reducer, ผู้ตรวจ:r.inspector, ผู้ตรวจสอบ:r.checker, ปกติ:r.ok_count, ไม่ปกติ:r.bad_count, รูป:(r.photo_urls||[]).join(' | '), หมายเหตุ:d.note})
          Object.entries(d.coolingRes||{}).forEach(([label,val])=>rows.push({วันที่:r.date, โครงการ:d.project, รายการ:label, ผล:val, ผู้ตรวจ:r.inspector}))
        } else if(d.kind==='fire'){
          (d.rows||[]).forEach(row=>rows.push({วันที่:r.date, ประจำเดือน:r.month, No:row.no, Description:row.description, Code:row.code, LOCATION:row.location, Room:row.room, ผล:row.result==='ปกติ'?'/':'x', หมายเหตุ:row.note, ผู้ตรวจ:r.inspector, ผู้ตรวจสอบ:r.checker, รูป:(row.photo_url||'')}))
        } else {
          (d.rows||[]).forEach(row=>rows.push({วันที่:r.date, เบอร์เครื่อง:row.machineNo, รุ่น:row.model, สถานที่:row.location, KW:row.kw, 'VOLT R':row.voltR, 'VOLT S':row.voltS, 'VOLT T':row.voltT, 'ชุดคอนโทรล':row.control, 'กระแส R':row.ampR, 'กระแส S':row.ampS, 'กระแส T':row.ampT, ความร้อน:row.heat, สั่นสะเทือน:row.vibration, หมายเหตุ:row.note, ผู้ตรวจ:r.inspector, รูป:(row.photo_url||'')}))
        }
      })
      const ws = XLSX.utils.json_to_sheet(rows.length?rows:[{ข้อความ:'ไม่มีข้อมูล'}])
      XLSX.utils.book_append_sheet(wb, ws, (sheetNames[k]||k).slice(0,31))
    })
    XLSX.writeFile(wb, `Supreme_Maintenance_${todayISO()}.xlsx`)
  }

  function filteredRecords(){
    return records.filter(r=>{
      if(filterSys!=='all' && r.system_key!==filterSys) return false
      if(filterResult==='ok' && !(r.bad_count===0)) return false
      if(filterResult==='bad' && !(r.bad_count>0)) return false
      if(search){
        const s = search.toLowerCase()
        const hay = JSON.stringify(r).toLowerCase()
        if(!hay.includes(s)) return false
      }
      return true
    })
  }

  const totalOk = records.reduce((a,r)=>a+(r.ok_count||0),0)
  const totalBad = records.reduce((a,r)=>a+(r.bad_count||0),0)

  if(view==='login'){
    return <div className="wrap">
      <img className="hero" src="/hero.jpg" alt="ช่างอาคารสุพรีม" />
      <div className="card" style={{textAlign:'center'}}><h2 style={{margin:'6px 0'}}>อาคารสุพรีม</h2><p className="small">ตรวจเช็คระบบอาคาร • ถ่ายรูปแนบฟอร์มได้จริง (ต้องเปิดผ่าน https)</p>
      {!hasSupabase && <div className="okbox">โหมดทดลอง: ใช้ <b>admin / 1234</b> ได้เลย ถ้าตั้งค่า Supabase แล้ว จะใช้สมัครสมาชิกจริงได้</div>}
      {hasSupabase && <div className="okbox">เชื่อมต่อ Supabase แล้ว • สมัครสมาชิกและอัปโหลดรูปขึ้น Cloud ได้</div>}
      </div>
      <div className="card">
        <div style={{display:'flex',gap:8}}>
          <button className={authMode==='login'?'btn btn-red':'btn btn-ghost'} style={{flex:1}} onClick={()=>setAuthMode('login')}>เข้าสู่ระบบ</button>
          <button className={authMode==='signup'?'btn btn-red':'btn btn-ghost'} style={{flex:1}} onClick={()=>setAuthMode('signup')}>สร้างบัญชีใหม่</button>
          <button className={authMode==='demo'?'btn btn-red':'btn btn-ghost'} style={{flex:1}} onClick={()=>setAuthMode('demo')}>ทดลองใช้</button>
        </div>
        <form onSubmit={handleAuth}>
          <div className="field"><label>{authMode==='demo'?'ชื่อผู้ใช้':'อีเมล'}</label><input value={authEmail} onChange={e=>setAuthEmail(e.target.value)} placeholder={authMode==='demo'?'admin':'name@email.com'} required /></div>
          <div className="field"><label>รหัสผ่าน</label><input type="password" value={authPass} onChange={e=>setAuthPass(e.target.value)} placeholder={authMode==='demo'?'1234':'อย่างน้อย 6 ตัว'} required /></div>
          {authMode==='signup' && <div className="field"><label>ชื่อ-นามสกุล</label><input value={authName} onChange={e=>setAuthName(e.target.value)} /></div>}
          {authErr && <div className="err">{authErr}</div>}
          {authMsg && <div className="okbox">{authMsg}</div>}
          <button className="btn btn-red" style={{width:'100%',marginTop:10}}>{authMode==='signup'?'สร้างบัญชี':'เข้าสู่ระบบ'}</button>
        </form>
        <p className="small" style={{marginTop:10}}>เปิดใน Chrome / Safari บนมือถือ แล้วอนุญาตกล้องเมื่อเบราว์เซอร์ถาม กล้องจะใช้งานได้เพราะเว็บนี้เป็น https</p>
      </div>
    </div>
  }

  if(view==='dashboard'){
    return <div className="wrap">
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}><div><b>อาคารสุพรีม</b><div className="small">{user?.name||user?.email} • {hasSupabase?'เชื่อม Cloud แล้ว':'โหมดทดลอง'}</div></div><button className="btn btn-ghost" onClick={async()=>{ if(hasSupabase) await supabase.auth.signOut(); setUser(null); setView('login') }}>ออกจากระบบ</button></div>
      <img className="hero" src="/hero.jpg" alt="" style={{marginTop:10}} />
      <div className="card"><b>ตรวจเช็คระบบอาคาร</b><div style={{display:'flex',gap:10,marginTop:10}}><div style={{flex:1,background:'#eaf7ef',borderRadius:12,padding:12,textAlign:'center'}}><div style={{fontSize:22,fontWeight:800,color:'#0e8a4d'}}>{totalOk} ✓</div><div className="small">ปกติ</div></div><div style={{flex:1,background:'#fff0f1',borderRadius:12,padding:12,textAlign:'center'}}><div style={{fontSize:22,fontWeight:800,color:'#c8102e'}}>{totalBad} ✗</div><div className="small">ไม่ปกติ</div></div></div></div>
      {SYSTEMS.map(s=>{
        const n = records.filter(r=>r.system_key===s.key).length
        return <div key={s.key} className="card" onClick={()=>startSystem(s.key)} style={{cursor:'pointer'}}><div style={{display:'flex',justifyContent:'space-between'}}><b>{s.no}. {s.name}</b><span className="chip">บันทึกแล้ว {n} ครั้ง</span></div><div className="small">{s.desc}</div><div style={{marginTop:10}}><button className="btn btn-red">เริ่มตรวจ →</button></div></div>
      })}
      <div className="nav"><button onClick={()=>setView('dashboard')}>🏠 หน้าหลัก</button><button onClick={()=>{ if(systemKey) startSystem(systemKey); else setView('dashboard') }}>📋 ตรวจเช็ค</button><button onClick={()=>{setView('history')}}>📁 ประวัติ</button></div>
    </div>
  }

  if(view==='history'){
    const list = filteredRecords()
    return <div className="wrap">
      <h2>ประวัติการตรวจ</h2>
      <div className="card">
        <div className="field"><label>ค้นหา</label><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="ค้นหา เบอร์เครื่อง / Code / สถานที่ / ผู้ตรวจ" /></div>
        <div className="row">
          <div className="field"><label>หมวด</label><select value={filterSys} onChange={e=>setFilterSys(e.target.value)}><option value="all">ทั้งหมด</option>{SYSTEMS.map(s=><option key={s.key} value={s.key}>{s.no}. {s.name}</option>)}</select></div>
          <div className="field"><label>ผล</label><select value={filterResult} onChange={e=>setFilterResult(e.target.value)}><option value="all">ทั้งหมด</option><option value="ok">ปกติทั้งหมด</option><option value="bad">มีไม่ปกติ</option></select></div>
        </div>
        <button className="btn btn-red" style={{width:'100%'}} onClick={exportExcel}>ส่งออก Excel (.xlsx) แยกชีตตามระบบ</button>
        <button className="btn btn-line" style={{width:'100%',marginTop:8,background:'#fff1f2',borderColor:'#c8102e',color:'#c8102e'}} onClick={async()=>{ if(!confirm('ลบข้อมูลทั้งหมดที่เห็นในหน้านี้เลยใช่ไหม? (ข้อมูลเทสทั้งหมดจะหาย)')) return; if(!confirm('ยืนยันอีกครั้ง - ลบทั้งหมดจริงๆ ใช่ไหม? กู้คืนไม่ได้นะครับ')) return; const ids=list.map(r=>r.id); if(hasSupabase){ for(const id of ids){ await supabase.from('inspections').delete().eq('id', id) } } const all=JSON.parse(localStorage.getItem('supreme_records')||'[]').filter(x=>!ids.includes(x.id)); localStorage.setItem('supreme_records', JSON.stringify(all)); await loadRecords(); alert('ลบข้อมูลทั้งหมดแล้วครับ') }}>🗑️ ลบข้อมูลทั้งหมดในหน้านี้ (เทส)</button>
        <button className="btn btn-line" style={{width:'100%',marginTop:8}} onClick={()=>{ if(!confirm('ล้างข้อมูลที่ค้างในเครื่องนี้ทั้งหมดเลยใช่ไหม? (ใช้ตอนกดลบแล้วเลขไม่ลด)')) return; localStorage.removeItem('supreme_records'); loadRecords(); alert('ล้างข้อมูลในเครื่องนี้แล้วครับ - กลับไปหน้าหลักเลขต้องเป็น 0') }}>🧹 ล้างข้อมูลที่ค้างในเครื่องนี้ (ถ้ากดลบแล้วเลขไม่ลด)</button>
        {msg && <div className="okbox">{msg}</div>}
      </div>
      {list.length===0 && <div className="card">ยังไม่มีประวัติ หรือไม่ตรงกับตัวกรอง</div>}
      {list.map(r=>{
        const d=r.data||{}
        return <div key={r.id} className="card">
          <div style={{display:'flex',justifyContent:'space-between'}}><b>{r.system_name}</b><span className={r.bad_count>0?'chip bad':'chip ok'}>{r.bad_count>0?`ไม่ปกติ ${r.bad_count} ข้อ`:'ปกติทั้งหมด'}</span></div>
          <div className="small">{r.date} {r.month?`• ประจำเดือน ${r.month}`:''} • ผู้ตรวจ {r.inspector}</div>
          <div className="small">ปกติ {r.ok_count} • ไม่ปกติ {r.bad_count} • {r.photo_urls?.length?`มีรูป ${r.photo_urls.length} รูป`:'ไม่มีรูป'}</div>
          {d.note && <div className="small">หมายเหตุ: {d.note}</div>}
          <div style={{display:'flex',gap:8,marginTop:10}}>
            <button className="btn btn-ghost" style={{flex:1}} onClick={()=>setDetail(r)}>ดูรายละเอียด</button>
            <button className="btn btn-line" onClick={async()=>{
              if(!confirm('ลบรายการนี้?')) return
              if(hasSupabase) await supabase.from('inspections').delete().eq('id', r.id)
              const all=JSON.parse(localStorage.getItem('supreme_records')||'[]').filter(x=>x.id!==r.id); localStorage.setItem('supreme_records', JSON.stringify(all))
              loadRecords()
            }}>ลบ</button>
          </div>
        </div>
      })}
      {detail && <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,.5)',zIndex:50,overflow:'auto',padding:12}}><div className="card" style={{maxWidth:680,margin:'20px auto'}}>
        <div style={{display:'flex',justifyContent:'space-between'}}><h3>{detail.system_name}</h3><button className="btn btn-ghost" onClick={()=>setDetail(null)}>ปิด</button></div>
        <p className="small">{detail.date} • {detail.inspector} • ผู้ตรวจสอบ {detail.data?.checker}</p>
        {detail.photo_urls?.length>0 && <div className="photo-grid">{detail.photo_urls.map((u,i)=><a key={i} href={u} target="_blank" rel="noreferrer"><img src={u} alt="" /></a>)}</div>}
        {detail.data?.kind==='cooling' && <div>{Object.entries(detail.data.coolingRes||{}).map(([k,v])=><div key={k} style={{display:'flex',justifyContent:'space-between',borderBottom:'1px solid #eee',padding:'6px 0'}}><span>{k}</span><b>{v}</b></div>)}
        <div className="small">โครงการ {detail.data.project} • รุ่น {detail.data.model} • C/T {detail.data.ctCount} • Flow {detail.data.design?.flow} • Hot {detail.data.design?.hot} • Cold {detail.data.design?.cold} • Wet {detail.data.design?.wet} • Reducer {detail.data.reducer}</div></div>}
        {detail.data?.kind==='fire' && <div className="tablewrap"><table><thead><tr><th>No</th><th>Code</th><th style={{minWidth:200}}>LOCATION</th><th>ผล</th><th>หมายเหตุ</th></tr></thead><tbody>{detail.data.rows.map((r,i)=><tr key={i}><td>{r.no}</td><td>{r.code}</td><td>{r.location}</td><td>{r.result}</td><td>{r.note}</td></tr>)}</tbody></table></div>}
        {(detail.data?.kind==='pump'||detail.data?.kind==='fan') && <div className="tablewrap"><table><thead><tr><th>เบอร์</th><th>รุ่น</th><th>คอนโทรล</th><th>ร้อน</th><th>สั่น</th><th>หมายเหตุ</th></tr></thead><tbody>{detail.data.rows.map((r,i)=><tr key={i}><td>{r.machineNo}</td><td>{r.model}</td><td>{r.control}</td><td>{r.heat}</td><td>{r.vibration}</td><td>{r.note}</td></tr>)}</tbody></table></div>}
        <div style={{display:'flex',gap:10,marginTop:12}}>{detail.data?.sig1 && <div><div className="small">ลายเซ็นผู้ตรวจ</div><img src={detail.data.sig1} style={{width:'100%',border:'1px solid #eee',borderRadius:8}} /></div>}{detail.data?.sig2 && <div><div className="small">ลายเซ็นผู้ตรวจสอบ</div><img src={detail.data.sig2} style={{width:'100%',border:'1px solid #eee',borderRadius:8}} /></div>}</div>
        {detail.data?.note && <p>หมายเหตุรวม: {detail.data.note}</p>}
      </div></div>}
      <div className="nav"><button onClick={()=>setView('dashboard')}>🏠 หน้าหลัก</button><button onClick={()=>{ if(systemKey) startSystem(systemKey) }}>📋 ตรวจเช็ค</button><button onClick={()=>setView('history')}>📁 ประวัติ</button></div>
    </div>
  }

  // FORM
  return <div className="wrap">
    <button className="btn btn-ghost" onClick={()=>setView('dashboard')}>← กลับหน้าหลัก</button>
    <h2 style={{margin:'12px 0 4px'}}>{sys.no}. {sys.name}</h2><p className="small">{sys.desc}</p>
    {saveErr && <div className="err">{saveErr}</div>}
    <div className="card">
      <div className="row">
        <div className="field"><label>วันที่ตรวจ *</label><input type="date" value={date} onChange={e=>setDate(e.target.value)} /></div>
        {sys.kind==='fire' && <div className="field"><label>ประจำเดือน *</label><input type="month" value={month} onChange={e=>setMonth(e.target.value)} /></div>}
      </div>
      <div className="row">
        <div className="field"><label>ผู้ตรวจ / ชื่อช่าง *</label><input value={inspector} onChange={e=>setInspector(e.target.value)} placeholder="ชื่อผู้ตรวจ" /></div>
        <div className="field"><label>ผู้ตรวจสอบ (หัวหน้าทีมวิศวกรรม)</label><input value={checker} onChange={e=>setChecker(e.target.value)} /></div>
      </div>
      {sys.kind==='cooling' && <>
        <div className="field"><label>ชื่อโครงการ *</label><input value={project} onChange={e=>setProject(e.target.value)} /></div>
        <div className="field"><label>สถานที่ติดตั้ง *</label><input value={location} onChange={e=>setLocation(e.target.value)} placeholder="เช่น ดาดฟ้า, ชั้น 1 ห้องเครื่อง" /></div>
        <div style={{display:'flex',flexWrap:'wrap'}}>{['ชั้น 1 ห้องเครื่อง','ดาดฟ้า','ชั้น 1 หน้าลิฟต์','ชั้น 2 ทางหนีไฟ','ห้องเก็บของ','โรงจอดรถ','สำนักงาน','โกดัง'].map(x=><button key={x} type="button" className="chip" onClick={()=>setLocation(x)}>{x}</button>)}</div>
        <div className="row">
          <div className="field"><label>รุ่น Model *</label><input value={model} onChange={e=>setModel(e.target.value)} placeholder="เช่น Liang Chi" /></div>
          <div className="field"><label>จำนวน C/T *</label><input value={ctCount} onChange={e=>setCtCount(e.target.value)} placeholder="เช่น 2" /></div>
        </div>
        <h3>DESIGN CONDITION</h3>
        <div className="row">
          <div className="field"><label>Water Flow (LPM) *</label><input type="number" value={design.flow} onChange={e=>setDesign({...design,flow:e.target.value})} /></div>
          <div className="field"><label>Hot Temp (OC) *</label><input type="number" value={design.hot} onChange={e=>setDesign({...design,hot:e.target.value})} /></div>
          <div className="field"><label>Cold Temp (OC) *</label><input type="number" value={design.cold} onChange={e=>setDesign({...design,cold:e.target.value})} /></div>
          <div className="field"><label>Wet Bulb Temp (OC) *</label><input type="number" value={design.wet} onChange={e=>setDesign({...design,wet:e.target.value})} /></div>
        </div>
      </>}
    </div>

    {sys.kind==='cooling' && <>
      {COOLING_GROUPS.map(g=><div key={g.group} className="card"><h3>{g.group}</h3>{g.items.map(it=><div key={it.label} className="field"><label>{it.label} *</label><div style={{display:'flex',flexWrap:'wrap',gap:6}}>{it.options.map(op=><button key={op} type="button" onClick={()=>setCoolingRes(prev=>({...prev,[it.label]:op}))} className={`btn ${coolingRes[it.label]===op ? (OK.includes(op)?'btn-green':'btn-red') : 'btn-ghost'}`} style={{flex:'1 1 30%',padding:'10px 6px',fontSize:13}}>{op}</button>)}</div></div>)}</div>)}
      <div className="card"><h3>MECHANIC - Speed Reducer *</h3>
        <div style={{display:'flex',gap:8}}>{['Direct','Belt','Gear'].map(x=><button key={x} type="button" className={reducer===x?'btn btn-red':'btn btn-ghost'} style={{flex:1}} onClick={()=>setReducer(x)}>{x}</button>)}</div>
        {reducer==='Belt' && <><div className="row"><div className="field"><label>Belt Type *</label><input value={belt.type} onChange={e=>setBelt({...belt,type:e.target.value})} /></div><div className="field"><label>Belt Model *</label><input value={belt.model} onChange={e=>setBelt({...belt,model:e.target.value})} /></div><div className="field"><label>Ratio *</label><input value={belt.ratio} onChange={e=>setBelt({...belt,ratio:e.target.value})} /></div></div>
        {[['ตรวจปรับสายพาน','check',['หย่อน','สึกมากควรเปลี่ยน','ปกติ']],['Pulley','pulley',['เยื้องศูนย์','มีจาระบี','ปกติ']],['อัดจาระบี','grease',['เสื่อม','น้อยไป','อัดจาระบีเพิ่ม']],['มีเสียงดัง','noise',['มี','ไม่มี']]].map(([label,key,opts])=><div key={key} className="field"><label>{label} *</label><div style={{display:'flex',gap:6}}>{opts.map(op=><button key={op} type="button" className={belt[key]===op?(OK.includes(op)?'btn btn-green':'btn btn-red'):'btn btn-ghost'} style={{flex:1}} onClick={()=>setBelt({...belt,[key]:op})}>{op}</button>)}</div></div>)}
        </>}
        {reducer==='Gear' && <><div className="row"><div className="field"><label>Gear Model *</label><input value={gear.model} onChange={e=>setGear({...gear,model:e.target.value})} /></div><div className="field"><label>Ratio *</label><input value={gear.ratio} onChange={e=>setGear({...gear,ratio:e.target.value})} /></div></div>
        {[['ระดับน้ำมัน','level',['สูง','ต่ำ','ปกติ']],['สภาพน้ำมัน','oil',['มีน้ำผสม','มีเศษโลหะ','ปกติ']],['มีเสียงดัง','noise',['มี','ไม่มี']]].map(([label,key,opts])=><div key={key} className="field"><label>{label} *</label><div style={{display:'flex',gap:6}}>{opts.map(op=><button key={op} type="button" className={gear[key]===op?(OK.includes(op)?'btn btn-green':'btn btn-red'):'btn btn-ghost'} style={{flex:1}} onClick={()=>setGear({...gear,[key]:op})}>{op}</button>)}</div></div>)}
        </>}
        {reducer==='Direct' && <p className="small">Direct Drive ไม่มีฟอร์มย่อยสายพาน / เกียร์</p>}
      </div>
      <div className="card"><h3>ใบพัด</h3><div className="row"><div className="field"><label>Fan Model *</label><input value={fanInfo.model} onChange={e=>setFanInfo({...fanInfo,model:e.target.value})} /></div><div className="field"><label>จำนวนใบ *</label><input value={fanInfo.blades} onChange={e=>setFanInfo({...fanInfo,blades:e.target.value})} /></div><div className="field"><label>องศา *</label><input value={fanInfo.angle} onChange={e=>setFanInfo({...fanInfo,angle:e.target.value})} /></div></div></div>
    </>}

    {(sys.kind==='pump'||sys.kind==='fan') && <div className="card">
      <h3>รายการเครื่อง</h3>
      <div className="field"><label>เพิ่มเครื่องจากรายการ (แสดงเฉพาะเบอร์เครื่อง)</label><div style={{display:'flex',gap:8}}><select value={pumpAddNo} onChange={e=>setPumpAddNo(e.target.value)} style={{flex:1,padding:12,borderRadius:10,border:'1px solid #e2e8f0'}}><option value="">-- เลือกเบอร์เครื่อง --</option>{(PUMP_PRESETS[systemKey]||[]).map(p=><option key={p.machineNo} value={p.machineNo}>{p.machineNo}</option>)}</select><button type="button" className="btn btn-red" onClick={()=>{ if(!pumpAddNo) return; if(!canAddRow(pumpRows)) return; const pre=(PUMP_PRESETS[systemKey]||[]).find(p=>p.machineNo===pumpAddNo); setPumpRows(prev=>[...prev,{id:uid(), machineNo:pumpAddNo, model:pre?.model||'', location:pre?.location||'', kw:pre?.kw||'', note:pre?.note||''}]); setPumpAddNo('') }}>+ เพิ่มแถว</button></div></div>
      <div className="tablewrap"><table><thead><tr><th>เบอร์เครื่อง *</th><th>รุ่น</th><th>สถานที่</th><th>KW</th><th>VOLT R/S/T</th><th>ชุดคอนโทรล *</th><th>กระแส R/S/T</th><th>ความร้อน *</th><th>สั่นสะเทือน *</th>{sys.kind==='fan'&&<><th>สายพาน *</th><th>ฟิลเตอร์ *</th></>}<th>หมายเหตุ</th><th>รูป *</th><th></th></tr></thead>
      <tbody>{pumpRows.map((r,idx)=><tr key={r.id||idx}>
        <td><select value={r.machineNo||''} onChange={e=>{ const v=e.target.value; const pre=(PUMP_PRESETS[systemKey]||[]).find(p=>p.machineNo===v); setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x, machineNo:v, model:pre?.model||x.model||'', location:pre?.location||x.location||'', kw:pre?.kw||x.kw||''}:x)) }}><option value="">-- เลือก --</option>{(PUMP_PRESETS[systemKey]||[]).map(p=><option key={p.machineNo} value={p.machineNo}>{p.machineNo}</option>)}</select>{r.machineNo==='__custom' && <input placeholder="กรอกเบอร์เอง" onChange={e=>setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x, machineNo:e.target.value}:x))} />}</td>
        <td><input value={r.model||''} onChange={e=>setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x,model:e.target.value}:x))} /></td>
        <td><input value={r.location||''} onChange={e=>setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x,location:e.target.value}:x))} /></td>
        <td><input value={r.kw||''} onChange={e=>setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x,kw:e.target.value}:x))} /></td>
        <td><div style={{display:'flex',gap:4}}><input style={{width:55}} placeholder="R" value={r.voltR||''} onChange={e=>setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x,voltR:e.target.value}:x))} /><input style={{width:55}} placeholder="S" value={r.voltS||''} onChange={e=>setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x,voltS:e.target.value}:x))} /><input style={{width:55}} placeholder="T" value={r.voltT||''} onChange={e=>setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x,voltT:e.target.value}:x))} /></div></td>
        <td><select value={r.control||''} onChange={e=>setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x,control:e.target.value}:x))}><option value="">--</option><option>ปกติ</option><option>ไม่ปกติ</option></select></td>
        <td><div style={{display:'flex',gap:4}}><input style={{width:55}} placeholder="R" value={r.ampR||''} onChange={e=>setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x,ampR:e.target.value}:x))} /><input style={{width:55}} placeholder="S" value={r.ampS||''} onChange={e=>setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x,ampS:e.target.value}:x))} /><input style={{width:55}} placeholder="T" value={r.ampT||''} onChange={e=>setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x,ampT:e.target.value}:x))} /></div></td>
        <td><select value={r.heat||''} onChange={e=>setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x,heat:e.target.value}:x))}><option value="">--</option><option>ปกติ</option><option>สูงผิดปกติ</option></select></td>
        <td><select value={r.vibration||''} onChange={e=>setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x,vibration:e.target.value}:x))}><option value="">--</option><option>ปกติ</option><option>สั่นเล็กน้อย</option><option>มาก</option></select></td>
        {sys.kind==='fan'&&<><td><select value={r.belt||''} onChange={e=>setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x,belt:e.target.value}:x))}><option value="">--</option><option>ปกติ</option><option>ไม่ปกติ</option></select></td><td><select value={r.filter||''} onChange={e=>setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x,filter:e.target.value}:x))}><option value="">--</option><option>ปกติ</option><option>สกปรกควรทำความสะอาด</option><option>ควรเปลี่ยน</option></select></td></>}
        <td><input value={r.note||''} onChange={e=>setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x,note:e.target.value}:x))} /></td>
        <td>{r.photo||r.photo_url ? <div style={{position:'relative',width:70}}><img src={r.photo?r.photo.preview:r.photo_url} alt="" style={{width:70,height:52,objectFit:'cover',borderRadius:8}} /><button type="button" onClick={()=>setPumpRows(prev=>prev.map((x,i)=>i===idx?{...x, photo:null, photo_url:''}:x))} style={{position:'absolute',top:-6,right:-6,background:'#c8102e',color:'#fff',border:'none',borderRadius:'50%',width:22,height:22,cursor:'pointer'}}>✕</button></div> : <div style={{display:'flex',flexDirection:'column',gap:4}}><label className="btn btn-line" style={{cursor:'pointer',whiteSpace:'nowrap',textAlign:'center'}}>🖼️ เลือกไฟล์<input type="file" accept="image/*" style={{display:'none'}} onChange={e=>{onRowPhoto(pumpRows,setPumpRows,idx,e.target.files?.[0]); e.target.value=''}} /></label><label className="btn btn-red" style={{cursor:'pointer',whiteSpace:'nowrap',textAlign:'center'}}>📷 ถ่ายจากกล้อง<input type="file" accept="image/*" capture="environment" style={{display:'none'}} onChange={e=>{onRowPhoto(pumpRows,setPumpRows,idx,e.target.files?.[0]); e.target.value=''}} /></label></div>}</td><td><button type="button" className="btn btn-line" onClick={()=>setPumpRows(prev=>prev.length<=1?prev:prev.filter((_,i)=>i!==idx))}>ลบ</button></td>
      </tr>)}</tbody></table></div>
      <button type="button" className="btn btn-ghost" style={{marginTop:10,width:'100%'}} onClick={()=>{ if(!canAddRow(pumpRows)) return; setPumpRows(prev=>[...prev,{id:uid()}]) }}>+ เพิ่มแถวเครื่องเปล่า</button>
    </div>}

    {sys.kind==='fire' && <div className="card">
      <h3>ตารางตรวจ 98 จุด</h3><p className="small">/ = ปกติ , x = ไม่ปกติ</p>
      <div className="field"><label>เพิ่มจุดจากรายการ - มีทั้งหมด 98 Code (G01 ถึง EF 1204) - พิมพ์ตัวเลขหรือรหัสในช่อง - พิมพ์แล้วลิสต์จะขึ้นมาให้เลือก - มี 98 Code</label><div style={{display:'flex',gap:8}}><div style={{flex:1}}><input value={fireAddCode} onChange={e=>setFireAddCode(e.target.value)} placeholder="พิมพ์ค้นหา เช่น G02 หรือ 1204 หรือ SE-ED - มี 98 Code" style={{width:'100%',padding:12,borderRadius:10,border:'1px solid #e2e8f0',background:'#fff'}} />{(fireAddCode||'').trim() ? <div style={{maxHeight:220,overflowY:'auto',border:'1px solid #e2e8f0',borderRadius:10,marginTop:6,background:'#fff'}}>{FIRE_PRESETS.filter(p=>{const q=(fireAddCode||'').trim().toUpperCase(); if(!q) return true; return p.code.includes(q)||p.location.toUpperCase().includes(q)||p.room.toUpperCase().includes(q)||p.description.toUpperCase().includes(q)}).map(p=><button key={p.code} type="button" onClick={()=>setFireAddCode(p.code)} style={{display:'block',width:'100%',textAlign:'left',padding:'10px 12px',border:'none',borderBottom:'1px solid #f1f5f9',background:fireAddCode===p.code?'#fee2e2':'#fff',cursor:'pointer',fontSize:15}}>{p.code} - {p.description} - {p.location} {p.room}</button>)}</div> : null}<div className="small">พิมพ์ตัวเลขหรือรหัสในช่องข้างบน ลิสต์จะขึ้นมาให้เลือกเอง ไม่ต้องโชว์ค้างไว้แล้ว - พิมพ์แค่ G0 ก็เห็น G01-G05 แล้ว</div></div><button type="button" className="btn btn-red" onClick={()=>{ const code=(fireAddCode||'').trim().toUpperCase(); if(!code) return; if(!canAddRow(fireRows)) return; const pre=FIRE_PRESETS.find(p=>(p.code||'').trim().toUpperCase()===code); setFireRows(prev=>[...prev,{id:uid(), no:pre?pre.no:'', description:pre?pre.description:'', code:code, location:pre?pre.location:'', room:pre?pre.room:''}]); setFireAddCode('') }}>+ เพิ่มแถว</button></div></div>
      <div className="tablewrap"><table><thead><tr><th>No.</th><th style={{minWidth:200}}>Description</th><th style={{minWidth:200}}>Code *</th><th style={{minWidth:200}}>LOCATION</th><th style={{minWidth:200}}>Room</th><th>ปกติ (/)</th><th>ไม่ปกติ (x)</th><th>หมายเหตุ</th><th>รูป *</th><th></th></tr></thead>
      <tbody>{fireRows.map((r,idx)=><tr key={r.id||idx}><td>{idx+1}</td><td><input value={r.description||''} onChange={e=>setFireRows(prev=>prev.map((x,i)=>i===idx?{...x,description:e.target.value}:x))} /></td>
        <td style={{minWidth:200}}><input value={r.code||''} onChange={e=>{ const v=e.target.value; const pre=FIRE_PRESETS.find(p=>(p.code||'').trim().toUpperCase()===(v||'').trim().toUpperCase()); setFireRows(prev=>prev.map((x,i)=>i===idx?{...x, code:v, description:pre?.description||x.description||'', location:pre?.location||x.location||'', room:pre?.room||x.room||'', no:pre?.no||x.no}:x)) }} placeholder="พิมพ์ Code" style={{width:200,minWidth:200,padding:8,borderRadius:8,border:'1px solid #e2e8f0',background:'#fff'}} /></td>
        <td><input value={r.location||''} onChange={e=>setFireRows(prev=>prev.map((x,i)=>i===idx?{...x,location:e.target.value}:x))} /></td><td><input value={r.room||''} onChange={e=>setFireRows(prev=>prev.map((x,i)=>i===idx?{...x,room:e.target.value}:x))} /></td>
        <td><button type="button" className={r.result==='ปกติ'?'btn btn-green':'btn btn-ghost'} onClick={()=>setFireRows(prev=>prev.map((x,i)=>i===idx?{...x,result:'ปกติ'}:x))}>/</button></td>
        <td><button type="button" className={r.result==='ไม่ปกติ'?'btn btn-red':'btn btn-ghost'} onClick={()=>setFireRows(prev=>prev.map((x,i)=>i===idx?{...x,result:'ไม่ปกติ'}:x))}>x</button></td>
        <td><input value={r.note||''} onChange={e=>setFireRows(prev=>prev.map((x,i)=>i===idx?{...x,note:e.target.value}:x))} /></td>
        <td>{r.photo||r.photo_url ? <div style={{position:'relative',width:70}}><img src={r.photo?r.photo.preview:r.photo_url} alt="" style={{width:70,height:52,objectFit:'cover',borderRadius:8}} /><button type="button" onClick={()=>setFireRows(prev=>prev.map((x,i)=>i===idx?{...x, photo:null, photo_url:''}:x))} style={{position:'absolute',top:-6,right:-6,background:'#c8102e',color:'#fff',border:'none',borderRadius:'50%',width:22,height:22,cursor:'pointer'}}>✕</button></div> : <div style={{display:'flex',flexDirection:'column',gap:4}}><label className="btn btn-line" style={{cursor:'pointer',whiteSpace:'nowrap',textAlign:'center'}}>🖼️ เลือกไฟล์<input type="file" accept="image/*" style={{display:'none'}} onChange={e=>{onRowPhoto(fireRows,setFireRows,idx,e.target.files?.[0]); e.target.value=''}} /></label><label className="btn btn-red" style={{cursor:'pointer',whiteSpace:'nowrap',textAlign:'center'}}>📷 ถ่ายจากกล้อง<input type="file" accept="image/*" capture="environment" style={{display:'none'}} onChange={e=>{onRowPhoto(fireRows,setFireRows,idx,e.target.files?.[0]); e.target.value=''}} /></label></div>}</td><td><button type="button" className="btn btn-line" onClick={()=>setFireRows(prev=>prev.length<=1?prev:prev.filter((_,i)=>i!==idx))}>ลบ</button></td></tr>)}</tbody></table></div>
      <button type="button" className="btn btn-ghost" style={{marginTop:10,width:'100%'}} onClick={()=>{ if(!canAddRow(fireRows)) return; setFireRows(prev=>[...prev,{id:uid()}]) }}>+ เพิ่มแถวจุดเปล่า</button>
    </div>}

    {sys.kind==='cooling' && <PhotoBox photos={photos} setPhotos={setPhotos} />}
    {sys.kind!=='cooling' && <div className="card"><b>รูปประจำเครื่อง - เลือกไฟล์หรือถ่ายจากกล้อง ในตารางแถวของเครื่องนั้นๆ</b><p className="small">แถวที่ 1 ต้องแนบรูปก่อนถึงจะเพิ่มแถวที่ 2 ได้ แนบรูปแถวที่ 2 แล้วถึงจะเพิ่มแถวที่ 3 ได้ - 1 เครื่องต่อ 1 รูป ห้ามใช้รูปเดียวกันซ้ำ</p></div>}
    <div className="card">
      <div className="field"><label>หมายเหตุรวม</label><textarea rows={3} value={note} onChange={e=>setNote(e.target.value)} placeholder="ข้อที่ต้องแก้ไข / หมายเหตุ" /></div>
      <SigPad label="ลายเซ็นผู้ตรวจ *" value={sig1} onChange={setSig1} />
      <SigPad label="ลายเซ็นผู้ตรวจสอบ" value={sig2} onChange={setSig2} />
      <button className="btn btn-red" style={{width:'100%',marginTop:12}} onClick={saveForm}>บันทึกข้อมูล</button>
      <p className="small" style={{textAlign:'center',marginTop:8}}>{hasSupabase?'บันทึกขึ้น Cloud + รูปอัปโหลดขึ้น Storage':'โหมดทดลอง: บันทึกในเครื่องนี้ (ยังไม่ขึ้น Cloud จนกว่าจะใส่ .env)'} </p>
    </div>
    <div className="nav"><button onClick={()=>setView('dashboard')}>🏠 หน้าหลัก</button><button onClick={()=>setView('form')}>📋 ตรวจเช็ค</button><button onClick={()=>setView('history')}>📁 ประวัติ</button></div>
  </div>
}
