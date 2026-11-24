"""The release world: the dark store PREREG-1 describes, beside the legacy mode, never inside it.

Truth program session 5, stage B (``docs/adr/ADR-062-the-release-world.md``). Built so that the same
seed gives the same bits in CPython and in Pyodide:

* **every random draw is counter-based** (:mod:`synapse_kernel.release.rng`): a pure function of the
  replicate's seed, a purpose, an entity (an item or a supplier) and a time slot, never of a
  policy's action, so arms at one seed face one world by construction;
* **every sampler uses exact arithmetic** (:mod:`synapse_kernel.release.sampling`): additions,
  multiplications, divisions, comparisons and powers of two, which IEEE 754 fixes on every platform,
  and no libm call and no ``numpy.random`` distribution, whose streams numpy does not promise across
  versions or CPUs (truth finding F-36);
* **the store's state is integers** (units, hours, batches), and the objective is summed exactly.
"""
