let runtime;
let font;

export async function pdfRuntime() {
  if (!runtime) runtime = new Promise((resolve, reject) => {
    if (window.jspdf?.jsPDF) { resolve(window.jspdf.jsPDF); return; }
    const script = document.createElement('script');
    script.src = '/vendor/jspdf.umd.min.js';
    script.onload = () => window.jspdf?.jsPDF ? resolve(window.jspdf.jsPDF) : reject(new Error('PDF export could not start.'));
    script.onerror = () => { runtime = undefined; script.remove(); reject(new Error('The PDF library could not be loaded. Refresh and retry.')); };
    document.head.appendChild(script);
  });
  async function loadFont(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error('The report font could not be loaded.');
    const bytes = new Uint8Array(await response.arrayBuffer());
    let value = '';
    for (let i = 0; i < bytes.length; i += 16384) value += String.fromCharCode(...bytes.subarray(i, i + 16384));
    return btoa(value);
  }
  if (!font) font = Promise.all([loadFont('/vendor/BloomSans.ttf'), loadFont('/vendor/NotoNaskhArabic-Regular.ttf')])
    .catch(error => { font = undefined; throw error; });
  return Promise.all([runtime, font]);
}

export function buildAssessmentPDF(jsPDF, report, fontBase64, arabicFontBase64) {
  const doc = new jsPDF({ unit: 'mm', format: 'a4', compress: true });
  doc.addFileToVFS('BloomSans.ttf', fontBase64);
  doc.addFont('BloomSans.ttf', 'BloomSans', 'normal');
  if (arabicFontBase64) {
    doc.addFileToVFS('NotoNaskhArabic.ttf', arabicFontBase64);
    doc.addFont('NotoNaskhArabic.ttf', 'NotoArabic', 'normal');
  }
  doc.setFont('BloomSans', 'normal');
  doc.setProperties({ title: 'BloomCare Assessment Report', creator: 'BloomCare' });
  let y = 24;
  function page() {
    if (y > 269) { doc.addPage(); y = 24; }
  }
  function text(value, size = 10, color = '#304a49') {
    doc.setTextColor(color);
    for (const paragraph of String(value ?? '').split('\n')) {
      const rtl = /[\u0600-\u06ff]/.test(paragraph);
      const effectiveSize = rtl ? size + 1.5 : size;
      doc.setFont(rtl && arabicFontBase64 ? 'NotoArabic' : 'BloomSans', 'normal');
      doc.setFontSize(effectiveSize);
      const lines = doc.splitTextToSize(paragraph || ' ', 170);
      for (const line of lines) {
        // jsPDF applies Unicode bidi shaping itself; forced reversal reverses Urdu twice.
        page(); doc.setR2L(false);
        doc.text(line, rtl ? 190 : 20, y, { align: rtl ? 'right' : 'left' });
        y += effectiveSize * 0.48 + 1.2;
      }
      doc.setR2L(false);
    }
  }
  function section(title) {
    y += 5; if (y > 253) { doc.addPage(); y = 24; }
    doc.setDrawColor('#d4e3df'); doc.line(20, y, 190, y); y += 8;
    text(title, 13, '#18605a'); y += 2;
  }
  const a = report.assessment, o = a.observations;
  text('BloomCare', 23, '#184e49');
  text('Maternal health assessment', 14); y += 3;
  text(`Patient: ${report.patient.full_name}`);
  text(`Email: ${report.patient.email}`);
  text(`Assessment saved: ${new Date(a.created_at).toLocaleString()}`);
  text(`Report generated: ${new Date(report.generated_at).toLocaleString()}`, 9);
  text(`Report reference: ${a.id}`, 8);
  section('Recorded measurements');
  const labels = {
    age_years: ['Age', 'years'], gestational_weeks: ['Pregnancy duration', 'weeks'],
    systolic_mmhg: ['Systolic blood pressure', 'mmHg'], diastolic_mmhg: ['Diastolic blood pressure', 'mmHg'],
    heart_rate_bpm: ['Heart rate', 'bpm'],
  };
  Object.entries(labels).forEach(([key, [label, unit]]) => text(`${label}: ${o[key]} ${unit}`));
  text(`Blood glucose: ${o.glucose_mmol_l} mmol/L (${(o.glucose_mmol_l * 18).toFixed(2)} mg/dL)`);
  text(`Body temperature: ${o.temperature_c} C (${(o.temperature_c * 9 / 5 + 32).toFixed(2)} F)`);
  if (a.clinical_indicators && Object.keys(a.clinical_indicators).length) {
    section('Recorded antenatal and laboratory measurements');
    const clinicalLabels = {
      gravida: 'Number of pregnancies', parity: 'Number of previous births', bmi: 'BMI (kg/m2)',
      hb: 'Haemoglobin (unit not confirmed)', fetal_weight_kg: 'Estimated fetal weight (kg)',
      amniotic_fluid_level_cm: 'Amniotic fluid measurement (cm)', diabetes: 'Diagnosed diabetes',
      history_of_hypertension: 'History of hypertension', protein_uria: 'Protein in urine',
    };
    Object.entries(a.clinical_indicators).forEach(([key, value]) => {
      if (value !== null && value !== undefined) text(`${clinicalLabels[key] || key}: ${typeof value === 'boolean' ? (value ? 'Yes' : 'No') : value}`, 9);
    });
  }
  section('Saved screening results');
  text(`Maternal category: ${a.maternal_risk}`, 13);
  const peStatus = { COMPLETED: 'Screening saved', AWAITING_INPUTS: 'More measurements needed', OUTSIDE_COVERAGE: 'Doctor review needed', UNAVAILABLE: 'Screening unavailable', NOT_REQUIRED: 'Additional screening not triggered' };
  text(`Pre-eclampsia screening: ${peStatus[a.pe_status] || 'Review assessment'}`);
  if (a.pe_screening) {
    text(`Pre-eclampsia category: ${a.pe_screening.risk}`, 12);
    const fields = a.pe_screening.model?.input_fields || [];
    Object.entries(a.pe_screening.observations).forEach(([key, value]) => {
      const field = fields.find(f => f.name === key);
      text(`${field?.label || labels[key]?.[0] || key.replaceAll('_', ' ')}: ${typeof value === 'boolean' ? (value ? 'Yes' : 'No') : value} ${field?.unit || labels[key]?.[1] || ''}`, 9);
    });
    text('The haemoglobin unit has not been confirmed. Review the original lab result with your doctor.', 9);
  } else text('No PE category was produced. This does not rule out pre-eclampsia; discuss your readings with your doctor.', 9);
  if (a.pe_input_issues?.length) {
    text('Readings that need a doctor review:', 10);
    a.pe_input_issues.forEach(field => text(`${field.label}: ${field.value} ${field.unit || ''}; supported screening range ${field.minimum}-${field.maximum} ${field.unit || ''}`, 9));
    text('Screening limits are not healthy ranges. Actual readings have been preserved.', 9);
  }
  section('Personalized care plan');
  if (a.care_plan) {
    text(`Saved ${new Date(a.care_plan.created_at).toLocaleString()}`, 8);
    if (!a.care_plan.current) text('This plan predates the current PE stage. Generate an updated guide before relying on its screening summary.', 9, '#984e30');
    text(a.care_plan.content);
  } else text('A personalized care plan has not been generated for this assessment.');
  section('Clinician review');
  const review = a.clinical_review;
  text(`Review status: ${({ PENDING: 'Awaiting review', REVIEWED: 'Reviewed', URGENT_FOLLOW_UP: 'Urgent follow-up' })[review?.status] || 'Awaiting review'}`);
  if (review?.reason) text(review.reason);
  if (review?.follow_up_at) text(`Follow-up: ${new Date(review.follow_up_at).toLocaleString()}`);
  if (report.notes?.length) {
    section('Patient-visible clinician notes');
    report.notes.forEach(n => {
      text(`${n.author} | ${new Date(n.created_at).toLocaleString()}${n.supersedes_id ? ' | Amendment' : ''}`, 9);
      text(n.body); y += 3;
    });
  }
  section('Report information'); text('Screening has not been clinically validated. Results support a conversation with your doctor and do not diagnose or rule out complications.', 9);
  text('Only patient-visible notes are included. Prescriptions and treatment decisions remain with the clinician.', 9);
  const count = doc.getNumberOfPages();
  for (let number = 1; number <= count; number++) {
    doc.setPage(number); doc.setR2L(false); doc.setDrawColor('#d4e3df'); doc.line(20, 280, 190, 280);
    doc.setFont('BloomSans', 'normal'); doc.setFontSize(8); doc.setTextColor('#56716c');
    doc.text(`BloomCare | Screening support | ${number} / ${count}`, 20, 286);
  }
  return doc;
}

export async function assessmentPDF(report) {
  const [jsPDF, [fontBase64, arabicFontBase64]] = await pdfRuntime();
  return buildAssessmentPDF(jsPDF, report, fontBase64, arabicFontBase64).output('blob');
}

export function savePDF(blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href = url; link.download = 'BloomCare-Assessment.pdf';
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
