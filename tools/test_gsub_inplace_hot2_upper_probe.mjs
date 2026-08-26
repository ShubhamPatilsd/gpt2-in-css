#!/usr/bin/env node
// Static falsification gate for the rejected in-place split-GSUB topology.

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const experiment = path.join(root, "experiments", "gpt2-gsub-inplace-hot2-upper");
const report = JSON.parse(await fs.readFile(path.join(experiment, "reference.json"), "utf8"));

const checks = {
  decisionIsOfflineRejection: report.decision === "reject-offline-topology",
  browserGateIsClosed: report.browserGate === false,
  browserWasNotLaunched: report.browserLaunched === false,
  browserArtifactWasNotBuilt: report.browserArtifactBuilt === false,
  retainedHas512HotCandidates:
    report.topologyProof.retainedHotUpperCandidateElements === 512,
  gsubTopStillNeeds512Candidates:
    report.topologyProof.minimumGsubTopCandidateElements === 512,
  noUpperCandidatesRemoved:
    report.topologyProof.upperCandidateElementsRemoved === 0,
  fullRemovalShortfall:
    report.topologyProof.removalShortfall === 512,
  gsubDoesNotPerformArgmax:
    report.topologyProof.gsubPerformsArgmax === false,
  runnerIsRequired:
    report.topologyProof.runnerGridRequiredForMargin === true,
  lazyRunnerAdds256Candidates:
    report.lazyRunner.additionalCandidateElementsPerSelectedHotVisit === 256,
  eagerTopologyAdds512Candidates:
    report.eagerRunner.netCandidateElementsVsRetained === 512,
  glyphsRiseFrom12To13:
    report.glyphWork.retainedGlyphsPerCandidate === 12 &&
      report.glyphWork.splitGlyphsPerCandidate === 13,
  conservativeAllowanceIs26Buckets:
    report.upperAllowance.requiredWrapperAllowanceBuckets === 26,
  empiricalBoundIsNotPortable:
    report.upperAllowance.empiricalChromeBoundOnly === true &&
      report.upperAllowance.portableBoundProved === false,
  fixtureGateHasNoUnsafeAccepts:
    report.fixtureSemantics.acceptedAtMarginGreaterThan4 === 19 &&
      report.fixtureSemantics.nearMarginFallbacks === 1 &&
      report.fixtureSemantics.unsafeAccepts === 0,
  corpusClaimWithheld: report.corpusSemantics.available === false,
  splitBankIsAdditive: report.assets.splitBankReplacesExactBank === false,
};

let indexExists = true;
try {
  await fs.access(path.join(experiment, "index.html"));
} catch {
  indexExists = false;
}
checks.noBrowserHtmlEmitted = !indexExists;

const pass = Object.values(checks).every(Boolean);
console.log(JSON.stringify({
  experiment: report.experiment,
  pass,
  browserLaunched: false,
  checks,
}, null, 2));

if (!pass) process.exitCode = 1;
