"""The verdict: one command that says, in about a minute, whether a decision-core change is safe.

``python -m scripts.verdict`` (or ``make verdict``) runs, at the same time:

* the decision core's fast test selection, in two process shards (safety: the confidence floor,
  the dispatch choke point, execution, the Inventory Sentinel's request mapping);
* a miniature of the E5 proof: E5's own cost function on its first twelve replicate seeds, for
  the consensus arm and the tuned control, plus two seeds run again (quality and determinism);
* the kernel's port of the decision core (``synapse_kernel.policies.sentinel``, the Sentinel alone)
  on the same seeds, which must cost exactly what the consensus pins say (truth session 5).

The costs are judged against committed pins (``infrastructure/quality/verdict-pins.json``), so a
change that moves any decision is reported, with whether it made the consensus arm cheaper or
dearer, and a change that moves the control or the physics is reported as such. The exit code
names the outcome; see :class:`scripts.verdict.judge.Outcome`.
"""
