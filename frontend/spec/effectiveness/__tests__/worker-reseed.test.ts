/**
 * A reseed swaps the fixtures the running MSW worker answers with and never stops it
 * (Req 1.3, Req 10.1). Why a stop is ruled out is stated once, on `HarnessHandle.reseed`.
 *
 * What is real and what is simulated. `startHarness`, `installAtlasHarness`, the handler sets
 * and msw's `getResponse` are the shipped code. `setupWorker` refuses a Node process, so
 * `msw/browser` is replaced by a worker double that records `start`, `stop` and
 * `resetHandlers` and holds the handler list the worker would answer from. Each request is
 * resolved through that list by `getResponse`, which runs the lookup the browser worker runs
 * for every request (`executeHandlers`).
 *
 * Falsifier: put a stop and a second `startHarness` back into `reseedWorker` and the last test
 * fails on the stop and on the second worker; drop the base handlers from a reseed and the
 * `/health` assertion fails; clear the unhandled-path record on a reseed and the gap test fails.
 */

import { EFFECTIVENESS_HARNESS_SEED } from "@lib/effectiveness-scorecard";
import { handlers as baseHandlers } from "@test/msw-handlers";
import { type RequestHandler, type UnhandledRequestCallback, getResponse } from "msw";
import type { StartOptions } from "msw/browser";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { type HarnessHandle, UnhandledFixtureError, startHarness } from "../browser-worker";
import { buildEffectivenessHandlers } from "../handlers";
import { installAtlasHarness } from "../harness";
import { RESOLVE_ESCALATION } from "../scenarios/resolve-escalation";
import { SPATIAL_VISUALIZATION } from "../scenarios/spatial-visualization";

const mswBrowser = vi.hoisted(() => {
  /** An MSW browser worker reduced to what `startHarness` calls on it. */
  class WorkerDouble {
    /** The handler list this worker answers requests from. */
    handlers: RequestHandler[];
    readonly start = vi.fn(async (_options?: StartOptions): Promise<undefined> => undefined);
    readonly stop = vi.fn((): void => undefined);
    readonly resetHandlers = vi.fn((...next: RequestHandler[]): void => {
      this.handlers = next;
    });
    readonly events = { on: vi.fn() };

    constructor(handlers: RequestHandler[]) {
      this.handlers = handlers;
    }
  }
  const workers: WorkerDouble[] = [];
  const setupWorker = vi.fn((...handlers: RequestHandler[]): WorkerDouble => {
    const worker = new WorkerDouble(handlers);
    workers.push(worker);
    return worker;
  });
  return { setupWorker, workers };
});

vi.mock("msw/browser", () => ({ setupWorker: mswBrowser.setupWorker }));

type WorkerDouble = (typeof mswBrowser.workers)[number];

/** Requests resolve against any origin: every handler matches on the path. */
const ORIGIN = "http://localhost:3001";
/** The topology the living map and the supply graph plot; its fixture is seed-derived. */
const TOPOLOGY = "/api/v1/topology";
/** Served only by the base handlers reused from `src/test/msw-handlers.ts`. */
const HEALTH = "/health";
/** msw's print helpers, silenced: these tests read the guard's own error. */
const SILENT_PRINT = { warning: (): void => undefined, error: (): void => undefined };
/** The globals `installAtlasHarness` replaces: the fetch edge, the stream doubles, its own. */
const HARNESS_GLOBALS = ["fetch", "WebSocket", "EventSource", "__atlasHarness"] as const;

interface SavedGlobal {
  readonly descriptor: PropertyDescriptor | undefined;
  readonly value: unknown;
}

const savedGlobals = new Map<string, SavedGlobal>();

beforeEach(() => {
  mswBrowser.workers.length = 0;
  mswBrowser.setupWorker.mockClear();
  for (const key of HARNESS_GLOBALS) {
    savedGlobals.set(key, {
      descriptor: Object.getOwnPropertyDescriptor(globalThis, key),
      value: Reflect.get(globalThis, key),
    });
  }
});

afterEach(() => {
  for (const [key, { descriptor, value }] of savedGlobals) {
    if (descriptor === undefined) {
      Reflect.deleteProperty(globalThis, key);
    } else {
      Object.defineProperty(globalThis, key, descriptor);
      // A global vitest copies from the jsdom window is an accessor that keeps an assigned
      // value behind its setter, so restoring the descriptor alone would keep the double.
      if (descriptor.set !== undefined) Reflect.set(globalThis, key, value);
    }
  }
  savedGlobals.clear();
});

/** Start the harness the way `installAtlasHarness` boots it: at the master seed. */
function bootHarness(): Promise<HarnessHandle> {
  return startHarness({ seed: EFFECTIVENESS_HARNESS_SEED, scenarioId: "harness.boot" });
}

/** The one worker the harness built, refused when there is not exactly one. */
function onlyWorker(): WorkerDouble {
  const [worker, ...others] = mswBrowser.workers;
  if (worker === undefined || others.length > 0) {
    throw new Error(`expected exactly one MSW worker, found ${mswBrowser.workers.length}`);
  }
  return worker;
}

/** The JSON body `handlers` answer `GET path` with, or `undefined` when none answers. */
async function answer(handlers: RequestHandler[], path: string): Promise<unknown> {
  const response = await getResponse(handlers, new Request(new URL(path, ORIGIN)));
  return response === undefined ? undefined : response.json();
}

/** The topology a worker holding the fixtures built from `seed` answers with. */
function topologyAt(seed: number): Promise<unknown> {
  return answer(buildEffectivenessHandlers(seed), TOPOLOGY);
}

/** The unhandled-request guard `startHarness` started the worker with. */
function unhandledRequestGuard(worker: WorkerDouble): UnhandledRequestCallback {
  const strategy = worker.start.mock.calls[0]?.[0]?.onUnhandledRequest;
  if (typeof strategy !== "function") {
    throw new Error("startHarness started the worker without an unhandled-request guard");
  }
  return strategy;
}

describe("the harness reseeds its one MSW worker in place", () => {
  it("a reseed swaps the fixtures and never stops the worker", async () => {
    const handle = await bootHarness();
    const worker = onlyWorker();
    const booted = await answer(worker.handlers, TOPOLOGY);
    expect(booted).toBeDefined();
    expect(booted).toEqual(await topologyAt(EFFECTIVENESS_HARNESS_SEED));

    handle.reseed(SPATIAL_VISUALIZATION.seed);

    // The running worker now answers from the scenario seed's fixtures...
    const reseeded = await answer(worker.handlers, TOPOLOGY);
    expect(reseeded).toEqual(await topologyAt(SPATIAL_VISUALIZATION.seed));
    expect(reseeded).not.toEqual(booted);
    // ...with the reused base handlers still behind them...
    const health = await answer(baseHandlers, HEALTH);
    expect(health).toBeDefined();
    expect(await answer(worker.handlers, HEALTH)).toEqual(health);
    expect(handle.seed).toBe(SPATIAL_VISUALIZATION.seed);
    // ...and it is the same worker: swapped once, started once, never stopped.
    expect(worker.resetHandlers).toHaveBeenCalledTimes(1);
    expect(worker.stop).not.toHaveBeenCalled();
    expect(worker.start).toHaveBeenCalledTimes(1);
    expect(mswBrowser.setupWorker).toHaveBeenCalledTimes(1);
  });

  it("a reseed to the current seed changes nothing", async () => {
    const handle = await bootHarness();
    const worker = onlyWorker();
    const held = worker.handlers;

    handle.reseed(EFFECTIVENESS_HARNESS_SEED);

    expect(worker.handlers).toBe(held);
    expect(worker.resetHandlers).not.toHaveBeenCalled();
    expect(worker.stop).not.toHaveBeenCalled();
    expect(worker.start).toHaveBeenCalledTimes(1);
    expect(handle.seed).toBe(EFFECTIVENESS_HARNESS_SEED);
  });

  it("a contract gap recorded before a reseed is still reported after it", async () => {
    const handle = await bootHarness();
    const worker = onlyWorker();
    const gap = "/api/v1/no-such-capability";
    // No handler answers the path, so msw would hand the request to the guard.
    expect(await answer(worker.handlers, gap)).toBeUndefined();

    const request = new Request(new URL(gap, ORIGIN));
    const guard = unhandledRequestGuard(worker);
    expect(() => guard(request, SILENT_PRINT)).toThrow(UnhandledFixtureError);
    handle.reseed(SPATIAL_VISUALIZATION.seed);

    expect(handle.unhandledPaths()).toEqual([gap]);
  });

  it("seeding scenarios on one page reseeds the boot worker in place and never stops or restarts it", async () => {
    const harness = await installAtlasHarness();
    const worker = onlyWorker();

    await harness.seedScenario(SPATIAL_VISUALIZATION.id);
    await harness.seedScenario(SPATIAL_VISUALIZATION.id);
    await harness.seedScenario(RESOLVE_ESCALATION.setup.scenarioId);

    // Two seed changes swap the fixtures twice; repeating a scenario swaps nothing.
    expect(worker.resetHandlers).toHaveBeenCalledTimes(2);
    const served = await answer(worker.handlers, TOPOLOGY);
    expect(served).toEqual(await topologyAt(RESOLVE_ESCALATION.seed));
    expect(worker.stop).not.toHaveBeenCalled();
    expect(worker.start).toHaveBeenCalledTimes(1);
    expect(mswBrowser.setupWorker).toHaveBeenCalledTimes(1);
  });
});
