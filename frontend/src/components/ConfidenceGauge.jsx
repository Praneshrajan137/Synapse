import React from "react";

function colorForConfidence(c) {
  if (c >= 0.8) return "#22c55e";
  if (c >= 0.7) return "#eab308";
  return "#ef4444";
}

export default function ConfidenceGauge({ value = 0, size = 100 }) {
  const pct = Math.round(value * 100);
  const color = colorForConfidence(value);
  const r = size / 2 - 8;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - value);

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#334155" strokeWidth={6} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={6}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" fill={color} fontSize={size * 0.22} fontWeight="700">
        {pct}%
      </text>
    </svg>
  );
}
