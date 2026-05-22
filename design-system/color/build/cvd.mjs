// ============================================================================
// SYNAPSE Chromatic System — color-vision-deficiency + perceptual distance
// (domain service: CvdSimulator)
//
// CVD simulation is treated as a metamorphic transform (MR-CLR-002): the
// agent palette must stay mutually distinguishable after the transform.
// ~8% of men have a CVD; the 8-agent palette is the hardest case.
// ============================================================================
import {
  filterDeficiencyDeuter,
  filterDeficiencyProt,
  filterDeficiencyTrit,
  differenceEuclidean,
} from "culori";

const FILTERS = {
  deuteranopia: filterDeficiencyDeuter(1),
  protanopia: filterDeficiencyProt(1),
  tritanopia: filterDeficiencyTrit(1),
};

export const CVD_TYPES = Object.keys(FILTERS);

/** Simulate how `color` appears under a given color-vision deficiency. */
export function simulateCvd(color, type) {
  const filter = FILTERS[type];
  if (!filter) throw new Error(`DbC: unknown CVD type "${type}"`);
  return filter(color);
}

const deltaOklab = differenceEuclidean("oklab");

/** Perceptual distance between two colors — Euclidean in OKLab (deltaEOK). */
export function deltaEOK(a, b) {
  return deltaOklab(a, b);
}

/** Angular hue distance in degrees, in [0, 180]. */
export function hueDistance(h1, h2) {
  const d = Math.abs(((h1 - h2) % 360) + 360) % 360;
  return d > 180 ? 360 - d : d;
}

/** Minimum pairwise deltaEOK across a list of colors (optionally CVD-filtered). */
export function minPairwiseDistance(colors, cvdType = null) {
  const view = cvdType ? colors.map((c) => simulateCvd(c, cvdType)) : colors;
  let min = Infinity;
  for (let i = 0; i < view.length; i++) {
    for (let j = i + 1; j < view.length; j++) {
      min = Math.min(min, deltaEOK(view[i], view[j]));
    }
  }
  return min;
}
