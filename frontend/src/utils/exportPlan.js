import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";

// jsPDF's built-in fonts have no rupee glyph, so PDFs use "Rs".
const rs = (n) => (n == null ? "-" : `Rs ${Number(n).toLocaleString("en-IN")}`);
const hhmm = (iso) => (iso ? iso.slice(11, 16) : "-");
const NAVY = [14, 34, 64];

function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const slug = (plan) => `voyager-${plan.destination.city.toLowerCase()}-${plan.request.departure_date}`;

export function exportJson(plan) {
  download(new Blob([JSON.stringify(plan, null, 2)], { type: "application/json" }), `${slug(plan)}.json`);
}

export function exportPdf(plan) {
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  const W = doc.internal.pageSize.getWidth();
  const M = 40;
  const req = plan.request;

  doc.setFillColor(...NAVY);
  doc.rect(0, 0, W, 96, "F");
  doc.setTextColor(255, 255, 255);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(20);
  doc.text(plan.trip_title, M, 46);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10.5);
  doc.text(
    `${req.origin} to ${plan.destination.city}  |  ${req.departure_date} to ${req.return_date}  |  ${req.travelers} traveller(s)  |  Est. total ${rs(plan.budget.grand_total)}`,
    M,
    70,
  );

  doc.setTextColor(...NAVY);
  let y = 122;
  doc.setFontSize(10.5);
  const summary = doc.splitTextToSize(plan.summary, W - 2 * M);
  doc.text(summary, M, y);
  y += summary.length * 13 + 10;

  const head = { fillColor: NAVY, textColor: 255, fontStyle: "bold" };
  const flights = [plan.outbound_flight, plan.return_flight].map((f, i) =>
    f
      ? [i ? "Return" : "Outbound", `${f.airline} ${f.flight_id}`, `${f.origin} ${hhmm(f.departure_time)}`, `${f.destination} ${hhmm(f.arrival_time)}`, rs(f.price_per_person), rs(f.total_price)]
      : [i ? "Return" : "Outbound", "No direct flight in dataset", "-", "-", "-", "-"],
  );
  autoTable(doc, { startY: y, head: [["Leg", "Flight", "Departs", "Arrives", "Per person", "Total"]], body: flights, headStyles: head, styles: { fontSize: 9 } });
  y = doc.lastAutoTable.finalY + 14;

  if (plan.hotel) {
    const h = plan.hotel;
    autoTable(doc, {
      startY: y,
      head: [["Hotel", "Stars", "Per night", "Rooms", "Stay total", "Amenities"]],
      body: [[h.name, String(h.stars), rs(h.price_per_night), String(h.rooms_needed), rs(h.total_stay_cost), h.amenities.join(", ")]],
      headStyles: head,
      styles: { fontSize: 9 },
    });
    y = doc.lastAutoTable.finalY + 14;
  }

  const fmt = (list) => list.map((a) => a.title).join("\n") || "Free time";
  autoTable(doc, {
    startY: y,
    head: [["Day", "Weather", "Morning", "Afternoon", "Evening", "Est. cost"]],
    body: plan.days.map((d) => [
      `Day ${d.day}\n${d.date}\n${d.theme}`,
      d.weather && d.weather.source !== "unavailable"
        ? `${d.weather.condition}\n${Math.round(d.weather.temp_max_c)}/${Math.round(d.weather.temp_min_c)} C${d.weather.source === "historical" ? "\n(last year)" : ""}`
        : "Unavailable",
      fmt(d.morning),
      fmt(d.afternoon),
      fmt(d.evening),
      rs(d.estimated_cost),
    ]),
    headStyles: head,
    styles: { fontSize: 8.5, valign: "top" },
    columnStyles: { 0: { cellWidth: 78 }, 1: { cellWidth: 74 }, 5: { cellWidth: 58 } },
  });
  y = doc.lastAutoTable.finalY + 14;

  autoTable(doc, {
    startY: y,
    head: [["Budget item", "Source", "Detail", "Amount"]],
    body: [
      ...plan.budget.lines.map((l) => [l.category, l.basis === "dataset" ? "Dataset" : "Estimate", l.detail, rs(l.amount)]),
      [{ content: "Total (group)", colSpan: 3, styles: { fontStyle: "bold" } }, { content: rs(plan.budget.grand_total), styles: { fontStyle: "bold" } }],
    ],
    headStyles: head,
    styles: { fontSize: 8.5 },
  });
  y = doc.lastAutoTable.finalY + 14;

  const ex = plan.explanations;
  autoTable(doc, {
    startY: y,
    head: [[{ content: "Why your AI travel agent chose this plan", colSpan: 2 }]],
    body: [
      ["Flight", ex.flight],
      ["Hotel", ex.hotel],
      ["Attractions", ex.attractions],
      ["Weather & location", ex.weather_and_location],
      ["Budget", ex.budget],
      ...(plan.warnings.length ? [["Notes", plan.warnings.join("\n")]] : []),
    ],
    headStyles: head,
    styles: { fontSize: 8.5, valign: "top" },
    columnStyles: { 0: { cellWidth: 100, fontStyle: "bold" } },
  });

  const pages = doc.getNumberOfPages();
  for (let i = 1; i <= pages; i++) {
    doc.setPage(i);
    doc.setFontSize(8);
    doc.setTextColor(138, 155, 176);
    doc.text(
      `Voyager AI | plan ${plan.plan_id} | ${plan.mode === "agent" ? `LangChain agent (${plan.model})` : "rule-based planner"} | page ${i} of ${pages}`,
      M,
      doc.internal.pageSize.getHeight() - 20,
    );
  }
  doc.save(`${slug(plan)}.pdf`);
}
