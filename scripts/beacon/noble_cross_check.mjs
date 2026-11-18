// Usage (from a scratch folder): npm install @noble/curves@1.9.7 @noble/hashes@1.8.0,
// then: node noble_cross_check.mjs <round.json> <info.json>. Recorded result, 2026-11-18, round 34052212:
// {"verifies":true,"wrong_round":false,"flipped_bit":false,"randomness_matches":true}
// Independent cross-check of a drand quicknet round with @noble/curves (MIT), as drand's own
// JavaScript client does: G1 short signatures, RFC 9380 hash-to-curve, drand's DST.
import { bls12_381 as bls } from '@noble/curves/bls12-381';
import { sha256 } from '@noble/hashes/sha256';
import { readFileSync } from 'node:fs';
const [roundFile, infoFile] = process.argv.slice(2);
const round = JSON.parse(readFileSync(roundFile, 'utf8'));
const info = JSON.parse(readFileSync(infoFile, 'utf8'));
const hex = (h) => Uint8Array.from(Buffer.from(h, 'hex'));
const msgFor = (r) => { const b = new Uint8Array(8); new DataView(b.buffer).setBigUint64(0, BigInt(r)); return sha256(b); };
const DST = 'BLS_SIG_BLS12381G1_XMD:SHA-256_SSWU_RO_NUL_';
const check = (r, sig) => {
  try {
    const point = bls.G1.hashToCurve(msgFor(r), { DST });
    return bls.verifyShortSignature(hex(sig), point, hex(info.public_key));
  } catch (e) { return false; }
};
const flipped = Buffer.from(round.signature, 'hex'); flipped[47] ^= 1;
console.log(JSON.stringify({
  noble: '1.9.7', round: round.round,
  verifies: check(round.round, round.signature),
  wrong_round: check(round.round + 1, round.signature),
  flipped_bit: check(round.round, flipped.toString('hex')),
  randomness_matches: Buffer.from(sha256(hex(round.signature))).toString('hex') === round.randomness,
}));
