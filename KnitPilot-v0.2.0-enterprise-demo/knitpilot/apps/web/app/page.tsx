"use client";

import { useEffect, useMemo, useState } from "react";

type Evidence = { value: string | number | null; unit: string | null; source: string; confidence: number; confirmed: boolean };
type Section = "measurements" | "gauge" | "shrinkage" | "machine" | "repeats" | "qc";
type Spec = { schema_version: string; project: Record<string, Evidence>; garment: Record<string, Evidence>;
  machine: Record<string, Evidence>; gauge: Record<string, Evidence>; shrinkage: Record<string, Evidence>;
  measurements: Record<string, Evidence>; repeats: Record<string, Evidence>; qc: Record<string, Evidence>;
  neck_rib: Record<string, Evidence>; [key: string]: unknown };
type Sequence = { interval_rows: number; stitches: number; times: number };
type Panel = { cast_on: number; total_rows: number; rib_rows: number; armhole_start_row: number;
  armhole: { start_stitches: number; bind_off_each_side: number; decreases_each_side: Sequence[]; shaping_rows: number; end_stitches: number };
  neck: { center_bind_off: number; decreases_each_side: Sequence[]; shaping_rows: number; shoulder_stitches_each_side: number };
  shoulder: { start_each_side: number; bind_off_each_side: Sequence[]; slope_rows: number }; final_stitches: number };
type Sleeve = { cast_on: number; upper_stitches: number; rows_before_cap: number; increases_each_side: Sequence[];
  cap: { start_stitches: number; base_bind_off_each_side: number; decreases_each_side: Sequence[]; cap_rows: number; top_bind_off: number }; final_stitches: number };
type Draft = { back_panel: Panel; front_panel: Panel; sleeve: Sleeve; neck_rib_stitches: number;
  neck_rib_rows: number; choices: [string, { selected_stitches: number; theoretical_stitches: number; difference: number; width_error_cm: number; reason: string }][];
  qc: { code: string; ok: boolean; detail: string }[] };
type PanelKey = "front_panel" | "back_panel" | "sleeve" | "neck_rib";
type Field = { key: string; label: string; unit: string };

const measureGroups: { title: string; hint: string; fields: Field[] }[] = [
  { title: "衣身与肩部", hint: "洗后平铺尺寸，厘米", fields: [
    { key: "chest_width", label: "胸宽（单片）", unit: "cm" }, { key: "body_length", label: "衣长", unit: "cm" },
    { key: "armhole_depth", label: "袖窿深", unit: "cm" }, { key: "shoulder_width", label: "肩宽", unit: "cm" },
    { key: "shoulder_slope", label: "肩斜高", unit: "cm" }, { key: "hem_rib_height", label: "下摆罗纹高", unit: "cm" },
  ] },
  { title: "领口", hint: "前后领深分别录入", fields: [
    { key: "neck_width", label: "领宽", unit: "cm" }, { key: "front_neck_depth", label: "前领深", unit: "cm" },
    { key: "back_neck_depth", label: "后领深", unit: "cm" }, { key: "neck_rib_height", label: "领条高度", unit: "cm" },
    { key: "neck_rib_circumference", label: "领条目标长度", unit: "cm" },
  ] },
  { title: "袖片", hint: "左右袖按同一规格计算", fields: [
    { key: "sleeve_length", label: "袖长", unit: "cm" }, { key: "sleeve_cuff_width", label: "袖口宽", unit: "cm" },
    { key: "sleeve_upper_width", label: "袖肥", unit: "cm" }, { key: "sleeve_cap_height", label: "袖山高", unit: "cm" },
    { key: "sleeve_cap_top_width", label: "袖山顶宽", unit: "cm" },
  ] },
];
const technicalGroups: { title: string; fields: { section: Section; key: string; label: string; unit: string; step?: string }[] }[] = [
  { title: "样布密度", fields: [
    { section: "gauge", key: "stitches_per_10cm", label: "横密", unit: "针 / 10cm" },
    { section: "gauge", key: "rows_per_10cm", label: "纵密", unit: "转 / 10cm" },
  ] },
  { title: "洗后尺寸变化率", fields: [
    { section: "shrinkage", key: "horizontal", label: "横向", unit: "%" },
    { section: "shrinkage", key: "vertical", label: "纵向", unit: "%" },
  ] },
  { title: "机台与循环", fields: [
    { section: "machine", key: "min_needles", label: "最少针数", unit: "针", step: "1" },
    { section: "machine", key: "max_needles", label: "最多针数", unit: "针", step: "1" },
    { section: "repeats", key: "pattern_repeat", label: "花型循环", unit: "针", step: "1" },
  ] },
  { title: "QC 容差", fields: [
    { section: "qc", key: "dimension_tolerance_cm", label: "尺寸误差", unit: "cm" },
    { section: "qc", key: "seam_tolerance_cm", label: "袖山缝合差", unit: "cm" },
  ] },
];
const panelLabels: Record<PanelKey, string> = { front_panel: "前片", back_panel: "后片", sleeve: "袖片", neck_rib: "领条" };
const notation = (seq: Sequence[]) => seq.length ? seq.map(s => `${s.interval_rows}-${s.stitches}-${s.times}`).join(" · ") : "无";

function Logo() { return <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#175e61] text-white shadow-sm">
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M4 3v18M20 3v18M4 7l8 6 8-6M4 13l8 6 8-6"/></svg>
</div>; }

function Drawing({ draft, panel, onSelect }: { draft: Draft; panel: PanelKey; onSelect: (area: string) => void }) {
  const isSleeve = panel === "sleeve";
  const isRib = panel === "neck_rib";
  const p = !isSleeve && !isRib ? draft[panel] as Panel : null;
  let path = "";
  if (p) {
    const base = 160, top = 160 * p.armhole.end_stitches / p.cast_on;
    const x0 = 230 - base, x1 = 230 + base, xt0 = 230 - top, xt1 = 230 + top;
    const armY = 320 - 260 * p.armhole_start_row / p.total_rows;
    const neckHalf = 160 * (p.neck.center_bind_off + 2 * p.neck.decreases_each_side.reduce((a,s)=>a+s.stitches*s.times,0)) / p.cast_on;
    const neckY = 32 + Math.min(95, 260 * p.neck.shaping_rows / p.total_rows);
    path = `M ${x0} 320 L ${x1} 320 L ${x1} ${armY} Q ${x1} ${armY-26} ${xt1} ${armY-39} L ${xt1} 37 L ${230+neckHalf} 37 Q ${230+neckHalf} ${neckY} 230 ${neckY} Q ${230-neckHalf} ${neckY} ${230-neckHalf} 37 L ${xt0} 37 L ${xt0} ${armY-39} Q ${x0} ${armY-26} ${x0} ${armY} Z`;
  } else if (isSleeve) {
    const s = draft.sleeve, cuff = 160*s.cast_on/s.upper_stitches, capTop = 160*s.cap.top_bind_off/s.upper_stitches;
    const capY = s.cap.cap_rows ? 110 : 36;
    path = `M ${230-cuff} 320 L ${230+cuff} 320 L 390 ${capY} Q 390 ${capY-38} ${230+capTop} 37 L ${230-capTop} 37 Q 70 ${capY-38} 70 ${capY} Z`;
  }
  return <svg className="h-full w-full" viewBox="0 0 460 370" role="img" aria-label={`${panelLabels[panel]}技术示意图`}>
    <defs><pattern id="knit-grid" width="16" height="16" patternUnits="userSpaceOnUse"><path d="M 16 0 L 0 0 0 16" fill="none" stroke="#e9eef0" strokeWidth="1"/></pattern><linearGradient id="fabric" x1="0" x2="1"><stop stopColor="#d9ebea"/><stop offset="1" stopColor="#eef6f3"/></linearGradient></defs>
    <rect x="0" y="0" width="460" height="370" fill="url(#knit-grid)" />
    {isRib ? <><rect x="62" y="132" width="336" height="88" rx="6" fill="url(#fabric)" stroke="#2a7473" strokeWidth="2" />
      {Array.from({length:31},(_,i)=><line key={i} x1={72+i*10.5} y1="137" x2={72+i*10.5} y2="215" stroke="#89b6b3" strokeWidth="1"/>)}
      <text x="230" y="265" textAnchor="middle" fontSize="13" fill="#65757c">罗纹领条 · 循环由程序约束</text></>
      : <><path d={path} fill="url(#fabric)" stroke="#287876" strokeWidth="2.6" strokeLinejoin="round" />
        <line x1="46" y1="320" x2="414" y2="320" stroke="#a1b9b6" strokeWidth="1" strokeDasharray="4 5" />
        <text x="230" y="348" textAnchor="middle" fontSize="13" fill="#68817e">{isSleeve ? `起针 ${draft.sleeve.cast_on} 针` : `起针 ${p?.cast_on} 针`}</text>
        {!isSleeve && <><g role="button" tabIndex={0} onClick={()=>onSelect("armhole")} onKeyDown={e=>e.key==="Enter"&&onSelect("armhole")} className="cursor-pointer"><circle cx="375" cy="160" r="17" fill="#fff" stroke="#72aaa3"/><text x="375" y="165" textAnchor="middle" fontSize="12" fill="#236b67">①</text></g>
          <g role="button" tabIndex={0} onClick={()=>onSelect("neck")} onKeyDown={e=>e.key==="Enter"&&onSelect("neck")} className="cursor-pointer"><circle cx="230" cy="82" r="17" fill="#fff" stroke="#72aaa3"/><text x="230" y="87" textAnchor="middle" fontSize="12" fill="#236b67">②</text></g></>}
      </>}
  </svg>;
}

export default function Home() {
  const [spec, setSpec] = useState<Spec | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [panel, setPanel] = useState<PanelKey>("front_panel");
  const [focus, setFocus] = useState("armhole");
  const [active, setActive] = useState<"measurements" | "technical">("measurements");
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => { fetch("/demo/demo-spec.json").then(r => { if (!r.ok) throw new Error("无法读取示例规格"); return r.json(); })
    .then(setSpec).catch(e => setError(e.message)); }, []);

  const failed = useMemo(() => draft?.qc.filter(q=>!q.ok) ?? [], [draft]);
  const updateField = (section: Section, key: string, value: number | null) => {
    setSpec(current => {
      if (!current) return current;
      const next = structuredClone(current);
      next[section][key] = { ...next[section][key], value, source: "manual:demo", confidence: 1, confirmed: value !== null };
      return next;
    });
    setDirty(true); setError("");
  };
  const updateStyle = (value: string) => {
    setSpec(current => {
      if (!current) return current;
      const next=structuredClone(current);
      next.garment.shoulder_style = {...next.garment.shoulder_style, value, source:"manual:demo", confidence:1, confirmed:true};
      const drop = value === "drop";
      for (const [key, v] of Object.entries({shoulder_width:drop?next.measurements.chest_width.value:44,
        sleeve_cap_height:drop?0:19.5, sleeve_cap_top_width:drop?next.measurements.sleeve_upper_width.value:12})) {
        next.measurements[key] = {...next.measurements[key], value:v, source:"manual:demo", confidence:1, confirmed:true};
      }
      return next;
    });
    setDirty(true);
  };
  const updateRib = (kind: string) => {
    setSpec(current => {
      if (!current) return current;
      const next=structuredClone(current);
      next.neck_rib.kind = {...next.neck_rib.kind, value:kind, source:"manual:demo", confidence:1, confirmed:true};
      next.repeats.rib_repeat = {...next.repeats.rib_repeat, value:kind==="1x1"?2:4, source:"manual:demo", confidence:1, confirmed:true};
      return next;
    });
    setDirty(true);
  };
  const calculate = async () => {
    if (!spec) return;
    setBusy(true); setError("");
    try {
      const response = await fetch("/v1/calculate", {method:"POST",headers:{"Content-Type":"application/json",...(token?{"X-Demo-Token":token}:{})},body:JSON.stringify(spec)});
      const data = await response.json();
      if (!response.ok) throw new Error(response.status===401?"访问码无效。请向演示提供方索取访问码。":(typeof data.detail==="string"?data.detail:"输入不完整，请检查所有数值和单位。"));
      setDraft(data); setDirty(false); setPanel("front_panel"); setFocus("armhole");
    } catch (e) { setError(e instanceof Error?e.message:"连接失败，请稍后重试。"); }
    finally { setBusy(false); }
  };
  const exportJson = () => {
    if (!spec || !draft || dirty) return;
    const blob=new Blob([JSON.stringify({spec,draft,generated_at:new Date().toISOString(),label:"演示草稿，需人工审核"},null,2)],{type:"application/json"});
    const url=URL.createObjectURL(blob); const a=document.createElement("a"); a.href=url; a.download="knitpilot-demo-draft.json"; a.click(); URL.revokeObjectURL(url);
  };
  const numericField = (section: Section, f: Field & {step?:string}, percent=false) => {
    const raw = spec?.[section]?.[f.key]?.value;
    return <label key={`${section}.${f.key}`} className="block min-w-0"><span className="mb-2 block text-[12px] font-semibold text-[#52636e]">{f.label}</span>
      <div className="relative"><input className="field-input pr-20 text-[14px] font-medium tabular-nums" type="number" step={f.step??"0.1"} value={raw===null||raw===undefined?"":percent?Number(raw)*100:raw}
        onChange={e=>updateField(section,f.key,e.target.value===""?null:percent?Number(e.target.value)/100:Number(e.target.value))}/>
        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-[#83949c]">{f.unit}</span></div>
    </label>;
  };

  return <div className="min-h-screen">
    <header className="border-b border-[#e5e9ec] bg-white"><div className="mx-auto flex max-w-[1540px] items-center justify-between gap-4 px-5 py-4 lg:px-10">
      <div className="flex items-center gap-3"><Logo/><div><div className="text-[17px] font-bold tracking-tight text-[#17333b]">KnitPilot <span className="ml-2 text-[12px] font-medium text-[#7a8c92]">AI针织工艺师</span></div><div className="text-[11px] text-[#87969d]">可审核的针织工艺初稿</div></div></div>
      <div className="flex items-center gap-3"><span className="hidden rounded-full border border-[#bce0d5] bg-[#eff9f4] px-3 py-1 text-[11px] font-semibold text-[#307960] sm:inline">企业试用演示 · V0.2</span>
        <a href="/docs" className="text-[12px] font-semibold text-[#52717a] hover:text-[#176a6a]">API 文档 ↗</a></div>
    </div></header>
    <main className="mx-auto max-w-[1540px] px-5 pb-12 pt-8 lg:px-10">
      <div className="mb-7 flex flex-wrap items-end justify-between gap-5"><div><div className="mb-2 text-[11px] font-bold uppercase tracking-[.2em] text-[#2b8c84]">Workspace / Demo</div>
        <h1 className="text-[26px] font-bold tracking-tight text-[#172d38] sm:text-[30px]">基础圆领套头衫 · 工艺初稿</h1>
        <p className="mt-2 text-[13px] leading-6 text-[#71818b]">修改目标尺寸，确定性程序换算针数和转数，并即时核对数学守恒。</p></div>
        <div className="flex gap-2"><span className="rounded-lg border border-[#dce4e6] bg-white px-3 py-2 text-[11px] text-[#71848d]">示例尺码 M</span><span className="rounded-lg border border-[#dce4e6] bg-white px-3 py-2 text-[11px] text-[#71848d]">长袖 · 平针</span></div></div>
      <div className="mb-6 rounded-xl border border-[#f2e2b5] bg-[#fffaf0] px-5 py-3.5 text-[12px] leading-5 text-[#826b37]">
        <strong>试用说明</strong>　当前版本使用手动确认的规格和演示数据。尚不识别上传文件，也不保存项目；不要输入企业机密。计算结果须由工艺师审核，不可直接下机。
      </div>
      <div className="grid gap-6 xl:grid-cols-[minmax(430px,0.93fr)_minmax(570px,1.07fr)]">
        <section className="card min-w-0 overflow-hidden"><div className="flex items-center justify-between border-b border-[#edf0f1] px-6 py-5"><div><h2 className="text-[16px] font-bold">规格输入</h2><p className="mt-1 text-[11px] text-[#8b989e]">字段修改后请重新生成工艺</p></div><span className="rounded-full bg-[#f0f4f5] px-2.5 py-1 text-[11px] text-[#60727a]">01 / 输入</span></div>
          <div className="flex gap-1 border-b border-[#edf0f1] px-6 pt-3"><button onClick={()=>setActive("measurements")} className={`border-b-2 px-4 pb-3 text-[13px] font-semibold ${active==="measurements"?"border-[#18766f] text-[#176a68]":"border-transparent text-[#8a99a0]"}`}>成衣尺寸</button><button onClick={()=>setActive("technical")} className={`border-b-2 px-4 pb-3 text-[13px] font-semibold ${active==="technical"?"border-[#18766f] text-[#176a68]":"border-transparent text-[#8a99a0]"}`}>密度与机台</button></div>
          <div className="subtle-scroll max-h-[690px] overflow-y-auto px-6 pb-6 pt-5">
            {spec ? <><div className="mb-6 grid gap-4 sm:grid-cols-2"><label className="text-[12px] font-semibold text-[#52636e]">肩型<select className="field-input mt-2 text-[13px]" value={String(spec.garment.shoulder_style.value)} onChange={e=>updateStyle(e.target.value)}><option value="set_in">正肩</option><option value="drop">基础落肩</option></select></label><label className="text-[12px] font-semibold text-[#52636e]">领条组织<select className="field-input mt-2 text-[13px]" value={String(spec.neck_rib.kind.value)} onChange={e=>updateRib(e.target.value)}><option value="1x1">1×1 罗纹</option><option value="2x2">2×2 罗纹</option></select></label></div>
              {active==="measurements"? measureGroups.map(group=><div key={group.title} className="mb-7"><div className="mb-4 flex items-baseline justify-between gap-2"><h3 className="text-[13px] font-bold text-[#243c46]">{group.title}</h3><span className="text-[10px] text-[#a0abb0]">{group.hint}</span></div><div className="grid gap-4 sm:grid-cols-2">{group.fields.map(f=>numericField("measurements",f))}</div></div>) : technicalGroups.map(group=><div key={group.title} className="mb-7"><h3 className="mb-4 text-[13px] font-bold text-[#243c46]">{group.title}</h3><div className="grid gap-4 sm:grid-cols-2">{group.fields.map(f=>numericField(f.section,f,f.section==="shrinkage"))}</div></div>)}
            </> : <div className="py-20 text-center text-[13px] text-[#8d9ca3]">正在载入演示规格…</div>}
          </div>
          <div className="border-t border-[#edf0f1] bg-[#fafbfb] px-6 py-5"><div className="mb-3 flex items-center gap-2"><label htmlFor="access-code" className="shrink-0 text-[12px] font-semibold text-[#566972]">演示访问码</label><input id="access-code" className="field-input !py-2 text-[12px]" type="password" autoComplete="off" placeholder="由演示提供方提供" value={token} onChange={e=>setToken(e.target.value)} /></div>
            {error && <p role="alert" className="mb-3 rounded-lg bg-[#fff1ed] px-3 py-2 text-[12px] text-[#ad513f]">{error}</p>}
            <button onClick={calculate} disabled={!spec||busy} className="w-full rounded-xl bg-[#176c6b] px-5 py-3.5 text-[13px] font-bold text-white shadow-md shadow-[#176c6b]/15 transition hover:bg-[#105958] disabled:cursor-not-allowed disabled:opacity-60">{busy?"正在计算…":draft&&dirty?"重新生成工艺初稿 →":"生成工艺初稿 →"}</button>
          </div></section>
        <section className="min-w-0 space-y-5"><div className="card overflow-hidden"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#edf0f1] px-6 py-5"><div><h2 className="text-[16px] font-bold">技术图与工艺</h2><p className="mt-1 text-[11px] text-[#8b989e]">程序绘制 SVG · 按部件查看</p></div>{draft&&<span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${dirty?"bg-[#fff2e0] text-[#a66b27]":failed.length?"bg-[#fff0ed] text-[#bd5a44]":"bg-[#e8f7f1] text-[#267c5e]"}`}>{dirty?"尺寸已修改，待重算":failed.length?`${failed.length} 项待复核`:"QC 全部通过"}</span>}</div>
            {draft ? <><div className="flex flex-wrap gap-2 border-b border-[#edf0f1] px-6 py-3">{(Object.keys(panelLabels) as PanelKey[]).map(key=><button key={key} onClick={()=>{setPanel(key);setFocus("armhole")}} className={`rounded-lg px-4 py-2 text-[12px] font-semibold ${panel===key?"bg-[#e7f3f1] text-[#176d68]":"text-[#819099] hover:bg-[#f4f7f7]"}`}>{panelLabels[key]}</button>)}</div>
              <div className="grid lg:grid-cols-[1fr_210px]"><div className="min-h-[300px] bg-[#fbfdfd] px-3 py-4"><Drawing draft={draft} panel={panel} onSelect={setFocus}/></div><div className="border-t border-[#edf0f1] px-5 py-5 lg:border-l lg:border-t-0"><div className="mb-4 text-[11px] font-bold uppercase tracking-widest text-[#95a3a9]">{panelLabels[panel]}参数</div>
                {panel==="neck_rib"?<div className="space-y-4"><Metric label="领条起针" value={`${draft.neck_rib_stitches} 针`}/><Metric label="领条高度" value={`${draft.neck_rib_rows} 转`}/></div>:
                  panel==="sleeve"?<div className="space-y-4"><Metric label="起针" value={`${draft.sleeve.cast_on} 针`}/><Metric label="袖肥" value={`${draft.sleeve.upper_stitches} 针`}/><Metric label="双侧加针" value={notation(draft.sleeve.increases_each_side)}/><Metric label="袖山双侧减针" value={notation(draft.sleeve.cap.decreases_each_side)}/><Metric label="袖山顶平收" value={`${draft.sleeve.cap.top_bind_off} 针`}/></div>:
                  <div className="space-y-4"><div className="flex gap-2"><button onClick={()=>setFocus("armhole")} className={`rounded px-2 py-1 text-[11px] ${focus==="armhole"?"bg-[#def0ed] text-[#176c69]":"bg-[#f2f5f5] text-[#7b8b91]"}`}>① 袖窿</button><button onClick={()=>setFocus("neck")} className={`rounded px-2 py-1 text-[11px] ${focus==="neck"?"bg-[#def0ed] text-[#176c69]":"bg-[#f2f5f5] text-[#7b8b91]"}`}>② 领窝</button></div>
                    {focus==="armhole"?<><Metric label="开始转数" value={`${draft[panel].armhole_start_row} 转`}/><Metric label="两侧平收" value={`${draft[panel].armhole.bind_off_each_side} 针 / 侧`}/><Metric label="两侧减针" value={notation(draft[panel].armhole.decreases_each_side)}/></>:<><Metric label="中心平收" value={`${draft[panel].neck.center_bind_off} 针`}/><Metric label="两侧减针" value={notation(draft[panel].neck.decreases_each_side)}/><Metric label="肩针" value={`${draft[panel].neck.shoulder_stitches_each_side} 针 / 侧`}/></>}
                  </div>}
              </div></div>
              <div className="flex items-center justify-between gap-3 border-t border-[#edf0f1] px-6 py-4"><span className="text-[11px] text-[#87979e]">{dirty?"当前结果对应修改前的规格":"结果仅供人工审核"}</span><button onClick={exportJson} disabled={dirty} className="rounded-lg border border-[#c6dbd8] px-3 py-2 text-[11px] font-bold text-[#24726d] hover:bg-[#eff8f5] disabled:opacity-40">下载 JSON 草稿 ↓</button></div>
            </> : <div className="flex min-h-[470px] flex-col items-center justify-center px-6 text-center"><div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-[#e8f4f1] text-[#2f827e]"><svg width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M5 3v26M27 3v26M5 9l11 8 11-8M5 17l11 8 11-8"/></svg></div><h3 className="text-[15px] font-bold">等待生成工艺初稿</h3><p className="mt-2 max-w-[260px] text-[12px] leading-6 text-[#8a9aa1]">左侧修改演示规格，点击生成后查看部件技术图、加减针序列及 QC 结果。</p></div>}
          </div>
          <div className="card px-6 py-5"><div className="mb-4 flex items-center justify-between"><div><h2 className="text-[15px] font-bold">QC 数学校核</h2><p className="mt-1 text-[11px] text-[#8b989e]">守恒、循环、尺寸与基础缝合长度</p></div>{draft&&<span className="text-[12px] font-bold text-[#267d63]">{draft.qc.length-failed.length}/{draft.qc.length} 通过</span>}</div>
            {draft?<div className="grid gap-2 sm:grid-cols-2">{(failed.length?failed:draft.qc.slice(0,6)).map(item=><div key={item.code} title={item.detail} className={`flex items-center gap-2 rounded-lg px-3 py-2 text-[11px] ${item.ok?"bg-[#f1f8f5] text-[#4c7866]":"bg-[#fff1ed] text-[#af5949]"}`}><span>{item.ok?"✓":"!"}</span><span className="truncate">{item.code.replaceAll("_"," ")}</span></div>)}</div>:<p className="text-[12px] text-[#a0abb1]">生成后显示检查项和异常原因。</p>}
          </div>
        </section>
      </div>
      <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-[#e2e8e9] pt-5 text-[11px] text-[#9aa8ad]"><span>© KnitPilot · 企业试用演示</span><span>未接入文件解析 · 未保存版本 · 不生成机器程序</span></div>
    </main>
  </div>;
}

function Metric({label,value}:{label:string;value:string}) { return <div><div className="mb-1 text-[11px] text-[#94a1a7]">{label}</div><div className="break-words font-mono text-[13px] font-semibold leading-5 text-[#28404a]">{value}</div></div>; }
