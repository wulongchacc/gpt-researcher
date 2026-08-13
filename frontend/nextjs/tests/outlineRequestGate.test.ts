import assert from "node:assert/strict";
import test from "node:test";

import { createOutlineRequestGate } from "../services/outlineRequestGate.ts";

test("the request gate rejects duplicate starts while a request is active", () => {
  const gate = createOutlineRequestGate();

  const firstRequest = gate.begin();

  assert.equal(typeof firstRequest, "number");
  assert.equal(gate.begin(), null);
  assert.equal(gate.isActive(), true);
});

test("finishing the active request releases the gate", () => {
  const gate = createOutlineRequestGate();
  const requestId = gate.begin();

  assert.notEqual(requestId, null);
  assert.equal(gate.finish(requestId as number), true);
  assert.equal(gate.isActive(), false);
  assert.equal(typeof gate.begin(), "number");
});

test("cancelling invalidates a late response and allows a retry", () => {
  const gate = createOutlineRequestGate();
  const cancelledRequest = gate.begin() as number;

  gate.cancel();
  const retryRequest = gate.begin() as number;

  assert.equal(gate.finish(cancelledRequest), false);
  assert.equal(gate.finish(retryRequest), true);
});

test("an unrelated request cannot release the active request", () => {
  const gate = createOutlineRequestGate();
  const requestId = gate.begin() as number;

  assert.equal(gate.finish(requestId + 100), false);
  assert.equal(gate.isActive(), true);
});
