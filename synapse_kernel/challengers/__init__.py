"""SYNAPSE's components on the release world, as fair policies (truth session 6, stage B).

Each component does the job PLAN 5.4 gives one of SYNAPSE's agents, as a light kernel policy built
only from cell N's declared world, the frozen incumbent tables and its own fitted parameters, and
reading only :class:`~synapse_kernel.release.observation.StoreObservation`:

* :mod:`~synapse_kernel.challengers.shelf` - the Freshness Guardian: the shelf-life lane, which
  incumbent version a planner who knew the product would run;
* :mod:`~synapse_kernel.challengers.sensing` - the Demand Prophet: today's demand level, sensed;
* :mod:`~synapse_kernel.challengers.surge` - the Disruption Shield: a demand surge, detected;
* :mod:`~synapse_kernel.challengers.supply` - Supplier Trust: a late or absent delivery, detected;
* :mod:`~synapse_kernel.challengers.sentinel_release` - the Inventory Sentinel's newsvendor.

The agents' own models (isolation forest, LSTM, GNN, Pyro, Prophet and TFT) are untrained, heavy
and not bit-exact in a browser, so they are not ported: their jobs are. Every decision path uses
exact arithmetic only (:mod:`~synapse_kernel.challengers.exact`), so the same bits come out on every
platform, and no module here may reach the world's scenario, engine or random streams
(``tests/kernel/challengers/test_rules.py``).
"""
