import assert from "node:assert/strict";
import test from "node:test";
import { isWebProcessForPort } from "../bin/process-targets.js";

test("restart targets the configured service port", () => {
  assert.equal(isWebProcessForPort("/usr/bin/python -m doc_reader.webapp --port 8766", 8766), true);
  assert.equal(isWebProcessForPort("/usr/bin/python -m doc_reader.webapp", 8766), true);
  assert.equal(isWebProcessForPort("/usr/bin/python -m doc_reader.webapp --port=9876", 9876), true);
});

test("restart preserves isolated test servers and unrelated processes", () => {
  assert.equal(isWebProcessForPort("/usr/bin/python -m doc_reader.webapp --port 18766", 8766), false);
  assert.equal(isWebProcessForPort("/usr/bin/python -m doc_reader.webapp", 9876), false);
  assert.equal(isWebProcessForPort("/usr/bin/python -m doc_reader.tts_service --port 8766", 8766), false);
  assert.equal(isWebProcessForPort("rg -m doc_reader.webapplication", 8766), false);
  assert.equal(isWebProcessForPort("python -m doc_reader.webapp --port invalid", 8766), false);
});
