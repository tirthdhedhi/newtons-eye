/**
 * Solve A x = b by Gaussian elimination with partial pivoting.
 *
 * A is n x n (row arrays) and is not modified. If A is rank deficient but the
 * system is consistent (for example a string between two bodies that are both
 * held static, which makes the tension indeterminate), the free variables are
 * set to 0 and a particular solution is returned. An inconsistent system
 * returns null.
 */
export function linsolve(A: number[][], b: number[]): number[] | null {
  const n = b.length;
  const M = A.map((row, i) => [...row, b[i] ?? 0]);
  const pivotColOfRow: number[] = [];
  let r = 0;
  for (let c = 0; c < n && r < n; c++) {
    let p = r;
    let best = Math.abs(M[r]?.[c] ?? 0);
    for (let k = r + 1; k < n; k++) {
      const v = Math.abs(M[k]?.[c] ?? 0);
      if (v > best) {
        best = v;
        p = k;
      }
    }
    if (best < 1e-12) continue; // free column
    const rowP = M[p];
    const rowR = M[r];
    if (!rowP || !rowR) return null;
    M[p] = rowR;
    M[r] = rowP;
    for (let k = r + 1; k < n; k++) {
      const row = M[k];
      if (!row) continue;
      const f = (row[c] ?? 0) / (rowP[c] ?? 1);
      if (f === 0) continue;
      for (let j = c; j <= n; j++) row[j] = (row[j] ?? 0) - f * (rowP[j] ?? 0);
    }
    pivotColOfRow[r] = c;
    r++;
  }
  for (let k = r; k < n; k++) {
    if (Math.abs(M[k]?.[n] ?? 0) > 1e-7) return null;
  }
  const x = new Array<number>(n).fill(0);
  for (let k = r - 1; k >= 0; k--) {
    const row = M[k];
    const c = pivotColOfRow[k];
    if (!row || c === undefined) return null;
    let sum = row[n] ?? 0;
    for (let j = c + 1; j < n; j++) sum -= (row[j] ?? 0) * (x[j] ?? 0);
    x[c] = sum / (row[c] ?? 1);
  }
  return x;
}
